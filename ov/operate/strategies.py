"""Journey-strategy helpers -- intent shaping for the three strategies (§2.3).

The three strategies reuse the same primitives, varying only the *intent* written
to the journal: crawl-and-map (``enumerate``), goal-pursuit (``advance``), and
guided-replay (``replay``). These helpers keep that vocabulary in one place and
provide the deterministic target-selection a model-free driver needs.
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from ..base import Affordance, Observation

# Intent labels -- the per-step intent recorded in the journal.
INTENT_ENUMERATE = "enumerate"
INTENT_ADVANCE = "advance"
INTENT_REPLAY = "replay"

#: Roles treated as navigable for crawl-and-map.
NAV_ROLES = frozenset({"a", "link", "tab", "menuitem"})


def is_same_origin(url: str, base_url: str) -> bool:
    """True when ``url`` shares scheme+host(+port) with ``base_url``.

    >>> is_same_origin("https://x.com/a", "https://x.com/b")
    True
    >>> is_same_origin("https://y.com/a", "https://x.com/b")
    False
    """
    a, b = urlparse(url), urlparse(base_url)
    return (a.scheme, a.netloc) == (b.scheme, b.netloc)


def navigable_affordances(observation: Observation) -> list[Affordance]:
    """Return affordances suitable for breadth-first crawl (links/tabs/menuitems)."""
    return [a for a in observation.affordances if a.role in NAV_ROLES and a.enabled]


def absolutize(href: str, base_url: str) -> str:
    """Resolve ``href`` against ``base_url`` (drops fragments)."""
    resolved = urljoin(base_url, href)
    return resolved.split("#", 1)[0]
