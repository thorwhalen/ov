# ov.analysis.arch.api

API-surface synthesis: merge schemas across journeys, classify, detect auth (D2 §4).

Groups captured XHR/fetch traffic by `(method, path_template)`, merges the JSON
request/response samples into one schema each with **GenSON** (a monoidal merge
over samples), classifies each endpoint REST/RPC/GraphQL, infers the auth scheme
from request headers, and scores per-endpoint coverage. Produces
`api_surface``. All pure over artifacts.

### Functions

| [`analyze_api`](#ov.analysis.arch.api.analyze_api)(ctx)                              | Synthesize the API surface from captured XHR/fetch traffic.            |
|------------------------------------------------------------------------------------------------|------------------------------------------------------------------------|
| [`classify_endpoint`](#ov.analysis.arch.api.classify_endpoint)(method, path, request_body) | Classify an endpoint as `rest` | `rpc` | `graphql` (pure).             |
| [`infer_auth`](#ov.analysis.arch.api.infer_auth)(request_headers)                   | Infer the auth scheme from (possibly redacted) request headers (pure). |
| [`normalize_path`](#ov.analysis.arch.api.normalize_path)(path)                          | Templatize a URL path, replacing id-like segments with `{id}` (pure).  |

### ov.analysis.arch.api.analyze_api(ctx)

Synthesize the API surface from captured XHR/fetch traffic.

* **Return type:**
  [`AnalyzerOutput`](ov.analysis.context.html.md#ov.analysis.context.AnalyzerOutput)

### ov.analysis.arch.api.classify_endpoint(method, path, request_body)

Classify an endpoint as `rest` | `rpc` | `graphql` (pure).

```pycon
>>> classify_endpoint("POST", "/graphql", {"query": "{ me { id } }"})
'graphql'
>>> classify_endpoint("POST", "/api/createUser", None)
'rpc'
>>> classify_endpoint("GET", "/api/users/{id}", None)
'rest'
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### ov.analysis.arch.api.infer_auth(request_headers)

Infer the auth scheme from (possibly redacted) request headers (pure).

```pycon
>>> infer_auth({"authorization": "<redacted:40>"})
'bearer'
>>> infer_auth({"cookie": "<redacted:20>"})
'cookie'
>>> infer_auth({}) is None
True
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str) | [`None`](https://docs.python.org/3/builtins/constants.html#None)

### ov.analysis.arch.api.normalize_path(path)

Templatize a URL path, replacing id-like segments with `{id}` (pure).

```pycon
>>> normalize_path("/api/users/42/posts/9c8")  # short slugs are left alone
'/api/users/{id}/posts/9c8'
>>> normalize_path("/v1/orders/550e8400-e29b-41d4-a716-446655440000")
'/v1/orders/{id}'
>>> normalize_path("/files/deadbeefcafe0001")  # 12+ hex looks like an id
'/files/{id}'
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
