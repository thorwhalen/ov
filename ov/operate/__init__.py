"""The operate layer -- deterministic, LLM-free tool primitives (the "hands").

This is the package-owned *tool plane* from §2.3. It composes as
``journal(progress(act(observe())))`` and contains no model and no policy: it
perceives affordances, executes actions, records the journey, and reports
loop/no-progress *facts*. The decision of *what to do next* and *when to stop*
belongs to the policy plane -- the host (Claude Code) via the ``ov-operate``
skill, or, later, an in-package agent.

Primitives (each is individually callable and testable):

* :func:`~ov.operate.observe.observe` -- ``observe(page, strategy) -> Observation``
* :func:`~ov.operate.act.act` -- ``act(page, action) -> ActionResult`` (returns a fresh Observation)
* :func:`~ov.operate.journal.journal` -- append a structured per-step record
* :func:`~ov.operate.progress.progress` -- loop/no-progress facts (never decides to stop)
* perception strategies -- :data:`~ov.operate.perception.PERCEPTION_REGISTRY`
"""

from .act import act  # noqa: F401
from .journal import journal, make_step  # noqa: F401
from .observe import observe  # noqa: F401
from .perception import PERCEPTION_REGISTRY, REF_ATTR, perceive  # noqa: F401
from .progress import progress  # noqa: F401

__all__ = [
    "observe",
    "act",
    "journal",
    "make_step",
    "progress",
    "perceive",
    "PERCEPTION_REGISTRY",
    "REF_ATTR",
]
