# claude-fafm-sdk

**Portable, cross-vendor AI memory in `.fafm`.** Give an AI agent memory that
versions with your project and moves between models — instead of being locked to
one vendor.

Offline-first: the local `Soul` works with no account. Connect a free
**namepoint** for the full intel (semantic recall, smart-merge) at personal scale.

## Install

```sh
uv add claude-fafm-sdk          # in a project (recommended)
uvx claude-fafm-sdk             # zero-install run
pip3 install claude-fafm-sdk    # also works
```

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

## Full intel (free namepoint)

A **namepoint** is a free handle on [memory.faf.one](https://memory.faf.one)
where your soul lives (hosted + sticky) and the full intel runs — **semantic /
ranked recall** and **LLM smart-merge** — at personal scale.

```python
from claude_fafm_sdk import Namepoint

np = Namepoint("@me")
np.recall("what did I decide about installs?")   # semantic, server-side
```

*(The namepoint backend is coming. Local `Soul` ops work fully offline today.)*

## Why

AI memory is vendor-locked. `.fafm` is the open, portable format — and this SDK
is the open, offline-first way to use it. Souls written here interop with the
`fafm-engine` and `grok-faf-voice` implementations: one format, never a fork.

## License

MIT. The format is open ([spec](https://github.com/Wolfe-Jam/faf)); the SDK is
open; the at-scale intel + hosting is the paid tier.
