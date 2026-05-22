"""WJTTC AERO — integration + polish.

The pieces working together (full soul lifecycle), cross-vendor format
conformance (the soul we write IS the format others read), and version sync.
"""

import asyncio
import os
import re
from pathlib import Path

import pytest
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


def test_aero_namepoint_sends_flexi_header(monkeypatch):
    # Regression guard: the namepoint transport MUST carry X-MCP-Mode: flexi —
    # mcpaas-cf defaults to strict MCP and rejects stock fastmcp clients (400).
    # This is the silent-drift the live e2e receipt caught. No network needed.
    from claude_fafm_sdk import client as client_mod

    captured: dict = {}

    class FakeTransport:
        def __init__(self, url, headers=None):
            captured["url"], captured["headers"] = url, headers

    class FakeResult:
        content = [type("Block", (), {"text": "soul-body"})()]

    class FakeClient:
        def __init__(self, transport):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def call_tool(self, name, args):
            captured["tool"], captured["args"] = name, args
            return FakeResult()

    monkeypatch.setattr(client_mod, "_client_classes", lambda: (FakeClient, FakeTransport))
    body = asyncio.run(client_mod.Namepoint("grok").pull())

    assert body == "soul-body"
    assert captured["headers"] == {"X-MCP-Mode": "flexi"}
    assert captured["tool"] == "get_soul"
    assert captured["args"] == {"soul": "grok"}


@pytest.mark.skipif(not os.environ.get("MCPAAS_LIVE"), reason="set MCPAAS_LIVE=1 to pull from live memory.faf.one")
def test_aero_live_pull_memory_faf_one():
    # Live end-to-end: the SDK Namepoint client pulls a public soul from the
    # deployed memory.faf.one/mcp. Needs the [namepoint] extra + network.
    from claude_fafm_sdk import Namepoint

    body = asyncio.run(Namepoint("claude").pull())
    assert body and "claude" in body.lower()
