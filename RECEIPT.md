# RECEIPT.md — 60-second Tier-2 proof

**Provable Receipt (1.3):** the proof ships **in the package** — one command, no clone.
Local **file** transport only (`.fafmp`); not namepoint push/pull.

## Honesty

- **CRC = integrity, not authentication.** A bad packet is rejected; a good packet is not a signature.
- **Same namepoint** across replicas — `merge_souls` (and therefore CLI `merge`) requires it. Use `-n <handle>` on `init` for both sides.
- The receipt exercises **transport + ingest**; it does not re-prove the dual-implementation merge (that's the 1.1 story).

## One command — no git clone

```sh
uvx claude-fafm-sdk receipt          # → TIER-2 RECEIPT GREEN (exit 0)
uvx claude-fafm-sdk receipt --json   # machine-readable PASS/FAIL
```

Runs the whole arc — etch → seal → send a file → merge → recall — plus three
falsifiers (CRC reject · double-merge idempotent · both-ways converge). Exit 0
on pass; non-zero if any check fails.

## From a source checkout (equivalent)

```sh
bash examples/tier2_receipt.sh       # the shell version of the same arc
```

## Manual paste (A / B + falsifiers)

```sh
export PYTHONPATH=.   # from repo root if not installed
cli() { python -c 'import sys; from claude_fafm_sdk.cli import main; raise SystemExit(main(sys.argv[1:]))' "$@"; }

NP=tier2
A=/tmp/a.fafm; B=/tmp/b.fafm; PKT=/tmp/a.fafmp

# A
cli init -f "$A" -n "$NP" --force
cli etch -f "$A" "tier2-proof-fact" --id tier2
cli seal -f "$A" -o "$PKT"

# B (file send = share $PKT)
cli init -f "$B" -n "$NP" --force
cli merge -f "$B" "$PKT"
cli recall -f "$B" tier2-proof

# CRC reject → non-zero; B unchanged
python -c "p=bytearray(open('$PKT','rb').read()); p[16]^=0xFF; open('/tmp/bad.fafmp','wb').write(p)"
cli merge -f "$B" /tmp/bad.fafmp   # expect exit ≠ 0

# double-merge → still one logical copy of the fact
cli merge -f "$B" "$PKT"
```

## CLI surface

| Command | Role |
|---------|------|
| `claude-fafm-sdk receipt` | Run the 60-second Tier-2 proof (in-package) |
| `claude-fafm-sdk seal -f soul.fafm -o soul.fafmp` | Seal local soul → packet |
| `claude-fafm-sdk merge -f soul.fafm packet.fafmp` | CvRDT ingest; fail-closed |
| `claude-fafm-sdk open packet.fafmp [-o soul.fafm]` | Open a packet → `.fafm` or a summary (fail-closed) |

See `PACKET.md` for wire layout. See `MERGE.md` for the join.
