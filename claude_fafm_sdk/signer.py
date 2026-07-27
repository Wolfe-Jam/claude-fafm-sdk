"""Verifiable Provenance (1.4) — optional Ed25519 signatures over Soul-Packets.

**Provenance, not authentication branding.** A signature binds *a key* to the
sealed payload bytes: it proves *this key signed these bytes*, nothing more. It is
NOT a PKI, NOT encryption, NOT a human identity (a key is not a person), and it
does NOT make memory "authenticated" or prevent a strip-downgrade (the ``SIGNED``
flag is not itself signed — see ``PacketError`` note in :mod:`.packet` / N1).

This module is the **only** crypto surface. It's gated behind the ``[sign]`` extra:

    pip install 'claude-fafm-sdk[sign]'

The base install (and the zero-crypto Provable Receipt) never import
``cryptography``. Importing *this* module is always safe — the dependency is
probed once and every public call fails closed with a clean install hint if it's
absent, never a raw ``ImportError``.

Wire: signing sets ``FLAG_SIGNED`` and appends a **fixed 64-byte** Ed25519
signature over ``payload[16:16+N]`` — the same bytes CRC covers. No ``key_id``,
no embedded public key (→ 1.4.1). ``SPK1`` ≠ ``FAFB``.
"""
from __future__ import annotations

from typing import Tuple, Union

from .packet import (
    FLAG_SIGNED,
    HEADER_SIZE,
    MAGIC,
    SIG_SIZE,
    VERSION,
    PacketError,
    _crc32,
    _HEADER,
    _pack_header,
    _payload_to_soul,
    canonical_payload,
)
from .soul import Soul

try:  # probe once; never raise at import — the base install has no cryptography
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

    _HAVE_CRYPTO = True
except ImportError:  # pragma: no cover — exercised via the [sign]-missing gate (S10)
    _HAVE_CRYPTO = False

_INSTALL_HINT = (
    "Ed25519 signing needs the optional dependency — install it with:\n"
    "    pip install 'claude-fafm-sdk[sign]'\n"
    "(the base SDK and the Provable Receipt stay zero-crypto)."
)

# Accepted key types: PEM bytes, or a cryptography key object.
PrivateKeyLike = Union[bytes, "Ed25519PrivateKey"]
PublicKeyLike = Union[bytes, "Ed25519PublicKey"]


def _require_crypto() -> None:
    """Fail closed with a clean, actionable message when ``[sign]`` is absent."""
    if not _HAVE_CRYPTO:
        raise PacketError(_INSTALL_HINT)


# ── keys ────────────────────────────────────────────────────────────────────

def _private_pem(key: "Ed25519PrivateKey") -> bytes:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _public_pem(key: "Ed25519PublicKey") -> bytes:
    return key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def generate_keypair() -> Tuple[bytes, bytes]:
    """Fresh Ed25519 keypair as ``(private_pem, public_pem)`` (PKCS8 / SPKI PEM).

    The private PEM is unencrypted — the caller owns key-at-rest (CLI ``keygen``
    writes it ``0600``). Commit only the **public** PEM.
    """
    _require_crypto()
    key = Ed25519PrivateKey.generate()
    return _private_pem(key), _public_pem(key.public_key())


def keypair_from_seed(seed: bytes) -> Tuple[bytes, bytes]:
    """Deterministic ``(private_pem, public_pem)`` from a 32-byte seed.

    Reproducible cross-machine — used for **fixed test fixtures** so a golden wire
    packet can be pinned without committing private key bytes (the seed is a
    TEST-ONLY constant in the test module). Not for production keys.
    """
    _require_crypto()
    if len(seed) != 32:
        raise PacketError(f"Ed25519 seed must be 32 bytes, got {len(seed)}")
    key = Ed25519PrivateKey.from_private_bytes(seed)
    return _private_pem(key), _public_pem(key.public_key())


def load_private_key(pem: bytes) -> "Ed25519PrivateKey":
    """Load an unencrypted Ed25519 private key from PEM. Fails closed on non-Ed25519."""
    _require_crypto()
    try:
        key = serialization.load_pem_private_key(pem, password=None)
    except (ValueError, TypeError) as e:
        raise PacketError(f"bad private key PEM: {e}") from e
    if not isinstance(key, Ed25519PrivateKey):
        raise PacketError("private key is not Ed25519")
    return key


def load_public_key(pem: bytes) -> "Ed25519PublicKey":
    """Load an Ed25519 public key from PEM. Fails closed on non-Ed25519."""
    _require_crypto()
    try:
        key = serialization.load_pem_public_key(pem)
    except (ValueError, TypeError) as e:
        raise PacketError(f"bad public key PEM: {e}") from e
    if not isinstance(key, Ed25519PublicKey):
        raise PacketError("public key is not Ed25519")
    return key


def _coerce_private(k: PrivateKeyLike) -> "Ed25519PrivateKey":
    if isinstance(k, (bytes, bytearray)):
        return load_private_key(bytes(k))
    if isinstance(k, Ed25519PrivateKey):
        return k
    raise PacketError("private_key must be PEM bytes or an Ed25519PrivateKey")


def _coerce_public(k: PublicKeyLike) -> "Ed25519PublicKey":
    if isinstance(k, (bytes, bytearray)):
        return load_public_key(bytes(k))
    if isinstance(k, Ed25519PublicKey):
        return k
    raise PacketError("public_key must be PEM bytes or an Ed25519PublicKey")


# ── sign / verify ─────────────────────────────────────────────────────────────

def sign_packet(soul: Soul, private_key: PrivateKeyLike) -> bytes:
    """Seal ``soul`` into a **signed** ``SPK1`` packet.

    Header ``flags`` = ``SIGNED``; a fixed 64-byte Ed25519 signature over the raw
    canonical payload (the same bytes CRC covers) is appended as the trailer.
    ``private_key`` may be PEM bytes or an ``Ed25519PrivateKey``.
    """
    _require_crypto()
    priv = _coerce_private(private_key)
    payload = canonical_payload(soul)  # identical bytes to the unsigned seal
    sig = priv.sign(payload)  # Ed25519 → deterministic 64 bytes (RFC 8032)
    return _pack_header(FLAG_SIGNED, payload) + payload + sig


def verify_packet(data: bytes, public_key: PublicKeyLike) -> Soul:
    """Open a **signed** ``SPK1`` packet, verifying the trailer against ``public_key``.

    Strict — a signed packet is opened **only** through here, and only after the
    signature verifies. Fails closed (``PacketError``, no partial ``Soul``) on any
    of: not-signed / truncated / bad magic-version / length mismatch / CRC mismatch
    / bad signature. ``public_key`` may be PEM bytes or an ``Ed25519PublicKey``.
    """
    _require_crypto()
    pub = _coerce_public(public_key)
    if len(data) < HEADER_SIZE:
        raise PacketError("truncated: shorter than the 16-byte header")
    magic, version, flags, crc, length = _HEADER.unpack(data[:HEADER_SIZE])
    if magic != MAGIC:
        raise PacketError(f"bad magic {magic!r} (expected {MAGIC!r})")
    if version != VERSION:
        raise PacketError(f"unsupported version {version} (expected {VERSION})")
    if not flags & FLAG_SIGNED:
        raise PacketError("packet is not signed — open it with from_packet, not verify")
    # signed length rule — verify against the exact 16 + N + 64 layout; do NOT
    # reuse the unsigned 'payload = data[16:]' (that would fold the trailer in).
    if length > (10 * 1024 * 1024):
        raise PacketError("declared length exceeds the payload cap")
    expected = HEADER_SIZE + length + SIG_SIZE
    if len(data) != expected:
        raise PacketError(
            f"signed length mismatch: expected {expected} bytes "
            f"(16 + {length} payload + {SIG_SIZE} sig), got {len(data)}"
        )
    payload = data[HEADER_SIZE:HEADER_SIZE + length]
    sig = data[HEADER_SIZE + length:HEADER_SIZE + length + SIG_SIZE]
    if _crc32(payload) != crc:
        raise PacketError("CRC mismatch — packet is corrupt")  # integrity, separate from provenance
    try:
        pub.verify(sig, payload)
    except InvalidSignature as e:
        raise PacketError("signature verification failed — wrong key or tampered payload") from e
    return _payload_to_soul(payload)
