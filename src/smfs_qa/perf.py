"""Performance measurement utilities."""

from __future__ import annotations

import time
from typing import Any

import numpy as np


class LatencyTracker:
    """Tracks latencies and computes percentiles."""

    def __init__(self) -> None:
        self._samples: list[float] = []

    def record(self, latency_ms: float) -> None:
        self._samples.append(latency_ms)

    @property
    def count(self) -> int:
        return len(self._samples)

    def percentile(self, n: float) -> float:
        """Compute the nth percentile of recorded latencies."""
        if not self._samples:
            return 0.0
        return float(np.percentile(self._samples, n))

    @property
    def p50(self) -> float:
        return float(np.percentile(self._samples, 50)) if self._samples else 0.0

    @property
    def p95(self) -> float:
        return float(np.percentile(self._samples, 95)) if self._samples else 0.0

    @property
    def p99(self) -> float:
        return float(np.percentile(self._samples, 99)) if self._samples else 0.0

    @property
    def mean(self) -> float:
        return float(np.mean(self._samples)) if self._samples else 0.0

    def summary(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "p50": round(self.p50, 2),
            "p95": round(self.p95, 2),
            "p99": round(self.p99, 2),
            "mean": round(self.mean, 2),
        }


class Timer:
    """Context manager for timing operations in milliseconds."""

    def __init__(self) -> None:
        self.elapsed_ms: float = 0.0
        self._start: float = 0.0

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000


async def warm_up(coro_factory: Any, count: int = 3) -> None:
    """Run a coroutine factory several times to warm up connections."""
    for _ in range(count):
        try:
            await coro_factory()
        except Exception:
            pass
