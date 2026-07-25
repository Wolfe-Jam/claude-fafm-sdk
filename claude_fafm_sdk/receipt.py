"""Provable Receipt — the 60-second Tier-2 proof as one command, shipped in the wheel.

`uvx claude-fafm-sdk receipt` runs the whole Sendable-Memory arc — etch → seal →
send a file → merge → recall — and **falsifies** it (CRC reject · double-merge
idempotent · both-ways converge). Exit 0 + a GREEN banner on pass; non-zero if any
check fails.

This is transport + ingest exercised end-to-end. It does **not** re-prove the
dual-implementation merge (that stays the 1.1 story) and CRC is integrity, not
authentication. A reader who runs this IS the public proof — no git clone needed.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Callable

from .merge import souls_equal
from .packet import (
    PacketError,
    from_packet,
    from_packet_file,
    merge_packet,
    to_packet,
    to_packet_file,
)
from .soul import Soul

NP = "@receipt-demo"  # one namepoint — every soul here is mergeable
_FACT = "provable receipt — memory that ships its own proof"


def _copy(soul: Soul) -> Soul:
    """Deep copy preserving created/last_etched — a *shared empty base* for the
    both-ways check (two separate inits would stamp different clocks; T4 lesson)."""
    return Soul.from_doc(soul.to_doc())


def run_receipt(as_json: bool = False) -> int:
    """Run the Tier-2 arc + falsifiers. Return 0 (all pass) or 1 (any fail)."""
    checks: list[dict] = []

    def check(name: str, fn: Callable[[], bool]) -> None:
        try:
            ok = bool(fn())
            detail = ""
        except Exception as e:  # a raised falsifier that shouldn't raise = fail
            ok, detail = False, f"{type(e).__name__}: {e}"
        checks.append({"name": name, "ok": ok, "detail": detail})

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # ── happy path: A etch → seal (to file) → send → B merge → recall ──────
        def happy() -> bool:
            a = Soul(NP)
            a.etch(_FACT, id="why")
            pkt_path = to_packet_file(a, tmp / "a.fafmp")  # seal → a real file
            b = merge_packet(Soul(NP), pkt_path.read_bytes())  # send + merge
            recalled = b.get_fact("why")
            return recalled is not None and recalled.text == _FACT

        check("etch → seal → send → merge → recall", happy)

        # cache one good packet for the falsifiers
        seed = Soul(NP)
        seed.etch(_FACT, id="why")
        good = to_packet(seed)

        # ── falsifier 1: CRC reject — a bit-flip must fail closed ─────────────
        def crc_reject() -> bool:
            bad = bytearray(good)
            bad[len(good) // 2] ^= 0xFF  # flip a payload byte
            try:
                from_packet(bytes(bad))
                return False  # opened corrupt bytes = FAIL
            except PacketError:
                return True  # rejected = PASS

        check("CRC-reject — bit-flip rejected (fail-closed)", crc_reject)

        # ── falsifier 2: double-merge idempotent ──────────────────────────────
        def double_merge() -> bool:
            once = merge_packet(Soul(NP), good)
            twice = merge_packet(once, good)
            return souls_equal(once, twice)

        check("double-merge idempotent", double_merge)

        # ── falsifier 3: both-ways converge (shared empty base) ───────────────
        def both_ways() -> bool:
            base = Soul(NP)
            a = _copy(base)
            a.etch("fact-from-a", id="fa")
            b = _copy(base)
            b.etch("fact-from-b", id="fb")
            pa = to_packet_file(a, tmp / "ba.fafmp").read_bytes()
            pb = to_packet_file(b, tmp / "bb.fafmp").read_bytes()
            ab = merge_packet(merge_packet(_copy(base), pa), pb)
            ba = merge_packet(merge_packet(_copy(base), pb), pa)
            texts = {f.text for f in ab.facts}
            return souls_equal(ab, ba) and texts == {"fact-from-a", "fact-from-b"}

        check("both-ways converge", both_ways)

    all_ok = all(c["ok"] for c in checks)

    if as_json:
        print(json.dumps({"receipt": "tier-2", "version": "1.3", "pass": all_ok,
                          "checks": checks}, indent=2))
    else:
        _print_banner(checks, all_ok)
    return 0 if all_ok else 1


def _print_banner(checks: list[dict], all_ok: bool) -> None:
    head = "=== TIER-2 RECEIPT GREEN ===" if all_ok else "=== TIER-2 RECEIPT FAILED ==="
    print(head)
    for c in checks:
        mark = "OK  " if c["ok"] else "FAIL"
        line = f"  {c['name']:<40} {mark}"
        if c["detail"] and not c["ok"]:
            line += f"  ({c['detail']})"
        print(line)
    print("  (CRC = integrity only; not authentication. Ingest is the same 1.1 CvRDT.)")
