"""Soul-Packet merge — state-based CvRDT (v1.1 / Soul-Packet track).

Frozen spec: ``MERGE.md`` (authored against a frozen encoding lock, verified by
an independent oracle).

This is NOT part of v1.0 INTEROP. ``Soul.add`` (single-replica overwrite) is
unchanged; ``merge_souls`` is the coordinator-free, order-independent join:
commutative · associative · idempotent (a product of join-semilattices).

Label (2026-07-24): the dual-implementation differential is green and independently
re-verified ⇒ unqualified **state-based CvRDT** (two independent implementations,
encoding lock v1.1 + the §8a gap-decisions + empty-timestamp pin). Grow/update-only —
no delete convergence in v1.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any

from .soul import Fact, PRIORITY_RANK, Soul, canonical_priority

# ── encodings (PINNED — byte-identical across implementations) ──────────────


def normalize_text(text: str) -> str:
    """NFC + strip. No casefold, no internal-whitespace collapse (MERGE.md §5.1)."""
    return unicodedata.normalize("NFC", text).strip()


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _is_bare(f: Fact) -> bool:
    return (
        f.id is None
        and f.type is None
        and not f.tags
        and not f.links
        and not f.timestamp  # empty-string ts is ABSENT (encoding-lock pin) — match the `if f.timestamp` hash guard
        and f.source is None
        and not f.extra
        and canonical_priority(f.priority) == "standard"
    )


def content_hash(f: Fact) -> str:
    """SHA-256 lowercase hex over the fact's canonical JSON (MERGE.md §5.2)."""
    ntext = normalize_text(f.text)
    if _is_bare(f):
        obj: dict[str, Any] = {"text": ntext}
    else:
        obj = {"text": ntext, "priority": canonical_priority(f.priority)}
        if f.id is not None:
            obj["id"] = f.id
        if f.type is not None:
            obj["type"] = f.type
        if f.tags:
            obj["tags"] = sorted(set(f.tags))  # set semantics — dedup + sort (invariant to dupes)
        if f.links:
            obj["links"] = sorted(set(f.links))
        if f.timestamp:
            obj["timestamp"] = f.timestamp
        if f.source is not None:
            obj["source"] = f.source
        if f.extra:
            obj["extra"] = f.extra
    return hashlib.sha256(_canonical_json(obj).encode("utf-8")).hexdigest()


def _value_hash(v: Any) -> str:
    return hashlib.sha256(_canonical_json(v).encode("utf-8")).hexdigest()


def lww_key(f: Fact) -> tuple[str, int, str, str]:
    """(timestamp, priority_rank, id, content_hash); greater wins; empty ts lowest.

    Full-fact key: used for the id-less G-Set winner and the sort order.
    """
    return (
        f.timestamp or "",
        PRIORITY_RANK.get(canonical_priority(f.priority), 1),
        f.id or "",
        content_hash(f),
    )


def _scalar_hash(f: Fact) -> str:
    """SHA-256 over ONLY the scalar fields (text/id/type/priority/timestamp/source).

    Excludes the union'd fields (tags/links/extra) so the scalar-LWW winner is
    STABLE under folding — otherwise unioning tags changes the key mid-merge and
    breaks associativity. (Implementation-correctness detail; associativity test
    is the guard.)
    """
    obj: dict[str, Any] = {
        "text": normalize_text(f.text),
        "priority": canonical_priority(f.priority),
    }
    if f.id is not None:
        obj["id"] = f.id
    if f.type is not None:
        obj["type"] = f.type
    if f.timestamp:
        obj["timestamp"] = f.timestamp
    if f.source is not None:
        obj["source"] = f.source
    return hashlib.sha256(_canonical_json(obj).encode("utf-8")).hexdigest()


def _scalar_lww_key(f: Fact) -> tuple[str, int, str, str]:
    """Scalar-only LWW key — stable under tag/link/extra union (for same-id merge)."""
    return (
        f.timestamp or "",
        PRIORITY_RANK.get(canonical_priority(f.priority), 1),
        f.id or "",
        _scalar_hash(f),
    )


def _canonical_sort_key(f: Fact) -> tuple[int, str, str, str]:
    """Post-merge deterministic order (MERGE.md §5.4): has_id True first."""
    return (0 if f.id else 1, f.id or "", content_hash(f), normalize_text(f.text) or f.text or "")


# ── field-level fact merge (same id) — MERGE.md §4a ─────────────────────────


def _canon_fact(f: Fact) -> Fact:
    """Deterministic emit form: normalized text, sorted tags/links, canonical priority.

    Text is normalized on merge input (MERGE.md §5.1 "normalize once") so
    whitespace/NFC variants store identically → merge is order-independent.
    """
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


def _merge_fact_extra(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Per-key LWW for Fact.extra — union of keys; shared key resolved by
    greater value-hash (order-independent — Fact.extra has no per-key clock).
    """
    out: dict[str, Any] = {}
    for k in set(a) | set(b):
        if k in a and k in b:
            out[k] = a[k] if _value_hash(a[k]) >= _value_hash(b[k]) else b[k]
        else:
            out[k] = a[k] if k in a else b[k]
    return out


def _merge_same_id(x: Fact, y: Fact) -> Fact:
    # scalar winner via scalar-only key → stable under the union'd fields.
    # (Scalar ties ⇒ identical scalar fields, so hi/lo order is harmless for scalars.)
    hi = x if _scalar_lww_key(x) >= _scalar_lww_key(y) else y
    return Fact(
        text=normalize_text(hi.text),
        id=hi.id,
        type=hi.type,
        priority=canonical_priority(hi.priority),
        tags=sorted(set(x.tags) | set(y.tags)),  # set-union, emitted sorted
        links=sorted(set(x.links) | set(y.links)),
        timestamp=hi.timestamp,
        source=hi.source,
        extra=_merge_fact_extra(x.extra, y.extra),  # per-key, order-independent
    )


# ── opaque LWW-per-key maps — MERGE.md §5.3 ─────────────────────────────────


def _entry(value: Any) -> dict[str, Any]:
    """Wrap a possibly-legacy opaque value into {v, t} form."""
    if isinstance(value, dict) and set(value.keys()) == {"v", "t"}:
        return {"v": value["v"], "t": value.get("t") or ""}
    return {"v": value, "t": ""}


def _merge_opaque(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in set(a) | set(b):
        cands = []
        if key in a:
            cands.append(_entry(a[key]))
        if key in b:
            cands.append(_entry(b[key]))
        win = max(cands, key=lambda e: (e["t"], _value_hash(e["v"])))
        out[key] = {"v": win["v"], "t": win["t"]}
    return out


def _merge_sessions(a: list[Any], b: list[Any]) -> list[Any]:
    """sessions is a LIST → G-Set union, dedup by canonical hash (implementer gap G1)."""
    seen: dict[str, Any] = {}
    for entry in list(a) + list(b):
        seen[_value_hash(entry)] = entry
    return [seen[h] for h in sorted(seen)]


def _det_scalar(x: str, y: str) -> str:
    """Deterministic, commutative resolution for unspecified soul-level scalars."""
    return x if x == y else max(x, y)


# ── the merge ───────────────────────────────────────────────────────────────


def merge_souls(a: Soul, b: Soul) -> Soul:
    """Coordinator-free CvRDT merge of two souls (same namepoint). See ``MERGE.md``."""
    if a.namepoint != b.namepoint:
        raise ValueError(
            f"cannot merge different namepoints: {a.namepoint!r} vs {b.namepoint!r}"
        )

    # facts: LWW-Element-Map (by id, field-level) + G-Set (id-less, by normalized text)
    by_id: dict[str, Fact] = {}
    idless: dict[str, Fact] = {}
    for f in list(a.facts) + list(b.facts):
        if f.id is not None:
            by_id[f.id] = _merge_same_id(by_id[f.id], f) if f.id in by_id else _canon_fact(f)
        else:
            k = normalize_text(f.text)
            if k not in idless or lww_key(f) > lww_key(idless[k]):
                idless[k] = _canon_fact(f)

    facts = list(by_id.values()) + list(idless.values())
    facts.sort(key=_canonical_sort_key)

    merged = Soul(
        a.namepoint,
        profile=_det_scalar(a.profile, b.profile),
        facts=facts,
        retention=_det_scalar(a.retention, b.retention),
        created=min(a.created, b.created),
        sessions=_merge_sessions(a.sessions, b.sessions),
        preferences=_merge_opaque(a.preferences, b.preferences),
        custom=_merge_opaque(a.custom, b.custom),
        extra=_merge_opaque(a.extra, b.extra),
        memory_extra=_merge_opaque(a.memory_extra, b.memory_extra),
    )
    merged.last_etched = max(a.last_etched, b.last_etched)
    merged.rebuild_index()
    return merged


# ── logical equality (the property-test oracle) — MERGE.md §8 ────────────────


def logical_state(soul: Soul) -> dict[str, Any]:
    """Canonical, order-independent view for logical equality.

    Facts by (id | normalized-text); tags/links as sets; extra canonicalized;
    opaque maps normalized to {v,t}; index DERIVED canonically (not as stored).
    """
    facts: dict[tuple[str, str], tuple] = {}
    for f in soul.facts:
        key = ("id", f.id) if f.id is not None else ("txt", normalize_text(f.text))
        facts[key] = (
            normalize_text(f.text),
            f.type,
            canonical_priority(f.priority),
            tuple(sorted(set(f.tags))),
            tuple(sorted(set(f.links))),
            f.timestamp or "",
            f.source,
            tuple(sorted((k, _canonical_json(v)) for k, v in f.extra.items())),
        )

    def norm_map(m: dict[str, Any]) -> dict[str, tuple[str, str]]:
        return {k: (e["t"], _canonical_json(e["v"])) for k, e in ((k, _entry(v)) for k, v in m.items())}

    # derived-canonical index (from canonically sorted facts), not the stored one
    derived_index = tuple(
        f"{f.id or '?'} — {f.text[:80]}"
        for f in sorted(soul.facts, key=_canonical_sort_key)
    )

    return {
        "namepoint": soul.namepoint,
        "profile": soul.profile,
        "retention": soul.retention,
        "created": soul.created,  # merge join = min; in the oracle so dual-impl cannot drift
        "last_etched": soul.last_etched,
        "facts": facts,
        "preferences": norm_map(soul.preferences),
        "custom": norm_map(soul.custom),
        "extra": norm_map(soul.extra),
        "memory_extra": norm_map(soul.memory_extra),
        "sessions": frozenset(_value_hash(s) for s in soul.sessions),
        "index": derived_index,
    }


def souls_equal(x: Soul, y: Soul) -> bool:
    """Logical equality (not raw bytes) — the equality used by the property suite."""
    return logical_state(x) == logical_state(y)
