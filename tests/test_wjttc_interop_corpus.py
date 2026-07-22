"""WJTTC — Step 3 symmetric cross-test corpus (INTEROP §4 / §8).

Always-on (no extra deps):
  - Load official-shaped fixtures (vendored from faf conformance)
  - Soul load → save → load logical roundtrip
  - Fact-level unknown-field preservation (knowledge extras)

Optional (grok-faf-voice installed):
  - Path A: live Soul.save() bytes → FAFMemory.from_file()  (highest-value gap)
  - Path B: FAFMemory.to_file() raw → Soul.load()

Third corpus file (from_claude_dir output) is gated on Step 4.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
import yaml

from claude_fafm_sdk import Fact, Soul

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fafm"
VOICE_FAFM = FIXTURES / "voice.fafm"
KNOWLEDGE_FAFM = FIXTURES / "knowledge.fafm"
UNKNOWN_FAFM = FIXTURES / "unknown-fields.fafm"

# Optional large knowledge soul (sibling repo) — path load only, never inlined.
_LARGE_KNOWLEDGE = (
    Path(__file__).resolve().parents[2] / "fafm-engine" / "claude-code-wolfejam.fafm"
)


def _logical_facts(soul: Soul) -> list[dict[str, Any]]:
    """Stable comparable view of facts (order = soul fact order, not recall rank)."""
    out: list[dict[str, Any]] = []
    for f in soul.facts:
        out.append(
            {
                "text": f.text,
                "id": f.id,
                "type": f.type,
                "priority": f.priority,
                "tags": list(f.tags),
                "links": list(f.links),
                "timestamp": f.timestamp,
                "source": f.source,
                "extra": dict(f.extra),
            }
        )
    return out


def _normalize_voice_facts(raw: list[Any]) -> list[dict[str, Any]]:
    """Map FAFMemory.facts (bare str | dict) to a comparable logical list."""
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            out.append(
                {
                    "text": item,
                    "id": None,
                    "type": None,
                    "priority": "standard",
                    "tags": [],
                    "links": [],
                    "timestamp": None,
                    "source": None,
                    "extra": {},
                }
            )
            continue
        if not isinstance(item, dict) or "text" not in item:
            raise AssertionError(f"unexpected fact shape from FAFMemory: {item!r}")
        known = {"text", "id", "type", "priority", "tags", "links", "timestamp", "source"}
        priority = item.get("priority") or "standard"
        out.append(
            {
                "text": item["text"],
                "id": item.get("id"),
                "type": item.get("type"),
                "priority": priority,
                "tags": list(item.get("tags") or []),
                "links": list(item.get("links") or []),
                "timestamp": item.get("timestamp"),
                "source": item.get("source"),
                "extra": {k: v for k, v in item.items() if k not in known},
            }
        )
    return out


# ---------------------------------------------------------------------------
# Tier A — always on
# ---------------------------------------------------------------------------


def test_corpus_fixtures_present():
    assert VOICE_FAFM.is_file()
    assert KNOWLEDGE_FAFM.is_file()
    assert UNKNOWN_FAFM.is_file()


def test_a1_load_voice_fixture():
    s = Soul.load(VOICE_FAFM)
    assert s.profile == "voice"
    assert s.namepoint == "@demo"
    assert s.index == []
    assert len(s.facts) == 2
    assert s.facts[0].text == "Prefers concise answers"
    assert s.facts[1].text == "Works in TypeScript"
    assert s.facts[1].tags == ["stack"]


def test_a2_load_knowledge_fixture_index_and_extras():
    """INTEROP §4: confidence_score / verification_status live in Fact.extra."""
    s = Soul.load(KNOWLEDGE_FAFM)
    assert s.profile == "knowledge"
    assert s.index == ["stack: TypeScript + Bun"]
    assert len(s.facts) == 1
    f = s.facts[0]
    assert f.id == "f1"
    assert f.text == "The project uses Bun"
    assert f.type == "project"
    assert f.priority == "high"
    assert f.extra.get("confidence_score") == 0.9
    assert f.extra.get("verification_status") == "verified"


def test_a3_soul_roundtrip_knowledge_preserves_logical(tmp_path):
    s = Soul.load(KNOWLEDGE_FAFM)
    before = _logical_facts(s)
    index_before = list(s.index)
    out = tmp_path / "k-rt.fafm"
    s.save(out, reindex=False)
    back = Soul.load(out)
    assert _logical_facts(back) == before
    assert back.index == index_before
    assert back.profile == "knowledge"
    # Fact extras survived structured serialize (not just load).
    assert back.facts[0].extra["confidence_score"] == 0.9
    assert back.facts[0].extra["verification_status"] == "verified"


def test_a3_soul_roundtrip_voice(tmp_path):
    s = Soul.load(VOICE_FAFM)
    before = _logical_facts(s)
    out = tmp_path / "v-rt.fafm"
    s.save(out, reindex=False)
    back = Soul.load(out)
    assert _logical_facts(back) == before
    assert back.profile == "voice"
    assert back.index == []


def test_a4_sdk_writer_fresh_soul(tmp_path):
    """Live code path: etch → save → load (not a hand-typed stand-in)."""
    s = Soul("@claude-code:corpus", profile="knowledge")
    s.etch("written by claude-fafm-sdk", id="origin", type="project", priority="high")
    s.etch("second fact", id="two", type="reference", tags=["corpus"])
    path = s.save(tmp_path / "live.fafm")  # reindex=True → index rebuilt
    back = Soul.load(path)
    assert [f.id for f in back.facts] == ["origin", "two"]
    assert any(line.startswith("origin — ") for line in back.index)
    assert any(line.startswith("two — ") for line in back.index)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "index" in doc
    assert doc["profile"] == "knowledge"


def test_a5_unknown_fields_fact_and_doc_extra_preserved(tmp_path):
    """INTEROP §4: fact extras + top-level residual keys survive Soul roundtrip."""
    s = Soul.load(UNKNOWN_FAFM)
    assert s.profile == "voice"
    assert s.facts[0].extra.get("experimental_attr") == 123
    assert s.extra.get("future_root_field") == (
        "a consumer MUST ignore this, not reject it"
    )

    s.save(tmp_path / "u-rt.fafm", reindex=False)
    back = Soul.load(tmp_path / "u-rt.fafm")
    assert back.facts[0].extra.get("experimental_attr") == 123
    assert back.extra.get("future_root_field") == (
        "a consumer MUST ignore this, not reject it"
    )

    rewritten = yaml.safe_load((tmp_path / "u-rt.fafm").read_text(encoding="utf-8"))
    assert rewritten.get("future_root_field") == (
        "a consumer MUST ignore this, not reject it"
    )
    # Modeled keys win if a residual tried to shadow them (not in fixture, but API).
    assert rewritten["version"] == "1.1"
    assert rewritten["namepoint"] == "@demo"


@pytest.mark.skipif(not _LARGE_KNOWLEDGE.is_file(), reason="large soul fixture not adjacent")
def test_a6_optional_large_knowledge_loads():
    s = Soul.load(_LARGE_KNOWLEDGE)
    assert s.profile in ("knowledge", "voice")
    assert len(s.facts) > 10
    assert isinstance(s.index, list)


# ---------------------------------------------------------------------------
# Tier B — optional live cross-vendor (real code paths both ends)
# ---------------------------------------------------------------------------


def test_b_path_a_soul_save_then_fafmemory_from_file(tmp_path):
    """Highest-value gap: FAFMemory reads *SDK-serialized* bytes, not a hand fixture."""
    FAFMemory = pytest.importorskip("grok_faf_voice.memory").FAFMemory

    s = Soul("@claude-code:path-a", profile="knowledge")
    s.etch(
        "Replace lossy umbrella terms with named tiers.",
        id="precision-is-power",
        type="feedback",
        priority="high",
        tags=["copy", "doctrine"],
    )
    s.add(
        Fact(
            text="The project uses Bun",
            id="f1",
            type="project",
            priority="high",
            extra={"confidence_score": 0.9, "verification_status": "verified"},
        )
    )
    path = s.save(tmp_path / "sdk-written.fafm")

    mem = FAFMemory.from_file(path)
    assert mem.profile == "knowledge"
    assert len(mem.facts) == 2
    assert mem.index  # rebuilt on save
    assert any("precision-is-power" in line for line in mem.index)

    # Logical facts: SDK Soul view vs voice raw view of the same file.
    soul_back = Soul.load(path)
    assert _normalize_voice_facts(mem.facts) == _logical_facts(soul_back)


def test_b_path_a_conformance_knowledge_via_soul_then_voice(tmp_path):
    """Conformance knowledge → Soul.save → FAFMemory (live SDK output of official shape)."""
    FAFMemory = pytest.importorskip("grok_faf_voice.memory").FAFMemory

    s = Soul.load(KNOWLEDGE_FAFM)
    path = s.save(tmp_path / "conf-k.fafm", reindex=False)
    mem = FAFMemory.from_file(path)
    assert mem.profile == "knowledge"
    assert mem.index == ["stack: TypeScript + Bun"]
    assert len(mem.facts) == 1
    raw = mem.facts[0]
    assert isinstance(raw, dict)
    assert raw["id"] == "f1"
    assert raw.get("confidence_score") == 0.9
    assert raw.get("verification_status") == "verified"


def test_b_path_b_voice_to_file_then_soul_load(tmp_path):
    """Voice raw to_file → Soul.load (SDK reads voice-touched knowledge bytes)."""
    FAFMemory = pytest.importorskip("grok_faf_voice.memory").FAFMemory

    mem = FAFMemory.from_file(KNOWLEDGE_FAFM)
    out = tmp_path / "voice-touched-knowledge.fafm"
    asyncio.run(mem.to_file(out))

    s = Soul.load(out)
    assert s.profile == "knowledge"
    assert s.index == ["stack: TypeScript + Bun"]
    assert s.facts[0].id == "f1"
    assert s.facts[0].extra.get("confidence_score") == 0.9


def test_b_path_b_voice_to_file_voice_profile_then_soul_load(tmp_path):
    """Step 5 gap: voice to_file on *voice-profile* fixture → Soul.load.

    Path B previously only exercised the knowledge fixture. to_file is raw
    passthrough (no profile branching), but this combination had zero coverage.
    """
    FAFMemory = pytest.importorskip("grok_faf_voice.memory").FAFMemory

    mem = FAFMemory.from_file(VOICE_FAFM)
    out = tmp_path / "voice-touched-voice.fafm"
    asyncio.run(mem.to_file(out))

    s = Soul.load(out)
    assert s.profile == "voice"
    assert s.index == []
    assert len(s.facts) == 2
    assert s.facts[0].text == "Prefers concise answers"
    assert s.facts[1].text == "Works in TypeScript"
    assert s.facts[1].tags == ["stack"]


def test_b_path_a_voice_fixture_via_soul_then_voice(tmp_path):
    FAFMemory = pytest.importorskip("grok_faf_voice.memory").FAFMemory

    s = Soul.load(VOICE_FAFM)
    path = s.save(tmp_path / "conf-v.fafm", reindex=False)
    mem = FAFMemory.from_file(path)
    assert mem.profile == "voice"
    assert mem.index == []
    assert len(mem.facts) == 2
