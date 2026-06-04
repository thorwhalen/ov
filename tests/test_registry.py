"""Tests for the plugin registry + topo-sort (``ov.registry``)."""

from ov.registry import Registry


def test_topo_order_by_produces_requires():
    reg = Registry("t")
    reg.register("c", requires=("y",))(lambda: "c")
    reg.register("a", produces=("x",))(lambda: "a")
    reg.register("b", requires=("x",), produces=("y",))(lambda: "b")
    order = [r.name for r in reg.ordered()]
    assert order.index("a") < order.index("b") < order.index("c")


def test_subset_selection_only_orders_selected():
    reg = Registry("t")
    reg.register("a", produces=("x",))(lambda: 1)
    reg.register("b", requires=("x",))(lambda: 2)
    reg.register("c")(lambda: 3)
    names = [r.name for r in reg.ordered(["b", "a"])]
    assert names == ["a", "b"]  # a before b; c excluded


def test_cycle_degrades_gracefully():
    reg = Registry("t")
    reg.register("a", requires=("y",), produces=("x",))(lambda: 1)
    reg.register("b", requires=("x",), produces=("y",))(lambda: 2)
    names = [r.name for r in reg.ordered()]
    assert set(names) == {"a", "b"}  # no crash, all present


def test_membership_and_access():
    reg = Registry("t")
    reg.register("a")(lambda: 1)
    assert "a" in reg and reg["a"].fn() == 1
    assert len(reg) == 1 and reg.names() == ["a"]
