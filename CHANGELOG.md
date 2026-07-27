# Changelog

All notable changes to `claude-fafm-sdk` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).

## [1.4.0] — 2026-07-27

**Verifiable Provenance.** 1.3 proved a packet travels *intact*; 1.4 lets it prove
*which key sealed it*. A packet MAY now carry an **optional Ed25519 signature** over the
same payload bytes CRC covers — integrity (CRC) and provenance (signature) stay
separate. Opt-in via the `[sign]` extra; the base SDK **and** the Provable Receipt
remain zero-crypto (pyyaml only). The merge oracle is untouched — this is transport.

### Added
- **Signing (`[sign]` extra → `cryptography`)** — `claude_fafm_sdk.signer` with
  `generate_keypair`, `sign_packet(soul, private_key)`, `verify_packet(data,
  public_key)` (also top-level on the package). Ed25519 over the raw canonical
  payload; a **fixed 64-byte** trailer, no `key_id`. `[sign]` missing → a clean
  "install `claude-fafm-sdk[sign]`" message, never a raw `ImportError`.
- **Signed wire** — header `flags` bit 0 = `SIGNED` (`0x0001`); a signed packet is
  `16-byte header + N-byte payload + 64-byte signature`. Unsigned seals are
  **byte-identical** to 1.2/1.3 (`flags=0`, no trailer).
- **CLI `keygen` / `seal --sign --key` / `verify -k`** — `keygen` writes
  `sign.pem` (`0600`) + `sign.pub.pem`; `verify` exits 0 (good) / 1 (bad).
- **Strict open** — `from_packet` and CLI `open` reject a signed packet with a
  pointer to `verify`; `merge_packet(local, data, public_key=…)` **verifies** a
  signed peer before ingest (never CRC-opens it) and rejects a signed packet given
  no key. A signed packet is rejected by old 1.2/1.3 readers (length-exact).
- **Fixed-fixture golden** — a signed wire-hex golden pinned from a **TEST-ONLY**
  32-byte seed; the repo commits **only the public PEM** (no private key material).
  Ed25519 is deterministic, so the golden reproduces on any machine.

### Verification
```
pip install 'claude-fafm-sdk[sign]'
claude-fafm-sdk keygen                                          # sign.pem (0600) + sign.pub.pem
claude-fafm-sdk seal -f soul.fafm -o soul.fafmp --sign --key sign.pem
claude-fafm-sdk verify soul.fafmp -k sign.pub.pem               # → signature OK (exit 0)
uvx claude-fafm-sdk receipt                                     # still GREEN, zero-crypto
```
- **We claim:** an optional Ed25519 signature binds a key to the sealed payload
  bytes (the same bytes CRC covers); verify is strict and fails closed; signed
  packets never CRC-open; unsigned seals are byte-identical to 1.3; base + receipt
  need no crypto.
- **We do NOT claim:** authentication branding, "authenticated memory", encryption,
  or a human identity (a key is not a person); a CA/CRL/PKI; that a signature
  prevents a **strip-downgrade** — stripping the 64-byte trailer and clearing the
  `SIGNED` flag recovers an equivalent unsigned packet of the same payload (the
  flag is not signed; verify proves *this key signed these bytes*, not *this
  content can only travel signed*); FAFB signing or `FLAG_SIGNED` interop (`SPK1` ≠
  `FAFB`); a `key_id` / embedded public key (→ 1.4.1); a signed-receipt one-liner
  (→ 1.4.1); namepoint↔key binding; delete convergence (grow/update-only — → 1.5);
  and verify does **not** re-prove the dual-implementation CvRDT merge (transport +
  ingest only; dual-impl remains the 1.1 story).

## [1.3.0] — 2026-07-26

**Provable Receipt.** 1.2 made memory *sendable*; 1.3 makes the proof *one
command*. The 60-second Tier-2 arc — etch → seal → send a file → merge → recall,
plus the falsifiers — now ships **inside the wheel**, so a stranger runs it with
no git clone. The merge is unchanged (the dual-implementation-verified CvRDT).

### Added
- **`claude-fafm-sdk receipt`** — runs the full Tier-2 proof in-process:
  etch→seal→send→merge→recall + **CRC-reject**, **double-merge idempotent**, and
  **both-ways converge** falsifiers. Exit 0 + a GREEN banner; non-zero if any
  check fails. `--json` for machine-readable PASS/FAIL. Works via
  **`uvx claude-fafm-sdk receipt`** from the published package.
- **`claude-fafm-sdk open`** — open a `.fafmp` packet → write `.fafm` or print a
  summary. Fail-closed: a bad packet exits non-zero, no partial write. Thin over
  `from_packet`.

### Verification
The receipt is now the proof — one command, no clone:
```
uvx claude-fafm-sdk receipt          # → TIER-2 RECEIPT GREEN (exit 0)
uvx claude-fafm-sdk receipt --json   # machine-readable
```
- **We claim:** the 60-second Tier-2 proof runs from the published package via
  `uvx claude-fafm-sdk receipt`; CLI `open` is fail-closed; same SPK1 / CvRDT
  semantics as 1.2 (no merge-law change).
- **We do NOT claim:** authentication or encryption (CRC = integrity, not auth —
  see 1.4); delete convergence (grow/update-only — see 1.5); session-id LWW, the
  full FAFB binary, or an IANA packet media type; that the receipt re-proves the
  dual-implementation merge (it exercises transport + ingest; dual-impl remains
  the 1.1 story).

## [1.2.0] — 2026-07-25

**Sendable Memory.** 1.1 made souls *mergeable*; 1.2 makes them *sendable* — seal
a soul into a CRC-integrity `.fafmp` packet, send the file, merge on arrival. The
merge is unchanged (the dual-implementation-verified CvRDT); this adds the
transport around it.

### Added
- **`claude_fafm_sdk.packet`** — top-level `to_packet` / `from_packet` /
  `merge_packet` (+ `to_packet_file` / `from_packet_file`, `PacketError`). An
  `SPK1` packet is a 16-byte little-endian header + canonical `.fafm` YAML,
  sealed with **CRC-32** over the payload. `merge_packet(local, data)` is exactly
  `merge_souls(local, from_packet(data))` — ingest reuses the CvRDT.
- **CLI `seal` / `merge`** — `claude-fafm-sdk seal -f soul.fafm -o out.fafmp` and
  `claude-fafm-sdk merge -f soul.fafm packet.fafmp`. File transport only (not
  namepoint push/pull). Fail-closed: a bad packet exits non-zero and never
  rewrites the local soul.
- **Byte-identity** — two seals of the same logical state are byte-for-byte equal
  (canonical dump by construction); a **wire-hex golden** pins the exact bytes as
  a cross-language interop anchor.
- **`PACKET.md` / `RECEIPT.md`** — packet format + the 60-second proof.
- **Hardening** — extended residual-field coverage + goldens, and an
  encoding-lock fuzz suite over `normalize_text` / `content_hash` / the `{v,t}`
  wrapper.

### Verification
Install proof (from the published wheel):
```
uvx claude-fafm-sdk quickstart              # or: pip install claude-fafm-sdk==1.2.0
python -c "from claude_fafm_sdk import to_packet, from_packet, merge_packet; print('sealable')"
```
The **60-second Tier-2 receipt** — a stranger runs the whole arc and falsifies it:
```
git clone https://github.com/Wolfe-Jam/claude-fafm-sdk && cd claude-fafm-sdk
git checkout v1.2.0 && uv run --extra dev pytest tests/test_wjttc_packet.py tests/test_wjttc_cli_packet.py
bash examples/tier2_receipt.sh              # etch→seal→send→merge→recall + CRC/idempotent/both-ways falsifiers
```
- **We claim:** memory travels as a CRC-integrity-sealed `.fafmp` packet and
  ingests through the same state-based CvRDT; seals are byte-deterministic.
- **We do NOT claim:** authentication or encryption (CRC = integrity, not auth);
  offline delete convergence (grow/update-only); the full FAFB binary or an IANA
  media type (`SPK1` is the v0 packet seal, distinct from `FAFB`).

## [1.1.1] — 2026-07-24

Packaging + reproducibility fix for the 1.1.0 Soul-Packet merge (1.1.0 was
TestPyPI-only; this is the first production merge release). **No API or
merge-logic change** — `merge_souls` and the CvRDT semantics are identical.

### Fixed
- **`hypothesis` added to dev extras** — the merge property + N-version suites
  import it; `pip install -e ".[dev]"` now runs them from a source checkout.
- **Reproduction receipt corrected** — the prior one-liner assumed you were already
  in a repo checkout with test deps. The receipt below is actually runnable by a
  stranger: an install-proof from the published wheel, plus the full property suite
  from a source checkout (tests are not shipped inside the wheel).

### Verification
Install proof (from the published wheel):
```
pip install claude-fafm-sdk==1.1.1
python -c "from claude_fafm_sdk import merge_souls, __version__; print(__version__, merge_souls)"
```
Full property-suite reproduction (from source — tests are not in the wheel):
```
git clone https://github.com/Wolfe-Jam/claude-fafm-sdk && cd claude-fafm-sdk
git checkout v1.1.1
pip install -e ".[dev]"
pytest tests/test_wjttc_merge_crdt.py tests/test_nversion_differential.py
```
- **We claim:** the merge is a state-based **CvRDT** under a frozen encoding lock,
  verified by two independent implementations (N-version).
- **We do NOT claim:** sealed-packet send / CRC (next release), offline delete
  convergence (grow/update-only in v1), or verification across all AIs beyond the
  N-version process.

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
Reproducible receipt: see **1.1.1** — the receipt command was corrected there
(1.1.0 was TestPyPI-only). Claims for this feature:
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
