# WJTTC — `claude-fafm-sdk` test regime

**F1-inspired, championship-grade. A 5-step flow — run all five, every time.**

The `.fafm` format and the namepoint contract are what devs build on, so breakage
must show up *here*, in our suite, before a user hits it. WJTTC is a **5-step
pipeline**, not three tiers. Even when a step has nothing to run yet, it shows as a
**pass-through (Y/N)** — never dropped — so we keep the full flow in muscle memory
and don't get stuck on 3.

## The 5-step flow

| # | Tier | Guards | Runs | Status (this repo) |
|---|------|--------|------|--------------------|
| 1 | 🛡️ **BRAKE** | hard gates + honesty invariants — fail = don't ship | every commit | ✅ covered |
| 2 | ⚙️ **ENGINE** | core `.fafm` ops + CLI correctness | every commit | ✅ covered |
| 3 | 🌀 **AERO** | integration + polish (lifecycle, conformance, version) | every commit | ✅ covered |
| 4 | 🛞 **TYRE** *(Test)* | live roundtrips against the real thing — costs creds | pre-release / manual | ✅ covered (gated) |
| 5 | 🅿️ **PIT** *(Eval)* | evaluation: quality + behavioural bars, not just pass/fail | as intel/scale land | ⏭️ pass-through |

> **TYRE ≠ PIT.** TYRE = the (live) **Test** tier. PIT = **Evaluation / EVAL** — a
> separate step. Don't conflate them.

## Pass-through (Y/N)

A step with nothing applicable yet is **not skipped or forgotten** — it's a
recorded pass-through: *"step considered, N/A at this stage → pass."*

- **Why:** keeps all five steps visible so the team stays familiar with the full
  flow (not just BRAKE/ENGINE/AERO), and surfaces *when* a step should start
  filling — e.g. the first hosted feature → TYRE; the first quality/behaviour bar
  → PIT.
- **Maturity curve:** early in a build, steps 4–5 are mostly pass-through. With
  more code and more release versions they grow and become prominent. The flow
  shape stays constant; the weight shifts down the pipeline over time.

## 🛡️ 1 · BRAKE — gates + honesty invariants

- `pytest -q` passes · `ruff check` clean · `python -m build` (wheel + sdist)
- **No-guess:** a bare `.fafm` loads (interop); the `Namepoint` client fails loud +
  clear when offline (`tests/test_wjttc_soul.py`)
- **Honesty:** `init` never fakes a fact count (printed == real, fresh soul empty);
  `namepoint link` never claims a soul is "live" before a real push
  (`tests/test_wjttc_cli.py`)

## ⚙️ 2 · ENGINE — correctness

- `Soul`: etch (O(1) id-dedup) · deterministic recall (priority + recency, with the
  same-second tiebreak) · save/load roundtrip · get/delete (`tests/test_wjttc_soul.py`)
- CLI: `init` / `etch` / `recall` (+ `--tag/--type/--priority`) / `ls` / `forget`
  / `namepoint link` (`tests/test_wjttc_cli.py`)

## 🌀 3 · AERO — integration + polish

- Full lifecycle: etch → save → load → recall together
- **Cross-vendor conformance:** the soul we write is canonical `vnd.fafm+yaml` v1.1
  — the shape `fafm-engine` + `grok-faf-voice` read
- Version single-source: installed metadata == `__version__`, no static pin;
  namepoint transport carries `X-MCP-Mode: flexi` (`tests/test_wjttc_aero.py`)

## 🛞 4 · TYRE — live test (costs creds)

Real `namepoint push`/`pull`/`sync` roundtrip against a live namepoint — **no
fakes**. Gated on `MCPAAS_API_KEY` + `CFS_TEST_NAMEPOINT`; skips cleanly without
them (`tests/test_wjttc_cli.py::test_tyre_live_push_pull_roundtrip`). Idempotent —
the marker text is stable, so client-side dedup keeps re-runs from duplicating, and
a converged `sync` reports no changes.

```sh
MCPAAS_API_KEY=... CFS_TEST_NAMEPOINT=you99 uv run pytest -k tyre
```

> **Was pass-through until v0.2.x.** Filled in once `push`/`pull` shipped — the
> maturity curve in action.

## 🅿️ 5 · PIT — evaluation / EVAL

**Pass-through (this repo, today).** Evaluation is quality + behavioural assessment
beyond pass/fail — e.g. recall-ranking quality, dedup correctness over large souls,
perf, and merge quality when the server intel lands. No eval suite yet → recorded
pass-through, not omitted. Fills in as the paid-intel / scale features arrive.

## Run

```sh
uv run pytest                       # steps 1–3 (+ 4–5 if their creds/data are set)
faf wjttc                           # tier-balance audit
MCPAAS_API_KEY=... CFS_TEST_NAMEPOINT=you99 uv run pytest -k tyre   # step 4 (live)
```

**5-step status:** 🛡️ BRAKE ✅ · ⚙️ ENGINE ✅ · 🌀 AERO ✅ · 🛞 TYRE ✅ (gated) ·
🅿️ PIT ⏭️ pass-through.

> **faf-cli note:** `faf wjttc` recognises BRAKE/ENGINE/AERO/PIT but not the TYRE
> keyword yet, so it shows the TYRE test as "untiered." That's a tool taxonomy gap
> (`~/FAF/cli`), not a coverage hole — TYRE stays TYRE.
