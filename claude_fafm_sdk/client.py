"""Namepoint client — full intel at personal scale, via MCPaaS.

A *namepoint* is your free handle on ``memory.faf.one`` where your soul lives
(hosted + sticky). This client wraps the MCPaaS ``get_soul`` / ``write_soul`` MCP
tools — the *same* backend and the *same* pattern as grok-faf-voice's
``FAFMemory``, so the family stays one integration, never a fork.

Offline-first: ``fastmcp`` is an OPTIONAL dependency. The local ``Soul`` works
with no account and no network; install ``claude-fafm-sdk[namepoint]`` only when
you want hosted reads/writes.

    np = Namepoint("@me", api_key=os.environ["MCPAAS_API_KEY"])
    await np.push("a durable fact", type="fact")
    body = await np.pull()
"""

from __future__ import annotations

import os
from typing import Any

MEMORY_ENDPOINT = "https://memory.faf.one"
_MCP_URL = f"{MEMORY_ENDPOINT}/mcp"


class NamepointUnavailable(RuntimeError):
    """The namepoint backend (or its client deps) isn't reachable."""


class NamepointAuthRequired(RuntimeError):
    """A write was attempted without a namepoint key."""


def _client_classes() -> tuple[Any, Any]:
    try:
        from fastmcp import Client
        from fastmcp.client.transports import StreamableHttpTransport
    except ImportError as e:  # pragma: no cover - exercised only when extra absent
        raise NamepointUnavailable(
            "hosted namepoints need fastmcp — install:  uv add 'claude-fafm-sdk[namepoint]'\n"
            "    (the local Soul works fully offline without it)"
        ) from e
    return Client, StreamableHttpTransport


def _first_text(result: Any) -> str:
    """Extract the first text block from a fastmcp tool result."""
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text is not None:
            return text
    return str(result)


class Namepoint:
    """Client to a hosted namepoint. Reads are public; writes need a key.

    Free tier: 1 namepoint, full intel, soul hosted. Scale (more namepoints /
    team / production) → paid.
    """

    def __init__(self, handle: str, *, api_key: str | None = None, mcp_url: str = _MCP_URL) -> None:
        self.handle = handle
        self._api_key = api_key or os.environ.get("MCPAAS_API_KEY")
        self._mcp_url = mcp_url

    async def pull(self) -> str:
        """Fetch the hosted soul body (``get_soul``). Public — no key needed."""
        Client, Transport = _client_classes()
        async with Client(Transport(url=self._mcp_url)) as client:
            return _first_text(await client.call_tool("get_soul", {"soul": self.handle}))

    async def push(self, text: str, *, type: str = "note", tags: list[str] | None = None) -> str:
        """Write an entry to the hosted soul (``write_soul``). Needs a key."""
        if not self._api_key:
            raise NamepointAuthRequired(
                "writing to a namepoint needs your free key — get one at "
                "https://memory.faf.one (or set MCPAAS_API_KEY). Reads (pull) need no key."
            )
        Client, Transport = _client_classes()
        args: dict[str, Any] = {"soul": self.handle, "entry": text, "type": type, "token": self._api_key}
        if tags:
            args["tags"] = tags
        async with Client(Transport(url=self._mcp_url)) as client:
            return _first_text(await client.call_tool("write_soul", args))

    async def recall(self, query: str, *, limit: int | None = None) -> list:
        """Recall from the hosted soul.

        Pulls the soul and runs deterministic recall locally today; semantic /
        ranked recall is the namepoint's full-intel upgrade, served as the
        server intel lands. Returns a list of matching ``Fact``s.
        """
        from io import StringIO

        import yaml

        from .soul import Fact

        body = await self.pull()
        # get_soul may prepend a server preamble before the YAML body.
        yaml_body = body.split("\n---\n", 1)[-1]
        doc = yaml.safe_load(StringIO(yaml_body)) or {}
        facts = [Fact.from_obj(f) for f in ((doc.get("memory") or {}).get("facts") or [])]
        q = (query or "").lower()
        hits = [f for f in facts if not q or q in f.text.lower()]
        return hits[:limit] if limit is not None else hits
