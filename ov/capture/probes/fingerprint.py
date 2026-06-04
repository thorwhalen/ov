"""Fingerprint probe: a built-in, license-clean technology detector.

The spec flags ``wappalyzer-next`` and the ``enthec/webappanalyzer`` ruleset as
GPL-3.0, incompatible with ``ov``'s MIT license (§6.2). So rather than depend on
them, this probe ships a small deterministic detector over the highest-signal,
lowest-false-positive sources: framework state-injection globals
(``__NEXT_DATA__``/``__NUXT__``/``__remixContext`` ...), devtools hooks, bundler
signatures, the ``<meta name=generator>`` tag, ``ng-version``, and response
headers. ``wappalyzer``/Retire.js remain available as *optional* external CLIs.

Each detection is a :class:`~ov.base.TechFinding` carrying confidence + provenance
and is appended to ``ctx.run.fingerprint`` so ``ov observe`` populates the run
immediately; the raw signals are also stored as an artifact for re-analysis.
"""

from __future__ import annotations

import json
from typing import Any

from ...base import Artifact, TechFinding
from . import Probe, ProbeContext, register_probe

_SIGNAL_JS = r"""
() => {
  const w = window;
  const has = (k) => { try { return k in w; } catch (e) { return false; } };
  const keys = Object.keys(w);
  const q = (sel) => document.querySelector(sel);
  const gen = q('meta[name="generator"]');
  const ngEl = q('[ng-version]');
  return {
    globals: {
      __NEXT_DATA__: has('__NEXT_DATA__'),
      __NUXT__: has('__NUXT__'),
      __remixContext: has('__remixContext'),
      __gatsby: has('___gatsby') || has('__GATSBY_RESOLVED'),
      __sveltekit: keys.some(k => k.startsWith('__sveltekit')),
      react_devtools: has('__REACT_DEVTOOLS_GLOBAL_HOOK__'),
      vue: has('__VUE_DEVTOOLS_GLOBAL_HOOK__') || has('__VUE__'),
      redux: has('__REDUX_DEVTOOLS_EXTENSION__'),
      jquery: has('jQuery'),
      angular: has('getAllAngularRootElements') || has('ng'),
      webpack: keys.some(k => k.startsWith('webpackChunk')) || has('__webpack_require__'),
    },
    metaGenerator: gen ? gen.getAttribute('content') : null,
    ngVersion: ngEl ? ngEl.getAttribute('ng-version') : null,
    reactRoot: !!q('[data-reactroot], #__next, #root, #app'),
    scripts: Array.from(document.scripts).map(s => s.src).filter(Boolean).slice(0, 120),
  };
}
"""

# global signal -> (technology name, categories, confidence, implies)
_GLOBAL_RULES: dict[str, tuple[str, list[str], int, list[str]]] = {
    "__NEXT_DATA__": ("Next.js", ["framework", "ssr"], 95, ["React"]),
    "__NUXT__": ("Nuxt", ["framework", "ssr"], 95, ["Vue.js"]),
    "__remixContext": ("Remix", ["framework", "ssr"], 95, ["React"]),
    "__gatsby": ("Gatsby", ["framework", "ssg"], 90, ["React"]),
    "__sveltekit": ("SvelteKit", ["framework"], 90, ["Svelte"]),
    "react_devtools": ("React", ["ui-framework"], 80, []),
    "vue": ("Vue.js", ["ui-framework"], 80, []),
    "redux": ("Redux", ["state-management"], 75, []),
    "jquery": ("jQuery", ["library"], 70, []),
    "angular": ("Angular", ["framework"], 80, []),
    "webpack": ("webpack", ["bundler"], 70, []),
}


def detect_technologies(
    signals: dict[str, Any], headers: dict[str, str] | None = None
) -> list[TechFinding]:
    """Map captured fingerprint signals (+ headers) into scored :class:`TechFinding`s.

    Reusable across modules (the arch analyzer enriches these with bundle/source
    -map evidence). Prefers ``js``/``dom`` signals over loose header regex.

    >>> findings = detect_technologies({"globals": {"__NEXT_DATA__": True}})
    >>> sorted(f.name for f in findings)
    ['Next.js', 'React']
    """
    findings: dict[str, TechFinding] = {}

    def _add(
        name: str,
        cats: list[str],
        conf: int,
        version: str | None = None,
        prov: str = "global",
    ) -> None:
        existing = findings.get(name)
        if existing is None:
            findings[name] = TechFinding(
                name=name,
                categories=list(cats),
                version=version,
                confidence=conf,
                provenance=[prov],
            )
            return
        # Accumulate evidence: keep every provenance, the max confidence, the
        # first known version, and the union of categories.
        if prov not in existing.provenance:
            existing.provenance.append(prov)
        existing.confidence = max(existing.confidence, conf)
        if version and not existing.version:
            existing.version = version
        for c in cats:
            if c not in existing.categories:
                existing.categories.append(c)

    for key, present in (signals.get("globals") or {}).items():
        if present and key in _GLOBAL_RULES:
            name, cats, conf, implies = _GLOBAL_RULES[key]
            _add(name, cats, conf, prov=f"window.{key}")
            for implied in implies:
                _add(implied, ["ui-framework"], conf - 10, prov=f"implied-by:{name}")

    if signals.get("ngVersion"):
        _add(
            "Angular",
            ["framework"],
            95,
            version=signals["ngVersion"],
            prov="ng-version",
        )
    if signals.get("reactRoot") and "React" not in findings:
        _add("React", ["ui-framework"], 55, prov="dom:react-root")

    gen = signals.get("metaGenerator")
    if gen:
        _add(gen.split()[0], ["cms-or-generator"], 70, prov="meta:generator")

    headers = headers or {}
    powered = headers.get("x-powered-by") or headers.get("X-Powered-By")
    if powered:
        _add(powered.split("/")[0].strip(), ["server"], 60, prov="header:x-powered-by")
    server = headers.get("server") or headers.get("Server")
    if server:
        _add(server.split("/")[0].strip(), ["server"], 50, prov="header:server")

    return sorted(findings.values(), key=lambda f: (-f.confidence, f.name))


@register_probe("fingerprint", requires=("network",), produces=("fingerprint",))
class FingerprintProbe(Probe):
    """Gather in-page signals + headers and populate ``run.fingerprint``."""

    name = "fingerprint"

    def finalize(self, ctx: ProbeContext) -> list[Artifact]:
        signals: dict[str, Any] = {}
        if ctx.page is not None:
            try:
                signals = ctx.page.evaluate(_SIGNAL_JS)
            except Exception:  # noqa: BLE001
                signals = {}

        headers = self._main_doc_headers(ctx)
        findings = detect_technologies(signals, headers)
        ctx.run.fingerprint = findings

        art = ctx.store.put_artifact(
            json.dumps({"signals": signals, "headers": headers}, indent=2).encode(
                "utf-8"
            ),
            kind="fingerprint",
            content_type="application/json",
            meta={"technologies": [f.name for f in findings]},
        )
        return [art]

    @staticmethod
    def _main_doc_headers(ctx: ProbeContext) -> dict[str, str]:
        records = ctx.extras.get("network_records", [])
        for rec in records:
            if rec.get("resource_type") == "document":
                return rec.get("response_headers", {})
        return {}
