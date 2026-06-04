"""Severity scoring: ``score = impact_tier x reach`` (D3 §1).

The design goal is that a high-reach moderate issue outranks a rare critical one.
``reach`` combines how many nodes/states an issue touches with the fraction of
the journey it affects::

    reach_magnitude = max(nodes, states_affected, 1)
    reach_value     = reach_magnitude * journey_fraction
    score           = impact_weight * reach_value

So a *serious* (3) issue on 12 nodes across 80% of journeys scores
``3 * (12 * 0.8) = 28.8``, while a *critical* (4) issue on 1 node in 5% of
journeys scores ``4 * (1 * 0.05) = 0.2`` -- exactly the prioritization D3 wants.
"""

from __future__ import annotations

from ...base import Severity

#: axe-style accessibility impact tiers -> numeric weight.
A11Y_TIER_WEIGHT: dict[str, int] = {
    "minor": 1,
    "moderate": 2,
    "serious": 3,
    "critical": 4,
}

#: Nielsen UX severity tiers (0 cosmetic .. 4 catastrophe) -> numeric weight.
UX_TIER_WEIGHT: dict[str, int] = {"0": 0, "1": 1, "2": 2, "3": 3, "4": 4}


def tier_weight(impact_tier: str) -> int:
    """Map an a11y label or a UX ``"0".."4"`` tier to its numeric weight (default 2)."""
    key = str(impact_tier).strip().lower()
    if key in A11Y_TIER_WEIGHT:
        return A11Y_TIER_WEIGHT[key]
    if key in UX_TIER_WEIGHT:
        return UX_TIER_WEIGHT[key]
    return 2  # moderate-ish default for unknown tiers


def make_severity(
    impact_tier: str,
    *,
    nodes: int = 1,
    states_affected: int = 1,
    journey_fraction: float = 1.0,
) -> Severity:
    """Build a :class:`~ov.base.Severity` with the ``impact x reach`` score.

    >>> make_severity("serious", nodes=12, journey_fraction=0.8).score
    28.8
    >>> round(make_severity("critical", nodes=1, journey_fraction=0.05).score, 2)
    0.2
    """
    journey_fraction = max(0.0, min(1.0, journey_fraction))
    reach_magnitude = max(nodes, states_affected, 1)
    reach_value = reach_magnitude * journey_fraction
    score = tier_weight(impact_tier) * reach_value
    return Severity(
        impact_tier=str(impact_tier),
        reach={
            "nodes": nodes,
            "states_affected": states_affected,
            "journey_fraction": journey_fraction,
        },
        score=round(score, 4),
    )
