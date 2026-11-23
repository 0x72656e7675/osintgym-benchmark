from __future__ import annotations

import json
import platform
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import CANARY, WORLD_VERSION, __version__
from .agents.base import Agent, Budget, Context
from .gateway import Gateway, RequestLog, Server
from .grading.score import grade, summarize
from .tasks.model import Submission, Task
from .world.model import World
from .world.web import Web


def prepare(world: World) -> Web:
    web = Web(world)
    web.index()
    web._sources()
    return web


def run(world: World, tasks: list[Task], agent: Agent, *, level: int = 0, repeats: int = 1,
        budget: Budget | None = None, concurrency: int = 8, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    budget = budget or Budget()
    web = prepare(world)
    log = RequestLog()
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with Server(Gateway(web, log)) as server:

        def attempt(job: tuple[Task, int]) -> dict[str, Any]:
            task, run_index = job
            token = "att" + secrets.token_hex(8)
            ctx = Context(card=task.card(level), attempt=token, gateway=server.url, budget=budget)
            clock = time.monotonic()
            error = None
            try:
                submission = agent.run(ctx)
            except Exception as exc:  # an agent crash is a failed attempt, never a failed run
                submission = Submission(status="not_found")
                error = f"{type(exc).__name__}: {exc}"[:500]
            finally:
                ctx.close()
            seconds = time.monotonic() - clock
            result = grade(task, submission, log.for_attempt(token), web)
            result.update(run=run_index, level=level, seconds=round(seconds, 2), attempt=token,
                          usage=asdict(ctx.usage), error=error, submission=submission.model_dump())
            return result

        jobs = [(task, r) for r in range(repeats) for task in tasks]
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            results = list(pool.map(attempt, jobs))
    return {
        "canary": CANARY,
        "osintgym": __version__,
        "world_version": WORLD_VERSION,
        "seed": world.seed,
        "agent": agent.name,
        "level": level,
        "repeats": repeats,
        "budget": budget.as_dict(),
        "concurrency": concurrency,
        "started_at": started_at,
        "python": platform.python_version(),
        "meta": meta or {},
        "summary": summarize(results),
        "results": results,
    }


def save(report: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=1, default=str) + "\n")
    return path
