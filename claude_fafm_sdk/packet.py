"""Soul-Packet seal — travel ``.fafm`` memory as CRC-sealed bytes (T3-min).

An ``SPK1`` packet is a 16-byte little-endian header + a **canonical** ``.fafm``
YAML payload, integrity-sealed with **CRC-32**. This is the transport layer: it
does not touch the merge. Ingest reuses the CvRDT — ``merge_packet`` is exactly
``merge_souls`` over ``from_packet``.

Honesty (PACKET.md):
- **CRC = integrity, NOT authentication.** No signing, no encryption. A packet
  proves it wasn't *corrupted*, not who *sent* it.
- ``SPK1`` is the Soul-Packet seal v0 — **distinct from** the project ``FAFB``
  binary. Extension ``.fafmp``. No IANA media type is claimed.
- Open **fails closed**: any bad magic / version / length / CRC / oversize /
  UTF-8 / YAML raises ``PacketError`` and returns **no partial Soul**.

Wire layout (little-endian)::

    offset size field
    0      4    magic    b"SPK1"
    4      2    version  u16 = 1
    6      2    flags    u16 = 0   (reserved; ignored on read)
    8      4    crc32    u32       CRC-32 of PAYLOAD ONLY (zlib/binascii)
    12     4    length   u32       payload byte length
    16     N    payload  UTF-8 canonical .fafm YAML
"""
from __future__ import annotations

import binascii
import struct
from pathlib import Path
from typing import Union

import yaml

from .merge import _canonical_sort_key, _value_hash, merge_souls
from .soul import Fact, Soul, canonical_priority

MAGIC = b"SPK1"  # Soul-Packet seal v0 — NOT the project FAFB binary
VERSION = 1
FLAGS = 0
_HEADER = struct.Struct("<4sHHII")  # magic, version, flags, crc32, length
HEADER_SIZE = _HEADER.size  # 16
MAX_PAYLOAD = 10 * 1024 * 1024  # 10 MiB — fail closed BEFORE parsing
PACKET_SUFFIX = ".fafmp"


class PacketError(ValueError):
    """A Soul-Packet failed to open — bad magic/version/length/CRC/size/YAML.

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


def to_packet(soul: Soul) -> bytes:
    """Seal a ``Soul`` into ``SPK1`` bytes (canonical payload + CRC-32)."""
    payload = to_canonical_yaml(soul).encode("utf-8")
    if len(payload) > MAX_PAYLOAD:
        raise PacketError(f"payload {len(payload)} exceeds {MAX_PAYLOAD}-byte cap")
    header = _HEADER.pack(MAGIC, VERSION, FLAGS, _crc32(payload), len(payload))
    return header + payload


def from_packet(data: bytes) -> Soul:
    """Open ``SPK1`` bytes into a ``Soul``. **Fails closed** — raises
    ``PacketError`` (never a partial ``Soul``) on any integrity failure.
    """
    if len(data) < HEADER_SIZE:
        raise PacketError("truncated: shorter than the 16-byte header")
    magic, version, _flags, crc, length = _HEADER.unpack(data[:HEADER_SIZE])
    if magic != MAGIC:
        raise PacketError(f"bad magic {magic!r} (expected {MAGIC!r})")
    if version != VERSION:
        raise PacketError(f"unsupported version {version} (expected {VERSION})")
    if length > MAX_PAYLOAD:
        raise PacketError(f"declared length {length} exceeds {MAX_PAYLOAD}-byte cap")
    payload = data[HEADER_SIZE:]
    if len(payload) != length:
        raise PacketError(f"length mismatch: header says {length}, got {len(payload)}")
    if _crc32(payload) != crc:
        raise PacketError("CRC mismatch — packet is corrupt")
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


def merge_packet(local: Soul, data: bytes) -> Soul:
    """Ingest a packet into a local soul via the CvRDT merge —
    ``merge_souls(local, from_packet(data))``. Same-namepoint rules apply.
    """
    return merge_souls(local, from_packet(data))


def to_packet_file(soul: Soul, path: Union[str, Path]) -> Path:
    """Seal a soul to a ``.fafmp`` file. Returns the written path."""
    p = Path(path)
    p.write_bytes(to_packet(soul))
    return p


def from_packet_file(path: Union[str, Path]) -> Soul:
    """Open a ``.fafmp`` file into a ``Soul`` (fails closed)."""
    return from_packet(Path(path).read_bytes())
