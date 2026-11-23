from __future__ import annotations

import hashlib
import json
import os
import platform
import secrets
import threading
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import CANARY, WORLD_VERSION, __version__
from .gateway import Entry
from .grading.score import MAX_COUNTED_CITATIONS, grade, summarize
from .report import leaderboard_row
from .tasks.model import Submission, Task
from .world.web import Web, canonical, split_url


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class Store:
    """What a hosted split keeps on disk: issued runs, known only by the digest of their key, the attempts they
    opened, the request log, the submissions, and the rows published from verified runs. The service appends the
    logs; the runs command edits runs and published rows. Only published rows are ever served."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._files: dict[str, Any] = {}
        self._runs: dict[str, dict[str, Any]] = {}
        self._stamp: int | None = None

    def _append(self, name: str, record: dict[str, Any]) -> None:
        with self._lock:
            handle = self._files.get(name)
            if handle is None:
                handle = self._files[name] = open(self.root / name, "a", buffering=1)
            handle.write(json.dumps(record, default=str) + "\n")

    def _read(self, name: str) -> list[dict[str, Any]]:
        path = self.root / name
        if not path.exists():
            return []
        records = []
        with open(path) as handle:
            for line in handle:
                try:
                    records.append(json.loads(line))
                except ValueError:  # the last line may still be being written
                    continue
        return records

    def _load(self, name: str) -> dict[str, Any]:
        path = self.root / name
        return json.loads(path.read_text()) if path.exists() else {}

    def _write(self, name: str, data: Any) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        draft = path.with_name(f".{path.name}.{os.getpid()}")
        draft.write_text(json.dumps(data, indent=1, default=str) + "\n")
        os.replace(draft, path)

    @contextmanager
    def _exclusive(self):
        import fcntl

        with open(self.root / ".lock", "a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    def runs(self) -> dict[str, dict[str, Any]]:
        try:
            stamp = (self.root / "runs.json").stat().st_mtime_ns
        except FileNotFoundError:
            return {}
        if stamp != self._stamp:
            self._runs, self._stamp = self._load("runs.json"), stamp
        return self._runs

    def run_for_key(self, key: str) -> tuple[str, dict[str, Any]] | None:
        digest = _digest(key)
        for run_id, run in self.runs().items():
            if secrets.compare_digest(run["key_sha256"], digest):
                return run_id, run
        return None

    def issue(self, **meta: Any) -> tuple[str, str]:
        key = "ogk_" + secrets.token_urlsafe(24)
        with self._exclusive():
            runs = self._load("runs.json")
            run_id = "run_" + secrets.token_hex(4)
            runs[run_id] = {"key_sha256": _digest(key), "created": time.time(), "closed": None, **meta}
            self._write("runs.json", runs)
        return run_id, key

    def update_run(self, run_id: str, **changes: Any) -> None:
        with self._exclusive():
            runs = self._load("runs.json")
            runs[run_id].update(changes)
            self._write("runs.json", runs)

    def opened(self, record: dict[str, Any]) -> None:
        self._append("attempts.jsonl", record)

    def request(self, entry: Entry) -> None:
        self._append("requests.jsonl", asdict(entry))

    def submitted(self, record: dict[str, Any]) -> None:
        self._append("submissions.jsonl", record)

    def attempts(self) -> list[dict[str, Any]]:
        return self._read("attempts.jsonl")

    def submissions(self) -> dict[str, dict[str, Any]]:
        return {r["attempt"]: r for r in self._read("submissions.jsonl")}

    def open_attempts(self) -> list[dict[str, Any]]:
        done = self.submissions()
        return [a for a in self.attempts() if a["attempt"] not in done]

    def entries(self, attempts: set[str]) -> list[Entry]:
        return [Entry(**r) for r in self._read("requests.jsonl") if r.get("attempt") in attempts]

    def publish(self, run_id: str, row: dict[str, Any] | None) -> None:
        with self._exclusive():
            rows = self._load("leaderboard.json")
            if row is None:
                rows.pop(run_id, None)
            else:
                rows[run_id] = row
            self._write("leaderboard.json", rows)

    def published(self) -> dict[str, dict[str, Any]]:
        return self._load("leaderboard.json")

    def save_report(self, run_id: str, report: dict[str, Any]) -> Path:
        self._write(f"reports/{run_id}.json", report)
        return self.root / "reports" / f"{run_id}.json"


def verify(store: Store, run_id: str, tasks: list[Task], web: Web) -> dict[str, Any]:
    """Grades a run on the hidden split into a results report and a leaderboard row. Every task of the split counts,
    each as many times as the run's repeats, in the order its attempts were opened: an attempt never submitted, or
    never opened, is graded as not found, so neither retries nor skipped tasks can lift a score."""
    run = store.runs()[run_id]
    attempts = [a for a in store.attempts() if a.get("run") == run_id]
    versions = {a["world_version"] for a in attempts} - {WORLD_VERSION}
    if versions:
        raise ValueError(f"attempts of {run_id} were made on world {sorted(versions)}, this build serves {WORLD_VERSION}")
    submissions = store.submissions()
    entries: dict[str, list[Entry]] = defaultdict(list)
    for entry in store.entries({a["attempt"] for a in attempts}):
        entries[entry.attempt].append(entry)
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        by_task[attempt["ref"]].append(attempt)
    integrity: Counter[str] = Counter()
    results = []
    for task in tasks:
        opened = by_task.get(task.ref or task.id, [])
        integrity["beyond_repeats"] += max(0, len(opened) - run["repeats"])
        for index in range(run["repeats"]):
            attempt = opened[index] if index < len(opened) else None
            record = submissions.get(attempt["attempt"]) if attempt else None
            integrity["submitted" if record else "unsubmitted" if attempt else "never_opened"] += 1
            submission = Submission.model_validate(record["submission"]) if record else Submission(status="not_found")
            mine = entries.get(attempt["attempt"], []) if attempt else []
            result = grade(task, submission, mine, web)
            result.update(run=index, level=run["level"], attempt=attempt["attempt"] if attempt else None,
                          seconds=round(record["submitted"] - attempt["opened"], 2) if record else 0,
                          usage=record.get("usage") or {} if record else {}, submission=submission.model_dump())
            if result["solved"]:
                visited = {canonical(e.url) for e in mine if e.in_world}
                cited = submission.cited_urls()[:MAX_COUNTED_CITATIONS]
                if any(web.is_world_host(split_url(u)[0]) and canonical(u) not in visited for u in cited):
                    integrity["solved_citing_unrequested_pages"] += 1
            results.append(result)
    started = min((a["opened"] for a in attempts), default=time.time())
    report = {
        "canary": CANARY,
        "osintgym": __version__,
        "world_version": WORLD_VERSION,
        "seed": "hidden",
        "split": "test",
        "agent": run["system"],
        "level": run["level"],
        "repeats": run["repeats"],
        "budget": run.get("budget"),
        "concurrency": None,
        "started_at": datetime.fromtimestamp(started, timezone.utc).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "meta": {"run": run_id, **{k: run.get(k) for k in ("model", "harness", "note")}},
        "integrity": dict(+integrity),
        "summary": summarize(results),
        "results": results,
    }
    row = leaderboard_row(report, kind="submission", verified=True, model=run.get("model") or "",
                          harness=run.get("harness") or "", note=run.get("note") or "")
    return {"report": report, "row": row}
