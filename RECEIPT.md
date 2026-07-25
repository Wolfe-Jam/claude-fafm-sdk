# RECEIPT.md — 60-second Tier-2 proof (T4)

**Status:** T4-min. Local **file** transport only (`.fafmp`). Not namepoint push/pull.

## Honesty

- **CRC = integrity, not authentication.** A bad packet is rejected; a good packet is not a signature.
- **Same namepoint** across replicas — `merge_souls` (and therefore CLI `merge`) requires it. Use `-n <handle>` on `init` for both sides.
- **Unreleased until T5:** seal/merge may live on `main` while PyPI is still older. Run against a checkout or a post-T5 install.

## One command

```sh
bash examples/tier2_receipt.sh
```

Expect: `TIER-2 RECEIPT GREEN` and exit 0.

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
| `claude-fafm-sdk seal -f soul.fafm -o soul.fafmp` | Seal local soul → packet |
| `claude-fafm-sdk merge -f soul.fafm packet.fafmp` | CvRDT ingest; fail-closed |

See `PACKET.md` for wire layout. See `MERGE.md` for the join.
