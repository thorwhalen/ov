"""Analysis layer: deterministic analyzers over captured artifacts (Phases 2-3).

Analyzers are registered plugins (:data:`ANALYZER_REGISTRY`) that read a
:class:`~ov.base.CaptureRun` plus its store and emit :class:`~ov.base.Finding`s /
:class:`~ov.base.Endpoint`s / facts -- all model-free and fully testable on
synthetic artifacts. The host (or, later, an in-package agent) adds narrative
judgment *on top* of these via the evidence bundle.

(The package is named ``analysis`` rather than ``analyze`` so it cannot shadow
the ``ov.analyze`` facade *function*; see ``ov/__init__.py``.)
"""

from __future__ import annotations

from ..registry import Registry

ANALYZER_REGISTRY = Registry("analyzer")
register_analyzer = ANALYZER_REGISTRY.register


def load_builtin_analyzers() -> None:
    """Import builtin analyzer modules so their ``@register_analyzer`` runs.

    Populated in Phase 2 (UX engine + arch pipeline). Safe to call repeatedly.
    """
    try:
        from .ux import (  # noqa: F401
            a11y,
            contrast_focus,
            cwv,
            heuristics,
            metrics,
        )
        from .arch import (  # noqa: F401
            api,
            dependencies,
            framework,
            rendering,
        )
    except ImportError:
        # Phase 1: analyzer modules not present yet.
        pass
