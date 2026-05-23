"""WJTTC — claude-fafm-sdk CLI (init / etch / recall).

ENGINE: the commands do what they say. BRAKE: the `init` message stays HONEST —
no fake fact counts, no fake "Grok read it back" claim. The wow must be true.
"""

import os

import pytest

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


def test_engine_cli_init_cta_points_to_claim(tmp_path, monkeypatch, capsys):
    # The onboarding gem: init nudges toward a free namepoint, honestly.
    monkeypatch.chdir(tmp_path)
    main(["init"])
    out = capsys.readouterr().out
    assert "mcpaas.live/claim" in out
    assert "namepoint link" in out


def test_engine_cli_namepoint_link_sets_handle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MCPAAS_API_KEY", raising=False)
    main(["init"])
    assert main(["namepoint", "link", "claude-fafm-sdk"]) == 0
    assert Soul.load(tmp_path / "soul.fafm").namepoint == "claude-fafm-sdk"


def test_brake_namepoint_link_is_honest_not_live(tmp_path, monkeypatch, capsys):
    # link writes LOCAL metadata only — it must NOT claim the soul is live/hosted
    # (nothing is uploaded until `namepoint push`). Honest-by-design.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MCPAAS_API_KEY", raising=False)
    main(["init"])
    capsys.readouterr()
    main(["namepoint", "link", "you99"])
    out = capsys.readouterr().out.lower()
    assert "is live" not in out and "now live" not in out and "readable by grok" not in out
    assert "namepoint push" in out          # tells you how to actually go live
    assert "mcpaas_api_key" in out          # no key set → points to the token


def test_brake_namepoint_link_missing_soul_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["namepoint", "link", "you99"]) == 1
    assert "not found" in capsys.readouterr().out


def test_brake_cli_namepoint_push_needs_key(tmp_path, monkeypatch, capsys):
    # Guard, no network: a write with no token stops BEFORE the wire, pointing at
    # the token you get on claim. (Local check — doesn't touch the namepoint.)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MCPAAS_API_KEY", raising=False)
    main(["init"])
    main(["namepoint", "link", "you99"])
    capsys.readouterr()
    assert main(["namepoint", "push"]) == 1
    assert "MCPAAS_API_KEY" in capsys.readouterr().out


def test_brake_cli_namepoint_push_needs_linked_handle(tmp_path, monkeypatch, capsys):
    # Guard, no network: refuses the unlinked @claude-code: placeholder.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCPAAS_API_KEY", "tok")
    main(["init"])
    capsys.readouterr()
    assert main(["namepoint", "push"]) == 1
    assert "mcpaas.live/claim" in capsys.readouterr().out


def test_brake_cli_namepoint_sync_needs_key(tmp_path, monkeypatch, capsys):
    # Guard, no network: sync writes, so no token → stops before the wire.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MCPAAS_API_KEY", raising=False)
    main(["init"])
    main(["namepoint", "link", "you99"])
    capsys.readouterr()
    assert main(["namepoint", "sync"]) == 1
    assert "MCPAAS_API_KEY" in capsys.readouterr().out


def test_brake_cli_namepoint_sync_needs_linked_handle(tmp_path, monkeypatch, capsys):
    # Guard, no network: refuses the unlinked @claude-code: placeholder.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MCPAAS_API_KEY", "tok")
    main(["init"])
    capsys.readouterr()
    assert main(["namepoint", "sync"]) == 1
    assert "link" in capsys.readouterr().out.lower()


@pytest.mark.skipif(
    not (os.environ.get("MCPAAS_API_KEY") and os.environ.get("CFS_TEST_NAMEPOINT")),
    reason="set MCPAAS_API_KEY + CFS_TEST_NAMEPOINT for the live TYRE push/pull/sync roundtrip",
)
def test_tyre_live_push_pull_roundtrip(tmp_path, monkeypatch):
    # TYRE (the live TEST tier — distinct from PIT/eval) — the real loop against a
    # live namepoint, no fakes. Idempotent: the marker text is stable, so
    # client-side dedup keeps re-runs from duplicating.
    handle = os.environ["CFS_TEST_NAMEPOINT"]
    marker = f"tyre roundtrip marker — {handle}"
    monkeypatch.chdir(tmp_path)
    main(["init"])
    main(["namepoint", "link", handle])
    main(["etch", marker, "--id", "tyre"])
    assert main(["namepoint", "push"]) == 0

    # Fresh local soul → pull from the live namepoint → the marker comes back.
    main(["init", "--force"])
    main(["namepoint", "link", handle])
    assert main(["namepoint", "pull"]) == 0
    texts = [f.text for f in Soul.load(tmp_path / "soul.fafm").facts]
    assert marker in texts

    # sync converges + is idempotent (both sides already hold the marker).
    assert main(["namepoint", "sync"]) == 0
    assert main(["namepoint", "sync"]) == 0
