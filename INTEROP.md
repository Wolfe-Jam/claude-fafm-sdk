# `.fafm` Interop Contract — claude-fafm-sdk

**Status:** locked for v1.0 implementation (Step 1 of the 0.4.0 → v1.0 plan);  
**addenda:** §12 (1.5 tombstones) · §13 (1.6 policies) · §14 (2.0 epoch — wire only; merge law in MERGE §11)  
**Base date:** 2026-07-22 · **Addenda date:** 2026-07-30  
**Applies to:** `Soul` / `Fact` in this package, and any writer/reader that claims format-compat with them (`fafm-engine`, `grok-faf-voice` local file path, future `faf memory` TS surface).

**Format:** `application/vnd.fafm+yaml` (IANA) · document version emitted: **`1.1`**  
**Schema (normative for shape):** [fafm.schema.json](https://faf.one/schemas/fafm.schema.json) (also under `faf` / `@faf/specification`)

**Bar:** identical logical data model · lossless roundtrip **both** directions · deterministic serialization. Compare reconstructed **Fact lists** (and stored `index` when present) — not raw YAML bytes. (Voice `from_file` → `to_file` remains byte-identical raw I/O; `Soul` is a structured writer.)

This document pins **behavior**. Code that contradicts it is a bug.  
Merge law lives in [MERGE.md](MERGE.md) (v1.1+ track; tombstones §9).

---

## 1. Document shape

### 1.1 Required top-level keys

Per schema, a valid `.fafm` document MUST include:

| Key | Role |
|-----|------|
| `version` | Format version string, pattern `\d+\.\d+` (this SDK writes `"1.1"`) |
| `namepoint` | Soul identifier (e.g. `@me`, `@claude-code:wolfejam`) |
| `created` | RFC3339-Z timestamp (see §2) |
| `last_etched` | RFC3339-Z timestamp (see §2) |
| `memory` | Object holding facts (and optional subtrees) |

Loaders MAY supply defaults for missing optional fields when **reading** non-strict files; writers MUST emit a schema-valid document when creating a new soul.

### 1.2 Profile

| Rule | Value |
|------|--------|
| Allowed values | `voice` \| `knowledge` |
| **Missing `profile` on load** | Treat as **`voice`** (schema default / v1.0 back-compat) |
| Constructor default when *creating* a knowledge soul in this SDK | `knowledge` is fine for new objects; **load** path follows the missing→`voice` rule |

### 1.3 Optional top-level keys

| Key | Rule |
|-----|------|
| `retention` | Free string; default `"forever"` if absent on load |
| `index` | Optional `string[]` — see **§5** (v1.0 in scope) |
| Other top-level keys | See **§4** (unknown fields) |

### 1.4 `memory` object

| Key | Rule | Edition |
|-----|------|---------|
| `facts` | Array of bare strings and/or fact objects (see §3). Primary durable payload. | v1.0 |
| `sessions` | Optional array — **preserve if present** on load→save | v1.0 |
| `preferences` | Optional object — **preserve if present** on load→save | v1.0 |
| `custom` | Optional object — **preserve if present** on load→save | v1.0 |
| `tombstones` | Optional list — convergent forget markers; **first-class** in ≥1.5 readers (see **§12**) | **1.5** |
| `policies` | Optional list — policy rules that *emit* forget; **first-class** in ≥1.6 readers (see **§13**) | **1.6** |
| `policy_auto` | Optional bool — default **false**; opt-in auto-apply (see **§13**) | **1.6** |
| Other keys under `memory` | **Preserve** as residual (schema `additionalProperties: true`) | v1.0 |

**v1.0 requirement:** `Soul.save` / `to_doc` MUST NOT wipe non-empty `sessions` / `preferences` / `custom` to empty defaults when the document had values on load. (Current 0.4.0 fixed-skeleton emit is a known defect relative to this contract.)

**≥1.5:** `tombstones` MUST NOT be treated as residual LWW-opaque by a 1.5+ structured reader (would break delete convergence).  
**≥1.6:** `policies` MUST NOT be residual LWW-opaque (would break rule-set merge).

---

## 2. Timestamps

| Rule | Value |
|------|--------|
| Form | **RFC3339 in UTC with `Z` suffix** |
| Precision | **Second** (no fractional seconds in SDK-emitted stamps) |
| Writer form | Match `_utcnow()`: `%Y-%m-%dT%H:%M:%SZ` (e.g. `2026-07-22T12:34:56Z`) |
| On `etch` | Set fact `timestamp` to `_utcnow()`; may advance document `last_etched` |
| On `add` (merge primitive) | Preserve the incoming Fact’s `timestamp` verbatim |
| Comparison | Lexicographic string compare is valid for this form (same precision, always `Z`) |

Consumers MUST tolerate other valid date-time strings when **reading** (schema `format: date-time`); emitters in this SDK use the form above.

---

## 3. Facts

### 3.1 Minimal fact

- Bare string fact: the string **is** the `text`.
- Object fact: **`text` is required**. All other fields optional.

### 3.2 Known fact fields

| Field | Semantics |
|-------|-----------|
| `text` | Memory unit body (required for objects) |
| `id` | Stable unique key when present |
| `type` | Optional type string (schema lists knowledge enums; other strings may appear — do not reject unknown types on load) |
| `priority` | See §3.3 |
| `tags` | See §3.4 |
| `links` | Cross-refs (string array) |
| `timestamp` | See §2 |
| `source` | Provenance string |
| Other keys | Fact-level unknowns → **preserve** in `extra` / passthrough (§4) |

### 3.3 Priority

**Canonical vocabulary (low → high):**

```text
ephemeral < standard < high < critical
```

| Input | Canonical |
|-------|-----------|
| `null` / missing | `standard` |
| `low` (legacy) | `ephemeral` |
| `medium` (legacy) | `standard` |
| value in vocabulary | as-is |
| anything else | `standard` |

### 3.4 Tags

| Rule | Value |
|------|--------|
| Ordering | **Preserve** as stored (no auto-sort) |
| Case | **Case-sensitive** |
| Dedup | **No** automatic dedup on write |
| Recall filter | Tag filter uses **set intersection** with the fact’s tag list |

### 3.5 Fact-id uniqueness / collision

| Rule | Value |
|------|--------|
| Facts without `id` | Always append; multiple id-less facts allowed |
| Facts with `id` | At most one live fact per id in the soul |
| **Collision** | **Overwrite** the entire Fact in place (replace fields; do not field-merge) |
| Index bookkeeping | O(1) id → list position; rebuild map after deletes |

This matches current `add` / `etch` behavior and is the v1.0 rule.

---

## 4. Unknown-field policy

Aligned with schema guidance: unknown fields are permitted.

| Layer | Policy |
|-------|--------|
| **Fact object** | **Preserve** unknown keys through load → in-memory `extra` → save |
| **Document / `memory` subtrees** | **Preserve** unknown and optional subtrees present on load when saving |
| **Top-level residual keys** | Keys outside the known set (`version`/`profile`/`namepoint`/`created`/`last_etched`/`retention`/`index`/`memory`) live in `Soul.extra` and are re-emitted after modeled keys; residuals never overwrite modeled keys |
| **`memory` residual keys** | Keys outside the **edition’s known set** live in `Soul.memory_extra` and are re-emitted under `memory`. **v1.0 known:** `facts`/`sessions`/`preferences`/`custom`. **+1.5:** `tombstones`. **+1.6:** `policies`/`policy_auto`. |
| **`memory.tombstones` (≤1.4 readers)** | Unknown to ≤1.4 → residual-preserve on load→save **but not honored** (facts stay live; no delete convergence). Preserving the key (not stripping) lets a later 1.5+ merge apply it. See **§12**. |
| **`memory.policies` (≤1.5 readers)** | Unknown to ≤1.5 → residual-preserve **but not merged as first-class** (opaque residual path). 1.6+ readers model the list. See **§13**. |
| **Strip (forbidden in v1.0 structured save)** | Silently dropping `index`, residual unknowns, or blanking non-empty `sessions` / `preferences` / `custom` |

**Voice note:** `FAFMemory.from_file` / `to_file` are raw text I/O (byte-identical). They do not interpret unknowns; they pass the file through. Structured writers (`Soul`) must still honor this section.

---

## 5. Top-level `index` (v1.0 — not deferred)

| Decision | Value |
|----------|--------|
| Kind | **Stored** optional top-level `string[]` |
| Absent | Treat as empty list; not an error (matches voice) |
| Consumer SoT | `grok-faf-voice.FAFMemory.index` → `doc.get("index") or []` |
| Rebuild formula (when recomputing) | `f"{id or '?'} — {text[:80]}"` per fact, same order as `facts` (matches `fafm-engine`) |
| Load | Read `index` if present |
| Save | **MUST NOT drop** index; always emit `"index"` (list, possibly empty) |
| Rebuild on save | `save(reindex=True)` **default** rebuilds via the formula; `reindex=False` preserves loaded/hand-tuned index |

**P0 defect (0.4.0):** `Soul.to_doc()` omitted `index` and never modeled memory subtrees — fixed in Step 2 (document fidelity).

---

## 6. Local recall (deterministic)

Offline `Soul.recall` is the **source of truth for Fact-level ranking** in v1.0.

### 6.1 Filter (all must pass)

1. Substring match on `text` (case-insensitive), if `query` set  
2. Tag set **intersection** non-empty, if `tags` set  
3. `type` equality, if `type` set  
4. `PRIORITY_RANK[fact.priority] >= PRIORITY_RANK[min_priority]` (default floor: `ephemeral`)

### 6.2 Rank (descending)

```text
(priority_rank, timestamp_string, insertion_index)
```

- Higher priority first  
- Then more recent `timestamp` (empty string sorts lowest)  
- Then **higher insertion index** — the fact’s current **list position**, not “time of last etch”  
- Same-second ties: higher index wins (typically last **appended** fact). Id-collision **update-in-place** keeps its slot and does not jump ahead of a later append with the same timestamp.

### 6.3 What is *not* rank SoT

| Surface | Behavior |
|---------|----------|
| `grok-faf-voice` `recall_for_prompt` | Injects full soul **body string** + header — not Fact-ordered list |
| MCPaaS `get_soul` | Server text; not this contract’s local rank |
| `fafm-engine` recall (today) | Sort key is `(priority, timestamp)` only. On **pure same-second** ties (equal priority+timestamp), stable `list.sort(reverse=True)` **preserves list order** (`a,b,c`), while the SDK’s insertion-index key **reverses** it (`c,b,a`). That is a real, pinned drift — not accidental parity. Cross-impl test: `tests/test_wjttc_recall_cross_impl.py`. |

**v1.0:** SDK local rank is SoT. Do not redefine SDK rank to match engine or voice. Engine may add an explicit insertion-index later to converge; until then the cross-impl test documents both orders.

---

## 7. Scratchpad and ledger

| Layer | v1.0 rule |
|-------|-----------|
| Runtime | Voice / engine **in-process** only (`Scratchpad`, session ledger) |
| On-disk `.fafm` | Soul **does not** write scratchpad/ledger as first-class format sections |
| If seen in a document | **Preserve or declare-ignore** — do not invent fields; do not silently corrupt other keys |
| Full formalization | **Deferred to v1.1** |

---

## 8. Cross-profile and cross-package

| Direction | Expectation |
|-----------|-------------|
| Voice-profile file → `Soul.load` | Loads; facts readable; missing profile → `voice` |
| Knowledge-profile file → `FAFMemory.from_file` | Loads; `.facts` / `.index` / `.profile` accessors work |
| `Soul.save` → voice read | Document remains valid YAML `.fafm`; index preserved when present |
| Logical equality | Same Fact texts/ids/priorities/tags (and index lines when stored), independent of key order in YAML |

**Converters** (`from_claude_dir`, etc.) MUST emit schema-constrained documents (`memory.facts`, not ad-hoc `memory.entries`). Proof scripts that emit `entries` are **not** the v1.0 target shape.

### Claude Code memory → Soul (`from_claude_dir`)

| Input | Output |
|-------|--------|
| Topic `*.md` with YAML frontmatter | One `Fact` when gates pass |
| `metadata.type` | Only `user` \| `feedback` \| `project` \| `reference` (else skip) |
| `name` | Fact `id` (required; missing → skip) |
| `description` or `name` | Fact `text` |
| File mtime | Fact `timestamp` (RFC3339-Z, second) |
| `[[wikilinks]]` in body | Fact `links` (body text is **not** the fact text) |
| `metadata.originSessionId` | `Fact.extra["provenance"] = ["session:…"]` — **not** a first-class Fact field in v1.0 |
| Skip basenames | `MEMORY.md`, `MEMORY-FULL.md`, `README.md` |

Returns a knowledge-profile `Soul` with `rebuild_index()` applied.

---

## 9. Explicitly out of v1.0 (v1.1)

| Item | Notes |
|------|--------|
| Bench-in-box | One-command convert + bench |
| Async surface parity | Soul stays sync offline |
| `recall_for_prompt` convenience | Voice already owns body+header inject |
| Scratchpad/ledger formalization | Beyond §7 one-liner |

**Not deferred:** `index` (§5), preserve-or-declare-ignore for scratchpad/ledger (§7), local recall SoT (§6).

---

## 10. Implementation checklist (post-contract)

Use this when coding Steps 2–6; not part of the prose contract but tracks compliance:

- [x] `INTEROP.md` committed (this file)
- [x] `Soul` load/save preserves `index` + memory subtrees
- [x] Missing `profile` on load → `voice`
- [x] `.index` property + `rebuild_index()` + `save(reindex=…)`
- [x] Symmetric corpus tests (Soul ↔ FAFMemory) — `tests/test_wjttc_interop_corpus.py` (+ optional voice Path A/B)
- [x] Residual top-level + memory unknown preserve (`Soul.extra` / `memory_extra`) — Step 2.5
- [x] Schema-constrained `from_claude_dir()` + `from_file`/`to_file` aliases — Step 4
- [x] Recall rank SoT verified (docstring + INTEROP + cross-impl test) — Step 6

---

## 11. References

- Schema: `faf/schemas/fafm.schema.json`
- Voice consumer tests: `grok-faf-voice/tests/test_local_souls.py`
- Engine twin: `fafm-engine/fafm_engine/soul.py` (`rebuild_index`)
- This package: `claude_fafm_sdk/soul.py`
- Merge / tombstones: [MERGE.md](MERGE.md) §9
- Packets: [PACKET.md](PACKET.md)

---

## 12. Addendum — Forgettable Memory (1.5) · tombstones

**Status:** shipped in product cut **1.5.1** (docs front door 1.5.2). Normative merge law: **MERGE.md §9**.

### 12.1 Wire

| Item | Rule |
|------|------|
| Key | `memory.tombstones` — list of maps |
| Id-fact entry | `{ id: <string>, deleted_at: <RFC3339-Z> }` |
| Id-less entry | `{ txt_hash: <hex sha256 of normalize_text(text)>, deleted_at: <RFC3339-Z> }` |
| Emit | **Only when non-empty** — a soul that never forgot is byte-identical to a ≤1.4 document for seal/wire goldens (T7) |
| Join | Per key, `max(deleted_at)` — grow-only LWW max-register |
| Suppress | On emit/merge: drop fact **versions** with `deleted_at >= fact.timestamp` (delete-wins on ties). Full order in MERGE §9.2 |

### 12.2 Reader classes

| Reader | Behavior |
|--------|----------|
| **≥1.5 structured** (`Soul` this package) | First-class: load, save, merge, seal, suppress on recall/merge |
| **≤1.4 structured** | Residual-preserve key; **keep facts** (no convergence) |
| **Raw I/O** (voice `from_file`/`to_file`) | Pass-through bytes; no interpretation |

### 12.3 Honesty

A tombstone is a **lattice marker, not a secure erase**. Prior packets, backups, and logs may still hold original bytes. Convergence is on **merge**, not a broadcast wipe. No automatic GC in 1.5 (grow-only graveyard).

### 12.4 Transports

Same join on **packet** (`merge_packet`) and **hosted** namepoint reconcile. Convergent forget on only one road is incomplete for the 1.5 product cut.

---

## 13. Addendum — Policy → tombstone (1.6)

**Status:** contract for **1.6** implementation (plan-locked 2026-07-30).  
**Does not change** MERGE §9. Policies never suppress facts at merge time — only tombstones do.

### 13.1 Intent

Policies **propose** or **apply** forget by calling the same surfaces as human forget (`forget` / `forget_text`). Apply writes **fact tombstones**. The policy list is configuration that travels with the soul.

### 13.2 Wire

| Key | Rule |
|-----|------|
| `memory.policies` | Optional list of policy objects. **Omit when empty** (seal / roundtrip identity). |
| `memory.policy_auto` | Optional bool. Default when absent: **`false`**. Opt-in only for auto-apply. |

**Policy object (minimum):**

| Field | Required | Rule |
|-------|----------|------|
| `id` | yes | Stable string — map key for merge |
| `when` | yes | Selector object (see §13.4) |
| `action` | yes | **`forget` only** in 1.6 (no hide-only / rank-only) |
| `enabled` | no | Bool; default `true` |
| `updated_at` | yes on write | RFC3339-Z — LWW among same `id` |

### 13.3 First-class (not residual)

≥1.6 `Soul` MUST model `policies` / `policy_auto` as known memory keys (same class of bug as treating `tombstones` as residual LWW).  
≤1.5 readers: residual-preserve if present; do not invent first-class merge.

### 13.4 Merge rule (policies)

```
policies ≅ LWW-Element-Map by rule id
  · same id     → greater updated_at wins whole rule
                  (tie-break: greater content_hash of canonical rule body)
  · different ids → union
  · disabled    → enabled: false via LWW (1.6); no separate policy-tombstone required
```

`policy_auto`: LWW bool (or max/or as implemented — prefer last-writer with timestamp if both sides carry meta; if bare bool, document deterministic join in code). **Default false** on create.

### 13.5 Apply semantics

| Surface | Rule |
|---------|------|
| **Propose** | List matching facts; **no write** |
| **Apply** | For each match, `forget(id)` or `forget_text(text)` with **`deleted_at = at`** |
| **Clock pin** | Library API: `apply_policies(..., at: RFC3339-Z)` **required**. CLI MAY default `at` to now. Goldens **freeze** `at`. |
| **Authority** | Propose is the default product surface. Apply requires explicit confirm (`--yes` or equivalent). `policy_auto` default **false**. |
| **Determinism** | Same `(soul, policy set, at)` → same tombstone set. No LLM in merge or apply path. |
| **Merge** | Fact convergence uses tombstones only. Two replicas that applied the same policy at different `at` still converge via `max(deleted_at)`. |

### 13.6 Selector (`when`) — 1.6 minimum

Implementations MUST support at least:

| Selector | Match |
|----------|--------|
| `max_age` | Fact `timestamp` older than duration relative to `at` (e.g. `"7d"`) |
| `priority_lte` | Fact priority ≤ named floor (`ephemeral`…`critical`) |
| `tag` | Fact tags set-intersects given tag(s) |
| `id` | Exact fact id |
| `text` | Id-less: `normalize_text` equality (tombstone via `txt_hash`) |

Compounds (AND lists) MAY be added in the same minor if goldens cover them.  
**Non-goal:** ranking-only “decay” as a substitute for forget.

### 13.7 Cross-impl

`fafm-engine` / `grok-faf-voice`: at minimum **residual-preserve** `policies` / `policy_auto` / `tombstones` on load→save. First-class honor is best-effort per package; format anti-fork forbids stripping unknown memory keys.

### 13.8 Out of 1.6

Automatic GC · epoch compact · watermark · LLM selection · hide-without-tombstone · MCP apply-as-default tool.

---

## 14. Addendum — Compactable epoch (2.0) · wire

**Status:** wire + residual contract for **2.0.0**. Normative merge/compact law: **MERGE.md §11** (frozen).

### 14.1 Top-level `epoch`

| Item | Rule |
|------|------|
| Key | `epoch` (integer ≥ 0) |
| Absent | Treat as **0** on load (pre-2.0 souls) |
| ≥2.0 writers | Always emit `epoch` (including `0`) |
| ≤1.7 structured | Residual-preserve if unknown; **must not strip** on load→save |
| Merge | Same-epoch only — see MERGE §11.2; cross-epoch **refuse** |

### 14.2 `memory.compaction_receipts`

| Item | Rule |
|------|------|
| Key | Optional list under `memory` |
| Emit | Only when non-empty |
| ≥2.0 | First-class known key |
| ≤1.7 | Residual-preserve |
| Schema | See MERGE §11.5 |

### 14.3 Known memory keys (edition map)

| Edition | Known under `memory` |
|---------|----------------------|
| v1.0 | `facts` · `sessions` · `preferences` · `custom` |
| +1.5 | `tombstones` |
| +1.6 | `policies` · `policy_auto` |
| +2.0 | `compaction_receipts` |

### 14.4 Out of 2.0.0 wire

Watermark frontiers · peer VV · auto-migrate on merge · secure erase claims.
