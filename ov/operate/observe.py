"""``observe(page, strategy) -> Observation`` -- the pure-read primitive.

A thin, timed wrapper over the perception strategies. It performs no action and
mutates no state; it is the "perceive" in perceive->decide->act->record.
"""

from __future__ import annotations

import time
from typing import Any

from ..base import Observation
from .perception import perceive


def observe(page: Any, strategy: str = "ax_snapshot") -> Observation:
    """Perceive the current page state with ``strategy`` and return an Observation.

    >>> from ov.operate.perception import PERCEPTION_REGISTRY
    >>> "ax_snapshot" in PERCEPTION_REGISTRY
    True
    """
    t0 = time.monotonic()
    obs = perceive(page, strategy)
    obs.t_ms = (time.monotonic() - t0) * 1000.0
    return obs
