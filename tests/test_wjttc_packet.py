"""WJTTC — Soul-Packet seal / open / CRC (T3-min gate, 20-T3-SCOPE P1–P7).

Transport only — merge stays ``merge_souls``. Round-trips the FULL residual
state (reuses the extended `_soul` strategy) so sessions / retention /
memory_extra travel too. Byte-identity (P7) is by construction: `to_packet`
normalizes + canonical-dumps, so equal logical state → equal bytes.
"""
from __future__ import annotations

import binascii
import os
import struct
import sys

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, os.path.dirname(__file__))

from claude_fafm_sdk.merge import merge_souls, normalize_text, souls_equal  # noqa: E402
from claude_fafm_sdk.packet import (  # noqa: E402
    HEADER_SIZE,
    MAGIC,
    MAX_PAYLOAD,
    VERSION,
    PacketError,
    _HEADER,
    from_packet,
    from_packet_file,
    merge_packet,
    to_packet,
    to_packet_file,
)
from claude_fafm_sdk.soul import Fact, Soul  # noqa: E402

from test_wjttc_merge_crdt import _soul  # noqa: E402  reuse the extended residual strategy


@st.composite
def _valid_soul(draw) -> Soul:
    """A soul with the one-fact-per-logical-key (id | normalized text) invariant
    that add/etch/merge all maintain. A raw list with collisions makes
    ``souls_equal`` order-dependent (``logical_state`` keeps last-in-list), so a
    seal that reorders to §5.4 would look like it "lost" a fact. Real souls never
    carry logical-key duplicates — the packet round-trips valid souls faithfully.
    """
    raw = draw(_soul())
    seen: set = set()
    facts = []
    for f in raw.facts:
        key = ("id", f.id) if f.id is not None else ("txt", normalize_text(f.text))
        if key not in seen:
            seen.add(key)
            facts.append(f)
    s = Soul(
        raw.namepoint,
        profile=raw.profile,
        facts=facts,
        retention=raw.retention,
        created=raw.created,
        sessions=raw.sessions,
        preferences=raw.preferences,
        custom=raw.custom,
        extra=raw.extra,
        memory_extra=raw.memory_extra,
    )
    s.last_etched = raw.last_etched
    return s


_S = _valid_soul()
_SET = settings(max_examples=200, deadline=None)


# ── P1 — round-trip logical equality (the T3-min "done" bar) ─────────────────
@_SET
@given(_S)
def test_p1_roundtrip_logical_equal(s):
    assert souls_equal(from_packet(to_packet(s)), s)


# ── P2 — bit-flip payload → CRC reject ───────────────────────────────────────
@_SET
@given(_S)
def test_p2_bitflip_payload_rejects(s):
    pkt = bytearray(to_packet(s))
    pkt[HEADER_SIZE] ^= 0xFF  # flip the first payload byte
    with pytest.raises(PacketError):
        from_packet(bytes(pkt))


# ── P3 — truncate → reject ───────────────────────────────────────────────────
def test_p3_truncate_rejects():
    pkt = to_packet(Soul("@t", facts=[Fact(text="alpha", id="x")]))
    with pytest.raises(PacketError):
        from_packet(pkt[:-4])  # payload shorter than declared length
    with pytest.raises(PacketError):
        from_packet(pkt[:8])  # cut into the header


# ── P4 — wrong magic → reject ────────────────────────────────────────────────
def test_p4_wrong_magic_rejects():
    pkt = bytearray(to_packet(Soul("@t")))
    pkt[0:4] = b"XXXX"
    with pytest.raises(PacketError):
        from_packet(bytes(pkt))


# ── P5 — double merge_packet idempotent (CvRDT through the seal) ─────────────
@_SET
@given(_S, _S)
def test_p5_double_merge_packet_idempotent(a, b):
    pkt = to_packet(b)
    m1 = merge_packet(a, pkt)
    assert souls_equal(merge_packet(m1, pkt), m1)


# ── P6 — both-ways converge through packets ─────────────────────────────────
@_SET
@given(_S, _S)
def test_p6_both_ways_converge(a, b):
    assert souls_equal(merge_packet(a, to_packet(b)), merge_packet(b, to_packet(a)))


# ── P7 — byte-identity (stretch, by construction) ───────────────────────────
@_SET
@given(_S, _S)
def test_p7_merge_both_ways_byte_identical(a, b):
    # seal(merge(a,b)) is byte-for-byte seal(merge(b,a)) — ties P6 to the wire
    assert to_packet(merge_souls(a, b)) == to_packet(merge_souls(b, a))


@_SET
@given(_S)
def test_p7_roundtrip_byte_stable(s):
    p = to_packet(s)
    assert to_packet(from_packet(p)) == p  # open then re-seal is identical


# ── adversarial (tiny, explicit) ────────────────────────────────────────────
def test_reject_empty_and_short():
    for bad in (b"", b"SPK1", b"SPK1\x01\x00\x00\x00"):
        with pytest.raises(PacketError):
            from_packet(bad)


def test_reject_version_mismatch():
    pkt = bytearray(to_packet(Soul("@t")))
    struct.pack_into("<H", pkt, 4, VERSION + 1)
    with pytest.raises(PacketError):
        from_packet(bytes(pkt))


def test_reject_oversize_declared_length():
    pkt = bytearray(to_packet(Soul("@t")))
    struct.pack_into("<I", pkt, 12, MAX_PAYLOAD + 1)  # length field beyond the cap
    with pytest.raises(PacketError):
        from_packet(bytes(pkt))


def test_reject_non_mapping_payload():
    payload = b"42\n"  # valid SPK1 wrapping a YAML scalar, not a mapping
    crc = binascii.crc32(payload) & 0xFFFFFFFF
    header = _HEADER.pack(MAGIC, VERSION, 0, crc, len(payload))
    with pytest.raises(PacketError):
        from_packet(header + payload)


def test_crc_is_payload_only_flags_ignored():
    # CRC covers PAYLOAD ONLY, and flags is reserved/ignored — so flipping the
    # (unvalidated) flags header field must still open cleanly.
    s = Soul("@t", facts=[Fact(text="alpha", id="x")])
    pkt = bytearray(to_packet(s))
    struct.pack_into("<H", pkt, 6, 0xFFFF)  # flags field
    assert souls_equal(from_packet(bytes(pkt)), s)


def test_integrity_not_auth_docstring():
    # honesty guard: the module says CRC is integrity, not authentication.
    import claude_fafm_sdk.packet as pkt

    assert "not authentication" in pkt.__doc__.lower() or "not auth" in pkt.__doc__.lower()


# ── file helpers ─────────────────────────────────────────────────────────────
def test_file_roundtrip(tmp_path):
    s = Soul(
        "@t",
        facts=[Fact(text="alpha", id="x")],
        retention="forever",
        sessions=[{"id": "s1", "n": 1}],
        memory_extra={"k": "v"},
    )
    p = to_packet_file(s, tmp_path / "soul.fafmp")
    assert souls_equal(from_packet_file(p), s)
