"""UX + accessibility deterministic analyzers (§5.1, D3).

Each module registers an analyzer that reads captured artifacts and emits
normalized :class:`~ov.base.Finding`s with ``severity = impact_tier x reach``.
The hard honesty constraint (D3) lives here: automated tooling catches only
~30-40% of WCAG issues, so the non-automatable tail is routed to
``needs_human_review`` and never asserted as resolved.
"""
