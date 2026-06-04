"""The plugin mechanism: decorated functions registered into a dict (§3.2).

Everything extensible in ``ov`` -- probes (what we collect), analyzers (what we
conclude), and report sections (what we render) -- is a callable registered with
declared ``requires``/``produces`` artifact dependencies. A run is then just:
*resolve registry -> topologically order by declared deps -> execute*. Adding a
new capability is registering a function; it never means editing a dispatcher
(open-closed).

This is the "functions as data" + dataflow-DAG shape the project favors. We keep
the ``meshed`` dependency optional by shipping a small, transparent topo-sort
here; a caller who wants ``meshed`` can build the same DAG from
:attr:`Registry.items`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable


@dataclass
class RegisteredFn:
    """A registered callable plus its declared artifact-kind dependencies."""

    name: str
    fn: Callable
    requires: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()
    meta: dict[str, Any] = field(default_factory=dict)

    def __call__(self, *args, **kwargs):
        return self.fn(*args, **kwargs)


class Registry:
    """A named registry of :class:`RegisteredFn`, with dependency-ordered resolution.

    >>> reg = Registry("demo")
    >>> @reg.register("a", produces=("x",))
    ... def a():
    ...     return "a"
    >>> @reg.register("b", requires=("x",), produces=("y",))
    ... def b():
    ...     return "b"
    >>> [r.name for r in reg.ordered()]   # b depends on a's output kind "x"
    ['a', 'b']
    >>> reg["a"].fn()
    'a'
    """

    def __init__(self, label: str):
        self.label = label
        self._items: dict[str, RegisteredFn] = {}

    def register(
        self,
        name: str,
        *,
        requires: Iterable[str] = (),
        produces: Iterable[str] = (),
        **meta: Any,
    ) -> Callable[[Callable], Callable]:
        """Decorator: register ``fn`` under ``name`` with its declared deps."""

        def deco(fn: Callable) -> Callable:
            self._items[name] = RegisteredFn(
                name=name,
                fn=fn,
                requires=tuple(requires),
                produces=tuple(produces),
                meta=dict(meta),
            )
            return fn

        return deco

    # --- mapping-ish access ------------------------------------------------ #

    def __getitem__(self, name: str) -> RegisteredFn:
        return self._items[name]

    def __contains__(self, name: str) -> bool:
        return name in self._items

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    @property
    def items(self) -> dict[str, RegisteredFn]:
        """The underlying ``name -> RegisteredFn`` mapping (read-only by convention)."""
        return dict(self._items)

    def names(self) -> list[str]:
        """Registered names in insertion order."""
        return list(self._items)

    # --- ordering ---------------------------------------------------------- #

    def ordered(self, names: Iterable[str] | None = None) -> list[RegisteredFn]:
        """Return the selected items topologically ordered by ``requires``/``produces``.

        An item depends on any *selected* item that ``produces`` a kind it
        ``requires``. Inputs produced by no selected item are treated as already
        available (captured upstream). Falls back to selection order on a cycle.
        """
        selected = list(self._items) if names is None else [n for n in names if n in self._items]
        chosen = [self._items[n] for n in selected]

        producers: dict[str, list[str]] = {}
        for item in chosen:
            for kind in item.produces:
                producers.setdefault(kind, []).append(item.name)

        # edges: producer.name -> consumer.name
        deps: dict[str, set[str]] = {it.name: set() for it in chosen}
        for item in chosen:
            for kind in item.requires:
                for prod in producers.get(kind, ()):
                    if prod != item.name:
                        deps[item.name].add(prod)

        ordered_names: list[str] = []
        remaining = dict(deps)
        # Kahn's algorithm, preserving selection order among ready nodes.
        while remaining:
            ready = [n for n in selected if n in remaining and not remaining[n]]
            if not ready:  # cycle -> degrade gracefully to selection order
                ready = [n for n in selected if n in remaining]
            for n in ready:
                ordered_names.append(n)
                remaining.pop(n, None)
                for other in remaining:
                    remaining[other].discard(n)
        return [self._items[n] for n in ordered_names]
