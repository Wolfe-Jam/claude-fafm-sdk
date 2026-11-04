"""`.fafm` v1.2 spec conformance — the shared corpus from ``Wolfe-Jam/faf`` @ ``0277dc2``.

Vendored under ``tests/fixtures/fafm-spec-v1.2/`` (see ``SOURCE.md`` there; the
SHA-256 manifest is checked below so a hand edit is caught).

- 13/13 fixtures validate against ``fafm.schema.json`` exactly as ``expected.json``
  says, after the §10 date rule (PyYAML-native timestamps → RFC 3339 strings, UTC ``Z``).
- 14/14 ``txt_hash`` vectors (§8.1) through EVERY normalization copy: the data model
  (``soul``), the merge implementation (``merge``) and the reference merge.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import jsonschema  # hard dependency in [dev]: conformance must never silently skip in CI
import pytest
import reference_merge
import yaml

from claude_fafm_sdk import merge as sdk_merge
from claude_fafm_sdk import soul as sdk_soul

SPEC = Path(__file__).parent / "fixtures" / "fafm-spec-v1.2"
SCHEMA = json.loads((SPEC / "fafm.schema.json").read_text(encoding="utf-8"))
EXPECTED: dict[str, dict[str, bool]] = json.loads(
    (SPEC / "expected.json").read_text(encoding="utf-8")
)["fafm"]
VECTORS = json.loads((SPEC / "txt_hash-vectors.json").read_text(encoding="utf-8"))["vectors"]

_VALIDATOR = jsonschema.Draft202012Validator(
    SCHEMA, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
)


def _rfc3339(value: Any) -> Any:
    """§10: a parser that resolves YAML timestamps to native dates MUST serialize them
    back to RFC 3339 strings before validating, writing a UTC instant with ``Z``."""
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None:  # no offset is not RFC 3339 — leave it to fail the schema
            return value.isoformat()
        utc = value.astimezone(datetime.timezone.utc)
        frac = f".{utc.microsecond:06d}".rstrip("0") if utc.microsecond else ""
        return utc.strftime("%Y-%m-%dT%H:%M:%S") + frac + "Z"
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _rfc3339(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_rfc3339(v) for v in value]
    return value


def _load(rel: str) -> Any:
    return _rfc3339(yaml.safe_load((SPEC / rel).read_text(encoding="utf-8")))


def _conforms(doc: Any) -> bool:
    return not list(_VALIDATOR.iter_errors(doc))


# ── corpus integrity ──────────────────────────────────────────────────────────


def test_vendored_manifest_matches_files():
    """Every vendored file still matches the SHA-256 recorded in SOURCE.md."""
    source = (SPEC / "SOURCE.md").read_text(encoding="utf-8")
    manifest = re.findall(r"^([0-9a-f]{64})  \./(\S+)$", source, re.MULTILINE)
    assert len(manifest) == 16
    for digest, rel in manifest:
        assert hashlib.sha256((SPEC / rel).read_bytes()).hexdigest() == digest, rel


def test_corpus_is_13_fixtures_and_14_vectors():
    on_disk = sorted(str(p.relative_to(SPEC)) for p in SPEC.glob("*/*.fafm"))
    assert sorted(EXPECTED) == on_disk
    assert len(EXPECTED) == 13
    assert len(VECTORS) == 14


def test_date_time_format_is_actually_asserted():
    """Guard: without a date-time checker jsonschema silently ignores ``format``."""
    assert "date-time" in _VALIDATOR.format_checker.checkers
    assert not _conforms({**_load("valid/voice.fafm"), "created": "not-a-date"})


# ── 13/13 schema conformance per expected.json ────────────────────────────────


@pytest.mark.parametrize("rel", sorted(EXPECTED))
def test_fixture_conforms_as_expected(rel: str):
    assert _conforms(_load(rel)) is EXPECTED[rel]["conforms"]


def test_unquoted_dates_need_the_section_10_rule():
    """The §10 rule is load-bearing: raw PyYAML datetimes are not strings."""
    raw = yaml.safe_load((SPEC / "valid/unquoted-dates.fafm").read_text(encoding="utf-8"))
    assert isinstance(raw["created"], datetime.datetime)
    assert not _conforms(raw)
    assert _load("valid/unquoted-dates.fafm")["created"] == "2026-11-02T00:00:00Z"


# ── SDK writer output conforms (Soul.load → to_doc) ───────────────────────────

_ROUND_TRIP = sorted(r for r, e in EXPECTED.items() if e["conforms"])


@pytest.mark.parametrize(
    "rel",
    [
        r
        for r in _ROUND_TRIP
    ],
)
def test_sdk_rewrite_of_valid_fixture_conforms(rel: str):
    doc = yaml.safe_load((SPEC / rel).read_text(encoding="utf-8"))
    soul = sdk_soul.Soul.from_doc(doc)
    out = yaml.safe_load(soul.to_yaml())
    assert _conforms(out), list(_VALIDATOR.iter_errors(out))
    # §10: never a lower version than read; every corpus doc is 1.1 or 1.2.
    assert out["version"] == "1.2"
    # tombstones survive the round trip
    assert len(out["memory"].get("tombstones", [])) == len(doc["memory"].get("tombstones", []))


# ── 14/14 txt_hash vectors, every copy ────────────────────────────────────────

_COPIES = {
    "soul": (sdk_soul.normalize_text, sdk_soul.txt_hash),
    "merge": (sdk_merge.normalize_text, sdk_merge._txt_hash),
    "reference": (reference_merge.normalize_text, reference_merge.txt_hash),
}


@pytest.mark.parametrize("copy", sorted(_COPIES))
@pytest.mark.parametrize("vec", VECTORS, ids=[v["name"] for v in VECTORS])
def test_txt_hash_vector(copy: str, vec: dict[str, str]):
    normalize, hasher = _COPIES[copy]
    assert normalize(vec["text"]) == vec["normalized"]
    assert hasher(vec["text"]) == vec["txt_hash"]
