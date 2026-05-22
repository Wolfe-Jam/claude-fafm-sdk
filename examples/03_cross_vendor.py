"""03 — Cross-vendor: the same soul, read by a *different* vendor's tool.

The SDK writes ``.fafm``; grok-faf-voice reads it back with its OWN reader. One
format, never a fork — this is the lock-in breaker.

Verified end-to-end in the grok-faf-voice v0.3.x roundtrip (Claude-native memory
tool → ``.fafm`` → grok read). The read below runs for real if grok-faf-voice is
installed; otherwise the SDK-write half still proves the file is the shared format.

    python examples/03_cross_vendor.py
"""

from claude_fafm_sdk import Soul

# --- Claude side: write a soul with the SDK -------------------------------
soul = Soul("@claude-code:roundtrip")
soul.etch("written by claude-fafm-sdk", id="origin", type="project", priority="high")
soul.etch("read by grok — no lock-in", id="proof", type="project", priority="high")
path = soul.save("roundtrip.fafm")
print(f"SDK wrote {len(soul.facts)} facts → {path}")

# --- Grok side: read the SAME file with grok-faf-voice's own reader --------
try:
    from grok_faf_voice.memory import FAFMemory

    read = FAFMemory.from_file(path)
    print(f"grok-faf-voice read {len(read.facts)} facts back — cross-vendor confirmed.")
except ImportError:
    print("(install grok-faf-voice to run the read half:  uv add grok-faf-voice)")
