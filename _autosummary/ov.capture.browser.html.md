# ov.capture.browser

Playwright facade – the baseline driver (§9, D1).

This hides Playwright behind a clean lifecycle so no caller (or skill, or future
agent) ever touches a raw Playwright object. It is treated as a \*facade over a
CDP escape hatch, not a wall\*: [`BrowserSession.cdp()`](#ov.capture.browser.BrowserSession.cdp) lazily attaches a
[`CdpSession`](ov.capture.cdp.html.md#ov.capture.cdp.CdpSession) for the ~20% the high-level API can’t reach.

The sync Playwright API is used deliberately – capture is a synchronous,
step-by-step orchestration and the sync API keeps the code legible. HAR is
recorded to a temp `.har.zip` with embedded bodies and read back after the
context closes (HAR only flushes on `context.close()`); structured network
records come from event accumulation in the network probe, not from the HAR.

### Classes

| [`BrowserSession`](#ov.capture.browser.BrowserSession)(config, \*[, record_har])   | Owns a Playwright browser/context/page for one capture run.   |
|---------------------------------------------------------------------------------------------|---------------------------------------------------------------|

### Exceptions

| [`BrowserNotAvailable`](#ov.capture.browser.BrowserNotAvailable)   | Raised when Playwright or its browsers are not usable.   |
|------------------------------------------------------------------------|----------------------------------------------------------|

### *exception* ov.capture.browser.BrowserNotAvailable

Bases: [`RuntimeError`](https://docs.python.org/3/builtins/exceptions.html#RuntimeError)

Raised when Playwright or its browsers are not usable.

Carries the install hint so the message is actionable, per the project’s
informative-errors principle.

### *class* ov.capture.browser.BrowserSession(config, , record_har=True)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Owns a Playwright browser/context/page for one capture run.

Lifecycle is explicit ([`start()`](#ov.capture.browser.BrowserSession.start) / [`close()`](#ov.capture.browser.BrowserSession.close)) so the orchestrator can
flush in-memory probe state *before* closing the context (which flushes HAR),
then ingest the HAR. It is also a context manager for simple call sites.

#### cdp()

Lazily attach and return a [`CdpSession`](ov.capture.cdp.html.md#ov.capture.cdp.CdpSession) (Chromium).

Returns `None` on non-Chromium browsers, where CDP is unavailable.

#### close()

Close the context (flushing HAR), read the HAR, then tear down.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

#### *property* context

The active Playwright `BrowserContext`.

#### *property* har_bytes *: [bytes](https://docs.python.org/3/builtins/stdtypes.html#bytes) | [None](https://docs.python.org/3/builtins/constants.html#None)*

The recorded HAR archive bytes (available only after [`close()`](#ov.capture.browser.BrowserSession.close)).

#### *property* page

The active Playwright `Page` (raises if not started).

#### start()

Launch the browser and open a context + page. Returns self.

* **Return type:**
  [`BrowserSession`](#ov.capture.browser.BrowserSession)

#### stop()

Hard teardown of browser + playwright (idempotent).

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)
