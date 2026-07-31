#!/usr/bin/env bash
# Acid test — claude-fafm-sdk
#
# Same product path for pre-pub and post-pub; only the install *source* changes.
#
#   pre-pub:  --from wheel     (build local tree → install wheel into fresh venv)
#   pre-pub:  --from testpypi  (stranger install from TestPyPI)
#   post-pub: --from pypi      (default — live index; closes the release)
#
# Doctrine: "It works! (and we know it.)"
# Not the repo editable. Not version-string-only. Real CLI + packets (+ compact when present).
#
# Usage:
#   bash scripts/post-pub-acid-test.sh 1.7.0
#   bash scripts/post-pub-acid-test.sh 1.7.0 --from pypi
#   bash scripts/post-pub-acid-test.sh 1.7.0 --from wheel
#   bash scripts/post-pub-acid-test.sh 1.7.0 --from testpypi
#
# Exit: 0 = PASS · non-zero = FAIL

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PKG="claude-fafm-sdk"
CLI="claude-fafm-sdk"

VERSION="${1:-}"
FROM="pypi"
shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --from)
      FROM="${2:-}"
      shift 2
      ;;
    --from=*)
      FROM="${1#--from=}"
      shift
      ;;
    *)
      echo "Unknown arg: $1"
      exit 2
      ;;
  esac
done

if [[ -z "$VERSION" ]]; then
  echo "Usage: bash scripts/post-pub-acid-test.sh <VERSION> [--from pypi|testpypi|wheel]"
  exit 2
fi
case "$FROM" in
  pypi|testpypi|wheel) ;;
  *)
    echo "Invalid --from $FROM (use pypi|testpypi|wheel)"
    exit 2
    ;;
esac

WORKDIR=$(mktemp -d "/tmp/${PKG}-acid-${FROM}-${VERSION}-XXXXXX")
export UV_CACHE_DIR="$WORKDIR/uv-cache"
trap 'echo ""; echo "WORKDIR (kept): $WORKDIR"' EXIT

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ACID TEST  ·  $PKG==$VERSION  ·  from=$FROM"
echo " Clean venv · stranger install · not editable"
echo " WORKDIR=$WORKDIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd "$WORKDIR"

fail() { echo "❌ ACID FAIL: $*"; exit 1; }
pass() { echo "  ✅ $*"; }

# ── 1) Install ─────────────────────────────────────────────────────────────
echo ""
echo "=== 1) Install (from=$FROM) ==="
uv venv .venv >/dev/null
# shellcheck disable=SC1091
source .venv/bin/activate

case "$FROM" in
  pypi)
    uv pip install "${PKG}==${VERSION}" || fail "pip install ${PKG}==${VERSION} from PyPI"
    ;;
  testpypi)
    uv pip install \
      --index-url https://test.pypi.org/simple/ \
      --extra-index-url https://pypi.org/simple/ \
      "${PKG}==${VERSION}" || fail "pip install from TestPyPI"
    ;;
  wheel)
    echo "  building wheel in $REPO_ROOT …"
    (
      cd "$REPO_ROOT"
      rm -rf dist/
      # use isolated build; need build tooling in this venv
      uv pip install -q build
      python -m build -o "$WORKDIR/dist" >/dev/null
    ) || fail "python -m build"
    whl=$(ls "$WORKDIR/dist"/"${PKG//-/_}"-*.whl 2>/dev/null | head -1 || true)
    if [[ -z "$whl" ]]; then
      whl=$(ls "$WORKDIR/dist"/*.whl 2>/dev/null | head -1 || true)
    fi
    [[ -n "$whl" && -f "$whl" ]] || fail "no wheel in $WORKDIR/dist"
    uv pip install "$whl" || fail "pip install wheel $whl"
    # version must match wheel metadata (and caller expectation)
    ;;
esac

got=$(python -c "import claude_fafm_sdk; print(claude_fafm_sdk.__version__)")
[[ "$got" == "$VERSION" ]] || fail "import version $got != $VERSION (wanted $VERSION)"
cli_v=$($CLI --version 2>&1 | tr -d '\r')
echo "$cli_v" | grep -q "$VERSION" || fail "CLI version: $cli_v"
pass "install + import + CLI == $VERSION (from=$FROM)"

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
python -c "d=open('soul.fafmp','rb').read(4); assert d==b'SPK1', d" || fail "packet magic not SPK1"
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

# ── 7) Merge packet into peer ──────────────────────────────────────────────
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
import yaml
d = yaml.safe_load(open('soul.fafm'))
m = d.get('memory') or {}
assert 'tombstones' in m and len(m['tombstones']) >= 2, m.get('tombstones')
assert 'policies' in m and m['policies'], m.get('policies')
assert len(m.get('facts') or []) == 2, m.get('facts')
print('keys', sorted(m.keys()))
print('tombstones', len(m['tombstones']), 'policies', len(m['policies']), 'facts', len(m['facts']))
" || fail "wire peek"
pass "YAML: tombstones + policies + 2 facts"

# ── 9) Compact (when CLI has it — wheel/main; skip on older PyPI) ───────────
echo ""
echo "=== 9) compact --epoch (if available) ==="
if $CLI compact -h >/dev/null 2>&1; then
  AT_C="2026-07-31T00:00:00Z"
  $CLI compact --epoch -f soul.fafm --at "$AT_C" --archive soul.epoch0.fafm || fail "compact"
  [[ -f soul.epoch0.fafm ]] || fail "missing archive soul.epoch0.fafm"
  debt0=$($CLI debt -f soul.fafm 2>&1)
  echo "$debt0" | grep -qE "tombstones:[[:space:]]+0" || fail "post-compact debt should be 0: $debt0"
  python -c "
from claude_fafm_sdk import Soul
live = Soul.load('soul.fafm')
arch = Soul.load('soul.epoch0.fafm')
assert live.epoch == 1, live.epoch
assert arch.epoch == 0, arch.epoch
assert len(live.tombstones) == 0
assert len(arch.tombstones) >= 1
print('live epoch', live.epoch, 'arch epoch', arch.epoch, 'receipts', len(live.compaction_receipts))
" || fail "compact epoch/archive checks"
  pass "compact epoch 0→1 · debt 0 · archive retained"
else
  echo "  ⏭  compact CLI not in this build (e.g. PyPI 1.7.0) — skip"
fi

# ── Receipt ────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ✅ ACID TEST PASS  ·  $PKG==$VERSION  ·  from=$FROM"
echo " It works! (and we know it.)"
if [[ "$FROM" == "pypi" ]]; then
  echo " Release close receipt (live index)."
elif [[ "$FROM" == "wheel" ]]; then
  echo " Pre-pub receipt (local wheel) — still run --from pypi after publish."
else
  echo " Pre-pub receipt (TestPyPI) — still run --from pypi after publish."
fi
echo " WORKDIR=$WORKDIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
exit 0
