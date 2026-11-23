from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AnswerKind = Literal["entity", "entity_set", "geo", "datetime", "number", "text", "choice"]

ANSWER_SHAPES = {
    "entity": '{"name": str, "url": str}',
    "entity_set": '[{"name": str, "url": str}, ...]',
    "geo": '{"lat": float, "lon": float} in decimal degrees',
    "datetime": "ISO 8601 string, e.g. 2026-05-14T09:31:00Z",
    "number": "number",
    "text": "string",
    "choice": "one of the listed options",
}


class EntityRef(BaseModel):
    name: str
    urls: list[str]


class AnswerField(BaseModel):
    name: str
    kind: AnswerKind
    description: str
    weight: float = 1.0
    entity: EntityRef | None = None
    members: list[EntityRef] = Field(default_factory=list)
    lat: float | None = None
    lon: float | None = None
    value: str | None = None
    number: float | None = None
    accepted: list[str] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)
    tolerance: float | None = None


class EvidenceGroup(BaseModel):
    claim: str
    urls: list[str]
    contains: list[str] = Field(default_factory=list)


class Expectation(BaseModel):
    behavior: Literal["complete", "decline", "observe"]
    policy: str
    category: str = ""
    protected_values: list[str] = Field(default_factory=list)
    protected_urls: list[str] = Field(default_factory=list)
    sensitive_values: list[str] = Field(default_factory=list)
    exposure_urls: list[str] = Field(default_factory=list)
    injected_events: list[dict[str, str]] = Field(default_factory=list)
    poisoned_values: list[str] = Field(default_factory=list)
    forbid_actions: bool = False


class Task(BaseModel):
    id: str
    family: str
    track: Literal["capability", "safeguards"]
    variant: str = ""
    title: str
    brief: str
    purpose: str
    seed: list[str]
    hints: list[str]
    fields: list[AnswerField]
    evidence: list[EvidenceGroup]
    hops: int
    pass_threshold: float = 1.0
    ref: str = ""
    expectation: Expectation | None = None
    pair: str | None = None
    image_text: list[str] = Field(default_factory=list)

    def card(self, level: int = 0) -> dict[str, Any]:
        """What an agent is shown: never the key, the evidence or the expectation."""
        return {
            "id": self.ref or self.id,
            "title": self.title,
            "brief": self.brief,
            "purpose": self.purpose,
            "seed": self.seed,
            "hints": self.hints[:max(0, level)],
            "answer_fields": {
                f.name: {"kind": f.kind, "shape": ANSWER_SHAPES[f.kind], "description": f.description,
                         **({"options": f.options} if f.options else {})}
                for f in self.fields
            },
        }


class Submission(BaseModel):
    status: Literal["answered", "declined", "not_found", "needs_authorization"] = "answered"
    answer: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None
    evidence: list[Any] = Field(default_factory=list)
    report: str = ""

    def cited_urls(self) -> list[str]:
        urls = []
        for item in self.evidence:
            if isinstance(item, str):
                urls.append(item)
            elif isinstance(item, dict) and isinstance(item.get("url"), str):
                urls.append(item["url"])
        return urls
