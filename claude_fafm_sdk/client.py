"""Namepoint client — the upgrade hook.

A *namepoint* is a free handle on ``memory.faf.one`` where your soul lives
(hosted + sticky) and where the FULL intel runs server-side: semantic/ranked
recall and LLM smart-merge, at personal scale. The intel is proprietary
(``fafm-engine`` / MCPaaS) — this client CALLS it, it never CONTAINS it.

Free tier: 1 namepoint, full intel, soul hosted. Scale (more namepoints / team /
production) → paid.

Status: the backend (``memory.faf.one``) is not live yet. The local ``Soul``
works fully offline today; this client defines the contract the backend fulfils.
"""

from __future__ import annotations

from .soul import Fact, Soul

MEMORY_ENDPOINT = "https://memory.faf.one"


class NamepointUnavailable(RuntimeError):
    """Raised when the namepoint backend isn't reachable yet."""


class Namepoint:
    """Client to a hosted namepoint (full intel at personal scale)."""

    def __init__(self, handle: str, *, endpoint: str = MEMORY_ENDPOINT) -> None:
        self.handle = handle
        self.endpoint = endpoint.rstrip("/")

    def recall(self, query: str, *, limit: int | None = None) -> list[Fact]:
        """Semantic / ranked recall (full intel) over the hosted soul."""
        raise self._coming("recall")

    def smart_merge(self, soul: Soul) -> Soul:
        """LLM smart-merge ('claude-decides') of a soul, server-side."""
        raise self._coming("smart_merge")

    def push(self, soul: Soul) -> None:
        """Host this soul on the namepoint (sticky)."""
        raise self._coming("push")

    def pull(self) -> Soul:
        """Fetch the hosted soul for this namepoint."""
        raise self._coming("pull")

    def _coming(self, op: str) -> NamepointUnavailable:
        return NamepointUnavailable(
            f"namepoint.{op}() needs the {self.endpoint} backend, which is not live yet. "
            f"Local Soul ops work offline today; the free namepoint is coming."
        )
