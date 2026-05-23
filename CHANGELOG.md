# Changelog

All notable changes to `claude-fafm-sdk` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).

## [Unreleased]

### Added
- **The STICK loop — `namepoint` command group** (local soul ↔ hosted namepoint):
  - `namepoint link <handle>` — link a claimed handle to the local soul (local
    metadata; stays honest — no "live" claim until a real push).
  - `namepoint push` — upload local facts; dedups client-side by text against the
    current hosted state (the wire is append-only with no server dedup), so re-runs
    are idempotent. Needs `MCPAAS_API_KEY`.
  - `namepoint pull` — merge hosted facts into the local soul; keyless (reads are
    public); dedup by text.
  - `namepoint sync` — reconcile both ways (union by text: pull hosted-only down,
    push local-only up). Client-side set-difference, not smart-merge (merge is the
    paid intel). Needs `MCPAAS_API_KEY`.
- `init` now prints a cross-vendor CTA → claim a free two-digit handle at
  mcpaas.live/claim, then `namepoint link`.
- WJTTC: live **TYRE** roundtrip test (gated on `MCPAAS_API_KEY` + `CFS_TEST_NAMEPOINT`).

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
