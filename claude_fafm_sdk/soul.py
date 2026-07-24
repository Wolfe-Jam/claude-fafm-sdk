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
_KNOWN_MEMORY_KEYS = frozenset({"facts", "sessions", "preferences", "custom"})


def _utcnow() -> str:
    return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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

    @classmethod
    def load(cls, path: str | Path) -> Soul:
        """Load a ``.fafm`` soul from disk.

        Missing ``profile`` defaults to ``voice`` (schema / INTEROP §1.2).
        Loads ``index`` and ``memory.sessions|preferences|custom`` when present.
        Unknown top-level and memory keys are preserved (INTEROP §4 residual).
        """
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        if not isinstance(doc, dict):
            raise ValueError("soul is not a YAML mapping")
        memory = doc.get("memory") or {}
        if not isinstance(memory, dict):
            memory = {}
        doc_extra = {
            k: copy.deepcopy(v) for k, v in doc.items() if k not in _KNOWN_DOC_KEYS
        }
        memory_extra = {
            k: copy.deepcopy(v) for k, v in memory.items() if k not in _KNOWN_MEMORY_KEYS
        }
        soul = cls(
            namepoint=doc.get("namepoint", Path(path).stem),
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
        )
        soul.last_etched = doc.get("last_etched", soul.created)
        return soul

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
        i = self._by_id.get(id)
        if i is None:
            return False
        del self._facts[i]
        self._by_id = {f.id: j for j, f in enumerate(self._facts) if f.id is not None}
        return True
