"""Source-map recovery: pure functions + the analyzer over synthetic artifacts.

Deterministic and Node-free -- no browser, no sidecar, no model. Exercises the
recovery seam (parse -> sanitize -> recover -> persist -> SBOM) end to end on
synthetic ``.map`` artifacts, plus the security (path-traversal) and idempotency
properties the design depends on.
"""

import base64
import json

from ov.analysis.arch.bundles import analyze_bundles
from ov.analysis.arch.sourcemaps import (
    RecoveredFile,
    extract_inline_map,
    node_modules_packages,
    parse_source_map,
    recover_from_map,
    sanitize_source_path,
)
from ov.analysis.context import AnalysisContext
from ov.analysis.run import run_analysis
from ov.base import CaptureRun, JourneyStep


def _ctx(store, run):
    return AnalysisContext(run=run, store=store)


def _run_with(artifacts, **kw):
    return CaptureRun(target_url="http://t.example", artifacts=list(artifacts), **kw)


def _js_network(store, *, url, body, marker=True):
    """A JS bundle request body + a network record pointing at it (present=True via marker)."""
    text = body + ("\n//# sourceMappingURL=app.js.map" if marker else "")
    art = store.put_artifact(
        text.encode(), kind="request", content_type="application/javascript"
    )
    rec = {
        "url": url,
        "resource_type": "script",
        "status": 200,
        "response_headers": {"content-type": "application/javascript"},
        "body_artifact_id": art.artifact_id,
    }
    return art, rec


_MAP_OBJ = {
    "version": 3,
    "sources": [
        "webpack:///src/App.tsx",
        "webpack:///node_modules/lodash/lodash.js",
        "webpack:///node_modules/.pnpm/axios@1.6.2/node_modules/axios/index.js",
        "webpack:///../../../etc/passwd",  # traversal -> must be skipped
    ],
    "sourcesContent": [
        "export const App = () => null",
        "module.exports = {}",
        "module.exports = axios",
        "root:x:0:0",
    ],
}


# --- pure: parse + sanitize ------------------------------------------------ #


def test_parse_source_map_validates_v3():
    assert parse_source_map('{"version":3,"sources":["a.js"]}')["version"] == 3
    assert parse_source_map("not json") is None
    assert parse_source_map('{"version":3}') is None  # no sources -> not a map


def test_sanitize_strips_scheme_and_contains_traversal():
    assert sanitize_source_path("webpack:///src/App.tsx") == "src/App.tsx"
    assert sanitize_source_path("a.js", source_root="webpack:///src/") == "src/a.js"
    assert sanitize_source_path("webpack:///./a/../b.js") == "b.js"
    assert sanitize_source_path("../../etc/passwd") is None
    assert sanitize_source_path("/abs/leading") == "abs/leading"  # de-absolutized
    assert sanitize_source_path("C:/Windows/x") is None  # windows-abs refused


# --- pure: recover_from_map ------------------------------------------------ #


def test_recover_from_map_skips_unsafe_and_null():
    obj = {
        "version": 3,
        "sources": ["webpack:///a.js", "webpack:///../evil", "webpack:///b.js"],
        "sourcesContent": ["A", "EVIL", None],  # b.js has no content -> not recovered
    }
    rec = recover_from_map(json.dumps(obj))
    assert [f.path for f in rec.files] == ["a.js"]
    assert rec.skipped_unsafe == 1
    assert rec.had_sources_content is True


# --- pure: node_modules version inference ---------------------------------- #


def test_node_modules_versions_pnpm_pkgjson_and_scoped():
    files = [
        RecoveredFile("node_modules/lodash/lodash.js", "x", "x"),
        RecoveredFile("node_modules/@scope/ui/index.js", "y", "y"),
        RecoveredFile(
            "node_modules/.pnpm/axios@1.6.2/node_modules/axios/i.js", "z", "z"
        ),
        RecoveredFile("node_modules/react/package.json", '{"version":"18.3.1"}', "p"),
        RecoveredFile("src/app.js", "not a dep", "src/app.js"),
    ]
    d = dict(node_modules_packages(files))
    assert d["lodash"] is None
    assert d["axios"] == "1.6.2"  # version from the pnpm path
    assert d["react"] == "18.3.1"  # version from recovered package.json
    assert "@scope/ui" in d
    assert "app.js" not in d  # non-node_modules paths are not packages


# --- pure: inline data-URI maps -------------------------------------------- #


def test_extract_inline_map_base64_and_external():
    payload = base64.b64encode(json.dumps(_MAP_OBJ).encode()).decode()
    js = "a=1\n//# sourceMappingURL=data:application/json;base64," + payload
    assert json.loads(extract_inline_map(js))["version"] == 3
    assert extract_inline_map("a=1\n//# sourceMappingURL=app.js.map") is None


# --- analyzer: recovery over an explicit source_map artifact --------------- #


def test_analyze_bundles_recovers_tree_and_sbom(tmp_store):
    js_art, rec = _js_network(tmp_store, url="http://t.example/app.js", body="var x=1;")
    net = tmp_store.put_artifact(
        json.dumps([rec]).encode(), kind="network", content_type="application/json"
    )
    smap = tmp_store.put_artifact(
        json.dumps(_MAP_OBJ).encode(),
        kind="source_map",
        content_type="application/json",
    )
    run = _run_with([js_art, net, smap])
    out = analyze_bundles(_ctx(tmp_store, run))

    assert out.run_fields["source_maps_present"] is True
    md = next(f for f in out.findings if f.signal == "arch.source_maps").metric_detail
    assert md["recovered_files"] == 3  # App.tsx + lodash + axios (passwd skipped)
    assert md["recovered_packages"] == 2
    assert md["skipped_unsafe_paths"] == 1
    assert md["had_sources_content"] is True
    assert md["manifest_uri"]

    # SBOM: recovered deps are top-provenance TechFindings
    by_name = {t.name: t for t in out.tech}
    assert by_name["axios"].version == "1.6.2" and by_name["axios"].confidence == 95
    assert by_name["lodash"].version is None and by_name["lodash"].confidence == 85
    assert all(
        t.provenance == ["sourcemap"] and "dependency" in t.categories for t in out.tech
    )

    # recovered files persisted + resolvable via the manifest
    manifest = json.loads(tmp_store.artifact_bytes(md["manifest_uri"]).decode())
    assert {m["path"] for m in manifest} == {
        "src/App.tsx",
        "node_modules/lodash/lodash.js",
        "node_modules/.pnpm/axios@1.6.2/node_modules/axios/index.js",
    }
    app = next(m for m in manifest if m["path"] == "src/App.tsx")
    assert (
        tmp_store.artifact_bytes(app["uri"]).decode() == "export const App = () => null"
    )

    # the analyzer must NOT mutate run.artifacts (idempotency contract)
    assert len(run.artifacts) == 3


def test_analyze_bundles_recovers_from_inline_map(tmp_store):
    payload = base64.b64encode(json.dumps(_MAP_OBJ).encode()).decode()
    body = "var x=1;\n//# sourceMappingURL=data:application/json;base64," + payload
    art = tmp_store.put_artifact(
        body.encode(), kind="request", content_type="application/javascript"
    )
    rec = {
        "url": "http://t.example/app.js",
        "resource_type": "script",
        "status": 200,
        "response_headers": {"content-type": "application/javascript"},
        "body_artifact_id": art.artifact_id,
    }
    net = tmp_store.put_artifact(
        json.dumps([rec]).encode(), kind="network", content_type="application/json"
    )
    out = analyze_bundles(_ctx(tmp_store, _run_with([art, net])))
    md = next(f for f in out.findings if f.signal == "arch.source_maps").metric_detail
    assert md["recovered_files"] == 3 and md["maps_consumed"] == 1


def test_analyze_bundles_no_maps_recovers_nothing(tmp_store):
    art, rec = _js_network(
        tmp_store, url="http://t/app.js", body="var x=1;", marker=False
    )
    net = tmp_store.put_artifact(
        json.dumps([rec]).encode(), kind="network", content_type="application/json"
    )
    out = analyze_bundles(_ctx(tmp_store, _run_with([art, net])))
    assert out.run_fields["source_maps_present"] is False
    md = next(f for f in out.findings if f.signal == "arch.source_maps").metric_detail
    assert md["recovered_files"] == 0
    assert not out.tech


def test_source_map_artifact_alone_marks_present(tmp_store):
    # No sourceMappingURL footer in any bundle, but a captured source_map artifact
    # (the capture probe's output) is itself evidence -> present + recovered.
    art, rec = _js_network(
        tmp_store, url="http://t/app.js", body="var x=1;", marker=False
    )
    net = tmp_store.put_artifact(
        json.dumps([rec]).encode(), kind="network", content_type="application/json"
    )
    smap = tmp_store.put_artifact(
        json.dumps(_MAP_OBJ).encode(),
        kind="source_map",
        content_type="application/json",
    )
    out = analyze_bundles(_ctx(tmp_store, _run_with([art, net, smap])))
    assert out.run_fields["source_maps_present"] is True
    md = next(f for f in out.findings if f.signal == "arch.source_maps").metric_detail
    assert md["recovered_files"] == 3


# --- idempotency across re-analysis ---------------------------------------- #


def test_recovery_is_idempotent_across_reanalysis(tmp_store):
    js_art, rec = _js_network(tmp_store, url="http://t.example/app.js", body="var x=1;")
    net = tmp_store.put_artifact(
        json.dumps([rec]).encode(), kind="network", content_type="application/json"
    )
    smap = tmp_store.put_artifact(
        json.dumps(_MAP_OBJ).encode(),
        kind="source_map",
        content_type="application/json",
    )
    dom = tmp_store.put_artifact(
        b"<html lang='en'><body></body></html>", kind="dom", content_type="text/html"
    )
    console = tmp_store.put_artifact(
        b"[]", kind="console", content_type="application/json"
    )
    run = _run_with(
        [js_art, net, smap, dom, console],
        steps=[JourneyStep(intent="load", post_obs_hash="h1")],
    )
    tmp_store.save_run(run)

    run_analysis(run, store=tmp_store)
    deps_first = sorted(t.name for t in run.fingerprint if "sourcemap" in t.provenance)
    fp_first = sorted(t.name for t in run.fingerprint)
    assert {"axios", "lodash"} <= set(deps_first)

    run_analysis(run, store=tmp_store)  # re-analyze -> no duplication
    assert sorted(t.name for t in run.fingerprint) == fp_first
    # idempotency also holds for the recovered deps' version/provenance, not just names
    axios = next(t for t in run.fingerprint if t.name == "axios")
    assert axios.version == "1.6.2" and axios.provenance == ["sourcemap"]


# --- hardening regressions (from adversarial review) ----------------------- #


def test_sanitize_rejects_backslash_traversal_and_control_chars():
    assert sanitize_source_path("..\\..\\..\\Windows\\System32") is None
    assert sanitize_source_path("a\\..\\b.js") == "b.js"  # backslash = separator
    assert sanitize_source_path("foo\x00bar") is None  # NUL rejected
    assert sanitize_source_path("\\Windows\\x") == "Windows/x"  # de-absolutized


def test_recover_from_map_ignores_non_string_and_non_list():
    # non-string sourcesContent entry must be skipped, never .encode()'d downstream
    r = recover_from_map(
        '{"version":3,"sources":["webpack:///a.js","webpack:///b.js"],'
        '"sourcesContent":[42,"ok"]}'
    )
    assert [f.path for f in r.files] == ["b.js"]
    # non-string source entry is skipped, not coerced into a fabricated path
    r2 = recover_from_map(
        '{"version":3,"sources":[null,"webpack:///c.js"],"sourcesContent":["x","y"]}'
    )
    assert [f.path for f in r2.files] == ["c.js"]
    # a non-list `sources` is not a usable map
    assert (
        recover_from_map('{"version":3,"sources":"a.js","sourcesContent":["x"]}').files
        == []
    )


def test_pnpm_peer_dep_suffix_is_trimmed():
    files = [
        RecoveredFile(
            "node_modules/.pnpm/axios@1.6.2_react@18.3.1/node_modules/axios/i.js",
            "x",
            "x",
        ),
        RecoveredFile(
            "node_modules/.pnpm/@babel+core@7.20.0(react@18.0.0)/node_modules/@babel/core/i.js",
            "y",
            "y",
        ),
    ]
    d = dict(node_modules_packages(files))
    assert d["axios"] == "1.6.2"  # _react@18.3.1 peer suffix trimmed
    assert d["@babel/core"] == "7.20.0"  # (react@...) peer suffix trimmed


def test_pnpm_transitive_dep_not_invented():
    # .pnpm/debug@4.3.4/node_modules/ms/... -> only `ms` is recovered here; the
    # outer `debug@4.3.4` version must NOT be invented for a package not present.
    files = [
        RecoveredFile(
            "node_modules/.pnpm/debug@4.3.4/node_modules/ms/index.js", "x", "x"
        )
    ]
    assert dict(node_modules_packages(files)) == {"ms": None}


def _big_inline_js(n=40):
    """A bundle whose only map is an inline data URI with a >2 kB base64 payload."""
    obj = {
        "version": 3,
        "sources": [f"webpack:///src/mod{i}.js" for i in range(n)],
        "sourcesContent": [
            f"export const v{i} = {i}; // " + "x" * 50 for i in range(n)
        ],
    }
    payload = base64.b64encode(json.dumps(obj).encode()).decode()
    assert len(payload) > 2000  # must defeat detect_source_maps' 2 kB tail window
    return "var x=1;\n//# sourceMappingURL=data:application/json;base64," + payload, n


def test_large_inline_map_recovered_despite_detection_window(tmp_store):
    body, n = _big_inline_js(40)
    art = tmp_store.put_artifact(
        body.encode(), kind="request", content_type="application/javascript"
    )
    rec = {
        "url": "http://t.example/app.js",
        "resource_type": "script",
        "status": 200,
        "response_headers": {"content-type": "application/javascript"},
        "body_artifact_id": art.artifact_id,
    }
    net = tmp_store.put_artifact(
        json.dumps([rec]).encode(), kind="network", content_type="application/json"
    )
    out = analyze_bundles(_ctx(tmp_store, _run_with([art, net])))
    # detect_source_maps misses the marker (pushed past the tail), but recovery
    # runs unconditionally and forces present=True.
    assert out.run_fields["source_maps_present"] is True
    md = next(f for f in out.findings if f.signal == "arch.source_maps").metric_detail
    assert md["recovered_files"] == n


def test_non_string_sources_content_does_not_crash_analyzer(tmp_store):
    obj = {
        "version": 3,
        "sources": ["webpack:///a.js", "webpack:///b.js"],
        "sourcesContent": [
            42,
            "console.log('b')",
        ],  # 42 (truthy non-str) must not crash
    }
    smap = tmp_store.put_artifact(
        json.dumps(obj).encode(), kind="source_map", content_type="application/json"
    )
    js_art, rec = _js_network(
        tmp_store, url="http://t/app.js", body="var x=1;", marker=False
    )
    net = tmp_store.put_artifact(
        json.dumps([rec]).encode(), kind="network", content_type="application/json"
    )
    out = analyze_bundles(_ctx(tmp_store, _run_with([js_art, net, smap])))
    assert out.run_fields["source_maps_present"] is True  # not left None by a crash
    md = next(f for f in out.findings if f.signal == "arch.source_maps").metric_detail
    assert md["recovered_files"] == 1  # only b.js; the int entry is skipped, no crash


def test_is_recovered_dependency_predicate():
    from ov.analysis.arch.sourcemaps import is_recovered_dependency
    from ov.base import TechFinding

    dep = TechFinding(
        name="lodash", categories=["dependency"], provenance=["sourcemap"]
    )
    bundler = TechFinding(
        name="webpack", categories=["dependency", "bundler"], provenance=["sourcemap"]
    )
    fw = TechFinding(
        name="React", categories=["ui-framework"], provenance=["window.react"]
    )
    assert is_recovered_dependency(dep) is True
    assert is_recovered_dependency(bundler) is False  # also a bundler -> stays in stack
    assert is_recovered_dependency(fw) is False
