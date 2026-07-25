"""claude-fafm-sdk CLI — init / etch / recall / seal / merge a portable ``.fafm`` soul.

Honest by design: ``init`` creates a real local soul and tells the truth about
it — portable `.fafm`, the open format other tools (grok-faf-voice, fafm-engine)
read. It does NOT claim a live readback or a hosted namepoint that isn't there
yet. The magic is real; we don't fake it.

``seal`` / ``merge`` are local file transport (``.fafmp`` Soul-Packet). CRC is
integrity only — not authentication. Fail closed: bad packets never clobber the
local soul. Not the hosted namepoint path.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .identity import Identity
from .packet import PACKET_SUFFIX, PacketError, merge_packet, to_packet_file
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
    print("    Go cross-vendor → just push (a namepoint auto-provisions, zero-config):")
    print("      claude-fafm-sdk namepoint push        # live + readable by Grok")
    print("    Keep it forever:  claude-fafm-sdk namepoint claim --email you@example.com")
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


def cmd_seal(args: argparse.Namespace) -> int:
    """Seal a local ``.fafm`` soul into a CRC-sealed ``.fafmp`` packet (file transport).

    Integrity only — not authentication. See ``PACKET.md``.
    """
    path = Path(args.file)
    if not path.exists():
        print(f"{path} not found — run: claude-fafm-sdk init")
        return 1
    out = Path(args.output) if args.output else path.with_suffix(PACKET_SUFFIX)
    try:
        soul = Soul.load(path)
        to_packet_file(soul, out)
    except PacketError as e:
        print(f"seal failed: {e}")
        return 1
    except (OSError, ValueError) as e:
        print(f"seal failed: {e}")
        return 1
    print(f"sealed → {out}  (SPK1 + CRC-32; integrity only, not auth)")
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    """Ingest a ``.fafmp`` packet into a local soul via the CvRDT merge.

    Fail closed: ``PacketError`` (or namepoint mismatch) → non-zero exit and the
    local soul file is **not** rewritten. Same-namepoint rule as ``merge_souls``.
    """
    path = Path(args.file)
    pkt = Path(args.packet)
    if not path.exists():
        print(f"{path} not found — run: claude-fafm-sdk init")
        return 1
    if not pkt.exists():
        print(f"packet not found: {pkt}")
        return 1
    try:
        local = Soul.load(path)
        # In-memory only until success — never clobber local on bad packet.
        merged = merge_packet(local, pkt.read_bytes())
    except PacketError as e:
        print(f"merge failed: {e}")
        return 1
    except ValueError as e:
        # e.g. different namepoints — oracle rule, not a transport error
        print(f"merge failed: {e}")
        return 1
    except OSError as e:
        print(f"merge failed: {e}")
        return 1
    merged.save(path)
    print(
        f"merged packet → ./{path}  ({len(merged.facts)} fact"
        f"{'s' if len(merged.facts) != 1 else ''}; CvRDT ingest)"
    )
    return 0


def _record_home(soul: Soul, path: Path, namepoint: str) -> None:
    """Stamp the soul file with the namepoint it lives at (cosmetic label)."""
    if soul.namepoint != namepoint:
        soul.namepoint = namepoint
        soul.save(path)


def _identity_for_write() -> tuple[Identity, bool]:
    """(identity, freshly_provisioned). A-for-first-touch: if there's no identity,
    auto-provision an ANONYMOUS one (zero-config) so writes just work."""
    from . import identity as idmod

    ident = idmod.resolve()
    if ident is not None:
        return ident, False
    ident = idmod.provision_anonymous()
    idmod.save_identity(ident)
    return ident, True


def _print_anon_reminder(ident: Identity) -> None:
    print(f"✨  No namepoint yet — provisioned an anonymous one (zero-config): {ident.url}")
    print("    ⚠️  It's session-like — lose this machine and the handle is gone (that's")
    print("        statelessness, the thing memory fixes). Make it permanent + recoverable:")
    print("          claude-fafm-sdk namepoint claim --email you@example.com")


def _read_handle(soul: Soul, args: argparse.Namespace) -> str | None:
    """Namepoint to READ from: --handle → saved identity → soul label (if real)."""
    from . import identity as idmod

    if getattr(args, "handle", None):
        return args.handle
    ident = idmod.resolve()
    if ident is not None:
        return ident.namepoint
    if soul.namepoint and not soul.namepoint.startswith("@claude-code:"):
        return soul.namepoint
    return None


def cmd_namepoint_claim(args: argparse.Namespace) -> int:
    """Get a namepoint identity. `--email` → a recoverable, named namepoint (B,
    keepers); no flag → an anonymous one (A, session-like). Saves it locally so
    push/pull/sync just work."""
    from . import identity as idmod

    path = Path(args.file)
    soul = Soul.load(path) if path.exists() else None
    try:
        ident = idmod.claim_email(args.email) if args.email else idmod.provision_anonymous()
    except idmod.IdentityError as e:
        print(str(e))
        return 1
    idmod.save_identity(ident)
    if soul is not None:
        _record_home(soul, path, ident.namepoint)
    if ident.recoverable:
        print(f"✅  namepoint: {ident.namepoint}  (recoverable) — {ident.url}")
        print("    key saved locally + emailed as backup. push when ready:  claude-fafm-sdk namepoint push")
    else:
        print(f"✅  namepoint: {ident.namepoint}  (anonymous, session-like) — {ident.url}")
        print("    make it permanent:  claude-fafm-sdk namepoint claim --email you@example.com")
    return 0


def cmd_namepoint_status(args: argparse.Namespace) -> int:
    """Show the current namepoint identity (if any)."""
    from . import identity as idmod

    try:
        ident = idmod.load_identity()
    except idmod.IdentityError as e:
        print(str(e))
        return 1
    if ident is None:
        print("no namepoint yet — it auto-provisions on your first push, or claim one now:")
        print("  claude-fafm-sdk namepoint claim --email you@example.com   (recoverable)")
        return 0
    kind = "recoverable (email)" if ident.recoverable else "anonymous (session-like — claim --email to keep)"
    print(f"namepoint:  {ident.namepoint}")
    print(f"url:        {ident.url}")
    print(f"identity:   {kind}")
    return 0


def _merge_into(soul: Soul, incoming: list) -> int:
    """Add facts the local soul lacks — matched by id, else by text — preserving
    each fact's fields (incl. timestamp). Additive: a local id is never overwritten
    (your edits win). Returns the count added. (Set/recency reconcile, not semantic
    merge — that's the paid intel.)"""
    texts = {f.text for f in soul.facts}
    added = 0
    for f in incoming:
        if f.id is not None:
            if soul.get_fact(f.id) is None:
                soul.add(f)
                added += 1
        elif f.text not in texts:
            soul.add(f)
            texts.add(f.text)
            added += 1
    return added


def cmd_namepoint_push(args: argparse.Namespace) -> int:
    """Upload the local soul to the namepoint. The `.fafm`-native write: replace the
    whole hosted document with our `.fafm` (ids + structure intact, idempotent).
    A-for-first-touch: auto-provisions an anonymous identity if none exists. Push
    overwrites the hosted copy — use `sync` to merge instead."""
    import asyncio

    from . import identity as idmod
    from .client import Namepoint, NamepointAuthRequired, NamepointUnavailable

    path = Path(args.file)
    if not path.exists():
        print(f"{path} not found — run: claude-fafm-sdk init")
        return 1
    soul = Soul.load(path)
    try:
        ident, fresh = _identity_for_write()
    except idmod.IdentityError as e:
        print(str(e))
        return 1

    async def run() -> None:
        np = Namepoint(ident.namepoint, api_key=ident.api_key)
        await np.replace(soul.to_yaml())  # full-document replace — the .fafm IS the soul

    try:
        asyncio.run(run())
    except (NamepointUnavailable, NamepointAuthRequired) as e:
        print(str(e))
        return 1
    _record_home(soul, path, ident.namepoint)
    if fresh:
        _print_anon_reminder(ident)
    n = len(soul.facts)
    print(f"⬆️  pushed your soul ({n} fact{'s' if n != 1 else ''}) → {ident.url}")
    print("    live + readable by Grok and any model.")
    return 0


def cmd_namepoint_pull(args: argparse.Namespace) -> int:
    """Merge hosted facts into the local soul (additive, by id). Reads are public —
    no key. If the hosted soul is a `.fafm` document, facts come back structured
    (ids intact); a markdown/voice soul simply yields no structured facts."""
    import asyncio

    from .client import Namepoint, NamepointUnavailable

    path = Path(args.file)
    soul = Soul.load(path) if path.exists() else None
    if soul is None:
        print(f"{path} not found — run: claude-fafm-sdk init")
        return 1
    handle = _read_handle(soul, args)
    if handle is None:
        print("no namepoint yet — claim or push first, or pass --handle <name>")
        return 1

    async def run() -> list:
        return await Namepoint(handle).facts()  # public read, no key

    try:
        hosted = asyncio.run(run())
    except NamepointUnavailable as e:
        print(str(e))
        return 1
    added = _merge_into(soul, hosted)
    soul.save(path)
    print(f"⬇️  pulled {added} new fact{'s' if added != 1 else ''} from {handle} "
          f"→ ./{path}  ({len(soul.facts)} total)")
    return 0


def cmd_namepoint_sync(args: argparse.Namespace) -> int:
    """Reconcile local <-> hosted: merge hosted facts into the local soul (by id),
    then replace the hosted document with the union. `.fafm`-native + idempotent.
    A-for-first-touch: auto-provisions an anonymous identity if none."""
    import asyncio

    from . import identity as idmod
    from .client import Namepoint, NamepointAuthRequired, NamepointUnavailable

    path = Path(args.file)
    if not path.exists():
        print(f"{path} not found — run: claude-fafm-sdk init")
        return 1
    soul = Soul.load(path)
    try:
        ident, fresh = _identity_for_write()
    except idmod.IdentityError as e:
        print(str(e))
        return 1

    async def run() -> int:
        np = Namepoint(ident.namepoint, api_key=ident.api_key)
        pulled = _merge_into(soul, await np.facts())  # hosted → local (by id)
        await np.replace(soul.to_yaml())  # write the union back as the soul
        return pulled

    try:
        pulled = asyncio.run(run())
    except (NamepointUnavailable, NamepointAuthRequired) as e:
        print(str(e))
        return 1
    soul.save(path)
    _record_home(soul, path, ident.namepoint)
    if fresh:
        _print_anon_reminder(ident)
    print(f"🔄  synced {ident.namepoint} ↔ ./{path}  (↓ {pulled} new local; union pushed; "
          f"{len(soul.facts)} facts)")
    print(f"    live: {ident.url}")
    return 0


def _is_interactive() -> bool:
    return sys.stdin.isatty()


def cmd_wizard(args: argparse.Namespace) -> int:
    """Guided first-run: soul → first memory → live & cross-vendor → proof. The
    30-second wow. Interactive in a terminal; in a non-tty it does the safe local
    steps and points at the manual commands (never auto-pushes without a yes)."""
    interactive = _is_interactive()

    def ask(prompt: str, default: str = "") -> str:
        if not interactive:
            return default
        try:
            return input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return default

    path = Path(args.file)
    print("🧬  claude-fafm-sdk — give your AI a memory that follows you.\n")

    # 1 · soul (create or reuse)
    if path.exists():
        soul = Soul.load(path)
        print(f"Found your soul — ./{path} ({len(soul.facts)} fact{'s' if len(soul.facts) != 1 else ''}).")
    else:
        soul = Soul(_namepoint(getattr(args, "namepoint", None)))
        soul.save(path)
        print(f"Created ./{path} — a portable .fafm soul (offline, no account).")

    # 2 · first memory
    first = ask("\nWhat should your AI always remember about you?\n  (one line — Enter to skip) > ")
    if first:
        soul.etch(first, id="about", type="user", priority="high")
        soul.save(path)
        print(f"  etched ✓  ({len(soul.facts)} fact{'s' if len(soul.facts) != 1 else ''})")

    # 3 · go live?
    if not interactive:
        print("\nSaved locally. Go live + cross-vendor anytime:  claude-fafm-sdk namepoint push")
        return 0
    go = ask(
        "\nMake it live + readable by Grok, Claude & Gemini?\n"
        "  (provisions a free namepoint, zero-config) [Y/n] > ",
        "y",
    )
    if go.lower() not in ("", "y", "yes"):
        print("\nSaved locally. Push when ready:  claude-fafm-sdk namepoint push")
        return 0

    # 4 · push (real — reuse the zero-config flow)
    import asyncio

    from . import identity as idmod
    from .client import Namepoint, NamepointAuthRequired, NamepointUnavailable

    print("\n  provisioning a namepoint + uploading…")
    try:
        ident, _fresh = _identity_for_write()
        asyncio.run(Namepoint(ident.namepoint, api_key=ident.api_key).replace(soul.to_yaml()))
    except (idmod.IdentityError, NamepointUnavailable, NamepointAuthRequired) as e:
        print(f"\n  {e}")
        return 1
    _record_home(soul, path, ident.namepoint)

    # 5 · the proof — see it read cross-vendor
    raw = f"https://mcpaas.live/raw/{ident.namepoint}"
    print(f"\n✨  Live: {ident.url}")
    print(f"    Read it back, no login:  {raw}")
    print("    Hand it to any model — paste this into Grok, Claude or Gemini:")
    print(f"      Read {raw} and tell me what you know about me.")
    print("\n    It's anonymous + session-like. Keep it forever:")
    print("      claude-fafm-sdk namepoint claim --email you@example.com")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="claude-fafm-sdk", description="Portable .fafm AI memory.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=False)

    pq = sub.add_parser("quickstart", help="guided first-run: soul → live → cross-vendor (the 30-second wow)")
    pq.add_argument("-f", "--file", default=DEFAULT_FILE)
    pq.add_argument("-n", "--namepoint", default=None, help="override the namepoint handle")
    pq.set_defaults(func=cmd_wizard)

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

    ps = sub.add_parser(
        "seal",
        help="seal a local .fafm into a CRC-sealed .fafmp packet (file transport; integrity only)",
    )
    ps.add_argument("-f", "--file", default=DEFAULT_FILE, help="local .fafm soul (default: soul.fafm)")
    ps.add_argument(
        "-o",
        "--output",
        default=None,
        help=f"output packet path (default: <soul>{PACKET_SUFFIX})",
    )
    ps.set_defaults(func=cmd_seal)

    pm = sub.add_parser(
        "merge",
        help="ingest a .fafmp packet into a local soul (CvRDT; fail-closed, no clobber on bad packet)",
    )
    pm.add_argument("packet", help="path to the .fafmp packet")
    pm.add_argument("-f", "--file", default=DEFAULT_FILE, help="local .fafm soul to merge into")
    pm.set_defaults(func=cmd_merge)

    pnp = sub.add_parser("namepoint", help="hosted namepoint ops (claim / status / push / pull / sync)")
    npsub = pnp.add_subparsers(dest="np_cmd", required=True)

    pnc = npsub.add_parser("claim", help="get a namepoint — --email for a recoverable one, else anonymous")
    pnc.add_argument("--email", default=None, help="claim a recoverable, named namepoint for this email")
    pnc.add_argument("-f", "--file", default=DEFAULT_FILE)
    pnc.set_defaults(func=cmd_namepoint_claim)

    pnst = npsub.add_parser("status", help="show the current namepoint identity")
    pnst.set_defaults(func=cmd_namepoint_status)

    pnpush = npsub.add_parser("push", help="upload local facts (auto-provisions anonymously first time)")
    pnpush.add_argument("-f", "--file", default=DEFAULT_FILE)
    pnpush.set_defaults(func=cmd_namepoint_push)

    pnpull = npsub.add_parser("pull", help="merge hosted facts into the local soul (public read)")
    pnpull.add_argument("-f", "--file", default=DEFAULT_FILE)
    pnpull.add_argument("--handle", default=None, help="read a specific namepoint instead of yours")
    pnpull.set_defaults(func=cmd_namepoint_pull)

    pnsync = npsub.add_parser("sync", help="reconcile local <-> hosted (auto-provisions first time)")
    pnsync.add_argument("-f", "--file", default=DEFAULT_FILE)
    pnsync.set_defaults(func=cmd_namepoint_sync)

    args = p.parse_args(argv)
    if getattr(args, "func", None) is None:
        # No subcommand → the guided first-run wizard.
        return cmd_wizard(argparse.Namespace(file=DEFAULT_FILE, namepoint=None))
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
