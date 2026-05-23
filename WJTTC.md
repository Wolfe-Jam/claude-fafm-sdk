# WJTTC — `claude-fafm-sdk` test regime

**F1-inspired, championship-grade. Four tiers, run on every commit.**

The `.fafm` format and the namepoint contract are the things devs build on — so
breakage must show up here, in our suite, **before** a user hits it. Tiers are
marked in the test name (`faf wjttc` reads them).

## Tiers

| Tier | Cost | Trigger | Job |
|------|------|---------|-----|
| 🛡️ **BRAKE** | ~free | every commit | Hard gates + no-guess/honesty invariants. Fail = don't ship. |
| ⚙️ **ENGINE** | ~free | every commit | Correctness of the local `.fafm` ops + the CLI. |
| 🌀 **AERO** | ~free | every commit | Integration + polish: full lifecycle, format conformance, version sync. |
| 🛞 **TYRE** | costs creds | pre-release / manual | Live `push`/`pull` roundtrip against a real namepoint (gated on `MCPAAS_API_KEY` + `CFS_TEST_NAMEPOINT`). |
| 🅿️ **PIT** | — | — | Evaluation / EVAL tier — reserved (no eval suite in this SDK yet). |

## 🛡️ BRAKE — gates + honesty invariants

- `pytest -q` passes · `ruff check` clean · `python -m build` (wheel + sdist)
- **No-guess:** a bare `.fafm` loads (interop); the `Namepoint` client fails loud
  + clear when offline (`tests/test_wjttc_soul.py`)
- **Honesty:** `init` never fakes a fact count — printed count == real count; a
  fresh soul is empty (`tests/test_wjttc_cli.py`)

## ⚙️ ENGINE — correctness

- `Soul`: etch (O(1) id-dedup) · deterministic recall (priority + recency) ·
  save/load roundtrip · get/delete (`tests/test_wjttc_soul.py`)
- CLI: `init` / `etch` / `recall` (`tests/test_wjttc_cli.py`)

## 🌀 AERO — integration + polish

- Full lifecycle: etch → save → load → recall together
- **Cross-vendor format conformance:** the soul we write is canonical
  `vnd.fafm+yaml` v1.1 — the shape `fafm-engine` + `grok-faf-voice` read
- Version single-source: installed metadata == `__version__`, no static pin (`tests/test_wjttc_aero.py`)

## 🛞 TYRE — live (the TEST tier)

Real `namepoint push`/`pull` roundtrip against a live namepoint — no fakes.
Gated on `MCPAAS_API_KEY` + `CFS_TEST_NAMEPOINT`; skips cleanly without them
(`tests/test_wjttc_cli.py::test_tyre_live_push_pull_roundtrip`). Idempotent —
the marker text is stable, so client-side dedup keeps re-runs from duplicating.

> **TYRE vs PIT:** TYRE = the (live) **Test** tier; PIT = **Evaluation / EVAL**, a
> separate tier (no eval suite here yet). Note: `faf wjttc` doesn't recognize the
> TYRE keyword yet — it shows this test as "untiered" — a faf-cli taxonomy gap, not
> a coverage hole.

```sh
MCPAAS_API_KEY=... CFS_TEST_NAMEPOINT=you99 uv run pytest -k tyre
```

## Run

```sh
uv run pytest                       # or: pip3 install -e ".[dev]" && pytest
faf wjttc                           # tier-balance audit
```

**Balance:** BRAKE + ENGINE + AERO + a live TYRE roundtrip. PIT (eval) reserved.
