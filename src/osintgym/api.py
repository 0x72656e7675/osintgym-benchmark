from __future__ import annotations

import json
import secrets
import threading
from typing import Any

from .grading.score import grade, summarize
from .gateway import RequestLog
from .tasks.model import Submission, Task
from .world.web import Web


class ControlAPI:
    """Control plane for harnesses that run elsewhere: list task cards, open an attempt (which returns the proxy
    credentials to reach the world through the gateway), submit an answer. Answer keys never leave this process."""

    def __init__(self, tasks: list[Task], web: Web, log: RequestLog, gateway: str, *, reveal: bool = False):
        self.tasks = {t.id: t for t in tasks}
        self.web = web
        self.log = log
        self.gateway = gateway.split("://", 1)[-1]
        self.reveal = reveal
        self.attempts: dict[str, dict[str, Any]] = {}
        self.results: list[dict[str, Any]] = []
        self._lock = threading.Lock()

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
        status, payload = self.route(scope["method"], scope["path"].rstrip("/"), scope.get("query_string", b"").decode(), body)
        data = json.dumps(payload, default=str).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(data)).encode())]})
        await send({"type": "http.response.body", "body": data})

    def route(self, method: str, path: str, query: str, body: bytes) -> tuple[int, Any]:
        level = 0
        for pair in query.split("&"):
            if pair.startswith("level=") and pair[6:].isdigit():
                level = int(pair[6:])
        if method == "GET" and path == "/v1/tasks":
            return 200, [task.card(level) for task in self.tasks.values()]
        if method == "GET" and path == "/v1/summary":
            with self._lock:
                return 200, summarize(self.results)
        try:
            data = json.loads(body or b"{}")
        except ValueError:
            return 400, {"error": "body is not JSON"}
        if method == "POST" and path == "/v1/attempts":
            task = self.tasks.get(str(data.get("task")))
            if task is None:
                return 404, {"error": "unknown task"}
            level = int(data.get("level", level))
            token = "att" + secrets.token_hex(8)
            with self._lock:
                self.attempts[token] = {"task": task.id, "level": level, "harness": str(data.get("harness", ""))[:200]}
            return 201, {"attempt": token, "proxy": f"http://{token}:x@{self.gateway}", "card": task.card(level)}
        if method == "POST" and path.startswith("/v1/attempts/") and path.endswith("/submission"):
            token = path.split("/")[3]
            with self._lock:
                attempt = self.attempts.pop(token, None)
            if attempt is None:
                return 404, {"error": "unknown or already submitted attempt"}
            usage = data.pop("usage", None) or {}
            try:
                submission = Submission.model_validate({k: v for k, v in data.items() if k in Submission.model_fields})
            except ValueError as exc:
                return 422, {"error": str(exc)[:500]}
            result = grade(self.tasks[attempt["task"]], submission, self.log.for_attempt(token), self.web)
            result.update(level=attempt["level"], attempt=token, harness=attempt["harness"], usage=usage)
            with self._lock:
                self.results.append(result)
            return 200, {"received": True, **({"result": result} if self.reveal else {})}
        return 404, {"error": "not found"}
