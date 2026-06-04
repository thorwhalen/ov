"""The analysis context + analyzer output -- the currency of the pure analyzers.

Analyzers are pure functions over captured *artifacts*: they never touch a
browser or a model. :class:`AnalysisContext` injects the run + store + config and
gives small helpers for reading artifacts by kind; :class:`AnalyzerOutput` is
what every analyzer returns, which the orchestrator merges back into the run.

This is the testability seam: feed an analyzer synthetic artifacts and assert on
the :class:`~ov.base.Finding`s it returns -- no network, no browser, no LLM.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..base import Artifact, CaptureRun, Endpoint, Finding, TechFinding
from ..config import OvConfig


@dataclass
class AnalyzerOutput:
    """What an analyzer produces; merged into the run by the orchestrator."""

    findings: list[Finding] = field(default_factory=list)
    endpoints: list[Endpoint] = field(default_factory=list)
    tech: list[TechFinding] = field(default_factory=list)
    run_fields: dict[str, Any] = field(default_factory=dict)  # e.g. rendering_model
    summary: dict[str, Any] = field(
        default_factory=dict
    )  # surfaced in analyze()'s dict


@dataclass
class AnalysisContext:
    """Everything an analyzer needs, plus artifact-reading helpers."""

    run: CaptureRun
    store: Any  # CaptureStore (avoid import cycle)
    config: OvConfig = field(default_factory=OvConfig)
    extras: dict[str, Any] = field(default_factory=dict)

    def artifacts(self, kind: str) -> list[Artifact]:
        """All artifacts of ``kind`` in run order."""
        return [a for a in self.run.artifacts if a.kind == kind]

    def latest(self, kind: str) -> Artifact | None:
        """The last artifact of ``kind`` (or ``None``)."""
        items = self.artifacts(kind)
        return items[-1] if items else None

    def raw(self, artifact: Artifact) -> bytes:
        """Raw bytes for an artifact."""
        return self.store.artifact_bytes(artifact)

    def text(self, artifact: Artifact) -> str:
        """Decode an artifact's bytes as UTF-8 text."""
        return self.raw(artifact).decode("utf-8", errors="replace")

    def json(self, artifact: Artifact) -> Any:
        """Parse an artifact's bytes as JSON (``None`` on failure)."""
        try:
            return json.loads(self.text(artifact))
        except (ValueError, TypeError):
            return None

    def jsons(self, kind: str) -> list[Any]:
        """Parse every artifact of ``kind`` as JSON, dropping unparseable ones."""
        out = []
        for a in self.artifacts(kind):
            parsed = self.json(a)
            if parsed is not None:
                out.append(parsed)
        return out

    def by_step(self, kind: str) -> dict[str | None, list[Artifact]]:
        """Group artifacts of ``kind`` by their ``step_id``."""
        grouped: dict[str | None, list[Artifact]] = {}
        for a in self.artifacts(kind):
            grouped.setdefault(a.step_id, []).append(a)
        return grouped
