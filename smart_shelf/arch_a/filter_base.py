"""Filter base class.

In:  items from the input pipe, until END
Out: process() results, then flush() results, then END on the output pipe
"""
from __future__ import annotations

import threading
from typing import Iterable

from smart_shelf.common.models import ReferenceData, UserProfile
from smart_shelf.arch_a.pipe import Pipe
from smart_shelf.arch_a.records import END, ExclusionSummary
from smart_shelf.arch_a.stores import StoreView


class Filter(threading.Thread):
    passthrough_types: tuple[type, ...] = (ExclusionSummary,)
    reads: frozenset[str] = frozenset()

    def __init__(self, inp: Pipe | None, out: Pipe, ref: ReferenceData,
                 profile: UserProfile | None = None):
        super().__init__(name=type(self).__name__, daemon=True)
        self.inp = inp
        self.out = out
        self.stores = StoreView(ref, profile, self.reads, self.name)
        self.error: BaseException | None = None

    def run(self) -> None:
        try:
            while (item := self.inp.get()) is not END:
                if isinstance(item, self.passthrough_types):
                    self.out.put(item)
                    continue
                for result in self.process(item):
                    self.out.put(result)
            for result in self.flush():
                self.out.put(result)
        except BaseException as e:
            self.error = e
        finally:
            self.out.close()

    def process(self, item) -> Iterable:
        """In: one item. Out: zero or more items."""
        raise NotImplementedError

    def flush(self) -> Iterable:
        """Out: items to send after END arrives."""
        return ()
