"""Sliding window for sustained-threshold detection."""
from __future__ import annotations

from collections import deque
from statistics import mean


class Window:
    """Keeps the last N metric samples and decides if a threshold is breached."""

    def __init__(self, size: int) -> None:
        self.samples: deque[float] = deque(maxlen=size)

    def add(self, value: float) -> None:
        self.samples.append(float(value))

    def is_breached(self, threshold: float, window_type: str = "consecutive") -> bool:
        """Return True if the threshold is breached in a sustained way."""
        if threshold is None:
            return False
        if len(self.samples) < self.samples.maxlen:
            # Wait until the window is full before alerting
            return False
        if window_type == "average":
            return mean(self.samples) >= threshold
        # consecutive: every sample in the window must be above the threshold
        return all(sample >= threshold for sample in self.samples)
