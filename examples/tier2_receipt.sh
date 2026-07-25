#!/usr/bin/env bash
# Tier-2 stranger receipt (T4) — ~60s product proof of sealed Soul-Packet travel.
#
# Arc:
#   A: init → etch → seal (.fafmp)
#   A→B: file send (cp — air-gap friendly; not namepoint)
#   B: merge → recall
# Falsifiers:
#   · CRC reject (bit-flip) → non-zero exit, B soul not clobbered
#   · double-merge → idempotent (no dup facts)
#   · both-ways → same logical soul
#
# Run from a checkout (or any env with the package importable):
#   bash examples/tier2_receipt.sh
# Or:  make receipt  (if wired) / pytest tests/test_wjttc_cli_packet.py
#
# Honesty: CRC = integrity, NOT authentication. PyPI may still be older than
# this mainline until a T5 release ships seal/merge.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"

cli() {
  # Same entry as the installed console script — exit codes are the falsifier contract.
  python -c 'import sys; from claude_fafm_sdk.cli import main; raise SystemExit(main(sys.argv[1:]))' "$@"
}

WORKDIR="${TMPDIR:-/tmp}/fafm-tier2-$$"
mkdir -p "$WORKDIR"
trap 'rm -rf "$WORKDIR"' EXIT

NP="tier2-receipt"   # merge_souls requires same namepoint across replicas
A="$WORKDIR/a.fafm"
B="$WORKDIR/b.fafm"
PKT="$WORKDIR/a.fafmp"
BAD="$WORKDIR/bad.fafmp"
FACT="tier2-proof-fact"

echo "=== Tier-2 receipt @ $WORKDIR ==="

# ── A: etch → seal ──────────────────────────────────────────────────────────
cli init -f "$A" -n "$NP" --force
cli etch -f "$A" "$FACT" --id tier2
cli seal -f "$A" -o "$PKT"
test -s "$PKT"

# ── B: merge → recall (file "send" = the packet path) ───────────────────────
cli init -f "$B" -n "$NP" --force
cli merge -f "$B" "$PKT"
OUT="$(cli recall -f "$B" tier2-proof || true)"
echo "$OUT" | grep -q "$FACT"

# ── Falsifier 1: CRC reject + no clobber ─────────────────────────────────────
python -c "
p = bytearray(open('$PKT','rb').read())
p[16] ^= 0xFF
open('$BAD','wb').write(p)
"
BEFORE="$(wc -c < "$B" | tr -d ' ')"
set +e
cli merge -f "$B" "$BAD"
RC=$?
set -e
test "$RC" -ne 0
AFTER="$(wc -c < "$B" | tr -d ' ')"
test "$BEFORE" = "$AFTER"
# local fact count still 1 (the merged A fact only — no corruption path)
COUNT="$(python -c "from claude_fafm_sdk.soul import Soul; print(len(Soul.load('$B').facts))")"
test "$COUNT" = "1"

# ── Falsifier 2: double-merge no-op (idempotent) ────────────────────────────
cli merge -f "$B" "$PKT"
COUNT2="$(python -c "from claude_fafm_sdk.soul import Soul; print(len(Soul.load('$B').facts))")"
test "$COUNT2" = "1"

# ── Falsifier 3: both-ways converge ─────────────────────────────────────────
# Start AB and BA from the *same* empty base so wall-clock created/last_etched
# on two separate `init`s cannot pollute the max/min registers (empty replicas
# stamped at different seconds are different starting states — not a merge bug).
A2="$WORKDIR/a2.fafm"
B2="$WORKDIR/b2.fafm"
PA="$WORKDIR/pa.fafmp"
PB="$WORKDIR/pb.fafmp"
BASE="$WORKDIR/empty.fafm"
AB="$WORKDIR/ab.fafm"
BA="$WORKDIR/ba.fafm"
cli init -f "$A2" -n "$NP" --force
cli init -f "$B2" -n "$NP" --force
cli etch -f "$A2" "from-a" --id fa
cli etch -f "$B2" "from-b" --id fb
cli seal -f "$A2" -o "$PA"
cli seal -f "$B2" -o "$PB"
cli init -f "$BASE" -n "$NP" --force
cp "$BASE" "$AB"
cp "$BASE" "$BA"
cli merge -f "$AB" "$PA"
cli merge -f "$AB" "$PB"
cli merge -f "$BA" "$PB"
cli merge -f "$BA" "$PA"
python -c "
from claude_fafm_sdk.merge import souls_equal
from claude_fafm_sdk.soul import Soul
assert souls_equal(Soul.load('$AB'), Soul.load('$BA')), 'both-ways diverge'
"

echo ""
echo "=== TIER-2 RECEIPT GREEN ==="
echo "  etch → seal → file → merge → recall  OK"
echo "  CRC-reject → non-zero, no clobber    OK"
echo "  double-merge idempotent              OK"
echo "  both-ways converge                   OK"
echo "  (CRC = integrity only; not auth; not a published-claim gate until T5)"
exit 0
