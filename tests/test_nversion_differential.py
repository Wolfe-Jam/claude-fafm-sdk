"""N-version differential — SDK merge  vs  reference merge (Soul-Packet §8).

The payoff of the N-version build: two independent implementations of the
same frozen spec (MERGE.md + the encoding lock + the §8a gap-decisions) must produce
the SAME logical soul for every input. Disagreement = a bug in one of them.

Gate: SKIPS entirely until the second implementation sets
``reference_merge.IMPLEMENTED = True``, so the suite stays green while it is still
being written. Now flipped and green — this differential is what earned the
unqualified "CvRDT" label.

Three tiers:
  A. the reference merge is internally a CvRDT   (5 laws, under the reference oracle)
  B. Cross-impl agreement                     (SDK out == reference out, by BOTH oracles)
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

from claude_fafm_sdk.merge import content_hash as sdk_chash  # noqa: E402
from claude_fafm_sdk.merge import merge_souls as sdk_merge  # noqa: E402
from claude_fafm_sdk.merge import souls_equal as sdk_equal  # noqa: E402
from claude_fafm_sdk.soul import Fact, Soul  # noqa: E402

import reference_merge  # noqa: E402
from reference_merge import content_hash as ref_chash  # noqa: E402
from reference_merge import merge_souls as ref_merge  # noqa: E402
from reference_merge import souls_equal as ref_equal  # noqa: E402

# whole module is gated on the clean-room impl being ready
pytestmark = pytest.mark.skipif(
    not getattr(reference_merge, "IMPLEMENTED", False),
    reason="reference_merge.IMPLEMENTED is False — reference differential not written yet",
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

# residual join-semilattice fields (residual-field coverage) — same extension as the
# WJTTC suite so the differential exercises sessions (G1), retention (G4), and
# memory_extra / soul-level extra (opaque maps) across BOTH implementations.
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


# ── Tier A: the reference merge is internally a CvRDT (its own oracle) ──────────


@_SETTINGS
@given(_S, _S)
def test_reference_commutative(a, b):
    assert ref_equal(ref_merge(a, b), ref_merge(b, a))


@_SETTINGS
@given(_S, _S, _S)
def test_reference_associative(a, b, c):
    left = ref_merge(ref_merge(a, b), c)
    right = ref_merge(a, ref_merge(b, c))
    assert ref_equal(left, right)


@_SETTINGS
@given(_S, _S)
def test_reference_idempotent(a, b):
    m = ref_merge(a, b)
    assert ref_equal(ref_merge(m, m), m)


@_SETTINGS
@given(_S, _S)
def test_reference_double_packet_noop(a, b):
    m = ref_merge(a, b)
    assert ref_equal(ref_merge(m, b), m)


@_SETTINGS
@given(_S, _S)
def test_reference_both_directions_converge(a, b):
    assert ref_equal(ref_merge(a, b), ref_merge(b, a))


# ── Tier B: cross-impl agreement — the differential (both oracles must agree) ─


@_SETTINGS
@given(_S, _S)
def test_cross_impl_agree(a, b):
    mo = sdk_merge(a, b)
    mc = ref_merge(a, b)
    # checked by BOTH oracles so neither a permissive nor a strict oracle can hide
    # a merge divergence between the two independent implementations.
    assert sdk_equal(mo, mc), "SDK oracle: SDK and reference merge outputs differ"
    assert ref_equal(mo, mc), "reference oracle: SDK and reference merge outputs differ"


@_SETTINGS
@given(_S, _S, _S)
def test_cross_impl_agree_triple(a, b, c):
    mo = sdk_merge(sdk_merge(a, b), c)
    mc = ref_merge(ref_merge(a, b), c)
    assert sdk_equal(mo, mc)
    assert ref_equal(mo, mc)


# ── Tier C: concrete adversarial values (oracle-independent) ─────────────────
# Literal expectations from the confirmed spec — do not rely on either souls_equal,
# so a wrong-but-permissive reference oracle still can't pass these.


def _s(*facts, **kw):
    return Soul(NP, facts=list(facts), **kw)


def test_c_same_second_same_id_one_live_fact():
    a = _s(Fact(text="alpha", id="x", timestamp="2026-01-01T00:00:00Z"))
    b = _s(Fact(text="beta", id="x", timestamp="2026-01-01T00:00:00Z"))
    m = ref_merge(a, b)
    assert len([f for f in m.facts if f.id == "x"]) == 1
    assert ref_equal(ref_merge(a, b), ref_merge(b, a))


def test_c_idless_whitespace_variant_dedups():
    m = ref_merge(_s(Fact(text="alpha")), _s(Fact(text=" alpha ")))
    assert len(m.facts) == 1


def test_c_empty_timestamp_sorts_lowest():
    a = _s(Fact(text="t", id="x", timestamp=""))
    b = _s(Fact(text="t2", id="x", timestamp="2026-01-01T00:00:00Z"))
    assert ref_merge(a, b).get_fact("x").text == "t2"


def test_c_priority_ties_converge():
    a = _s(Fact(text="p", id="x", priority="high", timestamp="2026-01-01T00:00:00Z"))
    b = _s(Fact(text="q", id="x", priority="high", timestamp="2026-01-01T00:00:00Z"))
    assert ref_equal(ref_merge(a, b), ref_merge(b, a))


def test_c_tags_links_set_union():
    a = _s(Fact(text="f", id="x", tags=["a"], links=["L1"], timestamp="2026-01-01T00:00:00Z"))
    b = _s(Fact(text="f", id="x", tags=["b"], links=["L2"], timestamp="2026-01-01T00:00:00Z"))
    fx = ref_merge(a, b).get_fact("x")
    assert set(fx.tags) == {"a", "b"}
    assert set(fx.links) == {"L1", "L2"}


def test_c_fact_extra_per_key_lww_union():
    a = _s(Fact(text="f", id="x", timestamp="2026-01-01T00:00:00Z", source="s",
                type=None, priority="standard", extra={"k1": 1}))
    b = _s(Fact(text="f", id="x", timestamp="2026-01-02T00:00:00Z", extra={"k2": 2}))
    fx = ref_merge(a, b).get_fact("x")
    assert fx.extra.get("k1") == 1 and fx.extra.get("k2") == 2


def test_c_opaque_stamped_beats_unstamped():
    a = _s(preferences={"tone": "terse"})
    b = _s(preferences={"tone": {"v": "warm", "t": "2026-01-01T00:00:00Z"}})
    assert ref_merge(a, b).preferences["tone"]["v"] == "warm"


def test_c_opaque_two_concurrent_stamps_converge():
    a = _s(preferences={"tone": {"v": "A", "t": "2026-01-01T00:00:00Z"}})
    b = _s(preferences={"tone": {"v": "B", "t": "2026-01-01T00:00:00Z"}})
    assert ref_equal(ref_merge(a, b), ref_merge(b, a))


def test_c_different_namepoints_reject():
    with pytest.raises(ValueError):
        ref_merge(Soul("@one"), Soul("@two"))


# ── empty-timestamp pin regression: bareness (encoding-lock pin) ──────
# A fact bare in every field except timestamp="" must hash + sort identically
# across impls, else id-less order (=> sealed .fafb bytes) diverges. This is the
# corner the 400-example run under-sampled; pinned + biased below.


def test_c_empty_ts_bare_hashes_agree():
    # oracle-independent: the two impls' content_hash of a bare ts="" fact match
    f = Fact(text="alpha", timestamp="")
    assert sdk_chash(f) == ref_chash(f)
    # and a ts=None bare fact hashes the same as the ts="" one (both absent)
    assert sdk_chash(f) == sdk_chash(Fact(text="alpha", timestamp=None))


def test_c_empty_ts_bare_order_agrees():
    # the exact reproducer from 13/14/15: order + both oracles must converge
    a = _s(Fact(text="alpha", timestamp=""))
    b = _s(Fact(text="beta"))
    mo, mc = sdk_merge(a, b), ref_merge(a, b)
    assert [f.text for f in mo.facts] == [f.text for f in mc.facts]
    assert sdk_equal(mo, mc) and ref_equal(mo, mc)


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
    mo, mc = sdk_merge(a, b), ref_merge(a, b)
    assert sdk_equal(mo, mc), "SDK oracle: empty-ts corner diverges"
    assert ref_equal(mo, mc), "reference oracle: empty-ts corner diverges (order/index)"
