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
from .identity import (
    Identity,
    IdentityError,
    claim_email,
    load_identity,
    provision_anonymous,
)
from .interop import from_claude_dir
from .soul import PRIORITY_ORDER, Fact, Soul, canonical_priority

__version__ = "0.4.0"

__all__ = [
    "Soul",
    "Fact",
    "from_claude_dir",
    "Namepoint",
    "NamepointAuthRequired",
    "NamepointUnavailable",
    "MEMORY_ENDPOINT",
    "Identity",
    "IdentityError",
    "provision_anonymous",
    "claim_email",
    "load_identity",
    "PRIORITY_ORDER",
    "canonical_priority",
    "__version__",
]
