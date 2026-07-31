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
from .merge import EpochMismatch, merge_souls
from .packet import (
    PacketError,
    from_packet,
    from_packet_file,
    merge_packet,
    packet_is_signed,
    to_packet,
    to_packet_file,
)
from .signer import generate_keypair, sign_packet, verify_packet
from .debt import DebtReport, debt
from .policy import Policy, apply_policies, propose_policies
from .residual import ResidualReport, risk_scan
from .soul import PRIORITY_ORDER, Fact, Soul, canonical_priority

__version__ = "1.7.0"

__all__ = [
    "MEMORY_ENDPOINT",
    "PRIORITY_ORDER",
    "DebtReport",
    "EpochMismatch",
    "Fact",
    "Identity",
    "IdentityError",
    "Namepoint",
    "NamepointAuthRequired",
    "NamepointUnavailable",
    "PacketError",
    "Policy",
    "ResidualReport",
    "Soul",
    "__version__",
    "apply_policies",
    "canonical_priority",
    "claim_email",
    "debt",
    "from_claude_dir",
    "from_packet",
    "from_packet_file",
    "generate_keypair",
    "load_identity",
    "merge_packet",
    "merge_souls",
    "packet_is_signed",
    "propose_policies",
    "provision_anonymous",
    "risk_scan",
    "sign_packet",
    "to_packet",
    "to_packet_file",
    "verify_packet",
]
