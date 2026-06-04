"""Configuration -- the single source of truth for ``ov``'s defaults.

Everything is a keyword-only field on :class:`OvConfig` with a smart default, so
``ov.observe(url)`` works with zero config while every knob stays reachable.
Environment variables (``OV_*``) override the defaults; an explicit constructor
argument overrides the environment.

This module also encodes the **default-safety checklist** from the spec's
boundary note (§6): redaction is on, secret/PII capture is off, a polite rate is
applied, ``robots.txt`` intent is respected by default, and a *foreign* target
requires an explicit ``authorized=True`` acknowledgement.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Store root (XDG-aligned)
# --------------------------------------------------------------------------- #


def default_store_root() -> Path:
    """Return the XDG-aligned default root for ``ov``'s capture stores.

    Honors ``OV_STORE_ROOT`` then ``XDG_DATA_HOME``, falling back to
    ``~/.local/share/ov``.
    """
    explicit = os.environ.get("OV_STORE_ROOT")
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return base / "ov"


# Default probes for the zero-config capture spine (Phase 1). Heavier probes
# (perf/storage/websocket/sse/sourcemaps) are opt-in via ``probes=...``.
DEFAULT_PROBES: tuple[str, ...] = (
    "navigation",
    "network",
    "dom",
    "screenshot",
    "console",
    "fingerprint",
    "assets",
    "a11y",  # computed text styles (for contrast) + optional axe-core
)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    try:
        return float(raw) if raw is not None else default
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


@dataclass(kw_only=True)
class OvConfig:
    """Resolved settings for a capture/analysis run (keyword-only, env-overridable).

    Construct with :meth:`from_env` for the env-aware default, or pass explicit
    fields to override. The instance is snapshotted into every
    :class:`~ov.base.CaptureRun` (``settings_snapshot``) for provenance.
    """

    # --- where things live ---
    store_root: Path = field(default_factory=default_store_root)

    # --- browser / driving ---
    headed: bool = False
    browser: str = "chromium"  # chromium gets the CDP tail; ff/webkit lose it
    nav_timeout_ms: int = 30_000
    default_probes: tuple[str, ...] = DEFAULT_PROBES

    # --- capture caps (keep stores bounded; avoid evicting on huge bodies) ---
    max_body_bytes: int = 2_000_000  # response bodies larger than this: metadata only
    console_text_cap: int = 2_000  # max chars kept per console/pageerror entry
    ws_frame_cap: int = 4_096  # max chars kept per captured WebSocket frame
    capture_body_content_types: tuple[str, ...] = (
        "application/json",
        "application/javascript",
        "text/javascript",
        "text/html",
        "text/css",
        "text/event-stream",
        "application/graphql",
        "application/xml",
        "text/plain",
    )

    # --- operate budgets (the package reports; the host enforces) ---
    max_steps: int = 40
    max_failures: int = 6
    wall_clock_s: float = 300.0
    no_progress_steps: int = 3  # consecutive flat steps before loop_suspected

    # --- safety / privacy defaults (the checklist) ---
    redact_values: bool = True  # storage/cookies/PII redacted before persisting
    capture_secrets: bool = False  # never persist raw secrets/PII by default
    respect_robots: bool = True  # honor robots.txt intent by default
    polite_rate_s: float = 0.3  # min delay between actions/requests
    authorized: bool = False  # MUST be True to study a foreign target

    # --- optional planes (off by default) ---
    use_proxy: bool = False  # mitmproxy plane (§6/§9) -- opt-in
    stealth_profile: str | None = None  # ToS-gated; None = off

    @classmethod
    def from_env(cls, **overrides: Any) -> "OvConfig":
        """Build a config from ``OV_*`` env vars, with explicit ``overrides`` winning.

        >>> isinstance(OvConfig.from_env().store_root, Path)
        True
        """
        env_values: dict[str, Any] = dict(
            headed=_env_bool("OV_HEADED", False),
            browser=os.environ.get("OV_BROWSER", "chromium"),
            nav_timeout_ms=_env_int("OV_NAV_TIMEOUT_MS", 30_000),
            max_body_bytes=_env_int("OV_MAX_BODY_BYTES", 2_000_000),
            max_steps=_env_int("OV_MAX_STEPS", 40),
            max_failures=_env_int("OV_MAX_FAILURES", 6),
            wall_clock_s=_env_float("OV_WALL_CLOCK_S", 300.0),
            redact_values=_env_bool("OV_REDACT_VALUES", True),
            capture_secrets=_env_bool("OV_CAPTURE_SECRETS", False),
            respect_robots=_env_bool("OV_RESPECT_ROBOTS", True),
            polite_rate_s=_env_float("OV_POLITE_RATE_S", 0.3),
            authorized=_env_bool("OV_AUTHORIZED", False),
            use_proxy=_env_bool("OV_USE_PROXY", False),
            stealth_profile=os.environ.get("OV_STEALTH_PROFILE") or None,
        )
        env_values.update(overrides)
        return cls(**env_values)

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot for ``CaptureRun.settings_snapshot``."""
        out: dict[str, Any] = {}
        for f in fields(self):
            val = getattr(self, f.name)
            if isinstance(val, Path):
                val = str(val)
            elif isinstance(val, tuple):
                val = list(val)
            out[f.name] = val
        return out
