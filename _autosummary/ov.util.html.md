# ov.util

Internal helpers: content-addressing, hashing, redaction, and requirements.

Nothing here knows about Playwright or analysis specifics – these are the
small, reusable primitives the rest of the package leans on. The most
user-facing item is [`check_requirements()`](#ov.util.check_requirements), which detects missing system
dependencies (Playwright browsers, Node, the sidecar, optional CLIs) and prints
the exact commands to install them, per the spec’s `check_requirements`
mandate (§9).

### Functions

| [`check_requirements`](#ov.util.check_requirements)(\*[, components, verbose])   | Detect missing system dependencies and print exact install commands.           |
|--------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------|
| [`content_hash`](#ov.util.content_hash)(data, \*[, length])                | Return a short, stable SHA-256 hex digest for content-addressing.              |
| [`redact_mapping`](#ov.util.redact_mapping)(mapping, \*[, redact])           | Return a copy of `mapping` with values redacted when `redact` is true.         |
| [`redact_value`](#ov.util.redact_value)(value)                             | Replace a value with a length-tagged placeholder (keeps shape, drops content). |
| [`sidecar_dir`](#ov.util.sidecar_dir)()                                   | Return the path to the Node sidecar directory (`OV_SIDECAR_DIR` override).     |
| [`stable_hash`](#ov.util.stable_hash)(obj, \*[, length])                  | Hash an arbitrary JSON-able object deterministically (sorted keys).            |

### Classes

| [`Requirement`](#ov.util.Requirement)(name, present[, detail, ...])   | One checked system dependency.                                                                                        |
|----------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------|
| [`RequirementReport`](#ov.util.RequirementReport)([requirements])           | The result of [`check_requirements()`](#ov.util.check_requirements) -- iterable, with a tidy summary. |

### *class* ov.util.Requirement(name, present, detail='', install_hint='', optional=True)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

One checked system dependency.

### *class* ov.util.RequirementReport(requirements=list())

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

The result of [`check_requirements()`](#ov.util.check_requirements) – iterable, with a tidy summary.

#### *property* missing *: [list](https://docs.python.org/3/builtins/stdtypes.html#list)[[Requirement](#ov.util.Requirement)]*

Requirements that are absent (optional or not).

#### *property* ok *: [bool](https://docs.python.org/3/builtins/functions.html#bool)*

True when every *non-optional* requirement is present.

#### render()

Human-readable multi-line summary with install hints for what’s missing.

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### ov.util.check_requirements(, components=None, verbose=True)

Detect missing system dependencies and print exact install commands.

`components` filters which groups to check (`"browser"`, `"node"`,
`"sidecar"`, `"clis"`); `None` checks all. The deterministic analysis
core needs none of these – they gate *capture* and the *arch sidecar*, so
every requirement here is reported as optional unless capture is requested.

```pycon
>>> rep = check_requirements(components=["clis"], verbose=False)
>>> isinstance(rep, RequirementReport)
True
```

* **Return type:**
  [`RequirementReport`](#ov.util.RequirementReport)

### ov.util.content_hash(data, , length=16)

Return a short, stable SHA-256 hex digest for content-addressing.

```pycon
>>> content_hash(b"hello")
'2cf24dba5fb0a30e'
>>> content_hash("hello") == content_hash(b"hello")
True
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### ov.util.redact_mapping(mapping, , redact=True)

Return a copy of `mapping` with values redacted when `redact` is true.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

### ov.util.redact_value(value)

Replace a value with a length-tagged placeholder (keeps shape, drops content).

```pycon
>>> redact_value("super-secret-token")
'<redacted:18>'
>>> redact_value(None)
'<redacted>'
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### ov.util.sidecar_dir()

Return the path to the Node sidecar directory (`OV_SIDECAR_DIR` override).

Defaults to `<repo_root>/sidecar` (sibling of the `ov` package). Packaging
the sidecar for installed use is a later concern; for now it lives in the
source tree.

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)

### ov.util.stable_hash(obj, , length=16)

Hash an arbitrary JSON-able object deterministically (sorted keys).

Used for `obs_hash` and `args_hash` so progress detection is reproducible.

```pycon
>>> stable_hash({"b": 1, "a": 2}) == stable_hash({"a": 2, "b": 1})
True
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
