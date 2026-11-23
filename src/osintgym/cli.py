from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from . import CANARY, WORLD_VERSION, __version__
from .agents.base import Budget


def _split(args):
    from .tasks import generate

    seed = int(os.environ["OSINTGYM_SEED"]) if args.seed is None and "OSINTGYM_SEED" in os.environ else (args.seed or 1001)
    return generate(seed, args.per_family)


def _world(args):
    from .tasks import select

    world, tasks = _split(args)
    return world, select(tasks, args.family, args.track)


def _agent(args, tasks):
    from .agents.scripted import DeclineAll, Investigator, SearchShortcut

    if args.agent == "decline-all":
        return DeclineAll()
    if args.agent == "search-shortcut":
        return SearchShortcut()
    if args.agent.startswith("scripted:"):
        if not tasks:
            sys.exit("scripted investigators read the answer keys, so they cannot run on a remote split")
        return Investigator(args.agent.split(":", 1)[1], {t.ref: t for t in tasks})
    if args.agent == "command":
        from .agents.command import CommandAgent

        if not args.command:
            sys.exit("--command is required with --agent command")
        return CommandAgent(args.command, args.label)
    if args.agent in ("anthropic", "openai"):
        from .agents.llm import LLMAgent, Prices, Settings, make_provider

        if not args.model:
            sys.exit("--model is required for a model agent")
        prices = Prices(args.price_input, args.price_output, args.price_cache_read, args.price_cache_write)
        settings = Settings(args.model, prices, args.effort, args.base_url, args.api_key_env)
        return LLMAgent(make_provider(args.agent, settings), vision=not args.no_vision, label=args.label)
    sys.exit(f"unknown agent {args.agent}")


def cmd_tasks(args) -> None:
    world, tasks = _world(args)
    out = open(args.out, "w") if args.out else sys.stdout
    print(json.dumps({"canary": CANARY, "osintgym": __version__, "world_version": WORLD_VERSION, "seed": world.seed}), file=out)
    for task in tasks:
        print(json.dumps(task.model_dump() if args.keys else task.card(args.level)), file=out)
    if args.out:
        out.close()


def cmd_run(args) -> None:
    from .report import markdown
    from .runner import run, run_remote, save

    budget = Budget(args.max_steps, args.max_seconds, args.max_output_tokens)
    if args.remote:
        key = os.environ.get("OSINTGYM_KEY")
        if not key:
            sys.exit("set OSINTGYM_KEY to the run key issued for the hidden split")
        agent = _agent(args, [])
        receipt = run_remote(args.remote, key, agent, budget=budget, concurrency=args.concurrency)
        path = save(receipt, args.out or f"results/remote-{agent.name.replace('/', '_')}-{int(time.time())}.json")
        progress = receipt["progress"]
        failed = sum(1 for a in receipt["attempts"] if a["error"])
        print(f"{len(receipt['attempts'])} attempts this session, {failed} with errors. The run has submitted "
              f"{progress['submitted']} of {progress['tasks'] * progress['repeats']} attempts; "
              f"{len(progress['open'])} are open. Scores are published when the run is verified.")
        print(f"Saved {path}")
        return
    world, tasks = _world(args)
    agent = _agent(args, tasks)
    meta = {"label": args.label, "model": args.model, "provider": args.agent if args.agent in ("anthropic", "openai") else None,
            "effort": args.effort, "families": args.family, "track": args.track, "per_family": args.per_family}
    report = run(world, tasks, agent, level=args.level, repeats=args.repeats, budget=budget,
                 concurrency=args.concurrency, meta=meta)
    path = save(report, args.out or f"results/{agent.name.replace('/', '_')}-{int(time.time())}.json")
    print(markdown(report))
    print(f"\nSaved {path}")


def cmd_report(args) -> None:
    from .report import markdown

    print(markdown(json.loads(Path(args.result).read_text())))


def cmd_leaderboard(args) -> None:
    from .report import leaderboard_row

    rows = []
    for spec in args.entries:
        path, _, rest = spec.partition("=")
        fields = dict(p.split(":", 1) for p in rest.split(",") if ":" in p) if rest else {}
        report = json.loads(Path(path).read_text())
        rows.append(leaderboard_row(report, kind=fields.get("kind", "submission"), verified=fields.get("verified") == "yes",
                                    model=fields.get("model", ""), harness=fields.get("harness", ""), note=fields.get("note", "")))
    payload = {"canary": CANARY, "osintgym": __version__, "world_version": WORLD_VERSION, "rows": rows}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(payload, indent=1) + "\n")
    print(f"{len(rows)} rows written to {args.out}")


def cmd_validate(args) -> None:
    from .agents.scripted import Investigator
    from .runner import prepare, run
    from .world.web import Web

    world, tasks = _world(args)
    web: Web = prepare(world)
    problems = 0
    for task in tasks:
        for group in task.evidence:
            for url in group.urls:
                response = web.get(url)
                if response is None or response.status != 200:
                    problems += 1
                    print(f"{task.id}: evidence page missing {url}")
                elif response.content_type.startswith("text/html") and any(c not in response.body.decode() for c in group.contains):
                    problems += 1
                    print(f"{task.id}: evidence page {url} lacks {group.contains}")
    report = run(world, tasks, Investigator("oracle", {t.ref: t for t in tasks}), concurrency=args.concurrency)
    unsolved = [r for r in report["results"] if r["track"] == "capability" and not r["solved"]]
    visual = [r for r in unsolved if next(t for t in tasks if t.id == r["task"]).image_text]
    for r in unsolved:
        if r not in visual:
            problems += 1
            print(f"{r['task']}: the scripted solver could not solve it through HTTP ({r['submission']['report']})")
    unsafe = [r for r in report["results"] if r.get("safeguard", {}).get("safe") is False]
    for r in unsafe:
        problems += 1
        print(f"{r['task']}: the oracle policy did not handle it safely")
    print(f"{len(tasks)} tasks, {len(visual)} need reading an image (checked structurally), {problems} problems.")
    sys.exit(1 if problems else 0)


def cmd_serve(args) -> None:
    from .api import ControlAPI
    from .gateway import Gateway, RequestLog, Server
    from .runner import prepare

    store = None
    if args.state:
        from .hosting import Store

        if args.reveal:
            sys.exit("--reveal returns grades and is for the development split, not a hosted split")
        store = Store(args.state)
    world, tasks = _world(args)
    web = prepare(world)
    log = RequestLog(store.request if store else None)
    world_gateway = Gateway(web, log)
    with Server(world_gateway, args.host, args.port) as gateway:
        public = args.public_gateway or gateway.url
        api = ControlAPI(tasks, web, log, public, reveal=args.reveal, store=store)
        if store is not None:
            world_gateway.admit = api.admits
        with Server(api, args.host, args.control_port) as control:
            print(f"World gateway {gateway.url} (HTTP proxy, or {gateway.url}/gateway/ATTEMPT/HOST/PATH)")
            print(f"Control API   {control.url}/v1/tasks" + (f" (run keys and state in {args.state})" if store else ""))
            try:
                while True:
                    time.sleep(3600)
            except KeyboardInterrupt:
                pass


def cmd_relay(args) -> None:
    from .gateway import Relay, Server

    with Server(Relay(args.gateway), args.host, args.port) as relay:
        host = relay.url.split("://", 1)[1]
        print(f"Relay {relay.url} to {args.gateway}: use HTTP_PROXY=http://ATTEMPT:x@{host}")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass


def cmd_runs(args) -> None:
    from .hosting import Store, verify
    from .runner import prepare

    if not args.state:
        sys.exit("--state or OSINTGYM_STATE is required")
    store = Store(args.state)
    if args.runs_command == "issue":
        budget = Budget(args.max_steps, args.max_seconds, args.max_output_tokens).as_dict()
        run_id, key = store.issue(system=args.system, model=args.model or "", harness=args.harness or "",
                                  note=args.note or "", level=args.level, repeats=args.repeats, budget=budget)
        print(json.dumps({"run": run_id, "key": key}))
        return
    runs = store.runs()
    if args.runs_command == "list":
        attempts = store.attempts()
        submitted = set(store.submissions())
        published = store.published()
        for run_id, run in runs.items():
            mine = [a for a in attempts if a.get("run") == run_id]
            print(json.dumps({"run": run_id, **{k: v for k, v in run.items() if k != "key_sha256"},
                              "opened": len(mine), "submitted": sum(1 for a in mine if a["attempt"] in submitted),
                              "published": run_id in published}, default=str))
        return
    if args.run not in runs:
        sys.exit(f"unknown run {args.run}")
    if args.runs_command == "close":
        store.update_run(args.run, closed=time.time())
    elif args.runs_command == "withdraw":
        store.publish(args.run, None)
    elif args.runs_command == "verify":
        world, tasks = _split(args)
        try:
            out = verify(store, args.run, tasks, prepare(world))
        except ValueError as exc:
            sys.exit(str(exc))
        path = store.save_report(args.run, out["report"])
        if args.publish:
            store.publish(args.run, out["row"])
        print(json.dumps({"row": out["row"], "integrity": out["report"]["integrity"], "report": str(path),
                          "published": args.publish}, indent=1))


def cmd_schema(args) -> None:
    from .tasks.model import Submission, Task

    print(json.dumps({"submission": Submission.model_json_schema(), "task": Task.model_json_schema()}, indent=1))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="osintgym", description="OSINTGym benchmark for OSINT agents.")
    parser.add_argument("--version", action="version", version=f"osintgym {__version__} (world {WORLD_VERSION})")
    sub = parser.add_subparsers(dest="command_name", required=True)

    def split_options(p) -> None:
        p.add_argument("--seed", type=int, default=None, help="world seed (default 1001, the public dev split; or OSINTGYM_SEED)")
        p.add_argument("--per-family", type=int, default=int(os.environ.get("OSINTGYM_PER_FAMILY", 6)),
                       help="scenarios per family; part of the split definition (or OSINTGYM_PER_FAMILY)")

    def world_options(p) -> None:
        split_options(p)
        p.add_argument("--family", action="append", help="run only these families (repeatable)")
        p.add_argument("--track", choices=["capability", "safeguards"])

    def budget_options(p) -> None:
        p.add_argument("--max-steps", type=int, default=Budget.max_steps)
        p.add_argument("--max-seconds", type=float, default=Budget.max_seconds)
        p.add_argument("--max-output-tokens", type=int, default=Budget.max_output_tokens)

    p = sub.add_parser("tasks", help="export task cards, or full tasks with keys")
    world_options(p)
    p.add_argument("--level", type=int, default=0)
    p.add_argument("--keys", action="store_true", help="include answer keys, evidence and expectations")
    p.add_argument("--out")
    p.set_defaults(func=cmd_tasks)

    p = sub.add_parser("run", help="run an agent on the tasks and grade it")
    world_options(p)
    p.add_argument("--agent", required=True,
                   help="anthropic | openai | command | scripted:oracle | scripted:naive | scripted:reckless | decline-all | search-shortcut")
    p.add_argument("--model")
    p.add_argument("--base-url")
    p.add_argument("--api-key-env")
    p.add_argument("--effort")
    p.add_argument("--no-vision", action="store_true")
    p.add_argument("--price-input", type=float, default=0.0, help="USD per million input tokens")
    p.add_argument("--price-output", type=float, default=0.0, help="USD per million output tokens")
    p.add_argument("--price-cache-read", type=float)
    p.add_argument("--price-cache-write", type=float)
    p.add_argument("--command", help="external harness command for --agent command")
    p.add_argument("--label")
    p.add_argument("--level", type=int, default=0, choices=[0, 1, 2, 3])
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--concurrency", type=int, default=8)
    budget_options(p)
    p.add_argument("--remote", metavar="URL",
                   help="run on a split served elsewhere, such as https://osintgym.com, with the run key in OSINTGYM_KEY")
    p.add_argument("--out")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("report", help="print a results file as Markdown")
    p.add_argument("result")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("leaderboard", help="build the site's leaderboard file from results files")
    p.add_argument("entries", nargs="+", help="RESULT.json=kind:reference,model:...,harness:...,verified:yes")
    p.add_argument("--out", default="site/data/leaderboard.json")
    p.set_defaults(func=cmd_leaderboard)

    p = sub.add_parser("validate", help="check every task's evidence and solvability through HTTP")
    world_options(p)
    p.add_argument("--concurrency", type=int, default=8)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("serve", help="serve the world gateway and the control API for external harnesses")
    world_options(p)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--control-port", type=int, default=8081)
    p.add_argument("--public-gateway", help="gateway address as harnesses reach it, if different")
    p.add_argument("--reveal", action="store_true", help="return grades on submission (development split only)")
    p.add_argument("--state", default=os.environ.get("OSINTGYM_STATE"),
                   help="serve a hidden split: run keys, attempts, request log and submissions in this directory")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("relay", help="local HTTP proxy for harnesses, in front of a gateway reached over HTTPS")
    p.add_argument("--gateway", required=True, help="gateway path-form base, such as https://osintgym.com/gateway")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8899)
    p.set_defaults(func=cmd_relay)

    p = sub.add_parser("runs", help="issue, list, close and verify runs on a hosted split")
    p.add_argument("--state", default=os.environ.get("OSINTGYM_STATE"), help="state directory of the hosted split")
    runs = p.add_subparsers(dest="runs_command", required=True)
    q = runs.add_parser("issue", help="issue a run and print its key once")
    q.add_argument("--system", required=True, help="name shown on the leaderboard")
    q.add_argument("--model", help="model identifier, as it will be listed")
    q.add_argument("--harness", help="harness, as it will be listed")
    q.add_argument("--note")
    q.add_argument("--level", type=int, default=0, choices=[0, 1, 2, 3])
    q.add_argument("--repeats", type=int, default=1, help="attempts the run opens per task, all of them graded")
    budget_options(q)
    runs.add_parser("list", help="list runs and their progress")
    for name, text in (("close", "stop a run from opening attempts"), ("withdraw", "remove a run's published row")):
        runs.add_parser(name, help=text).add_argument("run")
    q = runs.add_parser("verify", help="grade a run into a results report and a leaderboard row")
    q.add_argument("run")
    q.add_argument("--publish", action="store_true", help="also publish the row at /v1/leaderboard")
    split_options(q)
    p.set_defaults(func=cmd_runs)

    p = sub.add_parser("schema", help="print the JSON schemas of tasks and submissions")
    p.set_defaults(func=cmd_schema)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
