"""WJTTC — Soul-Packet merge CvRDT property suite (MERGE.md §8).

Oracle-first: these encode the frozen commutative / associative / idempotent
laws + the encoding lock's adversarial cases.
Green ⇒ the merge is a CvRDT under the encoding lock. Label is now unqualified
"CvRDT" (dual-implementation verified — see MERGE.md).

Equality is LOGICAL (fact set by id-or-normalized-text, field values, derived
index) — never raw YAML bytes.
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from claude_fafm_sdk.merge import merge_souls, souls_equal
from claude_fafm_sdk.soul import Fact, Soul

NP = "@merge-test"  # one namepoint → every generated pair is mergeable

# ── small pools → dense collisions / ties (the interesting CRDT cases) ───────
_ids = st.sampled_from([None, "a", "b", "c"])
_texts = st.sampled_from(
    ["alpha", "beta", " alpha ", "alpha\n", "café", "café"]  # whitespace + NFC variants
)
_prios = st.sampled_from(
    ["ephemeral", "standard", "high", "critical", "low", "medium", "junk"]
)
_ts = st.sampled_from([None, "", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"])


@st.composite
def _fact(draw) -> Fact:
    return Fact(
        text=draw(_texts),
        id=draw(_ids),
        type=draw(st.sampled_from([None, "project", "feedback"])),
        priority=draw(_prios),
        tags=draw(st.lists(st.sampled_from(["x", "y", "z"]), max_size=3)),
        links=draw(st.lists(st.sampled_from(["L1", "L2"]), max_size=2)),
        timestamp=draw(_ts),
        source=draw(st.sampled_from([None, "s1"])),
        extra=draw(
            st.dictionaries(
                st.sampled_from(["k1", "k2"]),
                st.sampled_from([1, 2, "v", True]),
                max_size=2,
            )
        ),
    )


_opaque = st.dictionaries(
    st.sampled_from(["p1", "p2"]),
    st.one_of(
        st.sampled_from(["plain", 1, True]),  # legacy plain value
        st.fixed_dictionaries(  # already {v,t}
            {
                "v": st.sampled_from(["vv", 2]),
                "t": st.sampled_from(["", "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z"]),
            }
        ),
    ),
    max_size=2,
)

# residual join-semilattice fields (residual-field coverage): the oracle already
# compares these, but the generators never populated them — so sessions (G1
# G-Set), retention (G4 max-register), and memory_extra / soul-level extra
# (opaque LWW maps) went untested until now.
_retention = st.sampled_from(["forever", "30d", "session", "ephemeral"])
_sessions = st.lists(
    st.fixed_dictionaries(
        {"id": st.sampled_from(["s1", "s2"]), "n": st.sampled_from([1, 2])}
    ),
    max_size=3,
)


@st.composite
def _soul(draw) -> Soul:
    return Soul(
        NP,
        profile=draw(st.sampled_from(["voice", "knowledge"])),
        facts=draw(st.lists(_fact(), max_size=4)),
        retention=draw(_retention),
        sessions=draw(_sessions),
        preferences=draw(_opaque),
        custom=draw(_opaque),
        extra=draw(_opaque),
        memory_extra=draw(_opaque),
    )


_S = _soul()
_SETTINGS = settings(max_examples=400, deadline=None)


# ── the three laws ───────────────────────────────────────────────────────────


@_SETTINGS
@given(_S, _S)
def test_commutative(a, b):
    assert souls_equal(merge_souls(a, b), merge_souls(b, a))


@_SETTINGS
@given(_S, _S, _S)
def test_associative(a, b, c):
    left = merge_souls(merge_souls(a, b), c)
    right = merge_souls(a, merge_souls(b, c))
    assert souls_equal(left, right)


@_SETTINGS
@given(_S, _S)
def test_idempotent(a, b):
    # idempotence on a lattice element (a merge output), per CvRDT semantics
    m = merge_souls(a, b)
    assert souls_equal(merge_souls(m, m), m)


@_SETTINGS
@given(_S, _S)
def test_double_packet_noop(a, b):
    m = merge_souls(a, b)
    assert souls_equal(merge_souls(m, b), m)  # re-applying b changes nothing


@_SETTINGS
@given(_S, _S)
def test_both_directions_converge(a, b):
    assert souls_equal(merge_souls(a, b), merge_souls(b, a))


# ── explicit adversarial cases (the encoding lock's required set) ─────────────


def _s(*facts, **kw):
    return Soul(NP, facts=list(facts), **kw)


def test_same_second_same_id_different_text():
    # same id, same second, same priority → content_hash decides, deterministically
    a = _s(Fact(text="alpha", id="x", timestamp="2026-01-01T00:00:00Z"))
    b = _s(Fact(text="beta", id="x", timestamp="2026-01-01T00:00:00Z"))
    assert souls_equal(merge_souls(a, b), merge_souls(b, a))
    m = merge_souls(a, b)
    assert len([f for f in m.facts if f.id == "x"]) == 1  # one live fact per id


def test_idless_whitespace_variant_dedups():
    a = _s(Fact(text="alpha"))
    b = _s(Fact(text=" alpha "))  # normalizes equal → one G-Set slot
    m = merge_souls(a, b)
    assert len(m.facts) == 1


def test_empty_timestamp_sorts_lowest():
    a = _s(Fact(text="t", id="x", timestamp=""))
    b = _s(Fact(text="t2", id="x", timestamp="2026-01-01T00:00:00Z"))
    m = merge_souls(a, b)
    # the stamped one wins the scalar text
    assert m.get_fact("x").text == "t2"


def test_priority_ties_converge():
    a = _s(Fact(text="p", id="x", priority="high", timestamp="2026-01-01T00:00:00Z"))
    b = _s(Fact(text="q", id="x", priority="high", timestamp="2026-01-01T00:00:00Z"))
    assert souls_equal(merge_souls(a, b), merge_souls(b, a))


def test_tags_links_set_union():
    a = _s(Fact(text="f", id="x", tags=["a"], links=["L1"], timestamp="2026-01-01T00:00:00Z"))
    b = _s(Fact(text="f", id="x", tags=["b"], links=["L2"], timestamp="2026-01-01T00:00:00Z"))
    m = merge_souls(a, b)
    fx = m.get_fact("x")
    assert set(fx.tags) == {"a", "b"}
    assert set(fx.links) == {"L1", "L2"}


def test_fact_extra_per_key_lww_union():
    a = _s(Fact(text="f", id="x", timestamp="2026-01-01T00:00:00Z", source="s",
                type=None, priority="standard", extra={"k1": 1}))
    b = _s(Fact(text="f", id="x", timestamp="2026-01-02T00:00:00Z",
                extra={"k2": 2}))  # newer ts → wins scalar, extra keys union
    fx = merge_souls(a, b).get_fact("x")
    assert fx.extra.get("k1") == 1 and fx.extra.get("k2") == 2


def test_opaque_stamped_beats_unstamped():
    a = _s(preferences={"tone": "terse"})  # legacy → t=""
    b = _s(preferences={"tone": {"v": "warm", "t": "2026-01-01T00:00:00Z"}})
    m = merge_souls(a, b)
    assert m.preferences["tone"]["v"] == "warm"  # stamped wins


def test_opaque_two_concurrent_stamps_converge():
    a = _s(preferences={"tone": {"v": "A", "t": "2026-01-01T00:00:00Z"}})
    b = _s(preferences={"tone": {"v": "B", "t": "2026-01-01T00:00:00Z"}})  # same t → hash(v) tiebreak
    assert souls_equal(merge_souls(a, b), merge_souls(b, a))


def test_different_namepoints_reject():
    import pytest

    with pytest.raises(ValueError):
        merge_souls(Soul("@one"), Soul("@two"))
