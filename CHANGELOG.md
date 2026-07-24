# Changelog

All notable changes to `claude-fafm-sdk` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).

## [1.1.0] — 2026-07-24

Soul-Packet **merge**: a coordinator-free, order-independent `Soul` join — the
mergeable half of portable memory. Two independent implementations, verified against
each other, converge on every input. The local v1.0 knowledge-profile / etch / recall /
namepoint loop is unchanged.

### Added
- **`claude_fafm_sdk.merge`** — `merge_souls(a, b) -> Soul`, a **state-based CvRDT**
  (product of join-semilattices): commutative · associative · idempotent, with no
  coordinator. Facts merge as an LWW-Element-Map (by id, field-level) + G-Set (id-less,
  by normalized text); `tags`/`links` set-union; soul-level maps LWW-per-key; `sessions`
  G-Set. **Grow/update-only.**
- **`MERGE.md`** — the frozen merge spec (encoding lock, §8a gap-decisions G1–G5, §8
  property oracle).
- **Property + differential test suites** — WJTTC merge laws (commutative / associative /
  idempotent + adversarial cases) and an **N-version differential** between two
  independent implementations, under logical equality.

### Fixed
- **Empty-string fact timestamps normalize to absent** at the `Fact` data model
  (`timestamp="" → None`), so bareness and `content_hash` use the same absence predicate
  and merged fact order (hence sealed bytes, later) is deterministic across
  implementations.

### Verification
Reproducible receipt — a stranger runs it against the published artifact:
```
pip install claude-fafm-sdk==1.1.0
pytest tests/test_wjttc_merge_crdt.py tests/test_nversion_differential.py
```
- **We claim:** the merge is a state-based **CvRDT** under a frozen encoding lock,
  verified by two independent implementations (N-version).
- **We do NOT claim:** sealed-packet send / CRC (next release), offline delete
  convergence (grow/update-only in v1), or verification across all AIs beyond the
  N-version process.

## [1.0.0] — 2026-07-22

Stable **v1.0** knowledge-profile `.fafm` baseline: interop contract, document
fidelity, cross-vendor corpus, Claude Code memory converter, local recall SoT.

### Added
- **`INTEROP.md`** — v1.0 interop contract (timestamps, priority/rank, id collision,
  unknown fields, index, scratchpad/ledger boundary, converters).
- **Document fidelity on `Soul`:** load/save `index`; model `sessions` /
  `preferences` / `custom`; `rebuild_index()`; `save(reindex=True)` default.
- **Residual preserve (INTEROP §4):** `Soul.extra` / `memory_extra` for arbitrary
  top-level and `memory` unknown keys (never overwrite modeled keys).
- **`from_claude_dir(path) → Soul`** (`claude_fafm_sdk.interop`) — schema-constrained
  Claude Code memory store → knowledge soul (`memory.facts` v1.1, not proof
  `entries`). `originSessionId` → `Fact.extra["provenance"]`.
- **`Soul.from_file` / `Soul.to_file`** — name parity with grok-faf-voice.
- **Test corpus:** vendored faf conformance fixtures; optional live Path A/B with
  `FAFMemory`; cross-impl same-second recall pin vs `fafm-engine`.

### Changed
- **Missing `profile` on load** defaults to **`voice`** (schema / INTEROP §1.2);
  new `Soul()` still defaults to `knowledge`.
- **`Soul.recall` docs** — rank is `(priority, timestamp, insertion_index)` where
  insertion index is list position (update-in-place keeps slot); SDK is local rank SoT.

### Fixed
- Structured save no longer drops `index` or invents empty memory subtrees.
- Top-level residual fields (e.g. conformance `future_root_field`) survive roundtrip.

### Tests
- **WJTTC FINISH** — `tests/test_wjttc_finish.py` release gate for 1.0.x (version,
  INTEROP, fidelity, converter, recall SoT, corpus).

## [0.4.0] — 2026-05-26

### Added
- **Guided onboarding wizard** — `claude-fafm-sdk quickstart` (also runs with **no
  subcommand**) walks the first run end to end: create a soul → capture a first
  memory → go live on a zero-config namepoint → and *proves* it cross-vendor with a
  keyless read-back URL (`mcpaas.live/raw/<handle>`) + a paste-ready "hand it to any
  model" line. The 30-second wow. Non-interactive shells do the safe local steps and
  point at `namepoint push` (never auto-push); stays honest — no "live" claim unless
  a push actually happened.

## [0.3.0] — 2026-05-23

### Added
- **Zero-config namepoints — the `.fafm`-native hosted loop.** A namepoint is your
  soul's live address (`mcpaas.live/<handle>`), readable by any model.
  - `namepoint push` — **A-for-first-touch:** with no setup, auto-provisions an
    anonymous namepoint + key (saved to `~/.claude-fafm-sdk/identity.json`) and
    uploads. Stores the **whole `.fafm` document** (replace), so ids/types/priorities
    survive the round-trip and re-pushes are idempotent.
  - `namepoint pull` — merge the hosted soul into the local one (by id); public read,
    no key.
  - `namepoint sync` — reconcile both ways (merge by id, then write the union back);
    idempotent.
  - `namepoint claim [--email …]` — **B-for-keepers:** `--email` provisions a named,
    recoverable namepoint; bare `claim` mints an anonymous one.
  - `namepoint status` — show the current identity (anonymous vs recoverable).
- `claude_fafm_sdk.identity` — `Identity`, `provision_anonymous`, `claim_email`,
  `load_identity` (the resolution chain: explicit → env → `identity.json` → provision).
- `Soul.to_yaml()` and `Soul.add(fact)` (id-preserving merge primitive).
- WJTTC: live **TYRE** push/pull/sync roundtrip (gated on `MCPAAS_API_KEY` + `FAF_SOUL`).

### Changed
- Onboarding is zero-config: `init`'s CTA points at `namepoint push` (auto-provisions),
  with `claim --email` to keep it. The soul's namepoint is stored *as* a `.fafm`
  document (the format is the carrier) — `.faf`/markdown souls interoperate on read.

### Removed
- `namepoint link` — superseded by zero-config provisioning + `claim` (the SDK no
  longer routes users to a manual web claim + token copy).

## [0.2.0] — 2026-05-22

### Added
- CLI `ls` — list every fact in the soul (ranked priority then recency).
- CLI `forget <id>` — delete a fact by id (wraps `Soul.delete_fact`).
- CLI `recall` filters: `--tag` (repeatable), `--type`, `--priority` (min floor) —
  the offline `Soul` API is now fully reachable from the CLI.

### Fixed
- `recall` recency tiebreak: facts sharing a second-granularity timestamp (any
  fast write loop — the demo soul, examples, an agent batch-etching) now return
  **newest-first** instead of insertion order. Recency is deterministic again.

### Changed
- Version is single-sourced from `claude_fafm_sdk.__version__` (hatchling dynamic);
  `pyproject.toml` no longer pins a second copy — no version drift.
- README + namepoint client state the free-namepoint rule accurately: a two-digit
  number makes a handle free (`@james99`, `@john10`; `@john9` isn't), prestige names
  are the paid tier. Claim at the live engine, [mcpaas.live/claim](https://mcpaas.live/claim).

## [0.1.1] — 2026-05-22

### Changed
- README: add PyPI badge + link.
- Cross-link the `grok-faf-voice` voice profile (README + pyproject URL) — two profiles, one `.fafm` format.

## [0.1.0] — 2026-05-21

First cut — the open, offline-first `.fafm` SDK.

### Added
- `Soul` — load/save `.fafm` (vnd.fafm+yaml v1.1), etch (O(1) id-dedup),
  deterministic recall (priority + recency rank), get/delete by id.
- `Fact` — the memory unit (`text` required; id/type/priority/tags/links/… optional).
- `Namepoint` — real MCP client (`fastmcp`, the family standard) for hosted
  souls: `pull` (`get_soul`, public reads) / `push` (`write_soul`, needs a key) /
  `recall`. Wired to the MCPaaS asset core (same backend as grok-faf-voice).
  Optional `[namepoint]` extra — the core stays offline-first. `memory.faf.one`
  front door + free-key signup landing.
- CLI — `claude-fafm-sdk init / etch / recall` (uvx-friendly). `init` prints an
  honest one-liner with a **dynamic real fact count** (0 on a fresh soul; never a
  placeholder). `init --demo` seeds a curated, shippable demo soul (`examples/`).
  No fake "Grok read it back" claims.
- Format-compatible with `fafm-engine` and `grok-faf-voice` — one format, no fork.
- WJTTC 4-tier test regime (BRAKE / ENGINE / AERO; TYRE awaits the backend) +
  `WJTTC.md`; 16 tests, 0 untiered (`faf wjttc`).
- `examples/` — runnable offline → portable → cross-vendor walkthrough + demo soul.
- MIT licensed; `uv`/`uvx`-first install.
