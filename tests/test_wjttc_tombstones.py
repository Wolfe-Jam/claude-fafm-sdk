"""WJTTC — Forgettable Memory (1.5): convergent forget via tombstones.

Hand-authored goldens for the property laws T1–T8 (freeze §4). Property search
under-samples delete corners AND can't catch a bug **both** implementations share
("they agree" proves nothing if both are wrong) — so these pin the spec-correct
outcome by hand and hold **every** merge implementation to it.

Discipline: the core suppression facts assert LITERAL fact-presence/absence and
tombstone membership (oracle-independent) — a permissive ``souls_equal`` cannot
hide a divergence. ``souls_equal`` is used only where the law IS about equality
(both merge directions converge; seal byte-identity).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import reference_merge

from claude_fafm_sdk.merge import merge_souls as sdk_merge
from claude_fafm_sdk.merge import souls_equal as sdk_equal
from claude_fafm_sdk.packet import (
    from_packet,
    normalize_for_seal,
    to_packet,
)
from claude_fafm_sdk.soul import (
    Fact,
    Soul,
    _tombstones_from_wire,
    _tombstones_to_wire,
    txt_hash,
)

NP = "@tomb"

# every implementation the goldens hold to (reference only if its clean-room impl is ready)
_IMPLS = {"sdk": sdk_merge}
if getattr(reference_merge, "IMPLEMENTED", False):
    _IMPLS["reference"] = reference_merge.merge_souls

_EQUALS = {"sdk": sdk_equal}
if getattr(reference_merge, "IMPLEMENTED", False):
    _EQUALS["reference"] = reference_merge.souls_equal

# literal txt_hashes (SHA-256 of NFC+stripped text) — pin them so a change to the
# id-less keying is a conscious wire decision, never a silent drift (T6).
H_ALPHA = "8ed3f6ad685b959ead7022518e1af76cd816f8e8ec7ccdda1ed4018e8f2223f8"

T1 = "2026-01-01T00:00:00Z"  # early
T2 = "2026-06-01T00:00:00Z"  # a delete after T1
T3 = "2026-09-01T00:00:00Z"  # a re-etch after T2


def _s(*facts: Fact, **kw) -> Soul:
    return Soul(NP, facts=list(facts), **kw)


def _both(a: Soul, b: Soul) -> dict[str, Soul]:
    """merge(a, b) under every implementation."""
    return {name: m(a, b) for name, m in _IMPLS.items()}


def _has(soul: Soul, id: str) -> bool:
    return soul.get_fact(id) is not None


def _has_text(soul: Soul, text: str) -> bool:
    return any(f.id is None and f.text == text for f in soul.facts)


# ── T1 — Resurrection: forget(X) merged with a peer that still has X → X absent ─
def test_t1_resurrection_id_fact():
    forgotten = _s(Fact(text="alpha", id="x", timestamp=T1))
    forgotten.forget("x", deleted_at=T2)
    peer = _s(Fact(text="alpha", id="x", timestamp=T1))  # peer never forgot
    for name, m in _both(forgotten, peer).items():
        assert not _has(m, "x"), f"{name}: forgotten fact resurrected"
        assert ("id", "x") in m.tombstones, f"{name}: tombstone lost"
    # ... and it converges the other way too (peer merged into forgetter).
    for name, eq in _EQUALS.items():
        assert eq(_IMPLS[name](forgotten, peer), _IMPLS[name](peer, forgotten)), name


# ── T2 — Re-etch: a later write (ts > deleted_at) outranks the tombstone ───────
def test_t2_reetch_after_delete_wins():
    base = _s(Fact(text="alpha", id="x", timestamp=T1))
    base.forget("x", deleted_at=T2)
    reetch = _s(Fact(text="alpha-v2", id="x", timestamp=T3))  # T3 > T2
    for name, m in _both(base, reetch).items():
        assert _has(m, "x"), f"{name}: re-etch suppressed"
        assert m.get_fact("x").text == "alpha-v2", name
        assert ("id", "x") in m.tombstones, f"{name}: tombstone must remain (grow-only)"


# ── T3 — Delete-wins tie: equal clocks → suppressed, in BOTH merge orders ──────
def test_t3_delete_wins_on_equal_clock():
    deleter = _s()
    deleter.forget("x", deleted_at=T1)          # deleted_at == fact ts
    holder = _s(Fact(text="alpha", id="x", timestamp=T1))
    for name, merge in _IMPLS.items():
        m_ab = merge(deleter, holder)
        m_ba = merge(holder, deleter)
        assert not _has(m_ab, "x"), f"{name}: equal clock did not delete-win (a,b)"
        assert not _has(m_ba, "x"), f"{name}: equal clock did not delete-win (b,a)"


def test_t3_delete_wins_over_empty_timestamp_fact():
    # an empty/absent-ts fact sorts lowest → any real tombstone outranks it.
    deleter = _s()
    deleter.forget("x", deleted_at=T1)
    holder = _s(Fact(text="alpha", id="x", timestamp=""))
    for name, m in _both(deleter, holder).items():
        assert not _has(m, "x"), name


# ── T4 — No zombie: suppression drops the WHOLE fact, not just some fields ─────
def test_t4_no_zombie_tags_links_extra():
    forgotten = _s(Fact(text="alpha", id="x", timestamp=T1, tags=["a"], links=["L"],
                        extra={"k": "v"}))
    forgotten.forget("x", deleted_at=T2)
    peer = _s(Fact(text="alpha", id="x", timestamp=T1, tags=["b"], links=["L2"],
                   extra={"k2": "v2"}))
    for name, m in _both(forgotten, peer).items():
        assert not _has(m, "x"), name
        # nothing from the fact survives — no zombie tags/links/extra anywhere.
        assert all(f.id != "x" for f in m.facts), name


# ── T5 — Monotone graveyard: join = max(deleted_at); tombstone never lost ─────
def test_t5_graveyard_deepens_to_max():
    early = _s()
    early.forget("x", deleted_at=T1)
    late = _s()
    late.forget("x", deleted_at=T2)   # T2 > T1
    for name, m in _both(early, late).items():
        assert m.tombstones[("id", "x")] == T2, f"{name}: join must keep max deleted_at"


def test_t5_tombstone_survives_merge_with_clean_peer():
    forgotten = _s()
    forgotten.forget("x", deleted_at=T2)
    clean = _s(Fact(text="unrelated", id="y", timestamp=T1))
    for name, m in _both(forgotten, clean).items():
        assert ("id", "x") in m.tombstones, name
        assert _has(m, "y"), name


# ── T6 — Id-less align: txt_hash keys the same G-Set membership, not content_hash ─
def test_t6_idless_forget_suppresses_by_normalized_text():
    forgotten = _s(Fact(text="alpha", timestamp=T1))     # id-less
    forgotten.forget_text("  alpha  ", deleted_at=T2)    # matches via NFC+strip
    peer = _s(Fact(text="alpha", timestamp=T1))
    for name, m in _both(forgotten, peer).items():
        assert not _has_text(m, "alpha"), f"{name}: id-less forget did not converge"
        assert ("txt", H_ALPHA) in m.tombstones, name


def test_t6_txt_hash_is_pinned_literal():
    # the id-less tombstone key is SHA-256 of normalize_text — pinned so a keying
    # change (e.g. drifting to content_hash) is a conscious wire decision.
    assert txt_hash("alpha") == H_ALPHA
    assert txt_hash("  alpha  ") == H_ALPHA           # NFC+strip, same key
    assert txt_hash("alpha") != txt_hash("beta")


# ── T7 — Seal identity: tombstones travel; equal logical state → equal bytes ──
def test_t7_seal_carries_tombstones_and_is_byte_identical():
    s = _s(Fact(text="keep", id="k", timestamp=T1))
    s.forget("gone", deleted_at=T2)
    pkt = to_packet(s)
    reopened = from_packet(pkt)
    assert ("id", "gone") in reopened.tombstones          # survived the seal
    assert _has(reopened, "k")
    # already-canonical soul re-seals to identical bytes (idempotent normalize).
    assert to_packet(s) == to_packet(normalize_for_seal(s))
    assert sdk_equal(reopened, s)


def test_t7_no_tombstones_seals_identically_to_pre_1_5():
    # a soul that never forgot emits NO tombstones key → byte-identical to a 1.4 seal.
    s = _s(Fact(text="alpha", id="x", timestamp=T1))
    assert "tombstones" not in s.to_doc()["memory"]
    assert from_packet(to_packet(s)).tombstones == {}


# ── T8 — C/A/I with deletes present (concrete; both impls) ─────────────────────
def test_t8_commutative_with_deletes():
    a = _s(Fact(text="alpha", id="x", timestamp=T1), Fact(text="beta", id="y", timestamp=T1))
    a.forget("y", deleted_at=T2)
    b = _s(Fact(text="alpha", id="x", timestamp=T1), Fact(text="gamma", id="z", timestamp=T1))
    for name, eq in _EQUALS.items():
        assert eq(_IMPLS[name](a, b), _IMPLS[name](b, a)), f"{name}: not commutative"


def test_t8_idempotent_live_fact_under_its_own_tombstone():
    # the corner that forced pre-suppression in logical_state: a soul holding a live
    # fact AND a tombstone that outranks it must equal its own self-merge.
    s = _s(Fact(text="alpha", id="x", timestamp=T1))
    s.forget("x", deleted_at=T2)
    s.add(Fact(text="alpha", id="x", timestamp=T1))   # a stale peer re-introduced it
    for name, eq in _EQUALS.items():
        assert eq(_IMPLS[name](s, s), s), f"{name}: idempotence broke under tombstone"


def test_t8_no_zombie_links_across_reetch_is_associative():
    # REGRESSION (differential, 2026-07-27): a forgotten low-clock version must not lend
    # its links to a surviving re-etch. b holds a live c-fact carrying L1 AND a tombstone
    # for c that outranks it (clock "" <= T1); soul c re-etches c at T3 (> T1) with no
    # links. Emit-only suppression folded L1 into the survivor in ONE fold order → broke
    # associativity. Version-level suppression (R1') drops the forgotten version's L1.
    # Oracle-independent: the surviving fact carries NO zombie link.
    a = _s()
    b = _s(Fact(text="alpha", id="c", links=["L1"]), tombstones={("id", "c"): T1})
    c = _s(Fact(text="alpha", id="c", timestamp=T3))
    for name, m in _IMPLS.items():
        left = m(m(a, b), c)
        right = m(a, m(b, c))
        for label, r in (("left", left), ("right", right)):
            fc = r.get_fact("c")
            assert fc is not None and fc.timestamp == T3, f"{name}/{label}: re-etch lost"
            assert fc.links == [], f"{name}/{label}: zombie link survived the tombstone"
        assert _EQUALS[name](left, right), f"{name}: not associative across the tombstone"


def test_t8_cex2_mirror_associativity():
    # CEX-2 (the mirror of the above): b holds BOTH c-versions in one soul
    # (c@T2[] and c@""[L1]); the tombstone lives in a THIRD soul. The naive fold unions
    # L1 into c@T2 before the tombstone is seen. Rule T + version-drop → links = [].
    a = _s()
    b = _s(
        Fact(text="alpha"),                          # id-less filler
        Fact(text="alpha", id="c", timestamp=T2),    # re-etch, no links
        Fact(text="alpha", id="c", links=["L1"]),    # low version @"" carrying L1
    )
    c = _s(tombstones={("id", "c"): T1})
    for name, m in _IMPLS.items():
        left = m(m(a, b), c)
        right = m(a, m(b, c))
        for label, r in (("left", left), ("right", right)):
            fc = r.get_fact("c")
            assert fc is not None and fc.links == [], f"{name}/{label}: zombie link survived"
        assert _EQUALS[name](left, right), f"{name}: CEX-2 not associative"


def test_rule_t_different_clock_same_id_tags_winner_only():
    # Rule T WITHOUT tombstones (the second merge-law delta): a later same-id
    # write's tags win; the older version's tags do NOT sticky-union. This is the
    # documented 1.4→1.5 behavior change. Oracle-independent.
    a = _s(Fact(text="f", id="x", tags=["old"], links=["Lold"], timestamp=T1))
    b = _s(Fact(text="f", id="x", tags=["new"], timestamp=T3))       # T3 > T1
    for name, m in _both(a, b).items():
        fx = m.get_fact("x")
        assert set(fx.tags) == {"new"}, f"{name}: lower-clock tag leaked (Rule T violated)"
        assert fx.links == [], f"{name}: lower-clock link leaked (Rule T violated)"


def test_rule_t_equal_clock_same_id_tags_still_union():
    # Concurrent (equal-clock) writes STILL union — add-wins preserved (unchanged from 1.4).
    a = _s(Fact(text="f", id="x", tags=["a"], links=["L1"], timestamp=T1))
    b = _s(Fact(text="f", id="x", tags=["b"], links=["L2"], timestamp=T1))
    for name, m in _both(a, b).items():
        fx = m.get_fact("x")
        assert set(fx.tags) == {"a", "b"}, f"{name}: concurrent union lost"
        assert set(fx.links) == {"L1", "L2"}, name


def test_t8_associative_with_deletes():
    a = _s(Fact(text="alpha", id="x", timestamp=T1))
    b = _s()
    b.forget("x", deleted_at=T2)
    c = _s(Fact(text="alpha", id="x", timestamp=T3))   # re-etch, T3 > T2
    for name, eq in _EQUALS.items():
        left = _IMPLS[name](_IMPLS[name](a, b), c)
        right = _IMPLS[name](a, _IMPLS[name](b, c))
        assert eq(left, right), f"{name}: not associative with deletes"
        assert _has(left, "x"), f"{name}: re-etch (T3>T2) should win"


# ── interop honesty: a soul reloads its graveyard from disk unchanged ─────────
def test_reload_roundtrip_preserves_tombstones(tmp_path):
    s = _s(Fact(text="alpha", id="x", timestamp=T1))
    s.forget("x", deleted_at=T2)
    s.forget_text("beta", deleted_at=T2)
    p = tmp_path / "s.fafm"
    s.save(p)
    again = Soul.load(p)
    assert again.tombstones == s.tombstones


# ── wire robustness: memory.tombstones parse is lenient (fail-open on load) ────
def test_wire_parse_skips_malformed_rows():
    raw = [
        {"id": "keep", "deleted_at": T1},          # valid id row
        {"txt_hash": H_ALPHA, "deleted_at": T2},   # valid txt row
        {"id": "nope"},                            # missing deleted_at → skip
        {"deleted_at": T1},                        # neither id nor txt_hash → skip
        {"id": "bad", "deleted_at": ""},           # empty deleted_at → skip
        {"id": "bad2", "deleted_at": 12345},       # non-string deleted_at → skip
        {"id": None, "deleted_at": T1},            # null id → skip
        "not-a-dict",                              # non-mapping → skip
    ]
    assert _tombstones_from_wire(raw) == {("id", "keep"): T1, ("txt", H_ALPHA): T2}


def test_wire_parse_dup_keys_take_max():
    raw = [
        {"id": "x", "deleted_at": T1},
        {"id": "x", "deleted_at": T3},   # max
        {"id": "x", "deleted_at": T2},
    ]
    assert _tombstones_from_wire(raw) == {("id", "x"): T3}


def test_wire_parse_non_list_is_empty():
    assert _tombstones_from_wire(None) == {}
    assert _tombstones_from_wire({"id": "x"}) == {}   # a mapping, not a list
    assert _tombstones_from_wire("") == {}


def test_wire_roundtrip_is_canonical_and_sorted():
    tombs = {("txt", H_ALPHA): T2, ("id", "b"): T1, ("id", "a"): T3}
    wire = _tombstones_to_wire(tombs)
    # canonical order by (kind, key): ("id","a") < ("id","b") < ("txt", …)
    assert [next(iter(r)) for r in wire] == ["id", "id", "txt_hash"]
    assert _tombstones_from_wire(wire) == tombs   # lossless round-trip


# ── seal: tombstone list order is canonical → forget order can't change bytes ──
def test_seal_tombstone_insertion_order_independent():
    a = _s(Fact(text="k", id="k", timestamp=T1))
    a.forget("z1", deleted_at=T1)
    a.forget("z2", deleted_at=T2)
    a.forget("z3", deleted_at=T3)
    b = _s(Fact(text="k", id="k", timestamp=T1))
    b.forget("z3", deleted_at=T3)   # same graveyard, opposite forget order
    b.forget("z1", deleted_at=T1)
    b.forget("z2", deleted_at=T2)
    assert to_packet(a) == to_packet(b)   # identical tombstones → identical sealed bytes


# ── forget edge cases (Soul API) ──────────────────────────────────────────────
def test_forget_on_empty_soul_records_tombstone():
    s = _s()
    assert s.forget("ghost") is False          # nothing live to remove
    assert ("id", "ghost") in s.tombstones     # …but the tombstone is recorded


def test_double_forget_deepens_never_regresses():
    s = _s()
    s.forget("x", deleted_at=T1)
    s.forget("x", deleted_at=T3)               # later → deepens
    assert s.tombstones[("id", "x")] == T3
    s.forget("x", deleted_at=T2)               # earlier → must NOT regress (grow-only)
    assert s.tombstones[("id", "x")] == T3


def test_forget_id_and_text_are_independent_keys():
    # an id-fact and an id-less fact with the SAME text are distinct tombstone keys.
    s = _s(Fact(text="alpha", id="a", timestamp=T1), Fact(text="alpha", timestamp=T1))
    s.forget("a", deleted_at=T1)                       # id tombstone only
    assert ("id", "a") in s.tombstones
    assert ("txt", H_ALPHA) not in s.tombstones
    assert any(f.id is None and f.text == "alpha" for f in s.facts)  # id-less "alpha" survives


def test_forget_removes_forgotten_fact_from_local_recall():
    s = _s(Fact(text="secret", id="sec", timestamp=T1), Fact(text="keep", id="k", timestamp=T1))
    s.forget("sec")
    assert s.get_fact("sec") is None
    assert [f.id for f in s.facts] == ["k"]            # gone from the live set immediately
