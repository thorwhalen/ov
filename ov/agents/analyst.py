"""The Analyst agents (UX + Arch) — grounded judgment over an evidence bundle.

The hard architectural seam (§8.1, D4): **analysts never touch the live browser.**
They consume a *deterministic, model-free* evidence bundle — marked screenshots +
derived facts + a cite-or-abstain contract — and add narrative judgment on top. The
package supplies three reused-unchanged pieces and the agent wires them:

1. :func:`~ov.analysis.evidence.build_evidence_bundle` assembles the bundle (Set-of-
   Mark regions, computed token budget);
2. the injected ``judge`` (an LLM under the cite-or-abstain contract) returns
   candidate :class:`~ov.base.Finding`s (``source_layer="llm"``);
3. :func:`~ov.analysis.reliability.verify_findings` gates them — any claim without a
   *resolvable* evidence ref (or referencing an unknown mark) is **downgraded to
   ``undetermined``**, never silently dropped.

So the model interprets; it never authors facts. The judge is injected (DI), so the
agent is unit-testable with a stub that returns canned findings — no API call, no
vision model. UX routes to Sonnet, Arch to Opus (§10). Satisfies ``aw.AgenticStep``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, MutableMapping, Optional

from ..analysis.evidence import build_evidence_bundle
from ..analysis.reliability import verify_findings
from ..base import CaptureRun, Evidence, EvidenceBundle, Finding

#: A judge maps an evidence bundle to candidate findings (dicts or Findings).
Judge = Callable[..., list]

_LENS_DEFAULTS = {
    "ux": {"model": "sonnet", "category": "ux", "type": "ux_issue"},
    "arch": {"model": "opus", "category": "architecture", "type": "arch_fact"},
}


@dataclass
class AnalystAgent:
    """Interpret a captured run's evidence bundle into grounded findings (UX or Arch).

    Args:
        lens: ``"ux"`` or ``"arch"`` — selects default model + finding defaults.
        llm: the injected LLM (a callable, an object exposing ``structured`` for the
            multimodal path, an ``aw`` ``StepConfig``, or ``None``). Ignored if a
            ``judge`` is given.
        judge: ``(bundle, *, run, store) -> list[Finding | dict]``. Override the whole
            LLM step (tests, alternative providers). Defaults to :meth:`_default_judge`.
        model: model selector for the image-budget + info (defaults from the lens).
        max_marks: cap on Set-of-Mark regions in the bundle.
    """

    lens: str
    llm: Any = None
    judge: Optional[Judge] = None
    model: Optional[str] = None
    max_marks: int = 20
    task: Optional[str] = None
    name: str = ""

    def __post_init__(self) -> None:
        if self.lens not in _LENS_DEFAULTS:
            raise ValueError(f"lens must be 'ux' or 'arch', got {self.lens!r}")
        self.model = self.model or _LENS_DEFAULTS[self.lens]["model"]
        self.name = self.name or f"{self.lens}-analyst"

    # --- aw.AgenticStep ----------------------------------------------------- #

    def execute(
        self, input_data: Any, context: Optional[MutableMapping[str, Any]] = None
    ) -> tuple[list[Finding], dict[str, Any]]:
        """Analyze a run (or a prebuilt bundle) → ``(verified_findings, info)`` (aw protocol).

        ``input_data`` may be a :class:`~ov.base.CaptureRun`, an
        :class:`~ov.base.EvidenceBundle`, or a mapping carrying ``run`` / ``store`` /
        ``bundle``. The verified LLM findings are appended to ``run.findings`` (additive
        — ``source_layer`` keeps them distinct from deterministic facts) and returned.
        """
        run, store, bundle = self._resolve_inputs(input_data, context)
        if bundle is None:
            bundle = build_evidence_bundle(
                run,
                store,
                model=self.model,
                max_marks=self.max_marks,
                task=self.task or self._default_task(),
            )

        judge = self.judge or self._default_judge
        candidates = self._coerce_findings(judge(bundle, run=run, store=store))
        report = verify_findings(candidates, run, bundle=bundle)
        run.findings.extend(report.all_findings)

        info = {
            "success": True,
            "agent": self.name,
            "lens": self.lens,
            "model": self.model,
            "backend": "in-package",
            "candidates": len(candidates),
            "kept": len(report.kept),
            "downgraded": len(report.downgraded),
            "bundle_facts": len(bundle.facts),
            "run_id": run.run_id,
        }
        if context is not None:
            context[self.name] = {
                k: info[k] for k in ("kept", "downgraded", "candidates")
            }
        return report.all_findings, info

    # --- inputs ------------------------------------------------------------- #

    def _resolve_inputs(
        self, input_data: Any, context: Optional[MutableMapping]
    ) -> tuple[CaptureRun, Any, Optional[EvidenceBundle]]:
        ctx = context or {}
        if isinstance(input_data, EvidenceBundle):
            run = ctx.get("run") or CaptureRun()
            return run, ctx.get("store"), input_data
        if isinstance(input_data, CaptureRun):
            return input_data, ctx.get("store"), ctx.get("bundle")
        if isinstance(input_data, MutableMapping):
            run = input_data.get("run") or ctx.get("run") or CaptureRun()
            return (
                run,
                input_data.get("store") or ctx.get("store"),
                input_data.get("bundle"),
            )
        run = ctx.get("run") or CaptureRun()
        return run, ctx.get("store"), ctx.get("bundle")

    # --- the default (LLM) judge ------------------------------------------- #

    def _default_judge(
        self, bundle: EvidenceBundle, *, run: CaptureRun, store: Any
    ) -> list:
        """Call the injected LLM under the cite-or-abstain contract; return raw findings.

        Returns ``[]`` (no findings) when no LLM is resolvable — the deterministic
        findings already on the run are the floor; the analyst layer is purely additive.
        """
        from .llm import structured

        prompt = self._bundle_prompt(bundle)
        images = self._bundle_images(bundle, run, store)
        data = structured(prompt, self._findings_schema(), llm=self.llm, images=images)
        if not isinstance(data, dict):
            return []
        return data.get("findings", []) or []

    def _findings_schema(self) -> dict:
        """An object schema wrapping a list of :class:`~ov.base.Finding` (for structured output)."""
        return {
            "type": "object",
            "properties": {
                "findings": {"type": "array", "items": Finding.model_json_schema()}
            },
            "required": ["findings"],
        }

    def _bundle_prompt(self, bundle: EvidenceBundle) -> str:
        """Render the bundle as text: contract + cited facts + task (images sent separately)."""
        facts = (
            "\n".join(
                f"  - {ev.evidence_id}: {ev.summary}"
                + (f"  [{ev.meta.get('mark')}]" if ev.meta.get("mark") else "")
                for ev in bundle.facts
            )
            or "  (no facts)"
        )
        marks = ", ".join(bundle.marks) or "(none)"
        return (
            f"{bundle.contract}\n\n"
            f"Marked regions: {marks}\n"
            f"Facts you may cite (use these ids in evidence_refs):\n{facts}\n\n"
            f"Task: {bundle.task}\n\n"
            'Return JSON {"findings": [...]}. Each finding MUST set source_layer='
            '"llm", cite at least one fact/mark id in evidence_refs, and use type '
            "'undetermined' when the evidence does not support a claim. Fields: type, "
            "signal, category, title, evidence_refs, judgment, suggested_fix."
        )

    @staticmethod
    def _bundle_images(bundle: EvidenceBundle, run: CaptureRun, store: Any) -> list:
        """Resolve the bundle's marked-image artifacts to bytes (for a vision client)."""
        if store is None:
            return []
        images = []
        for artifact_id in (
            *bundle.marked_image_artifact_ids,
            *bundle.crop_artifact_ids,
        ):
            artifact = run.artifact_by_id(artifact_id)
            getter = getattr(store, "artifact_bytes", None)
            if artifact is not None and callable(getter):
                try:
                    images.append(getter(artifact))
                except Exception:  # noqa: BLE001 - images are best-effort grounding aids
                    continue
        return images

    # --- coercion ----------------------------------------------------------- #

    def _coerce_findings(self, raw: Any) -> list[Finding]:
        """Turn the judge's output (dicts and/or Findings) into valid LLM Findings."""
        defaults = _LENS_DEFAULTS[self.lens]
        out: list[Finding] = []
        for item in raw or []:
            if isinstance(item, Finding):
                item.source_layer = "llm"
                out.append(item)
                continue
            if not isinstance(item, dict):
                continue
            data = dict(item)
            # Fill required fields, overriding *falsy* values (explicit null/"" from
            # the judge), not just absent keys — setdefault would keep a present None
            # and the Finding would then fail validation and be silently dropped.
            if not data.get("category"):
                data["category"] = defaults["category"]
            if not data.get("type"):
                data["type"] = defaults["type"]
            if not data.get("signal"):
                data["signal"] = "llm.finding"
            data["source_layer"] = "llm"
            try:
                out.append(
                    Finding(
                        **{k: v for k, v in data.items() if k in Finding.model_fields}
                    )
                )
            except Exception:  # noqa: BLE001 - a malformed candidate is dropped, not fatal
                continue
        return out

    def _default_task(self) -> str:
        if self.lens == "ux":
            return (
                "Assess usability & accessibility of the marked regions; cite a "
                "mark/fact id for every issue and give a grounded fix."
            )
        return (
            "Identify architecture facts & reconstruction signals from the cited "
            "evidence; cite a fact id for every claim."
        )


def ux_analyst(llm: Any = None, **kwargs: Any) -> AnalystAgent:
    """A UX/accessibility analyst (Sonnet-routed). ``llm`` is the injected model.

    >>> a = ux_analyst()
    >>> a.lens, a.model, a.name
    ('ux', 'sonnet', 'ux-analyst')
    """
    return AnalystAgent(lens="ux", llm=llm, **kwargs)


def arch_analyst(llm: Any = None, **kwargs: Any) -> AnalystAgent:
    """A software-architecture analyst (Opus-routed). ``llm`` is the injected model.

    >>> arch_analyst().model
    'opus'
    """
    return AnalystAgent(lens="arch", llm=llm, **kwargs)
