# MERGE.md — `.fafm` Soul merge (Soul-Packet v1.1 track)

**Status:** FROZEN spec for v1 merge (2026-07-24). Authored against a frozen encoding lock; the §8a gap-decisions (G1–G5) were resolved deterministically and confirmed by an independent oracle. Two independent implementations (an N-version differential) are held to this spec; on conflict with stale prose, the locked §8a gap-decisions control.

**Addendum §11 Compactable (epoch)** — SPEC FROZEN for **2.0.0** implementation (2026-07-30). Second merge-law re-open after §9. Code must match §11; dual-impl gate required before unqualified CvRDT claim on the compact cut.

**NOT part of v1.0 INTEROP.** Merge is a v1.1 / Soul-Packet feature. `Soul.add` (single-replica overwrite) is unchanged; `Soul.merge` is the multi-replica, coordinator-free join defined here.

**Label:** the dual-implementation differential is green and independently re-verified ⇒ unqualified **"CvRDT"** (state-based; two independent implementations under encoding lock v1.1 + the §8a gap-decisions + the empty-timestamp pin). Grow/update-only for the fact lattice; **convergent forget (facts) is added in v1.5 via tombstones (§9).** Epoch barrier + epoch compact in **§11 (2.0)**.

**Packet transport (T3):** a sealed `.fafmp` packet ingests through this same merge — `merge_packet(local, data) = merge_souls(local, from_packet(data))`. The seal is transport only; the merge is unchanged. See `PACKET.md`.

---

## 1. Type

A **state-based CvRDT** — a product of join-semilattices, merged whole-state:

```
Soul ≅  LWW-Element-Map (facts by id)          # scalar fields per id
      ⨯ G-Set            (id-less facts)         # by normalized text
      ⨯ G-Set/LWW        (tags, links per fact)  # winner-clock; equal-clock union (Rule T §4a)
      ⨯ LWW-Map          (Fact.extra per key)    # per-key LWW by value_hash (G2)
      ⨯ max-register      (last_etched)
      ⨯ G-Set            (sessions list entries)                     # by value_hash (G1)
      ⨯ LWW-Map          (preferences/custom/extra/memory_extra)     # {v,t} per key
      ⨯ LWW-max-register (tombstones — key → deleted_at)             # v1.5, §9 — suppresses facts
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

### 4a. Facts WITH `id` — LWW-Element-Map, merged **field-level** (deltas #2/#3; **Rule T** in v1.5)
For the two facts sharing an id (`hi` = greater **`_scalar_lww_key`**, `lo` = other — **G3**, not full `lww_key`):
- **scalar fields** (`text`, `type`, `priority`, `timestamp`, `source`) ← from **`hi`** (LWW-Register). Stored `text` is **`normalize_text(hi.text)`** (NFC+strip — **G5**), never raw whitespace.
- **`tags` / `links` / `Fact.extra`** ← **Rule T (v1.5)** — by the **winning clock** (`fact_clock = timestamp or ""`):
  - **equal clock** (concurrent): **union** — `tags`/`links` set-union sorted asc; `extra` **per-key LWW by value_hash (G2)** (shared key → greater `value_hash`, loser-only keys kept). Concurrent **add-wins**, unchanged from v1.1.
  - **different clock**: take **`hi`'s set only** — a **strictly lower-clock** version contributes **nothing** (no cross-clock union).

> ⚠️ **Rule T is a v1.5 merge-law delta** (the second, after tombstones §9). Pre-1.5 unioned `tags`/`links`/`extra` across **all** same-id versions regardless of clock; that is **not associative** once a tombstone can retroactively invalidate a low-clock version (§9.2). Winner-clock tags (`max(clock)` + `union` on ties, both associative) restore C/A/I. **1.4-compat narrows:** a soul with **no** tombstones merges **as 1.4 except** this — same-id facts at **different** clocks no longer cross-clock-union tags/links/extra (winner-clock only). Equal-clock union and the id-less G-Set are unchanged.
> ⚠️ Still **not** whole-fact replace for the concurrent case: equal-clock `tags`/`links`/`extra` merge across both facts even though the scalar tiebreak comes from `hi`.
> ⚠️ **Scalar winner is `_scalar_lww_key` (§8a G3), independent of `tags`/`links`/`extra`.** The full `lww_key` (with `content_hash`) is used **only** for the id-less G-Set winner and the §5.4 sort.

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

## 6. Deletes (v1.1–v1.4)
Out of the packet/merge path. `delete_fact` stays single-replica / coordinator-only. `merge` is **grow/update-only**. No "deletes converge" claim. **Superseded for facts by §9 (v1.5 tombstones)** — `delete_fact` remains the tombstone-free local removal; `forget` is the convergent one.

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

## 9. Forgettable Memory — tombstones (v1.5)

The one deliberate merge-law re-open. A **tombstone** makes a delete *state* (not absence) so it survives a merge instead of being resurrected by a peer that still holds the fact. Facts only; sessions and opaque maps are out.

### 9.1 Component & encoding
A tombstone map: `key → deleted_at`, an **LWW max-register** per key (grow-only graveyard, no GC in v1).

| Fact kind | Map key | Wire record (`memory.tombstones[]`) |
|-----------|---------|-------------------------------------|
| id-fact | `("id", id)` | `{ id, deleted_at }` |
| id-less | `("txt", txt_hash)` | `{ txt_hash, deleted_at }` |

- **`txt_hash`** = lowercase-hex SHA-256 of UTF-8 `normalize_text(text)` (§5.1) — the **same keying as the id-less G-Set**, NOT `content_hash`. Hash the text so the forgotten content does not linger.
- **`deleted_at`** = RFC3339-Z, **required non-empty** on every write (`forget` → `_utcnow()`).
- **Join per key** = `max(deleted_at)` (a later delete deepens the grave).
- **Emit** `memory.tombstones` only when non-empty → a soul that never forgot is byte-identical to a ≤1.4 doc (every prior seal/wire golden stays valid).

### 9.2 Suppression order (R1′ — mandatory, version-level)
```
1. join tombstone map:  key → max(deleted_at)
2. join facts as §4, BUT drop any fact VERSION with deleted_at >= fact_clock
   BEFORE it is grouped/field-merged (its scalars AND tags/links/extra all vanish)
3. emit surviving facts in canonical order
```
`fact_clock = fact.timestamp or ""` (empty/missing sorts lowest). **delete-wins on ties** (`>=`).

**Why version-level, not emit-level (R1 → R1′).** The 1.5 design first specified suppression *only* on the final emitted fact. The N-version differential falsified associativity (2026-07-27): a same-id field-merge unions tags/links across versions, so a **forgotten low-clock version** straddled by a tombstone (`fact_clock ≤ deleted_at < re-etch_clock`) would fold its `L1` into a *surviving* re-etch in one fold order but be suppressed-then-gone in the other. Dropping the outranked **version** before the field-merge is the field-level realization of the same "no zombie tags/links/extra" rule — and restores associativity. Suppression is still **whole-version** (never a partial field-strip); priority / `content_hash` must **not** resurrect a fact on an equal clock.

### 9.3 Logical equality
`logical_state` compares the **observable** fact set (tombstones applied, exactly as emit) **and** the raw tombstone map. Applying suppression in the oracle is what keeps `merge(a,a) == a` when `a` still carries a live fact under its own tombstone; including the raw map means losing a tombstone counts as a difference.

### 9.4 Property laws (gate the label)
T1 resurrection · T2 re-etch (`ts > deleted_at` wins) · T3 delete-wins tie · T4 no-zombie · T5 monotone graveyard · T6 id-less align (`txt_hash`, not `content_hash`) · T7 seal identity · T8 C/A/I with deletes. Hand-authored goldens required — property search under-samples delete corners.

### 9.5 Interop / honesty
≤1.4 readers residual-preserve the `tombstones` key but **keep the facts** (no forget convergence). A tombstone is a **lattice marker, not a secure erase** — old copies, backups, and already-sent packets are untouched. Convergence is *on merge*, not a broadcast wipe.

## 10. Not needed in v1 / pre-2.0
Version vectors / dots (not required for full-state CvRDT; add only for causality / δ-ops later — and for **watermark tombstone GC**, a **2.0.1+** layer — see §11.9). MV-Register (only if "never drop a concurrent same-id etch" becomes a requirement — v1 accepts LWW's deterministic drop).

**Tombstone GC without epoch is not in 1.5–1.7.** The grow-only graveyard stands until **§11 Compactable** (epoch) or **§11.9 watermark**.

---

## 11. Compactable Memory — epoch compact (v2.0)

**Status:** SPEC FROZEN for implementation (2026-07-30). Second deliberate merge-law re-open after §9 tombstones.  
**Edition:** Compactable Forgettable Memory · product cut **2.0.0**  
**Doctrine:** never silent resurrection · ARCHIVE-DEFAULT · lattice honesty · dual-impl gate.

This section freezes **epoch-only compact** for dual-transport souls (packet + hosted).  
**Watermark / peer-frontier GC is not in 2.0.0** (§11.9).

### 11.0 Why a second re-open

§9 makes delete **state** (grow-only graveyard). Debt is correct and visible (1.7) but unbounded.  
Dropping tombstones **without** a lineage barrier resurrects facts when a lagging peer or pre-forget packet merges in (Cassandra zombie / dual-transport packet case).

**2.0.0 answer:** pay debt only by **epoch snapshot** — a deliberate lineage break. Cross-epoch merge **refuses** by default. Pre-compact souls remain mergeable among themselves at their epoch.

### 11.1 Component — `epoch`

| Item | Rule |
|------|------|
| Wire | Top-level integer `epoch` (document key), default **0** when absent |
| Domain | Non-negative integer (`0, 1, 2, …`) |
| Meaning | Compact generation / lineage id — **not** a wall clock |
| Pre-2.0 souls | Missing `epoch` ≡ **0** on load |
| Emit | Always emit `epoch` in ≥2.0 writers (including `0`) so seals are explicit |
| ≤1.7 readers | Residual-preserve unknown top-level `epoch` if modeled as residual; **must not strip** on load→save (INTEROP). First-class honor is 2.0+. |

`epoch` is **soul meta**, not under `memory`. Same value on every transport of that soul.

### 11.2 Merge precondition — same epoch (E1)

```
merge_souls(a, b):
  ea = a.epoch if defined else 0
  eb = b.epoch if defined else 0
  if ea != eb:
      raise EpochMismatch(ea, eb)   # refuse — never silent join
  # else: existing CvRDT join (§1–§9 + policies 1.6)
```

| Case | Result |
|------|--------|
| `ea == eb` | Full join (facts, tombstones, policies, …) as today |
| `ea != eb` | **Refuse** — no partial merge, no “take max epoch and hope” |
| Packet ingest | `merge_packet = merge_souls(local, from_packet(…))` — same E1 |

**Namepoint** and **packet** use **identical** E1. No transport-specific epoch rule.

### 11.3 Explicit migrate (E2) — not silent merge

Cross-epoch recovery is a **named tool**, not merge:

```
migrate_epoch(source, target_epoch, *, mode) -> Soul
```

| Mode (2.0.0) | Behavior |
|--------------|----------|
| **`refuse` (default)** | Do not migrate; surface EpochMismatch |
| **`project-live`** | Build a **new** soul at `target_epoch` from **observable** facts of `source` only (tombstones applied then dropped as in §11.4); does **not** merge concurrent lagging facts from another replica — operator must re-etch or re-pull intentionally |

**Forbidden:** auto-migrate inside `merge_souls`.  
**Forbidden:** taking `max(epoch)` and joining fact maps across epochs.

Migrate is for operator/tooling after archive; it is **not** a substitute for dual-transport sync of live peers (those must share an epoch).

### 11.4 Epoch compact operation (E3)

```
compact_epoch(soul, *, at: RFC3339-Z, actor: str | None) -> (new_soul, receipt)
```

**Preconditions (product law, enforced by CLI/API):**

1. **Archive-first** — prior soul bytes saved (file path / seal / tag). ARCHIVE-DEFAULT. Compact MUST NOT proceed without an archive receipt path or explicit `--i-archived` override in CLI (library documents the duty).  
2. **`at`** pinned (same discipline as policy apply).  
3. Soul is at epoch `e`; result is epoch **`e + 1`**.

**Effect on `new_soul`:**

| Component | After compact |
|-----------|----------------|
| `epoch` | `e + 1` |
| **Facts** | **Observable** set only (tombstone suppression applied — same as emit/logical_state §9.3) |
| **Tombstones** | **Empty** (debt paid for this lineage; forgotten facts are absent as facts, protected by epoch barrier not by graveyard) |
| **Policies** | Preserved (config); not “debts” |
| **policy_auto**, sessions, preferences, custom, residuals | Preserved (deep copy) |
| **index** | Rebuilt from observable facts |
| **created** | Preserved |
| **last_etched** | `max(previous, at)` |

**Re-etch after compact:** a new fact at epoch `e+1` is normal etch. A lagging epoch-`e` peer that still holds a forgotten fact **cannot** resurrect it via merge — E1 refuses.

### 11.5 CompactionReceipt (E4)

Every successful compact **must** produce a receipt (returned to caller **and** optionally appended on the new soul for audit).

Wire (list under `memory.compaction_receipts[]`, omit when empty on souls that never compacted):

```yaml
memory:
  compaction_receipts:
    - from_epoch: 0
      to_epoch: 1
      at: "2026-07-30T18:00:00Z"
      actor: "cli:compact"          # optional string
      tombstones_before: 42
      facts_before: 100
      facts_after: 88
      archive_ref: "soul.epoch0.fafm"  # path or seal hash note — optional but recommended
```

| Field | Required | Rule |
|-------|----------|------|
| `from_epoch` | yes | integer |
| `to_epoch` | yes | `from_epoch + 1` for epoch compact |
| `at` | yes | RFC3339-Z clock pin |
| `actor` | no | free string |
| `tombstones_before` | yes | count |
| `facts_before` / `facts_after` | yes | counts |
| `archive_ref` | no | operator pointer (path, content hash, tag) |

**Merge of receipts:** grow-only **append-union** by whole-record identity (canonical JSON hash) — or simpler 2.0.0: **LWW not used**; concatenate and dedupe by `(from_epoch, to_epoch, at, tombstones_before, facts_after)`. Receipts **never** suppress facts. Losing a receipt is audit degradation, not lattice resurrection.

≥2.0 readers: first-class `memory.compaction_receipts`.  
≤1.7: residual-preserve if present.

### 11.6 Seal / packet (E5)

- `normalize_for_seal` / `to_doc` carry **`epoch`** and **`compaction_receipts`** (when non-empty).  
- Opened packet is a full soul; `merge_packet` applies **E1**.  
- A packet sealed at epoch `e` **refuses** merge into local epoch `e' ≠ e`.

### 11.7 Honesty bounds (E6)

| Claim | Truth |
|-------|--------|
| Compact pays tombstone **debt** in the new lineage | Yes — graveyard empty at `e+1` |
| Forgotten facts stay forgotten under merge with **same-epoch** lagging peers that never saw the forget | **Only if** those peers also compacted or still carry tombstones at same epoch — if they are still on `e` with live facts and no tombstone, they are a **different problem** (they never forgot). Epoch compact does not rewrite peers. |
| Pre-forget **packet** at epoch `e` after local compact to `e+1` | **Refuse** merge (E1) — never silent join |
| Secure erase of archives / old packets / disks | **No** — lattice marker / lineage break only (same honesty as §9.5) |
| Auto-GC on grace alone | **No** |

### 11.8 Property laws — zombie suite (gate 2.0)

Hand-authored goldens (Z1–Z8). Property search under-samples these corners.

| Law | Statement |
|-----|-----------|
| **Z1** | Same-epoch merge still obeys T1–T8 (tombstones) |
| **Z2** | `merge(epoch=0, epoch=1)` raises EpochMismatch — no fact bleed |
| **Z3** | Packet sealed **pre-forget** at `e`, local compacted to `e+1` → merge_packet **refuses** |
| **Z4** | After compact, forgotten facts are **absent** from facts; tombstones empty; re-etch with new ts works |
| **Z5** | Compact is deterministic given `(soul, at)` for fact set + epoch + receipt counts |
| **Z6** | Dual-transport: packet and hosted use the **same** E1 |
| **Z7** | Archive-first: API/CLI documents refuse without archive ack (product test) |
| **Z8** | C/A/I of merge **within** a fixed epoch (including post-compact epoch-1 peers) |

**Dual-impl / N-version:** epoch field, E1 refuse, and compact projection must agree across `merge.py` and `reference_merge.py` (or successor). Unqualified **CvRDT** claim for 2.0 requires this gate green (same bar as §9).

### 11.9 Reserved — watermark compact (2.0.1+, not frozen for 2.0.0)

| Item | Status |
|------|--------|
| Device / peer version vectors | Not in 2.0.0 |
| `compact --watermark` | Illegal / unimplemented until membership + frontier exchange exist |
| Dropping tombstones **without** epoch bump | **Forbidden** in 2.0.0 |

When specified later: only drop tombstones dominated by a **stable frontier**; still emit a receipt; packet-only topologies remain epoch-only.

### 11.10 Implementation checklist (code after this freeze)

- [x] `Soul.epoch` load/save (default 0) — epoch-only slice  
- [x] `EpochMismatch` on merge / merge_packet — E1 + dual-impl (reference_merge)  
- [x] Seal carries epoch (`normalize_for_seal`)  
- [x] INTEROP addendum §14 (wire)  
- [x] Z2 goldens + packet refuse (`tests/test_wjttc_epoch.py`); same-epoch merge  
- [x] `compact_epoch` + CompactionReceipt (`compact.py`)  
- [x] CLI `compact --epoch` (archive gate + `--at`)  
- [x] CLI `migrate` (E2 refuse | project-live + archive gate)  
- [x] Z3–Z8 goldens in `test_wjttc_epoch.py` · Z7 CLI archive-first  
- [x] Dual-impl compact/migrate projection (`reference_merge` + epoch tests)  
- [x] T1–T8 still green on epoch-0 souls (held)

**No code ships 2.0 product cut without Doc Gate + acid + version 2.0.0.** Lattice laws Z2+Z3 green on main.

---

*§1–§9 verified by independent oracle and N-version differential (1.5 track).*  
*§11 is the frozen implementation contract for 2.0.0 Compactable — code must match this prose; on conflict during implementation, amend §11 deliberately (second freeze note) rather than silent drift.*
