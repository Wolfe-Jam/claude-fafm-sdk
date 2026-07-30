"""1.7 Debt + residual-risk — TESTING.md gates."""

from __future__ import annotations

from pathlib import Path

import pytest

from claude_fafm_sdk import Soul, debt, risk_scan
from claude_fafm_sdk.packet import to_packet_file
from claude_fafm_sdk.soul import Fact


AT = "2026-07-30T12:00:00Z"
OLD = "2026-06-01T00:00:00Z"
MID = "2026-07-20T00:00:00Z"


def _soul_with_stones() -> Soul:
    s = Soul("@debt", created=OLD)
    s.add(Fact(text="a", id="a", timestamp=OLD))
    s.add(Fact(text="b", id="b", timestamp=OLD))
    s.forget("a", deleted_at=OLD)
    s.forget("b", deleted_at=MID)
    return s


def test_debt_count_matches_tombstones():
    s = _soul_with_stones()
    r = s.debt()
    assert r.count == 2
    assert r.count == len(s.tombstones)
    assert r.bytes > 0
    assert r.oldest == OLD
    assert r.newest == MID


def test_debt_does_not_mutate():
    s = _soul_with_stones()
    before = dict(s.tombstones)
    s.debt(at=AT, purge_eligible_after="7d")
    assert s.tombstones == before


def test_purge_eligible_mark_only():
    s = _soul_with_stones()
    # at AT, 10d window: OLD is eligible, MID (10 days before AT) is on the edge
    r = debt(s, at=AT, purge_eligible_after="15d")
    assert r.purge_eligible_count >= 1  # at least OLD
    assert r.count == 2  # nothing dropped
    assert ("id", "a") in s.tombstones
    assert ("id", "b") in s.tombstones


def test_debt_empty_soul():
    s = Soul("@empty")
    r = s.debt()
    assert r.count == 0
    assert r.bytes == 0
    assert r.oldest is None
    assert r.purge_eligible_count == 0


def test_risk_scan_requires_paths():
    with pytest.raises(ValueError, match="explicit paths"):
        risk_scan([])


def test_risk_scan_finds_fixture_soul_and_packet(tmp_path: Path):
    soul_path = tmp_path / "soul.fafm"
    pkt_path = tmp_path / "out.fafmp"
    s = _soul_with_stones()
    s.save(soul_path)
    to_packet_file(s, pkt_path)

    report = risk_scan([tmp_path])
    kinds = {h.kind for h in report.hits}
    paths = {h.path for h in report.hits}
    assert "soul" in kinds
    assert "packet" in kinds
    assert any(p.endswith("soul.fafm") for p in paths)
    assert any(p.endswith(".fafmp") for p in paths)
    assert "not a wipe" in report.note.lower() or "not" in report.note.lower()
    assert "RTBF" in report.note or "rtbf" in report.note.lower() or "legal" in report.note.lower()


def test_risk_scan_explicit_file(tmp_path: Path):
    p = tmp_path / "copy.fafm"
    Soul("@x").save(p)
    report = risk_scan([p])
    assert report.count == 1
    assert report.hits[0].kind == "soul"
