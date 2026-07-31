"""Epoch compact — MERGE.md §11.4–§11.5 (Compactable 2.0).

``compact_epoch`` pays tombstone debt in a new lineage (epoch+1).
Cross-epoch merge remains refuse (E1). This module does not implement watermark GC.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from .merge import _is_suppressed, _soul_epoch
from .soul import Fact, Soul


@dataclass(frozen=True)
class CompactionReceipt:
    """MERGE §11.5 — audit of one epoch compact."""

    from_epoch: int
    to_epoch: int
    at: str
    tombstones_before: int
    facts_before: int
    facts_after: int
    actor: str | None = None
    archive_ref: str | None = None

    def to_wire(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "from_epoch": int(self.from_epoch),
            "to_epoch": int(self.to_epoch),
            "at": self.at,
            "tombstones_before": int(self.tombstones_before),
            "facts_before": int(self.facts_before),
            "facts_after": int(self.facts_after),
        }
        if self.actor:
            out["actor"] = self.actor
        if self.archive_ref:
            out["archive_ref"] = self.archive_ref
        return out

    @classmethod
    def from_wire(cls, raw: Any) -> CompactionReceipt | None:
        if not isinstance(raw, dict):
            return None
        try:
            fe = int(raw["from_epoch"])
            te = int(raw["to_epoch"])
            at = str(raw["at"])
            tb = int(raw["tombstones_before"])
            fb = int(raw["facts_before"])
            fa = int(raw["facts_after"])
        except (KeyError, TypeError, ValueError):
            return None
        if not at:
            return None
        actor = raw.get("actor")
        archive_ref = raw.get("archive_ref")
        return cls(
            from_epoch=fe,
            to_epoch=te,
            at=at,
            tombstones_before=tb,
            facts_before=fb,
            facts_after=fa,
            actor=str(actor) if actor else None,
            archive_ref=str(archive_ref) if archive_ref else None,
        )


def receipts_from_wire(raw: Any) -> list[CompactionReceipt]:
    if not isinstance(raw, list):
        return []
    out: list[CompactionReceipt] = []
    for row in raw:
        r = CompactionReceipt.from_wire(row)
        if r is not None:
            out.append(r)
    return out


def receipts_to_wire(receipts: list[CompactionReceipt]) -> list[dict[str, Any]]:
    return [r.to_wire() for r in receipts]


def _receipt_id(r: CompactionReceipt) -> str:
    blob = json.dumps(r.to_wire(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    import hashlib

    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def merge_receipts(
    a: list[CompactionReceipt], b: list[CompactionReceipt]
) -> list[CompactionReceipt]:
    """Grow-only append-union by receipt content hash (MERGE §11.5)."""
    by: dict[str, CompactionReceipt] = {}
    for r in list(a) + list(b):
        by[_receipt_id(r)] = r
    # stable order: by (from_epoch, to_epoch, at, id)
    return sorted(
        by.values(),
        key=lambda r: (r.from_epoch, r.to_epoch, r.at, _receipt_id(r)),
    )


def _observable_facts(soul: Soul) -> list[Fact]:
    """Facts after tombstone suppression — same as emit / logical_state (§9.3)."""
    return [f for f in soul.facts if not _is_suppressed(f, soul.tombstones)]


def compact_epoch(
    soul: Soul,
    *,
    at: str,
    actor: str | None = None,
    archive_ref: str | None = None,
) -> tuple[Soul, CompactionReceipt]:
    """MERGE §11.4 E3 — new soul at epoch+1, observable facts only, empty tombstones.

    Library does **not** enforce archive on disk; callers (CLI) must archive first.
    ``at`` is required (clock pin). Receipt is returned and appended on the new soul.
    """
    if not at or not str(at).strip():
        raise ValueError("compact_epoch requires non-empty at= (RFC3339-Z clock pin)")
    at = str(at).strip()
    e = _soul_epoch(soul)
    obs = _observable_facts(soul)
    # deep-copy facts so caller soul is not mutated
    facts = [
        Fact(
            text=f.text,
            id=f.id,
            type=f.type,
            priority=f.priority,
            tags=list(f.tags),
            links=list(f.links),
            timestamp=f.timestamp,
            source=f.source,
            extra=copy.deepcopy(f.extra),
        )
        for f in obs
    ]
    prior_receipts = list(getattr(soul, "compaction_receipts", []) or [])
    receipt = CompactionReceipt(
        from_epoch=e,
        to_epoch=e + 1,
        at=at,
        tombstones_before=len(soul.tombstones),
        facts_before=len(soul.facts),
        facts_after=len(facts),
        actor=actor,
        archive_ref=archive_ref,
    )
    new = Soul(
        soul.namepoint,
        profile=soul.profile,
        facts=facts,
        retention=soul.retention,
        created=soul.created,
        index=[],
        sessions=copy.deepcopy(list(soul.sessions)),
        preferences=copy.deepcopy(dict(soul.preferences)),
        custom=copy.deepcopy(dict(soul.custom)),
        extra=copy.deepcopy(dict(soul.extra)),
        memory_extra=copy.deepcopy(dict(soul.memory_extra)),
        tombstones={},  # debt paid in this lineage
        policies=list(soul.policies),
        policy_auto=bool(soul.policy_auto),
        epoch=e + 1,
        compaction_receipts=prior_receipts + [receipt],
    )
    new.last_etched = max(soul.last_etched or "", at)
    new.rebuild_index()
    return new, receipt


def migrate_epoch(
    source: Soul,
    target_epoch: int,
    *,
    mode: str = "refuse",
    at: str | None = None,
    actor: str | None = None,
) -> Soul:
    """MERGE §11.3 E2 — explicit only; never called from merge_souls.

    ``refuse`` (default): raise EpochMismatch-style error if epochs differ intent.
    ``project-live``: new soul at target_epoch from observable facts (no lagging merge).
    """
    te = int(target_epoch)
    if te < 0:
        raise ValueError("target_epoch must be >= 0")
    se = _soul_epoch(source)
    if mode == "refuse":
        from .merge import EpochMismatch

        if se != te:
            raise EpochMismatch(se, te)
        return source
    if mode != "project-live":
        raise ValueError(f"unknown migrate mode: {mode!r} (use refuse|project-live)")
    # project-live: observable only, empty tombstones, set epoch (not +1 compact semantics)
    pin = (at or "").strip() or (source.last_etched or source.created)
    obs = _observable_facts(source)
    facts = [
        Fact(
            text=f.text,
            id=f.id,
            type=f.type,
            priority=f.priority,
            tags=list(f.tags),
            links=list(f.links),
            timestamp=f.timestamp,
            source=f.source,
            extra=copy.deepcopy(f.extra),
        )
        for f in obs
    ]
    new = Soul(
        source.namepoint,
        profile=source.profile,
        facts=facts,
        retention=source.retention,
        created=source.created,
        sessions=copy.deepcopy(list(source.sessions)),
        preferences=copy.deepcopy(dict(source.preferences)),
        custom=copy.deepcopy(dict(source.custom)),
        extra=copy.deepcopy(dict(source.extra)),
        memory_extra=copy.deepcopy(dict(source.memory_extra)),
        tombstones={},
        policies=list(source.policies),
        policy_auto=bool(source.policy_auto),
        epoch=te,
        compaction_receipts=list(getattr(source, "compaction_receipts", []) or []),
    )
    new.last_etched = max(source.last_etched or "", pin)
    new.rebuild_index()
    return new
