"""``ov.observe(read_only=True)``: no non-GET request leaves the browser (#22)."""

import http.server
import json
import threading

import pytest

from _browser import requires_browser

pytestmark = requires_browser

PAGE = b"""<html><body><h1>hi</h1>
<script>fetch('/counter', {method: 'POST', body: 'x'}).catch(() => {});</script>
</body></html>"""


@pytest.fixture
def posting_site():
    posts: list[str] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(PAGE)

        def do_POST(self):
            posts.append(self.path)
            self.send_response(204)
            self.end_headers()

        def log_message(self, *a):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/", posts
    finally:
        httpd.shutdown()


def test_read_only_blocks_posts_and_lists_them(posting_site, tmp_store):
    import ov

    url, posts = posting_site
    run = ov.observe(url, store=tmp_store, read_only=True)
    assert posts == []
    arts = [a for a in run.artifacts if a.kind == "blocked_requests"]
    assert len(arts) == 1
    blocked = json.loads(tmp_store.artifact_bytes(arts[0]))
    assert [b["method"] for b in blocked] == ["POST"]
    assert blocked[0]["url"].endswith("/counter")


def test_default_is_unchanged(posting_site, tmp_store):
    import ov

    url, posts = posting_site
    run = ov.observe(url, store=tmp_store)
    assert posts == ["/counter"]
    assert not [a for a in run.artifacts if a.kind == "blocked_requests"]
