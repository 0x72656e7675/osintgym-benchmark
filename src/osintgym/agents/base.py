from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

import httpx

from ..tasks.model import Submission


@dataclass
class Budget:
    """Per-attempt limits. They are part of the protocol, recorded with every result, and set by whoever runs."""

    max_steps: int = 60
    max_seconds: float = 900.0
    max_output_tokens: int = 16000

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    steps: int = 0
    calls: int = 0


@dataclass
class Context:
    card: dict[str, Any]
    attempt: str
    gateway: str
    budget: Budget
    usage: Usage = field(default_factory=Usage)
    started: float = field(default_factory=time.monotonic)
    notes: dict[str, Any] = field(default_factory=dict)
    _client: httpx.Client | None = None

    @property
    def proxy(self) -> str:
        host = self.gateway.split("://", 1)[1]
        return f"http://{self.attempt}:x@{host}"

    @property
    def http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(proxy=self.proxy, timeout=30.0, follow_redirects=True,
                                        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) osint-research"})
        return self._client

    def get(self, url: str) -> httpx.Response:
        return self.http.get(url)

    def text(self, url: str) -> str:
        response = self.get(url)
        return response.text if response.status_code == 200 else ""

    def post(self, url: str, data: dict[str, str]) -> httpx.Response:
        return self.http.post(url, data=data)

    def expired(self) -> bool:
        return time.monotonic() - self.started > self.budget.max_seconds

    def close(self) -> None:
        if self._client is not None:
            self._client.close()


class Agent(Protocol):
    name: str

    def run(self, ctx: Context) -> Submission: ...
