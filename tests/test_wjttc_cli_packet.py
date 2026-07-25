"""WJTTC — T4 CLI seal/merge + no-clobber (28-T4-SCOPE C1–C4).

Thin shell tests: call ``cli.main([...])`` (same exit-code contract the
receipt script relies on). Library packet correctness lives in
``test_wjttc_packet.py``; this file only guards the CLI glue.
"""
from __future__ import annotations

from pathlib import Path

from claude_fafm_sdk.cli import main
from claude_fafm_sdk.merge import souls_equal
from claude_fafm_sdk.packet import from_packet
from claude_fafm_sdk.soul import Soul

NP = "tier2-cli-test"  # same namepoint required by merge_souls


def _init(path: Path, name: str = NP) -> None:
    assert main(["init", "-f", str(path), "-n", name, "--force"]) == 0


def _etch(path: Path, text: str, fid: str | None = None) -> None:
    args = ["etch", "-f", str(path), text]
    if fid:
        args.extend(["--id", fid])
    assert main(args) == 0


def test_c1_cli_seal_merge_roundtrip_logical(tmp_path: Path) -> None:
    a = tmp_path / "a.fafm"
    b = tmp_path / "b.fafm"
    pkt = tmp_path / "a.fafmp"
    _init(a)
    _etch(a, "tier2-proof-fact", fid="t2")
    assert main(["seal", "-f", str(a), "-o", str(pkt)]) == 0
    assert pkt.is_file() and pkt.stat().st_size > 16

    _init(b)
    assert main(["merge", "-f", str(b), str(pkt)]) == 0
    assert souls_equal(Soul.load(b), from_packet(pkt.read_bytes()))

    # recall path (stranger sees the fact)
    # etch id t2 — recall by text fragment
    rc = main(["recall", "-f", str(b), "tier2-proof"])
    assert rc == 0


def test_c2_cli_merge_bitflip_no_clobber(tmp_path: Path) -> None:
    a = tmp_path / "a.fafm"
    b = tmp_path / "b.fafm"
    good = tmp_path / "good.fafmp"
    bad = tmp_path / "bad.fafmp"
    _init(a)
    _etch(a, "should-not-arrive")
    assert main(["seal", "-f", str(a), "-o", str(good)]) == 0

    flipped = bytearray(good.read_bytes())
    flipped[16] ^= 0xFF  # payload bit-flip → CRC reject
    bad.write_bytes(bytes(flipped))

    _init(b)
    _etch(b, "local-only-fact", fid="local")
    before = b.read_bytes()
    assert main(["merge", "-f", str(b), str(bad)]) == 1  # falsifier: non-zero
    assert b.read_bytes() == before  # no clobber
    soul = Soul.load(b)
    assert len(soul.facts) == 1
    assert soul.facts[0].id == "local"


def test_c3_cli_double_merge_idempotent(tmp_path: Path) -> None:
    a = tmp_path / "a.fafm"
    b = tmp_path / "b.fafm"
    pkt = tmp_path / "a.fafmp"
    _init(a)
    _etch(a, "once-only", fid="once")
    assert main(["seal", "-f", str(a), "-o", str(pkt)]) == 0
    _init(b)
    assert main(["merge", "-f", str(b), str(pkt)]) == 0
    first = Soul.load(b)
    assert main(["merge", "-f", str(b), str(pkt)]) == 0
    second = Soul.load(b)
    assert len(first.facts) == len(second.facts) == 1
    assert souls_equal(first, second)


def test_c4_cli_both_ways_converge(tmp_path: Path) -> None:
    a = tmp_path / "a.fafm"
    b = tmp_path / "b.fafm"
    pa = tmp_path / "a.fafmp"
    pb = tmp_path / "b.fafmp"
    base = tmp_path / "empty.fafm"
    ab = tmp_path / "ab.fafm"
    ba = tmp_path / "ba.fafm"
    _init(a)
    _init(b)
    _etch(a, "fact-from-a", fid="fa")
    _etch(b, "fact-from-b", fid="fb")
    assert main(["seal", "-f", str(a), "-o", str(pa)]) == 0
    assert main(["seal", "-f", str(b), "-o", str(pb)]) == 0

    # Shared empty base — two separate inits can stamp different last_etched
    # and make max-register metadata diverge without any merge bug.
    _init(base)
    ab.write_bytes(base.read_bytes())
    ba.write_bytes(base.read_bytes())
    assert main(["merge", "-f", str(ab), str(pa)]) == 0
    assert main(["merge", "-f", str(ab), str(pb)]) == 0
    assert main(["merge", "-f", str(ba), str(pb)]) == 0
    assert main(["merge", "-f", str(ba), str(pa)]) == 0

    assert souls_equal(Soul.load(ab), Soul.load(ba))
    texts = {f.text for f in Soul.load(ab).facts}
    assert texts == {"fact-from-a", "fact-from-b"}


def test_cli_seal_missing_soul(tmp_path: Path) -> None:
    assert main(["seal", "-f", str(tmp_path / "nope.fafm")]) == 1


def test_cli_merge_missing_packet(tmp_path: Path) -> None:
    soul = tmp_path / "s.fafm"
    _init(soul)
    assert main(["merge", "-f", str(soul), str(tmp_path / "missing.fafmp")]) == 1
