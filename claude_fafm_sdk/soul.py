"""Soul — the local model of a ``.fafm`` knowledge soul (open, offline).

Reads/writes ``application/vnd.fafm+yaml`` v1.1 and provides the basic memory
operations every consumer needs: ``etch`` (write a fact, dedup by id) and
``recall`` (deterministic filter + priority/recency rank). This is the OPEN
baseline — it works offline with no account. Semantic/ranked recall and
LLM smart-merge are the *full intel*, served via a namepoint (see ``client.py``).

Format-compatible with `fafm-engine` and `grok-faf-voice` — one format, never a fork.

Interop contract: see ``INTEROP.md`` (v1.0).
"""

from __future__ import annotations

import copy
import datetime
import hashlib
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Canonical priority vocabulary (.fafm spec §6.1), low → high.
PRIORITY_ORDER = ("ephemeral", "standard", "high", "critical")
PRIORITY_RANK = {p: i for i, p in enumerate(PRIORITY_ORDER)}
_LEGACY_PRIORITY = {"low": "ephemeral", "medium": "standard"}

# Top-level keys Soul models explicitly (INTEROP §1). Everything else is residual.
_KNOWN_DOC_KEYS = frozenset(
    {
        "version",
        "profile",
        "namepoint",
        "created",
        "last_etched",
        "retention",
        "index",
        "memory",
    }
)
# Keys under memory that Soul models; other memory keys are residual.
# ``tombstones`` (1.5) is first-class — NOT residual: residual treatment would join
# it as an opaque LWW map (wrong lattice) and never suppress a fact (freeze §3.2).
# tombstones (1.5) · policies / policy_auto (1.6) — first-class, never residual LWW
_KNOWN_MEMORY_KEYS = frozenset(
    {"facts", "sessions", "preferences", "custom", "tombstones", "policies", "policy_auto"}
)


def _utcnow() -> str:
    return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_text(text: str) -> str:
    """NFC + strip — the pinned text normalization (MERGE.md §5.1). The data-model
    copy: it keys id-less facts and the ``txt_hash`` of a tombstone. Each merge
    implementation keeps its OWN copy (N-version); this one serves the Soul API."""
    return unicodedata.normalize("NFC", text).strip()


def txt_hash(text: str) -> str:
    """Tombstone key for an id-less fact (freeze §2.1): lowercase-hex SHA-256 of the
    UTF-8 bytes of ``normalize_text(text)`` — the SAME keying as G-Set membership,
    NOT the full ``content_hash`` (which folds in tags/priority/etc). We hash the
    text so a forgotten fact's content does not linger in the tombstone."""
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def _tombstones_from_wire(raw: Any) -> dict[tuple[str, str], str]:
    """Parse ``memory.tombstones`` (a list of ``{id|txt_hash, deleted_at}``) into the
    LWW map. Lenient (matches the residual-preserve load philosophy): an entry with
    no non-empty ``deleted_at`` or neither key is skipped, never a load crash. Duplicate
    keys collapse to ``max(deleted_at)`` (the same grow-only join merge uses)."""
    out: dict[tuple[str, str], str] = {}
    if not isinstance(raw, list):
        return out
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        deleted_at = entry.get("deleted_at")
        if not deleted_at or not isinstance(deleted_at, str):
            continue  # deleted_at required non-empty (freeze §2.3) — skip a bad row
        if "id" in entry and entry["id"] is not None:
            key: tuple[str, str] = ("id", str(entry["id"]))
        elif "txt_hash" in entry and entry["txt_hash"] is not None:
            key = ("txt", str(entry["txt_hash"]))
        else:
            continue
        if key not in out or deleted_at > out[key]:
            out[key] = deleted_at
    return out


def _tombstones_to_wire(tombstones: dict[tuple[str, str], str]) -> list[dict[str, str]]:
    """Serialize the tombstone map to the ``memory.tombstones`` list, in canonical
    order ``(kind, key, deleted_at)`` so the human save and the sealed bytes agree
    (freeze §3.3 — list order is not covered by YAML ``sort_keys``)."""
    rows: list[dict[str, str]] = []
    for (kind, key), deleted_at in sorted(tombstones.items()):
        field_name = "id" if kind == "id" else "txt_hash"
        rows.append({field_name: key, "deleted_at": deleted_at})
    return rows


def canonical_priority(p: str | None) -> str:
    """Map any input (incl. legacy vocab) to a canonical priority."""
    if p is None:
        return "standard"
    return _LEGACY_PRIORITY.get(p, p if p in PRIORITY_RANK else "standard")


@dataclass
class Fact:
    """A single memory unit. ``text`` is the only required field; everything
    else is optional, per the spec — so any consumer can read a soul."""

    text: str
    id: str | None = None
    type: str | None = None
    priority: str = "standard"
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    timestamp: str | None = None
    source: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Empty-string timestamp is ABSENT (Soul-Packet encoding-lock pin). Normalize at
        # the data model so every construction — load, add, merge emit — agrees and
        # the empty-ts content_hash/order divergence can't arise at the source. Both
        # merge impls inherit this because they build Facts through this dataclass.
        if self.timestamp == "":
            self.timestamp = None

    @classmethod
    def from_obj(cls, obj: Any) -> Fact:
        """Build a Fact from a bare string or a ``{text, ...}`` mapping."""
        if isinstance(obj, str):
            return cls(text=obj)
        if not isinstance(obj, dict) or "text" not in obj:
            raise ValueError(f"fact must be a string or a mapping with 'text': {obj!r}")
        known = {"text", "id", "type", "priority", "tags", "links", "timestamp", "source"}
        return cls(
            text=obj["text"],
            id=obj.get("id"),
            type=obj.get("type"),
            priority=canonical_priority(obj.get("priority")),
            tags=list(obj.get("tags") or []),
            links=list(obj.get("links") or []),
            timestamp=obj.get("timestamp"),
            source=obj.get("source"),
            extra={k: v for k, v in obj.items() if k not in known},
        )

    def to_obj(self) -> Any:
        """Serialize back to a `.fafm` fact. Bare string when it has no metadata."""
        bare = (
            self.id is None and self.type is None and not self.tags and not self.links
            and self.timestamp is None and self.source is None and not self.extra
            and self.priority == "standard"
        )
        if bare:
            return self.text
        out: dict[str, Any] = {"text": self.text}
        if self.id is not None:
            out["id"] = self.id
        if self.type is not None:
            out["type"] = self.type
        out["priority"] = self.priority
        if self.tags:
            out["tags"] = self.tags
        if self.links:
            out["links"] = self.links
        if self.timestamp is not None:
            out["timestamp"] = self.timestamp
        if self.source is not None:
            out["source"] = self.source
        out.update(self.extra)
        return out


class Soul:
    """A loaded ``.fafm`` knowledge soul + its basic (offline) memory ops."""

    def __init__(
        self,
        namepoint: str,
        *,
        profile: str = "knowledge",
        facts: list[Fact] | None = None,
        retention: str = "forever",
        created: str | None = None,
        index: list[str] | None = None,
        sessions: list[Any] | None = None,
        preferences: dict[str, Any] | None = None,
        custom: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
        memory_extra: dict[str, Any] | None = None,
        tombstones: dict[tuple[str, str], str] | None = None,
        policies: list[Any] | None = None,
        policy_auto: bool = False,
    ) -> None:
        self.namepoint = namepoint
        self.profile = profile
        self.retention = retention
        self.created = created or _utcnow()
        self.last_etched = self.created
        self._facts: list[Fact] = list(facts or [])
        self._by_id: dict[str, int] = {
            f.id: i for i, f in enumerate(self._facts) if f.id is not None
        }
        # Tombstones (1.5) — LWW max-register map: key → deleted_at (RFC3339-Z).
        # key is ("id", <id>) for an id-fact, ("txt", <txt_hash>) for an id-less one.
        # Grow-only graveyard; merge joins by max(deleted_at) and suppresses on emit.
        self._tombstones: dict[tuple[str, str], str] = dict(tombstones or {})
        # Policies (1.6) — first-class LWW-Element-Map by rule id; emit forget only.
        # Imported lazily in accessors to avoid circular import at module load.
        from .policy import Policy, policies_from_wire

        if policies is None:
            self._policies: list[Any] = []
        elif policies and isinstance(policies[0], Policy):
            self._policies = list(policies)
        else:
            self._policies = policies_from_wire(policies)
        self._policy_auto = bool(policy_auto)
        # Document fidelity (INTEROP §1.4 / §5) — soul-owned copies.
        self._index: list[str] = list(index or [])
        self._sessions: list[Any] = list(sessions or [])
        self._preferences: dict[str, Any] = dict(preferences or {})
        self._custom: dict[str, Any] = dict(custom or {})
        # Residual unknowns (INTEROP §4) — preserved on load→save.
        self._extra: dict[str, Any] = dict(extra or {})
        self._memory_extra: dict[str, Any] = dict(memory_extra or {})

    @property
    def facts(self) -> list[Fact]:
        return self._facts

    @property
    def index(self) -> list[str]:
        """Top-level one-line index (knowledge profile). Empty list if none."""
        return self._index

    @property
    def sessions(self) -> list[Any]:
        return self._sessions

    @property
    def preferences(self) -> dict[str, Any]:
        return self._preferences

    @property
    def custom(self) -> dict[str, Any]:
        return self._custom

    @property
    def extra(self) -> dict[str, Any]:
        """Top-level document keys not in the known model (INTEROP §4)."""
        return self._extra

    @property
    def memory_extra(self) -> dict[str, Any]:
        """``memory`` keys beyond facts/sessions/preferences/custom."""
        return self._memory_extra

    @property
    def tombstones(self) -> dict[tuple[str, str], str]:
        """The forget graveyard (1.5): ``(kind, key) -> deleted_at``. ``kind`` is
        ``"id"`` or ``"txt"``. Grow-only; ``merge_souls`` joins by ``max(deleted_at)``
        and suppresses a fact whose tombstone outranks its clock (freeze §2)."""
        return self._tombstones

    @property
    def policies(self) -> list[Any]:
        """Forget policies (1.6) — list of :class:`policy.Policy`. First-class wire."""
        return self._policies

    @policies.setter
    def policies(self, value: list[Any]) -> None:
        from .policy import Policy, policies_from_wire

        if value and isinstance(value[0], Policy):
            self._policies = list(value)
        else:
            self._policies = policies_from_wire(value)

    @property
    def policy_auto(self) -> bool:
        """When True, callers MAY auto-apply policies; default False (INTEROP §13)."""
        return self._policy_auto

    @policy_auto.setter
    def policy_auto(self, value: bool) -> None:
        self._policy_auto = bool(value)

    @classmethod
    def from_doc(cls, doc: Any, *, namepoint_fallback: str | None = None) -> Soul:
        """Build a Soul from a parsed ``.fafm`` mapping — the shared deserialize
        path used by :meth:`load` (from disk) and the packet ``from_packet``.

        Missing ``profile`` defaults to ``voice`` (schema / INTEROP §1.2).
        Loads ``index`` and ``memory.sessions|preferences|custom`` when present.
        Unknown top-level and memory keys are preserved (INTEROP §4 residual).
        ``namepoint`` must be present in ``doc`` unless a fallback is given.
        """
        if not isinstance(doc, dict):
            raise TypeError("soul is not a YAML mapping")
        memory = doc.get("memory") or {}
        if not isinstance(memory, dict):
            memory = {}
        doc_extra = {
            k: copy.deepcopy(v) for k, v in doc.items() if k not in _KNOWN_DOC_KEYS
        }
        memory_extra = {
            k: copy.deepcopy(v) for k, v in memory.items() if k not in _KNOWN_MEMORY_KEYS
        }
        namepoint = doc.get("namepoint") or namepoint_fallback
        if not namepoint:
            raise ValueError("soul doc missing 'namepoint'")
        raw_auto = memory.get("policy_auto", False)
        policy_auto = bool(raw_auto) if raw_auto is not None else False
        soul = cls(
            namepoint=namepoint,
            profile=doc.get("profile", "voice"),
            facts=[Fact.from_obj(f) for f in (memory.get("facts") or [])],
            retention=doc.get("retention", "forever"),
            created=doc.get("created"),
            index=list(doc.get("index") or []),
            sessions=copy.deepcopy(list(memory.get("sessions") or [])),
            preferences=copy.deepcopy(dict(memory.get("preferences") or {})),
            custom=copy.deepcopy(dict(memory.get("custom") or {})),
            extra=doc_extra,
            memory_extra=memory_extra,
            tombstones=_tombstones_from_wire(memory.get("tombstones")),
            policies=memory.get("policies"),
            policy_auto=policy_auto,
        )
        soul.last_etched = doc.get("last_etched", soul.created)
        return soul

    @classmethod
    def load(cls, path: str | Path) -> Soul:
        """Load a ``.fafm`` soul from disk (see :meth:`from_doc`)."""
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.from_doc(doc, namepoint_fallback=Path(path).stem)

    def to_doc(self) -> dict[str, Any]:
        """The ``.fafm`` v1.1 document this soul serializes to.

        Known keys first, then residual top-level extras (INTEROP §4).
        Residual keys never overwrite modeled keys.
        """
        memory: dict[str, Any] = {
            "facts": [f.to_obj() for f in self._facts],
            "sessions": copy.deepcopy(self._sessions),
            "preferences": copy.deepcopy(self._preferences),
            "custom": copy.deepcopy(self._custom),
        }
        # Emit tombstones only when non-empty — a soul that never forgot is byte-identical
        # to a 1.4 doc (keeps every ≤1.4 seal/wire golden valid; freeze §3.3 + §5 claim).
        if self._tombstones:
            memory["tombstones"] = _tombstones_to_wire(self._tombstones)
        # Policies (1.6): omit when empty — seal identity for no-policy souls (INTEROP §13.2).
        if self._policies:
            from .policy import policies_to_wire

            memory["policies"] = policies_to_wire(self._policies)
        if self._policy_auto:
            memory["policy_auto"] = True
        for k, v in self._memory_extra.items():
            if k not in _KNOWN_MEMORY_KEYS:
                memory[k] = copy.deepcopy(v)
        doc: dict[str, Any] = {
            "version": "1.1",
            "profile": self.profile,
            "namepoint": self.namepoint,
            "created": self.created,
            "last_etched": self.last_etched,
            "retention": self.retention,
            "index": list(self._index),
            "memory": memory,
        }
        for k, v in self._extra.items():
            if k not in _KNOWN_DOC_KEYS:
                doc[k] = copy.deepcopy(v)
        return doc

    def to_yaml(self) -> str:
        """Serialize to the ``.fafm`` (vnd.fafm+yaml) document text."""
        return yaml.safe_dump(self.to_doc(), sort_keys=False, allow_unicode=True, width=100)

    def rebuild_index(self, width: int = 80) -> list[str]:
        """Regenerate the top-level one-line index from current facts.

        Formula matches ``fafm-engine`` / INTEROP §5:
        ``f"{id or '?'} — {text[:width]}"``.
        """
        self._index = [f"{f.id or '?'} — {f.text[:width]}" for f in self._facts]
        return self._index

    def save(self, path: str | Path, *, reindex: bool = True) -> Path:
        """Write the soul to disk as ``.fafm`` (vnd.fafm+yaml).

        When ``reindex`` is True (default), rebuilds ``index`` from facts before
        write so the index stays true after etch/delete. Pass ``reindex=False``
        to preserve a loaded or hand-tuned index.
        """
        if reindex:
            self.rebuild_index()
        p = Path(path)
        p.write_text(self.to_yaml(), encoding="utf-8")
        return p

    # -- name parity with grok-faf-voice FAFMemory.from_file / to_file ------

    @classmethod
    def from_file(cls, path: str | Path) -> Soul:
        """Alias of :meth:`load` — read a ``.fafm`` from disk."""
        return cls.load(path)

    def to_file(self, path: str | Path, *, reindex: bool = True) -> Path:
        """Alias of :meth:`save` — write this soul as ``.fafm``."""
        return self.save(path, reindex=reindex)

    def add(self, fact: Fact) -> Fact:
        """Insert or update a ``Fact`` by id, preserving its fields (incl. its
        original timestamp) — the merge primitive. ``etch`` builds on this."""
        if fact.id is not None and fact.id in self._by_id:
            self._facts[self._by_id[fact.id]] = fact
        else:
            self._facts.append(fact)
            if fact.id is not None:
                self._by_id[fact.id] = len(self._facts) - 1
        if fact.timestamp and fact.timestamp > (self.last_etched or ""):
            self.last_etched = fact.timestamp
        return fact

    def etch(
        self,
        text: str,
        *,
        id: str | None = None,
        type: str | None = None,
        priority: str = "standard",
        tags: list[str] | None = None,
        links: list[str] | None = None,
        source: str | None = None,
    ) -> Fact:
        """Write a fact. If ``id`` matches an existing fact it's updated in place
        (O(1) dedup); otherwise appended."""
        return self.add(
            Fact(
                text=text,
                id=id,
                type=type,
                priority=canonical_priority(priority),
                tags=list(tags or []),
                links=list(links or []),
                timestamp=_utcnow(),
                source=source,
            )
        )

    def recall(
        self,
        query: str | None = None,
        *,
        tags: list[str] | None = None,
        type: str | None = None,
        min_priority: str = "ephemeral",
        limit: int | None = None,
    ) -> list[Fact]:
        """Deterministic recall: filter then rank (INTEROP §6).

        Filters (all must pass when set): case-insensitive substring on
        ``text``, tag set intersection, type equality, priority floor.

        Rank (descending): ``(priority_rank, timestamp, insertion_index)``.
        Insertion index is the fact's current position in the list — not
        "time of last etch". Same-second ties: higher index wins (typically
        last **appended** fact). An id-collision update keeps its slot, so it
        does not jump ahead of a later append with the same timestamp.
        """
        floor = PRIORITY_RANK.get(canonical_priority(min_priority), 0)
        q = (query or "").lower()
        want_tags = set(tags or [])
        indexed = [
            (i, f) for i, f in enumerate(self._facts)
            if (not q or q in f.text.lower())
            and (not want_tags or want_tags.intersection(f.tags))
            and (type is None or f.type == type)
            and PRIORITY_RANK.get(f.priority, 1) >= floor
        ]
        # Stable, deterministic: priority → timestamp → list position.
        indexed.sort(
            key=lambda t: (PRIORITY_RANK.get(t[1].priority, 1), t[1].timestamp or "", t[0]),
            reverse=True,
        )
        results = [f for _, f in indexed]
        return results[:limit] if limit is not None else results

    def get_fact(self, id: str) -> Fact | None:
        i = self._by_id.get(id)
        return self._facts[i] if i is not None else None

    def delete_fact(self, id: str) -> bool:
        """Single-replica removal of a live fact by id (no tombstone). Used inside
        :meth:`forget`; for a deletion that CONVERGES across replicas, use ``forget``."""
        i = self._by_id.get(id)
        if i is None:
            return False
        del self._facts[i]
        self._by_id = {f.id: j for j, f in enumerate(self._facts) if f.id is not None}
        return True

    def _tombstone(self, key: tuple[str, str], deleted_at: str) -> None:
        """Upsert a tombstone at ``key`` to ``max(existing, deleted_at)`` — the
        grow-only, deepen-only join (freeze §2.1). ``deleted_at`` must be non-empty."""
        if not deleted_at:
            raise ValueError("tombstone deleted_at must be non-empty (RFC3339-Z)")
        cur = self._tombstones.get(key)
        if cur is None or deleted_at > cur:
            self._tombstones[key] = deleted_at

    def forget(self, id: str, *, deleted_at: str | None = None) -> bool:
        """Forget an id-fact so the deletion **converges** (1.5). Removes the live
        fact if present AND records a tombstone; a later merge will not resurrect it
        from a peer that still holds it. The tombstone is always written (freeze §3.4)
        — forgetting an id you no longer hold still suppresses it on merge. Returns
        True iff a live fact was removed here."""
        removed = self.delete_fact(id)
        self._tombstone(("id", id), deleted_at or _utcnow())
        return removed

    def forget_text(self, text: str, *, deleted_at: str | None = None) -> bool:
        """Forget an **id-less** fact by its text (1.5). Matches live id-less facts by
        ``normalize_text`` (the G-Set key), removes them, and records a ``txt_hash``
        tombstone. Always writes the tombstone (freeze §3.4). Returns True iff a live
        id-less fact was removed here."""
        want = normalize_text(text)
        kept = [f for f in self._facts if not (f.id is None and normalize_text(f.text) == want)]
        removed = len(kept) != len(self._facts)
        if removed:
            self._facts = kept
            self._by_id = {f.id: j for j, f in enumerate(self._facts) if f.id is not None}
        self._tombstone(("txt", txt_hash(text)), deleted_at or _utcnow())
        return removed

    def propose_policies(self, *, at: str) -> list[Any]:
        """Dry-run: facts matching enabled policies (1.6). No write."""
        from .policy import propose_policies

        return propose_policies(self, at=at)

    def apply_policies(self, *, at: str) -> list[Any]:
        """Apply enabled policies with clock pin ``at`` (1.6). Writes tombstones.

        Does **not** check ``policy_auto`` or CLI confirm — caller enforces authority.
        """
        from .policy import apply_policies

        return apply_policies(self, at=at)


    def set_policy(
        self,
        id: str,
        when: dict[str, Any],
        *,
        action: str = "forget",
        enabled: bool = True,
        updated_at: str | None = None,
    ) -> Any:
        """Upsert a policy rule by id (local; merge joins by LWW on updated_at)."""
        from .policy import Policy

        if action != "forget":
            raise ValueError("1.6 policies support action=forget only")
        p = Policy(
            id=id,
            when=dict(when),
            action="forget",
            enabled=enabled,
            updated_at=updated_at or _utcnow(),
        )
        rest = [x for x in self._policies if x.id != id]
        rest.append(p)
        rest.sort(key=lambda x: x.id)
        self._policies = rest
        return p
