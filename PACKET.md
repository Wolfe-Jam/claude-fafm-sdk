# PACKET.md — Soul-Packet seal (`.fafmp`)

**Status:** T3-min (2026-07-24). **Transport only** — this seals a `Soul` into
bytes and opens it back; it does **not** touch the merge. Ingest reuses the
CvRDT: `merge_packet(local, data) == merge_souls(local, from_packet(data))`.

## Honesty (read this first)

- **CRC is INTEGRITY, not AUTHENTICATION.** A packet proves it was not
  *corrupted* in transit — not *who* sent it. There is **no signing and no
  encryption** in v0. Do not use a packet as a trust boundary.
- **`SPK1` is the Soul-Packet seal v0 — distinct from the project `FAFB`
  binary.** Extension `.fafmp`. **No IANA media type is claimed.** This is not
  the full FAFB section-mapped format.
- **Open fails closed.** Any bad magic / version / length / CRC / oversize /
  UTF-8 / YAML raises `PacketError` and returns **no partial `Soul`**.

## Wire layout (little-endian)

| offset | size | field   | value |
|-------:|-----:|---------|-------|
| 0      | 4    | magic   | `b"SPK1"` |
| 4      | 2    | version | `u16 = 1` |
| 6      | 2    | flags   | `u16 = 0` (reserved; ignored on read) |
| 8      | 4    | crc32   | `u32` — **CRC-32 of the PAYLOAD ONLY** (zlib / `binascii.crc32`, unsigned) |
| 12     | 4    | length  | `u32` — payload byte length |
| 16     | N    | payload | UTF-8 canonical `.fafm` YAML |

> **Interop note:** the CRC covers the **payload only**, never the header. A
> second implementation must CRC the payload bytes (offset 16..) — CRC-ing the
> header is the classic cross-language mismatch.

## Canonical payload

The payload is the whole soul as **canonical** `.fafm` YAML, produced by
`normalize_for_seal` + `to_canonical_yaml`:

- UTF-8; deterministic key order (`sort_keys=True`); block style; no line wrap.
- Facts in §5.4 order, with canonical priority + sorted tags/links (**raw text
  preserved**). Sessions sorted by `value_hash`. Index rebuilt.
- Empty-string timestamps are absent (normalized at the `Fact` model).
- Kept **separate** from `Soul.to_yaml()` (the human-facing save is unsorted /
  wrapped) so the pretty save and the sealed bytes never couple.

**Byte-identity:** two seals of the same **logical** state are byte-identical
(e.g. `to_packet(merge(a,b)) == to_packet(merge(b,a))`), and open→re-seal is a
no-op.

## API (`claude_fafm_sdk.packet`)

```python
to_packet(soul) -> bytes            # seal (canonical payload + CRC-32)
from_packet(data) -> Soul           # open, fail-closed (PacketError, no partial Soul)
merge_packet(local, data) -> Soul   # merge_souls(local, from_packet(data))
normalize_for_seal(soul) -> Soul    # pure: §5.4 + sorted sessions + rebuilt index
to_packet_file(soul, path) -> Path  # write a .fafmp file
from_packet_file(path) -> Soul      # read a .fafmp file
```

`PacketError(ValueError)` — every open failure, so callers catch sealed-transport
errors without swallowing unrelated `ValueError`s.

## Errors (fail closed)

| Condition | Result |
|-----------|--------|
| shorter than the 16-byte header | `PacketError` |
| bad magic / unsupported version | `PacketError` |
| declared length > 10 MiB cap | `PacketError` |
| length ≠ actual payload size | `PacketError` |
| CRC mismatch | `PacketError` |
| non-UTF-8 / YAML parse fail / not a mapping | `PacketError` |

No "best effort" partial soul, ever.

## Out of scope (v0)

Signing / encryption · tombstones / delete sync · CLI seal/merge · full FAFB
binary · IANA media type. Deletes remain out of the merge path (grow/update-only).
