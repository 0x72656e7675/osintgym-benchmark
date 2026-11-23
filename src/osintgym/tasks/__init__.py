from __future__ import annotations

from ..world.build import Builder, populate
from ..world.model import World
from .capability import CAPABILITY
from .model import Task
from .safeguards import SAFEGUARDS

FAMILIES = {**CAPABILITY, **SAFEGUARDS}

# Public development split. The test split uses the same generator with a seed that is never published.
DEV_SEED = 1001
PER_FAMILY = 6


def generate(seed: int = DEV_SEED, per_family: int = PER_FAMILY) -> tuple[World, list[Task]]:
    """Every family always plants into the world, so a seed yields the same world whatever subset is later run."""
    builder = Builder(seed)
    populate(builder)
    tasks: list[Task] = []
    for plant in FAMILIES.values():
        for index in range(per_family):
            tasks.extend(plant(builder, index))
    return builder.world, tasks


def select(tasks: list[Task], families: list[str] | None = None, track: str | None = None) -> list[Task]:
    chosen = tasks
    if families:
        chosen = [t for t in chosen if any(t.family == f or t.family.startswith(f + ".") or t.id.startswith(f) for f in families)]
    if track:
        chosen = [t for t in chosen if t.track == track]
    return chosen
