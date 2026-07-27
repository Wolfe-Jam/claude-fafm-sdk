"""WJTTC — claude-fafm-sdk CLI (init / etch / recall).

ENGINE: the commands do what they say. BRAKE: the `init` message stays HONEST —
no fake fact counts, no fake "Grok read it back" claim. The wow must be true.
"""

import os

import pytest

from claude_fafm_sdk import Soul, cli
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
    soul = Soul.load(tmp_path / "soul.fafm")
    assert soul.get_fact("why") is None          # live fact removed
    assert ("id", "why") in soul.tombstones      # 1.5: + a convergent tombstone


def test_forget_missing_id_still_tombstones_for_convergence(tmp_path, monkeypatch, capsys):
    # 1.5 semantics: forgetting an id you don't hold locally is NOT an error — it
    # records a tombstone so the fact is suppressed if it arrives later via merge
    # (freeze §3.4 "append/upsert tombstone"). Honest message, exit 0.
    _seed(monkeypatch, tmp_path)
    capsys.readouterr()
    assert main(["forget", "nope"]) == 0
    assert "no live fact" in capsys.readouterr().out
    assert ("id", "nope") in Soul.load(tmp_path / "soul.fafm").tombstones


def test_forget_text_tombstones_idless_fact(tmp_path, monkeypatch, capsys):
    # forget --text: id-less fact matched by normalized text, removed + tombstoned.
    monkeypatch.chdir(tmp_path)
    main(["init"])
    main(["etch", "a stray thought"])  # id-less
    capsys.readouterr()
    assert main(["forget", "--text", " a stray thought "]) == 0  # normalized match
    out = capsys.readouterr().out
    assert "left" in out
    soul = Soul.load(tmp_path / "soul.fafm")
    assert all(f.text != "a stray thought" for f in soul.facts)
    assert any(kind == "txt" for kind, _ in soul.tombstones)


def test_forget_needs_exactly_one_target(tmp_path, monkeypatch, capsys):
    _seed(monkeypatch, tmp_path)
    capsys.readouterr()
    # neither id nor --text → usage error, exit 1
    assert main(["forget"]) == 1
    assert "exactly one" in capsys.readouterr().out
    # both id and --text → also rejected (no ambiguity)
    assert main(["forget", "why", "--text", "x"]) == 1


def test_engine_cli_init_cta_nudges_zero_config(tmp_path, monkeypatch, capsys):
    # The onboarding gem: init points at zero-config push + the keepers upgrade.
    monkeypatch.chdir(tmp_path)
    main(["init"])
    out = capsys.readouterr().out
    assert "namepoint push" in out          # A: just push, auto-provisions
    assert "claim --email" in out           # B: keep it forever


def test_engine_cli_wizard_noninteractive_creates_soul(tmp_path, monkeypatch, capsys):
    # No subcommand → the guided wizard. In a non-tty it does the safe local steps
    # and points at the manual command (never auto-pushes).
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "_is_interactive", lambda: False)
    assert main([]) == 0
    assert (tmp_path / "soul.fafm").exists()
    assert "namepoint push" in capsys.readouterr().out


def test_engine_cli_wizard_etches_first_memory_skips_push(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "_is_interactive", lambda: True)
    answers = iter(["I prefer TypeScript", "n"])  # first memory, then decline going live
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(answers))
    assert main(["quickstart"]) == 0
    soul = Soul.load(tmp_path / "soul.fafm")
    assert any(f.text == "I prefer TypeScript" for f in soul.facts)
    assert "push when ready" in capsys.readouterr().out.lower()


def test_brake_wizard_no_false_live_without_push(tmp_path, monkeypatch, capsys):
    # Honesty: decline going live → must NOT claim the soul is live/readable
    # (nothing was pushed). No network touched.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "_is_interactive", lambda: True)
    answers = iter(["", "n"])  # skip memory, decline live
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(answers))
    assert main(["quickstart"]) == 0
    out = capsys.readouterr().out.lower()
    assert "live:" not in out and "read it back" not in out


def test_engine_cli_namepoint_status_none(tmp_path, monkeypatch, capsys):
    # No network, no fakes: a fresh machine has no identity → honest "not yet".
    import claude_fafm_sdk.identity as idmod
    monkeypatch.setattr(idmod, "IDENTITY_PATH", tmp_path / "identity.json")
    monkeypatch.delenv("MCPAAS_API_KEY", raising=False)
    monkeypatch.delenv("FAF_SOUL", raising=False)
    assert main(["namepoint", "status"]) == 0
    out = capsys.readouterr().out
    assert "no namepoint yet" in out and "claim --email" in out


@pytest.mark.skipif(
    not (os.environ.get("MCPAAS_API_KEY") and os.environ.get("FAF_SOUL")),
    reason="set MCPAAS_API_KEY + FAF_SOUL for the live TYRE push/pull/sync roundtrip",
)
def test_tyre_live_push_pull_sync_roundtrip(tmp_path, monkeypatch):
    # TYRE (the live TEST tier) — the real loop against a live namepoint, no fakes.
    # Uses the env identity (MCPAAS_API_KEY + FAF_SOUL). Idempotent: the marker text
    # is stable, so client-side dedup keeps re-runs from duplicating.
    handle = os.environ["FAF_SOUL"]
    marker = f"tyre roundtrip marker — {handle}"
    monkeypatch.chdir(tmp_path)
    main(["init"])
    main(["etch", marker, "--id", "tyre"])
    assert main(["namepoint", "push"]) == 0          # uploads (auto-dedup)

    # Fresh local soul → pull from the live namepoint → the marker comes back.
    main(["init", "--force"])
    assert main(["namepoint", "pull"]) == 0
    assert marker in [f.text for f in Soul.load(tmp_path / "soul.fafm").facts]

    # sync converges + is idempotent (both sides already hold the marker).
    assert main(["namepoint", "sync"]) == 0
    assert main(["namepoint", "sync"]) == 0
