# claude-fafm-sdk

[![PyPI](https://img.shields.io/pypi/v/claude-fafm-sdk)](https://pypi.org/project/claude-fafm-sdk/) · [![IANA: vnd.fafm+yaml](https://img.shields.io/badge/IANA-vnd.fafm%2Byaml-00D4D4)](https://www.iana.org/assignments/media-types/application/vnd.fafm+yaml) · [![DOI: Memory paper](https://img.shields.io/badge/DOI-Memory%20paper-FF6B35)](https://doi.org/10.5281/zenodo.20348942) · [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Home:** [faf.one/memory](https://faf.one/memory)

**Portable, cross-vendor AI memory in `.fafm`.** Give an AI agent memory that
versions with your project and moves between models — instead of being locked to
one vendor.

### What's New in 1.3.0 — Provable Receipt

1.2 made memory **sendable**; 1.3 makes the proof **one command**. The 60-second
Tier-2 arc — etch → seal → send → merge → recall, plus the falsifiers — now ships
**in the wheel**, so anyone runs it with no git clone:

```sh
uvx claude-fafm-sdk receipt          # → TIER-2 RECEIPT GREEN (exit 0)
```

- **`receipt`** — the whole arc + CRC-reject / double-merge / both-ways falsifiers, one command  
- **`open`** — open a `.fafmp` packet → `.fafm` or a summary (fail-closed)  
- **Sendable (1.2)** — `to_packet` / `merge_packet` + CLI `seal` / `merge`  
- **Mergeable (1.1)** — `merge_souls`, the dual-implementation-verified CvRDT  
- See [CHANGELOG](CHANGELOG.md) for the full list

Offline-first: the local `Soul` works with no account. Connect a free
**namepoint** for the full intel (semantic recall, smart-merge) at personal scale.

> **Two profiles, one `.fafm` format.** This is the **knowledge** profile (typed,
> cross-linked agent memory). For the **voice** profile — the Voice Memory Layer —
> see [grok-faf-voice](https://pypi.org/project/grok-faf-voice/).

## Install

```sh
uv add claude-fafm-sdk          # in a project (recommended)
pip3 install claude-fafm-sdk    # also works
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
claude-fafm-sdk forget install           # delete a fact by id
```

Five commands — `init`, `etch`, `recall`, `ls`, `forget`. Run `claude-fafm-sdk
--help` (or `<cmd> --help`) for the full surface.

Hand `soul.fafm` to `grok-faf-voice` and it reads it — same format, no fork.

## Quickstart

```python
from claude_fafm_sdk import Soul

soul = Soul("@me")
soul.etch("ships uv-first", id="install", type="reference", priority="high")
soul.etch("portable across vendors", id="why", type="project")
soul.save("me.fafm")            # → application/vnd.fafm+yaml

# later, anywhere:
soul = Soul.load("me.fafm")
soul.recall("uv")               # deterministic recall, ranked by priority + recency
```

That's the whole offline loop — no account, no server.

More in **[examples/](examples/)** — portability + a real cross-vendor roundtrip
(SDK writes `.fafm`, grok-faf-voice reads it back).

**Interop contract (v1.0):** [INTEROP.md](INTEROP.md) — timestamps, priority/rank, id collision, unknown fields, `index`, scratchpad/ledger boundary.

## Go cross-vendor (a namepoint)

A **namepoint** is your soul's live address — `mcpaas.live/<handle>` — readable by
Grok and any model. **Zero-config:** just push. With no setup, the first push
auto-provisions an anonymous namepoint and saves it locally — no claim page, no key
to copy.

```sh
uv add "claude-fafm-sdk[namepoint]"      # hosted ops use the family MCP client
claude-fafm-sdk namepoint push           # → live at mcpaas.live/anon… (auto-provisioned)
claude-fafm-sdk namepoint pull           # merge your hosted soul back (public read)
claude-fafm-sdk namepoint sync           # reconcile both ways
```

**A-for-first-touch, B-for-keepers.** The anonymous namepoint is *session-like* —
lose this machine and it orphans (a reminder of the statelessness memory cures).
Make it permanent + recoverable:

```sh
claude-fafm-sdk namepoint claim --email you@example.com   # a named, recoverable namepoint
claude-fafm-sdk namepoint status                           # what you've got
```

The whole `.fafm` document is stored at the namepoint, so ids, types, and
priorities survive the round-trip — structured memory, not prose. Reads are public
(no key); writes use the key auto-provisioning hands you. The local `Soul` still
works fully offline, no account.

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
