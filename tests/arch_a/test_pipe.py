import threading

import pytest

from smart_shelf.arch_a.pipe import Pipe, PipeTimeout
from smart_shelf.arch_a.records import END


def test_items_come_out_in_fifo_order():
    p = Pipe()
    for i in range(5):
        p.put(i)
    assert [p.get() for _ in range(5)] == [0, 1, 2, 3, 4]


def test_close_sends_end_marker():
    p = Pipe()
    p.put("a")
    p.close()
    assert p.get() == "a"
    assert p.get() is END


def test_get_waits_for_an_item():
    p = Pipe()
    threading.Timer(0.05, p.put, args=("late",)).start()
    assert p.get(timeout=2) == "late"


def test_get_times_out_on_empty_pipe():
    with pytest.raises(PipeTimeout, match="p1"):
        Pipe("p1").get(timeout=0.01)
