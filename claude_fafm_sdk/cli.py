"""claude-fafm-sdk CLI — init / etch / recall a portable ``.fafm`` soul.

Honest by design: ``init`` creates a real local soul and tells the truth about
it — portable `.fafm`, the open format other tools (grok-faf-voice, fafm-engine)
read. It does NOT claim a live readback or a hosted namepoint that isn't there
yet. The magic is real; we don't fake it.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .soul import Soul

DEFAULT_FILE = "soul.fafm"

# Curated, shippable demo facts (about .fafm itself — never personal memory).
# `init --demo` seeds these; the count printed is always the real len(facts).
DEMO_FACTS: list[tuple[str, str, str, str]] = [
    (".fafm is the open, portable AI-memory format", "what", "project", "high"),
    ("souls move between Claude, Grok and GPT — no vendor lock-in", "why", "project", "high"),
    ("etch writes a fact; recall reads it back, ranked by priority then recency", "ops", "reference", "standard"),
    ("the SDK is offline-first — no account needed for the local soul", "offline", "reference", "standard"),
    ("a free namepoint adds the full intel (semantic recall, smart-merge)", "namepoint", "reference", "standard"),
    ("install leads with uv: `uvx claude-fafm-sdk init`", "install", "reference", "standard"),
    ("one format, never a fork — fafm-engine and grok-faf-voice read the same soul", "interop", "project", "high"),
    ("a fact has text (required) plus optional id, type, priority, tags, links", "schema", "reference", "standard"),
    ("priority vocab: ephemeral, standard, high, critical", "priority", "reference", "ephemeral"),
    ("etch by id is O(1) dedup — re-etching the same id updates in place", "dedup", "reference", "standard"),
]


def _namepoint(name: str | None = None) -> str:
    return f"@claude-code:{name or Path.cwd().name}"


def _fmt_fact(f) -> str:
    """One-line render of a fact for recall/ls output: priority, id, text."""
    head = f"[{f.priority}]"
    if f.id:
        head += f" {f.id}"
    return f"  • {head} — {f.text}"


def cmd_init(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if path.exists() and not args.force:
        print(f"{path} already exists — use --force to overwrite.")
        return 1
    np = _namepoint(args.namepoint)
    soul = Soul(np)
    if args.demo:
        for text, fid, ftype, prio in DEMO_FACTS:
            soul.etch(text, id=fid, type=ftype, priority=prio)
    soul.save(path)
    n = len(soul.facts)  # always the real count — never a placeholder
    print(f"🧬  Soul created — ./{path}")
    print(f"    namepoint  {np}")
    if n:
        print(f"    {n} facts ready — portable .fafm, the open format grok-faf-voice reads.")
        print("    Try:  claude-fafm-sdk recall fafm")
    else:
        print("    Portable .fafm — the open format grok-faf-voice + fafm-engine read.")
        print('    Next:  claude-fafm-sdk etch "your first memory"')
    print("    Cross-vendor → claim a free handle (a two-digit number, e.g. you99)")
    print("      at https://mcpaas.live/claim, then:  claude-fafm-sdk namepoint link <handle>")
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
    hits = Soul.load(path).recall(
        args.query,
        tags=args.tag or None,
        type=args.type,
        min_priority=args.priority,
        limit=args.limit,
    )
    if not hits:
        print("no matches")
        return 0
    for f in hits:
        print(_fmt_fact(f))
    return 0


def cmd_ls(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.exists():
        print(f"{path} not found — run: claude-fafm-sdk init")
        return 1
    soul = Soul.load(path)
    facts = soul.recall(limit=args.limit)  # all facts, ranked priority then recency
    n = len(soul.facts)
    print(f"{n} fact{'s' if n != 1 else ''} in ./{path}  ({soul.namepoint})")
    for f in facts:
        print(_fmt_fact(f))
    return 0


def cmd_forget(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.exists():
        print(f"{path} not found — run: claude-fafm-sdk init")
        return 1
    soul = Soul.load(path)
    if not soul.delete_fact(args.id):
        print(f"no fact with id {args.id!r}")
        return 1
    soul.save(path)
    print(f"forgot {args.id!r} → ./{path}  ({len(soul.facts)} left)")
    return 0


def cmd_namepoint_link(args: argparse.Namespace) -> int:
    """Link this local soul to a claimed namepoint handle. Local metadata only —
    nothing is uploaded here (that's `namepoint push`). Stays honest: no "live"
    claim until a push actually puts it there."""
    path = Path(args.file)
    if not path.exists():
        print(f"{path} not found — run: claude-fafm-sdk init")
        return 1
    soul = Soul.load(path)
    soul.namepoint = args.handle
    soul.save(path)
    has_key = bool(os.environ.get("MCPAAS_API_KEY"))
    print(f"🔗  Linked ./{path} → {args.handle}")
    print("    Push it so Grok (and any model) can read your soul:")
    if has_key:
        print("      claude-fafm-sdk namepoint push")
    else:
        print("      export MCPAAS_API_KEY=...   # token emailed when you claimed at mcpaas.live/claim")
        print("      claude-fafm-sdk namepoint push")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="claude-fafm-sdk", description="Portable .fafm AI memory.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="create a local .fafm soul")
    pi.add_argument("-f", "--file", default=DEFAULT_FILE)
    pi.add_argument("-n", "--namepoint", default=None, help="override the namepoint handle")
    pi.add_argument("--demo", action="store_true", help="seed a curated demo soul")
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
    pr.add_argument("--tag", action="append", default=None, help="filter by tag (repeatable)")
    pr.add_argument("--type", default=None, help="filter by type")
    pr.add_argument(
        "--priority", default="ephemeral", help="minimum priority floor (default: ephemeral)"
    )
    pr.add_argument("--limit", type=int, default=None)
    pr.set_defaults(func=cmd_recall)

    pls = sub.add_parser("ls", help="list every fact in the soul (ranked)")
    pls.add_argument("-f", "--file", default=DEFAULT_FILE)
    pls.add_argument("--limit", type=int, default=None)
    pls.set_defaults(func=cmd_ls)

    pf = sub.add_parser("forget", help="delete a fact by id")
    pf.add_argument("id")
    pf.add_argument("-f", "--file", default=DEFAULT_FILE)
    pf.set_defaults(func=cmd_forget)

    pnp = sub.add_parser("namepoint", help="hosted namepoint ops (link → push/pull coming)")
    npsub = pnp.add_subparsers(dest="np_cmd", required=True)
    pnl = npsub.add_parser("link", help="link this soul to a claimed namepoint handle")
    pnl.add_argument("handle")
    pnl.add_argument("-f", "--file", default=DEFAULT_FILE)
    pnl.set_defaults(func=cmd_namepoint_link)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
