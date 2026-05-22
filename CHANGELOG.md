# Changelog

All notable changes to `claude-fafm-sdk` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).

## [0.1.0] — 2026-05-21

First cut — the open, offline-first `.fafm` SDK.

### Added
- `Soul` — load/save `.fafm` (vnd.fafm+yaml v1.1), etch (O(1) id-dedup),
  deterministic recall (priority + recency rank), get/delete by id.
- `Fact` — the memory unit (`text` required; id/type/priority/tags/links/… optional).
- `Namepoint` — client contract for the free-namepoint full intel (semantic
  recall, smart-merge) at personal scale; backend (`memory.faf.one`) coming.
- Format-compatible with `fafm-engine` and `grok-faf-voice` — one format, no fork.
- MIT licensed; `uv`/`uvx`-first install.
