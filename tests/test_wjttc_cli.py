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


def test_engine_cli_etch_then_recall(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    main(["etch", "ships uv-first", "--id", "x"])
    capsys.readouterr()
    assert main(["recall", "uv"]) == 0
    assert "ships uv-first" in capsys.readouterr().out
