from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from urllib.parse import urlsplit

_COMPOUND = re.compile(r"[a-z0-9]+(?:[._@-][a-z0-9]+)*")
_PART = re.compile(r"[a-z0-9]+")


def fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def tokens(text: str) -> list[str]:
    folded = fold(text)
    out: list[str] = []
    for compound in _COMPOUND.findall(folded):
        out.append(compound)
        parts = _PART.findall(compound)
        if len(parts) > 1:
            out.extend(parts)
    return out


@dataclass
class Hit:
    url: str
    title: str
    snippet: str


class Index:
    def __init__(self) -> None:
        self.docs: list[tuple[str, str, str]] = []
        self.postings: dict[str, dict[int, int]] = {}
        self.lengths: list[int] = []

    def add(self, url: str, title: str, text: str) -> None:
        doc = len(self.docs)
        self.docs.append((url, title, text))
        counts = Counter(tokens(f"{title} {text}"))
        self.lengths.append(sum(counts.values()))
        for term, tf in counts.items():
            self.postings.setdefault(term, {})[doc] = tf

    def search(self, query: str, *, limit: int = 10, offset: int = 0) -> tuple[list[Hit], int]:
        phrases = [fold(p) for p in re.findall(r'"([^"]+)"', query)]
        rest = re.sub(r'"[^"]+"', " ", query)
        sites = [s.lower() for s in re.findall(r"\bsite:(\S+)", rest)]
        rest = re.sub(r"\bsite:\S+", " ", rest)
        terms = list(dict.fromkeys(tokens(rest) + [t for p in phrases for t in _PART.findall(p)]))
        if not terms:
            return [], 0
        candidates: set[int] | None = None
        for term in terms:
            docs = set(self.postings.get(term, {}))
            candidates = docs if candidates is None else candidates & docs
        n = len(self.docs) or 1
        average = (sum(self.lengths) / n) if self.lengths else 1
        scored = []
        for doc in sorted(candidates or ()):
            url, title, text = self.docs[doc]
            if sites and not any(urlsplit(url).hostname == s or (urlsplit(url).hostname or "").endswith("." + s) for s in sites):
                continue
            folded = fold(f"{title} {text}")
            if any(p not in folded for p in phrases):
                continue
            score = 0.0
            for term in terms:
                postings = self.postings[term]
                tf = postings[doc]
                idf = math.log(1 + (n - len(postings) + 0.5) / (len(postings) + 0.5))
                score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * self.lengths[doc] / average))
            scored.append((-score, url, doc))
        scored.sort()
        hits = [Hit(self.docs[d][0], self.docs[d][1], _snippet(self.docs[d][2], terms)) for _, _, d in scored[offset:offset + limit]]
        return hits, len(scored)


def _snippet(text: str, terms: list[str]) -> str:
    folded = fold(text)
    position = min((folded.find(t) for t in terms if folded.find(t) >= 0), default=0)
    start = max(0, position - 90)
    excerpt = text[start:start + 220].strip()
    return ("... " if start else "") + excerpt + (" ..." if start + 220 < len(text) else "")
