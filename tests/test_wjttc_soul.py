"""WJTTC — claude-fafm-sdk Soul (open .fafm ops) + Namepoint contract.

ENGINE-tier: the core local memory ops. BRAKE-tier: format + contract invariants
(one .fafm format, no fork; offline client fails loud + clear).
"""

import pytest

import asyncio

from claude_fafm_sdk import Fact, Namepoint, NamepointAuthRequired, Soul


def test_engine_etch_and_recall():
    s = Soul("@me")
    s.etch("ships uv-first", id="install", type="reference")
    assert [f.text for f in s.recall("uv")] == ["ships uv-first"]


def test_engine_id_dedup_updates_in_place():
    s = Soul("@me")
    s.etch("draft", id="x")
    s.etch("final", id="x")  # same id → update, not append
    assert len(s.facts) == 1
    assert s.get_fact("x").text == "final"


def test_engine_save_load_roundtrip(tmp_path):
    s = Soul("@me")
    s.etch("portable across vendors", id="why", type="project", priority="high")
    p = s.save(tmp_path / "me.fafm")
    loaded = Soul.load(p)
    assert loaded.namepoint == "@me"
    assert loaded.get_fact("why").text == "portable across vendors"
    assert loaded.get_fact("why").priority == "high"


def test_engine_recall_ranks_priority_then_recency():
    s = Soul("@me")
    s.etch("low note", id="a", priority="standard", tags=["t"])
    s.etch("hot note", id="b", priority="critical", tags=["t"])
    ranked = s.recall(tags=["t"])
    assert [f.id for f in ranked] == ["b", "a"]  # critical before standard


def test_engine_recall_recency_breaks_same_second_ties():
    # Facts etched in one fast loop share a second-granularity timestamp; recall
    # must still return them newest-first (insertion-index tiebreak), not the
    # insertion order. Regression guard for the recency bug.
    s = Soul("@me")
    s.etch("first", id="a")
    s.etch("second", id="b")
    s.etch("third", id="c")
    assert len({f.timestamp for f in s.facts}) == 1  # same second
    assert [f.id for f in s.recall()] == ["c", "b", "a"]  # newest first


def test_engine_to_yaml_roundtrip_preserves_ids(tmp_path):
    # The .fafm-native namepoint stores the whole document — ids must survive a
    # serialize → parse round-trip (this is what push/pull rely on).
    s = Soul("@me")
    s.etch("structured fact", id="a", type="project", priority="high")
    text = s.to_yaml()
    (tmp_path / "rt.fafm").write_text(text, encoding="utf-8")
    back = Soul.load(tmp_path / "rt.fafm")
    assert back.get_fact("a").text == "structured fact"
    assert back.get_fact("a").priority == "high"


def test_engine_add_preserves_timestamp_and_dedups_by_id():
    # `add` is the merge primitive: keep the incoming fact verbatim (timestamp too),
    # update-in-place by id.
    s = Soul("@me")
    s.add(Fact(text="v1", id="x", timestamp="2020-01-01T00:00:00Z"))
    assert s.get_fact("x").timestamp == "2020-01-01T00:00:00Z"
    s.add(Fact(text="v2", id="x", timestamp="2021-01-01T00:00:00Z"))
    assert len(s.facts) == 1 and s.get_fact("x").text == "v2"


def test_engine_delete_fact():
    s = Soul("@me")
    s.etch("temp", id="z")
    assert s.delete_fact("z") is True
    assert s.get_fact("z") is None
    assert s.delete_fact("z") is False


def test_brake_save_is_fafm_v11_shape():
    # Format invariant: one .fafm format, never a fork.
    s = Soul("@me")
    s.etch("a fact", id="f1")
    doc = s.to_doc()
    assert doc["version"] == "1.1"
    assert "facts" in doc["memory"]


def test_brake_bare_string_facts_load(tmp_path):
    # Interop: a soul whose facts are bare strings must load (spec allows it).
    (tmp_path / "bare.fafm").write_text(
        "version: '1.1'\nnamepoint: '@x'\nmemory:\n  facts:\n    - just a string\n",
        encoding="utf-8",
    )
    s = Soul.load(tmp_path / "bare.fafm")
    assert s.facts[0].text == "just a string"


def test_brake_namepoint_write_needs_a_key():
    # No key → loud, clear refusal that points to the free signup. Reads (pull)
    # need no key; only writes gate. (No network: the key check precedes any call.)
    np = Namepoint("@me")
    with pytest.raises(NamepointAuthRequired) as e:
        asyncio.run(np.push("a fact"))
    assert "claim" in str(e.value)  # points to `namepoint claim`
