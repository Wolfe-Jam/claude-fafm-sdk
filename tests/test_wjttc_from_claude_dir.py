"""WJTTC — Step 4: from_claude_dir + from_file/to_file aliases."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from claude_fafm_sdk import Soul, from_claude_dir

CLAUDE_MEM = Path(__file__).resolve().parent / "fixtures" / "claude-memory"
LIVE_MEM = Path.home() / ".claude" / "projects" / "-Users-wolfejam" / "memory"


def test_from_claude_dir_converts_mini_fixture():
    soul = from_claude_dir(CLAUDE_MEM)
    assert soul.profile == "knowledge"
    assert soul.namepoint == "@claude-code:claude-memory"

    ids = {f.id for f in soul.facts}
    assert ids == {"good-project", "good-feedback", "name-only-slug"}
    assert "bad-type-note" not in ids

    by_id = {f.id: f for f in soul.facts}
    assert by_id["good-project"].type == "project"
    assert by_id["good-project"].text == "A solid project fact for corpus conversion."
    assert by_id["good-project"].links == ["related-topic"]
    assert by_id["good-project"].extra.get("provenance") == ["session:sess-aaa-111"]
    assert by_id["good-project"].source == "claude-code memory: good-project.md"
    assert by_id["good-project"].timestamp  # mtime stamp present

    assert by_id["good-feedback"].type == "feedback"
    assert by_id["name-only-slug"].text == "name-only-slug"
    assert by_id["name-only-slug"].type == "reference"

    # Index rebuilt from facts
    assert len(soul.index) == 3
    assert any(line.startswith("good-project — ") for line in soul.index)


def test_from_claude_dir_custom_namepoint():
    soul = from_claude_dir(CLAUDE_MEM, namepoint="@claude-code:test")
    assert soul.namepoint == "@claude-code:test"


def test_from_claude_dir_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        from_claude_dir(tmp_path / "nope")


def test_from_claude_dir_file_raises(tmp_path):
    p = tmp_path / "x.md"
    p.write_text("hi", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        from_claude_dir(p)


def test_from_claude_dir_empty_dir(tmp_path):
    soul = from_claude_dir(tmp_path, namepoint="@empty")
    assert soul.facts == []
    assert soul.profile == "knowledge"
    assert soul.index == []


def test_from_claude_dir_to_doc_is_facts_not_entries(tmp_path):
    """Must not emit proof-converter shape (memory.entries / version 1.0)."""
    soul = from_claude_dir(CLAUDE_MEM)
    path = soul.to_file(tmp_path / "converted.fafm")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert doc["version"] == "1.1"
    assert doc["profile"] == "knowledge"
    assert "facts" in doc["memory"]
    assert "entries" not in doc["memory"]
    assert "index" in doc


def test_from_file_to_file_aliases(tmp_path):
    soul = from_claude_dir(CLAUDE_MEM)
    path = soul.to_file(tmp_path / "via-alias.fafm", reindex=False)
    back = Soul.from_file(path)
    assert {f.id for f in back.facts} == {f.id for f in soul.facts}
    assert back.profile == "knowledge"
    # provenance survived structured roundtrip via Fact.extra
    gp = next(f for f in back.facts if f.id == "good-project")
    assert gp.extra.get("provenance") == ["session:sess-aaa-111"]


def test_corpus_third_file_converted_loads_clean(tmp_path):
    """Step 3 deferred third fixture: convert mini dir → Soul path."""
    soul = from_claude_dir(CLAUDE_MEM, namepoint="@claude-code:corpus-converted")
    out = tmp_path / "converted-corpus.fafm"
    soul.to_file(out)
    loaded = Soul.load(out)
    assert len(loaded.facts) == 3
    assert loaded.index
    assert loaded.get_fact("good-project") is not None


@pytest.mark.skipif(not LIVE_MEM.is_dir(), reason="live Claude memory dir not present")
def test_optional_live_claude_memory_smoke():
    soul = from_claude_dir(LIVE_MEM, namepoint="@claude-code:wolfejam")
    assert soul.profile == "knowledge"
    assert len(soul.facts) > 0
    # Every fact has canonical type
    for f in soul.facts:
        assert f.type in ("user", "feedback", "project", "reference")
        assert f.id
        assert f.text
