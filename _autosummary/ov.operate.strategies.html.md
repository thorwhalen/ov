# ov.operate.strategies

Journey-strategy helpers – intent shaping for the three strategies (§2.3).

The three strategies reuse the same primitives, varying only the *intent* written
to the journal: crawl-and-map (`enumerate`), goal-pursuit (`advance`), and
guided-replay (`replay`). These helpers keep that vocabulary in one place and
provide the deterministic target-selection a model-free driver needs.

### Module Attributes

| [`NAV_ROLES`](#ov.operate.strategies.NAV_ROLES)   | Roles treated as navigable for crawl-and-map.   |
|--------------------------------------------------------------|-------------------------------------------------|

### Functions

| [`absolutize`](#ov.operate.strategies.absolutize)(href, base_url)         | Resolve `href` against `base_url` (drops fragments).                        |
|-------------------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| [`is_same_origin`](#ov.operate.strategies.is_same_origin)(url, base_url)      | True when `url` shares scheme+host(+port) with `base_url`.                  |
| [`navigable_affordances`](#ov.operate.strategies.navigable_affordances)(observation) | Return affordances suitable for breadth-first crawl (links/tabs/menuitems). |

### ov.operate.strategies.NAV_ROLES *= frozenset({'a', 'link', 'menuitem', 'tab'})*

Roles treated as navigable for crawl-and-map.

### ov.operate.strategies.absolutize(href, base_url)

Resolve `href` against `base_url` (drops fragments).

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### ov.operate.strategies.is_same_origin(url, base_url)

True when `url` shares scheme+host(+port) with `base_url`.

```pycon
>>> is_same_origin("https://x.com/a", "https://x.com/b")
True
>>> is_same_origin("https://y.com/a", "https://x.com/b")
False
```

* **Return type:**
  [`bool`](https://docs.python.org/3/builtins/functions.html#bool)

### ov.operate.strategies.navigable_affordances(observation)

Return affordances suitable for breadth-first crawl (links/tabs/menuitems).

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Affordance`](ov.base.html.md#ov.base.Affordance)]
