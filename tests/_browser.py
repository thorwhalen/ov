"""Browser-availability gate shared by capture tests (importable, not a conftest)."""

import pytest


def _browser_ok() -> bool:
    """Return True if a Chromium browser can actually launch (not just be present)."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:  # noqa: BLE001
        return False


BROWSER_OK = _browser_ok()
requires_browser = pytest.mark.skipif(
    not BROWSER_OK, reason="Playwright Chromium not launchable"
)
