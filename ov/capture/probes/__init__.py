"""Probes -- the registerable units of *what intelligence to gather* (§2).

Each probe is an independent plugin that writes typed artifacts into the capture
store. A probe is a small class implementing the :class:`Probe` lifecycle:

* :meth:`Probe.attach` -- subscribe event listeners *before* navigation (used by
  the streaming probes: network, console, navigation, websocket, sse).
* :meth:`Probe.capture` -- snapshot the current state into artifacts (used by the
  per-state probes: dom, screenshot, perf, storage, fingerprint).
* :meth:`Probe.finalize` -- flush accumulated state into artifacts at run end.

Probes are registered with :func:`register_probe` and ordered by the registry's
``requires``/``produces`` dependency declarations, so e.g. ``assets`` (which
needs the network stream) runs after ``network``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...base import Artifact, CaptureRun, JourneyStep
from ...config import OvConfig
from ...registry import Registry

PROBE_REGISTRY = Registry("probe")
register_probe = PROBE_REGISTRY.register


@dataclass
class ProbeContext:
    """Everything a probe needs, injected by the :class:`CaptureSession`.

    ``extras`` is shared scratch (e.g. the accumulating network record list) so
    streaming probes can hand data to per-state probes without globals.
    """

    store: Any  # CaptureStore (avoid import cycle)
    run: CaptureRun
    config: OvConfig
    page: Any = None  # Playwright Page
    cdp: Any = None  # CdpSession | None
    step: JourneyStep | None = None
    extras: dict[str, Any] = field(default_factory=dict)


class Probe:
    """Base class for probes; override only the lifecycle hooks you need."""

    name: str = "probe"

    def attach(self, ctx: ProbeContext) -> None:
        """Subscribe listeners before navigation. Default: no-op."""

    def capture(self, ctx: ProbeContext) -> list[Artifact]:
        """Snapshot current state into artifacts. Default: nothing."""
        return []

    def finalize(self, ctx: ProbeContext) -> list[Artifact]:
        """Flush accumulated state into artifacts at run end. Default: nothing."""
        return []


def load_builtin_probes() -> None:
    """Import the builtin probe modules so their ``@register_probe`` runs.

    Called by the session; safe to call repeatedly (imports are cached).
    """
    from . import (  # noqa: F401
        assets,
        console,
        dom,
        fingerprint,
        navigation,
        network,
        perf,
        screenshot,
        sse,
        storage,
        websocket,
    )
