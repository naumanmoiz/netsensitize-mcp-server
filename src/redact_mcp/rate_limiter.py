"""Async sliding window rate limiter used by middleware."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Deque, Dict, Optional


class SlidingWindowRateLimiter:
    """Per-key sliding window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._entries: Dict[str, Deque[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> tuple[bool, Optional[float]]:
        """Return (allowed, retry_after_seconds)."""

        now = time.monotonic()
        async with self._lock:
            queue = self._entries.setdefault(key, deque())
            self._drain(queue, now)
            if len(queue) >= self._max_requests:
                retry_after = self._window_seconds - (now - queue[0])
                return False, max(retry_after, 0.0)
            queue.append(now)
            return True, None

    def _drain(self, queue: Deque[float], now: float) -> None:
        boundary = now - self._window_seconds
        while queue and queue[0] <= boundary:
            queue.popleft()

    async def reset(self) -> None:
        async with self._lock:
            self._entries.clear()
