"""WJTTC — Verifiable Provenance (1.4): optional Ed25519 signatures over SPK1.

Provenance is a **transport** property — it never touches the merge oracle. These
guard the sign/verify contract and the fixed-fixture golden:

- **No private key material in git.** The golden's keypair is derived from a
  pinned 32-byte TEST-ONLY seed; the repo commits only the public PEM + the wire
  hex. Ed25519 is deterministic (RFC 8032), so the golden is reproducible on any
  machine.
- Signature covers the **same payload bytes** CRC covers. The ``SIGNED`` flag is
  not signed — verify proves *this key signed these bytes*, not *content can only
  travel signed* (N1).
"""
from __future__ import annotations

import struct

import pytest

# Signing needs the optional [sign] extra. In the zero-crypto base config
# (what a plain `pip install` and the base CI job give you) these tests skip —
# the base SDK + Provable Receipt stay crypto-free; the `sign` CI job runs them.
pytest.importorskip("cryptography")

from claude_fafm_sdk import (
    PacketError,
    from_packet,
    generate_keypair,
    merge_packet,
    packet_is_signed,
    sign_packet,
    to_packet,
    verify_packet,
)
from claude_fafm_sdk.merge import souls_equal
from claude_fafm_sdk.packet import FLAG_SIGNED, HEADER_SIZE, SIG_SIZE
from claude_fafm_sdk.signer import keypair_from_seed
from claude_fafm_sdk.soul import Fact, Soul

# TEST ONLY — a pinned 32-byte seed (00 01 .. 1f). NEVER a production key. It
# exists so the golden below can be reproduced without committing a private key.
_TEST_SEED = bytes(range(32))

# The fixed public key derived from _TEST_SEED (committed; the private half is not).
FIXTURE_PUBLIC_PEM = (
    b"-----BEGIN PUBLIC KEY-----\n"
    b"MCowBQYDK2VwAyEAA6EHv/POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg=\n"
    b"-----END PUBLIC KEY-----\n"
)

# captured 2026-07-31 from _fixture_soul() signed under _TEST_SEED @ SPK1 v1 +
# SIGNED + epoch: 0 (MERGE §11). Changing this is a wire-format change —
# conscious, a compat decision.
SIGNED_GOLDEN_HEX = (
    "53504b3101000100464fbf246c010000637265617465643a2027323032362d30312d30"
    "315430303a30303a30305a270a65706f63683a20300a696e6465783a0a2d206120e280"
    "9420616c7068610a2d20273f20e280942062657461270a6c6173745f6574636865643a"
    "2027323032362d30312d30325430303a30303a30305a270a6d656d6f72793a0a202063"
    "7573746f6d3a207b7d0a202066616374733a0a20202d2069643a20610a202020207072"
    "696f726974793a20686967680a20202020746578743a20616c7068610a202020207469"
    "6d657374616d703a2027323032362d30312d30315430303a30303a30305a270a20202d"
    "20626574610a20206b3a20760a2020707265666572656e6365733a207b7d0a20207365"
    "7373696f6e733a0a20202d2069643a2073310a202020206e3a20310a6e616d65706f69"
    "6e743a2027407369676e270a70726f66696c653a206b6e6f776c656467650a72657465"
    "6e74696f6e3a20666f72657665720a76657273696f6e3a2027312e31270a76ad187fa6"
    "2d68202ca7cbba60a2b3caed09431555df7d5b5f0711423e877ceb006bc71a16a04e9e"
    "609ad00d00fbbadb7785fd2a1fd02aa531740b30b2e8150d"
)
SIGNED_GOLDEN = bytes.fromhex(SIGNED_GOLDEN_HEX)


def _fixture_soul() -> Soul:
    """The pinned soul the golden bytes were captured from (byte-stable)."""
    s = Soul(
        "@sign",
        profile="knowledge",
        facts=[
            Fact(text="alpha", id="a", priority="high", timestamp="2026-01-01T00:00:00Z"),
            Fact(text="beta"),
        ],
        retention="forever",
        created="2026-01-01T00:00:00Z",
        sessions=[{"id": "s1", "n": 1}],
        memory_extra={"k": "v"},
    )
    s.last_etched = "2026-01-02T00:00:00Z"
    return s


def _fixture_keys() -> tuple[bytes, bytes]:
    return keypair_from_seed(_TEST_SEED)


# ── S1 — sign → verify round-trip ─────────────────────────────────────────────
def test_s1_sign_verify_roundtrip_logical() -> None:
    priv, pub = generate_keypair()  # runtime keygen path
    soul = _fixture_soul()
    signed = sign_packet(soul, priv)
    assert packet_is_signed(signed)
    assert souls_equal(verify_packet(signed, pub), soul)


# ── S2 — fixed-fixture golden wire hex ────────────────────────────────────────
def test_s2_signed_golden_is_byte_identical() -> None:
    priv, _pub = _fixture_keys()
    assert sign_packet(_fixture_soul(), priv) == SIGNED_GOLDEN


def test_s2_signed_golden_verifies_to_soul() -> None:
    assert souls_equal(verify_packet(SIGNED_GOLDEN, FIXTURE_PUBLIC_PEM), _fixture_soul())


def test_s2_fixture_pub_pem_matches_seed() -> None:
    _priv, pub = _fixture_keys()
    assert pub == FIXTURE_PUBLIC_PEM  # committed public PEM == the seed's public half


def test_s2_golden_header_and_layout() -> None:
    magic, version, flags, _crc, length = struct.unpack("<4sHHII", SIGNED_GOLDEN[:HEADER_SIZE])
    assert magic == b"SPK1"
    assert version == 1
    assert flags & FLAG_SIGNED  # SIGNED bit set
    assert len(SIGNED_GOLDEN) == HEADER_SIZE + length + SIG_SIZE  # fixed-64 trailer


# ── S3 — wrong public key rejects ─────────────────────────────────────────────
def test_s3_wrong_pubkey_rejected() -> None:
    priv, _pub = _fixture_keys()
    signed = sign_packet(_fixture_soul(), priv)
    _p2, other_pub = keypair_from_seed(bytes([0x09]) * 32)
    with pytest.raises(PacketError):
        verify_packet(signed, other_pub)


# ── S4 — payload bit-flip fails verify ────────────────────────────────────────
def test_s4_payload_bitflip_fails() -> None:
    priv, pub = _fixture_keys()
    signed = bytearray(sign_packet(_fixture_soul(), priv))
    signed[HEADER_SIZE] ^= 0xFF  # first payload byte
    with pytest.raises(PacketError):
        verify_packet(bytes(signed), pub)


# ── S5 — signature bit-flip fails verify ──────────────────────────────────────
def test_s5_signature_bitflip_fails() -> None:
    priv, pub = _fixture_keys()
    signed = bytearray(sign_packet(_fixture_soul(), priv))
    signed[-1] ^= 0xFF  # last trailer byte
    with pytest.raises(PacketError, match="signature"):
        verify_packet(bytes(signed), pub)


# ── S6 — unsigned seal byte-identical to 1.3 (flags=0, no trailer) ────────────
def test_s6_unsigned_seal_unchanged() -> None:
    soul = _fixture_soul()
    unsigned = to_packet(soul)
    _magic, _v, flags, _crc, length = struct.unpack("<4sHHII", unsigned[:HEADER_SIZE])
    assert flags == 0  # no SIGNED bit
    assert len(unsigned) == HEADER_SIZE + length  # no trailer
    assert not packet_is_signed(unsigned)


# ── S7 / U1 — from_packet: unsigned unchanged; signed → explicit reject ───────
def test_s7_from_packet_unsigned_unchanged() -> None:
    soul = _fixture_soul()
    assert souls_equal(from_packet(to_packet(soul)), soul)


def test_u1_from_packet_signed_rejects_explicitly() -> None:
    priv, _pub = _fixture_keys()
    signed = sign_packet(_fixture_soul(), priv)
    # length-exact reject in spirit; explicit SIGNED message points to verify.
    with pytest.raises(PacketError, match="signed"):
        from_packet(signed)


# ── U2 — merge of a signed packet without a key rejects (never CRC-open) ──────
def test_u2_merge_signed_without_key_rejects() -> None:
    priv, _pub = _fixture_keys()
    signed = sign_packet(_fixture_soul(), priv)
    with pytest.raises(PacketError, match="public_key"):
        merge_packet(Soul("@sign"), signed)


def test_merge_signed_with_key_ingests() -> None:
    priv, pub = _fixture_keys()
    signed = sign_packet(_fixture_soul(), priv)
    merged = merge_packet(Soul("@sign"), signed, public_key=pub)
    assert {f.text for f in merged.facts} == {"alpha", "beta"}


def test_signed_packet_carries_tombstones_1_4_x_1_5() -> None:
    # Provenance (1.4) over a Forgettable soul (1.5): the graveyard is part of the
    # canonical payload the signature covers, so it survives sign → verify intact.
    priv, pub = _fixture_keys()
    soul = Soul("@sign", facts=[Fact(text="keep", id="k")])
    soul.forget("gone", deleted_at="2026-06-01T00:00:00Z")
    signed = sign_packet(soul, priv)
    opened = verify_packet(signed, pub)
    assert ("id", "gone") in opened.tombstones
    assert souls_equal(opened, soul)
    # tampering with a signed tombstoned packet still fails closed
    bad = bytearray(signed)
    bad[HEADER_SIZE] ^= 0xFF
    with pytest.raises(PacketError):
        verify_packet(bytes(bad), pub)


def test_merge_signed_with_wrong_key_rejects_no_clobber() -> None:
    priv, _pub = _fixture_keys()
    signed = sign_packet(_fixture_soul(), priv)
    _p2, other_pub = keypair_from_seed(bytes([0x07]) * 32)
    local = Soul("@sign")
    local.etch("local-only", id="loc")
    with pytest.raises(PacketError):
        merge_packet(local, signed, public_key=other_pub)
    assert [f.id for f in local.facts] == ["loc"]  # never merged unverified


# ── optional gate rows (defensive wire edges) ────────────────────────────────
def test_signed_flag_missing_trailer_rejected() -> None:
    # SIGNED set but total == 16+N (no trailer) → verify length rule rejects.
    priv, pub = _fixture_keys()
    signed = sign_packet(_fixture_soul(), priv)
    truncated = signed[:-SIG_SIZE]  # drop the 64-byte trailer, keep SIGNED flag
    with pytest.raises(PacketError, match="length"):
        verify_packet(truncated, pub)


def test_unsigned_with_stray_trailer_rejected() -> None:
    # flags=0 but 64 trailing bytes → from_packet length-exact reject.
    stray = to_packet(_fixture_soul()) + b"\x00" * SIG_SIZE
    with pytest.raises(PacketError, match="length mismatch"):
        from_packet(stray)


def test_verify_on_unsigned_rejects() -> None:
    _priv, pub = _fixture_keys()
    with pytest.raises(PacketError, match="not signed"):
        verify_packet(to_packet(_fixture_soul()), pub)


# ── keys ──────────────────────────────────────────────────────────────────────
def test_keypair_from_seed_is_deterministic() -> None:
    a = keypair_from_seed(_TEST_SEED)
    b = keypair_from_seed(_TEST_SEED)
    assert a == b


def test_keypair_from_seed_wrong_length_rejected() -> None:
    with pytest.raises(PacketError, match="32 bytes"):
        keypair_from_seed(b"tooshort")


def test_generate_keypair_unique() -> None:
    assert generate_keypair()[0] != generate_keypair()[0]  # private PEMs differ


# ── S10 — [sign] missing → clean install hint, never a raw ImportError ────────
def test_s10_sign_extra_missing_clean_message(monkeypatch: pytest.MonkeyPatch) -> None:
    from claude_fafm_sdk import signer

    monkeypatch.setattr(signer, "_HAVE_CRYPTO", False)
    with pytest.raises(PacketError, match=r"claude-fafm-sdk\[sign\]"):
        signer.generate_keypair()
    with pytest.raises(PacketError, match=r"claude-fafm-sdk\[sign\]"):
        signer.sign_packet(_fixture_soul(), b"x")
    with pytest.raises(PacketError, match=r"claude-fafm-sdk\[sign\]"):
        signer.verify_packet(SIGNED_GOLDEN, FIXTURE_PUBLIC_PEM)
