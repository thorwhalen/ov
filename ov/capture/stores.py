"""The capture store -- a ``MutableMapping`` Mall over a run directory (§3.4).

A single root holds many runs. Artifacts are **content-addressed** (keyed by a
hash of their bytes) so identical assets dedupe across runs -- which is exactly
what makes own-target diffing cheap. ``dol`` provides the filesystem-backed
mappings; this module is a thin facade that adds the ``ov`` semantics (typed
runs, artifact put/get, report + analysis storage) on top.

Layout under ``root``::

    runs/<run_id>.json          # CaptureRun, JSON
    artifacts/<hash>.<ext>      # content-addressed bytes (shared across runs)
    reports/<run_id>/<name>     # rendered Markdown
    analyses/<analysis_id>.json # analysis JSON

The Mall exposes four ``MutableMapping`` attributes (``runs``, ``artifacts``,
``reports``, ``analyses``) for callers who want raw access, plus convenience
methods that speak the SSOT models.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from dol import Files, JsonFiles, TextFiles, mk_dirs_if_missing

from ..base import Artifact, CaptureRun
from ..config import default_store_root
from ..util import content_hash

# Map a small set of content types / kinds to file extensions for legibility.
_EXT_BY_CONTENT_TYPE = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "application/json": "json",
    "text/html": "html",
    "text/css": "css",
    "application/javascript": "js",
    "text/javascript": "js",
    "application/json+har": "har",
    "text/plain": "txt",
}
_EXT_BY_KIND = {
    "screenshot": "png",
    "dom": "html",
    "ax_tree": "json",
    "har": "har",
    "request": "json",
    "console": "json",
    "sse": "json",
    "source_map": "map",
}


def _ext_for(kind: str, content_type: str | None) -> str:
    if content_type:
        base = content_type.split(";")[0].strip().lower()
        if base in _EXT_BY_CONTENT_TYPE:
            return _EXT_BY_CONTENT_TYPE[base]
    return _EXT_BY_KIND.get(kind, "bin")


class CaptureStore:
    """A store of stores for one or many capture runs (XDG-aligned root by default).

    >>> import tempfile
    >>> store = CaptureStore(tempfile.mkdtemp())
    >>> art = store.put_artifact(b"<html>hi</html>", kind="dom")
    >>> store.artifact_bytes(art) == b"<html>hi</html>"
    True
    >>> from ov.base import CaptureRun
    >>> run = CaptureRun(target_url="http://x", artifacts=[art])
    >>> store.save_run(run)
    >>> store.load_run(run.run_id).target_url
    'http://x'
    """

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root is not None else default_store_root()
        for sub in ("runs", "artifacts", "reports", "analyses"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        self.runs = mk_dirs_if_missing(JsonFiles(str(self.root / "runs")))
        self.artifacts = mk_dirs_if_missing(Files(str(self.root / "artifacts")))
        self.reports = mk_dirs_if_missing(TextFiles(str(self.root / "reports")))
        self.analyses = mk_dirs_if_missing(JsonFiles(str(self.root / "analyses")))

    # --- artifacts (content-addressed) ------------------------------------- #

    def put_artifact(
        self,
        data: bytes,
        *,
        kind: str,
        step_id: str | None = None,
        content_type: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> Artifact:
        """Store ``data`` content-addressed and return its :class:`Artifact` record.

        Identical bytes produce the same ``uri``, so re-storing is a no-op write
        and cross-run assets dedupe automatically.
        """
        h = content_hash(data, length=24)
        ext = _ext_for(kind, content_type)
        uri = f"{h}.{ext}"
        if uri not in self.artifacts:  # idempotent: skip rewriting identical bytes
            self.artifacts[uri] = data
        return Artifact(
            kind=kind,
            step_id=step_id,
            uri=uri,
            content_hash=h,
            content_type=content_type,
            size=len(data),
            meta=meta or {},
        )

    def artifact_bytes(self, artifact_or_uri: Artifact | str) -> bytes:
        """Return the raw bytes for an :class:`Artifact` (or a raw ``uri`` string)."""
        uri = artifact_or_uri.uri if isinstance(artifact_or_uri, Artifact) else artifact_or_uri
        return self.artifacts[uri]

    # --- runs -------------------------------------------------------------- #

    def save_run(self, run: CaptureRun) -> None:
        """Persist a :class:`CaptureRun` as JSON under its ``run_id``."""
        self.runs[f"{run.run_id}.json"] = run.model_dump(mode="json")

    def load_run(self, run_id: str) -> CaptureRun:
        """Load a :class:`CaptureRun` by id (accepts bare id or ``<id>.json``)."""
        key = run_id if run_id.endswith(".json") else f"{run_id}.json"
        return CaptureRun.model_validate(self.runs[key])

    def run_ids(self) -> list[str]:
        """List stored run ids (without the ``.json`` suffix)."""
        return sorted(k[:-5] for k in self.runs if k.endswith(".json"))

    # --- reports ----------------------------------------------------------- #

    def save_report(self, run_id: str, name: str, markdown: str) -> str:
        """Store a rendered Markdown report; return its store key."""
        key = f"{run_id}/{name}"
        self.reports[key] = markdown
        return key

    def report_names(self, run_id: str) -> list[str]:
        """List report keys belonging to ``run_id`` (separator-normalized).

        ``dol`` returns directory-listing keys with the OS separator, which is a
        backslash on Windows; we always speak the logical ``/`` separator (and
        store/read with it), so normalize before the prefix match.
        """
        prefix = f"{run_id}/"
        return sorted(
            norm for k in self.reports if (norm := k.replace("\\", "/")).startswith(prefix)
        )

    # --- analyses ---------------------------------------------------------- #

    def save_analysis(self, analysis_id: str, obj: dict[str, Any]) -> None:
        """Persist an analysis JSON blob by id."""
        self.analyses[f"{analysis_id}.json"] = obj

    def load_analysis(self, analysis_id: str) -> dict[str, Any]:
        """Load an analysis JSON blob by id."""
        key = analysis_id if analysis_id.endswith(".json") else f"{analysis_id}.json"
        return self.analyses[key]

    def __repr__(self) -> str:
        return f"CaptureStore(root={str(self.root)!r}, runs={len(self.run_ids())})"


def resolve_store(store: CaptureStore | str | Path | None) -> CaptureStore:
    """Coerce ``store`` (a CaptureStore, a path, or ``None``) into a CaptureStore.

    The dependency-injection seam: callers pass whatever they have and get a
    usable store, defaulting to the XDG root.
    """
    if isinstance(store, CaptureStore):
        return store
    return CaptureStore(store)
