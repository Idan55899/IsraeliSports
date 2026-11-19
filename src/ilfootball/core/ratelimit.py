"""Per-host politeness delay: at least `interval` seconds (+ jitter) between requests."""
from __future__ import annotations

import random
import time
from typing import Callable


class HostRateLimiter:
    def __init__(
        self,
        interval_for: Callable[[str], float],
        jitter: float = 0.5,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        rand: Callable[[], float] = random.random,
    ) -> None:
        self._interval_for = interval_for
        self._jitter = jitter
        self._clock = clock
        self._sleep = sleep
        self._rand = rand
        self._last: dict[str, float] = {}

    def wait(self, host: str) -> float:
        """Block until `host` may be requested again. Returns seconds slept."""
        slept = 0.0
        last = self._last.get(host)
        if last is not None:
            due = last + self._interval_for(host) + self._jitter * self._rand()
            slept = max(0.0, due - self._clock())
            if slept > 0:
                self._sleep(slept)
        self._last[host] = self._clock()
        return slept
