# claude-fafm-sdk

[![PyPI](https://img.shields.io/pypi/v/claude-fafm-sdk)](https://pypi.org/project/claude-fafm-sdk/) · [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE) · [memory.faf.one](https://memory.faf.one)

**Portable, cross-vendor AI memory in `.fafm`.** Give an AI agent memory that
versions with your project and moves between models — instead of being locked to
one vendor.

Offline-first: the local `Soul` works with no account. Connect a free
**namepoint** for the full intel (semantic recall, smart-merge) at personal scale.

## Install

```sh
uv add claude-fafm-sdk          # in a project (recommended)
pip3 install claude-fafm-sdk    # also works
```

## 30 seconds

```sh
uvx claude-fafm-sdk init                 # 🧬 create a portable soul
claude-fafm-sdk etch "ships uv-first"    # write a memory
claude-fafm-sdk recall uv                # recall it
```

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

## Full intel (free namepoint)

A **namepoint** is a free handle on [memory.faf.one](https://memory.faf.one)
where your soul lives (hosted + sticky) and the full intel runs at personal scale.
Hosted reads/writes use the family-standard MCP client (`fastmcp`), an opt-in extra:

```sh
uv add "claude-fafm-sdk[namepoint]"
```

```python
from claude_fafm_sdk import Namepoint

np = Namepoint("@me", api_key="...")        # free key from memory.faf.one
await np.push("a durable fact", type="fact")
body = await np.pull()                       # reads are public — no key
```

Wired to the MCPaaS asset core — the same backend grok-faf-voice uses
(`get_soul` / `write_soul`). The `memory.faf.one` front door + free-namepoint
signup are landing; the local `Soul` works fully offline today, no account.

## Why

AI memory is vendor-locked. `.fafm` is the open, portable format — and this SDK
is the open, offline-first way to use it. Souls written here interop with the
`fafm-engine` and `grok-faf-voice` implementations: one format, never a fork.

## License

MIT. The format is open ([spec](https://github.com/Wolfe-Jam/faf)); the SDK is
open; the at-scale intel + hosting is the paid tier.
