"""Visible tombstone debt (1.7) — never auto-drops the lattice.

Eligibility is **mark-only**: older than ``purge_eligible_after`` relative to ``at``
does not delete tombstones. GC/epoch is a later cut (2.0). See TESTING.md · plan §1.7.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .policy import parse_duration
from .soul import Soul, _tombstones_to_wire


def _parse_rfc3339(ts: str) -> datetime:
    t = (ts or "").strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    return datetime.fromisoformat(t).astimezone(timezone.utc)


@dataclass(frozen=True)
class DebtReport:
    """Snapshot of grow-only graveyard cost (falsifiable)."""

    count: int
    bytes: int
    oldest: str | None
    newest: str | None
    purge_eligible_count: int
    purge_eligible_after: str | None  # duration spec used, if any
    at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "bytes": self.bytes,
            "oldest": self.oldest,
            "newest": self.newest,
            "purge_eligible_count": self.purge_eligible_count,
            "purge_eligible_after": self.purge_eligible_after,
            "at": self.at,
            "note": "eligible marks only — never auto-drops tombstones (1.7)",
        }


def debt(
    soul: Soul,
    *,
    at: str | None = None,
    purge_eligible_after: str | None = None,
) -> DebtReport:
    """Measure tombstone debt. Does **not** mutate the soul.

    ``purge_eligible_after`` (e.g. ``30d``): count tombstones with
    ``deleted_at <= at - duration``. Never removes them.
    """
    stones = soul.tombstones
    count = len(stones)
    wire = _tombstones_to_wire(stones) if stones else []
    # Approximate on-disk debt: canonical list form as UTF-8 YAML-ish JSON length
    import json

    blob = json.dumps(wire, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    nbytes = len(blob.encode("utf-8")) if wire else 0

    times = [da for da in stones.values() if da]
    oldest = min(times) if times else None
    newest = max(times) if times else None

    eligible = 0
    if purge_eligible_after and at and times:
        limit = parse_duration(purge_eligible_after)
        at_dt = _parse_rfc3339(at)
        cutoff = at_dt - limit
        for da in times:
            try:
                if _parse_rfc3339(da) <= cutoff:
                    eligible += 1
            except (ValueError, TypeError):
                continue

    return DebtReport(
        count=count,
        bytes=nbytes,
        oldest=oldest,
        newest=newest,
        purge_eligible_count=eligible,
        purge_eligible_after=purge_eligible_after,
        at=at,
    )
