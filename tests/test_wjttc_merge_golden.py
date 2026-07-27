"""Golden fixtures — hand-authored `input → expected` for the residual
join-semilattice fields (sessions G1, retention G4, opaque LWW maps).

Property search under-samples these (residual fields) AND can't catch a bug that BOTH
implementations share ("the two agree" proves nothing if both are wrong). These
goldens pin the **spec-correct** expected output by hand, and assert *every*
available merge implementation (both independent implementations) reproduces it.
Frozen against 1.1.1 — a change that alters a golden is a conscious decision.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from claude_fafm_sdk.merge import merge_souls as sdk_merge  # noqa: E402
from claude_fafm_sdk.merge import souls_equal as sdk_equal  # noqa: E402
from claude_fafm_sdk.soul import Fact, Soul  # noqa: E402

import reference_merge  # noqa: E402

NP = "@golden"

# every implementation the goldens hold to (reference only if its clean-room impl is ready)
_IMPLS = {"sdk": sdk_merge}
if getattr(reference_merge, "IMPLEMENTED", False):
    _IMPLS["reference"] = reference_merge.merge_souls


def _both(a: Soul, b: Soul) -> dict[str, Soul]:
    return {name: m(a, b) for name, m in _IMPLS.items()}


def test_golden_sessions_identical_entry_dedups():
    # G1: identical session entries → G-Set dedups to ONE.
    a = Soul(NP, sessions=[{"id": "s1", "n": 1}])
    b = Soul(NP, sessions=[{"id": "s1", "n": 1}])
    for name, m in _both(a, b).items():
        assert len(m.sessions) == 1, name


def test_golden_sessions_same_id_diff_content_keeps_both():
    # G1 append-only bound (MERGE.md §5.3a): SAME session id, different content
    # → both survive. v1 has NO session-id LWW; this pins the documented honesty.
    a = Soul(NP, sessions=[{"id": "s1", "n": 1}])
    b = Soul(NP, sessions=[{"id": "s1", "n": 2}])
    for name, m in _both(a, b).items():
        assert len(m.sessions) == 2, name


def test_golden_retention_conflict_max_register():
    # G4: retention conflict → deterministic max("forever","30d") == "forever",
    # commutatively.
    a, b = Soul(NP, retention="forever"), Soul(NP, retention="30d")
    for name, m in _both(a, b).items():
        assert m.retention == "forever", name
    for name, m in _both(b, a).items():  # commutative
        assert m.retention == "forever", name


def test_golden_memory_extra_key_union():
    # opaque LWW-per-key: disjoint keys both survive.
    a = Soul(NP, memory_extra={"k1": "v1"})
    b = Soul(NP, memory_extra={"k2": "v2"})
    for name, m in _both(a, b).items():
        assert set(m.memory_extra) == {"k1", "k2"}, name


def test_golden_memory_extra_same_key_lww_newer_wins():
    # opaque LWW-per-key CONFLICT (not just union): same key, {v,t} form →
    # the newer timestamp wins, commutatively.
    a = Soul(NP, memory_extra={"k1": {"v": "old", "t": "2026-01-01T00:00:00Z"}})
    b = Soul(NP, memory_extra={"k1": {"v": "new", "t": "2026-02-01T00:00:00Z"}})
    for name, m in _both(a, b).items():
        assert m.memory_extra["k1"]["v"] == "new", name
    for name, m in _both(b, a).items():  # commutative
        assert m.memory_extra["k1"]["v"] == "new", name


def test_golden_soul_extra_union_and_lww():
    # soul-level `extra` shares the opaque-map join: disjoint keys union +
    # same-key LWW by timestamp — dedicated `extra` golden.
    a = Soul(NP, extra={"k1": "v1", "shared": {"v": "old", "t": "2026-01-01T00:00:00Z"}})
    b = Soul(NP, extra={"k2": "v2", "shared": {"v": "new", "t": "2026-02-01T00:00:00Z"}})
    for name, m in _both(a, b).items():
        assert set(m.extra) == {"k1", "k2", "shared"}, name
        assert m.extra["shared"]["v"] == "new", name


def test_golden_empty_ts_plus_residual_combo():
    # empty-ts fact (T2 → absent) alongside every residual field → deterministic,
    # and all impls converge on the same logical soul.
    a = Soul(
        NP,
        facts=[Fact(text="alpha", timestamp="")],
        retention="forever",
        sessions=[{"id": "s1", "n": 1}],
        memory_extra={"k1": "v1"},
    )
    b = Soul(
        NP,
        facts=[Fact(text="beta")],
        retention="30d",
        sessions=[{"id": "s2", "n": 2}],
        memory_extra={"k2": "v2"},
    )
    outs = _both(a, b)

    # cross-impl convergence (if reference is present)
    if "reference" in outs:
        assert sdk_equal(outs["sdk"], outs["reference"])
        assert reference_merge.souls_equal(outs["sdk"], outs["reference"])

    # concrete spec-correct values, every impl
    for name, m in outs.items():
        assert len(m.facts) == 2, name
        assert len(m.sessions) == 2, name
        assert set(m.memory_extra) == {"k1", "k2"}, name
        assert m.retention == "forever", name
        alpha = next(f for f in m.facts if f.text == "alpha")
        assert alpha.timestamp is None, name  # T2: empty-ts normalized to absent
