"""Playwright facade -- the baseline driver (§9, D1).

This hides Playwright behind a clean lifecycle so no caller (or skill, or future
agent) ever touches a raw Playwright object. It is treated as a *facade over a
CDP escape hatch, not a wall*: :meth:`BrowserSession.cdp` lazily attaches a
:class:`~ov.capture.cdp.CdpSession` for the ~20% the high-level API can't reach.

The sync Playwright API is used deliberately -- capture is a synchronous,
step-by-step orchestration and the sync API keeps the code legible. HAR is
recorded to a temp ``.har.zip`` with embedded bodies and read back after the
context closes (HAR only flushes on ``context.close()``); structured network
records come from event accumulation in the network probe, not from the HAR.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from ..config import OvConfig


class BrowserNotAvailable(RuntimeError):
    """Raised when Playwright or its browsers are not usable.

    Carries the install hint so the message is actionable, per the project's
    informative-errors principle.
    """


class BrowserSession:
    """Owns a Playwright browser/context/page for one capture run.

    Lifecycle is explicit (:meth:`start` / :meth:`close`) so the orchestrator can
    flush in-memory probe state *before* closing the context (which flushes HAR),
    then ingest the HAR. It is also a context manager for simple call sites.
    """

    def __init__(self, config: OvConfig, *, record_har: bool = True):
        self.config = config
        self.record_har = record_har
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._cdp = None
        self._har_path: Path | None = None
        self._har_bytes: bytes | None = None

    # --- lifecycle --------------------------------------------------------- #

    def start(self) -> "BrowserSession":
        """Launch the browser and open a context + page. Returns self."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:  # pragma: no cover - import guard
            raise BrowserNotAvailable(
                "playwright is not installed; `pip install playwright` then "
                "`playwright install chromium`"
            ) from e

        self._pw = sync_playwright().start()
        browser_type = getattr(self._pw, self.config.browser, self._pw.chromium)
        try:
            self._browser = browser_type.launch(headless=not self.config.headed)
        except Exception as e:  # noqa: BLE001 - surface a clean, actionable error
            self.stop()
            raise BrowserNotAvailable(
                f"could not launch {self.config.browser}: {e}. "
                "Run `playwright install chromium`."
            ) from e

        context_kwargs: dict[str, Any] = {
            "service_workers": "block",  # so page.route/event capture sees SW traffic
        }
        if self.record_har:
            self._har_path = Path(tempfile.mkstemp(suffix=".har.zip")[1])
            context_kwargs["record_har_path"] = str(self._har_path)
            context_kwargs["record_har_content"] = "embed"

        self._context = self._browser.new_context(**context_kwargs)
        self._context.set_default_navigation_timeout(self.config.nav_timeout_ms)
        self._context.set_default_timeout(self.config.nav_timeout_ms)
        self._page = self._context.new_page()
        return self

    def close(self) -> None:
        """Close the context (flushing HAR), read the HAR, then tear down."""
        if self._context is not None:
            try:
                self._context.close()
            finally:
                self._context = None
            if self._har_path is not None and self._har_path.exists():
                try:
                    self._har_bytes = self._har_path.read_bytes()
                except OSError:
                    self._har_bytes = None
                finally:
                    try:
                        self._har_path.unlink()
                    except OSError:
                        pass
        self.stop()

    def stop(self) -> None:
        """Hard teardown of browser + playwright (idempotent)."""
        self._cdp = None
        for closer in (
            lambda: self._browser and self._browser.close(),
            lambda: self._pw and self._pw.stop(),
        ):
            try:
                closer()
            except Exception:  # noqa: BLE001 - best-effort teardown
                pass
        self._browser = None
        self._pw = None

    def __enter__(self) -> "BrowserSession":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.close()

    # --- accessors --------------------------------------------------------- #

    @property
    def page(self):
        """The active Playwright ``Page`` (raises if not started)."""
        if self._page is None:
            raise BrowserNotAvailable("BrowserSession not started; call start() first")
        return self._page

    @property
    def context(self):
        """The active Playwright ``BrowserContext``."""
        if self._context is None:
            raise BrowserNotAvailable("BrowserSession context not available")
        return self._context

    def cdp(self):
        """Lazily attach and return a :class:`~ov.capture.cdp.CdpSession` (Chromium).

        Returns ``None`` on non-Chromium browsers, where CDP is unavailable.
        """
        if self.config.browser != "chromium":
            return None
        if self._cdp is None:
            from .cdp import CdpSession

            self._cdp = CdpSession(self.context.new_cdp_session(self.page))
        return self._cdp

    @property
    def har_bytes(self) -> bytes | None:
        """The recorded HAR archive bytes (available only after :meth:`close`)."""
        return self._har_bytes
