"""Pure source-map recovery: original file tree + ``node_modules`` versions (D2).

Source maps are the decisive, *bimodal* reconstruction lever. When a deployed
bundle ships a Source Map v3 document (``//# sourceMappingURL=...`` or a sibling
``.js.map``), the original file tree and source text are recoverable by a plain
JSON parse: the ``sourcesContent`` array holds the verbatim sources, indexed in
parallel with ``sources``. No VLQ ``mappings`` decoding and **no Node** are needed
for source recovery -- that machinery only matters for stack-trace *position*
mapping. Keeping recovery pure-Python keeps the deterministic core testable,
cheap, and ungated by an optional sidecar (the spec's "source-map sidecar depth"
is satisfied here in-process; the sidecar remains for the no-maps webcrack path).

This module is model-free and side-effect-free: it parses bytes already captured
into the store and returns plain, transient data. Persisting recovered files as
artifacts and emitting findings/tech is the analyzer's job
(:mod:`ov.analysis.arch.bundles`).

Security: ``sources`` paths come from an untrusted producer, so every path is
sanitized (scheme prefixes stripped, traversal contained) before it is used as a
relative path -- escaping entries are skipped and counted, never resolved above a
root. The path-sanitization approach is adapted from rarecoil's MIT-licensed
``unwebpack-sourcemap`` ``PathSanitiser``.
"""

from __future__ import annotations

import base64
import json
import posixpath
import re
from dataclasses import dataclass, field
from urllib.parse import unquote

# Any ``scheme://`` prefix bundlers stamp onto ``sources`` (webpack://, file://,
# webpack-internal://, vite://, ...). Two-or-more slashes so a Windows ``C:/`` --
# which has a single slash -- is never mistaken for a scheme and stripped.
_SOURCE_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:/{2,}")
# A Windows absolute / UNC remnant we refuse to treat as a relative path.
_WINDOWS_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]|^\\\\")
# pnpm encodes the version directly: node_modules/.pnpm/lodash@4.17.21/...  and
# scoped as node_modules/.pnpm/@scope+pkg@1.2.3/...
_PNPM_VERSION_RE = re.compile(r"/\.pnpm/((?:@[^/]+\+)?[^/@]+)@([0-9][^/]*)/")
# sourceMappingURL footer markers (mirrors ov.analysis.arch.bundles._MAP_MARKERS).
_MAP_MARKERS = ("//# sourceMappingURL=", "//@ sourceMappingURL=")
# node_modules sub-dirs that are not packages themselves.
_NON_PACKAGE_DIRS = frozenset({".pnpm", ".bin", ".cache", ".vite", ".store"})


@dataclass(frozen=True)
class RecoveredFile:
    """One original file recovered from a source map (transient; never serialized)."""

    path: str  # sanitized, root-relative POSIX path
    content: str  # original source text (from ``sourcesContent``)
    raw_source: str  # the original, unsanitized ``sources[i]`` entry


@dataclass
class MapRecovery:
    """Result of recovering one source map (transient internal data, not SSOT)."""

    files: list[RecoveredFile] = field(default_factory=list)
    sources_total: int = 0
    had_sources_content: bool = False
    skipped_unsafe: int = 0

    @property
    def recovered_count(self) -> int:
        """Number of files with content actually recovered."""
        return len(self.files)


def parse_source_map(map_text: str) -> dict | None:
    """Parse a ``.map`` body into a Source Map v3 dict, or ``None`` if it is not one.

    >>> parse_source_map('{"version":3,"sources":["a.js"]}')["version"]
    3
    >>> parse_source_map("not json") is None
    True
    >>> parse_source_map('{"version":3}') is None
    True
    """
    try:
        obj = json.loads(map_text)
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict) or "sources" not in obj:
        return None
    return obj


def sanitize_source_path(raw: str, *, source_root: str = "") -> str | None:
    """Turn an untrusted ``sources`` entry into a safe root-relative path (or ``None``).

    Applies ``sourceRoot``, drops query/fragment and any ``scheme://`` prefix, then
    *contains* traversal: a path that would escape the virtual root (a leading
    ``..`` after normalization) or is absolute is rejected.

    >>> sanitize_source_path("webpack:///src/App.tsx")
    'src/App.tsx'
    >>> sanitize_source_path("../../etc/passwd") is None
    True
    >>> sanitize_source_path("webpack:///./a/../b.js")
    'b.js'
    >>> sanitize_source_path("a.js", source_root="webpack:///src/")
    'src/a.js'
    """
    if not raw or not isinstance(raw, str):
        return None
    candidate = raw
    if source_root:
        sep = "" if source_root.endswith("/") else "/"
        candidate = f"{source_root}{sep}{raw}"
    candidate = candidate.split("?", 1)[0].split("#", 1)[0]
    # Treat Windows separators as path separators so backslash-`..` traversal is
    # contained (posixpath would otherwise see one opaque segment), and reject any
    # NUL/control char (a truncation-injection primitive for downstream consumers).
    candidate = candidate.replace("\\", "/")
    if any(ord(c) < 0x20 for c in candidate):
        return None
    candidate = _SOURCE_SCHEME_RE.sub("", candidate)
    if _WINDOWS_ABS_RE.match(candidate):
        return None
    candidate = posixpath.normpath(candidate.lstrip("/"))
    if not candidate or candidate == "." or posixpath.isabs(candidate):
        return None
    if candidate == ".." or candidate.startswith("../"):
        return None
    return candidate


def recover_from_map(map_text: str) -> MapRecovery:
    """Recover original files from one source-map body (pure; no I/O, no Node).

    Only ``sources`` with non-empty ``sourcesContent`` are recoverable; entries
    whose path escapes the root are skipped and counted in ``skipped_unsafe``.

    >>> m = ('{"version":3,"sources":["webpack:///src/a.js","webpack:///../evil"],'
    ...      '"sourcesContent":["console.log(1)","x"]}')
    >>> r = recover_from_map(m)
    >>> [f.path for f in r.files], r.skipped_unsafe, r.had_sources_content
    (['src/a.js'], 1, True)
    """
    rec = MapRecovery()
    obj = parse_source_map(map_text)
    if obj is None:
        return rec
    sources = obj.get("sources")
    if not isinstance(sources, list):  # a non-list `sources` is not a usable map
        return rec
    contents = obj.get("sourcesContent")
    contents = contents if isinstance(contents, list) else []
    source_root = obj.get("sourceRoot")
    source_root = source_root if isinstance(source_root, str) else ""
    rec.sources_total = len(sources)
    rec.had_sources_content = any(isinstance(c, str) and c for c in contents)
    for i, raw in enumerate(sources):
        if not isinstance(raw, str):
            continue  # malformed source entry -> never fabricate a file from it
        content = contents[i] if i < len(contents) else None
        if not isinstance(content, str) or not content:
            continue  # null/empty/non-string sourcesContent -> nothing to recover
        safe = sanitize_source_path(raw, source_root=source_root)
        if safe is None:
            rec.skipped_unsafe += 1
            continue
        rec.files.append(RecoveredFile(path=safe, content=content, raw_source=raw))
    return rec


def _package_of(path: str) -> str | None:
    """Return the ``node_modules`` package owning ``path`` (scoped-aware) or ``None``.

    Uses the *last* ``node_modules/`` segment so pnpm's nested
    ``.pnpm/<pkg>@<ver>/node_modules/<pkg>/...`` resolves to the real package.

    >>> _package_of("node_modules/lodash/lodash.js")
    'lodash'
    >>> _package_of("node_modules/@scope/ui/index.js")
    '@scope/ui'
    >>> _package_of("src/app.js") is None
    True
    """
    marker = "node_modules/"
    idx = path.rfind(marker)
    if idx == -1:
        return None
    parts = [p for p in path[idx + len(marker) :].split("/") if p]
    if not parts or parts[0] in _NON_PACKAGE_DIRS:
        return None
    if parts[0].startswith("@"):
        return f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else None
    return parts[0]


def node_modules_packages(files: list[RecoveredFile]) -> list[tuple[str, str | None]]:
    """Infer sorted ``(package, version|None)`` pairs from recovered ``node_modules`` paths.

    Version sources, in precedence order: a pnpm ``.pnpm/<pkg>@<ver>/`` path
    segment, then a recovered ``package.json`` ``version`` field. Otherwise the
    version is unknown (``None``). Scoped packages (``@scope/name``) are handled.

    >>> fs = [
    ...   RecoveredFile("node_modules/lodash/lodash.js", "x", "x"),
    ...   RecoveredFile("node_modules/@scope/ui/index.js", "y", "y"),
    ...   RecoveredFile("node_modules/.pnpm/axios@1.6.2/node_modules/axios/i.js", "z", "z"),
    ... ]
    >>> d = dict(node_modules_packages(fs))
    >>> d["lodash"] is None, d["axios"], "@scope/ui" in d
    (True, '1.6.2', True)
    """
    versions: dict[str, str | None] = {}
    from_pkgjson: dict[str, str] = {}
    for f in files:
        pkg = _package_of(f.path)
        if pkg is None:
            continue
        versions.setdefault(pkg, None)
        m = _PNPM_VERSION_RE.search("/" + f.path)
        # Attribute the pnpm-encoded version ONLY to the package whose virtual-store
        # dir it is -- a nested transitive path (.pnpm/debug@4/node_modules/ms/...)
        # resolves to `ms`, and `debug`'s version must NOT be invented from it.
        if m and m.group(1).replace("+", "/") == pkg:
            versions[pkg] = m.group(2).split("_", 1)[0].split("(", 1)[0]
        if f.path.endswith("package.json"):
            try:
                v = json.loads(f.content).get("version")
            except (ValueError, TypeError, AttributeError):
                v = None
            if isinstance(v, str):
                from_pkgjson[pkg] = v
    for pkg, v in from_pkgjson.items():
        if not versions.get(pkg):
            versions[pkg] = v
    return sorted(versions.items())


def extract_inline_map(js_text: str) -> str | None:
    """Return the decoded JSON of an inline ``sourceMappingURL=data:...`` map, else ``None``.

    Handles ``;base64,`` and URL-encoded data URIs. External (``.map`` URL) markers
    return ``None`` -- those are fetched by the capture probe, not decoded here.

    >>> import base64, json
    >>> payload = base64.b64encode(json.dumps({"version": 3, "sources": []}).encode()).decode()
    >>> js = "a=1\\n//# sourceMappingURL=data:application/json;base64," + payload
    >>> json.loads(extract_inline_map(js))["version"]
    3
    >>> extract_inline_map("a=1\\n//# sourceMappingURL=app.js.map") is None
    True
    """
    for marker in _MAP_MARKERS:
        idx = js_text.rfind(marker)
        if idx == -1:
            continue
        rest = js_text[idx + len(marker) :].strip()
        url = rest.splitlines()[0].strip() if rest else ""
        if url.startswith("data:"):
            return _decode_data_uri(url)
    return None


def _decode_data_uri(uri: str) -> str | None:
    """Decode a ``data:[<mediatype>][;base64],<data>`` URI to text (``None`` on failure)."""
    try:
        header, _, data = uri.partition(",")
        if not data:
            return None
        if ";base64" in header.lower():
            return base64.b64decode(data).decode("utf-8", errors="replace")
        return unquote(data)
    except (ValueError, TypeError):
        return None


def is_recovered_dependency(tech) -> bool:
    """True for a ``node_modules`` package recovered from a source map (SBOM, not stack).

    Single source of truth for separating the recovered-dependency SBOM from
    framework-level technologies wherever ``run.fingerprint`` is summarized (the
    overview header, the architecture stack table, the synopsis, review-mode
    tech-diff). A tech that is ALSO a framework/bundler -- e.g. ``webpack``
    detected both as a recovered dependency and by signature -- carries an extra
    category (so the set is not exactly ``{"dependency"}``) and is NOT treated as a
    pure recovered dependency, keeping it in the headline stack.
    """
    return "sourcemap" in tech.provenance and set(tech.categories) == {"dependency"}
