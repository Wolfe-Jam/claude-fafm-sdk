"""WJTTC — claude-fafm-sdk CLI (init / etch / recall).

ENGINE: the commands do what they say. BRAKE: the `init` message stays HONEST —
no fake fact counts, no fake "Grok read it back" claim. The wow must be true.
"""

from claude_fafm_sdk import Soul
from claude_fafm_sdk.cli import main


def test_engine_cli_init_creates_soul(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    assert (tmp_path / "soul.fafm").exists()
    assert Soul.load(tmp_path / "soul.fafm").namepoint.startswith("@claude-code:")


def test_brake_init_message_is_honest(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    out = capsys.readouterr().out.lower()
    # must NOT fake: a fresh soul has 0 facts; there is no live readback
    assert "131" not in out
    assert "read it back" not in out
    assert "confirmed" not in out
    # must be TRUE: portable format that other tools read
    assert "portable" in out
    assert "grok-faf-voice" in out


def test_brake_init_fresh_soul_is_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    assert Soul.load(tmp_path / "soul.fafm").facts == []  # 0 facts — never claim otherwise


def test_brake_demo_count_is_the_real_count(tmp_path, monkeypatch, capsys):
    # The printed "N facts ready" must equal the soul's actual fact count — never
    # a hardcoded placeholder (no "131" baked into a fresh/seeded init).
    from claude_fafm_sdk.cli import DEMO_FACTS

    monkeypatch.chdir(tmp_path)
    main(["init", "--demo"])
    out = capsys.readouterr().out
    n = len(Soul.load(tmp_path / "soul.fafm").facts)
    assert n == len(DEMO_FACTS)
    assert f"{n} facts ready" in out


def test_engine_cli_etch_then_recall(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    main(["etch", "ships uv-first", "--id", "x"])
    capsys.readouterr()
    assert main(["recall", "uv"]) == 0
    assert "ships uv-first" in capsys.readouterr().out


def _seed(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    main(["etch", "ships uv-first", "--id", "install", "--type", "reference", "--priority", "high"])
    main(["etch", "portable across vendors", "--id", "why", "--type", "project"])


def test_engine_cli_recall_filters_by_type(tmp_path, monkeypatch, capsys):
    _seed(monkeypatch, tmp_path)
    capsys.readouterr()
    assert main(["recall", "--type", "project"]) == 0
    out = capsys.readouterr().out
    assert "portable across vendors" in out and "ships uv-first" not in out


def test_engine_cli_recall_filters_by_priority(tmp_path, monkeypatch, capsys):
    _seed(monkeypatch, tmp_path)
    capsys.readouterr()
    assert main(["recall", "--priority", "high"]) == 0
    out = capsys.readouterr().out
    assert "ships uv-first" in out and "portable across vendors" not in out


def test_engine_cli_ls_lists_all_facts(tmp_path, monkeypatch, capsys):
    _seed(monkeypatch, tmp_path)
    capsys.readouterr()
    assert main(["ls"]) == 0
    out = capsys.readouterr().out
    assert "2 facts" in out
    assert "ships uv-first" in out and "portable across vendors" in out


def test_engine_cli_forget_deletes_by_id(tmp_path, monkeypatch, capsys):
    _seed(monkeypatch, tmp_path)
    capsys.readouterr()
    assert main(["forget", "why"]) == 0
    assert "1 left" in capsys.readouterr().out
    assert Soul.load(tmp_path / "soul.fafm").get_fact("why") is None


def test_brake_forget_missing_id_fails_loud(tmp_path, monkeypatch, capsys):
    _seed(monkeypatch, tmp_path)
    capsys.readouterr()
    assert main(["forget", "nope"]) == 1  # non-zero exit, clear message
    assert "no fact" in capsys.readouterr().out
