"""1.6 Policy → tombstone — INTEROP §13 goldens."""

from __future__ import annotations

import pytest

from claude_fafm_sdk import Soul, merge_souls
from claude_fafm_sdk.packet import merge_packet, to_packet
from claude_fafm_sdk.policy import Policy, apply_policies, merge_policies
from claude_fafm_sdk.soul import Fact, txt_hash


AT = "2026-07-30T12:00:00Z"
OLDER = "2026-07-01T00:00:00Z"
NEWER = "2026-07-30T18:00:00Z"


def _soul() -> Soul:
    s = Soul("@policy-test", created=OLDER)
    s.last_etched = OLDER
    return s


def _add(
    s: Soul,
    text: str,
    *,
    id: str | None = None,
    priority: str = "standard",
    tags: list[str] | None = None,
    timestamp: str = OLDER,
) -> Fact:
    return s.add(
        Fact(
            text=text,
            id=id,
            priority=priority,
            tags=list(tags or []),
            timestamp=timestamp,
        )
    )


def test_empty_policies_omitted_from_doc_seal_identity():
    s = _soul()
    _add(s, "hello", id="h")
    doc = s.to_doc()
    assert "policies" not in doc["memory"]
    assert "policy_auto" not in doc["memory"]
    # roundtrip
    s2 = Soul.from_doc(doc)
    assert s2.policies == []
    assert s2.policy_auto is False


def test_policy_load_save_first_class():
    s = _soul()
    s.set_policy("ttl-eph", {"priority_lte": "ephemeral", "max_age": "7d"}, updated_at=AT)
    s.policy_auto = False
    doc = s.to_doc()
    assert "policies" in doc["memory"]
    assert doc["memory"]["policies"][0]["id"] == "ttl-eph"
    s2 = Soul.from_doc(doc)
    assert len(s2.policies) == 1
    assert s2.policies[0].when["max_age"] == "7d"


def test_propose_priority_lte():
    s = _soul()
    _add(s, "noise", id="n1", priority="ephemeral")
    _add(s, "keep", id="k1", priority="high")
    s.set_policy("drop-eph", {"priority_lte": "ephemeral"}, updated_at=AT)
    hits = s.propose_policies(at=AT)
    ids = {h.key for h in hits}
    assert ids == {"n1"}


def test_propose_max_age():
    s = _soul()
    _add(s, "old", id="old", timestamp=OLDER)
    _add(s, "fresh", id="fresh", timestamp=AT)
    s.set_policy("age", {"max_age": "7d"}, updated_at=AT)
    hits = s.propose_policies(at=AT)
    assert {h.key for h in hits} == {"old"}


def test_propose_tag_and_id_less_text():
    s = _soul()
    _add(s, "tagged", id="t1", tags=["tmp"])
    _add(s, "plain id-less fact")  # id-less
    s.set_policy("by-tag", {"tag": "tmp"}, updated_at=AT)
    s.set_policy("by-text", {"text": "plain id-less fact"}, updated_at=AT)
    hits = s.propose_policies(at=AT)
    kinds = {(h.kind, h.key) for h in hits}
    assert ("id", "t1") in kinds
    assert ("txt", txt_hash("plain id-less fact")) in kinds


def test_apply_requires_at_and_writes_tombstones():
    s = _soul()
    _add(s, "gone", id="g1", priority="ephemeral")
    s.set_policy("p", {"priority_lte": "ephemeral"}, updated_at=AT)
    with pytest.raises(ValueError, match="at="):
        apply_policies(s, at="")
    hits = s.apply_policies(at=AT)
    assert len(hits) == 1
    assert ("id", "g1") in s.tombstones
    assert s.tombstones[("id", "g1")] == AT
    assert all(f.id != "g1" for f in s.facts)


def test_t2_re_etch_after_policy_forget():
    """Re-etch with ts > deleted_at beats the tombstone (MERGE T2)."""
    s = _soul()
    _add(s, "x", id="x", priority="ephemeral")
    s.set_policy("p", {"id": "x"}, updated_at=AT)
    s.apply_policies(at=AT)
    assert ("id", "x") in s.tombstones
    _add(s, "x revived", id="x", priority="high", timestamp=NEWER)
    live = [f for f in s.facts if f.id == "x"]
    assert len(live) == 1
    assert live[0].text == "x revived"
    # merge with self still keeps re-etch
    m = merge_souls(s, s)
    assert any(f.id == "x" and f.text == "x revived" for f in m.facts)


def test_merge_policies_lww_by_id():
    a = Policy(id="p1", when={"tag": "a"}, updated_at="2026-07-01T00:00:00Z")
    b = Policy(id="p1", when={"tag": "b"}, updated_at="2026-07-30T00:00:00Z")
    c = Policy(id="p2", when={"tag": "c"}, updated_at=AT)
    merged = merge_policies([a, c], [b])
    by = {p.id: p for p in merged}
    assert by["p1"].when["tag"] == "b"
    assert "p2" in by


def test_merge_souls_carries_policies_not_suppress():
    """Policies travel on merge; only tombstones suppress facts."""
    a = _soul()
    _add(a, "live", id="L")
    a.set_policy("p", {"id": "L"}, updated_at=AT)
    b = _soul()
    _add(b, "live", id="L")
    m = merge_souls(a, b)
    assert any(f.id == "L" for f in m.facts)  # not applied yet
    assert len(m.policies) == 1
    m.apply_policies(at=AT)
    assert ("id", "L") in m.tombstones


def test_packet_both_road_policy_emitted_tombstones():
    a = _soul()
    _add(a, "secret", id="sec", priority="ephemeral")
    a.set_policy("p", {"priority_lte": "ephemeral"}, updated_at=AT)
    a.apply_policies(at=AT)
    pkt = to_packet(a)
    b = _soul()
    _add(b, "secret", id="sec", priority="ephemeral")
    m = merge_packet(b, pkt)
    assert ("id", "sec") in m.tombstones
    assert all(f.id != "sec" for f in m.facts)


def test_policies_not_in_memory_extra():
    s = _soul()
    s.set_policy("p", {"tag": "x"}, updated_at=AT)
    doc = s.to_doc()
    # residual path must not also hold policies
    s2 = Soul.from_doc(doc)
    assert "policies" not in s2.memory_extra
    assert len(s2.policies) == 1
