"""Clean-room merge — the second (differential) implementation of Soul-Packet merge.

⛔ N-VERSION RULE — the whole point of this file:
   Implement ONLY from the spec. DO **NOT** read ``claude_fafm_sdk/merge.py`` (the
   first implementation) while writing this one — reading it collapses the two
   versions into one and destroys the differential. You may read the shared DATA
   MODEL (``soul.py``) and the spec; nothing else about the merge.

READ (frozen spec):
   MERGE.md                  the canonical merge spec (§1–§8, incl. the §8a gap-decisions)
   claude_fafm_sdk/soul.py   data model only (imported below)

WRITE (from spec):
   merge_souls(a, b) -> Soul   the coordinator-free CvRDT join (MERGE.md §1–§7)
   souls_equal(x, y) -> bool   an independent logical equality (§8), derived from spec

The differential (``test_nversion_differential.py``) then checks this implementation
against the first for logical equality on every input.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any

# Data model ONLY — do not import from claude_fafm_sdk.merge.
from claude_fafm_sdk.soul import (  # noqa: F401
    Fact,
    PRIORITY_RANK,
    Soul,
    canonical_priority,
)

# Flip to True when merge_souls + souls_equal are complete. While False, the
# differential harness SKIPS (keeps the suite green until you're ready).
IMPLEMENTED = True


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip()


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def value_hash(val: Any) -> str:
    return hashlib.sha256(_canonical_json(val).encode("utf-8")).hexdigest()


def _is_bare(f: Fact) -> bool:
    return (
        f.id is None
        and f.type is None
        and not f.tags
        and not f.links
        and not f.timestamp
        and f.source is None
        and not f.extra
        and canonical_priority(f.priority) == "standard"
    )


def _fact_hash_obj(f: Fact, *, scalar_only: bool = False) -> dict[str, Any]:
    nt = normalize_text(f.text)
    if _is_bare(f) and not scalar_only:
        return {"text": nt}

    obj: dict[str, Any] = {"text": nt}
    if f.id is not None:
        obj["id"] = f.id
    if f.type is not None:
        obj["type"] = f.type
    obj["priority"] = canonical_priority(f.priority)
    if not scalar_only:
        if f.tags:
            obj["tags"] = sorted(set(f.tags))
        if f.links:
            obj["links"] = sorted(set(f.links))
    if f.timestamp:
        obj["timestamp"] = f.timestamp
    if f.source is not None:
        obj["source"] = f.source
    if not scalar_only and f.extra:
        obj["extra"] = f.extra
    return obj


def content_hash(f: Fact) -> str:
    return hashlib.sha256(_canonical_json(_fact_hash_obj(f)).encode("utf-8")).hexdigest()


def scalar_hash(f: Fact) -> str:
    return hashlib.sha256(_canonical_json(_fact_hash_obj(f, scalar_only=True)).encode("utf-8")).hexdigest()


def lww_key(f: Fact) -> tuple[Any, ...]:
    return (
        f.timestamp or "",
        PRIORITY_RANK.get(canonical_priority(f.priority), 1),
        f.id or "",
        content_hash(f),
    )


def scalar_lww_key(f: Fact) -> tuple[Any, ...]:
    return (
        f.timestamp or "",
        PRIORITY_RANK.get(canonical_priority(f.priority), 1),
        f.id or "",
        scalar_hash(f),
    )


def _merge_scalar_register(x: str, y: str) -> str:
    return x if x == y else max(x, y)


def _is_opaque_entry(val: Any) -> bool:
    return isinstance(val, dict) and set(val.keys()) == {"v", "t"}


def _unwrap_opaque(val: Any) -> tuple[Any, str]:
    if _is_opaque_entry(val):
        return val["v"], val["t"]
    return val, ""


def _merge_opaque_map(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in set(a) | set(b):
        if key in a and key not in b:
            v, t = _unwrap_opaque(a[key])
        elif key in b and key not in a:
            v, t = _unwrap_opaque(b[key])
        else:
            va, ta = _unwrap_opaque(a[key])
            vb, tb = _unwrap_opaque(b[key])
            if (ta, value_hash(va)) >= (tb, value_hash(vb)):
                v, t = va, ta
            else:
                v, t = vb, tb
        out[key] = {"v": v, "t": t}
    return out


def _merge_sessions(a: list[Any], b: list[Any]) -> list[Any]:
    by_hash: dict[str, Any] = {}
    for entry in list(a) + list(b):
        by_hash[value_hash(entry)] = entry
    return [by_hash[h] for h in sorted(by_hash)]


# ── tombstones (1.5, from MERGE.md §9) — independent of the SDK impl ──────────


def txt_hash(text: str) -> str:
    """id-less tombstone key: SHA-256 of normalize_text (§9.1). Reference copy."""
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def _join_tombstones(x: dict[tuple[str, str], str], y: dict[tuple[str, str], str]):
    """Max-register join over the union of keys (grow-only; latest delete wins)."""
    joined = dict(x)
    for key, when in y.items():
        if joined.get(key, "") < when:
            joined[key] = when
    return joined


def _tomb_key(f: Fact) -> tuple[str, str]:
    return ("id", f.id) if f.id is not None else ("txt", txt_hash(f.text))


def _suppressed_by(f: Fact, tombs: dict[tuple[str, str], str]) -> bool:
    """A tombstone kills a fact when deleted_at >= fact clock (delete-wins tie)."""
    when = tombs.get(_tomb_key(f))
    return when is not None and when >= (f.timestamp or "")


def _normalize_fact(f: Fact) -> Fact:
    return Fact(
        text=normalize_text(f.text),
        id=f.id,
        type=f.type,
        priority=canonical_priority(f.priority),
        tags=sorted(set(f.tags)),
        links=sorted(set(f.links)),
        timestamp=f.timestamp,
        source=f.source,
        extra=dict(f.extra),
    )


def _merge_id_facts(facts: list[Fact]) -> Fact:
    if len(facts) == 1:
        return _normalize_fact(facts[0])

    hi = max(facts, key=scalar_lww_key)
    # Rule T (§4a): tags/links/extra come ONLY from versions at the winning clock —
    # concurrent peers union, strictly-lower-clock versions contribute nothing (cross-clock
    # union is non-associative under retroactive tombstones). Group-at-once here.
    win_clock = hi.timestamp or ""
    peers = [f for f in facts if (f.timestamp or "") == win_clock]
    tags: set[str] = set()
    links: set[str] = set()
    extra: dict[str, Any] = {}
    for f in peers:
        tags |= set(f.tags)
        links |= set(f.links)
        for k, v in f.extra.items():
            if k not in extra or value_hash(v) >= value_hash(extra[k]):
                extra[k] = v
    return Fact(
        text=normalize_text(hi.text),
        id=hi.id,
        type=hi.type,
        priority=canonical_priority(hi.priority),
        tags=sorted(tags),
        links=sorted(links),
        timestamp=hi.timestamp,
        source=hi.source,
        extra=extra,
    )


def _merge_idless_facts(facts: list[Fact]) -> Fact:
    winner = max(facts, key=lww_key)
    return _normalize_fact(winner)


def _merge_facts(facts_a: list[Fact], facts_b: list[Fact],
                 tombs: dict[tuple[str, str], str] | None = None) -> list[Fact]:
    tombs = tombs or {}
    by_id: dict[str, list[Fact]] = {}
    idless: list[Fact] = []
    for f in facts_a + facts_b:
        # A version the graveyard outranks is dropped BEFORE grouping — a forgotten
        # low-clock write must not lend its tags/links to a surviving re-etch, or
        # associativity breaks (field-merge folds them in one order only). §9.2 R1'.
        if _suppressed_by(f, tombs):
            continue
        if f.id is not None:
            by_id.setdefault(f.id, []).append(f)
        else:
            idless.append(f)

    merged: list[Fact] = [_merge_id_facts(group) for group in by_id.values()]

    by_norm: dict[str, list[Fact]] = {}
    for f in idless:
        by_norm.setdefault(normalize_text(f.text), []).append(f)
    merged.extend(_merge_idless_facts(group) for group in by_norm.values())

    merged.sort(
        key=lambda f: (
            0 if f.id else 1,
            f.id or "",
            content_hash(f),
            normalize_text(f.text) or f.text or "",
        )
    )
    return merged


def _fact_logical_entry(f: Fact) -> tuple[Any, ...]:
    return (
        normalize_text(f.text),
        f.type,
        canonical_priority(f.priority),
        tuple(sorted(set(f.tags))),
        tuple(sorted(set(f.links))),
        f.timestamp or "",
        f.source,
        tuple(sorted((k, _canonical_json(v)) for k, v in f.extra.items())),
    )


def _opaque_logical(m: dict[str, Any]) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for k, val in m.items():
        v, t = _unwrap_opaque(val)
        out[k] = (t, _canonical_json(v))
    return out


def _observable_facts(soul: Soul) -> list[Fact]:
    """Facts a tombstone does NOT outrank — the emitted / equatable view (§9.2)."""
    return [f for f in soul.facts if not _suppressed_by(f, soul.tombstones)]


def logical_state(soul: Soul) -> dict[str, Any]:
    live = _observable_facts(soul)
    facts: dict[tuple[str, str], tuple[Any, ...]] = {}
    for f in live:
        key = ("id", f.id) if f.id is not None else ("txt", normalize_text(f.text))
        facts[key] = _fact_logical_entry(f)
    # index derived from the canonically-ordered observable facts (not the stored one),
    # so a live-but-suppressed fact equates the same whether or not merge has run.
    ordered = sorted(
        live,
        key=lambda f: (0 if f.id else 1, f.id or "", content_hash(f),
                       normalize_text(f.text) or f.text or ""),
    )
    return {
        "namepoint": soul.namepoint,
        "profile": soul.profile,
        "retention": soul.retention,
        "created": soul.created,
        "last_etched": soul.last_etched,
        "facts": facts,
        "preferences": _opaque_logical(soul.preferences),
        "custom": _opaque_logical(soul.custom),
        "extra": _opaque_logical(soul.extra),
        "memory_extra": _opaque_logical(soul.memory_extra),
        "sessions": frozenset(value_hash(e) for e in soul.sessions),
        "tombstones": frozenset((kind, k, when) for (kind, k), when in soul.tombstones.items()),
        "index": tuple(f"{f.id or '?'} — {f.text[:80]}" for f in ordered),
    }


def merge_souls(a: Soul, b: Soul) -> Soul:
    """CvRDT join of two souls (same namepoint). Implement from MERGE.md §1–§9."""
    if a.namepoint != b.namepoint:
        raise ValueError(
            f"cannot merge souls with different namepoints: {a.namepoint!r} vs {b.namepoint!r}"
        )

    # graveyard joins first; then facts join with forgotten VERSIONS pre-dropped
    # (§9.2 R1' — version-level, not emit-level, or associativity breaks).
    graveyard = _join_tombstones(a.tombstones, b.tombstones)
    surviving = _merge_facts(a.facts, b.facts, graveyard)

    merged = Soul(
        a.namepoint,
        profile=_merge_scalar_register(a.profile, b.profile),
        retention=_merge_scalar_register(a.retention, b.retention),
        created=min(a.created, b.created),
        facts=surviving,
        sessions=_merge_sessions(a.sessions, b.sessions),
        preferences=_merge_opaque_map(a.preferences, b.preferences),
        custom=_merge_opaque_map(a.custom, b.custom),
        extra=_merge_opaque_map(a.extra, b.extra),
        memory_extra=_merge_opaque_map(a.memory_extra, b.memory_extra),
        tombstones=graveyard,
    )
    merged.last_etched = max(a.last_etched or "", b.last_etched or "")
    merged.rebuild_index()
    return merged


def souls_equal(x: Soul, y: Soul) -> bool:
    """Logical (not byte) equality — §8 from spec."""
    return logical_state(x) == logical_state(y)
