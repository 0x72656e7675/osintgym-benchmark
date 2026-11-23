from __future__ import annotations

import json
import secrets
import threading
import time
from collections import Counter
from typing import TYPE_CHECKING, Any

from . import CANARY, WORLD_VERSION, __version__
from .gateway import PATH_PREFIX, RequestLog
from .grading.score import grade, summarize
from .tasks.model import Submission, Task
from .world.web import Web

if TYPE_CHECKING:
    from .hosting import Store

USAGE_KEYS = ("input_tokens", "output_tokens", "cost_usd", "steps", "calls")


def _usage(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {k: value[k] for k in USAGE_KEYS if isinstance(value.get(k), (int, float)) and not isinstance(value[k], bool)}


class ControlAPI:
    """Control plane for harnesses that run elsewhere: list task cards, open an attempt (which returns how to reach the
    world through the gateway), submit an answer. Answer keys never leave this process.

    With a store it serves a hidden split: every call needs the key of a run issued by the host, a run opens as many
    attempts per task as its repeats, and submissions are graded and kept on disk without returning anything about
    them; scores come only from verifying the whole run."""

    def __init__(self, tasks: list[Task], web: Web, log: RequestLog, gateway: str, *, reveal: bool = False,
                 store: Store | None = None):
        self.tasks = {t.ref or t.id: t for t in tasks}
        self.web = web
        self.log = log
        self.gateway = (gateway if "://" in gateway else f"http://{gateway}").rstrip("/")
        self.reveal = reveal
        self.store = store
        self.attempts: dict[str, dict[str, Any]] = {}
        self.opened: Counter[tuple[str, str]] = Counter()
        self.results: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        if store is not None:
            for attempt in store.attempts():
                self.opened[attempt["run"], attempt["ref"]] += 1
            self.attempts = {a["attempt"]: a for a in store.open_attempts()}
            log.restore(store.entries(set(self.attempts)))

    def admits(self, attempt: str | None) -> bool:
        with self._lock:
            return attempt in self.attempts

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["type"] != "http":
            return
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body") or len(body) > 2_000_000:
                break
        authorization = next((v.decode("latin-1") for k, v in scope["headers"] if k.lower() == b"authorization"), "")
        status, payload = self.route(scope["method"], scope["path"].rstrip("/"), scope.get("query_string", b"").decode(),
                                     body, authorization)
        data = json.dumps(payload, default=str).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(data)).encode()),
                                (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": data})

    def route(self, method: str, path: str, query: str, body: bytes, authorization: str = "") -> tuple[int, Any]:
        if method == "GET" and path == "/healthz":
            return 200, {"ok": True}
        if method == "GET" and path == "/v1/leaderboard":
            rows = list(self.store.published().values()) if self.store is not None else []
            return 200, {"canary": CANARY, "osintgym": __version__, "world_version": WORLD_VERSION, "rows": rows}
        level = 0
        for pair in query.split("&"):
            if pair.startswith("level=") and pair[6:].isdigit():
                level = int(pair[6:])
        run_id, run = None, None
        if self.store is not None:
            found = self.store.run_for_key(authorization[7:].strip()) if authorization[:7].lower() == "bearer " else None
            if found is None:
                return 401, {"error": "a run key is required: Authorization: Bearer KEY"}
            run_id, run = found
            level = run["level"]
        if method == "GET" and path == "/v1/tasks":
            return 200, [task.card(level) for task in self.tasks.values()]
        if method == "GET" and path == "/v1/summary":
            if run_id is not None:
                return 200, self.progress(run_id, run)
            with self._lock:
                return 200, summarize(self.results)
        try:
            data = json.loads(body or b"{}")
        except ValueError:
            return 400, {"error": "body is not JSON"}
        if not isinstance(data, dict):
            return 400, {"error": "body is not a JSON object"}
        if method == "POST" and path == "/v1/attempts":
            ref = str(data.get("task"))
            task = self.tasks.get(ref)
            if task is None:
                return 404, {"error": "unknown task"}
            try:
                asked = int(data.get("level", level))
            except (TypeError, ValueError):
                return 400, {"error": "level is not a number"}
            if run is not None and asked != level:
                return 400, {"error": f"this run is at level {level}"}
            level = asked
            token = "att" + secrets.token_hex(8)
            record = {"attempt": token, "ref": ref, "task": task.id, "level": level,
                      "harness": str(data.get("harness", ""))[:200]}
            with self._lock:
                if run is not None:
                    if run.get("closed"):
                        return 403, {"error": "this run is closed"}
                    if self.opened[run_id, ref] >= run["repeats"]:
                        return 409, {"error": f"this run has opened its {run['repeats']} attempt(s) for this task"}
                    record.update(run=run_id, opened=time.time(), osintgym=__version__, world_version=WORLD_VERSION)
                    self.store.opened(record)
                    self.opened[run_id, ref] += 1
                self.attempts[token] = record
            opened = {"attempt": token, "card": task.card(level), "gateway": f"{self.gateway}{PATH_PREFIX}{token}"}
            if self.gateway.startswith("http://"):
                opened["proxy"] = f"http://{token}:x@{self.gateway.split('://', 1)[1]}"
            return 201, opened
        if method == "POST" and path.startswith("/v1/attempts/") and path.endswith("/submission"):
            token = path.split("/")[3]
            usage = _usage(data.pop("usage", None))
            try:
                submission = Submission.model_validate({k: v for k, v in data.items() if k in Submission.model_fields})
            except ValueError as exc:
                return 422, {"error": str(exc)[:500]}
            with self._lock:
                attempt = self.attempts.get(token)
                if attempt is None or attempt.get("run") != run_id:
                    return 404, {"error": "unknown or already submitted attempt"}
                del self.attempts[token]
            result = grade(self.tasks[attempt["ref"]], submission, self.log.for_attempt(token), self.web)
            result.update(level=attempt["level"], attempt=token, harness=attempt["harness"], usage=usage)
            if self.store is not None:
                now = time.time()
                result["seconds"] = round(now - attempt["opened"], 2)
                self.store.submitted({"attempt": token, "run": run_id, "submitted": now,
                                      "submission": submission.model_dump(), "usage": usage, "result": result})
                self.log.forget(token)
                return 200, {"received": True}
            with self._lock:
                self.results.append(result)
            return 200, {"received": True, **({"result": result} if self.reveal else {})}
        return 404, {"error": "not found"}

    def progress(self, run_id: str, run: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            mine = [{"attempt": a["attempt"], "task": a["ref"]} for a in self.attempts.values() if a.get("run") == run_id]
            used = {ref: n for (r, ref), n in self.opened.items() if r == run_id}
        remaining = [ref for ref in self.tasks for _ in range(max(0, run["repeats"] - used.get(ref, 0)))]
        return {
            "run": run_id, "level": run["level"], "repeats": run["repeats"], "tasks": len(self.tasks),
            "opened": sum(used.values()), "submitted": sum(used.values()) - len(mine), "open": mine,
            "remaining": remaining, "closed": bool(run.get("closed")), "gateway": self.gateway + PATH_PREFIX.rstrip("/"),
        }
