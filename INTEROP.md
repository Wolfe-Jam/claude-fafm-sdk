# `.fafm` Interop Contract — claude-fafm-sdk v1.0

**Status:** locked for v1.0 implementation (Step 1 of the 0.4.0 → v1.0 plan)  
**Date:** 2026-07-22  
**Applies to:** `Soul` / `Fact` in this package, and any writer/reader that claims format-compat with them (`fafm-engine`, `grok-faf-voice` local file path, future `faf memory` TS surface).

**Format:** `application/vnd.fafm+yaml` (IANA) · document version emitted: **`1.1`**  
**Schema (normative for shape):** [fafm.schema.json](https://faf.one/schemas/fafm.schema.json) (also under `faf` / `@faf/specification`)

**Bar:** identical logical data model · lossless roundtrip **both** directions · deterministic serialization. Compare reconstructed **Fact lists** (and stored `index` when present) — not raw YAML bytes. (Voice `from_file` → `to_file` remains byte-identical raw I/O; `Soul` is a structured writer.)

This document pins **behavior**. Code that contradicts it is a bug.

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

| Key | Rule |
|-----|------|
| `facts` | Array of bare strings and/or fact objects (see §3). Primary durable payload. |
| `sessions` | Optional array — **preserve if present** on load→save |
| `preferences` | Optional object — **preserve if present** on load→save |
| `custom` | Optional object — **preserve if present** on load→save |
| Other keys under `memory` | **Preserve** (schema `additionalProperties: true`) |

**v1.0 requirement:** `Soul.save` / `to_doc` MUST NOT wipe non-empty `sessions` / `preferences` / `custom` to empty defaults when the document had values on load. (Current 0.4.0 fixed-skeleton emit is a known defect relative to this contract.)

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
| **`memory` residual keys** | Keys outside `facts`/`sessions`/`preferences`/`custom` live in `Soul.memory_extra` and are re-emitted under `memory` |
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
- Then **higher insertion index** (breaks same-second ties so newest etch wins)

### 6.3 What is *not* rank SoT

| Surface | Behavior |
|---------|----------|
| `grok-faf-voice` `recall_for_prompt` | Injects full soul **body string** + header — not Fact-ordered list |
| MCPaaS `get_soul` | Server text; not this contract’s local rank |
| `fafm-engine` recall (today) | Priority + timestamp only — **no** insertion-index; may drift on same-second ties until aligned |

**v1.0:** document engine same-second drift if unfixed; do not redefine SDK rank to match voice prompt dump.

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
- [ ] Schema-constrained `from_claude_dir()`
- [x] Recall rank tests remain green (incl. same-second ties) — no Step 2 change

---

## 11. References

- Plan: `PLANET-FAF/FAFM/CLAUDE-FAFM-SDK-V1.0-BUILD-STEPS-2026-07-22.md`
- Schema: `faf/schemas/fafm.schema.json`
- Voice consumer tests: `grok-faf-voice/tests/test_local_souls.py`
- Engine twin: `fafm-engine/fafm_engine/soul.py` (`rebuild_index`)
- This package: `claude_fafm_sdk/soul.py` (0.4.0 baseline)
