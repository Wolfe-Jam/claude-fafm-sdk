# Changelog

All notable changes to `claude-fafm-sdk` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).

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
