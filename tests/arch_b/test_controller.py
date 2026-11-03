import pytest

from smart_shelf.arch_b import Blackboard, Controller, ControllerError, KnowledgeSource


class Source(KnowledgeSource):
    def __init__(self, name, inputs, outputs, dietary=False):
        self._name, self.inputs, self.outputs = name, inputs, outputs
        self.requires_dietary = dietary

    @property
    def name(self):
        return self._name

    def run(self, board):
        board.publish(**{self.outputs[0]: self.name})


def test_priority_is_stable_for_simultaneously_ready_sources():
    for _ in range(10):
        board = Blackboard()
        controller = Controller(board, (Source("first", ("input",), ("x",)),
                                        Source("second", ("input",), ("y",))))
        board.publish(input=True)
        assert controller.run() == ("first", "second")
        assert controller.run() == ()


def test_dietary_barrier_overrides_priority():
    board = Blackboard()
    controller = Controller(board, (
        Source("Ranker", ("input",), ("rankings",), True),
        Source("SubstituteFinder", ("input",), ("substituted",), True),
        Source("DietaryChecker", ("input",), ("dietary",)),
    ))
    board.publish(input=True)
    assert controller.run() == ("DietaryChecker", "Ranker", "SubstituteFinder")


def test_region_changes_invalidate_transitive_dependents_only():
    board = Blackboard()
    controller = Controller(board, (
        Source("a", ("input",), ("a",)), Source("b", ("a",), ("b",)),
        Source("c", ("b",), ("c",)), Source("other", ("separate",), ("other",))))
    board.publish(input=1, separate=True)
    controller.run()
    board.publish(a="changed")
    assert board.has("a", "other")
    assert not board.has("b") and not board.has("c")
    assert controller.run() == ("b", "c")
    assert controller.events[-1] == frozenset({"c"})


def test_snapshots_do_not_allow_mutation_without_an_event():
    board = Blackboard()
    value = {"x": [1]}
    board.publish(value=value)
    value["x"].append(2)
    snapshot = board.read("value")
    snapshot["x"].append(3)
    assert board.read("value") == {"x": [1]}
    assert board.publish(value={"x": [1]}) is False
    assert board.versions["value"] == 1


def test_missing_output_fails_instead_of_looping():
    class Broken(Source):
        def run(self, board):
            pass

    board = Blackboard()
    controller = Controller(board, (Broken("bad", ("input",), ("out",)),))
    board.publish(input=True)
    with pytest.raises(ControllerError, match="declared outputs"):
        controller.run()


@pytest.mark.parametrize("sources", [
    (Source("a", ("b",), ("a",)), Source("b", ("a",), ("b",))),
    (Source("a", (), ("x",)), Source("b", (), ("x",))),
    (Source("a", (), ()),),
])
def test_invalid_dependency_configuration_is_rejected(sources):
    with pytest.raises(ValueError):
        Controller(Blackboard(), sources)


def test_activation_limit_prevents_nonquiescent_custom_sources():
    class Repeating(Source):
        def can_run(self, board):
            return True

    controller = Controller(Blackboard(), (Repeating("bad", (), ("out",)),), max_steps=3)
    with pytest.raises(ControllerError, match="quiescence"):
        controller.run()


def test_exactly_max_steps_can_complete():
    controller = Controller(Blackboard(), (Source("once", (), ("out",)),), max_steps=1)
    assert controller.run() == ("once",)
