#!/usr/bin/env bash
# Post-Pub Acid Test — claude-fafm-sdk
#
# Doctrine: After software is released, this is the norm — not optional polish.
# Clean install from the INDEX (PyPI), not the repo. Real commands. Real packets.
# "It works! (and we know it.)" — a great receipt.
#
# Usage:
#   bash scripts/post-pub-acid-test.sh [VERSION]
#   bash scripts/post-pub-acid-test.sh 1.7.0
#   VERSION defaults to __version__ in the package on PyPI if omitted → pass explicitly.
#
# Exit: 0 = PASS receipt · non-zero = FAIL (release not closed)

set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  echo "Usage: bash scripts/post-pub-acid-test.sh <VERSION>"
  echo "  e.g. bash scripts/post-pub-acid-test.sh 1.7.0"
  exit 2
fi

PKG="claude-fafm-sdk"
CLI="claude-fafm-sdk"
WORKDIR=$(mktemp -d "/tmp/${PKG}-acid-${VERSION}-XXXXXX")
export UV_CACHE_DIR="$WORKDIR/uv-cache"
trap 'echo ""; echo "WORKDIR (kept): $WORKDIR"' EXIT

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " POST-PUB ACID TEST  ·  $PKG==$VERSION"
echo " Clean venv · PyPI only · not the repo"
echo " WORKDIR=$WORKDIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd "$WORKDIR"

fail() { echo "❌ ACID FAIL: $*"; exit 1; }
pass() { echo "  ✅ $*"; }

# ── 1) Install from PyPI ───────────────────────────────────────────────────
echo ""
echo "=== 1) Install from PyPI ==="
uv venv .venv >/dev/null
# shellcheck disable=SC1091
source .venv/bin/activate
uv pip install "${PKG}==${VERSION}" || fail "pip install ${PKG}==${VERSION}"
got=$(python -c "import claude_fafm_sdk; print(claude_fafm_sdk.__version__)")
[[ "$got" == "$VERSION" ]] || fail "import version $got != $VERSION"
cli_v=$($CLI --version 2>&1 | tr -d '\r')
echo "$cli_v" | grep -q "$VERSION" || fail "CLI version: $cli_v"
pass "install + import + CLI == $VERSION"

# ── 2) Core soul loop ──────────────────────────────────────────────────────
echo ""
echo "=== 2) init · etch · ls ==="
$CLI init -f soul.fafm -n @acid-test || fail "init"
$CLI etch "ships uv-first" -f soul.fafm --id install --priority high || fail "etch install"
$CLI etch "ephemeral note" -f soul.fafm --id temp --priority ephemeral || fail "etch temp"
$CLI etch "id-less portable fact" -f soul.fafm || fail "etch id-less"
ls_out=$($CLI ls -f soul.fafm 2>&1)
echo "$ls_out" | grep -q "3 facts" || fail "expected 3 facts: $ls_out"
pass "init / etch / ls (3 facts)"

# ── 3) Forget + debt ───────────────────────────────────────────────────────
echo ""
echo "=== 3) forget · debt ==="
$CLI forget temp -f soul.fafm || fail "forget"
debt_out=$($CLI debt -f soul.fafm 2>&1)
echo "$debt_out" | grep -q "tombstones:" || fail "debt missing tombstones line"
echo "$debt_out" | grep -qE "tombstones:[[:space:]]+[1-9]" || fail "expected ≥1 tombstone: $debt_out"
pass "forget + debt (graveyard visible)"

# ── 4) Policy propose / apply ──────────────────────────────────────────────
echo ""
echo "=== 4) policy ==="
$CLI policy set drop-eph --priority-lte ephemeral -f soul.fafm || fail "policy set"
$CLI etch "another ephemeral" -f soul.fafm --id e2 --priority ephemeral || fail "etch e2"
$CLI policy list -f soul.fafm | grep -q "drop-eph" || fail "policy list"
AT="2026-07-30T18:00:00Z"
$CLI policy propose --at "$AT" -f soul.fafm | grep -q "e2" || fail "policy propose"
$CLI policy apply --yes --at "$AT" -f soul.fafm || fail "policy apply"
ls2=$($CLI ls -f soul.fafm 2>&1)
echo "$ls2" | grep -q "2 facts" || fail "expected 2 facts after apply: $ls2"
debt2=$($CLI debt -f soul.fafm 2>&1)
echo "$debt2" | grep -qE "tombstones:[[:space:]]+2" || fail "expected 2 tombstones: $debt2"
pass "policy propose/apply + debt=2"

# ── 5) Seal packet · open · magic ──────────────────────────────────────────
echo ""
echo "=== 5) seal · open packet ==="
$CLI seal -f soul.fafm -o soul.fafmp || fail "seal"
[[ -f soul.fafmp ]] || fail "missing soul.fafmp"
# SPK1 magic
head -c 4 soul.fafmp | od -An -tx1 | grep -qi "53 50 4b 31\|53504b31" \
  || python -c "d=open('soul.fafmp','rb').read(4); assert d==b'SPK1', d" \
  || fail "packet magic not SPK1"
open_out=$($CLI open soul.fafmp 2>&1)
echo "$open_out" | grep -q "2 facts" || fail "open facts: $open_out"
echo "$open_out" | grep -qi "install" || fail "open missing install"
pass "seal SPK1 + open (2 facts)"

# ── 6) Residual risk-scan ──────────────────────────────────────────────────
echo ""
echo "=== 6) risk-scan ==="
mkdir -p backup
cp soul.fafm backup/soul-copy.fafm
cp soul.fafmp backup/packet-copy.fafmp
scan=$($CLI risk-scan . backup 2>&1)
echo "$scan" | grep -qi "packet" || fail "scan missing packet: $scan"
echo "$scan" | grep -qi "soul" || fail "scan missing soul: $scan"
echo "$scan" | grep -qiE "not a wipe|not legal|residual" || fail "scan missing honesty note"
pass "risk-scan finds copies + honesty note"

# ── 7) Merge packet into peer (convergent forget travels) ──────────────────
echo ""
echo "=== 7) merge packet → peer ==="
$CLI init -f peer.fafm -n @acid-test || fail "peer init"
$CLI etch "peer only fact" -f peer.fafm --id peer1 || fail "peer etch"
$CLI merge -f peer.fafm soul.fafmp || fail "merge"
peer_ls=$($CLI ls -f peer.fafm 2>&1)
echo "$peer_ls" | grep -q "3 facts" || fail "peer after merge: $peer_ls"
peer_debt=$($CLI debt -f peer.fafm 2>&1)
echo "$peer_debt" | grep -qE "tombstones:[[:space:]]+2" || fail "peer debt should carry 2 stones: $peer_debt"
pass "merge: 3 facts + tombstones traveled (debt=2)"

# ── 8) Wire peek ───────────────────────────────────────────────────────────
echo ""
echo "=== 8) wire peek ==="
python -c "
import yaml, sys
d = yaml.safe_load(open('soul.fafm'))
m = d.get('memory') or {}
assert 'tombstones' in m and len(m['tombstones']) >= 2, m.get('tombstones')
assert 'policies' in m and m['policies'], m.get('policies')
assert len(m.get('facts') or []) == 2, m.get('facts')
print('keys', sorted(m.keys()))
print('tombstones', len(m['tombstones']), 'policies', len(m['policies']), 'facts', len(m['facts']))
" || fail "wire peek"
pass "YAML: tombstones + policies + 2 facts"

# ── Receipt ────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ✅ POST-PUB ACID TEST PASS  ·  $PKG==$VERSION"
echo " It works! (and we know it.)"
echo " WORKDIR=$WORKDIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
exit 0
