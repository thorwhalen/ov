"""Form-records analyzer: the state-changing actions a page offers, and what guards them (#21).

One record per ``<form>`` (and per AJAX submission found in inline scripts) in the captured DOM:
page URL, resolved action, method, encoding, fields, and the protections around it (CSRF token,
honeypot-like fields, captcha, file upload, navigation-only forms). From the main document's
response headers it adds the session cookie's ``SameSite`` and the framing policy. Read-only: it
only reads captured artifacts and never submits anything. Writes one ``forms`` artifact (a JSON
list) and a summary; it emits no findings.

Caveat: ``Set-Cookie`` values are redacted at capture by default (``redact_values``), so
``session_cookie_samesite`` is ``None`` unless the run was captured with redaction off.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from .. import register_analyzer
from ..context import AnalysisContext, AnalyzerOutput

_NON_FIELD_INPUTS = {"submit", "button", "reset", "image"}
_CSRF_NAME = re.compile(r"csrf|xsrf|authenticity_token|^_token$|__requestverificationtoken", re.I)
_HONEYPOT = re.compile(r"honeypot|hp_|_hp$|^website$|^url$|leave.?blank|do.?not.?fill", re.I)
_CAPTCHA = re.compile(r"captcha|g-recaptcha|h-captcha|cf-turnstile|turnstile", re.I)
_AJAX_POST = re.compile(
    r"""(?:\$\.post\(\s*|\$\.ajax\(\s*\{[^}]*?url\s*:\s*|fetch\(\s*|\.open\(\s*['"]POST['"]\s*,\s*)['"]([^'"]+)['"]""",
    re.I | re.S,
)
_CSRF_META = re.compile(r"csrf|xsrf", re.I)


def _label_for(tree: Any) -> dict[str, str]:
    return {
        lab.attributes["for"]: (lab.text() or "").strip()
        for lab in tree.css("label[for]")
        if lab.attributes.get("for")
    }


def _field(node: Any, labels: dict[str, str]) -> dict[str, Any]:
    attrs = node.attributes
    rec: dict[str, Any] = {
        "tag": node.tag,
        "type": attrs.get("type") or ("text" if node.tag == "input" else node.tag),
        "name": attrs.get("name"),
        "label": labels.get(attrs.get("id") or "") or attrs.get("aria-label"),
        "required": "required" in attrs or attrs.get("aria-required") == "true",
    }
    if node.tag == "select":
        rec["options"] = [
            o.attributes.get("value", (o.text() or "").strip()) for o in node.css("option")
        ]
    if attrs.get("accept"):
        rec["accept"] = attrs["accept"]
    return rec


def _concealed(node: Any) -> bool:
    style = (node.attributes.get("style") or "").replace(" ", "").lower()
    return "display:none" in style or "visibility:hidden" in style or "left:-" in style


def _is_honeypot(node: Any) -> bool:
    """A visible-type field hidden from people (inline style, on it or its parent) or named like a trap."""
    if _concealed(node) or (node.parent is not None and _concealed(node.parent)):
        return True
    attrs = node.attributes
    return bool(
        _HONEYPOT.search(attrs.get("name") or "")
        and (attrs.get("tabindex") == "-1" or attrs.get("autocomplete") == "off")
    )


def _encoding(form: Any, fields: list[dict]) -> str:
    enc = (form.attributes.get("enctype") or "").lower()
    if "multipart" in enc or any(f["type"] == "file" for f in fields):
        return "multipart"
    return "text" if "text/plain" in enc else "urlencoded"


def extract_forms(html: str, page_url: str = "") -> list[dict[str, Any]]:
    """Form records for every ``<form>`` and inline-script AJAX POST in ``html`` (pure).

    >>> recs = extract_forms('<form action="/go" method="post"><input name="_token" type="hidden"></form>', "https://x.org/a")
    >>> recs[0]["action"], recs[0]["method"], recs[0]["protections"]["csrf"]
    ('https://x.org/go', 'POST', True)
    """
    tree = HTMLParser(html)
    labels = _label_for(tree)
    meta_csrf = any(
        _CSRF_META.search(m.attributes.get("name") or "") for m in tree.css("meta[name]")
    )
    records: list[dict[str, Any]] = []
    for form in tree.css("form"):
        nodes = [
            n
            for n in form.css("input, select, textarea")
            if not (n.tag == "input" and (n.attributes.get("type") or "text") in _NON_FIELD_INPUTS)
        ]
        fields = [_field(n, labels) for n in nodes]
        raw_action = form.attributes.get("action")
        names = [f["name"] or "" for f in fields]
        visible = [f for f in fields if f["type"] != "hidden"]
        honeypots = [
            f["name"]
            for f, n in zip(fields, nodes)
            if f["type"] != "hidden" and f["name"] and _is_honeypot(n)
        ]
        nav_only = (
            (raw_action in (None, "", "#"))
            and len(visible) > 0
            and all(f["tag"] == "select" for f in visible)
            and (form.attributes.get("method") or "get").lower() == "get"
        )
        records.append(
            {
                "page_url": page_url,
                "kind": "form",
                "action": urljoin(page_url, raw_action) if raw_action else page_url,
                "method": (form.attributes.get("method") or "GET").upper(),
                "encoding": _encoding(form, fields),
                "fields": fields,
                "protections": {
                    "csrf": any(_CSRF_NAME.search(n) for n in names) or meta_csrf,
                    "honeypot_fields": honeypots,
                    "captcha": bool(_CAPTCHA.search(form.html or "")),
                    "file_upload": any(f["type"] == "file" for f in fields),
                    "navigation_only": nav_only,
                },
            }
        )
    for script in tree.css("script:not([src])"):
        code = script.text() or ""
        for m in _AJAX_POST.finditer(code):
            window = code[m.start() : m.start() + 600]
            if not re.search(r"post|method", window, re.I):
                continue
            records.append(
                {
                    "page_url": page_url,
                    "kind": "ajax",
                    "action": urljoin(page_url, m.group(1)),
                    "method": "POST",
                    "encoding": "ajax",
                    "fields": [],
                    "protections": {
                        "csrf": bool(re.search(r"x-csrf-token|x-xsrf-token", window, re.I)),
                        "honeypot_fields": [],
                        "captcha": False,
                        "file_upload": False,
                        "navigation_only": False,
                    },
                }
            )
    return records


def _cookie_samesite(set_cookie: str | None) -> str | None:
    """The ``SameSite`` value of a (not redacted) ``Set-Cookie`` header, else ``None``."""
    if not set_cookie or set_cookie.startswith("<redacted"):
        return None
    m = re.search(r"samesite\s*=\s*(\w+)", set_cookie, re.I)
    return m.group(1).capitalize() if m else None


def header_facts(headers: dict[str, str]) -> dict[str, Any]:
    """Response-header facts that decide how a site can be posted to or framed (pure).

    >>> header_facts({"X-Frame-Options": "DENY"})["framing_blocked"]
    True
    """
    low = {k.lower(): v for k, v in (headers or {}).items()}
    csp = low.get("content-security-policy", "")
    fa = re.search(r"frame-ancestors\s+([^;]+)", csp, re.I)
    return {
        "session_cookie_samesite": _cookie_samesite(low.get("set-cookie")),
        "frame_ancestors": fa.group(1).strip() if fa else None,
        "x_frame_options": low.get("x-frame-options"),
        "framing_blocked": bool(
            low.get("x-frame-options") or (fa and "*" not in fa.group(1))
        ),
    }


@register_analyzer("forms", lens="ux", requires=("dom",), produces=("forms",))
def analyze_forms(ctx: AnalysisContext) -> AnalyzerOutput:
    """Write a ``forms`` artifact (JSON list of form records) for the run's captured pages."""
    out = AnalyzerOutput()
    records: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for art in ctx.artifacts("dom"):
        page_url = (art.meta or {}).get("url") or ctx.run.target_url
        for rec in extract_forms(ctx.text(art), page_url):
            key = (rec["page_url"], rec["kind"], rec["action"], rec["method"], tuple(f["name"] for f in rec["fields"]))
            if key not in seen:
                seen.add(key)
                records.append(rec)
    headers: dict[str, str] = {}
    for recs in ctx.jsons("network"):
        for r in recs or []:
            if r.get("resource_type") == "document":
                headers = r.get("response_headers", {})
                break
        if headers:
            break
    facts = header_facts(headers)
    payload = {"forms": records, "headers": facts}
    # Drop a stale forms artifact so re-analysis does not accumulate them.
    ctx.run.artifacts[:] = [a for a in ctx.run.artifacts if a.kind != "forms"]
    ctx.run.artifacts.append(
        ctx.store.put_artifact(
            json.dumps(payload, indent=2).encode("utf-8"),
            kind="forms",
            content_type="application/json",
            meta={"form_count": len(records)},
        )
    )
    out.summary = {"forms": len(records), **facts}
    return out
