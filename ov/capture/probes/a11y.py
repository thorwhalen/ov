"""Accessibility-signals probe: computed text styles (for contrast) + optional axe.

Contrast cannot be judged from static DOM -- it needs *computed* colors. This
probe snapshots, per visible text element, the effective foreground/background
colors, font size/weight, and bbox, so the deterministic
:mod:`ov.analysis.ux.contrast_focus` analyzer can compute WCAG ratios offline.

If an axe-core bundle is resolvable (``OV_AXE_PATH`` or the sidecar's
``node_modules/axe-core/axe.min.js``), it is injected and ``axe.run()`` results
are stored as an ``axe`` artifact -- additive, never required. axe-core is used
as an external tool here (no vendoring), keeping the package license-clean.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ...base import Artifact
from ...util import sidecar_dir
from . import Probe, ProbeContext, register_probe

_STYLES_JS = r"""
(maxEls) => {
  const toRGB = (s) => {
    const m = (s || '').match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map(x => parseFloat(x));
    return [p[0] || 0, p[1] || 0, p[2] || 0, p[3] === undefined ? 1 : p[3]];
  };
  const effBg = (el) => {
    let n = el;
    while (n && n.nodeType === 1) {
      const rgb = toRGB(getComputedStyle(n).backgroundColor);
      if (rgb && rgb[3] !== 0) return rgb.slice(0, 3);
      n = n.parentElement;
    }
    return [255, 255, 255];
  };
  const sel = (el) => {
    if (el.id) return '#' + el.id;
    const parts = []; let n = el;
    while (n && n.nodeType === 1 && parts.length < 4) {
      let s = n.tagName.toLowerCase();
      const p = n.parentElement;
      if (p) {
        const sib = Array.from(p.children).filter(c => c.tagName === n.tagName);
        if (sib.length > 1) s += ':nth-of-type(' + (sib.indexOf(n) + 1) + ')';
      }
      parts.unshift(s); n = p;
    }
    return parts.join('>');
  };
  const out = [];
  const els = document.querySelectorAll(
    'p,span,a,button,h1,h2,h3,h4,h5,h6,li,td,th,label,strong,em,small');
  for (const el of els) {
    if (out.length >= maxEls) break;
    const txt = Array.from(el.childNodes).filter(n => n.nodeType === 3)
                  .map(n => n.textContent).join('').trim();
    if (!txt) continue;
    const cs = getComputedStyle(el);
    const fg = toRGB(cs.color);
    if (!fg) continue;
    const fontSize = parseFloat(cs.fontSize) || 16;
    const bold = (parseInt(cs.fontWeight) || 400) >= 700;
    const large = fontSize >= 24 || (fontSize >= 18.66 && bold);
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    out.push({selector: sel(el), text: txt.slice(0, 60), fg: fg.slice(0, 3),
              bg: effBg(el), fontSize, bold, large});
  }
  return out;
}
"""


def _axe_source() -> str | None:
    """Resolve an axe-core bundle path (env override, then sidecar node_modules)."""
    override = os.environ.get("OV_AXE_PATH")
    candidates = [Path(override)] if override else []
    candidates.append(sidecar_dir() / "node_modules" / "axe-core" / "axe.min.js")
    for c in candidates:
        if c.exists():
            try:
                return c.read_text(encoding="utf-8")
            except OSError:
                continue
    return None


@register_probe("a11y", produces=("a11y_styles", "axe"))
class A11yProbe(Probe):
    """Capture computed text styles (always) + axe-core results (when available)."""

    name = "a11y"
    max_text_elements = 400

    def capture(self, ctx: ProbeContext) -> list[Artifact]:
        page = ctx.page
        if page is None:
            return []
        step_id = ctx.step.id if ctx.step else None
        artifacts: list[Artifact] = []

        try:
            styles = page.evaluate(_STYLES_JS, self.max_text_elements)
            artifacts.append(
                ctx.store.put_artifact(
                    json.dumps(styles, indent=2).encode("utf-8"),
                    kind="a11y_styles",
                    step_id=step_id,
                    content_type="application/json",
                    meta={"url": page.url, "count": len(styles)},
                )
            )
        except Exception:  # noqa: BLE001
            pass

        src = ctx.extras.get("axe_source", "missing")
        if src == "missing":  # resolve once per session
            src = _axe_source()
            ctx.extras["axe_source"] = src
        if src:
            try:
                page.add_script_tag(content=src)
                result = page.evaluate(
                    "async () => await axe.run(document, "
                    "{runOnly: {type: 'tag', values: ['wcag2a','wcag21aa','wcag22aa']}})"
                )
                artifacts.append(
                    ctx.store.put_artifact(
                        json.dumps(result).encode("utf-8"),
                        kind="axe",
                        step_id=step_id,
                        content_type="application/json",
                        meta={"violations": len(result.get("violations", []))},
                    )
                )
            except Exception:  # noqa: BLE001 - axe is best-effort
                pass

        return artifacts
