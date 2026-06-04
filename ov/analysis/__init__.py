"""Analysis layer: deterministic analyzers over captured artifacts (Phases 2-3).

Analyzers are registered plugins (:data:`ANALYZER_REGISTRY`) that read a
:class:`~ov.base.CaptureRun` plus its store and emit :class:`~ov.base.Finding`s /
:class:`~ov.base.Endpoint`s / facts -- all model-free and fully testable on
synthetic artifacts. The host (or, later, an in-package agent) adds narrative
judgment *on top* of these via the evidence bundle.

Each analyzer is registered with a ``lens`` (``"ux"`` or ``"arch"``) so
``ov.analyze(run, lenses=...)`` can select which to run; ``requires``/``produces``
order them. The builtins are eagerly imported on first import of this package so
the registry is never half-populated (same robustness rule as the probes).

(The package is named ``analysis`` rather than ``analyze`` so it cannot shadow
the ``ov.analyze`` facade *function*; see ``ov/__init__.py``.)
"""

from __future__ import annotations

from ..registry import Registry
from .context import AnalysisContext, AnalyzerOutput  # noqa: F401

ANALYZER_REGISTRY = Registry("analyzer")
register_analyzer = ANALYZER_REGISTRY.register


def load_builtin_analyzers() -> None:
    """Import builtin analyzer modules so their ``@register_analyzer`` runs.

    Safe to call repeatedly. Invoked once at the bottom of this module so the
    registry is fully populated on import (no order-dependent gaps).
    """
    from .arch import api, bundles, dependencies, framework, rendering  # noqa: F401
    from .ux import a11y, contrast_focus, cwv, heuristics, metrics  # noqa: F401


load_builtin_analyzers()
