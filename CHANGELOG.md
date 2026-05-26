# Changelog

All notable changes to `claude-fafm-sdk` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).

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
