"""API-surface synthesis: merge schemas across journeys, classify, detect auth (D2 §4).

Groups captured XHR/fetch traffic by ``(method, path_template)``, merges the JSON
request/response samples into one schema each with **GenSON** (a monoidal merge
over samples), classifies each endpoint REST/RPC/GraphQL, infers the auth scheme
from request headers, and scores per-endpoint coverage. Produces
:class:`~ov.base.Endpoint`s for ``run.api_surface``. All pure over artifacts.
"""

from __future__ import annotations

import re
from typing import Any

from genson import SchemaBuilder

from ...base import Endpoint
from .. import register_analyzer
from ..context import AnalysisContext, AnalyzerOutput

_API_RESOURCE_TYPES = {"xhr", "fetch"}
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_HEX_RE = re.compile(r"^[0-9a-fA-F]{12,}$")
_VERB_SEGMENT_RE = re.compile(
    r"^(get|set|create|update|delete|fetch|list|add|remove)[A-Z]"
)


def normalize_path(path: str) -> str:
    """Templatize a URL path, replacing id-like segments with ``{id}`` (pure).

    >>> normalize_path("/api/users/42/posts/9c8")  # short slugs are left alone
    '/api/users/{id}/posts/9c8'
    >>> normalize_path("/v1/orders/550e8400-e29b-41d4-a716-446655440000")
    '/v1/orders/{id}'
    >>> normalize_path("/files/deadbeefcafe0001")  # 12+ hex looks like an id
    '/files/{id}'
    """
    segments = []
    for seg in path.split("/"):
        if seg.isdigit() or _UUID_RE.match(seg) or _HEX_RE.match(seg):
            segments.append("{id}")
        else:
            segments.append(seg)
    return "/".join(segments) or "/"


def classify_endpoint(method: str, path: str, request_body: Any) -> str:
    """Classify an endpoint as ``rest`` | ``rpc`` | ``graphql`` (pure).

    >>> classify_endpoint("POST", "/graphql", {"query": "{ me { id } }"})
    'graphql'
    >>> classify_endpoint("POST", "/api/createUser", None)
    'rpc'
    >>> classify_endpoint("GET", "/api/users/{id}", None)
    'rest'
    """
    if path.rstrip("/").endswith("/graphql") or (
        isinstance(request_body, dict)
        and ("query" in request_body or "mutation" in request_body)
    ):
        return "graphql"
    last = path.rstrip("/").rsplit("/", 1)[-1]
    is_jsonrpc = (
        isinstance(request_body, dict)
        and "jsonrpc" in request_body
        and "method" in request_body
    )
    if is_jsonrpc or (
        method.upper() == "POST" and (_VERB_SEGMENT_RE.match(last) or "." in last)
    ):
        return "rpc"
    return "rest"


def infer_auth(request_headers: dict[str, str]) -> str | None:
    """Infer the auth scheme from (possibly redacted) request headers (pure).

    >>> infer_auth({"authorization": "<redacted:40>"})
    'bearer'
    >>> infer_auth({"cookie": "<redacted:20>"})
    'cookie'
    >>> infer_auth({}) is None
    True
    """
    lower = {k.lower(): v for k, v in (request_headers or {}).items()}
    if "authorization" in lower:
        val = str(lower["authorization"]).lower()
        return "basic" if val.startswith("basic") else "bearer"
    if "x-api-key" in lower or "api-key" in lower:
        return "api-key"
    if "cookie" in lower:
        return "cookie"
    return None


@register_analyzer(
    "api_surface", lens="arch", requires=("network",), produces=("endpoints",)
)
def analyze_api(ctx: AnalysisContext) -> AnalyzerOutput:
    """Synthesize the API surface from captured XHR/fetch traffic."""
    out = AnalyzerOutput()
    body_arts = {a.artifact_id: a for a in ctx.artifacts("request")}

    # group: (method, path_template) -> aggregation
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for records in ctx.jsons("network"):
        for rec in records or []:
            if rec.get("resource_type") not in _API_RESOURCE_TYPES:
                continue
            method = (rec.get("method") or "GET").upper()
            path = _path_of(rec.get("url", ""))
            template = normalize_path(path)
            g = groups.setdefault(
                (method, template),
                {
                    "req_builder": SchemaBuilder(),
                    "resp_builder": SchemaBuilder(),
                    "samples": 0,
                    "statuses": set(),
                    "auth": None,
                    "kind": "rest",
                    "has_req": False,
                    "has_resp": False,
                    "artifact": None,
                },
            )
            g["samples"] += 1
            g["statuses"].add(rec.get("status"))
            g["auth"] = g["auth"] or infer_auth(rec.get("request_headers", {}))

            req_body = rec.get("request_body")
            if isinstance(req_body, (dict, list)):
                g["req_builder"].add_object(req_body)
                g["has_req"] = True
                g["kind"] = classify_endpoint(method, template, req_body)
            else:
                g["kind"] = classify_endpoint(method, template, None)

            resp = _json_body(ctx, body_arts.get(rec.get("body_artifact_id")))
            if resp is not None:
                g["resp_builder"].add_object(resp)
                g["has_resp"] = True
                g["artifact"] = rec.get("body_artifact_id")

    for (method, template), g in groups.items():
        coverage = _coverage_confidence(g["samples"], g["statuses"])
        out.endpoints.append(
            Endpoint(
                method=method,
                path_template=template,
                kind=g["kind"],
                request_schema=g["req_builder"].to_schema() if g["has_req"] else None,
                response_schema=g["resp_builder"].to_schema()
                if g["has_resp"]
                else None,
                auth=g["auth"],
                coverage={
                    "samples": g["samples"],
                    "statuses": sorted(s for s in g["statuses"] if s),
                },
                confidence=coverage,
                provenance=[g["artifact"]] if g["artifact"] else [],
            )
        )

    out.summary = {
        "endpoints": len(out.endpoints),
        "kinds": sorted({e.kind for e in out.endpoints}),
    }
    return out


def _path_of(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).path or "/"


def _json_body(ctx: AnalysisContext, artifact) -> Any:
    if artifact is None:
        return None
    ct = artifact.content_type or ""
    if "json" not in ct:
        return None
    return ctx.json(artifact)


def _coverage_confidence(samples: int, statuses: set) -> int:
    """Per-endpoint coverage confidence (0-100): more samples + error coverage = higher."""
    score = min(50, samples * 15)
    if any(s and 200 <= s < 300 for s in statuses):
        score += 25
    if any(s and s >= 400 for s in statuses):
        score += 25  # observed an error path too
    return min(100, score)
