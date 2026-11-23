from __future__ import annotations

import hashlib
import random

_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def _digest(seed: int, parts: tuple[object, ...]) -> bytes:
    return hashlib.sha256("\x1f".join([str(seed), *map(str, parts)]).encode()).digest()


def keyed(seed: int, *parts: object) -> random.Random:
    """A generator that depends only on the seed and its key, so adding entities elsewhere never shifts it."""
    return random.Random(int.from_bytes(_digest(seed, parts)[:16], "big"))


def token(seed: int, *parts: object, length: int = 10) -> str:
    n = int.from_bytes(_digest(seed, ("token", *parts)), "big")
    chars = []
    for _ in range(length):
        n, r = divmod(n, len(_ALPHABET))
        chars.append(_ALPHABET[r])
    return "".join(chars)
