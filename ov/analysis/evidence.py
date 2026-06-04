"""The evidence-bundle assembler (§8.1, D4) -- deterministic, model-free.

Builds the grounded bundle a vision LLM (the host) reasons over, so token cost and
grounding are *computed*, not hoped for:

* **Set-of-Mark** -- each discussable region (a step's affordances) gets a stable
  mark id (``R1`` ...) that is overlaid on the screenshot, appears in the facts,
  and is *required* in the model's output. This turns "describe what you see" into
  "interpret marked region R3".
* **Order** -- the bundle is ``[role/system + cite-or-abstain] -> [marked image(s)]
  -> [facts keyed to ids] -> [task last]``.
* **Token budget** -- projected as ``Σ(w×h/750)`` per image against the model cap
  (≈1568 px / 1568 tok standard; ≈2576 px / 4784 tok on Opus 4.7/4.8) *before* the
  call; images are downsampled to fit.
* **Omit raw bytes** -- facts are *derived summaries*, never raw HAR/DOM/bundle
  text; those stay reachable by ``evidence_id`` for just-in-time retrieval.

The actual image overlay needs Pillow (the ``evidence`` extra); everything else
(dimensions, budget, mark assignment, the bundle structure) is pure stdlib so the
budget math and grounding are testable without it.
"""

from __future__ import annotations

import math
import struct
from typing import Any

from ..base import CaptureRun, Evidence, EvidenceBundle, Finding, JourneyStep

#: Per-model image caps: (long-edge pixels, token cap). Opus 4.7/4.8 are larger.
MODEL_CAPS: dict[str, tuple[int, int]] = {
    "opus": (2576, 4784),
    "standard": (1568, 1568),
}

_CITE_OR_ABSTAIN = (
    "You are grounding UX/architecture judgments in captured evidence. Rules: "
    "(1) discuss ONLY the marked regions (R1, R2, ...) and the listed facts; "
    "(2) every claim must cite at least one fact/mark id; "
    "(3) if the evidence does not support a claim, output type 'undetermined' "
    "rather than guessing; (4) never invent a fact field -- cite, never author."
)


def png_dimensions(data: bytes) -> tuple[int, int] | None:
    """Return ``(width, height)`` of a PNG from its IHDR header (stdlib only).

    >>> import base64
    >>> px = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')
    >>> png_dimensions(px)
    (1, 1)
    """
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    try:
        width, height = struct.unpack(">II", data[16:24])
        return int(width), int(height)
    except struct.error:
        return None


def image_token_cost(width: int, height: int) -> int:
    """Anthropic image token estimate ``ceil(w*h/750)``.

    >>> image_token_cost(1000, 1000)
    1334
    """
    return math.ceil((width * height) / 750)


def fit_to_cap(width: int, height: int, model: str = "opus") -> dict[str, Any]:
    """Project tokens and a downsample factor to fit a model's image cap (pure).

    Honors BOTH constraints -- the long-edge pixel cap *and* the token (area) cap
    -- taking whichever is more restrictive, because a long-edge-only clamp can
    still blow the token budget (a 2576x2576 image is ~8853 tokens).

    >>> r = fit_to_cap(5000, 4000, "opus")
    >>> r["downsampled"] and r["fitted"]["tokens"] <= 4784
    True
    >>> fit_to_cap(800, 600, "opus")["downsampled"]
    False
    """
    long_edge_cap, token_cap = MODEL_CAPS.get(model, MODEL_CAPS["standard"])
    long_edge = max(width, height)
    tokens = image_token_cost(width, height)

    edge_factor = long_edge_cap / long_edge if long_edge > long_edge_cap else 1.0
    area_factor = math.sqrt(token_cap / tokens) if tokens > token_cap else 1.0
    factor = min(edge_factor, area_factor)

    fw, fh = (
        (round(width * factor), round(height * factor))
        if factor < 1.0
        else (width, height)
    )
    return {
        "original": {"w": width, "h": height, "tokens": tokens},
        "fitted": {"w": fw, "h": fh, "tokens": image_token_cost(fw, fh)},
        "factor": round(factor, 4),
        "downsampled": factor < 1.0,
        "token_cap": token_cap,
        "long_edge_cap": long_edge_cap,
    }


def _pick_step(run: CaptureRun, step_id: str | None) -> JourneyStep | None:
    if step_id:
        return next((s for s in run.steps if s.id == step_id), None)
    # otherwise the richest step that has a screenshot
    screenshot_steps = [
        s
        for s in run.steps
        if any(a.kind == "screenshot" and a.step_id == s.id for a in run.artifacts)
    ]
    candidates = screenshot_steps or run.steps
    return max(candidates, key=lambda s: len(s.affordances_seen), default=None)


def _screenshot_for(run: CaptureRun, step: JourneyStep):
    """Return *this step's own* screenshot, or None.

    Never falls back to an arbitrary screenshot: set-of-mark grounding requires the
    overlaid regions to belong to the image actually shown, so marks are only built
    when the selected step has its own screenshot.
    """
    return next(
        (a for a in run.artifacts if a.kind == "screenshot" and a.step_id == step.id),
        None,
    )


def build_evidence_bundle(
    run: CaptureRun,
    store: Any,
    *,
    step_id: str | None = None,
    model: str = "opus",
    task: str = "Assess UX and architecture; cite marks/facts for every claim.",
    max_marks: int = 20,
    overlay: bool = True,
    out_dir: Any = None,
) -> EvidenceBundle:
    """Assemble a grounded :class:`~ov.base.EvidenceBundle` for a step (model-free).

    Marks are drawn from the step's affordances (which carry bounding boxes);
    facts include those marked regions plus the deterministic findings touching the
    step. The token budget is computed against ``model``'s cap. When Pillow is
    available and ``overlay`` is set, a numbered overlay screenshot (and crops for
    small regions) are rendered and stored; otherwise the original screenshot is
    referenced and a note is recorded.
    """
    step = _pick_step(run, step_id)
    bundle = EvidenceBundle(
        step_id=step.id if step else None, contract=_CITE_OR_ABSTAIN, task=task
    )
    if step is None:
        return bundle

    shot = _screenshot_for(run, step)
    budget: dict[str, Any] = {"model": model}
    if shot is not None:
        dims = png_dimensions(store.artifact_bytes(shot))
        if dims:
            budget.update(fit_to_cap(dims[0], dims[1], model))

    facts: list[Evidence] = []
    marks: dict[str, str] = {}
    # Marks are regions ON the screenshot, so only build them when this step has
    # its own screenshot -- otherwise we'd ground marks against the wrong image.
    affordances = (
        [a for a in step.affordances_seen if a.bbox][:max_marks]
        if shot is not None
        else []
    )
    for i, aff in enumerate(affordances, 1):
        mark_id = f"R{i}"
        ev = Evidence(
            evidence_id=f"mark:{step.id}#{mark_id}",
            kind="mark",
            artifact_id=shot.artifact_id if shot else None,
            summary=f"{aff.role} '{aff.name}'" if aff.name else aff.role,
            meta={"mark": mark_id, "bbox": list(aff.bbox)},
        )
        facts.append(ev)
        marks[mark_id] = ev.evidence_id

    # deterministic findings touching this step (or global, capped) become facts
    step_findings = [
        f for f in run.findings if (f.location or {}).get("step_id") == step.id
    ]
    for f in (step_findings or run.findings)[:max_marks]:
        facts.append(
            Evidence(
                evidence_id=f"find:{f.finding_id}",
                kind=_evidence_kind(f),
                artifact_id=f.evidence_refs[0] if f.evidence_refs else None,
                summary=f"{f.signal}: {f.observed or f.title}",
                meta={
                    "severity": f.severity.score if f.severity else None,
                    "needs_human_review": f.needs_human_review,
                },
            )
        )

    bundle.facts = facts
    bundle.marks = marks
    bundle.token_budget = budget

    marked_ids, crop_ids = (
        _render_overlay(run, store, step, shot, affordances, budget, out_dir)
        if overlay
        else ([], [])
    )
    if marked_ids:
        bundle.marked_image_artifact_ids = marked_ids
        bundle.crop_artifact_ids = crop_ids
    elif shot is not None:
        bundle.marked_image_artifact_ids = [shot.artifact_id]
        bundle.token_budget.setdefault(
            "note", "set-of-mark overlay skipped (Pillow not installed)"
        )
    return bundle


def _evidence_kind(f: Finding) -> str:
    return {"performance": "metric", "architecture": "stack"}.get(f.category, "dom")


def _render_overlay(run, store, step, shot, affordances, budget, out_dir):
    """Overlay numbered marks on the screenshot (Pillow); return (marked_ids, crop_ids)."""
    if shot is None:
        return [], []
    try:
        import io

        from PIL import Image, ImageDraw
    except ImportError:
        return [], []
    try:
        img = Image.open(io.BytesIO(store.artifact_bytes(shot))).convert("RGB")
        factor = budget.get("factor", 1.0)
        if factor < 1.0:
            img = img.resize((budget["fitted"]["w"], budget["fitted"]["h"]))
        draw = ImageDraw.Draw(img)
        for i, aff in enumerate(affordances, 1):
            x, y, w, h = (c * factor for c in aff.bbox)
            draw.rectangle([x, y, x + w, y + h], outline=(255, 0, 0), width=2)
            draw.text((x + 2, max(0, y - 12)), f"R{i}", fill=(255, 0, 0))
        out = io.BytesIO()
        img.save(out, format="PNG")
        art = store.put_artifact(
            out.getvalue(),
            kind="screenshot",
            step_id=step.id,
            content_type="image/png",
            meta={"set_of_mark": True},
        )
        run.artifacts.append(art)
        if out_dir:
            from pathlib import Path

            Path(out_dir).mkdir(parents=True, exist_ok=True)
            (Path(out_dir) / f"evidence_{step.id}.png").write_bytes(out.getvalue())

        # Full-vs-crop (§8.1): also emit targeted crops so small regions stay
        # readable after downsampling. Prefer many small crops over one huge image.
        crop_ids = _emit_crops(run, store, step, img, affordances, factor, out_dir)
        return [art.artifact_id], crop_ids
    except Exception:  # noqa: BLE001 - overlay is best-effort
        return [], []


def _emit_crops(
    run, store, step, img, affordances, factor, out_dir, *, max_crops=6, pad=24
):
    """Crop a padded region around each marked affordance; store + return ids."""
    import io

    crop_ids: list[str] = []
    iw, ih = img.size
    for i, aff in enumerate(affordances[:max_crops], 1):
        x, y, w, h = (c * factor for c in aff.bbox)
        box = (
            max(0, int(x - pad)),
            max(0, int(y - pad)),
            min(iw, int(x + w + pad)),
            min(ih, int(y + h + pad)),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        try:
            crop = img.crop(box)
            buf = io.BytesIO()
            crop.save(buf, format="PNG")
            art = store.put_artifact(
                buf.getvalue(),
                kind="screenshot",
                step_id=step.id,
                content_type="image/png",
                meta={"crop_of": f"R{i}"},
            )
            run.artifacts.append(art)
            crop_ids.append(art.artifact_id)
        except Exception:  # noqa: BLE001
            continue
    return crop_ids
