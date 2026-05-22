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
| 🛞 **TYRE** | costs creds | pre-release / manual | Live namepoint probes against `memory.faf.one` (when the backend is real). |

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
- Version sync: `pyproject.toml` == `__version__` (`tests/test_wjttc_aero.py`)

## 🛞 TYRE — live (later)

When the namepoint backend is live: real `Namepoint.recall/push/pull` against
`memory.faf.one`, and an SDK→`.fafm`→grok-faf-voice read roundtrip. (End-to-end
roundtrip verified previously in grok-faf-voice v0.3.x.)

## Run

```sh
uv run pytest                       # or: pip3 install -e ".[dev]" && pytest
faf wjttc                           # tier-balance audit
```

**Balance:** BRAKE + ENGINE + AERO covered (0 untiered). TYRE waits on the backend.
