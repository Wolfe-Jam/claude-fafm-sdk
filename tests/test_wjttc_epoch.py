"""WJTTC — Epoch E1 (MERGE §11 slice, 2.0 prep).

Hand-authored goldens for epoch wire + same-epoch merge + cross-epoch refuse.
Compact / CompactionReceipt / full Z3–Z8 (post-compact packet) come with compact_epoch.

Discipline: hold **every** merge implementation (sdk + reference) to the same
refuse/outcome — dual-impl bar for E1 (MERGE §11.8 Z2).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pytest
import reference_merge

from claude_fafm_sdk import EpochMismatch, Soul, merge_souls
from claude_fafm_sdk.merge import logical_state
from claude_fafm_sdk.merge import merge_souls as sdk_merge
from claude_fafm_sdk.merge import souls_equal as sdk_equal
from claude_fafm_sdk.packet import from_packet, merge_packet, normalize_for_seal, to_packet
from claude_fafm_sdk.soul import Fact

NP = "@epoch"
T1 = "2026-07-01T00:00:00Z"
T2 = "2026-07-02T00:00:00Z"

_IMPLS = {"sdk": sdk_merge}
if getattr(reference_merge, "IMPLEMENTED", False):
    _IMPLS["reference"] = reference_merge.merge_souls


def _s(*facts: Fact, epoch: int = 0, name: str = NP) -> Soul:
    s = Soul(name, created=T1, epoch=epoch)
    s.last_etched = T1
    for f in facts:
        s.add(f)
    return s


def _ids(soul: Soul) -> set[str | None]:
    return {f.id for f in soul.facts}


# ── Wire / load / save ───────────────────────────────────────────────────────


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
        "created": T1,
        "last_etched": T1,
        "retention": "forever",
        "index": [],
        "memory": {
            "facts": [{"text": "hi", "id": "x", "timestamp": T1}],
            "sessions": [],
            "preferences": {},
            "custom": {},
        },
    }
    s = Soul.from_doc(doc)
    assert s.epoch == 0
    assert "epoch" not in doc
    assert s.to_doc()["epoch"] == 0  # writers always emit


def test_epoch_roundtrip_nonzero():
    s = _s(Fact(text="a", id="a", timestamp=T1), epoch=3)
    s2 = Soul.from_doc(s.to_doc())
    assert s2.epoch == 3
    assert s2.to_doc()["epoch"] == 3


def test_epoch_not_in_memory_extra():
    s = _s(Fact(text="a", id="a", timestamp=T1), epoch=2)
    doc = s.to_doc()
    assert "epoch" in doc and "epoch" not in (doc.get("memory") or {})
    s2 = Soul.from_doc(doc)
    assert "epoch" not in s2.memory_extra
    assert s2.epoch == 2


def test_epoch_rejects_negative_on_construct():
    with pytest.raises(ValueError, match="epoch"):
        Soul("@e", epoch=-1)


def test_epoch_rejects_negative_on_setter():
    s = Soul("@e")
    with pytest.raises(ValueError, match="epoch"):
        s.epoch = -1


def test_epoch_coerces_string_wire():
    doc = _s(Fact(text="a", id="a", timestamp=T1), epoch=0).to_doc()
    doc["epoch"] = "4"
    s = Soul.from_doc(doc)
    assert s.epoch == 4


def test_epoch_garbage_wire_falls_back_zero():
    doc = _s(Fact(text="a", id="a", timestamp=T1), epoch=0).to_doc()
    doc["epoch"] = "nope"
    s = Soul.from_doc(doc)
    assert s.epoch == 0


# ── Same-epoch merge (E1 pass path) ──────────────────────────────────────────


def test_same_epoch_merge_ok_all_impls():
    a = _s(Fact(text="alpha", id="x", timestamp=T1), epoch=0)
    b = _s(Fact(text="beta", id="y", timestamp=T1), epoch=0)
    for name, merge in _IMPLS.items():
        m = merge(a, b)
        assert m.epoch == 0, name
        assert _ids(m) == {"x", "y"}, name


def test_same_nonzero_epoch_merge_ok_all_impls():
    a = _s(Fact(text="alpha", id="x", timestamp=T1), epoch=5)
    b = _s(Fact(text="beta", id="y", timestamp=T1), epoch=5)
    for name, merge in _IMPLS.items():
        m = merge(a, b)
        assert m.epoch == 5, name
        assert _ids(m) == {"x", "y"}, name


def test_same_epoch_merge_commutative_all_impls():
    a = _s(Fact(text="alpha", id="x", timestamp=T1), epoch=0)
    b = _s(Fact(text="beta", id="y", timestamp=T1), epoch=0)
    for name, merge in _IMPLS.items():
        assert sdk_equal(merge(a, b), merge(b, a)), name


def test_same_epoch_merge_idempotent_all_impls():
    a = _s(Fact(text="alpha", id="x", timestamp=T1), epoch=2)
    b = _s(Fact(text="beta", id="y", timestamp=T1), epoch=2)
    for name, merge in _IMPLS.items():
        m = merge(a, b)
        assert sdk_equal(merge(m, m), m), name
        assert sdk_equal(merge(m, b), m), name


def test_z1_same_epoch_forget_still_converges_all_impls():
    """Z1 lite: tombstones still work inside a fixed epoch."""
    a = _s(
        Fact(text="alpha", id="x", timestamp=T1),
        Fact(text="beta", id="y", timestamp=T1),
        epoch=0,
    )
    a.forget("y", deleted_at=T2)
    b = _s(
        Fact(text="alpha", id="x", timestamp=T1),
        Fact(text="beta", id="y", timestamp=T1),
        epoch=0,
    )
    for name, merge in _IMPLS.items():
        m = merge(a, b)
        assert m.epoch == 0, name
        assert ("id", "y") in m.tombstones, name
        assert "y" not in _ids(m), name
        assert "x" in _ids(m), name


# ── Cross-epoch refuse (Z2) ──────────────────────────────────────────────────


def test_z2_cross_epoch_refuse_all_impls():
    a = _s(Fact(text="alpha", id="x", timestamp=T1), epoch=0)
    b = _s(Fact(text="beta", id="y", timestamp=T1), epoch=1)
    for name, merge in _IMPLS.items():
        with pytest.raises(EpochMismatch) as ei:
            merge(a, b)
        assert ei.value.epoch_a == 0 and ei.value.epoch_b == 1, name
        # no fact bleed into either side
        assert _ids(a) == {"x"}, name
        assert _ids(b) == {"y"}, name


def test_z2_refuse_is_order_independent_message():
    """Both directions refuse; attributes reflect the call order (a, b)."""
    a = _s(Fact(text="alpha", id="x", timestamp=T1), epoch=0)
    b = _s(Fact(text="beta", id="y", timestamp=T1), epoch=1)
    with pytest.raises(EpochMismatch) as e_ab:
        merge_souls(a, b)
    with pytest.raises(EpochMismatch) as e_ba:
        merge_souls(b, a)
    assert (e_ab.value.epoch_a, e_ab.value.epoch_b) == (0, 1)
    assert (e_ba.value.epoch_a, e_ba.value.epoch_b) == (1, 0)


def test_z2_large_epoch_gap_refuses():
    a = _s(Fact(text="alpha", id="x", timestamp=T1), epoch=0)
    b = _s(Fact(text="beta", id="y", timestamp=T1), epoch=99)
    with pytest.raises(EpochMismatch) as ei:
        merge_souls(a, b)
    assert ei.value.epoch_b == 99


def test_z2_epoch_mismatch_is_value_error():
    a = _s(Fact(text="a", id="a", timestamp=T1), epoch=0)
    b = _s(Fact(text="b", id="b", timestamp=T1), epoch=1)
    with pytest.raises(ValueError):
        merge_souls(a, b)


def test_namepoint_mismatch_still_checked_before_or_with_epoch():
    """Different namepoints still fail (existing law); not swallowed by epoch."""
    a = _s(Fact(text="a", id="a", timestamp=T1), epoch=0, name="@one")
    b = _s(Fact(text="b", id="b", timestamp=T1), epoch=0, name="@two")
    with pytest.raises(ValueError, match="namepoint"):
        merge_souls(a, b)


# ── Packet / seal ────────────────────────────────────────────────────────────


def test_seal_carries_epoch():
    s = _s(Fact(text="alpha", id="x", timestamp=T1), epoch=2)
    reopened = from_packet(to_packet(s))
    assert reopened.epoch == 2
    assert sdk_equal(reopened, s) or (
        reopened.epoch == s.epoch and _ids(reopened) == _ids(s)
    )


def test_normalize_for_seal_preserves_epoch():
    s = _s(Fact(text="alpha", id="x", timestamp=T1), epoch=7)
    n = normalize_for_seal(s)
    assert n.epoch == 7


def test_packet_same_epoch_merge():
    a = _s(Fact(text="alpha", id="x", timestamp=T1), epoch=0)
    b = _s(Fact(text="beta", id="y", timestamp=T1), epoch=0)
    m = merge_packet(b, to_packet(a))
    assert m.epoch == 0
    assert _ids(m) == {"x", "y"}


def test_z2_packet_cross_epoch_refuse():
    a = _s(Fact(text="alpha", id="x", timestamp=T1), epoch=0)
    b = _s(Fact(text="beta", id="y", timestamp=T1), epoch=1)
    with pytest.raises(EpochMismatch):
        merge_packet(b, to_packet(a))
    assert _ids(b) == {"y"}  # local untouched


def test_packet_roundtrip_epoch_zero_default_soul():
    s = _s(Fact(text="alpha", id="x", timestamp=T1), epoch=0)
    assert from_packet(to_packet(s)).epoch == 0


# ── Logical state ────────────────────────────────────────────────────────────


def test_logical_state_includes_epoch():
    s0 = _s(Fact(text="a", id="a", timestamp=T1), epoch=0)
    s1 = _s(Fact(text="a", id="a", timestamp=T1), epoch=1)
    assert logical_state(s0)["epoch"] == 0
    assert logical_state(s1)["epoch"] == 1
    assert logical_state(s0) != logical_state(s1)


def test_logical_state_same_epoch_equal_facts():
    a = _s(Fact(text="a", id="a", timestamp=T1), epoch=3)
    b = Soul.from_doc(a.to_doc())
    assert logical_state(a) == logical_state(b)


# ── Dual-impl agreement on refuse ────────────────────────────────────────────


def test_dual_impl_agree_on_refuse_and_success():
    """Both impls succeed same-epoch and refuse cross-epoch the same way."""
    assert "sdk" in _IMPLS and "reference" in _IMPLS
    a0 = _s(Fact(text="alpha", id="x", timestamp=T1), epoch=0)
    b0 = _s(Fact(text="beta", id="y", timestamp=T1), epoch=0)
    b1 = _s(Fact(text="beta", id="y", timestamp=T1), epoch=1)

    m_sdk = _IMPLS["sdk"](a0, b0)
    m_ref = _IMPLS["reference"](a0, b0)
    assert _ids(m_sdk) == _ids(m_ref) == {"x", "y"}
    assert m_sdk.epoch == m_ref.epoch == 0

    for merge in _IMPLS.values():
        with pytest.raises(EpochMismatch):
            merge(a0, b1)


# ── Compact (E3) + Z3–Z8 ────────────────────────────────────────────────────


def test_z4_compact_projection_and_empty_tombstones():
    from claude_fafm_sdk import compact_epoch

    s = _s(
        Fact(text="alpha", id="x", timestamp=T1),
        Fact(text="beta", id="y", timestamp=T1),
        epoch=0,
    )
    s.forget("y", deleted_at=T2)
    # live fact still present under tombstone (stale re-add corner optional)
    new, receipt = compact_epoch(s, at=T2, actor="test")
    assert receipt.from_epoch == 0 and receipt.to_epoch == 1
    assert receipt.tombstones_before == 1
    assert receipt.facts_after == 1
    assert new.epoch == 1
    assert new.tombstones == {}
    assert _ids(new) == {"x"}
    assert len(new.compaction_receipts) == 1
    # original unchanged
    assert s.epoch == 0
    assert ("id", "y") in s.tombstones


def test_z5_compact_deterministic():
    from claude_fafm_sdk import compact_epoch
    from claude_fafm_sdk.merge import logical_state

    s = _s(
        Fact(text="alpha", id="x", timestamp=T1),
        Fact(text="beta", id="y", timestamp=T1),
        epoch=0,
    )
    s.forget("y", deleted_at=T2)
    n1, r1 = compact_epoch(s, at=T2, actor="test")
    n2, r2 = compact_epoch(s, at=T2, actor="test")
    assert logical_state(n1) == logical_state(n2)
    assert r1.to_wire() == r2.to_wire()


def test_z3_packet_pre_forget_post_compact_refuses():
    """Packet sealed at epoch 0 (with forgotten fact still on peer) vs local epoch 1."""
    from claude_fafm_sdk import compact_epoch

    # peer still has y (never forgot) — sealed at epoch 0
    peer = _s(
        Fact(text="alpha", id="x", timestamp=T1),
        Fact(text="beta", id="y", timestamp=T1),
        epoch=0,
    )
    pkt = to_packet(peer)

    local = _s(
        Fact(text="alpha", id="x", timestamp=T1),
        Fact(text="beta", id="y", timestamp=T1),
        epoch=0,
    )
    local.forget("y", deleted_at=T2)
    local2, _ = compact_epoch(local, at=T2, actor="test")
    assert local2.epoch == 1
    assert "y" not in _ids(local2)

    with pytest.raises(EpochMismatch):
        merge_packet(local2, pkt)
    # forgotten stays forgotten in local lineage
    assert "y" not in _ids(local2)


def test_z2_post_compact_vs_pre_compact_soul_refuses():
    from claude_fafm_sdk import compact_epoch

    a = _s(Fact(text="alpha", id="x", timestamp=T1), epoch=0)
    a.forget("x", deleted_at=T2)
    b = _s(Fact(text="alpha", id="x", timestamp=T1), epoch=0)
    a1, _ = compact_epoch(a, at=T2)
    with pytest.raises(EpochMismatch):
        merge_souls(a1, b)


def test_z6_dual_transport_same_e1_after_compact():
    from claude_fafm_sdk import compact_epoch

    a = _s(Fact(text="a", id="a", timestamp=T1), epoch=0)
    b = _s(Fact(text="b", id="b", timestamp=T1), epoch=0)
    a1, _ = compact_epoch(a, at=T2)
    # packet of epoch-0 b into a1 refuses
    with pytest.raises(EpochMismatch):
        merge_packet(a1, to_packet(b))
    # merge_souls same refuse
    with pytest.raises(EpochMismatch):
        merge_souls(a1, b)


def test_z8_same_epoch_post_compact_peers_merge():
    from claude_fafm_sdk import compact_epoch

    a = _s(Fact(text="a", id="a", timestamp=T1), epoch=0)
    b = _s(Fact(text="b", id="b", timestamp=T1), epoch=0)
    a1, _ = compact_epoch(a, at=T2, actor="t")
    b1, _ = compact_epoch(b, at=T2, actor="t")
    assert a1.epoch == b1.epoch == 1
    m = merge_souls(a1, b1)
    assert m.epoch == 1
    assert _ids(m) == {"a", "b"}
    # dual-impl
    m2 = reference_merge.merge_souls(a1, b1)
    assert _ids(m2) == {"a", "b"}


def test_compact_requires_at():
    from claude_fafm_sdk import compact_epoch

    s = _s(Fact(text="a", id="a", timestamp=T1), epoch=0)
    with pytest.raises(ValueError, match="at"):
        compact_epoch(s, at="")


def test_compact_receipt_on_wire():
    from claude_fafm_sdk import compact_epoch

    s = _s(Fact(text="a", id="a", timestamp=T1), epoch=0)
    s.forget("a", deleted_at=T2)
    new, _ = compact_epoch(s, at=T2, actor="unit", archive_ref="arch.fafm")
    doc = new.to_doc()
    assert "compaction_receipts" in doc["memory"]
    r = doc["memory"]["compaction_receipts"][0]
    assert r["from_epoch"] == 0 and r["to_epoch"] == 1
    assert r["archive_ref"] == "arch.fafm"
    loaded = Soul.from_doc(doc)
    assert len(loaded.compaction_receipts) == 1


def test_re_etch_after_compact():
    from claude_fafm_sdk import compact_epoch

    s = _s(Fact(text="a", id="a", timestamp=T1), epoch=0)
    s.forget("a", deleted_at=T2)
    new, _ = compact_epoch(s, at=T2)
    new.add(Fact(text="a revived", id="a", timestamp="2026-07-03T00:00:00Z"))
    assert any(f.id == "a" and "revived" in f.text for f in new.facts)


def test_migrate_project_live():
    from claude_fafm_sdk import migrate_epoch

    s = _s(
        Fact(text="a", id="a", timestamp=T1),
        Fact(text="b", id="b", timestamp=T1),
        epoch=0,
    )
    s.forget("b", deleted_at=T2)
    m = migrate_epoch(s, 5, mode="project-live", at=T2)
    assert m.epoch == 5
    assert _ids(m) == {"a"}
    assert m.tombstones == {}


# ── Dual-impl compact / migrate projection (MERGE §11.8 dual-impl bar) ───────


def _fact_projection(soul: Soul) -> set[tuple]:
    """Comparable live fact set for dual-impl (id, text, ts, priority)."""
    return {
        (f.id, f.text, f.timestamp or "", f.priority)
        for f in soul.facts
    }


def test_dual_impl_compact_projection_agrees():
    """SDK compact_epoch and reference compact_epoch project the same live set."""
    from claude_fafm_sdk import compact_epoch as sdk_compact

    s = _s(
        Fact(text="alpha", id="a", timestamp=T1, priority="high"),
        Fact(text="beta", id="b", timestamp=T1),
        Fact(text="gamma id-less", timestamp=T1),
        epoch=0,
    )
    s.forget("b", deleted_at=T2)
    s.forget_text("gamma id-less", deleted_at=T2)

    # same actor/archive so receipt identity matches under both oracles
    sdk_new, sdk_r = sdk_compact(s, at=T2, actor="dual", archive_ref="a.fafm")
    ref_new, ref_r = reference_merge.compact_epoch(
        s, at=T2, actor="dual", archive_ref="a.fafm"
    )

    assert sdk_new.epoch == ref_new.epoch == 1
    assert sdk_new.tombstones == {} and ref_new.tombstones == {}
    assert _fact_projection(sdk_new) == _fact_projection(ref_new)
    assert _ids(sdk_new) == {"a"}
    assert sdk_r.from_epoch == ref_r.from_epoch == 0
    assert sdk_r.to_epoch == ref_r.to_epoch == 1
    assert sdk_r.tombstones_before == ref_r.tombstones_before == 2
    assert sdk_r.facts_before == ref_r.facts_before
    assert sdk_r.facts_after == ref_r.facts_after == len(sdk_new.facts)
    # logical equality (sdk oracle includes receipts; same inputs → match)
    assert sdk_equal(sdk_new, ref_new)
    # reference oracle: projection + epoch + empty graveyard
    assert reference_merge.souls_equal(sdk_new, ref_new)


def test_dual_impl_compact_deterministic_across_impls():
    from claude_fafm_sdk import compact_epoch as sdk_compact

    s = _s(
        Fact(text="x", id="x", timestamp=T1),
        Fact(text="y", id="y", timestamp=T1),
        epoch=2,
    )
    s.forget("y", deleted_at=T2)
    a1, _ = sdk_compact(s, at=T2, actor="t")
    a2, _ = sdk_compact(s, at=T2, actor="t")
    b1, _ = reference_merge.compact_epoch(s, at=T2, actor="t")
    b2, _ = reference_merge.compact_epoch(s, at=T2, actor="t")
    assert _fact_projection(a1) == _fact_projection(a2) == _fact_projection(b1) == _fact_projection(b2)
    assert a1.epoch == b1.epoch == 3


def test_dual_impl_migrate_project_live_agrees():
    from claude_fafm_sdk import migrate_epoch as sdk_migrate

    s = _s(
        Fact(text="a", id="a", timestamp=T1),
        Fact(text="b", id="b", timestamp=T1),
        epoch=0,
    )
    s.forget("b", deleted_at=T2)
    m_sdk = sdk_migrate(s, 5, mode="project-live", at=T2)
    m_ref = reference_merge.migrate_epoch(s, 5, mode="project-live", at=T2)
    assert m_sdk.epoch == m_ref.epoch == 5
    assert m_sdk.tombstones == m_ref.tombstones == {}
    assert _fact_projection(m_sdk) == _fact_projection(m_ref)
    assert _ids(m_sdk) == _ids(m_ref) == {"a"}
    assert sdk_equal(m_sdk, m_ref)
    assert reference_merge.souls_equal(m_sdk, m_ref)


def test_dual_impl_migrate_refuse_agrees():
    from claude_fafm_sdk import migrate_epoch as sdk_migrate

    s = _s(Fact(text="a", id="a", timestamp=T1), epoch=1)
    # same epoch — both return source
    assert sdk_migrate(s, 1, mode="refuse") is s or sdk_migrate(s, 1, mode="refuse").epoch == 1
    assert reference_merge.migrate_epoch(s, 1, mode="refuse").epoch == 1
    with pytest.raises(EpochMismatch):
        sdk_migrate(s, 2, mode="refuse")
    with pytest.raises(EpochMismatch):
        reference_merge.migrate_epoch(s, 2, mode="refuse")
