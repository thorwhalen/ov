"""Internal helpers: content-addressing, hashing, redaction, and requirements.

Nothing here knows about Playwright or analysis specifics -- these are the
small, reusable primitives the rest of the package leans on. The most
user-facing item is :func:`check_requirements`, which detects missing system
dependencies (Playwright browsers, Node, the sidecar, optional CLIs) and prints
the exact commands to install them, per the spec's ``check_requirements``
mandate (§9).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# --------------------------------------------------------------------------- #
# Hashing / content-addressing
# --------------------------------------------------------------------------- #


def content_hash(data: bytes | str, *, length: int = 16) -> str:
    """Return a short, stable SHA-256 hex digest for content-addressing.

    >>> content_hash(b"hello")
    '2cf24dba5fb0a30e'
    >>> content_hash("hello") == content_hash(b"hello")
    True
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:length]


def stable_hash(obj: Any, *, length: int = 16) -> str:
    """Hash an arbitrary JSON-able object deterministically (sorted keys).

    Used for ``obs_hash`` and ``args_hash`` so progress detection is reproducible.

    >>> stable_hash({"b": 1, "a": 2}) == stable_hash({"a": 2, "b": 1})
    True
    """
    try:
        payload = json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False)
    except TypeError:
        payload = repr(obj)
    return content_hash(payload, length=length)


# --------------------------------------------------------------------------- #
# Redaction (privacy default; see OvConfig.redact_values)
# --------------------------------------------------------------------------- #

_REDACTED = "<redacted>"


def redact_value(value: Any) -> str:
    """Replace a value with a length-tagged placeholder (keeps shape, drops content).

    >>> redact_value("super-secret-token")
    '<redacted:18>'
    >>> redact_value(None)
    '<redacted>'
    """
    if value is None:
        return _REDACTED
    try:
        n = len(value) if isinstance(value, (str, bytes, list, dict)) else len(str(value))
    except TypeError:
        n = 0
    return f"<redacted:{n}>"


def redact_mapping(mapping: dict[str, Any], *, redact: bool = True) -> dict[str, Any]:
    """Return a copy of ``mapping`` with values redacted when ``redact`` is true."""
    if not redact:
        return dict(mapping)
    return {k: redact_value(v) for k, v in mapping.items()}


# --------------------------------------------------------------------------- #
# Locating the Node sidecar (dev/source-tree; see §6.1)
# --------------------------------------------------------------------------- #


def sidecar_dir() -> Path:
    """Return the path to the Node sidecar directory (``OV_SIDECAR_DIR`` override).

    Defaults to ``<repo_root>/sidecar`` (sibling of the ``ov`` package). Packaging
    the sidecar for installed use is a later concern; for now it lives in the
    source tree.
    """
    override = os.environ.get("OV_SIDECAR_DIR")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parent.parent / "sidecar"


# --------------------------------------------------------------------------- #
# check_requirements
# --------------------------------------------------------------------------- #


@dataclass
class Requirement:
    """One checked system dependency."""

    name: str
    present: bool
    detail: str = ""
    install_hint: str = ""
    optional: bool = True


@dataclass
class RequirementReport:
    """The result of :func:`check_requirements` -- iterable, with a tidy summary."""

    requirements: list[Requirement] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when every *non-optional* requirement is present."""
        return all(r.present for r in self.requirements if not r.optional)

    @property
    def missing(self) -> list[Requirement]:
        """Requirements that are absent (optional or not)."""
        return [r for r in self.requirements if not r.present]

    def __iter__(self):
        return iter(self.requirements)

    def render(self) -> str:
        """Human-readable multi-line summary with install hints for what's missing."""
        lines = []
        for r in self.requirements:
            mark = "OK " if r.present else ("-- " if r.optional else "!! ")
            tag = "" if not r.optional else " (optional)"
            lines.append(f"  [{mark}] {r.name}{tag}: {r.detail}")
            if not r.present and r.install_hint:
                lines.append(f"        install: {r.install_hint}")
        status = "all required dependencies present" if self.ok else "missing REQUIRED dependencies"
        return f"ov requirements -- {status}\n" + "\n".join(lines)


def _which_version(cmd: str, version_args: Iterable[str] = ("--version",)) -> str | None:
    """Return the trimmed version string for ``cmd`` if runnable, else ``None``."""
    if shutil.which(cmd) is None:
        return None
    try:
        out = subprocess.run(
            [cmd, *version_args],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr) else ""
    except (OSError, subprocess.SubprocessError):
        return None


def _playwright_browser_present(browser: str = "chromium") -> tuple[bool, str]:
    """Heuristically detect an installed Playwright browser without launching it."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False, "playwright python package not importable"
    # Browsers cache: PLAYWRIGHT_BROWSERS_PATH, else per-OS default.
    cache = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    candidates = []
    if cache:
        candidates.append(Path(cache))
    home = Path.home()
    candidates += [
        home / "Library" / "Caches" / "ms-playwright",  # macOS
        home / ".cache" / "ms-playwright",  # Linux
        home / "AppData" / "Local" / "ms-playwright",  # Windows
    ]
    for c in candidates:
        if c.exists() and any(p.name.startswith(browser) for p in c.iterdir()):
            return True, f"found under {c}"
    return False, "no installed browser found in the playwright cache"


def check_requirements(
    *,
    components: Iterable[str] | None = None,
    verbose: bool = True,
) -> RequirementReport:
    """Detect missing system dependencies and print exact install commands.

    ``components`` filters which groups to check (``"browser"``, ``"node"``,
    ``"sidecar"``, ``"clis"``); ``None`` checks all. The deterministic analysis
    core needs none of these -- they gate *capture* and the *arch sidecar*, so
    every requirement here is reported as optional unless capture is requested.

    >>> rep = check_requirements(components=["clis"], verbose=False)
    >>> isinstance(rep, RequirementReport)
    True
    """
    want = set(components) if components is not None else {"browser", "node", "sidecar", "clis"}
    reqs: list[Requirement] = []

    if "browser" in want:
        present, detail = _playwright_browser_present()
        reqs.append(
            Requirement(
                "playwright-chromium",
                present,
                detail,
                install_hint="playwright install chromium",
                optional=False,  # required to capture
            )
        )

    if "node" in want:
        ver = _which_version("node")
        reqs.append(
            Requirement(
                "node",
                ver is not None,
                ver or "not found on PATH",
                install_hint="install Node.js >= 18 (https://nodejs.org)",
            )
        )

    if "sidecar" in want:
        sd = sidecar_dir()
        installed = (sd / "node_modules").exists()
        reqs.append(
            Requirement(
                "ov-node-sidecar",
                installed,
                f"node_modules present at {sd}" if installed else f"not installed at {sd}",
                install_hint=f"cd {sd} && npm install",
            )
        )

    if "clis" in want:
        for cli, hint in (
            ("retire", "npm install -g retire"),
            ("wappalyzer", "pipx install wappalyzer  # GPL-3.0, optional"),
        ):
            ver = _which_version(cli)
            reqs.append(
                Requirement(cli, ver is not None, ver or "not found on PATH", install_hint=hint)
            )

    report = RequirementReport(reqs)
    if verbose:
        print(report.render())
    return report
