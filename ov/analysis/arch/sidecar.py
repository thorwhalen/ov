"""Python facade over the Node reverse-engineering sidecar (§6.1, D2).

The mature JS-only tooling (``source-map``, bundle unpacking, AST literal
extraction) lives in a long-lived Node process spoken to over **newline-delimited
JSON-RPC 2.0 on stdio** -- the same transport MCP uses, sub-process-bound with no
network exposure of a process that ingests untrusted JS. The wire contract is
defined once here as typed methods; the sidecar functions are pure and stateless.

Everything degrades gracefully: if Node or the sidecar deps are absent,
:meth:`Sidecar.available` is ``False`` and callers skip recovery rather than fail.
"""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from typing import Any

from ...util import sidecar_dir


class SidecarUnavailable(RuntimeError):
    """Raised when the Node sidecar cannot be used (Node/deps missing)."""


class Sidecar:
    """A lazily-started Node sidecar process exposing pure JSON-RPC functions."""

    def __init__(self, *, node: str = "node", script: Path | None = None, timeout: float = 30.0):
        self.node = node
        self.script = Path(script) if script else sidecar_dir() / "server.js"
        self.timeout = timeout
        self._proc: subprocess.Popen | None = None
        self._next_id = 0

    def available(self) -> bool:
        """True when the script exists and its ``node_modules`` are installed."""
        import shutil

        return (
            shutil.which(self.node) is not None
            and self.script.exists()
            and (self.script.parent / "node_modules").exists()
        )

    def _start(self) -> None:
        if self._proc is not None:
            return
        if not self.available():
            raise SidecarUnavailable(
                f"Node sidecar not ready; run `cd {self.script.parent} && npm install`"
            )
        self._proc = subprocess.Popen(
            [self.node, str(self.script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

    def call(self, method: str, params: dict[str, Any]) -> Any:
        """Invoke a sidecar method; raise :class:`SidecarUnavailable` on transport error."""
        self._start()
        assert self._proc is not None and self._proc.stdin and self._proc.stdout
        self._next_id += 1
        request = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        try:
            self._proc.stdin.write(json.dumps(request) + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:  # pragma: no cover
            raise SidecarUnavailable(f"sidecar transport failed: {e}") from e
        line = self._readline_with_timeout()
        if not line:
            raise SidecarUnavailable("sidecar returned no response")
        resp = json.loads(line)
        if resp.get("error"):
            raise SidecarUnavailable(f"sidecar error: {resp['error']}")
        return resp.get("result")

    def _readline_with_timeout(self) -> str:
        """Read one response line, enforcing ``self.timeout`` (kills the process on hang).

        Uses a reader thread + join so the timeout works cross-platform (``select``
        on stdout pipes is POSIX-only). A hung sidecar must never hang the analysis.
        """
        assert self._proc is not None and self._proc.stdout is not None
        box: dict[str, Any] = {}

        def _read() -> None:
            try:
                box["line"] = self._proc.stdout.readline()
            except Exception as e:  # noqa: BLE001
                box["err"] = e

        t = threading.Thread(target=_read, daemon=True)
        t.start()
        t.join(self.timeout)
        if t.is_alive():
            self.close()  # terminate the hung process
            raise SidecarUnavailable(f"sidecar timed out after {self.timeout}s")
        if "err" in box:
            raise SidecarUnavailable(f"sidecar transport failed: {box['err']}")
        return box.get("line", "")

    # --- typed methods (mirror server.js) --------------------------------- #

    def consume_source_map(self, map_json: str) -> dict[str, Any]:
        """Recover ``{files: [{path, content}], sources}`` from a source map."""
        return self.call("consumeSourceMap", {"mapJson": map_json})

    def unpack_bundle(self, js_text: str) -> dict[str, Any]:
        """Unpack a bundle into ``{modules: [...]}`` (names lost without a map)."""
        return self.call("unpackBundle", {"jsText": js_text})

    def extract_literals(self, js_text: str) -> dict[str, Any]:
        """Static AST extraction of ``{strings, urls, routes}`` (never evals JS)."""
        return self.call("extractLiterals", {"jsText": js_text})

    def close(self) -> None:
        """Terminate the sidecar process (idempotent)."""
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                pass
            self._proc = None

    def __enter__(self) -> "Sidecar":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
