from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from ..tasks.model import AnswerField, EntityRef, Task
from ..world.search import fold
from ..world.web import canonical, distance_km

GEO_BANDS = ((0.05, 1.0), (0.25, 0.75), (1.0, 0.5), (5.0, 0.25))


def norm(text: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.]+", " ", fold(str(text)))).strip(" .")


def _entity(value: Any, ref: EntityRef) -> float:
    if isinstance(value, str):
        value = {"url": value} if "://" in value or value.startswith(("www.", "http")) else {"name": value}
    if not isinstance(value, dict):
        return 0.0
    url = value.get("url")
    if isinstance(url, str) and url and canonical(url) in {canonical(u) for u in ref.urls}:
        return 1.0
    name = value.get("name")
    return 0.5 if isinstance(name, str) and norm(name) == norm(ref.name) else 0.0


def _entity_set(value: Any, members: list[EntityRef]) -> float:
    if isinstance(value, dict):
        value = value.get("items") or value.get("members") or list(value.values())
    if not isinstance(value, list) or not members:
        return 0.0
    claimed = value[:max(len(members) * 3, 10)]
    remaining = list(members)
    true_positive = 0.0
    for item in claimed:
        best, match = 0.0, None
        for ref in remaining:
            score = _entity(item, ref)
            if score > best:
                best, match = score, ref
        if match is not None:
            true_positive += best
            remaining.remove(match)
    if true_positive == 0:
        return 0.0
    precision, recall = true_positive / len(value), true_positive / len(members)
    return 2 * precision * recall / (precision + recall)


def _geo(value: Any, field: AnswerField) -> float:
    try:
        if isinstance(value, dict):
            lat, lon = float(value["lat"]), float(value["lon"])
        elif isinstance(value, (list, tuple)):
            lat, lon = float(value[0]), float(value[1])
        else:
            lat, lon = (float(p) for p in str(value).replace(";", ",").split(",")[:2])
    except (KeyError, ValueError, TypeError, IndexError):
        return 0.0
    distance = distance_km(lat, lon, field.lat, field.lon)
    return next((score for limit, score in GEO_BANDS if distance <= limit), 0.0)


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip().replace("Z", "+00:00").replace(" UTC", "+00:00")
    for candidate in (text, text.replace(" ", "T")):
        try:
            moment = datetime.fromisoformat(candidate)
            return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _datetime(value: Any, field: AnswerField) -> float:
    moment, expected = parse_time(value), parse_time(field.value)
    if moment is None or expected is None:
        return 0.0
    return 1.0 if abs((moment - expected).total_seconds()) <= (field.tolerance or 0) else 0.0


def _number(value: Any, field: AnswerField) -> float:
    try:
        number = float(str(value).replace(",", ".").split()[0]) if not isinstance(value, (int, float)) else float(value)
    except (ValueError, IndexError):
        return 0.0
    return 1.0 if abs(number - field.number) <= (field.tolerance or 0) else 0.0


def _text(value: Any, field: AnswerField) -> float:
    if not isinstance(value, (str, int, float)):
        return 0.0
    given = norm(str(value).split(",")[0])
    return 1.0 if any(given == norm(a) for a in field.accepted) else 0.0


def score_field(field: AnswerField, value: Any) -> float:
    if value is None:
        return 0.0
    if field.kind == "entity":
        return _entity(value, field.entity)
    if field.kind == "entity_set":
        return _entity_set(value, field.members)
    if field.kind == "geo":
        return _geo(value, field)
    if field.kind == "datetime":
        return _datetime(value, field)
    if field.kind == "number":
        return _number(value, field)
    return _text(value, field)


def score_answer(task: Task, answer: dict[str, Any]) -> tuple[float, dict[str, float]]:
    scores = {f.name: score_field(f, answer.get(f.name)) for f in task.fields}
    total = sum(f.weight for f in task.fields) or 1.0
    return sum(scores[f.name] * f.weight for f in task.fields) / total, scores
