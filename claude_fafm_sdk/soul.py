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

    @classmethod
    def load(cls, path: str | Path) -> Soul:
        """Load a ``.fafm`` soul from disk.

        Missing ``profile`` defaults to ``voice`` (schema / INTEROP §1.2).
        Loads ``index`` and ``memory.sessions|preferences|custom`` when present.
        """
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        if not isinstance(doc, dict):
            raise ValueError("soul is not a YAML mapping")
        memory = doc.get("memory") or {}
        if not isinstance(memory, dict):
            memory = {}
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
        )
        soul.last_etched = doc.get("last_etched", soul.created)
        return soul

    def to_doc(self) -> dict[str, Any]:
        """The ``.fafm`` v1.1 document this soul serializes to."""
        return {
            "version": "1.1",
            "profile": self.profile,
            "namepoint": self.namepoint,
            "created": self.created,
            "last_etched": self.last_etched,
            "retention": self.retention,
            "index": list(self._index),
            "memory": {
                "facts": [f.to_obj() for f in self._facts],
                "sessions": copy.deepcopy(self._sessions),
                "preferences": copy.deepcopy(self._preferences),
                "custom": copy.deepcopy(self._custom),
            },
        }

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
        """Deterministic recall: case-insensitive substring match on ``text``,
        tag intersection, type equality, priority floor — ranked by priority then
        recency. (Semantic/ranked recall is the full intel — see ``client.py``.)"""
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
        # Rank by priority, then recency. The insertion index breaks timestamp
        # ties (second-granularity stamps collide in a fast write loop) so the
        # most-recently-etched fact always wins — recency must be deterministic.
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
