"""WJTTC — `.fafm` v1.2 alignment (spec ``Wolfe-Jam/faf`` @ ``0277dc2``).

Four gaps, one section each:

1. §8.1 tombstones compare INSTANTS, not strings (suppression + join), in every copy.
2. §10 the writer emits ``version: "1.2"`` and never a lower version than it read.
3. §10 an unknown ``priority`` is preserved; only the §6.1 legacy mapping applies.
4. §8.1 ``normalize_text`` strips exactly the pinned 29-code-point set after NFC.
"""
from __future__ import annotations

import sys
import unicodedata

import pytest
import reference_merge as ref
import yaml

from claude_fafm_sdk import merge as m
from claude_fafm_sdk import soul as s
from claude_fafm_sdk.compact import compact_epoch
from claude_fafm_sdk.soul import Fact, Soul

NP = "@v12"

# ═══ 1. Tombstones by instant (§8.1) ═══════════════════════════════════════════

# (fact timestamp, tombstone deleted_at, suppressed?)
CASES = [
    # measured wrong in 2.1.0: 12:00+05:00 is 07:00Z — before the 09:00Z delete.
    pytest.param("2026-11-01T12:00:00+05:00", "2026-11-01T09:00:00Z", True, id="offset-+05:00"),
    # measured wrong in 2.1.0: the delete is half a second after the fact.
    pytest.param("2026-11-01T09:00:00Z", "2026-11-01T09:00:00.5Z", True, id="fractional-delete"),
    pytest.param("2026-11-01T09:00:00Z", "2026-11-01T09:00:00Z", True, id="tie-same-string"),
    pytest.param("2026-11-01T14:00:00+05:00", "2026-11-01T09:00:00Z", True, id="tie-same-instant"),
    pytest.param("2026-11-01T09:00:00.000Z", "2026-11-01T09:00:00Z", True, id="tie-trailing-zeros"),
    pytest.param(None, "2026-11-01T09:00:00Z", True, id="missing-timestamp"),
    pytest.param("", "2026-11-01T09:00:00Z", True, id="empty-timestamp"),
    pytest.param("2026-11-01T09:00:01Z", "2026-11-01T09:00:00Z", False, id="later-re-etch"),
    pytest.param("2026-11-01T09:00:00.6Z", "2026-11-01T09:00:00.5Z", False, id="later-fractional"),
    pytest.param("2026-11-01T14:30:00+05:00", "2026-11-01T09:00:00Z", False, id="later-+05:00"),
    pytest.param("2026-11-01T04:00:01-05:00", "2026-11-01T09:00:00Z", False, id="later--05:00"),
]

_SUPPRESSORS = {"merge": m._is_suppressed, "reference": ref._suppressed_by}


@pytest.mark.parametrize("impl", sorted(_SUPPRESSORS))
@pytest.mark.parametrize(("ts", "deleted_at", "suppressed"), CASES)
def test_suppression_is_by_instant(impl, ts, deleted_at, suppressed):
    by_id = Fact(text="x", id="x", timestamp=ts)
    by_txt = Fact(text="y", timestamp=ts)
    tombs = {("id", "x"): deleted_at, ("txt", s.txt_hash("y")): deleted_at}
    assert _SUPPRESSORS[impl](by_id, tombs) is suppressed
    assert _SUPPRESSORS[impl](by_txt, tombs) is suppressed


@pytest.mark.parametrize(("ts", "deleted_at", "suppressed"), CASES)
def test_merge_and_compact_emit_by_instant(ts, deleted_at, suppressed):
    live = Soul(NP, facts=[Fact(text="x", id="x", timestamp=ts)])
    dead = Soul(NP, tombstones={("id", "x"): deleted_at})
    for out in (m.merge_souls(live, dead), ref.merge_souls(live, dead)):
        assert (out.get_fact("x") is None) is suppressed
    both = Soul(NP, facts=[Fact(text="x", id="x", timestamp=ts)],
                tombstones={("id", "x"): deleted_at})
    compacted, _ = compact_epoch(both, at="2026-12-01T00:00:00Z")
    assert (compacted.get_fact("x") is None) is suppressed


# (older, newer) — the join keeps `newer` in either order.
JOINS = [
    pytest.param("2026-11-01T09:00:00Z", "2026-11-01T09:00:00.5Z", id="fractional"),
    pytest.param("2026-11-01T12:00:00+05:00", "2026-11-01T08:00:00Z", id="offset"),
    pytest.param("2026-11-01T09:00:00.25Z", "2026-11-01T09:00:00.3Z", id="fraction-digits"),
]

_JOINERS = {"merge": m._merge_tombstones, "reference": ref._join_tombstones}


@pytest.mark.parametrize("impl", sorted(_JOINERS))
@pytest.mark.parametrize(("older", "newer"), JOINS)
def test_tombstone_join_is_max_instant(impl, older, newer):
    join = _JOINERS[impl]
    k = ("id", "x")
    assert join({k: older}, {k: newer}) == {k: newer}
    assert join({k: newer}, {k: older}) == {k: newer}


@pytest.mark.parametrize(("older", "newer"), JOINS)
def test_data_model_tombstone_upsert_is_max_instant(older, newer):
    # Soul.forget (upsert) and the wire loader (duplicate rows) — the data-model copy.
    for first, second in ((older, newer), (newer, older)):
        soul = Soul(NP)
        soul.forget("x", deleted_at=first)
        soul.forget("x", deleted_at=second)
        assert soul.tombstones == {("id", "x"): newer}
        rows = [{"id": "x", "deleted_at": first}, {"id": "x", "deleted_at": second}]
        assert s._tombstones_from_wire(rows) == {("id", "x"): newer}


def test_same_instant_two_spellings_join_deterministically():
    k = ("id", "x")
    a, b = "2026-11-01T09:00:00Z", "2026-11-01T14:00:00+05:00"
    for join in (m._merge_tombstones, ref._join_tombstones):
        assert join({k: a}, {k: b}) == join({k: b}, {k: a})


def test_fact_clock_uses_the_same_order_as_suppression():
    """Associativity counterexample if fact LWW stayed on strings: x@12:00+05:00 (07:00Z)
    beats x@09:00Z as a string, but an 08:00Z delete kills only the first. Both fold
    orders must agree, and the 09:00Z version survives."""
    a = Soul(NP, facts=[Fact(text="old", id="x", tags=["L1"],
                             timestamp="2026-11-01T12:00:00+05:00")])
    b = Soul(NP, facts=[Fact(text="new", id="x", timestamp="2026-11-01T09:00:00Z")])
    c = Soul(NP, tombstones={("id", "x"): "2026-11-01T08:00:00Z"})
    for merge, equal in ((m.merge_souls, m.souls_equal), (ref.merge_souls, ref.souls_equal)):
        left = merge(merge(a, b), c)
        right = merge(a, merge(b, c))
        assert equal(left, right)
        fact = left.get_fact("x")
        assert fact is not None and fact.text == "new" and fact.tags == []


def test_unparseable_clock_sorts_below_every_instant():
    for clock in (s._instant_key, m._clock, ref.instant):
        assert clock(None) < clock("not-a-date") < clock("0001-01-01T00:00:00Z")
        assert clock("2026-13-01T00:00:00Z")[0] == 1  # month 13 is not an instant
        assert clock("2026-11-01T09:00:00+05:75")[0] == 1  # offset minutes > 59


def test_three_clock_copies_agree():
    stamps = [None, "", "junk", "2026-11-01T09:00:00Z", "2026-11-01T09:00:00.5Z",
              "2026-11-01T14:00:00+05:00", "2026-11-01T04:00:00-05:00",
              "2026-11-01T09:00:00.500Z", "2026-11-01t09:00:00z", "1999-12-31T23:59:59.999Z"]
    for x in stamps:
        for y in stamps:
            want = (s._instant_key(x) > s._instant_key(y), s._instant_key(x) == s._instant_key(y))
            assert (m._clock(x) > m._clock(y), m._clock(x) == m._clock(y)) == want, (x, y)
            assert (ref.instant(x) > ref.instant(y), ref.instant(x) == ref.instant(y)) == want


# ═══ 2. version (§10) ══════════════════════════════════════════════════════════


def _doc(version: str | None) -> dict:
    d = {"namepoint": NP, "created": "2026-11-01T00:00:00Z",
         "last_etched": "2026-11-01T00:00:00Z", "memory": {"facts": ["a"]}}
    if version is not None:
        d["version"] = version
    return d


def test_new_soul_writes_1_2():
    assert Soul(NP).to_doc()["version"] == "1.2"
    assert yaml.safe_load(Soul(NP).to_yaml())["version"] == "1.2"


@pytest.mark.parametrize(
    ("read", "written"),
    [("1.0", "1.2"), ("1.1", "1.2"), ("1.2", "1.2"), ("1.3", "1.3"), ("1.10", "1.10"),
     (None, "1.2"), ("v1.1", "1.2")],
)
def test_never_writes_lower_than_read(read, written):
    assert Soul.from_doc(_doc(read)).to_doc()["version"] == written


def test_derived_souls_keep_the_highest_version_read():
    hi = Soul.from_doc(_doc("1.3"))
    lo = Soul.from_doc(_doc("1.1"))
    assert m.merge_souls(hi, lo).to_doc()["version"] == "1.3"
    assert m.merge_souls(lo, hi).to_doc()["version"] == "1.3"
    compacted, _ = compact_epoch(hi, at="2026-12-01T00:00:00Z")
    assert compacted.to_doc()["version"] == "1.3"


# ═══ 3. unknown priority preserved (§10, §6.1) ═════════════════════════════════


def _round_trip(fact: object) -> object:
    doc = _doc("1.2")
    doc["memory"] = {"facts": [fact]}
    return yaml.safe_load(Soul.from_doc(doc).to_yaml())["memory"]["facts"][0]


def test_unknown_priority_round_trips_unchanged():
    # 2.1.0 wrote the bare string "- x" here.
    assert _round_trip({"text": "x", "priority": "urgent"}) == {"text": "x", "priority": "urgent"}


@pytest.mark.parametrize(("legacy", "canonical"), [("low", "ephemeral"), ("medium", "standard")])
def test_legacy_priority_mapping_still_applies(legacy, canonical):
    out = _round_trip({"text": "x", "priority": legacy})
    assert out == ("x" if canonical == "standard" else {"text": "x", "priority": canonical})


def test_unknown_priority_is_treated_as_standard_by_consumers():
    assert s.canonical_priority("urgent") == "standard"
    soul = Soul(NP, facts=[Fact(text="u", priority="urgent", timestamp="2026-11-01T00:00:00Z"),
                           Fact(text="h", priority="high", timestamp="2026-11-01T00:00:00Z"),
                           Fact(text="e", priority="ephemeral", timestamp="2026-11-01T00:00:00Z")])
    assert [f.text for f in soul.recall()] == ["h", "u", "e"]
    assert [f.text for f in soul.recall(min_priority="standard")] == ["h", "u"]


# ═══ 4. pinned strip set (§8.1) ════════════════════════════════════════════════

SPEC_STRIP = frozenset(
    [*range(0x09, 0x0E), *range(0x1C, 0x20), 0x20, 0x85, 0xA0, 0x1680,
     *range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F, 0x205F, 0x3000]
)


def test_strip_set_is_exactly_the_29_spec_code_points():
    assert len(SPEC_STRIP) == 29
    assert {ord(c) for c in s._FAFM_STRIP} == SPEC_STRIP
    assert {ord(c) for c in m._STRIP_SET} == SPEC_STRIP
    assert {cp for lo, hi in ref._SPEC_STRIP_RANGES for cp in range(lo, hi + 1)} == SPEC_STRIP


@pytest.mark.parametrize("normalize", [s.normalize_text, m.normalize_text, ref.normalize_text])
def test_normalize_strips_exactly_the_set(normalize):
    for cp in range(0x110000):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        ch = chr(cp)
        if unicodedata.normalize("NFC", ch) != ch:
            continue  # NFC may rewrite it (e.g. U+2000 → U+2002); covered by the vectors
        stripped = normalize(f"{ch}a{ch}") == "a"
        assert stripped is (cp in SPEC_STRIP), hex(cp)


@pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="spec set is Python 3.13's")
def test_set_matches_python_3_13_str_strip():
    """Same output as 2.1.0 on 3.13: the pinned set IS 3.13's ``str.strip()`` set."""
    assert {cp for cp in range(0x110000) if chr(cp).strip() == ""} == SPEC_STRIP


# ── §10 date rule on load + header clocks by instant (review of PR #20) ──────


def test_unquoted_dates_keep_tombstone_and_write_z():
    import yaml as _yaml

    from claude_fafm_sdk.soul import Soul as _Soul

    text = (
        'version: "1.2"\nnamepoint: "@d"\n'
        "created: 2026-11-02T00:00:00Z\nlast_etched: 2026-11-02T00:00:00Z\n"
        "memory:\n  facts:\n    - x\n  tombstones:\n"
        '    - id: "old-fact"\n      deleted_at: 2026-11-01T09:00:00Z\n'
    )
    out = _yaml.safe_load(_Soul.from_doc(_yaml.safe_load(text)).to_yaml())
    assert out["created"] == "2026-11-02T00:00:00Z"
    assert out["last_etched"] == "2026-11-02T00:00:00Z"
    assert out["memory"]["tombstones"] == [{"id": "old-fact", "deleted_at": "2026-11-01T09:00:00Z"}]


def test_header_clocks_merge_by_instant():
    from claude_fafm_sdk.merge import merge_souls
    from claude_fafm_sdk.soul import Soul as _Soul

    left = _Soul("@d", created="2026-01-01T09:00:00Z")
    left.last_etched = "2026-01-01T09:00:00Z"
    right = _Soul("@d", created="2026-01-01T12:00:00+05:00")  # 07:00Z
    right.last_etched = "2026-01-01T12:00:00+05:00"
    for a, b in ((left, right), (right, left)):
        m = merge_souls(a, b)
        assert m.created == "2026-01-01T12:00:00+05:00"  # the earlier instant
        assert m.last_etched == "2026-01-01T09:00:00Z"  # the later instant
