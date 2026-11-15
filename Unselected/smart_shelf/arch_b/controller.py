"""Deterministic, dependency-aware blackboard scheduling."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter

from .blackboard import Blackboard


class KnowledgeSource(ABC):
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    requires_dietary = False

    @property
    def name(self) -> str:
        return type(self).__name__

    def can_run(self, board: Blackboard) -> bool:
        return board.has(*self.inputs) and not board.has(*self.outputs)

    @abstractmethod
    def run(self, board: Blackboard) -> None:
        """Read snapshots and publish all declared output regions."""


class ControllerError(RuntimeError):
    pass


class Controller:
    """The source sequence is the fixed priority order, not a call chain.

    Readiness is recomputed after every publication. Substitution and ranking
    have an additional mandatory dietary barrier even for custom sources.
    """

    def __init__(self, board: Blackboard, sources, max_steps: int = 100):
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        self.board = board
        self.sources = tuple(sources)
        self.max_steps = max_steps
        self.activations: list[str] = []
        self.events: list[frozenset[str]] = []
        self.counts: Counter[str] = Counter()
        outputs = [region for source in self.sources for region in source.outputs]
        if len(outputs) != len(set(outputs)):
            raise ValueError("Each blackboard region must have exactly one producer")
        if any(not source.outputs for source in self.sources):
            raise ValueError("Every knowledge source must declare its output regions")
        graph: dict[str, set[str]] = {}
        for source in self.sources:
            for region in source.inputs:
                graph.setdefault(region, set()).update(source.outputs)
        self._check_cycles(graph)
        board.configure(graph)
        board.subscribe(self.events.append)

    @staticmethod
    def _check_cycles(graph):
        visiting, done = set(), set()

        def visit(region):
            if region in visiting:
                raise ValueError("Knowledge-source dependencies must be acyclic")
            if region in done:
                return
            visiting.add(region)
            for child in graph.get(region, ()):
                visit(child)
            visiting.remove(region)
            done.add(region)

        for region in graph:
            visit(region)

    def run(self) -> tuple[str, ...]:
        start = len(self.activations)
        for _ in range(self.max_steps):
            ready = [source for source in self.sources if source.can_run(self.board)
                     and (not source.requires_dietary or self.board.has("dietary"))]
            if not ready:
                return tuple(self.activations[start:])
            source = ready[0]
            source.run(self.board)
            if not self.board.has(*source.outputs):
                raise ControllerError(f"{source.name} did not publish its declared outputs")
            self.activations.append(source.name)
            self.counts[source.name] += 1
        if not any(source.can_run(self.board)
                   and (not source.requires_dietary or self.board.has("dietary"))
                   for source in self.sources):
            return tuple(self.activations[start:])
        raise ControllerError("Knowledge sources did not reach quiescence within max_steps")
