"""01 — Quickstart: a portable soul in five lines, fully offline (no account).

    python examples/01_quickstart.py
"""

from claude_fafm_sdk import Soul

soul = Soul("@me")
soul.etch("ships uv-first", id="install", type="reference", priority="high")
soul.etch("portable across vendors", id="why", type="project")
soul.save("me.fafm")

for fact in Soul.load("me.fafm").recall("uv"):
    print("recall →", fact.text)
