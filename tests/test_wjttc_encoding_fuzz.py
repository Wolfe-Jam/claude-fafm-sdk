"""Encoding-lock fuzz — the invariants the whole CvRDT rests on.

The merge is only a CvRDT if the pinned encodings hold under any input: text
normalization is idempotent + NFC-stable, content_hash is deterministic and
matches the bareness rule, and the opaque {v,t} wrapper is idempotent. These
fuzz the primitives directly so a regression surfaces here (loud, minimal) rather
than as a mysterious merge divergence.
"""
from __future__ import annotations

import unicodedata

from hypothesis import given, settings
from hypothesis import strategies as st

from claude_fafm_sdk.merge import (
    _entry,
    _is_bare,
    _value_hash,
    content_hash,
    normalize_text,
)
from claude_fafm_sdk.soul import Fact

_SET = settings(max_examples=300, deadline=None)

# nasty text fragments: whitespace, combining marks, NFC/NFD pairs (é, Å built
# both ways), ligatures, ideographic space, controls, emoji. Joined into strings
# (st.text(alphabet=...) requires length-1 elements, so we compose instead).
_FRAGS = [
    "a",
    " ",
    "\n",
    "\t",
    "\r\n",
    "　",  # ideographic space
    "\x00",  # control
    "  x  ",
    "北",  # 北
    "\U0001f3ce",  # 🏎
    "ﬁ",  # ﬁ ligature
    "café",  # café, NFD (e + combining acute)
    "café",  # café, NFC (é precomposed)
    "Å",  # Å, NFD (A + combining ring)
    "Å",  # Å, NFC (precomposed)
]
_frag = st.sampled_from(_FRAGS)
_text = st.builds("".join, st.lists(_frag, max_size=6))

_json_val = st.recursive(
    st.one_of(st.none(), st.booleans(), st.integers(-5, 5), st.text(max_size=4)),
    lambda c: st.lists(c, max_size=3) | st.dictionaries(st.text(max_size=3), c, max_size=3),
    max_leaves=6,
)


# ── normalize_text ───────────────────────────────────────────────────────────
@_SET
@given(_text)
def test_normalize_text_idempotent(t):
    once = normalize_text(t)
    assert normalize_text(once) == once


@_SET
@given(_text)
def test_normalize_text_is_nfc_and_stripped(t):
    n = normalize_text(t)
    assert n == unicodedata.normalize("NFC", n)  # already NFC
    assert n == n.strip()  # already stripped


@_SET
@given(_text)
def test_normalize_text_nfc_equivalents_collapse(t):
    # NFC and NFD spellings of the same text normalize identically — the property
    # that makes composed "café" == decomposed "café" merge to one G-Set slot.
    nfc = normalize_text(unicodedata.normalize("NFC", t))
    nfd = normalize_text(unicodedata.normalize("NFD", t))
    assert nfc == nfd


# ── content_hash ─────────────────────────────────────────────────────────────
@st.composite
def _fact(draw) -> Fact:
    return Fact(
        text=draw(_text),
        id=draw(st.one_of(st.none(), st.sampled_from(["x", "y"]))),
        type=draw(st.one_of(st.none(), st.just("t"))),
        priority=draw(st.sampled_from(["ephemeral", "standard", "high", "critical", "junk"])),
        tags=draw(st.lists(st.sampled_from(["a", "b"]), max_size=3)),
        links=draw(st.lists(st.sampled_from(["L"]), max_size=2)),
        timestamp=draw(st.sampled_from([None, "", "2026-01-01T00:00:00Z"])),
        source=draw(st.one_of(st.none(), st.just("s"))),
        extra=draw(st.dictionaries(st.sampled_from(["k"]), st.integers(0, 2), max_size=1)),
    )


@_SET
@given(_fact())
def test_content_hash_deterministic(f):
    assert content_hash(f) == content_hash(f)


@_SET
@given(_fact())
def test_content_hash_invariant_to_tag_order_and_dupes(f):
    g = Fact(
        text=f.text, id=f.id, type=f.type, priority=f.priority,
        tags=list(reversed(f.tags)) + f.tags,  # reordered + duplicated
        links=list(reversed(f.links)) + f.links,
        timestamp=f.timestamp, source=f.source, extra=dict(f.extra),
    )
    assert content_hash(f) == content_hash(g)  # set semantics (G5)


@_SET
@given(_fact())
def test_content_hash_bare_fact_matches_bare(f):
    # a bare fact hashes {"text"} only; if f is bare it must hash identically to
    # a fresh bare fact of the same text (bareness ⇒ text-only object).
    if _is_bare(f):
        assert content_hash(f) == content_hash(Fact(text=f.text))


@_SET
@given(_text)
def test_empty_and_none_ts_are_bare_and_hash_consistent(t):
    # ts="" and ts=None are indistinguishable for bareness AND hash (the
    # empty-ts pin — the footgun the differential caught).
    f_empty = Fact(text=t, timestamp="")
    f_none = Fact(text=t, timestamp=None)
    assert _is_bare(f_empty) == _is_bare(f_none)
    assert content_hash(f_empty) == content_hash(f_none)


# ── opaque {v,t} wrapper ─────────────────────────────────────────────────────
@_SET
@given(_json_val)
def test_entry_idempotent(v):
    e = _entry(v)
    assert set(e) == {"v", "t"}
    assert _entry(e) == e  # wrapping an already-{v,t} value is a no-op


@_SET
@given(_json_val)
def test_value_hash_deterministic(v):
    assert _value_hash(v) == _value_hash(v)
