"""Pipe connector.

In:  items put() by the upstream filter
Out: the same items, in order, from get(); END after close()
"""
from __future__ import annotations

import queue

from smart_shelf.arch_a.records import END


class PipeTimeout(Exception):
    """Raised by get() when no item arrives within the timeout."""


class Pipe:
    def __init__(self, name: str = "pipe"):
        self.name = name
        self._q: queue.Queue = queue.Queue()

    def put(self, item) -> None:
        self._q.put(item)

    def get(self, timeout: float | None = 10.0):
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            raise PipeTimeout(f"{self.name}: no item within {timeout}s") from None

    def close(self) -> None:
        self._q.put(END)
