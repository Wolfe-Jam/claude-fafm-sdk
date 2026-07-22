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
    assert "index" in doc
    assert isinstance(doc["memory"]["sessions"], list)
    assert isinstance(doc["memory"]["preferences"], dict)
    assert isinstance(doc["memory"]["custom"], dict)


def test_brake_bare_string_facts_load(tmp_path):
    # Interop: a soul whose facts are bare strings must load (spec allows it).
    (tmp_path / "bare.fafm").write_text(
        "version: '1.1'\nnamepoint: '@x'\nmemory:\n  facts:\n    - just a string\n",
        encoding="utf-8",
    )
    s = Soul.load(tmp_path / "bare.fafm")
    assert s.facts[0].text == "just a string"


# ---------------------------------------------------------------------------
# Step 2 — document fidelity (INTEROP §1.2 / §1.4 / §5)
# ---------------------------------------------------------------------------

# Voice-shaped knowledge fixture (mirrors grok-faf-voice test_local_souls).
_KNOWLEDGE_FAFM = """\
version: "1.1"
profile: "knowledge"
namepoint: "@claude-code:wolfejam"
created: "2026-05-21T00:00:00Z"
last_etched: "2026-05-21T09:00:00Z"
retention: "forever"
index:
  - "precision-is-power — named tiers beat umbrella terms"
memory:
  facts:
    - text: "Replace lossy umbrella terms with named tiers."
      id: "precision-is-power"
      type: "feedback"
      priority: "high"
      tags: ["copy", "doctrine"]
      links: ["no-made-up-numbers"]
      timestamp: "2026-05-20T00:00:00Z"
      source: "session note"
  sessions:
    - id: "s1"
      note: "kept"
  preferences:
    tone: "terse"
  custom:
    project: "fafm"
"""


def test_brake_missing_profile_defaults_to_voice(tmp_path):
    """INTEROP §1.2: absent profile on load → voice (schema default)."""
    (tmp_path / "noprofile.fafm").write_text(
        "version: '1.1'\nnamepoint: '@x'\n"
        "created: '2026-01-01T00:00:00Z'\nlast_etched: '2026-01-01T00:00:00Z'\n"
        "memory:\n  facts:\n    - just a string\n",
        encoding="utf-8",
    )
    s = Soul.load(tmp_path / "noprofile.fafm")
    assert s.profile == "voice"
    # Constructor for *new* knowledge souls still defaults to knowledge.
    assert Soul("@me").profile == "knowledge"


def test_brake_index_load_and_empty_when_absent(tmp_path):
    p = tmp_path / "k.fafm"
    p.write_text(_KNOWLEDGE_FAFM, encoding="utf-8")
    s = Soul.load(p)
    assert s.index == ["precision-is-power — named tiers beat umbrella terms"]

    (tmp_path / "v.fafm").write_text(
        "version: '1.1'\nprofile: voice\nnamepoint: '@v'\n"
        "created: '2026-01-01T00:00:00Z'\nlast_etched: '2026-01-01T00:00:00Z'\n"
        "memory:\n  facts:\n    - hi\n",
        encoding="utf-8",
    )
    v = Soul.load(tmp_path / "v.fafm")
    assert v.index == []


def test_brake_memory_subtrees_load_and_roundtrip(tmp_path):
    """sessions/preferences/custom are modeled — not reinvented empty on save."""
    p = tmp_path / "k.fafm"
    p.write_text(_KNOWLEDGE_FAFM, encoding="utf-8")
    s = Soul.load(p)
    assert s.sessions == [{"id": "s1", "note": "kept"}]
    assert s.preferences == {"tone": "terse"}
    assert s.custom == {"project": "fafm"}

    out = tmp_path / "out.fafm"
    s.save(out, reindex=False)
    back = Soul.load(out)
    assert back.sessions == [{"id": "s1", "note": "kept"}]
    assert back.preferences == {"tone": "terse"}
    assert back.custom == {"project": "fafm"}
    assert back.index == ["precision-is-power — named tiers beat umbrella terms"]


def test_brake_index_preserved_when_reindex_false(tmp_path):
    p = tmp_path / "k.fafm"
    p.write_text(_KNOWLEDGE_FAFM, encoding="utf-8")
    s = Soul.load(p)
    s.etch("new fact without touching index rebuild path", id="extra")
    s.save(tmp_path / "kept.fafm", reindex=False)
    back = Soul.load(tmp_path / "kept.fafm")
    assert back.index == ["precision-is-power — named tiers beat umbrella terms"]
    assert back.get_fact("extra") is not None


def test_brake_save_reindexes_by_default(tmp_path):
    p = tmp_path / "k.fafm"
    p.write_text(_KNOWLEDGE_FAFM, encoding="utf-8")
    s = Soul.load(p)
    s.etch("second durable fact", id="second-fact")
    s.save(tmp_path / "rebuilt.fafm")  # reindex=True default
    back = Soul.load(tmp_path / "rebuilt.fafm")
    assert any(line.startswith("second-fact — ") for line in back.index)
    assert any(line.startswith("precision-is-power — ") for line in back.index)


def test_brake_rebuild_index_formula():
    s = Soul("@me")
    s.add(Fact(text="short", id="a"))
    s.add(Fact(text="x" * 100))  # no id → '?'
    lines = s.rebuild_index(width=80)
    assert lines[0] == "a — short"
    assert lines[1].startswith("? — ")
    assert len(lines[1].split(" — ", 1)[1]) == 80


def test_brake_to_doc_always_emits_index_key():
    s = Soul("@me")
    s.etch("a fact", id="f1")
    doc = s.to_doc()
    assert "index" in doc
    assert isinstance(doc["index"], list)


def test_brake_top_level_and_memory_residual_roundtrip(tmp_path):
    """Step 2.5: arbitrary unknowns under root and memory are preserved."""
    (tmp_path / "res.fafm").write_text(
        "version: '1.1'\nprofile: knowledge\nnamepoint: '@r'\n"
        "created: '2026-01-01T00:00:00Z'\nlast_etched: '2026-01-01T00:00:00Z'\n"
        "future_root_field: keep-me\n"
        "memory:\n"
        "  facts:\n    - text: hi\n"
        "  sessions: []\n"
        "  preferences: {}\n"
        "  custom: {}\n"
        "  experimental_bucket: {n: 1}\n",
        encoding="utf-8",
    )
    s = Soul.load(tmp_path / "res.fafm")
    assert s.extra["future_root_field"] == "keep-me"
    assert s.memory_extra["experimental_bucket"] == {"n": 1}
    s.save(tmp_path / "out.fafm", reindex=False)
    back = Soul.load(tmp_path / "out.fafm")
    assert back.extra["future_root_field"] == "keep-me"
    assert back.memory_extra["experimental_bucket"] == {"n": 1}
    doc = back.to_doc()
    assert doc["future_root_field"] == "keep-me"
    assert doc["memory"]["experimental_bucket"] == {"n": 1}
    # Residual must not clobber modeled keys even if stuffed into extra.
    s.extra["namepoint"] = "@hijack"
    assert s.to_doc()["namepoint"] == "@r"


def test_brake_namepoint_write_needs_a_key():
    # No key → loud, clear refusal that points to the free signup. Reads (pull)
    # need no key; only writes gate. (No network: the key check precedes any call.)
    np = Namepoint("@me")
    with pytest.raises(NamepointAuthRequired) as e:
        asyncio.run(np.push("a fact"))
    assert "claim" in str(e.value)  # points to `namepoint claim`
