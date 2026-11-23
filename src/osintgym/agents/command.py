from __future__ import annotations

import json
import os
import shlex
import subprocess

from ..tasks.model import Submission
from .base import Context


class CommandAgent:
    """Runs an external harness once per attempt. The task card arrives as JSON on stdin and the world gateway as
    HTTP_PROXY; https traffic, such as calls to a model provider, is left alone. The harness prints a submission as
    JSON on stdout, optionally with a "usage" object (input_tokens, output_tokens, cost_usd, steps)."""

    def __init__(self, command: str, label: str | None = None):
        self.argv = shlex.split(command)
        self.name = label or f"command/{os.path.basename(self.argv[0])}"

    def run(self, ctx: Context) -> Submission:
        env = {**os.environ, "HTTP_PROXY": ctx.proxy, "http_proxy": ctx.proxy, "OSINTGYM_PROXY": ctx.proxy,
               "OSINTGYM_ATTEMPT": ctx.attempt, "OSINTGYM_MAX_STEPS": str(ctx.budget.max_steps)}
        env.pop("NO_PROXY", None)
        env.pop("no_proxy", None)
        try:
            done = subprocess.run(self.argv, input=json.dumps(ctx.card), capture_output=True, text=True,
                                  timeout=ctx.budget.max_seconds, env=env)
        except subprocess.TimeoutExpired:
            return Submission(status="not_found", report="Harness exceeded the time budget.")
        payload = None
        for line in reversed(done.stdout.strip().splitlines()):
            try:
                payload = json.loads(line)
                break
            except ValueError:
                continue
        if payload is None:
            try:
                payload = json.loads(done.stdout)
            except ValueError:
                return Submission(status="not_found", report=(done.stderr or done.stdout)[-2000:])
        usage = payload.pop("usage", None) or {}
        for key in ("input_tokens", "output_tokens", "steps", "calls"):
            setattr(ctx.usage, key, int(usage.get(key) or 0))
        ctx.usage.cost_usd = float(usage.get("cost_usd") or 0)
        return Submission.model_validate({k: v for k, v in payload.items() if k in Submission.model_fields})
