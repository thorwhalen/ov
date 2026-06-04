"""Architecture-reconstruction analyzers (§6, D2).

A deterministic ``fingerprint -> bundle-recovery -> api-synthesis`` pipeline,
each analyzer reading captured artifacts and emitting scored facts
(:class:`~ov.base.TechFinding`/:class:`~ov.base.Endpoint`) with provenance. The
single biggest lever is source-map presence (reconstruction quality is bimodal),
so ``source_maps_present`` gates downstream confidence. Heavy JS-only tooling runs
in the optional Node sidecar; everything degrades gracefully without it.
"""
