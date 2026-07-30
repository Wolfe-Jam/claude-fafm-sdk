# claude-fafm-sdk

[![PyPI](https://img.shields.io/pypi/v/claude-fafm-sdk)](https://pypi.org/project/claude-fafm-sdk/) · [![IANA: vnd.fafm+yaml](https://img.shields.io/badge/IANA-vnd.fafm%2Byaml-00D4D4)](https://www.iana.org/assignments/media-types/application/vnd.fafm+yaml) · [![DOI: Memory paper](https://img.shields.io/badge/DOI-Memory%20paper-FF6B35)](https://doi.org/10.5281/zenodo.20348942) · [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Home:** [faf.one/memory](https://faf.one/memory) · **Blog:** [Forgettable Memory](https://faf.one/blog/forgettable-memory)

**Portable, cross-vendor AI memory in `.fafm`.** Give an AI agent memory that
versions with your project and moves between models — instead of being locked to
one vendor.

| | |
|--|--|
| **Edition** | **Forgettable Memory** |
| **Release** | **[1.5.2](https://pypi.org/project/claude-fafm-sdk/1.5.2/)** (docs/polish) |
| **Product cut** | **1.5.1** — first 1.5.x on PyPI (no production 1.5.0) |

### What's New in 1.5.2 — Docs and polish

**Docs and polish — PyPI front door matches Forgettable Memory (1.5.1 production cut); no lattice change.**

Same product as 1.5.1. This patch bakes the correct front door into the package long-description
(PyPI freezes README at publish). No merge, wire, or API change.

### Product: Forgettable Memory (1.5.x)

Until 1.5, every edition only *grew* the soul: delete was absence, and merge
resurrected whatever a peer still held. **1.5 makes a delete state** —
`forget` writes a **tombstone** that travels with the soul, joins as an LWW
max-register, and **suppresses** the fact on emit. **1.5.1** is the production
cut: forget converges on **both** the packet path *and* hosted namepoint
`pull` / `sync` (same CvRDT). Could have been 2.0; we kept the arc honest as 1.5.

#### Key features (1.5.x)

- **`Soul.forget` / `forget_text` + CLI `forget`** — remove the live fact **and** write a tombstone  
- **Both transports** — packet (`seal` / `merge`) **and** hosted (`pull` / `sync`)  
- **Tombstone ≠ secure erase** — lattice convergence, not forensic wipe  
- **Verifiable Provenance (1.4)** — optional Ed25519 (`[sign]` extra); base path zero-crypto  
- **Provable Receipt (1.3)** · **Sendable (1.2)** · **Mergeable (1.1)**  

**Arc:** Mergeable → Sendable → Provable → Verifiable → **Forgettable**

Full detail: [CHANGELOG](CHANGELOG.md) · [faf.one/blog/forgettable-memory](https://faf.one/blog/forgettable-memory)

```sh
uvx claude-fafm-sdk --version          # → 1.5.2
uvx claude-fafm-sdk forget --help
claude-fafm-sdk forget secret-id       # id — or: forget --text "…"
claude-fafm-sdk seal -f soul.fafm -o out.fafmp   # tombstones ride the packet
# hosted: push → pull/sync go through merge_souls — forgotten stays forgotten
```

Offline-first: the local `Soul` works with no account. Connect a free
**namepoint** for the full intel (semantic recall, smart-merge) at personal scale.

> **Two profiles, one `.fafm` format.** This is the **knowledge** profile (typed,
> cross-linked agent memory). For the **voice** profile — the Voice Memory Layer —
> see [grok-faf-voice](https://pypi.org/project/grok-faf-voice/).

## Install

```sh
uv add claude-fafm-sdk                 # in a project (recommended)
pip3 install claude-fafm-sdk==1.5.2    # pin the front door you expect
# optional provenance:
pip3 install 'claude-fafm-sdk[sign]==1.5.2'
# optional hosted namepoint client:
uv add "claude-fafm-sdk[namepoint]"
```

## 30 seconds

New here? One guided command takes you soul → live → cross-vendor:

```sh
uvx claude-fafm-sdk quickstart           # 🧬 guided first-run (the 30-second wow)
```

Or drive it yourself:

```sh
uvx claude-fafm-sdk init                 # 🧬 create a portable soul
claude-fafm-sdk etch "ships uv-first"    # write a memory
claude-fafm-sdk recall uv                # recall it  (filters: --tag --type --priority)
claude-fafm-sdk ls                       # list every fact, ranked
claude-fafm-sdk forget install           # convergent delete by id (tombstone)
```

Five commands — `init`, `etch`, `recall`, `ls`, `forget`. Run `claude-fafm-sdk
--help` (or `<cmd> --help`) for the full surface.

Hand `soul.fafm` to `grok-faf-voice` and it reads it — same format, no fork.

## How it works

```python
from claude_fafm_sdk import Soul

soul = Soul("@me")
soul.etch("ships uv-first", id="install", type="reference", priority="high")
soul.etch("portable across vendors", id="why", type="project")
soul.forget("install")          # tombstone — merge will not resurrect
soul.save("me.fafm")            # → application/vnd.fafm+yaml

# later, anywhere:
soul = Soul.load("me.fafm")
soul.recall("uv")               # deterministic recall, ranked by priority + recency
```

That's the whole offline loop — no account, no server. Deletes travel as
**state** (tombstones) so peers converge without lying about the join.

More in **[examples/](examples/)** — portability + a real cross-vendor roundtrip
(SDK writes `.fafm`, grok-faf-voice reads it back).

**Interop contract (v1.0):** [INTEROP.md](INTEROP.md) — timestamps, priority/rank, id collision, unknown fields, `index`, scratchpad/ledger boundary.  
**Merge + tombstones:** [MERGE.md](MERGE.md) · **Packets:** [PACKET.md](PACKET.md) · **Provenance:** [PROVENANCE.md](PROVENANCE.md)

## Go cross-vendor (a namepoint)

A **namepoint** is your soul's live address — `mcpaas.live/<handle>` — readable by
Grok and any model. **Zero-config:** just push. With no setup, the first push
auto-provisions an anonymous namepoint and saves it locally — no claim page, no key
to copy.

```sh
uv add "claude-fafm-sdk[namepoint]"      # hosted ops use the family MCP client
claude-fafm-sdk namepoint push           # → live at mcpaas.live/anon… (auto-provisioned)
claude-fafm-sdk namepoint pull           # merge via CvRDT (forget converges)
claude-fafm-sdk namepoint sync           # reconcile both ways
```

**A-for-first-touch, B-for-keepers.** The anonymous namepoint is *session-like* —
lose this machine and it orphans (a reminder of the statelessness memory cures).
Make it permanent + recoverable:

```sh
claude-fafm-sdk namepoint claim --email you@example.com   # a named, recoverable namepoint
claude-fafm-sdk namepoint status                           # what you've got
```

The whole `.fafm` document is stored at the namepoint, so ids, types, priorities,
**and tombstones** survive the round-trip — structured memory, not prose. Reads are
public (no key); writes use the key auto-provisioning hands you. The local `Soul`
still works fully offline, no account.

Programmatic access mirrors the CLI:

```python
from claude_fafm_sdk import Namepoint, Soul, provision_anonymous

soul = Soul.load("soul.fafm")
ident = provision_anonymous()                       # {namepoint, key}, zero-config
await Namepoint(ident.namepoint, api_key=ident.api_key).replace(soul.to_yaml())
body = await Namepoint(ident.namepoint).pull()      # reads are public — no key
```

## Why

AI memory is vendor-locked. `.fafm` is the open, portable format — and this SDK
is the open, offline-first way to use it. Souls written here interop with the
`fafm-engine` and `grok-faf-voice` implementations: one format, never a fork.
Memory that grows, moves, proves, signs — and can forget without resurrecting on join.

## Citation

If you use `claude-fafm-sdk` or the `.fafm` format in research or production, please cite the format paper:

> Wolfe, J. (2026). *Permanent Memory and Instant Recall: The .fafm Standard for Multi-Profile AI Agent Memory*. Zenodo. https://doi.org/10.5281/zenodo.20348942

### BibTeX

```bibtex
@article{wolfe2026fafm,
  title     = {Permanent Memory and Instant Recall: The .fafm Standard for Multi-Profile AI Agent Memory},
  author    = {Wolfe, James},
  year      = {2026},
  month     = {may},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.20348942},
  url       = {https://doi.org/10.5281/zenodo.20348942}
}
```

**DOI:** [`10.5281/zenodo.20348942`](https://doi.org/10.5281/zenodo.20348942)

## License

MIT. The format is open ([spec](https://github.com/Wolfe-Jam/faf)); the SDK is
open; the at-scale intel + hosting is the paid tier.
