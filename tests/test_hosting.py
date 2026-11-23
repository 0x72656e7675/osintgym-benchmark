import json
import sys
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest

from osintgym.agents.command import CommandAgent
from osintgym.api import ControlAPI
from osintgym.cli import main
from osintgym.gateway import Gateway, Relay, RequestLog, Server
from osintgym.hosting import Store, verify
from osintgym.runner import prepare, run_remote
from osintgym.tasks import generate

HARNESS = Path(__file__).with_name("tiny_harness.py")


@pytest.fixture(scope="module")
def dev():
    world, tasks = generate()
    return world, tasks, prepare(world)


def through(gateway: str, url: str) -> str:
    parts = urlsplit(url)
    return f"{gateway}/{parts.netloc}{parts.path or '/'}" + (f"?{parts.query}" if parts.query else "")


@contextmanager
def hosted(tasks, web, store):
    log = RequestLog(store.request)
    world_gateway = Gateway(web, log)
    with Server(world_gateway) as gateway:
        api = ControlAPI(tasks, web, log, gateway.url, store=store)
        world_gateway.admit = api.admits
        with Server(api) as control:
            yield control, api


def test_path_form_serves_the_same_world_as_the_proxy(dev):
    world, _, web = dev
    log = RequestLog()
    handle = next(a.handle for a in world.accounts.values() if a.site == "murmur")
    with Server(Gateway(web, log)) as server:
        with httpx.Client(proxy=f"http://att-proxy:x@127.0.0.1:{server.port}") as client:
            proxied = client.get("http://search.test/search?q=harbour%20road")
        base = f"{server.url}/gateway/att-path"
        direct = httpx.get(through(base, "http://search.test/search?q=harbour%20road"))
        assert direct.status_code == 200 and direct.content == proxied.content
        assert direct.headers["cache-control"] == "no-store, no-transform"
        assert httpx.post(f"{base}/murmur.test/@{handle}/follow", data={}).status_code == 200
        assert httpx.get(f"{base}/example.com/").status_code == 502
        assert httpx.get(f"{server.url}/healthz").text == "ok\n"
    mine = log.for_attempt("att-path")
    assert [e.url for e in mine] == [log.for_attempt("att-proxy")[0].url, f"http://murmur.test/@{handle}/follow",
                                     "http://example.com/"]
    assert [e.in_world for e in mine] == [True, True, False]
    assert mine[1].event["kind"] == "follow"
    assert len(log.entries) == 4


def test_gateway_serves_only_admitted_attempts(dev):
    _, _, web = dev
    log = RequestLog()
    with Server(Gateway(web, log, admit=lambda attempt: attempt == "att-open")) as server:
        assert httpx.get(f"{server.url}/gateway/att-open/atlas.test/").status_code == 200
        assert httpx.get(f"{server.url}/gateway/att-other/atlas.test/").status_code == 403
        with httpx.Client(proxy=f"http://att-other:x@127.0.0.1:{server.port}") as client:
            assert client.get("http://atlas.test/").status_code == 403
    assert [e.attempt for e in log.entries] == ["att-open"]


def test_relay_carries_proxy_clients_to_the_path_form(dev):
    world, _, web = dev
    log = RequestLog()
    handle = next(a.handle for a in world.accounts.values() if a.site == "murmur")
    with Server(Gateway(web, log)) as gateway, Server(Relay(f"{gateway.url}/gateway")) as relay:
        with httpx.Client(proxy=f"http://att-r:x@127.0.0.1:{gateway.port}") as client:
            expected = client.get(f"http://murmur.test/@{handle}").content
        with httpx.Client(proxy=f"http://att-relay:x@127.0.0.1:{relay.port}") as client:
            page = client.get(f"http://murmur.test/@{handle}")
            assert page.status_code == 200 and page.content == expected
            assert client.post(f"http://murmur.test/@{handle}/message", data={"text": "hi"}).status_code == 200
            assert client.get("http://example.com/").status_code == 502
        assert httpx.get(f"{relay.url}/", follow_redirects=False).status_code == 407
    mine = log.for_attempt("att-relay")
    assert [(e.method, e.in_world) for e in mine] == [("GET", True), ("POST", True), ("GET", False)]
    assert mine[1].event == {"kind": "message", "site": "murmur", "target": mine[1].event["target"], "fields": {"text": "hi"}}


def test_hidden_split_keeps_keys_grades_and_log_on_the_server(dev, tmp_path):
    _, tasks, web = dev
    store = Store(tmp_path)
    run_id, key = store.issue(system="test", model="m", harness="h", note="", level=1, repeats=1, budget=None)
    target = next(t for t in tasks if t.id == "finint.ubo/00")
    other = next(t for t in tasks if t.id == "ident.handle/00")
    auth = {"Authorization": f"Bearer {key}"}
    with hosted(tasks, web, store) as (control, _):
        assert httpx.get(f"{control.url}/v1/tasks").status_code == 401
        assert httpx.get(f"{control.url}/v1/tasks", headers={"Authorization": "Bearer ogk_wrong"}).status_code == 401
        cards = httpx.get(f"{control.url}/v1/tasks?level=0", headers=auth).json()
        assert all(len(card["hints"]) == min(1, len(t.hints)) for card, t in zip(cards, tasks))
        assert httpx.post(f"{control.url}/v1/attempts", headers=auth, json={"task": target.ref, "level": 0}).status_code == 400
        opened = httpx.post(f"{control.url}/v1/attempts", headers=auth, json={"task": target.ref, "harness": "t"}).json()
        assert httpx.post(f"{control.url}/v1/attempts", headers=auth, json={"task": target.ref}).status_code == 409
        cited = [u for group in target.evidence for u in group.urls][:12]
        for url in cited:
            assert httpx.get(through(opened["gateway"], url)).status_code == 200
        left_open = httpx.post(f"{control.url}/v1/attempts", headers=auth, json={"task": other.ref}).json()
        assert httpx.get(through(left_open["gateway"], other.seed[0])).status_code == 200
        progress = httpx.get(f"{control.url}/v1/summary", headers=auth).json()
        assert progress["opened"] == 2 and progress["submitted"] == 0 and len(progress["remaining"]) == len(tasks) - 2
    with hosted(tasks, web, Store(tmp_path)) as (control, api):
        assert api.admits(opened["attempt"]) and api.admits(left_open["attempt"])
        owners = [{"name": m.name, "url": m.urls[0]} for m in target.fields[0].members]
        submission = {"status": "answered", "answer": {"beneficial_owners": owners}, "evidence": cited, "report": "",
                      "usage": {"input_tokens": 10, "cost_usd": "free"}}
        url = f"{control.url}/v1/attempts/{opened['attempt']}/submission"
        assert httpx.post(url, json=submission).status_code == 401
        assert httpx.post(url, headers=auth, json=submission).json() == {"received": True}
        assert httpx.post(url, headers=auth, json=submission).status_code == 404
        assert httpx.get(through(f"{api.gateway}/gateway/{opened['attempt']}", target.seed[0])).status_code == 403
        assert httpx.get(f"{control.url}/v1/leaderboard").json()["rows"] == []
    stored = store.submissions()[opened["attempt"]]
    assert stored["result"]["solved"] and stored["result"]["requests"] == len(cited)
    assert stored["usage"] == {"input_tokens": 10}

    out = verify(store, run_id, tasks, web)
    row, integrity = out["row"], out["report"]["integrity"]
    assert row["verified"] and row["kind"] == "submission" and row["seed"] == "hidden" and row["level"] == 1
    assert integrity == {"submitted": 1, "unsubmitted": 1, "never_opened": len(tasks) - 2}
    assert len(out["report"]["results"]) == len(tasks)
    capability = [r for r in out["report"]["results"] if r["track"] == "capability"]
    assert row["capability"] == round(100 * sum(r["score"] for r in capability) / len(capability), 1) > 0
    unsubmitted = next(r for r in out["report"]["results"] if r["attempt"] == left_open["attempt"])
    assert unsubmitted["status"] == "not_found" and unsubmitted["requests"] == 1
    store.publish(run_id, row)
    with hosted(tasks, web, Store(tmp_path)) as (control, _):
        assert httpx.get(f"{control.url}/v1/leaderboard").json()["rows"] == [row]


def test_remote_run_drives_a_command_harness_through_the_relay(dev, tmp_path):
    _, tasks, web = dev
    subset = [t for t in tasks if t.id in ("imint.geolocate/00", "entity.site/00", "safe.opsec/00")]
    store = Store(tmp_path)
    run_id, key = store.issue(system="remote", level=0, repeats=1, budget=None)
    with hosted(subset, web, store) as (control, _):
        receipt = run_remote(control.url, key, CommandAgent(f"{sys.executable} {HARNESS}"), concurrency=2)
        assert [a["error"] for a in receipt["attempts"]] == [None] * 3
        assert {a["status"] for a in receipt["attempts"]} == {"answered"}
        assert receipt["progress"]["submitted"] == 3 and receipt["progress"]["remaining"] == []
        assert run_remote(control.url, key, CommandAgent(f"{sys.executable} {HARNESS}"))["attempts"] == []
    submissions = store.submissions()
    assert len(submissions) == 3 and all(s["usage"]["input_tokens"] == 7 for s in submissions.values())
    entries = store.entries(set(submissions))
    assert len(entries) == 3 and all(e.in_world and e.status == 200 for e in entries)
    assert verify(store, run_id, subset, web)["report"]["integrity"] == {"submitted": 3}


def test_runs_command_issues_verifies_and_publishes(tmp_path, capsys, monkeypatch):
    for name in ("OSINTGYM_SEED", "OSINTGYM_PER_FAMILY", "OSINTGYM_STATE"):
        monkeypatch.delenv(name, raising=False)
    state = ["runs", "--state", str(tmp_path)]
    main(state + ["issue", "--system", "Example agent", "--model", "example-model", "--repeats", "2"])
    issued = json.loads(capsys.readouterr().out)
    assert issued["key"].startswith("ogk_") and issued["key"] not in (tmp_path / "runs.json").read_text()
    main(state + ["list"])
    listed = json.loads(capsys.readouterr().out)
    assert listed["run"] == issued["run"] and listed["repeats"] == 2 and "key_sha256" not in listed
    main(state + ["verify", issued["run"], "--publish", "--per-family", "1"])
    verified = json.loads(capsys.readouterr().out)
    assert verified["row"]["system"] == "Example agent" and verified["row"]["capability"] == 0
    assert verified["integrity"]["never_opened"] == 2 * 15
    assert Store(tmp_path).published() == {issued["run"]: verified["row"]}
    main(state + ["withdraw", issued["run"]])
    main(state + ["close", issued["run"]])
    store = Store(tmp_path)
    assert store.published() == {} and store.runs()[issued["run"]]["closed"]
