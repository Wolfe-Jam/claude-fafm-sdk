"""WJTTC AERO — integration + polish.

The pieces working together (full soul lifecycle), cross-vendor format
conformance (the soul we write IS the format others read), and version sync.
"""

import re
from pathlib import Path

import yaml

import claude_fafm_sdk
from claude_fafm_sdk import Soul


def test_aero_full_lifecycle_roundtrip(tmp_path):
    # etch → save → load → recall, all the pieces together.
    s = Soul("@me")
    s.etch("first", id="a", type="reference", priority="high")
    s.etch("second", id="b", type="project")
    back = Soul.load(s.save(tmp_path / "life.fafm"))
    assert len(back.facts) == 2
    assert [f.id for f in back.recall(min_priority="high")] == ["a"]


def test_aero_cross_vendor_format_conformance(tmp_path):
    # The .fafm we write must be canonical vnd.fafm+yaml v1.1 — the shape
    # fafm-engine + grok-faf-voice read. One format, never a fork.
    s = Soul("@me")
    s.etch("a fact", id="x", type="project", priority="high")
    doc = yaml.safe_load((s.save(tmp_path / "c.fafm")).read_text())
    assert doc["version"] == "1.1"
    assert doc["namepoint"] == "@me"
    assert isinstance(doc["memory"]["facts"], list)
    fact = doc["memory"]["facts"][0]
    assert fact["text"] == "a fact" and fact["id"] == "x"  # canonical fact keys


def test_aero_version_sync():
    # pyproject version == package __version__ — no drift.
    pyproject = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()
    m = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
    assert m and m.group(1) == claude_fafm_sdk.__version__
