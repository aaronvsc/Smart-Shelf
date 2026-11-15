"""Versioned regions and event notifications for Architecture B."""
from __future__ import annotations

from copy import deepcopy
from typing import Callable, Mapping


class Blackboard:
    """Publish related regions atomically; readers receive isolated snapshots.

    Missing regions are invalid, rather than silently exposing stale results.
    The controller installs the dependency graph and receives change events.
    """

    def __init__(self):
        self._regions: dict[str, object] = {}
        self._dependents: dict[str, set[str]] = {}
        self._listeners: list[Callable[[frozenset[str]], None]] = []
        self.versions: dict[str, int] = {}

    def configure(self, dependencies: Mapping[str, set[str]]) -> None:
        self._dependents = {key: set(value) for key, value in dependencies.items()}

    def subscribe(self, listener: Callable[[frozenset[str]], None]) -> None:
        self._listeners.append(listener)

    def has(self, *regions: str) -> bool:
        return all(region in self._regions for region in regions)

    def read(self, region: str):
        return deepcopy(self._regions[region])

    def publish(self, **regions) -> bool:
        changed = {key for key, value in regions.items()
                   if key not in self._regions or self._regions[key] != value}
        if not changed:
            return False
        invalid = set()
        pending = list(changed)
        while pending:
            for target in self._dependents.get(pending.pop(), ()):
                if target not in invalid:
                    invalid.add(target)
                    pending.append(target)
        for key in invalid - regions.keys():
            self._regions.pop(key, None)
        for key, value in regions.items():
            self._regions[key] = deepcopy(value)
            if key in changed:
                self.versions[key] = self.versions.get(key, 0) + 1
        event = frozenset(changed)
        for listener in self._listeners:
            listener(event)
        return True
