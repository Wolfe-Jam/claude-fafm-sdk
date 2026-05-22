"""claude-fafm-sdk CLI — init / etch / recall a portable ``.fafm`` soul.

Honest by design: ``init`` creates a real local soul and tells the truth about
it — portable `.fafm`, the open format other tools (grok-faf-voice, fafm-engine)
read. It does NOT claim a live readback or a hosted namepoint that isn't there
yet. The magic is real; we don't fake it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .soul import Soul

DEFAULT_FILE = "soul.fafm"


def _namepoint(name: str | None = None) -> str:
    return f"@claude-code:{name or Path.cwd().name}"


def cmd_init(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if path.exists() and not args.force:
        print(f"{path} already exists — use --force to overwrite.")
        return 1
    np = _namepoint(args.namepoint)
    Soul(np).save(path)
    print(f"🧬  Soul created — ./{path}")
    print(f"    namepoint  {np}")
    print("    Portable .fafm — the open format grok-faf-voice + fafm-engine read.")
    print(f'    Next:  claude-fafm-sdk etch "your first memory"')
    return 0


def cmd_etch(args: argparse.Namespace) -> int:
    path = Path(args.file)
    soul = Soul.load(path) if path.exists() else Soul(_namepoint())
    soul.etch(args.text, id=args.id, type=args.type, priority=args.priority)
    soul.save(path)
    print(f"etched → ./{path}  ({len(soul.facts)} fact{'s' if len(soul.facts) != 1 else ''})")
    return 0


def cmd_recall(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.exists():
        print(f"{path} not found — run: claude-fafm-sdk init")
        return 1
    hits = Soul.load(path).recall(args.query, limit=args.limit)
    if not hits:
        print("no matches")
        return 0
    for f in hits:
        print(f"  • {f.text}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="claude-fafm-sdk", description="Portable .fafm AI memory.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="create a local .fafm soul")
    pi.add_argument("-f", "--file", default=DEFAULT_FILE)
    pi.add_argument("-n", "--namepoint", default=None, help="override the namepoint handle")
    pi.add_argument("--force", action="store_true", help="overwrite an existing soul")
    pi.set_defaults(func=cmd_init)

    pe = sub.add_parser("etch", help="write a fact to the soul")
    pe.add_argument("text")
    pe.add_argument("-f", "--file", default=DEFAULT_FILE)
    pe.add_argument("--id", default=None)
    pe.add_argument("--type", default=None)
    pe.add_argument("--priority", default="standard")
    pe.set_defaults(func=cmd_etch)

    pr = sub.add_parser("recall", help="recall facts from the soul")
    pr.add_argument("query", nargs="?", default=None)
    pr.add_argument("-f", "--file", default=DEFAULT_FILE)
    pr.add_argument("--limit", type=int, default=None)
    pr.set_defaults(func=cmd_recall)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
