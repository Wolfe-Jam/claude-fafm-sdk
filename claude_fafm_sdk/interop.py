"""Cross-format interop helpers for ``.fafm`` (v1.0).

``from_claude_dir`` converts a Claude Code auto-memory store (topic ``.md``
files with YAML frontmatter) into a knowledge-profile :class:`Soul`.

Approach cited from ``fafm-engine/scripts/serialize_memory.py`` — not the
proof ``convert_md_to_fafm.py`` (which emits ``memory.entries`` / version 1.0).

Claude ``metadata.originSessionId`` is parked under
``Fact.extra["provenance"]`` (reserved schema field; not a first-class Fact
attribute in v1.0 — INTEROP §4).
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any

import yaml

from .soul import Fact, Soul

# Index / non-topic files in a Claude Code memory directory.
DEFAULT_SKIP = frozenset({"MEMORY.md", "MEMORY-FULL.md", "README.md"})

# Schema knowledge types only (strict — untyped / other types are skipped).
KNOWLEDGE_TYPES = frozenset({"user", "feedback", "project", "reference"})

_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _iso_mtime(path: Path) -> str:
    return datetime.datetime.fromtimestamp(
        path.stat().st_mtime, tz=datetime.timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    try:
        fm = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None, text
    body = parts[2].strip()
    return (fm if isinstance(fm, dict) else None), body


def _fact_from_topic(path: Path, *, body: str, fm: dict[str, Any]) -> Fact | None:
    """Build one Fact from a topic file, or None if it fails the type/name gate."""
    if "name" not in fm or not fm["name"]:
        return None
    meta = fm.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}
    mtype = meta.get("type")
    if mtype not in KNOWLEDGE_TYPES:
        return None

    name = str(fm["name"]).strip()
    description = (fm.get("description") or "").strip() if fm.get("description") else ""
    text = description or name

    extra: dict[str, Any] = {}
    origin = meta.get("originSessionId")
    if origin:
        # Engine-shaped reserved field — rides in Fact.extra (INTEROP §4).
        extra["provenance"] = [f"session:{origin}"]

    links = sorted(set(_LINK_RE.findall(body)))
    return Fact(
        text=text,
        id=name,
        type=str(mtype),
        priority="standard",
        tags=[],
        links=links,
        timestamp=_iso_mtime(path),
        source=f"claude-code memory: {path.name}",
        extra=extra,
    )


def from_claude_dir(
    path: str | Path,
    *,
    namepoint: str | None = None,
    skip: frozenset[str] | set[str] | None = None,
) -> Soul:
    """Convert a Claude Code memory directory into a knowledge :class:`Soul`.

    Reads ``*.md`` topic files with YAML frontmatter. Skips index files
    (``MEMORY.md``, etc.) and any topic whose ``metadata.type`` is not one of
    ``user`` | ``feedback`` | ``project`` | ``reference``.

    Parameters
    ----------
    path
        Directory containing Claude Code memory topic files.
    namepoint
        Soul address. Default: ``@claude-code:{directory name}``.
    skip
        Basenames to ignore (default: MEMORY.md, MEMORY-FULL.md, README.md).

    Returns
    -------
    Soul
        Profile ``knowledge``, facts from topics, index rebuilt from facts.
        Empty facts if the directory has no qualifying topics.
    """
    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(f"Claude memory directory not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Claude memory path is not a directory: {root}")

    skip_names = frozenset(skip) if skip is not None else DEFAULT_SKIP
    np = namepoint if namepoint is not None else f"@claude-code:{root.resolve().name}"

    facts: list[Fact] = []
    for md in sorted(root.glob("*.md")):
        if md.name in skip_names:
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        fm, body = _parse_frontmatter(text)
        if not fm:
            continue
        fact = _fact_from_topic(md, body=body, fm=fm)
        if fact is not None:
            facts.append(fact)

    # created / last_etched from fact timestamps when present
    stamps = [f.timestamp for f in facts if f.timestamp]
    created = min(stamps) if stamps else None
    last = max(stamps) if stamps else None

    soul = Soul(np, profile="knowledge", facts=facts, created=created)
    if last:
        soul.last_etched = last
    soul.rebuild_index()
    return soul
