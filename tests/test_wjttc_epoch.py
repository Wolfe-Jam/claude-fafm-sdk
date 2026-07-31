"""Epoch-only slice of MERGE §11 (2.0 prep) — E1 refuse + wire default 0.

Compact / CompactionReceipt / Z3–Z8 full suite come with compact_epoch.
This file gates: load/save epoch · same-epoch merge · cross-epoch refuse · packet E1.
"""

from __future__ import annotations

import pytest

from claude_fafm_sdk import EpochMismatch, Soul, merge_souls
from claude_fafm_sdk.packet import merge_packet, to_packet
from claude_fafm_sdk.soul import Fact
from tests import reference_merge as ref


def _s(*facts: Fact, epoch: int = 0, name: str = "@epoch") -> Soul:
    s = Soul(name, created="2026-07-01T00:00:00Z", epoch=epoch)
    s.last_etched = "2026-07-01T00:00:00Z"
    for f in facts:
        s.add(f)
    return s


def test_epoch_default_zero():
    s = Soul("@e")
    assert s.epoch == 0
    assert s.to_doc()["epoch"] == 0


def test_epoch_absent_wire_loads_as_zero():
    """Pre-2.0 souls without epoch key ≡ 0 (INTEROP §14)."""
    doc = {
        "version": "1.1",
        "profile": "knowledge",
        "namepoint": "@old",
        "created": "2026-01-01T00:00:00Z",
        "last_etched": "2026-01-01T00:00:00Z",
        "retention": "forever",
        "index": [],
        "memory": {"facts": [{"text": "hi", "id": "x"}], "sessions": [], "preferences": {}, "custom": {}},
    }
    s = Soul.from_doc(doc)
    assert s.epoch == 0
    assert "epoch" not in doc  # wire had no key
    assert s.to_doc()["epoch"] == 0  # writers always emit


def test_epoch_roundtrip():
    s = _s(Fact(text="a", id="a", timestamp="2026-07-01T00:00:00Z"), epoch=3)
    s2 = Soul.from_doc(s.to_doc())
    assert s2.epoch == 3


def test_same_epoch_merge_ok_both_impls():
    a = _s(Fact(text="alpha", id="x", timestamp="2026-07-01T00:00:00Z"), epoch=0)
    b = _s(Fact(text="beta", id="y", timestamp="2026-07-01T00:00:00Z"), epoch=0)
    m = merge_souls(a, b)
    assert m.epoch == 0
    ids = {f.id for f in m.facts}
    assert ids == {"x", "y"}
    m2 = ref.merge_souls(a, b)
    assert m2.epoch == 0
    assert {f.id for f in m2.facts} == {"x", "y"}


def test_z2_cross_epoch_refuse_sdk():
    a = _s(Fact(text="alpha", id="x", timestamp="2026-07-01T00:00:00Z"), epoch=0)
    b = _s(Fact(text="beta", id="y", timestamp="2026-07-01T00:00:00Z"), epoch=1)
    with pytest.raises(EpochMismatch) as ei:
        merge_souls(a, b)
    assert ei.value.epoch_a == 0 and ei.value.epoch_b == 1
    # no fact bleed — a unchanged
    assert {f.id for f in a.facts} == {"x"}


def test_z2_cross_epoch_refuse_reference():
    a = _s(Fact(text="alpha", id="x", timestamp="2026-07-01T00:00:00Z"), epoch=0)
    b = _s(Fact(text="beta", id="y", timestamp="2026-07-01T00:00:00Z"), epoch=1)
    with pytest.raises(EpochMismatch):
        ref.merge_souls(a, b)


def test_packet_same_epoch_merge():
    a = _s(Fact(text="alpha", id="x", timestamp="2026-07-01T00:00:00Z"), epoch=0)
    b = _s(Fact(text="beta", id="y", timestamp="2026-07-01T00:00:00Z"), epoch=0)
    pkt = to_packet(a)
    m = merge_packet(b, pkt)
    assert m.epoch == 0
    assert {f.id for f in m.facts} == {"x", "y"}


def test_z2_packet_cross_epoch_refuse():
    a = _s(Fact(text="alpha", id="x", timestamp="2026-07-01T00:00:00Z"), epoch=0)
    b = _s(Fact(text="beta", id="y", timestamp="2026-07-01T00:00:00Z"), epoch=1)
    pkt = to_packet(a)
    with pytest.raises(EpochMismatch):
        merge_packet(b, pkt)


def test_seal_carries_epoch():
    s = _s(Fact(text="alpha", id="x", timestamp="2026-07-01T00:00:00Z"), epoch=2)
    from claude_fafm_sdk.packet import from_packet

    reopened = from_packet(to_packet(s))
    assert reopened.epoch == 2
