"""Step 6 — cross-implementation same-second recall (SDK vs fafm-engine).

SDK rank: (priority, timestamp, insertion_index) descending → higher list
index wins same-second ties (last appended first).

Engine rank: (priority, timestamp) only + stable sort → equal keys keep
**list order** (first stored first). So on pure same-second ties the two
**diverge** (opposite ends of the list). That is a real drift, not a match.

This test pins both behaviors so neither side can change silently.
Engine optional: skip if not installed / not adjacent under ~/FAF/fafm-engine.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from claude_fafm_sdk import Fact, Soul

_ENGINE_ROOT = Path(__file__).resolve().parents[2] / "fafm-engine"
if _ENGINE_ROOT.is_dir() and str(_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENGINE_ROOT))

pytest.importorskip("fafm_engine", reason="fafm_engine not installed / not adjacent")
from fafm_engine.soul import Fact as EngineFact  # noqa: E402  # after optional importorskip
from fafm_engine.soul import Soul as EngineSoul  # noqa: E402


def _seed_both() -> tuple[Soul, EngineSoul]:
    """Same insert/update sequence: append a,b → update a in place → append c.

    All facts share one second-granularity timestamp.
    """
    ts = "2026-06-15T12:00:00Z"
    sdk = Soul("@cross")
    eng = EngineSoul("@cross")

    sdk.add(Fact(text="first", id="a", priority="standard", timestamp=ts))
    sdk.add(Fact(text="second", id="b", priority="standard", timestamp=ts))
    sdk.add(Fact(text="first-v2", id="a", priority="standard", timestamp=ts))
    sdk.add(Fact(text="third", id="c", priority="standard", timestamp=ts))

    # Engine has no public add — mirror storage on private list + _by_id
    eng._facts = [
        EngineFact(text="first", id="a", priority="standard", timestamp=ts),
        EngineFact(text="second", id="b", priority="standard", timestamp=ts),
    ]
    eng._by_id = {"a": 0, "b": 1}
    eng._facts[eng._by_id["a"]] = EngineFact(
        text="first-v2", id="a", priority="standard", timestamp=ts
    )
    eng._facts.append(EngineFact(text="third", id="c", priority="standard", timestamp=ts))
    eng._by_id["c"] = 2

    return sdk, eng


def test_cross_impl_same_second_recall_documents_known_drift():
    """Pin SDK SoT order and engine's stable-sort list order (they differ)."""
    sdk, eng = _seed_both()

    assert [f.id for f in sdk.facts] == ["a", "b", "c"]
    assert [f.id for f in eng.facts] == ["a", "b", "c"]
    assert sdk.get_fact("a").text == "first-v2"
    assert eng.get_fact("a").text == "first-v2"

    sdk_order = [f.id for f in sdk.recall()]
    eng_order = [f.id for f in eng.recall()]

    # SDK SoT: insertion_index desc → last appended first
    assert sdk_order == ["c", "b", "a"]

    # Engine: equal (priority, ts) → stable sort preserves list order
    assert eng_order == ["a", "b", "c"]

    # Explicit: this is the known same-second drift (not accidental parity)
    assert sdk_order != eng_order
