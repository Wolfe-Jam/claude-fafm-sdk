"""WJTTC — CLI compact / migrate (MERGE §11 Z7 archive-first + E2 migrate).

Product law: compact and project-live migrate refuse without archive ack.
Library compact_epoch does not enforce disk archive — CLI does.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from claude_fafm_sdk.cli import main
from claude_fafm_sdk.soul import Soul

AT = "2026-07-30T12:00:00Z"
NP = "cli-compact-test"


def _seed(path: Path) -> None:
    assert main(["init", "-f", str(path), "-n", NP, "--force"]) == 0
    assert main(["etch", "-f", str(path), "keep-me", "--id", "k"]) == 0
    assert main(["etch", "-f", str(path), "drop-me", "--id", "d"]) == 0
    assert main(["forget", "-f", str(path), "d"]) == 0


# ── Z7 — archive-first (MERGE §11.4 / §11.8) ─────────────────────────────────


def test_z7_compact_refuses_without_archive(tmp_path: Path, capsys) -> None:
    soul = tmp_path / "soul.fafm"
    _seed(soul)
    capsys.readouterr()
    rc = main(["compact", "--epoch", "-f", str(soul), "--at", AT])
    assert rc == 1
    err = capsys.readouterr().out.lower()
    assert "archive" in err
    # soul unchanged — still epoch 0 with tombstone
    s = Soul.load(soul)
    assert s.epoch == 0
    assert len(s.tombstones) >= 1


def test_z7_compact_with_archive_pays_debt(tmp_path: Path, capsys) -> None:
    soul = tmp_path / "soul.fafm"
    arch = tmp_path / "soul.epoch0.fafm"
    _seed(soul)
    before = Soul.load(soul)
    assert before.epoch == 0
    assert len(before.tombstones) >= 1
    capsys.readouterr()
    rc = main(
        [
            "compact",
            "--epoch",
            "-f",
            str(soul),
            "--at",
            AT,
            "--archive",
            str(arch),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out.lower()
    assert "archived" in out
    assert "compacted" in out
    assert arch.is_file()
    arch_soul = Soul.load(arch)
    assert arch_soul.epoch == 0
    assert len(arch_soul.tombstones) >= 1
    after = Soul.load(soul)
    assert after.epoch == 1
    assert after.tombstones == {}
    assert any(f.id == "k" for f in after.facts)
    assert not any(f.id == "d" for f in after.facts)


def test_z7_compact_i_archived_override(tmp_path: Path, capsys) -> None:
    soul = tmp_path / "soul.fafm"
    _seed(soul)
    capsys.readouterr()
    rc = main(
        [
            "compact",
            "--epoch",
            "-f",
            str(soul),
            "--at",
            AT,
            "--i-archived",
            "--archive-ref",
            "manual-backup",
        ]
    )
    assert rc == 0
    after = Soul.load(soul)
    assert after.epoch == 1
    assert after.tombstones == {}
    assert after.compaction_receipts
    assert after.compaction_receipts[-1].archive_ref == "manual-backup"


def test_z7_compact_missing_at_is_usage_error(tmp_path: Path) -> None:
    soul = tmp_path / "soul.fafm"
    _seed(soul)
    # argparse --at is required=True on compact
    with pytest.raises(SystemExit):
        main(
            [
                "compact",
                "--epoch",
                "-f",
                str(soul),
                "--archive",
                str(tmp_path / "a.fafm"),
            ]
        )


# ── migrate CLI (E2) ─────────────────────────────────────────────────────────


def test_migrate_project_live_archive_first(tmp_path: Path, capsys) -> None:
    soul = tmp_path / "soul.fafm"
    arch = tmp_path / "pre.fafm"
    _seed(soul)
    capsys.readouterr()
    # refuse without archive
    assert (
        main(["migrate", "--to", "3", "--mode", "project-live", "-f", str(soul), "--at", AT])
        == 1
    )
    assert "archive" in capsys.readouterr().out.lower()
    assert Soul.load(soul).epoch == 0

    rc = main(
        [
            "migrate",
            "--to",
            "3",
            "--mode",
            "project-live",
            "-f",
            str(soul),
            "--at",
            AT,
            "--archive",
            str(arch),
        ]
    )
    assert rc == 0
    after = Soul.load(soul)
    assert after.epoch == 3
    assert after.tombstones == {}
    assert any(f.id == "k" for f in after.facts)
    assert not any(f.id == "d" for f in after.facts)
    assert arch.is_file() and Soul.load(arch).epoch == 0


def test_migrate_refuse_same_epoch_no_write(tmp_path: Path, capsys) -> None:
    soul = tmp_path / "soul.fafm"
    _seed(soul)
    capsys.readouterr()
    rc = main(["migrate", "--to", "0", "--mode", "refuse", "-f", str(soul)])
    assert rc == 0
    assert "refuse" in capsys.readouterr().out.lower()
    assert Soul.load(soul).epoch == 0


def test_migrate_refuse_cross_epoch_exits_1(tmp_path: Path, capsys) -> None:
    soul = tmp_path / "soul.fafm"
    _seed(soul)
    capsys.readouterr()
    rc = main(["migrate", "--to", "2", "--mode", "refuse", "-f", str(soul)])
    assert rc == 1
    assert "refuse" in capsys.readouterr().out.lower()
    assert Soul.load(soul).epoch == 0


def test_migrate_project_live_requires_at(tmp_path: Path, capsys) -> None:
    soul = tmp_path / "soul.fafm"
    _seed(soul)
    capsys.readouterr()
    rc = main(
        [
            "migrate",
            "--to",
            "1",
            "--mode",
            "project-live",
            "-f",
            str(soul),
            "--i-archived",
        ]
    )
    assert rc == 1
    out = capsys.readouterr().out.lower()
    assert "at" in out
