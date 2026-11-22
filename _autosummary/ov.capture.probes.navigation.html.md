# ov.capture.probes.navigation

Navigation probe: URL changes, redirects, frame tree, and SPA history.

Hard navigations are captured from `framenavigated`; SPA soft navigations
(`history.pushState`/`replaceState`/`popstate`) are captured by injecting a
tiny init script that records URL changes onto `window.__ov_nav` and reading it
back at finalize. This keeps client-side route changes visible even when no
network request accompanies them.

### Classes

| [`NavigationProbe`](#ov.capture.probes.navigation.NavigationProbe)()   | Record hard navigations (events) + soft SPA navigations (injected hook).   |
|----------------------------------------------------------------------|----------------------------------------------------------------------------|

### *class* ov.capture.probes.navigation.NavigationProbe

Bases: [`Probe`](ov.capture.probes.html.md#ov.capture.probes.Probe)

Record hard navigations (events) + soft SPA navigations (injected hook).

#### attach(ctx)

Subscribe listeners before navigation. Default: no-op.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### finalize(ctx)

Flush accumulated state into artifacts at run end. Default: nothing.

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`Artifact`](ov.base.html.md#ov.base.Artifact)]
