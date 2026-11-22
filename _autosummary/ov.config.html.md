# ov.config

Configuration – the single source of truth for `ov`’s defaults.

Everything is a keyword-only field on [`OvConfig`](#ov.config.OvConfig) with a smart default, so
`ov.observe(url)` works with zero config while every knob stays reachable.
Environment variables (`OV_*`) override the defaults; an explicit constructor
argument overrides the environment.

This module also encodes the **default-safety checklist** from the spec’s
boundary note (§6): redaction is on, secret/PII capture is off, a polite rate is
applied, `robots.txt` intent is respected by default, and a *foreign* target
requires an explicit `authorized=True` acknowledgement.

### Functions

| [`default_store_root`](#ov.config.default_store_root)()   | Return the XDG-aligned default root for `ov`'s capture stores.   |
|-------------------------------------------------------------------------|------------------------------------------------------------------|

### Classes

| [`OvConfig`](#ov.config.OvConfig)(\*[, store_root, headed, browser, ...])   | Resolved settings for a capture/analysis run (keyword-only, env-overridable).   |
|-----------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------|

### *class* ov.config.OvConfig(, store_root=default_store_root(), headed=False, browser='chromium', nav_timeout_ms=30000, default_probes=('navigation', 'network', 'dom', 'screenshot', 'console', 'fingerprint', 'assets', 'a11y'), max_body_bytes=2000000, console_text_cap=2000, ws_frame_cap=4096, capture_body_content_types=('application/json', 'application/javascript', 'text/javascript', 'text/html', 'text/css', 'text/event-stream', 'application/graphql', 'application/xml', 'text/plain'), max_steps=40, max_failures=6, wall_clock_s=300.0, no_progress_steps=3, redact_values=True, capture_secrets=False, respect_robots=True, polite_rate_s=0.3, authorized=False, use_proxy=False, stealth_profile=None)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Resolved settings for a capture/analysis run (keyword-only, env-overridable).

Construct with [`from_env()`](#ov.config.OvConfig.from_env) for the env-aware default, or pass explicit
fields to override. The instance is snapshotted into every
[`CaptureRun`](ov.base.html.md#ov.base.CaptureRun) (`settings_snapshot`) for provenance.

#### *classmethod* from_env(\*\*overrides)

Build a config from `OV_*` env vars, with explicit `overrides` winning.

```pycon
>>> isinstance(OvConfig.from_env().store_root, Path)
True
```

* **Return type:**
  [`OvConfig`](#ov.config.OvConfig)

#### snapshot()

Return a JSON-serializable snapshot for `CaptureRun.settings_snapshot`.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]

### ov.config.default_store_root()

Return the XDG-aligned default root for `ov`’s capture stores.

Honors `OV_STORE_ROOT` then `XDG_DATA_HOME`, falling back to
`~/.local/share/ov`.

* **Return type:**
  [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)
