# ov.analysis.ux.severity

Severity scoring: `score = impact_tier x reach` (D3 §1).

The design goal is that a high-reach moderate issue outranks a rare critical one.
`reach` combines how many nodes/states an issue touches with the fraction of
the journey it affects:

```default
reach_magnitude = max(nodes, states_affected, 1)
reach_value     = reach_magnitude * journey_fraction
score           = impact_weight * reach_value
```

So a *serious* (3) issue on 12 nodes across 80% of journeys scores
`3 * (12 * 0.8) = 28.8`, while a *critical* (4) issue on 1 node in 5% of
journeys scores `4 * (1 * 0.05) = 0.2` – exactly the prioritization D3 wants.

### Module Attributes

| [`A11Y_TIER_WEIGHT`](#ov.analysis.ux.severity.A11Y_TIER_WEIGHT)   | axe-style accessibility impact tiers -> numeric weight.   |
|---------------------------------------------------------------------|-----------------------------------------------------------|
| [`UX_TIER_WEIGHT`](#ov.analysis.ux.severity.UX_TIER_WEIGHT)     | Nielsen UX severity tiers (0 cosmetic .                   |

### Functions

| [`make_severity`](#ov.analysis.ux.severity.make_severity)(impact_tier, \*[, nodes, ...])   | Build a [`Severity`](ov.base.html.md#ov.base.Severity) with the `impact x reach` score.   |
|-------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------|
| [`tier_weight`](#ov.analysis.ux.severity.tier_weight)(impact_tier)                       | Map an a11y label or a UX `"0".."4"` tier to its numeric weight (default 2).                                          |

### ov.analysis.ux.severity.A11Y_TIER_WEIGHT *: [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [int](https://docs.python.org/3/builtins/functions.html#int)]* *= {'critical': 4, 'minor': 1, 'moderate': 2, 'serious': 3}*

axe-style accessibility impact tiers -> numeric weight.

### ov.analysis.ux.severity.UX_TIER_WEIGHT *: [dict](https://docs.python.org/3/builtins/stdtypes.html#dict)[[str](https://docs.python.org/3/builtins/stdtypes.html#str), [int](https://docs.python.org/3/builtins/functions.html#int)]* *= {'0': 0, '1': 1, '2': 2, '3': 3, '4': 4}*

Nielsen UX severity tiers (0 cosmetic .. 4 catastrophe) -> numeric weight.

### ov.analysis.ux.severity.make_severity(impact_tier, , nodes=1, states_affected=1, journey_fraction=1.0)

Build a [`Severity`](ov.base.html.md#ov.base.Severity) with the `impact x reach` score.

```pycon
>>> make_severity("serious", nodes=12, journey_fraction=0.8).score
28.8
>>> round(make_severity("critical", nodes=1, journey_fraction=0.05).score, 2)
0.2
```

* **Return type:**
  [`Severity`](ov.base.html.md#ov.base.Severity)

### ov.analysis.ux.severity.tier_weight(impact_tier)

Map an a11y label or a UX `"0".."4"` tier to its numeric weight (default 2).

* **Return type:**
  [`int`](https://docs.python.org/3/builtins/functions.html#int)
