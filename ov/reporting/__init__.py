"""Report layer: registered Markdown sections + the synopsis (Phase 2).

Each section is a registered function (:func:`register_section`) that takes the
analyses + run and returns a Markdown fragment; :mod:`ov.reporting.render`
concatenates the selected sections. :mod:`ov.reporting.synopsis` performs the
structured map-reduce that compresses many findings into one agent-consumable
synopsis.

(The package is named ``reporting`` rather than ``report`` so it cannot shadow
the ``ov.report`` facade *function*; see ``ov/__init__.py``.)
"""

from __future__ import annotations

from ..registry import Registry

REPORT_SECTION_REGISTRY = Registry("section")
register_section = REPORT_SECTION_REGISTRY.register


def load_builtin_sections() -> None:
    """Import builtin report-section modules so their ``@register_section`` runs.

    Invoked once at the bottom of this module so the section registry is fully
    populated on import (no order-dependent gaps). Safe to call repeatedly.
    """
    from . import sections  # noqa: F401


load_builtin_sections()
