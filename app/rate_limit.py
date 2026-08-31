from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Iterable, Tuple


class RateLimiter:
    """A small in-memory sliding-window limiter for the single Web worker."""

    def __init__(self):
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._windows: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._checks = 0

    def allow(self, limits: Iterable[Tuple[str, int, float]]) -> bool:
        limits = list(limits)
        now = time.monotonic()
        with self._lock:
            self._checks += 1
            for key, maximum, window_seconds in limits:
                self._windows[key] = window_seconds
                events = self._events[key]
                cutoff = now - window_seconds
                while events and events[0] <= cutoff:
                    events.popleft()
                if len(events) >= maximum:
                    return False
            for key, _, _ in limits:
                self._events[key].append(now)
            if self._checks % 256 == 0:
                self._remove_expired_keys(now)
            return True

    def _remove_expired_keys(self, now: float) -> None:
        for key, events in list(self._events.items()):
            cutoff = now - self._windows[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if not events:
                del self._events[key]
                del self._windows[key]
