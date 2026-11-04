import pytest

from smart_shelf.arch_a.filter_base import Filter
from smart_shelf.arch_a.pipe import Pipe
from smart_shelf.arch_a.records import END, ExclusionSummary


class Double(Filter):
    def process(self, item):
        yield item * 2


class DropOdd(Filter):
    def process(self, item):
        if item % 2 == 0:
            yield item


class FanOut(Filter):
    def process(self, item):
        yield from range(item)


class Buffer(Filter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen = []

    def process(self, item):
        self.seen.append(item)
        return ()

    def flush(self):
        yield from sorted(self.seen)


class Boom(Filter):
    def process(self, item):
        raise RuntimeError("boom")


@pytest.mark.parametrize("cls, items, expected", [
    (Double, [1, 2, 3], [2, 4, 6]),
    (DropOdd, [1, 2, 3, 4], [2, 4]),
    (FanOut, [3], [0, 1, 2]),
    (Buffer, [3, 1, 2], [1, 2, 3]),
])
def test_process_and_flush(run_filter, cls, items, expected):
    assert run_filter(cls, items, ctx=None) == expected


def test_exclusion_summary_passes_through_untouched(run_filter):
    summary = ExclusionSummary(1, {})
    assert run_filter(Double, [1, summary], ctx=None) == [2, summary]


def test_end_marker_is_sent_even_when_the_filter_fails(ref):
    inp, out = Pipe(), Pipe()
    f = Boom(inp, out, None, ref)
    f.start()
    inp.put(1)
    inp.close()
    assert out.get(timeout=2) is END
    f.join(timeout=2)
    assert isinstance(f.error, RuntimeError)
