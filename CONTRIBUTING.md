# Contributing

Contributions are welcome: new task families, sharper decoys, harness adapters, grading fixes and documentation.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,anthropic]"
pytest
osintgym validate
```

`pytest` covers grading, determinism across hash seeds, the gateway and its path form, the control API, a hosted
split and end-to-end runs of the scripted agents. `osintgym validate` must report no problems before a change to generation is merged.

## Adding a task family

A family is a function `plant(builder, index) -> list[Task]` registered in `src/osintgym/tasks/capability.py` or
`safeguards.py`. It draws randomness only from `builder.rng(key)` keyed on its own scenario, plants its entities
and decoys through the builder, and returns tasks whose evidence groups name the pages that establish each step.
Add a solver to the scripted investigator so `validate` can prove the family is solvable through HTTP, and make sure
a shallow search cannot solve it. Any change to what a seed produces bumps `WORLD_VERSION` in
`src/osintgym/__init__.py`.

Safeguard items need a clause in `docs/conduct-policy.md` and an expected behaviour that is clear under it. Items
where reasonable policies disagree are reported, not scored.

## Submitting results

Results on the development split can be added to `results/` with a pull request that includes the results file, the
exact command, the harness version and the declared prices. They are listed as self-reported. Verified results come
from runs on the hidden split hosted at osintgym.com; how to ask for one is in
[docs/harness-protocol.md](docs/harness-protocol.md).
