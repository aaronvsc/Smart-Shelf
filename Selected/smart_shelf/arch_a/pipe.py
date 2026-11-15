"""Pipe connector: a one-way stream between two filters."""
from __future__ import annotations

import queue

from smart_shelf.arch_a.records import END


class PipeTimeout(Exception):
    """A reader waited too long; the upstream filter is likely stuck."""


class Pipe:
    def __init__(self, name: str = "pipe"):
        self.name = name
        self._q: queue.Queue = queue.Queue()

    def put(self, item) -> None:
        self._q.put(item)

    def get(self, timeout: float | None = 10.0):
        """Block until an item arrives. Returns END once the stream is closed."""
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            raise PipeTimeout(f"{self.name}: no item within {timeout}s") from None

    def close(self) -> None:
        self._q.put(END)
