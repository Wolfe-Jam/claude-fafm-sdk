"""Wire-hex golden — a captured SPK1 packet's exact bytes.

Cross-language interop anchor: a second implementation of the seal must produce
these byte-for-byte from the same soul, and must CRC the **payload only**. Pins
the header layout, canonical-YAML determinism, and the payload-only CRC contract
(the classic cross-language trap). A change here is a wire-format change —
conscious, and a compat decision.
"""
from __future__ import annotations

import binascii
import struct

from claude_fafm_sdk.packet import HEADER_SIZE, MAGIC, VERSION, from_packet, to_packet
from claude_fafm_sdk.soul import Fact, Soul


def _wire_soul() -> Soul:
    """The fixed soul the golden bytes were captured from. Fully deterministic:
    pinned created / last_etched so the seal is byte-stable across runs."""
    s = Soul(
        "@wire",
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


# captured 2026-07-31 from _wire_soul() @ SPK1 v1 + epoch: 0 (MERGE §11).
# Changing this is a wire change.
GOLDEN_HEX = (
    "53504b3101000000f74f34bb6c010000637265617465643a2027323032362d30312d30"
    "315430303a30303a30305a270a65706f63683a20300a696e6465783a0a2d206120e280"
    "9420616c7068610a2d20273f20e280942062657461270a6c6173745f6574636865643a"
    "2027323032362d30312d30325430303a30303a30305a270a6d656d6f72793a0a202063"
    "7573746f6d3a207b7d0a202066616374733a0a20202d2069643a20610a202020207072"
    "696f726974793a20686967680a20202020746578743a20616c7068610a202020207469"
    "6d657374616d703a2027323032362d30312d30315430303a30303a30305a270a20202d"
    "20626574610a20206b3a20760a2020707265666572656e6365733a207b7d0a20207365"
    "7373696f6e733a0a20202d2069643a2073310a202020206e3a20310a6e616d65706f69"
    "6e743a20274077697265270a70726f66696c653a206b6e6f776c656467650a72657465"
    "6e74696f6e3a20666f72657665720a76657273696f6e3a2027312e31270a"
)
GOLDEN = bytes.fromhex(GOLDEN_HEX)


def test_wire_seal_is_byte_identical_to_golden():
    assert to_packet(_wire_soul()) == GOLDEN


def test_wire_golden_opens_to_the_soul():
    from claude_fafm_sdk.merge import souls_equal

    assert souls_equal(from_packet(GOLDEN), _wire_soul())


def test_wire_header_fields():
    magic, version, flags, _crc, length = struct.unpack("<4sHHII", GOLDEN[:HEADER_SIZE])
    assert magic == MAGIC == b"SPK1"
    assert version == VERSION == 1
    assert flags == 0
    assert length == len(GOLDEN) - HEADER_SIZE


def test_wire_crc_is_payload_only():
    # the contract a second language must match: CRC-32 over payload bytes only,
    # NEVER the header.
    _, _, _, crc, _ = struct.unpack("<4sHHII", GOLDEN[:HEADER_SIZE])
    payload = GOLDEN[HEADER_SIZE:]
    assert crc == (binascii.crc32(payload) & 0xFFFFFFFF)
    # CRC of the WHOLE packet is different — proves it's payload-only, not all-bytes
    assert crc != (binascii.crc32(GOLDEN) & 0xFFFFFFFF)
