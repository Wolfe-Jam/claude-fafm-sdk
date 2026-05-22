"""02 — Portability: a soul is just a file.

Plain ``vnd.fafm+yaml`` you can read with your own eyes, diff, and commit to git.
No database, no proprietary blob, no lock-in.

    python examples/02_portability.py
"""

from pathlib import Path

from claude_fafm_sdk import Soul

soul = Soul("@me")
soul.etch("memory you can read with your own eyes", id="point", type="project", priority="high")
soul.etch("versions with your code, in git", id="git", type="reference")
path = soul.save("me.fafm")

print(f"--- {path}  (open vnd.fafm+yaml v1.1) ---\n")
print(Path(path).read_text(), end="")
