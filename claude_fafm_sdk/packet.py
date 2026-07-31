"""Soul-Packet seal — travel ``.fafm`` memory as CRC-sealed bytes (T3-min).

An ``SPK1`` packet is a 16-byte little-endian header + a **canonical** ``.fafm``
YAML payload, integrity-sealed with **CRC-32**. This is the transport layer: it
does not touch the merge. Ingest reuses the CvRDT — ``merge_packet`` is exactly
``merge_souls`` over ``from_packet``.

**Provenance (1.4, optional):** a packet MAY carry an Ed25519 signature over the
same payload bytes CRC covers — the ``SIGNED`` flag bit + a fixed 64-byte trailer.
Signing/verifying live in the ``[sign]``-gated :mod:`claude_fafm_sdk.signer`; this
module stays **zero-crypto** (pyyaml only). ``from_packet`` opens *unsigned* only
and rejects a signed packet with an explicit pointer to ``verify_packet``.

Honesty (PACKET.md):
- **CRC = integrity, NOT authentication.** A signature (1.4) proves *a key signed
  these payload bytes* — NOT *this content can only travel signed* (the flag is not
  signed; stripping the trailer + clearing SIGNED recovers an equivalent unsigned
  packet). Not a PKI; a key is not a person.
- ``SPK1`` is the Soul-Packet seal — **distinct from** the project ``FAFB`` binary.
  The ``SIGNED`` bit is SPK1-local, not ``FAFB``/``FLAG_SIGNED`` interop.
  Extension ``.fafmp``. No IANA media type is claimed.
- Open **fails closed**: any bad magic / version / length / CRC / oversize /
  UTF-8 / YAML / signature raises ``PacketError`` and returns **no partial Soul**.

Wire layout (little-endian)::

    offset size field
    0      4    magic    b"SPK1"
    4      2    version  u16 = 1
    6      2    flags    u16       bit 0 = SIGNED (0x0001); other bits reserved, 0
    8      4    crc32    u32       CRC-32 of PAYLOAD ONLY (zlib/binascii)
    12     4    length   u32       payload byte length (N) — trailer NOT counted
    16     N    payload  UTF-8 canonical .fafm YAML
    16+N   64   sig      Ed25519 signature over payload[16:16+N]  (iff SIGNED)
"""
from __future__ import annotations

import binascii
import struct
from pathlib import Path

import yaml

from .merge import _canonical_sort_key, _value_hash, merge_souls
from .soul import Fact, Soul, canonical_priority

MAGIC = b"SPK1"  # Soul-Packet seal — NOT the project FAFB binary
VERSION = 1
FLAGS = 0  # default (unsigned) write flags
FLAG_SIGNED = 0x0001  # bit 0 — payload carries an Ed25519 trailer (SPK1-local, not FAFB)
SIG_SIZE = 64  # Ed25519 signature — fixed 64-byte trailer, no key_id (→1.4.1)
_HEADER = struct.Struct("<4sHHII")  # magic, version, flags, crc32, length
HEADER_SIZE = _HEADER.size  # 16
MAX_PAYLOAD = 10 * 1024 * 1024  # 10 MiB — fail closed BEFORE parsing
PACKET_SUFFIX = ".fafmp"


class PacketError(ValueError):
    """A Soul-Packet failed to open — bad magic/version/length/CRC/size/YAML/signature.

    Subclasses ``ValueError`` so callers can catch sealed-transport failures
    distinctly from other domain errors.
    """


def _crc32(payload: bytes) -> int:
    return binascii.crc32(payload) & 0xFFFFFFFF  # unsigned; PAYLOAD ONLY


def _seal_fact(f: Fact) -> Fact:
    """Fact in canonical SEAL form for byte-stability: **canonical priority**
    (``from_packet`` canonicalizes it on load, so raw ``"junk"`` must seal as the
    ``"standard"`` it re-loads as) + **sorted** tags/links. RAW text is preserved
    on purpose — the merge oracle's derived index keys on raw ``f.text``, and text
    is byte-stable through YAML unchanged. (T2 already made empty-``ts`` absent.)
    """
    return Fact(
        text=f.text,
        id=f.id,
        type=f.type,
        priority=canonical_priority(f.priority),
        tags=sorted(set(f.tags)),
        links=sorted(set(f.links)),
        timestamp=f.timestamp,
        source=f.source,
        extra=dict(f.extra),
    )


def normalize_for_seal(soul: Soul) -> Soul:
    """Pure — return a copy in **canonical seal order** so equal logical state
    seals to equal bytes: facts in canonical emit form (:func:`_seal_fact`) sorted
    by §5.4; sessions by ``value_hash``; index rebuilt. Opaque-map key order is
    handled by the canonical dump's ``sort_keys``. Idempotent; a merge output is
    already in this form. Does NOT change logical state.
    """
    facts = sorted((_seal_fact(f) for f in soul.facts), key=_canonical_sort_key)
    sessions = [s for _, s in sorted((_value_hash(s), s) for s in soul.sessions)]
    out = Soul(
        soul.namepoint,
        profile=soul.profile,
        facts=list(facts),
        retention=soul.retention,
        created=soul.created,
        sessions=sessions,
        preferences=dict(soul.preferences),
        custom=dict(soul.custom),
        extra=dict(soul.extra),
        memory_extra=dict(soul.memory_extra),
        tombstones=dict(soul.tombstones),  # 1.5: carry the graveyard; to_doc emits it sorted
        policies=list(soul.policies),  # 1.6: carry policy rules; to_doc omits when empty
        policy_auto=bool(soul.policy_auto),
        epoch=int(getattr(soul, "epoch", 0) or 0),  # 2.0: MERGE §11 / E5
        compaction_receipts=list(getattr(soul, "compaction_receipts", []) or []),
    )
    out.last_etched = soul.last_etched
    out.rebuild_index()
    return out


def to_canonical_yaml(soul: Soul) -> str:
    """Deterministic ``.fafm`` YAML for the seal payload — sorted keys, block
    style, no line wrap. Kept **separate** from ``Soul.to_yaml`` (human-facing,
    unsorted, wrapped) so the human save and the sealed bytes never couple.
    """
    return yaml.safe_dump(
        normalize_for_seal(soul).to_doc(),
        sort_keys=True,
        allow_unicode=True,
        default_flow_style=False,
        width=1 << 30,  # effectively no wrapping — wrapping is content-dependent
    )


def canonical_payload(soul: Soul) -> bytes:
    """The canonical ``.fafm`` payload bytes — what CRC and the signature both
    cover. Shared by :func:`to_packet` (unsigned) and the signer (signed) so the
    two paths seal identical bytes. Fails closed above the size cap.
    """
    payload = to_canonical_yaml(soul).encode("utf-8")
    if len(payload) > MAX_PAYLOAD:
        raise PacketError(f"payload {len(payload)} exceeds {MAX_PAYLOAD}-byte cap")
    return payload


def _pack_header(flags: int, payload: bytes) -> bytes:
    """Header for ``payload`` at ``flags`` — CRC and length are payload-only."""
    return _HEADER.pack(MAGIC, VERSION, flags, _crc32(payload), len(payload))


def to_packet(soul: Soul) -> bytes:
    """Seal a ``Soul`` into **unsigned** ``SPK1`` bytes (canonical payload + CRC-32).

    Byte-identical to 1.2/1.3 seals (``flags=0``, no trailer). For a signed packet
    use :func:`claude_fafm_sdk.signer.sign_packet`.
    """
    payload = canonical_payload(soul)
    return _pack_header(FLAGS, payload) + payload


def _payload_to_soul(payload: bytes) -> Soul:
    """Parse verified canonical payload bytes into a ``Soul`` (fail closed).

    Shared parse tail for :func:`from_packet` (unsigned) and the signer's
    ``verify_packet`` (signed) — both reach a ``Soul`` only after their own
    integrity/provenance gate has passed.
    """
    try:
        doc = yaml.safe_load(payload.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as e:
        raise PacketError(f"payload decode/parse failed: {e}") from e
    if not isinstance(doc, dict):
        raise PacketError("payload is not a .fafm mapping")
    try:
        return Soul.from_doc(doc)
    except ValueError as e:
        raise PacketError(f"invalid soul document: {e}") from e


def packet_is_signed(data: bytes) -> bool:
    """True iff ``data`` is a well-formed SPK1 header with the ``SIGNED`` bit set.

    A cheap, non-raising header peek used to route dispatch (``merge_packet``, CLI
    ``open``). Bad magic/version/short data → ``False`` so the caller falls through
    to the precise error raised by the real parser.
    """
    if len(data) < HEADER_SIZE:
        return False
    magic, version, flags, _crc, _length = _HEADER.unpack(data[:HEADER_SIZE])
    if magic != MAGIC or version != VERSION:
        return False
    return bool(flags & FLAG_SIGNED)


def from_packet(data: bytes) -> Soul:
    """Open **unsigned** ``SPK1`` bytes into a ``Soul``. **Fails closed** — raises
    ``PacketError`` (never a partial ``Soul``) on any integrity failure.

    A **signed** packet is rejected with an explicit pointer to ``verify_packet``:
    ``from_packet`` never CRC-opens a signed packet as unsigned (the trailer would
    fail the payload-only length check anyway; the flag check makes the reason
    actionable). A ``flags=0`` packet with a stray 64-byte tail is rejected by the
    length-exact check below.
    """
    if len(data) < HEADER_SIZE:
        raise PacketError("truncated: shorter than the 16-byte header")
    magic, version, flags, crc, length = _HEADER.unpack(data[:HEADER_SIZE])
    if magic != MAGIC:
        raise PacketError(f"bad magic {magic!r} (expected {MAGIC!r})")
    if version != VERSION:
        raise PacketError(f"unsupported version {version} (expected {VERSION})")
    if flags & FLAG_SIGNED:
        raise PacketError(
            "signed packet — open with a public key: verify_packet(data, public_key) "
            "or `claude-fafm-sdk verify -k <pubkey>`. from_packet opens unsigned only."
        )
    if length > MAX_PAYLOAD:
        raise PacketError(f"declared length {length} exceeds {MAX_PAYLOAD}-byte cap")
    payload = data[HEADER_SIZE:]
    if len(payload) != length:
        raise PacketError(f"length mismatch: header says {length}, got {len(payload)}")
    if _crc32(payload) != crc:
        raise PacketError("CRC mismatch — packet is corrupt")
    return _payload_to_soul(payload)


def merge_packet(local: Soul, data: bytes, *, public_key=None) -> Soul:
    """Ingest a packet into a local soul via the CvRDT merge.

    - **Unsigned** packet → ``merge_souls(local, from_packet(data))``.
    - **Signed** packet → **must** verify first: a signed peer is *never*
      CRC-opened. ``public_key`` is required (else ``PacketError``); the packet is
      opened through ``verify_packet`` (bad signature → ``PacketError``), then
      merged. Same-namepoint rules apply.

    ``public_key`` on an unsigned packet is ignored — a signature cannot be
    *required* of a peer (N1: the flag is not signed; strip-downgrade is possible).
    """
    if packet_is_signed(data):
        if public_key is None:
            raise PacketError(
                "signed packet — pass public_key to merge (a signed peer is never "
                "merged unverified). Strip the trailer to accept it as unsigned."
            )
        from .signer import verify_packet  # lazy: keep packet.py zero-crypto at import

        return merge_souls(local, verify_packet(data, public_key))
    return merge_souls(local, from_packet(data))


def to_packet_file(soul: Soul, path: str | Path) -> Path:
    """Seal a soul to an **unsigned** ``.fafmp`` file. Returns the written path."""
    p = Path(path)
    p.write_bytes(to_packet(soul))
    return p


def from_packet_file(path: str | Path) -> Soul:
    """Open an unsigned ``.fafmp`` file into a ``Soul`` (fails closed)."""
    return from_packet(Path(path).read_bytes())
