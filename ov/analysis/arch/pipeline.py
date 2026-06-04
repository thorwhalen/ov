"""The arch pipeline as a composable transform (§6: fingerprint -> bundles -> api).

The architecture lens is conceptually a three-stage deterministic pipeline. The
registry already orders the arch analyzers by their declared dependencies; this
module exposes that ordering and a convenience that runs *only* the arch lens
over a context and returns the merged output -- useful for callers (or tests)
that want architecture facts without the full UX pass.
"""

from __future__ import annotations

from .. import ANALYZER_REGISTRY
from ..context import AnalysisContext, AnalyzerOutput
from ..run import merge_output

#: Canonical arch stage order (fingerprint detection -> bundle recovery -> API synthesis).
ARCH_STAGES = ("rendering", "framework", "bundles", "api_surface", "dependencies")


def run_arch_pipeline(ctx: AnalysisContext) -> AnalyzerOutput:
    """Run the arch-lens analyzers in dependency order; return one merged output."""
    arch_names = [n for n, item in ANALYZER_REGISTRY.items.items() if item.meta.get("lens") == "arch"]
    merged = AnalyzerOutput()
    for item in ANALYZER_REGISTRY.ordered(arch_names):
        out = item.fn(ctx)
        merge_output(ctx.run, out)
        merged.findings.extend(out.findings)
        merged.endpoints.extend(out.endpoints)
        merged.tech.extend(out.tech)
        merged.run_fields.update(out.run_fields)
        merged.summary[item.name] = out.summary
    return merged
