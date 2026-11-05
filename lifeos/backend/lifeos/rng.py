"""Seeded, reproducible randomness organised as independent streams.

Every random draw comes from a stream derived from (world seed, stream name, keys).
A character's decision on a given day and slot always uses the same stream no matter
what anyone else did, so changing one system or one character does not shift the
random numbers every other system sees. There is no hidden RNG state to save:
the seed plus the world state fully determines what happens next.
"""
from __future__ import annotations

import hashlib
import math
import random


def derive_seed(*parts) -> int:
    h = hashlib.blake2b("|".join(str(p) for p in parts).encode("utf-8"), digest_size=8)
    return int.from_bytes(h.digest(), "big")


def unit_hash(*parts) -> float:
    """Deterministic number in [0, 1) from the parts (used for latent pair chemistry)."""
    return derive_seed(*parts) / 2 ** 64


class Streams:
    def __init__(self, seed: int):
        self.seed = int(seed)

    def get(self, stream: str, *keys) -> random.Random:
        return random.Random(derive_seed(self.seed, stream, *keys))


def softmax_pick(utilities: list[float], temperature: float, u: float) -> tuple[int, list[float]]:
    """Pick an index by softmax over utilities using one uniform draw u (recorded in traces)."""
    t = max(temperature, 1e-6)
    m = max(utilities)
    ws = [math.exp((x - m) / t) for x in utilities]
    s = sum(ws)
    probs = [w / s for w in ws]
    acc = 0.0
    for i, p in enumerate(probs):
        acc += p
        if u < acc:
            return i, probs
    return len(probs) - 1, probs


def sigmoid(x: float) -> float:
    if x < -60:
        return 0.0
    if x > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x
