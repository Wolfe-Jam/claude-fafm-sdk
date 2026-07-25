"""WJTTC FINISH — v1.0 release gate (championship finish line).

Fail = do not ship 1.0.x. One file, every critical v1.0 bar from the
build-steps ladder (Steps 1–6). Complements tier suites; does not replace them.

Run:  pytest -q tests/test_wjttc_finish.py
"""

from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

import yaml

import claude_fafm_sdk
from claude_fafm_sdk import Fact, Soul, from_claude_dir

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLAUDE_MEM = FIXTURES / "claude-memory"
FAFM = FIXTURES / "fafm"


# ---------------------------------------------------------------------------
# BRAKE — version + contract surface (don't ship without these)
# ---------------------------------------------------------------------------


def test_finish_version_is_1_2():
    """v1.2 release gate: package is 1.2.x and single-sourced."""
    assert claude_fafm_sdk.__version__.startswith("1.2")
    assert version("claude-fafm-sdk") == claude_fafm_sdk.__version__


def test_finish_interop_contract_on_disk():
    """Step 1: INTEROP.md is part of the shipped tree."""
    path = ROOT / "INTEROP.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "1.0" in text or "v1.0" in text
    assert "insertion_index" in text or "insertion index" in text.lower()
    assert "from_claude_dir" in text


def test_finish_public_exports():
    """v1.2 public API surface is importable (incl. merge + packet features)."""
    from claude_fafm_sdk import (
        Fact,
        PacketError,
        Soul,
        __version__,
        canonical_priority,
        from_claude_dir,
        from_packet,
        merge_packet,
        merge_souls,
        to_packet,
    )

    assert __version__.startswith("1.2")
    assert callable(from_claude_dir)
    assert callable(merge_souls)
    assert callable(to_packet) and callable(from_packet) and callable(merge_packet)
    assert issubclass(PacketError, ValueError)
    assert Soul.from_file is not None
    assert Fact is not None
    assert canonical_priority("low") == "ephemeral"


# ---------------------------------------------------------------------------
# ENGINE — document fidelity + converter + recall SoT
# ---------------------------------------------------------------------------


def test_finish_document_fidelity_index_subtrees_residual(tmp_path):
    """Steps 2 + 2.5: index, memory subtrees, residual top-level survive save."""
    src = FAFM / "unknown-fields.fafm"
    s = Soul.load(src)
    assert s.profile == "voice"
    assert s.facts[0].extra.get("experimental_attr") == 123
    assert "future_root_field" in s.extra

    out = tmp_path / "finish-residual.fafm"
    s.to_file(out, reindex=False)
    back = Soul.from_file(out)
    assert back.extra.get("future_root_field") == s.extra["future_root_field"]
    doc = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert "index" in doc
    assert "future_root_field" in doc


def test_finish_missing_profile_defaults_to_voice(tmp_path):
    """Step 2: INTEROP §1.2 — absent profile → voice; new Soul stays knowledge."""
    p = tmp_path / "noprofile.fafm"
    p.write_text(
        "version: '1.1'\nnamepoint: '@x'\n"
        "created: '2026-01-01T00:00:00Z'\nlast_etched: '2026-01-01T00:00:00Z'\n"
        "memory:\n  facts:\n    - hi\n",
        encoding="utf-8",
    )
    assert Soul.load(p).profile == "voice"
    assert Soul("@me").profile == "knowledge"


def test_finish_from_claude_dir_schema_shape(tmp_path):
    """Step 4: converter → knowledge Soul, facts not entries, provenance in extra."""
    soul = from_claude_dir(CLAUDE_MEM, namepoint="@claude-code:finish")
    assert soul.profile == "knowledge"
    assert {f.id for f in soul.facts} == {
        "good-project",
        "good-feedback",
        "name-only-slug",
    }
    gp = soul.get_fact("good-project")
    assert gp is not None
    assert gp.extra.get("provenance") == ["session:sess-aaa-111"]

    path = soul.to_file(tmp_path / "converted.fafm")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert doc["version"] == "1.1"
    assert "facts" in doc["memory"]
    assert "entries" not in doc["memory"]
    assert "index" in doc


def test_finish_recall_sot_same_second_and_update_in_place():
    """Step 6: local rank SoT — append order + update keeps slot."""
    s = Soul("@finish")
    ts = "2026-07-22T00:00:00Z"
    s.add(Fact(text="a", id="a", priority="standard", timestamp=ts))
    s.add(Fact(text="b", id="b", priority="standard", timestamp=ts))
    s.add(Fact(text="a2", id="a", priority="standard", timestamp=ts))
    s.add(Fact(text="c", id="c", priority="standard", timestamp=ts))
    assert [f.id for f in s.recall()] == ["c", "b", "a"]
    assert s.get_fact("a").text == "a2"


# ---------------------------------------------------------------------------
# AERO — corpus + cross-profile finish line
# ---------------------------------------------------------------------------


def test_finish_corpus_fixtures_load():
    """Step 3: vendored conformance fixtures present and loadable."""
    assert (FAFM / "voice.fafm").is_file()
    assert (FAFM / "knowledge.fafm").is_file()
    v = Soul.load(FAFM / "voice.fafm")
    k = Soul.load(FAFM / "knowledge.fafm")
    assert v.profile == "voice" and v.index == []
    assert k.profile == "knowledge"
    assert k.index
    assert k.facts[0].extra.get("confidence_score") == 0.9


def test_finish_knowledge_roundtrip_preserves_extras(tmp_path):
    """Step 3/5: structured knowledge load → to_file → from_file."""
    s = Soul.load(FAFM / "knowledge.fafm")
    path = s.to_file(tmp_path / "k.fafm", reindex=False)
    back = Soul.from_file(path)
    assert back.index == s.index
    assert back.facts[0].extra.get("verification_status") == "verified"


def test_finish_aliases_match_load_save(tmp_path):
    """from_file/to_file are load/save aliases (Step 4 name parity)."""
    s = Soul("@alias")
    s.etch("via alias", id="x", type="project")
    p = s.to_file(tmp_path / "a.fafm")
    assert Soul.from_file(p).get_fact("x").text == "via alias"
