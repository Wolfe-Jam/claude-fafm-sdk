"""WJTTC — Provable Receipt (1.3): the wheel-hosted Tier-2 proof + CLI `open`.

The `receipt` command is what makes `uvx claude-fafm-sdk receipt` runnable with
no git clone — so the receipt logic ships **in the package**, not only in the
bash `examples/` script. These guard the module + its two CLI verbs.
"""
from __future__ import annotations

import json
from pathlib import Path

from claude_fafm_sdk.cli import main
from claude_fafm_sdk.merge import souls_equal
from claude_fafm_sdk.packet import to_packet_file
from claude_fafm_sdk.receipt import run_receipt
from claude_fafm_sdk.soul import Fact, Soul


# ── R1 — receipt runs green ──────────────────────────────────────────────────
def test_r1_receipt_module_exit_zero():
    assert run_receipt() == 0


def test_r1_receipt_cli_exit_zero():
    assert main(["receipt"]) == 0


def test_r1_receipt_json(capsys):
    assert main(["receipt", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["pass"] is True
    names = {c["name"] for c in out["checks"]}
    # all four arc/falsifier checks present
    assert any("recall" in n for n in names)
    assert any("CRC" in n for n in names)
    assert any("idempotent" in n for n in names)
    assert any("both-ways" in n for n in names)
    assert all(c["ok"] for c in out["checks"])


# ── R2 — the receipt actually exercises the falsifiers (not a rubber stamp) ───
def test_r2_receipt_falsifiers_are_real(monkeypatch, capsys):
    # If the CRC guard were broken (from_packet accepted corrupt bytes), the
    # receipt's CRC-reject check must FAIL — proving the check has teeth.
    import claude_fafm_sdk.receipt as r

    def _accept_anything(_data):
        return Soul(r.NP)  # pretend a corrupt packet "opened"

    monkeypatch.setattr(r, "from_packet", _accept_anything)
    rc = run_receipt(as_json=True)
    out = json.loads(capsys.readouterr().out)
    crc = next(c for c in out["checks"] if "CRC" in c["name"])
    assert crc["ok"] is False  # the falsifier caught the (injected) break
    assert rc == 1  # overall receipt fails when a check fails


# ── O1 — CLI open round-trips the fact ───────────────────────────────────────
def test_o1_cli_open_roundtrip(tmp_path: Path):
    src = tmp_path / "s.fafm"
    pkt = tmp_path / "s.fafmp"
    out = tmp_path / "opened.fafm"
    assert main(["init", "-f", str(src), "-n", "@o", "--force"]) == 0
    assert main(["etch", "-f", str(src), "portable proof", "--id", "p"]) == 0
    assert main(["seal", "-f", str(src), "-o", str(pkt)]) == 0
    assert main(["open", str(pkt), "-o", str(out)]) == 0
    assert souls_equal(Soul.load(out), Soul.load(src))


def test_o1_cli_open_summary_exit_zero(tmp_path: Path):
    pkt = tmp_path / "x.fafmp"
    to_packet_file(Soul("@o", facts=[Fact(text="one", id="a")]), pkt)
    assert main(["open", str(pkt)]) == 0  # summary print path


# ── O2 — open fails closed on a bad packet ───────────────────────────────────
def test_o2_cli_open_bad_packet_exit_one(tmp_path: Path):
    bad = tmp_path / "bad.fafmp"
    good = to_packet_file(Soul("@o", facts=[Fact(text="t", id="a")]), tmp_path / "g.fafmp")
    flipped = bytearray(good.read_bytes())
    flipped[16] ^= 0xFF  # corrupt payload → CRC mismatch
    bad.write_bytes(bytes(flipped))
    assert main(["open", str(bad)]) == 1


def test_o2_cli_open_missing_packet_exit_one(tmp_path: Path):
    assert main(["open", str(tmp_path / "nope.fafmp")]) == 1


# ── W1 — the receipt ships in the package (wheel import smoke) ────────────────
def test_w1_receipt_module_importable_from_package():
    import importlib

    mod = importlib.import_module("claude_fafm_sdk.receipt")
    assert hasattr(mod, "run_receipt") and callable(mod.run_receipt)
