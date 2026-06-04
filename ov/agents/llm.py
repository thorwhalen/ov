"""Provider-agnostic LLM facade for the ``ov`` agent layer (thin, injected, optional).

``ov``'s deterministic core needs no model. The agent layer adds *bounded* model use
— always **dependency-injected**, so there is no provider lock-in and the package
imports fine with no LLM SDK present. This facade is a thin layer over
:mod:`coact.llm` (itself glue over ``skill.ai``), adding the two ov-specific things
coact's generic facade does not carry:

* **model routing** — the per-role default models from the spec's §10 cost gate:
  operator → Haiku (throughput, many steps), UX-analyst → Sonnet (grounded
  narrative judgment), Arch-analyst / orchestrator → Opus (design reasoning /
  planning);
* a **multimodal** :func:`structured` path — the UX analyst grounds judgment in
  *marked screenshots*, which coact's text-only ``structured`` cannot carry. Inject
  any object exposing ``structured(prompt, schema, *, images=...)`` for full control
  (real vision client); otherwise this degrades to coact's portable text-only path,
  which is still grounded because the evidence bundle's *facts* are textual
  summaries of each marked region (§8.1).
"""

from __future__ import annotations

from typing import Any, Optional

from ._util import require

#: Per-role default model selectors (host SDK literals), from the §10 cost gate.
DEFAULT_MODELS: dict[str, str] = {
    "operator": "haiku",
    "ux": "sonnet",
    "arch": "opus",
    "orchestrator": "opus",
}


def default_model(role: str) -> str:
    """The default model selector for a role (falls back to ``"sonnet"``).

    >>> default_model("operator"), default_model("arch"), default_model("???")
    ('haiku', 'opus', 'sonnet')
    """
    return DEFAULT_MODELS.get(role, "sonnet")


def resolve_llm(llm: Any = None):
    """Resolve ``llm`` to a ``callable(str) -> str`` (via coact), or ``None``.

    Re-exported from :func:`coact.llm.resolve_llm` so ov callers have one import and
    one injection convention (a callable, an ``aw`` ``StepConfig``, a model-name
    string, or ``None`` to discover an ambient provider).
    """
    (coact_llm,) = require("coact.llm", feature="ov.agents LLM facade")
    return coact_llm.resolve_llm(llm)


def structured(
    prompt: str,
    schema: dict,
    *,
    llm: Any = None,
    images: Optional[list] = None,
    retries: int = 1,
) -> Optional[dict]:
    """Best-effort schema-conforming dict from an LLM, or ``None`` if unavailable.

    Resolution order honours dependency injection:

    1. if ``llm`` exposes a ``structured`` method, it is used as-is — this is the
       multimodal path (the method may accept ``images=``); a real vision client
       plugs in here;
    2. otherwise fall through to coact's portable text-only ``structured`` (any
       ``images`` are dropped — the bundle's textual facts still ground the claims);
    3. if no LLM is resolvable at all, return ``None`` so callers fall back to a
       deterministic-only path (no crash, no provider lock-in).
    """
    client_structured = getattr(llm, "structured", None)
    if callable(client_structured):
        try:
            return client_structured(prompt, schema, images=images)
        except TypeError:
            return client_structured(prompt, schema)
    (coact_llm,) = require("coact.llm", feature="ov.agents LLM facade")
    return coact_llm.structured(prompt, schema, llm=llm, retries=retries)
