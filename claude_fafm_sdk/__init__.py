"""claude-fafm-sdk — portable, cross-vendor AI memory in ``.fafm``.

Offline-first: the local ``Soul`` works with no account. Connect a free
namepoint for the full intel (semantic recall, smart-merge) at personal scale.

    from claude_fafm_sdk import Soul

    soul = Soul("@me")
    soul.etch("ships uv-first", id="install", type="reference", priority="high")
    soul.save("me.fafm")
    soul.recall("uv")
"""

from .client import (
    MEMORY_ENDPOINT,
    Namepoint,
    NamepointAuthRequired,
    NamepointUnavailable,
)
from .soul import PRIORITY_ORDER, Fact, Soul, canonical_priority

__version__ = "0.1.1"

__all__ = [
    "Soul",
    "Fact",
    "Namepoint",
    "NamepointAuthRequired",
    "NamepointUnavailable",
    "MEMORY_ENDPOINT",
    "PRIORITY_ORDER",
    "canonical_priority",
    "__version__",
]
