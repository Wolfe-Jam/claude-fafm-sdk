# MERGE.md — `.fafm` Soul merge (Soul-Packet v1.1 track)

**Status:** FROZEN spec for v1 merge (2026-07-24). Authored against a frozen encoding lock; the §8a gap-decisions (G1–G5) were resolved deterministically and confirmed by an independent oracle. Two independent implementations (an N-version differential) are held to this spec; on conflict with stale prose, the locked §8a gap-decisions control.

**NOT part of v1.0 INTEROP.** Merge is a v1.1 / Soul-Packet feature. `Soul.add` (single-replica overwrite) is unchanged; `Soul.merge` is the multi-replica, coordinator-free join defined here.

**Label:** the dual-implementation differential is green and independently re-verified ⇒ unqualified **"CvRDT"** (state-based; two independent implementations under encoding lock v1.1 + the §8a gap-decisions + the empty-timestamp pin). Always **grow/update-only** — deletes-converge is **never** claimed in v1 (§6).

**Packet transport (T3):** a sealed `.fafmp` packet ingests through this same merge — `merge_packet(local, data) = merge_souls(local, from_packet(data))`. The seal is transport only; the merge is unchanged. See `PACKET.md`.

---

## 1. Type

A **state-based CvRDT** — a product of join-semilattices, merged whole-state:

```
Soul ≅  LWW-Element-Map (facts by id)          # scalar fields per id
      ⨯ G-Set            (id-less facts)         # by normalized text
      ⨯ OR/G-Set         (tags, links per fact)  # set-union
      ⨯ LWW-Map          (Fact.extra per key)    # per-key LWW by value_hash (G2)
      ⨯ max-register      (last_etched)
      ⨯ G-Set            (sessions list entries)                     # by value_hash (G1)
      ⨯ LWW-Map          (preferences/custom/extra/memory_extra)     # {v,t} per key
      + derived view      (index — recomputed, never merged)
```

`merge` is commutative · associative · idempotent (least-upper-bound). No coordinator, no ordering authority.

## 2. Preconditions
- **Same `namepoint`** required (different namepoints are not one soul's lattice) → else raise.
- `created` = `min(a, b)`. `last_etched` = `max(a, b)` (RFC3339-Z lexicographic).
- `index` is **never a merge input**; it is recomputed after merge (§7).

## 3. The LWW key (total order — the hinge)

```
lww_key(fact) = ( fact.timestamp or "",                     # missing/empty sorts lowest
                  PRIORITY_RANK[canonical_priority(prio)],  # ephemeral0<standard1<high2<critical3
                  fact.id or "",
                  content_hash(fact) )                       # §5 — final total tiebreak (mandatory)
greater key WINS.
```

## 4. Facts

### 4a. Facts WITH `id` — LWW-Element-Map, merged **field-level** (deltas #2/#3)
For the two facts sharing an id (`hi` = greater **`_scalar_lww_key`**, `lo` = other — **G3**, not full `lww_key`):
- **scalar fields** (`text`, `type`, `priority`, `timestamp`, `source`) ← from **`hi`** (LWW-Register). Stored `text` is **`normalize_text(hi.text)`** (NFC+strip — **G5**), never raw whitespace.
- **`tags`** ← **set-union** of both, emitted **sorted asc**.
- **`links`** ← **set-union** of both, emitted **sorted asc**.
- **`Fact.extra`** ← **per-key LWW by value_hash (G2)**: union of keys; shared key resolved to the value with the **greater `value_hash`** (SHA-256 of canonical JSON of the value); loser-only keys kept. **No** per-key timestamp; **not** whole-fact `lww_key` override (that re-introduces fold-order sensitivity — rejected for v1).

> ⚠️ Explicit: this is **not** whole-fact replace. `tags`/`links`/`extra` merge across both facts even though scalars come from the winner. (Q2's "whole-fact replace" is refined by deltas #2/#3.)
> ⚠️ **Scalar winner is `_scalar_lww_key` (§8a G3), independent of `tags`/`links`/`extra`.** The full `lww_key` (with `content_hash`) is used **only** for the id-less G-Set winner and the §5.4 sort — using it here would let a mid-fold tag union flip the scalar winner and break associativity.

### 4b. Facts WITHOUT `id` — G-Set, by **normalized text**
- Membership key = `normalized_text` (§5). One slot per normalized text.
- If ≥2 id-less facts share a `normalized_text`, keep the one with the **greater `lww_key`**; the stored `text` is **`normalize_text(winner.text)`** (NFC+strip — **G5**), not raw. (Candidates already share a normalized text; other fields may differ, so the winner is still the max-`lww_key` candidate.)

### 4c. `add` collision within one soul (pre-merge) is unchanged (overwrite by id). Merge is the cross-replica op.

## 5. Encodings (PINNED — byte-identical across implementations)

### 5.1 `normalize_text`
```python
normalized_text = unicodedata.normalize("NFC", text).strip()
```
No casefold, no internal-whitespace collapse. Applied **once** on merge input, used for **both** the G-Set key and the `text` field inside the content-hash JSON.

### 5.2 `content_hash`
`SHA-256` (lowercase hex, 64 chars) over **UTF-8** bytes of **canonical JSON**:
```python
json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
```
Object fields (omit a key when value is `None`/missing/empty; **bare** fact = `text` only):
| key | rule |
|-----|------|
| `text` | `normalize_text(text)` |
| `priority` | `canonical_priority(...)` — **included on any non-bare fact** |
| `id` | if present |
| `type` | if present |
| `tags` | JSON array, **sorted asc** |
| `links` | JSON array, **sorted asc** |
| `timestamp` | as stored, if present |
| `source` | if present |
| `extra` | JSON object, keys sorted (values canonical recursively) |

**Bare fact** (no id/type/tags/links/timestamp/source/extra and priority `standard`) → hash object is `{"text": normalize_text(text)}` only.

**Empty timestamp = ABSENT (encoding-lock pin).** `timestamp` is absent for **both** bareness and `content_hash` inclusion iff it is **falsy**: `timestamp_absent(t) ⇔ t is None or t == ""`. `_is_bare` MUST use `not f.timestamp` (the same predicate as the `if f.timestamp:` hash guard), never `is None` alone — otherwise a `ts=""` otherwise-bare fact hashes as `{"text","priority"}` in one impl and `{"text"}` in another → divergent id-less sort order → divergent sealed bytes. `lww_key` first component stays `f.timestamp or ""` (empty and missing both sort lowest). Preferred merge emit: omit / `None` over storing `""`.

### 5.3 Opaque LWW-per-key clock (`preferences`/`custom`/`extra`/`memory_extra`) — Pin 3, option (a)
Each key's value is treated as `{"v": <json-canonical value>, "t": <RFC3339-Z second>}`:
- **local write** sets `t = _utcnow()`.
- **legacy read** (plain value, no `t`) → wrap `{"v": value, "t": ""}` (`""` sorts lowest).
- **join per key** = max by `(t, value_hash(v))` — total order (`value_hash` = SHA-256 of canonical JSON of `v`).
- **merge output** for a key that participated = always the `{v,t}` form.

### 5.3a `sessions` G-Set (G1)
`sessions` is a **list**, not an opaque map. Join = **G-Set union**, dedup by `value_hash` of the entry (SHA-256 of canonical JSON), emitted **sorted by hash asc**. Concurrent "update the same logical session" is **not** modeled in v1 (no session-id LWW); if needed, introduce keyed sessions in v1.x — do **not** silently treat list elements as opaque `{v,t}` values.

### 5.4 Deterministic order (Pin 4)
Post-merge fact list sorted **ascending** by:
```python
( 0 if fact.id else 1,          # has_id True first (0<1)
  fact.id or "",
  content_hash(fact),
  normalized_text or fact.text or "" )
```
then `rebuild_index()`. `tags`/`links` emitted **sorted asc**. Soul-level key order unchanged; equality is **logical**, not byte-identity of the whole file.

## 6. Deletes (v1)
Out of the packet/merge path. `delete_fact` stays single-replica / coordinator-only. `merge` is **grow/update-only**. No "deletes converge" claim until tombstones (a future v1.x). Do not advertise offline delete sync.

## 7. Post-merge
Canonical-sort facts (§5.4) → `rebuild_index()`. `last_etched = max`. Emit deterministic `{v,t}` for merged opaque keys.

## 8. Property oracle (the tests that gate the label)
Hypothesis/QuickCheck; equality = **logical** (fact set by id-or-normalized-text, field values, `created`/`last_etched`, opaque `{v,t}` maps, `sessions` value-hash set, derived index) — not raw YAML bytes. `created` is in the logical state (**N2**) so the min-join is checked and dual-impl cannot drift.

> **N1 — lattice elements are post-normalize souls.** Idempotence/no-op laws hold under *logical* equality on merge **outputs**. Raw un-normalized ingress may rewrite `text` (NFC+strip) on first merge — intended (G5) — so `merge(a,a)` equals `a` logically, not byte-for-byte on unnormalized `a`.

Assert:
- `merge(a,b) == merge(b,a)` — commutative
- `merge(merge(a,b),c) == merge(a,merge(b,c))` — associative
- `merge(a,a) == a` — idempotent
- re-applying the same packet is a **no-op**
- both merge directions yield the **identical logical soul**

**Adversarial cases (must appear):** same-second same-id different text · id-less duplicate / whitespace-variant text · empty timestamp · priority ties · residual keys / `Fact.extra` concurrent · double packet · opaque key stamped-vs-unstamped + two concurrent stamps.

## 8a. Gap-decisions — **LOCKED (confirmed by the independent oracle, 2026-07-24)**

The frozen encoding lock left these under-specified; resolved deterministically so the property laws hold, then **confirmed by the independent oracle** (G1–G5, no overrides that change the join). **Both independent implementations must use the identical choices**, or dual-impl diverges. On any conflict with stale §4a/§4b prose, these locked gap-decisions control.

- **G1 — `sessions` is a LIST, not a map.** Merged as a **G-Set**: union, dedup by `content_hash` of the entry, emitted sorted by hash. (Pin 3 grouped it with the opaque maps, but it's a list.)
- **G2 — `Fact.extra` has no per-key clock.** Per-key LWW resolved by **greater `value_hash`** (canonical-JSON SHA-256 of the value), order-independent. (Distinct from the soul-level opaque maps, which use `{v,t}` per Pin 3.)
- **G3 — scalar-only key for same-id merge.** Scalar fields resolved by `_scalar_lww_key = (timestamp, priority_rank, id, scalar_hash)` where `scalar_hash` **excludes** `tags`/`links`/`extra`. Required so the winner is stable under the union'd fields → **associativity**. (The full `lww_key` with `content_hash` is used only for the id-less G-Set winner and the sort order.)
- **G4 — soul-level scalar conflicts** (`profile`, `retention`): deterministic **`x if x==y else max(x,y)`**. `created = min`, `last_etched = max`.
- **G5 — set semantics + normalization.** `content_hash` and `_scalar_hash` **dedup** `tags`/`links` (`sorted(set(...))`); merged facts store **NFC+stripped `text`**. Both required for order-independence (property tests caught the failures).

## 9. Not needed in v1
Version vectors / dots (not required for full-state CvRDT; add only for causality / δ-ops later). MV-Register (only if "never drop a concurrent same-id etch" becomes a requirement — v1 accepts LWW's deterministic drop).

---
*Verified by an independent oracle and a two-implementation (N-version) differential against this frozen spec.*
