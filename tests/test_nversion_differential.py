"""N-version differential — Opus merge  vs  Composer merge (Soul-Packet §8).

The payoff of the N-version build: two independent implementations of the
same frozen spec (MERGE.md + the encoding lock + the §8a gap-decisions) must produce
the SAME logical soul for every input. Disagreement = a bug in one of them.

Gate: SKIPS entirely until the second implementation sets
``composer_merge.IMPLEMENTED = True``, so the suite stays green while it is still
being written. Now flipped and green — this differential is what earned the
unqualified "CvRDT" label.

Three tiers:
  A. Composer's merge is internally a CvRDT   (5 laws, under Composer's oracle)
  B. Cross-impl agreement                     (Opus out == Composer out, by BOTH oracles)
  C. Concrete adversarial values              (oracle-independent literal expectations)
"""
from __future__ import annotations

import os
import sys

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ensure the sibling clean-room module is importable regardless of pytest mode
sys.path.insert(0, os.path.dirname(__file__))

from claude_fafm_sdk.merge import content_hash as opus_chash  # noqa: E402
from claude_fafm_sdk.merge import merge_souls as opus_merge  # noqa: E402
from claude_fafm_sdk.merge import souls_equal as opus_equal  # noqa: E402
from claude_fafm_sdk.soul import Fact, Soul  # noqa: E402

import composer_merge  # noqa: E402
from composer_merge import content_hash as comp_chash  # noqa: E402
from composer_merge import merge_souls as comp_merge  # noqa: E402
from composer_merge import souls_equal as comp_equal  # noqa: E402

# whole module is gated on the clean-room impl being ready
pytestmark = pytest.mark.skipif(
    not getattr(composer_merge, "IMPLEMENTED", False),
    reason="composer_merge.IMPLEMENTED is False — Composer differential not written yet",
)

NP = "@merge-test"  # one namepoint → every generated pair is mergeable

# ── strategies (IDENTICAL to test_wjttc_merge_crdt.py — same input space) ─────
_ids = st.sampled_from([None, "a", "b", "c"])
_texts = st.sampled_from(["alpha", "beta", " alpha ", "alpha\n", "café", "café"])
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
        st.sampled_from(["plain", 1, True]),
        st.fixed_dictionaries(
            {
                "v": st.sampled_from(["vv", 2]),
                "t": st.sampled_from(["", "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z"]),
            }
        ),
    ),
    max_size=2,
)


@st.composite
def _soul(draw) -> Soul:
    return Soul(
        NP,
        profile=draw(st.sampled_from(["voice", "knowledge"])),
        facts=draw(st.lists(_fact(), max_size=4)),
        preferences=draw(_opaque),
        custom=draw(_opaque),
    )


_S = _soul()
_SETTINGS = settings(max_examples=400, deadline=None)


# ── Tier A: Composer's merge is internally a CvRDT (its own oracle) ──────────


@_SETTINGS
@given(_S, _S)
def test_composer_commutative(a, b):
    assert comp_equal(comp_merge(a, b), comp_merge(b, a))


@_SETTINGS
@given(_S, _S, _S)
def test_composer_associative(a, b, c):
    left = comp_merge(comp_merge(a, b), c)
    right = comp_merge(a, comp_merge(b, c))
    assert comp_equal(left, right)


@_SETTINGS
@given(_S, _S)
def test_composer_idempotent(a, b):
    m = comp_merge(a, b)
    assert comp_equal(comp_merge(m, m), m)


@_SETTINGS
@given(_S, _S)
def test_composer_double_packet_noop(a, b):
    m = comp_merge(a, b)
    assert comp_equal(comp_merge(m, b), m)


@_SETTINGS
@given(_S, _S)
def test_composer_both_directions_converge(a, b):
    assert comp_equal(comp_merge(a, b), comp_merge(b, a))


# ── Tier B: cross-impl agreement — the differential (both oracles must agree) ─


@_SETTINGS
@given(_S, _S)
def test_cross_impl_agree(a, b):
    mo = opus_merge(a, b)
    mc = comp_merge(a, b)
    # checked by BOTH oracles so neither a permissive nor a strict oracle can hide
    # a merge divergence between the two independent implementations.
    assert opus_equal(mo, mc), "Opus oracle: Opus and Composer merge outputs differ"
    assert comp_equal(mo, mc), "Composer oracle: Opus and Composer merge outputs differ"


@_SETTINGS
@given(_S, _S, _S)
def test_cross_impl_agree_triple(a, b, c):
    mo = opus_merge(opus_merge(a, b), c)
    mc = comp_merge(comp_merge(a, b), c)
    assert opus_equal(mo, mc)
    assert comp_equal(mo, mc)


# ── Tier C: concrete adversarial values (oracle-independent) ─────────────────
# Literal expectations from the confirmed spec — do not rely on either souls_equal,
# so a wrong-but-permissive Composer oracle still can't pass these.


def _s(*facts, **kw):
    return Soul(NP, facts=list(facts), **kw)


def test_c_same_second_same_id_one_live_fact():
    a = _s(Fact(text="alpha", id="x", timestamp="2026-01-01T00:00:00Z"))
    b = _s(Fact(text="beta", id="x", timestamp="2026-01-01T00:00:00Z"))
    m = comp_merge(a, b)
    assert len([f for f in m.facts if f.id == "x"]) == 1
    assert comp_equal(comp_merge(a, b), comp_merge(b, a))


def test_c_idless_whitespace_variant_dedups():
    m = comp_merge(_s(Fact(text="alpha")), _s(Fact(text=" alpha ")))
    assert len(m.facts) == 1


def test_c_empty_timestamp_sorts_lowest():
    a = _s(Fact(text="t", id="x", timestamp=""))
    b = _s(Fact(text="t2", id="x", timestamp="2026-01-01T00:00:00Z"))
    assert comp_merge(a, b).get_fact("x").text == "t2"


def test_c_priority_ties_converge():
    a = _s(Fact(text="p", id="x", priority="high", timestamp="2026-01-01T00:00:00Z"))
    b = _s(Fact(text="q", id="x", priority="high", timestamp="2026-01-01T00:00:00Z"))
    assert comp_equal(comp_merge(a, b), comp_merge(b, a))


def test_c_tags_links_set_union():
    a = _s(Fact(text="f", id="x", tags=["a"], links=["L1"], timestamp="2026-01-01T00:00:00Z"))
    b = _s(Fact(text="f", id="x", tags=["b"], links=["L2"], timestamp="2026-01-01T00:00:00Z"))
    fx = comp_merge(a, b).get_fact("x")
    assert set(fx.tags) == {"a", "b"}
    assert set(fx.links) == {"L1", "L2"}


def test_c_fact_extra_per_key_lww_union():
    a = _s(Fact(text="f", id="x", timestamp="2026-01-01T00:00:00Z", source="s",
                type=None, priority="standard", extra={"k1": 1}))
    b = _s(Fact(text="f", id="x", timestamp="2026-01-02T00:00:00Z", extra={"k2": 2}))
    fx = comp_merge(a, b).get_fact("x")
    assert fx.extra.get("k1") == 1 and fx.extra.get("k2") == 2


def test_c_opaque_stamped_beats_unstamped():
    a = _s(preferences={"tone": "terse"})
    b = _s(preferences={"tone": {"v": "warm", "t": "2026-01-01T00:00:00Z"}})
    assert comp_merge(a, b).preferences["tone"]["v"] == "warm"


def test_c_opaque_two_concurrent_stamps_converge():
    a = _s(preferences={"tone": {"v": "A", "t": "2026-01-01T00:00:00Z"}})
    b = _s(preferences={"tone": {"v": "B", "t": "2026-01-01T00:00:00Z"}})
    assert comp_equal(comp_merge(a, b), comp_merge(b, a))


def test_c_different_namepoints_reject():
    with pytest.raises(ValueError):
        comp_merge(Soul("@one"), Soul("@two"))


# ── empty-timestamp pin regression: bareness (encoding-lock pin) ──────
# A fact bare in every field except timestamp="" must hash + sort identically
# across impls, else id-less order (=> sealed .fafb bytes) diverges. This is the
# corner the 400-example run under-sampled (Grok nit N4); pinned + biased below.


def test_c_empty_ts_bare_hashes_agree():
    # oracle-independent: the two impls' content_hash of a bare ts="" fact match
    f = Fact(text="alpha", timestamp="")
    assert opus_chash(f) == comp_chash(f)
    # and a ts=None bare fact hashes the same as the ts="" one (both absent)
    assert opus_chash(f) == opus_chash(Fact(text="alpha", timestamp=None))


def test_c_empty_ts_bare_order_agrees():
    # the exact reproducer from 13/14/15: order + both oracles must converge
    a = _s(Fact(text="alpha", timestamp=""))
    b = _s(Fact(text="beta"))
    mo, mc = opus_merge(a, b), comp_merge(a, b)
    assert [f.text for f in mo.facts] == [f.text for f in mc.facts]
    assert opus_equal(mo, mc) and comp_equal(mo, mc)


# generator that ALWAYS plants a bare ts="" fact next to >=1 id-less partner,
# so every example hits the corner (N4 coverage, not just random chance).
_bare_empty_ts = st.builds(
    lambda t: Fact(text=t, timestamp=""),
    st.sampled_from(["alpha", "beta", "café", "gamma", "zzz"]),
)
_idless_partner = st.builds(
    lambda t: Fact(text=t),
    st.sampled_from(["alpha", "beta", "zzz", "0", "~", "gamma", "delta"]),
)


@st.composite
def _soul_empty_ts_corner(draw) -> Soul:
    facts = [draw(_bare_empty_ts)] + draw(
        st.lists(_idless_partner, min_size=1, max_size=3)
    )
    return Soul(NP, facts=facts)


@_SETTINGS
@given(_soul_empty_ts_corner(), _soul_empty_ts_corner())
def test_cross_impl_agree_empty_ts_corner(a, b):
    mo, mc = opus_merge(a, b), comp_merge(a, b)
    assert opus_equal(mo, mc), "Opus oracle: empty-ts corner diverges"
    assert comp_equal(mo, mc), "Composer oracle: empty-ts corner diverges (order/index)"
