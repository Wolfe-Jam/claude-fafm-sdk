#!/usr/bin/env bash
# Doc identity gate for claude-fafm-sdk (de-faffed but disciplined).
# Version · What's New hero · CHANGELOG top · short lead agreement.
# Usage: bash scripts/doc-gate.sh
set -euo pipefail
cd "$(dirname "$0")/.."

pkg=$(python3 -c "import re; t=open('claude_fafm_sdk/__init__.py').read(); print(re.search(r'__version__\s*=\s*\"([^\"]+)\"', t).group(1))")
if [[ -z "$pkg" ]]; then
  echo "❌ __version__ unreadable"
  exit 1
fi

drift=0

# CHANGELOG top ## [X.Y.Z]
top=$(grep -oE '^## \[[0-9]+\.[0-9]+\.[0-9]+\]' CHANGELOG.md | head -1 | tr -d '[]# ' || true)
if [[ "$top" != "$pkg" ]]; then
  echo "❌ CHANGELOG top = $top (expected $pkg)"
  drift=1
else
  echo "  ✅ CHANGELOG top $pkg"
fi

# README "What's New in X.Y.Z"
wn=$(grep -oE "What's New in [0-9]+\.[0-9]+\.[0-9]+" README.md | head -1 | sed 's/What.s New in //' || true)
if [[ "$wn" != "$pkg" ]]; then
  echo "❌ README What's New = $wn (expected $pkg)"
  drift=1
else
  echo "  ✅ README What's New $pkg"
fi

# README current release stamp (badge-independent)
if ! grep -qE "\*\*Release\*\*.*${pkg//./\\.}" README.md && ! grep -qE "claude-fafm-sdk/${pkg//./\\.}" README.md; then
  # require either Release table or pypi link with version
  if ! grep -q "$pkg" README.md; then
    echo "❌ README missing version stamp $pkg"
    drift=1
  else
    echo "  ✅ README mentions $pkg"
  fi
else
  echo "  ✅ README release stamp $pkg"
fi

# Short lead: CHANGELOG first bold line after ## [ver] should appear in README
lead=$(awk "/^## \\[${pkg}\\]/{p=1;next} p&&/^\*\*/{print; exit}" CHANGELOG.md | sed 's/^\*\*//;s/\*\*$//' || true)
if [[ -n "$lead" ]]; then
  # first 40 chars of lead should appear in README (allow soft wrap)
  snippet=$(printf '%s' "$lead" | head -c 48)
  if ! grep -qF "$snippet" README.md; then
    echo "❌ README missing CHANGELOG short lead snippet: ${snippet}…"
    drift=1
  else
    echo "  ✅ short lead present in README"
  fi
fi

# CITATION.cff version if present
if [[ -f CITATION.cff ]]; then
  cv=$(grep -E '^version:' CITATION.cff | head -1 | sed 's/.*"\([^"]*\)".*/\1/;s/version: *//;s/"//g' | tr -d ' ')
  if [[ -n "$cv" && "$cv" != "$pkg" ]]; then
    echo "❌ CITATION.cff version = $cv (expected $pkg)"
    drift=1
  else
    echo "  ✅ CITATION.cff $pkg"
  fi
fi

if [[ "$drift" -ne 0 ]]; then
  echo "🚫 Doc Gate REFUSED — identity drift on v$pkg"
  exit 1
fi
echo "✅ Doc Gate: identity agrees on v$pkg"
