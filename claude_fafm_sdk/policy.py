"""Policy → tombstone (1.6) — INTEROP.md §13.

Policies are first-class configuration that *emit* fact forget via the existing
``Soul.forget`` / ``forget_text`` surfaces. They never suppress at merge time;
only ``memory.tombstones`` do (MERGE.md §9).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from .soul import PRIORITY_RANK, Fact, Soul, canonical_priority, normalize_text, txt_hash

Action = Literal["forget"]

_DURATION_RE = re.compile(
    r"^\s*(?:(?P<days>\d+)\s*d)?\s*(?:(?P<hours>\d+)\s*h)?\s*(?:(?P<minutes>\d+)\s*m)?\s*(?:(?P<seconds>\d+)\s*s)?\s*$",
    re.IGNORECASE,
)


def parse_duration(spec: str) -> timedelta:
    """Parse a compact duration like ``7d``, ``12h``, ``30m``, ``1d12h``."""
    s = (spec or "").strip()
    if not s:
        raise ValueError("empty duration")
    # bare integer → days
    if s.isdigit():
        return timedelta(days=int(s))
    m = _DURATION_RE.match(s)
    if not m or not any(m.group(g) for g in ("days", "hours", "minutes", "seconds")):
        raise ValueError(f"invalid duration: {spec!r} (use e.g. 7d, 12h, 30m)")
    return timedelta(
        days=int(m.group("days") or 0),
        hours=int(m.group("hours") or 0),
        minutes=int(m.group("minutes") or 0),
        seconds=int(m.group("seconds") or 0),
    )


def _parse_rfc3339(ts: str) -> datetime:
    t = (ts or "").strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    return datetime.fromisoformat(t).astimezone(timezone.utc)


@dataclass
class Policy:
    """One forget policy rule (INTEROP §13.2)."""

    id: str
    when: dict[str, Any]
    action: Action = "forget"
    enabled: bool = True
    updated_at: str = ""

    def to_wire(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "when": dict(self.when),
            "action": self.action,
            "enabled": self.enabled,
        }
        if self.updated_at:
            out["updated_at"] = self.updated_at
        return out

    @classmethod
    def from_wire(cls, raw: Any) -> Policy | None:
        if not isinstance(raw, dict):
            return None
        pid = raw.get("id")
        when = raw.get("when")
        if not isinstance(pid, str) or not pid.strip():
            return None
        if not isinstance(when, dict) or not when:
            return None
        action = raw.get("action", "forget")
        if action != "forget":
            return None  # 1.6: only forget
        enabled = raw.get("enabled", True)
        if not isinstance(enabled, bool):
            enabled = bool(enabled)
        updated = raw.get("updated_at") or ""
        if updated is not None and not isinstance(updated, str):
            updated = str(updated)
        return cls(
            id=pid.strip(),
            when=dict(when),
            action="forget",
            enabled=enabled,
            updated_at=updated or "",
        )


def policies_from_wire(raw: Any) -> list[Policy]:
    if not isinstance(raw, list):
        return []
    out: list[Policy] = []
    seen: set[str] = set()
    for entry in raw:
        p = Policy.from_wire(entry)
        if p is None or p.id in seen:
            continue
        seen.add(p.id)
        out.append(p)
    out.sort(key=lambda p: p.id)
    return out


def policies_to_wire(policies: list[Policy]) -> list[dict[str, Any]]:
    return [p.to_wire() for p in sorted(policies, key=lambda p: p.id)]


def policy_body_hash(p: Policy) -> str:
    """Canonical content hash for LWW tie-break (INTEROP §13.4)."""
    body = {
        "id": p.id,
        "when": p.when,
        "action": p.action,
        "enabled": p.enabled,
    }
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def merge_policies(a: list[Policy], b: list[Policy]) -> list[Policy]:
    """LWW-Element-Map by rule id (INTEROP §13.4)."""
    by_id: dict[str, Policy] = {}
    for p in list(a) + list(b):
        cur = by_id.get(p.id)
        if cur is None:
            by_id[p.id] = p
            continue
        # greater updated_at wins; empty sorts lowest
        ta, tb = cur.updated_at or "", p.updated_at or ""
        if tb > ta:
            by_id[p.id] = p
        elif tb < ta:
            continue
        elif policy_body_hash(p) > policy_body_hash(cur):
            by_id[p.id] = p
    return sorted(by_id.values(), key=lambda p: p.id)


def _matches_when(fact: Fact, when: dict[str, Any], *, at: str) -> bool:
    """True if fact matches all keys present in ``when`` (AND)."""
    if "id" in when:
        want = when["id"]
        if fact.id != want:
            return False
    if "text" in when:
        if normalize_text(fact.text) != normalize_text(str(when["text"])):
            return False
    if "tag" in when:
        tags = when["tag"]
        if isinstance(tags, str):
            tags = [tags]
        if not isinstance(tags, list):
            return False
        fact_tags = set(fact.tags)
        if not fact_tags.intersection(str(t) for t in tags):
            return False
    if "priority_lte" in when:
        floor = canonical_priority(str(when["priority_lte"]))
        if PRIORITY_RANK[canonical_priority(fact.priority)] > PRIORITY_RANK[floor]:
            return False
    if "max_age" in when:
        if not fact.timestamp:
            return True  # empty clock sorts lowest — treat as older than any real at
        try:
            age = _parse_rfc3339(at) - _parse_rfc3339(fact.timestamp)
            limit = parse_duration(str(when["max_age"]))
        except (ValueError, TypeError):
            return False
        if age < limit:
            return False
    return True


@dataclass
class ProposeHit:
    """One fact a policy would forget."""

    policy_id: str
    fact: Fact
    kind: Literal["id", "txt"]
    key: str  # id or txt_hash


def propose_policies(soul: Soul, *, at: str, policies: list[Policy] | None = None) -> list[ProposeHit]:
    """List facts matching enabled policies — no write (INTEROP §13.5)."""
    rules = policies if policies is not None else list(soul.policies)
    hits: list[ProposeHit] = []
    seen: set[tuple[str, str]] = set()  # (kind, key) once
    for p in rules:
        if not p.enabled or p.action != "forget":
            continue
        for f in soul.facts:
            if not _matches_when(f, p.when, at=at):
                continue
            if f.id is not None:
                kind: Literal["id", "txt"] = "id"
                key = f.id
            else:
                kind = "txt"
                key = txt_hash(f.text)
            sk = (kind, key)
            if sk in seen:
                continue
            # already forgotten under current graveyard?
            if soul.tombstones.get(sk) and (soul.tombstones[sk] or "") >= (f.timestamp or ""):
                # still report if live fact present — propose shows live matches
                pass
            seen.add(sk)
            hits.append(ProposeHit(policy_id=p.id, fact=f, kind=kind, key=key))
    return hits


def apply_policies(
    soul: Soul,
    *,
    at: str,
    policies: list[Policy] | None = None,
) -> list[ProposeHit]:
    """Apply enabled policies: write fact tombstones with ``deleted_at=at``.

    Library API **requires** ``at`` (RFC3339-Z). Does not check ``policy_auto``
    or CLI ``--yes`` — callers enforce authority.
    """
    if not at or not str(at).strip():
        raise ValueError("apply_policies requires non-empty at= (RFC3339-Z clock pin)")
    at = str(at).strip()
    hits = propose_policies(soul, at=at, policies=policies)
    for h in hits:
        if h.kind == "id":
            soul.forget(h.key, deleted_at=at)
        else:
            soul.forget_text(h.fact.text, deleted_at=at)
    return hits
