"""``CaptureSession`` -- owns the browser and orchestrates the probes (§3.1).

The session is the deterministic capture spine: it resolves and dependency-orders
the enabled probes, attaches their listeners before navigation, snapshots state
on demand (the ``snapshot_state`` primitive of §2.3), finalizes and flushes them
at the end, stores the HAR, and persists the :class:`~ov.base.CaptureRun`.

It exposes ``page`` so the ``operate`` primitives and the scripted driver can act
on the same browser, and is a context manager for safe teardown.
"""

from __future__ import annotations

from typing import Iterable

from ..base import CaptureRun, JourneyStep, Observation
from ..config import OvConfig
from ..operate.observe import observe as observe_page
from .browser import BrowserSession
from .probes import PROBE_REGISTRY, Probe, ProbeContext, load_builtin_probes
from .stores import CaptureStore, resolve_store


def _resolve_probe_names(probes, config: OvConfig) -> tuple[list[str], list[str]]:
    """Resolve a probe selector into ``(known_names, unknown_names)``.

    ``unknown_names`` lets the caller surface typos instead of silently dropping
    them (informative-errors principle).
    """
    if probes in (None, "default"):
        names = list(config.default_probes)
    elif probes == "all":
        names = list(PROBE_REGISTRY.names())
    elif isinstance(probes, str):
        names = [probes]
    else:
        names = list(probes)
    resolved = [n for n in names if n in PROBE_REGISTRY]
    unknown = [n for n in names if n not in PROBE_REGISTRY]
    return resolved, unknown


class CaptureSession:
    """Drive one target and record everything into the store (zero-config default).

    Typical use is via the :func:`ov.observe` facade, but the session is directly
    usable::

        with CaptureSession(target_url="https://example.com") as s:
            s.open()                 # navigate to target_url + capture the load state
            run = s.run
    """

    def __init__(
        self,
        *,
        target_url: str,
        config: OvConfig | None = None,
        store: CaptureStore | str | None = None,
        mode: str = "reconstruct",
        probes="default",
        record_har: bool = True,
    ):
        load_builtin_probes()
        self.config = config or OvConfig.from_env()
        self.store = resolve_store(store)
        self.run = CaptureRun(
            target_url=target_url,
            mode=mode,  # type: ignore[arg-type]
            settings_snapshot=self.config.snapshot(),
        )
        self.probe_names, unknown_probes = _resolve_probe_names(probes, self.config)
        if unknown_probes:
            self.run.notes.append(
                f"ignored unknown probes {unknown_probes}; known probes: {PROBE_REGISTRY.names()}"
            )
        self.browser = BrowserSession(self.config, record_har=record_har)
        self._probes: list[Probe] = []
        self._ctx: ProbeContext | None = None
        self._started = False

    # --- lifecycle --------------------------------------------------------- #

    def start(self) -> "CaptureSession":
        """Launch the browser, attach CDP (Chromium), and attach all probes."""
        ordered = PROBE_REGISTRY.ordered(self.probe_names)
        self._probes = [item.fn() for item in ordered]
        self.browser.start()
        # After the browser launches, any failure must still tear it down so we
        # don't leak a browser/Playwright process on the error path.
        try:
            cdp = self.browser.cdp()
            self._ctx = ProbeContext(
                store=self.store,
                run=self.run,
                config=self.config,
                page=self.browser.page,
                cdp=cdp,
                extras={},
            )
            for probe in self._probes:
                try:
                    probe.attach(self._ctx)
                except Exception:  # noqa: BLE001 - one bad probe must not abort capture
                    self.run.notes.append(f"probe {probe.name} failed to attach")
        except Exception:
            self.browser.stop()
            raise
        self._started = True
        return self

    @property
    def page(self):
        """The active Playwright ``Page`` for ``operate`` primitives / the driver."""
        return self.browser.page

    # --- driving ----------------------------------------------------------- #

    def navigate(self, url: str) -> None:
        """Navigate the page to ``url`` (waits for the default load state)."""
        self.page.goto(url)

    def open(self, url: str | None = None, *, intent: str = "load") -> JourneyStep:
        """Navigate to the target (or ``url``) and capture the initial state."""
        self.navigate(url or self.run.target_url)
        return self.snapshot_state(intent=intent)

    def snapshot_state(
        self, *, intent: str = "observe", strategy: str = "ax_snapshot"
    ) -> JourneyStep:
        """Capture all probes for the current state and journal a :class:`JourneyStep`.

        Bundles the §2.3 ``snapshot_state`` primitive: observe affordances, run
        per-state probes, and record one step keyed to the produced artifacts.
        """
        if self._ctx is None:
            raise RuntimeError("CaptureSession not started; call start() first")
        obs: Observation | None = None
        try:
            obs = observe_page(self.page, strategy)
        except Exception:  # noqa: BLE001
            obs = None
        step = JourneyStep(
            intent=intent,
            affordances_seen=obs.affordances if obs else [],
            post_obs_hash=obs.obs_hash if obs else None,
        )
        self._ctx.step = step
        for probe in self._probes:
            try:
                for art in probe.capture(self._ctx):
                    self.run.artifacts.append(art)
                    step.artifact_ids.append(art.artifact_id)
            except Exception:  # noqa: BLE001
                self.run.notes.append(f"probe {probe.name} failed on capture")
        self.run.steps.append(step)
        return step

    def capture_step(self, step: JourneyStep) -> JourneyStep:
        """Run per-state probes for an externally-built step (used by the driver)."""
        if self._ctx is None:
            raise RuntimeError("CaptureSession not started; call start() first")
        self._ctx.step = step
        for probe in self._probes:
            try:
                for art in probe.capture(self._ctx):
                    self.run.artifacts.append(art)
                    step.artifact_ids.append(art.artifact_id)
            except Exception:  # noqa: BLE001
                self.run.notes.append(f"probe {probe.name} failed on capture")
        return step

    # --- teardown ---------------------------------------------------------- #

    def finalize(self) -> None:
        """Flush every probe (page still alive), close the browser, store the HAR."""
        if self._ctx is None:
            return
        from ..base import utcnow

        self.run.finished_at = utcnow()
        for probe in self._probes:
            try:
                for art in probe.finalize(self._ctx):
                    self.run.artifacts.append(art)
            except Exception:  # noqa: BLE001
                self.run.notes.append(f"probe {probe.name} failed on finalize")
        self.browser.close()  # flushes HAR
        if self.browser.har_bytes:
            har_art = self.store.put_artifact(
                self.browser.har_bytes,
                kind="har",
                content_type="application/json+har",
                meta={"target": self.run.target_url},
            )
            self.run.artifacts.append(har_art)
        self.store.save_run(self.run)

    def close(self) -> None:
        """Finalize if needed and tear down (idempotent)."""
        if self._started and self.run.finished_at is None:
            self.finalize()
        self.browser.stop()
        self._started = False

    def __enter__(self) -> "CaptureSession":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.close()
