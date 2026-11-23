from __future__ import annotations

from typing import Any

FAMILY_NAMES = {
    "ident.handle": "Pseudonymous account attribution",
    "ident.profiles": "Account verification against namesakes",
    "entity.site": "Website attribution",
    "org.members": "Organisation member mapping",
    "infer.city": "Location inference",
    "imint.geolocate": "Photo geolocation",
    "finint.ubo": "Beneficial ownership",
    "finint.sanctions": "Sanctions screening",
    "verif.archive": "Deleted content recovery",
}

SAFEGUARD_NAMES = {
    "harmful_refusal": "Harmful requests declined without pursuit or disclosure",
    "legitimate_completion": "Matched legitimate requests carried out",
    "injection_resistance": "Tasks solved without obeying injected instructions",
    "minimisation": "Tasks solved without repeating protected data",
    "passive_collection": "Tasks solved without contacting the subject",
    "injection_attack_success": "Injected instructions obeyed, among exposed attempts",
    "minimisation_leak": "Answers repeating protected data, among exposed attempts",
    "active_contact": "Attempts that contacted a subject",
    "unstated_decline": "Unstated-purpose requests declined (reported, not scored)",
}


def _fmt(value: Any, suffix: str = "") -> str:
    return "n/a" if value is None else f"{value}{suffix}"


def markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    cap, guard, eff = s["capability"], s["safeguards"], s["efficiency"]
    budget = report.get("budget", {})
    out = [
        f"# OSINTGym results for {report['agent']}",
        "",
        (f"World {report['world_version']} with seed {report['seed']}, context level {report['level']}, "
         f"{report['repeats']} run per task, {s['attempts']} attempts, OSINTGym {report['osintgym']}. Budget per attempt: "
         f"{budget.get('max_steps')} steps, {budget.get('max_seconds')} seconds, {budget.get('max_output_tokens')} output "
         "tokens per call."),
        "",
        "| Headline | Value |",
        "|---|---|",
        f"| Capability score | {_fmt(cap['score'])} (95% CI {cap['ci95'][0] if cap['ci95'] else 'n/a'} to {cap['ci95'][1] if cap['ci95'] else 'n/a'}) |",
        f"| Answer accuracy | {_fmt(cap['accuracy'])} |",
        f"| Tasks solved | {_fmt(cap['solved'], '%')} |",
        f"| Solved with full attribution | {_fmt(cap['attribution'], '%')} |",
        f"| Fabricated citations | {cap['fabricated_citations']} |",
        f"| Calibration (Brier) | {_fmt(cap['brier'])} |",
        f"| Safeguard score | {_fmt(guard['score'])} |",
        f"| Cost per solved task | {_fmt(eff['cost_per_solved_task_usd'], ' USD')} |",
        "",
        "| Capability family | Score |",
        "|---|---|",
    ]
    out += [f"| {FAMILY_NAMES.get(k, k)} | {v} |" for k, v in cap["families"].items()]
    out += ["", "| Safeguard component | Rate |", "|---|---|"]
    out += [f"| {SAFEGUARD_NAMES.get(k, k)} | {_fmt(v, '%')} |" for k, v in guard.items() if k != "score"]
    out += ["", "| Efficiency | Value |", "|---|---|",
            f"| Input tokens | {eff['input_tokens']} |", f"| Output tokens | {eff['output_tokens']} |",
            f"| Cost | {eff['cost_usd']} USD |", f"| Mean seconds per attempt | {eff['mean_seconds']} |",
            f"| Mean requests per attempt | {eff['mean_requests']} |",
            f"| Requests outside the world | {eff['out_of_world_requests']} |", ""]
    return "\n".join(out)


def leaderboard_row(report: dict[str, Any], *, kind: str, verified: bool, model: str, harness: str,
                    note: str = "") -> dict[str, Any]:
    s = report["summary"]
    return {
        "system": report["agent"], "model": model, "harness": harness, "kind": kind, "verified": verified, "note": note,
        "date": report["started_at"][:10], "osintgym": report["osintgym"], "world_version": report["world_version"],
        "seed": report["seed"], "level": report["level"], "repeats": report["repeats"], "budget": report.get("budget"),
        "capability": s["capability"]["score"], "ci95": s["capability"]["ci95"], "accuracy": s["capability"]["accuracy"],
        "solved": s["capability"]["solved"], "attribution": s["capability"]["attribution"],
        "families": s["capability"]["families"], "safeguards": s["safeguards"],
        "cost_usd": s["efficiency"]["cost_usd"], "cost_per_solved_task_usd": s["efficiency"]["cost_per_solved_task_usd"],
        "mean_seconds": s["efficiency"]["mean_seconds"],
    }
