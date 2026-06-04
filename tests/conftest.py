"""Shared pytest fixtures: a hermetic local test app + a temp store.

The local site is served in-process so capture tests are offline and
reproducible (no network). Browser-dependent tests gate on ``browser_available``
so the deterministic core stays fully testable without Playwright browsers.
"""

import functools
import http.server
import threading
from pathlib import Path

import pytest

SITE_DIR = Path(__file__).parent / "fixtures" / "site"


@pytest.fixture(scope="session")
def local_site():
    """Serve ``tests/fixtures/site`` on a random localhost port; yield the base URL."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE_DIR))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()


@pytest.fixture
def tmp_store(tmp_path):
    """A fresh :class:`CaptureStore` rooted in a temp dir."""
    from ov.capture.stores import CaptureStore

    return CaptureStore(tmp_path / "store")
