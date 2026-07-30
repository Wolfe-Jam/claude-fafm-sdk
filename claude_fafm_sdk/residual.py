"""Residual-risk surfacing (1.7) — what the lattice cannot erase.

Path-bounded: only explicit paths / globs the caller provides (plus optional
default relative patterns under a root). Not DFIR. Not RTBF. Not secure erase.

Honesty: finds copies of soul/packet bytes that may still hold forgotten content.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class ResidualHit:
    path: str
    kind: str  # soul | packet | other
    size: int
    sha256_prefix: str  # first 16 hex — enough to compare without dumping secrets


@dataclass
class ResidualReport:
    """Copies found under scanned paths — lattice cannot erase these."""

    hits: list[ResidualHit] = field(default_factory=list)
    scanned_paths: list[str] = field(default_factory=list)
    note: str = (
        "Residual copies only — not a wipe, not legal RTBF, not forensic erase. "
        "Tombstones converge on merge; disk images and prior packets may still hold bytes."
    )

    @property
    def count(self) -> int:
        return len(self.hits)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hits": [
                {
                    "path": h.path,
                    "kind": h.kind,
                    "size": h.size,
                    "sha256_prefix": h.sha256_prefix,
                }
                for h in self.hits
            ],
            "scanned_paths": list(self.scanned_paths),
            "count": self.count,
            "note": self.note,
        }


_PACKET_SUFFIXES = {".fafmp"}
_SOUL_SUFFIXES = {".fafm", ".yaml", ".yml"}


def _kind_for(path: Path) -> str:
    suf = path.suffix.lower()
    if suf in _PACKET_SUFFIXES:
        return "packet"
    if suf in _SOUL_SUFFIXES:
        return "soul"
    return "other"


def _sha16(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _iter_files(paths: Iterable[str | Path], *, patterns: tuple[str, ...]) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        p = Path(raw).expanduser()
        if not p.exists():
            continue
        if p.is_file():
            rp = p.resolve()
            if rp not in seen:
                seen.add(rp)
                found.append(rp)
            continue
        if p.is_dir():
            for pat in patterns:
                for hit in sorted(p.rglob(pat)):
                    if hit.is_file():
                        rp = hit.resolve()
                        if rp not in seen:
                            seen.add(rp)
                            found.append(rp)
    return found


def risk_scan(
    paths: list[str | Path],
    *,
    patterns: tuple[str, ...] = ("*.fafm", "*.fafmp"),
    max_files: int = 500,
) -> ResidualReport:
    """Scan **only** the given paths for soul/packet copies.

    - Files: included if they match a known suffix or any path given explicitly.
    - Dirs: rglob ``patterns`` only (default ``*.fafm`` / ``*.fafmp``).
    - Cap ``max_files`` so this never becomes unbounded DFIR.
    """
    if not paths:
        raise ValueError(
            "risk_scan requires explicit paths (path-bounded; no implicit home crawl)"
        )
    scanned = [str(Path(p).expanduser()) for p in paths]
    files = _iter_files(paths, patterns=patterns)
    hits: list[ResidualHit] = []
    for f in files[:max_files]:
        # explicit files always; rglob already filtered by pattern
        kind = _kind_for(f)
        if kind == "other" and f.suffix.lower() not in _PACKET_SUFFIXES | _SOUL_SUFFIXES:
            # still report explicit non-matching files so caller sees what was named
            kind = "other"
        try:
            size = f.stat().st_size
            prefix = _sha16(f)
        except OSError:
            continue
        hits.append(
            ResidualHit(
                path=str(f),
                kind=kind,
                size=size,
                sha256_prefix=prefix,
            )
        )
    return ResidualReport(hits=hits, scanned_paths=scanned)
