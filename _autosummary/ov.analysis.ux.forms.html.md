# ov.analysis.ux.forms

Form-records analyzer: the state-changing actions a page offers, and what guards them (#21).

One record per `<form>` (and per AJAX submission found in inline scripts) in the captured DOM:
page URL, resolved action, method, encoding, fields, and the protections around it (CSRF token,
honeypot-like fields, captcha, file upload, navigation-only forms). From the main document’s
response headers it adds the session cookie’s `SameSite` and the framing policy. Read-only: it
only reads captured artifacts and never submits anything. Writes one `forms` artifact (a JSON
list) and a summary; it emits no findings.

Caveat: `Set-Cookie` values are redacted at capture by default (`redact_values`), so
`session_cookie_samesite` is `None` unless the run was captured with redaction off.

### Functions

| [`analyze_forms`](#ov.analysis.ux.forms.analyze_forms)(ctx)              | Write a `forms` artifact (JSON list of form records) for the run's captured pages.   |
|----------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| [`extract_forms`](#ov.analysis.ux.forms.extract_forms)(html[, page_url]) | Form records for every `<form>` and inline-script AJAX POST in `html` (pure).        |
| [`header_facts`](#ov.analysis.ux.forms.header_facts)(headers)           | Response-header facts that decide how a site can be posted to or framed (pure).      |

### ov.analysis.ux.forms.analyze_forms(ctx)

Write a `forms` artifact (JSON list of form records) for the run’s captured pages.

* **Return type:**
  [`AnalyzerOutput`](ov.analysis.context.html.md#ov.analysis.context.AnalyzerOutput)

### ov.analysis.ux.forms.extract_forms(html, page_url='')

Form records for every `<form>` and inline-script AJAX POST in `html` (pure).

```pycon
>>> recs = extract_forms('<form action="/go" method="post"><input name="_token" type="hidden"></form>', "https://x.org/a")
>>> recs[0]["action"], recs[0]["method"], recs[0]["protections"]["csrf"]
('https://x.org/go', 'POST', True)
```

* **Return type:**
  [`list`](https://docs.python.org/3/builtins/stdtypes.html#list)[[`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]

### ov.analysis.ux.forms.header_facts(headers)

Response-header facts that decide how a site can be posted to or framed (pure).

```pycon
>>> header_facts({"X-Frame-Options": "DENY"})["framing_blocked"]
True
```

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]
