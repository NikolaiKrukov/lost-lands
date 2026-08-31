"""可播种 RNG。同一存档 + 同一种子可复现。"""

from __future__ import annotations

import random


class GameRNG:
    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)
        self.seed = seed

    def randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)

    def random(self) -> float:
        return self._rng.random()

    def getstate(self) -> tuple:
        return self._rng.getstate()

    def setstate(self, state: tuple) -> None:
        self._rng.setstate(state)
