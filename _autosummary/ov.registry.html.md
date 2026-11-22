# ov.registry

The plugin mechanism: decorated functions registered into a dict (§3.2).

Everything extensible in `ov` – probes (what we collect), analyzers (what we
conclude), and report sections (what we render) – is a callable registered with
declared `requires`/`produces` artifact dependencies. A run is then just:
*resolve registry -> topologically order by declared deps -> execute*. Adding a
new capability is registering a function; it never means editing a dispatcher
(open-closed).

This is the “functions as data” + dataflow-DAG shape the project favors. We keep
the `meshed` dependency optional by shipping a small, transparent topo-sort
here; a caller who wants `meshed` can build the same DAG from
[`Registry.items`](#ov.registry.Registry.items).

### Classes

| [`RegisteredFn`](#ov.registry.RegisteredFn)(name, fn[, requires, produces, ...])   | A registered callable plus its declared artifact-kind dependencies.                                                    |
|------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------|
| [`Registry`](#ov.registry.Registry)(label)                                     | A named registry of [`RegisteredFn`](#ov.registry.RegisteredFn), with dependency-ordered resolution. |

### *class* ov.registry.RegisteredFn(name, fn, requires=(), produces=(), meta=dict())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A registered callable plus its declared artifact-kind dependencies.

### *class* ov.registry.Registry(label)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A named registry of [`RegisteredFn`](#ov.registry.RegisteredFn), with dependency-ordered resolution.

```pycon
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
```

#### *property* items *: [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [RegisteredFn](#ov.registry.RegisteredFn)]*

The underlying `name -> RegisteredFn` mapping (read-only by convention).

#### names()

Registered names in insertion order.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

#### ordered(names=None)

Return the selected items topologically ordered by `requires`/`produces`.

An item depends on any *selected* item that `produces` a kind it
`requires`. Inputs produced by no selected item are treated as already
available (captured upstream). Falls back to selection order on a cycle.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`RegisteredFn`](#ov.registry.RegisteredFn)]

#### register(name, , requires=(), produces=(), \*\*meta)

Decorator: register `fn` under `name` with its declared deps.

* **Return type:**
  [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)[[[`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)], [`Callable`](https://docs.python.org/3/library/typing.html#typing.Callable)]
