"""Filter base class: reads its input pipe, processes each item, writes its output pipe."""
from __future__ import annotations

import threading
from typing import Iterable

from smart_shelf.common.models import ReferenceData, UserProfile
from smart_shelf.arch_a.pipe import Pipe
from smart_shelf.arch_a.records import END, ExclusionSummary
from smart_shelf.arch_a.stores import StoreView


class Filter(threading.Thread):
    # Items of these types are forwarded untouched (the Dietary summary).
    passthrough_types: tuple[type, ...] = (ExclusionSummary,)
    # Data stores this filter may read (Figure 1's data-access arrows). Empty = none.
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
        except BaseException as e:      # recorded here, re-raised by Pipeline.run
            self.error = e
        finally:
            self.out.close()            # END always goes downstream, even on error

    def process(self, item) -> Iterable:
        """Yield nothing to drop the item, one item to pass it on, or many to fan out."""
        raise NotImplementedError

    def flush(self) -> Iterable:
        """Called once after END arrives. Override in filters that buffer."""
        return ()
