# TESTING.md — claude-fafm-sdk

**Status:** essential · ship law  
**Doctrine:** We break things here so they **never even know it was ever broken.**  
If a law is not a red-line test, it is a rumor.

This file is part of the product contract for Forgettable Memory and the
trajectory to Compactable (2.0). Full roadmap: private vault  
`PLANET-FAF/memory/plan-forgettable-memory-2-0.md`.  
Interop / merge law: [INTEROP.md](INTEROP.md) · [MERGE.md](MERGE.md).

---

## 0. Why this exists

| Surface | Promise |
|---------|---------|
| **Users / agents** | Forget stays forgotten. Merge does not lie. Seal is deterministic. |
| **This suite** | Every promise above is a **failing test** when broken — before publish, before “it worked on my machine.” |

We do **not** ship on vibes, coverage %, or “property search found nothing.”  
Delete corners and epoch barriers are **hand-authored goldens**. Property tests under-sample them (lesson from 1.5 Rule T / R1′).

---

## 1. Three belts (always)

```text
1. LAW      — hand goldens (T1–T8, policy selection, epoch refuse, zombie suite)
2. ALGEBRA  — C/A/I · dual-impl / N-version differential when lattice re-opens
3. PRODUCT  — CLI authority · both roads · seal identity · Doc Gate on pub
```

| Belt | Blocks ship when red? |
|------|------------------------|
| LAW | **Yes** — always |
| ALGEBRA | **Yes** on any merge-law re-open (1.5 tombstones · 2.0 epoch); hold on additive cuts |
| PRODUCT | **Yes** for the surface you advertise (CLI, packet, namepoint) |

---

## 2. Kernel forever (every PR / every cut)

These stay green from **1.5 forward**. Additive editions (1.6, 1.7) do not reopen them; they **must not** turn them red.

| Law | Module (primary) | Meaning |
|-----|------------------|---------|
| T1–T8 tombstones | `tests/test_wjttc_tombstones.py` | No resurrection · re-etch · delete-wins · seal omit empty · C/A/I with deletes |
| Merge CRDT / goldens | `tests/test_wjttc_merge_*.py` | Field merge · Rule T · associativity |
| N-version differential | `tests/test_nversion_differential.py` + `reference_merge.py` | Second impl agrees — unqualified **CvRDT** bar |
| Packet = merge_souls | `tests/test_wjttc_packet*.py` | Seal carries graveyard; ingest joins same as hosted |
| Soul / interop / recall | soul · interop corpus · recall cross-impl | Format fidelity · rank SoT |

**North-star (every future cut, especially 2.0):**

> Lagging peer + pre-forget packet + post-compact soul  
> → forgotten stays forgotten **or** merge **explicitly refuses**  
> → never silent resurrection.

If that case is not a red-line golden, 2.0 is not shippable.

---

## 3. What / when by edition

### 1.5 Forgettable (shipped — hold)

| What | When |
|------|------|
| T1–T8 + dual-impl + both roads (packet + namepoint via `merge_souls`) | Hold forever |
| Seal identity: no-tombstone soul byte-class with ≤1.4 | Hold forever |

### 1.6 Policy → tombstone (current)

| What | When | Gate |
|------|------|------|
| Selection: id · id-less/`txt_hash` · tag · `priority_lte` · `max_age` | Before 1.6 pub | LAW |
| Apply requires non-empty `at=` (lib) | Before pub | LAW |
| Propose does not write; apply writes tombstones only | Before pub | LAW |
| T2 re-etch after policy forget | Before pub | LAW |
| Packet road: policy-emitted tombstones converge | Before pub | LAW |
| Empty `policies` omitted (seal identity) | Before pub | LAW |
| Policies first-class — not residual `memory_extra` | Before pub | LAW |
| CLI: `policy apply` without `--yes` fails; apply needs `--at` | Before pub | PRODUCT |
| Full kernel suite green | Every PR / pre-pub | LAW |
| Hosted path smoke (pull/sync still `merge_souls`) | Pre-pub if claiming both roads | PRODUCT |

Primary: `tests/test_wjttc_policies.py`.

### 1.7 Debt + residual (shipped in tree as 1.7.0)

| What | When | Gate |
|------|------|------|
| `debt()` counts match wire tombstones / bytes | Before 1.7 pub | LAW ✅ `test_wjttc_debt_residual.py` |
| Eligibility marks only — **never** auto-drops lattice | Before pub | LAW ✅ |
| View cache (if any): recall == lattice after etch/forget/merge | Before default-on | LAW · kill view if red · **deferred** (not in 1.7.0) |
| Residual scan finds fixture `.fafmp` + path copy | Before pub | PRODUCT ✅ |
| No “wiped worldwide” / RTBF language in tool output | Before pub | PRODUCT ✅ honesty note |
| Kernel T1–T8 + policies still green | Always | LAW |

**No** dual-impl extension required (no merge re-open).

### MCP side package (optional track)

| What | When |
|------|------|
| Tools call Soul API only — no reimplemented merge | Every MCP PR |
| `policy_propose` free; apply gated / two-step | Before “safe default” claim |
| Path sandbox; no full secret dump by default | Before publish |

**Does not gate** kernel 2.0.0. Lives in that package’s CI.

### 2.0.0 Compactable — epoch (second lattice re-open)

**Spec:** `MERGE.md` **§11 FROZEN** (2026-07-30) · INTEROP **§14** wire.  
**Laws:** Z1–Z8 in MERGE §11.8 — implement as `tests/test_wjttc_epoch.py` (name locked at impl).

| What | When | Gate |
|------|------|------|
| §11 prose frozen before code | **Done** | SPEC |
| `Soul.epoch` · `EpochMismatch` (E1) | Impl | LAW |
| `compact_epoch` + CompactionReceipt (E3–E4) | Impl | LAW |
| Archive-first CLI/API (Z7) | Impl | PRODUCT |
| **Zombie suite Z1–Z8** hand goldens | Before 2.0 claim | **SHIP BLOCKER** |
| · Z2 cross-epoch refuse | | no fact bleed |
| · Z3 packet pre-forget / post-epoch refuse | | never silent join |
| · Z4 compact projection + empty tombstones | | debt paid in lineage |
| · Z6 dual-transport same E1 | | |
| **Dual-impl / N-version** for epoch + E1 + compact | Before unqualified CvRDT | **SHIP BLOCKER** |
| T1–T8 green on **epoch-0** souls | Always | LAW |
| ≤1.7 residual-preserve `epoch` / receipts | Interop §14 | LAW |
| Claims: compact ≠ secure erase | Doc Gate | PRODUCT |

**Do not ship 2.0** if Z2, Z3, or dual-impl is red.

### 2.0.1+ Watermark

| What | When |
|------|------|
| Only drop tombstones dominated by frontier | With feature |
| No peer registry → watermark compact errors / illegal | With feature |
| Packet-only still epoch-only | Regression |
| Full zombie suite still green | Ship blocker |

### 2.1 Scale / binary

| What | When |
|------|------|
| Binary → YAML logical rebuild equal | With binary |
| Partial sync never drops required tombstones | With sync |
| Binary never sole SoT | Always |

### 2.x Multi-writer

Only if production concurrent re-etch races exist. No theater suite.

---

## 4. When to run what (ops)

| Moment | Command / suite |
|--------|------------------|
| **Every commit / PR** | Fast core: tombstones + merge_crdt + packet + policies (+ soul) |
| **Pre-pub any release** | Full `tests/` + version identity + Doc Gate |
| **Pre-pub 2.0 (big Release + blog)** | Full + **zombie suite** + **n-version** + epoch seal goldens |
| **After MERGE / INTEROP edit** | merge + tombstones + policies (if §13) + interop corpus |
| **Never skip** | T1–T8 when touching forget, merge, packet, compact, policy apply |
| **🚨 After every PyPI publish** | **Post-pub acid test** (§4.1) — **MANDATORY receipt** |

### 4.1 Post-pub acid test (norm after release)

**Doctrine:** CI green + upload 200 is not closed.  
A release is closed only when a **clean install from the live index** runs **real product commands** successfully.

> **It works! (and we know it.)**

Not the repo. Not editable. Not “version string only.” Soul · forget · policy · debt · **packet seal/open** · risk-scan · merge — the path a stranger hits.

```sh
# Same script; only --from changes (pre-pub vs post-pub)
bash scripts/post-pub-acid-test.sh 1.7.0 --from wheel      # pre-pub: build+install local wheel
bash scripts/post-pub-acid-test.sh 1.7.0 --from testpypi   # pre-pub staging
bash scripts/post-pub-acid-test.sh 1.7.0 --from pypi       # post-pub close (default)
# → ✅ ACID TEST PASS · It works! (and we know it.)
```

| Rule | |
|------|--|
| **Pre-pub** | `--from wheel` or `testpypi` — dry stranger; catch breaks before GO |
| **Post-pub** | `--from pypi` (default) — live stranger; **only this closes the release** |
| **Who** | Human or agent on `/pubpypi` pre-GO and Step 9 |
| **Fail** | Not done — fix / patch forward |
| **Pass** | The 1.7.0 feeling — that is the **norm** |

Also enforced in `~/.claude/skills/pubpypi/SKILL.md` Step 9.

Example fast core:

```sh
uv run --extra dev pytest \
  tests/test_wjttc_tombstones.py \
  tests/test_wjttc_merge_crdt.py \
  tests/test_wjttc_packet.py \
  tests/test_wjttc_policies.py \
  -q
```

Full:

```sh
uv run --extra dev pytest -q
```

---

## 5. What we refuse to call “tested”

| Trap | Why it fails the doctrine |
|------|---------------------------|
| Property-only forget / compact | Under-samples; users would see zombies we “didn’t find” |
| Coverage without goldens | Green bar, red product |
| Auto-apply as happy path | Breaks “explicit forget” — authority is product law |
| Shipping 2.0 without dual-impl | Demotes CvRDT claim; second reopen needs same bar as §9 |
| Silent grace GC “tests” that don’t include lagging packet | The exact failure users hit |
| Unbounded residual / RTBF theater tests | Wrong product; overclaim |

---

## 6. Kill criteria (tests force the call)

| Workstream | Stop when tests say |
|------------|---------------------|
| View cache | Any golden where recall ≠ lattice |
| Epoch compact | Any zombie golden red |
| Watermark | No membership model — illegal without peers |
| Policy | Selection requires LLM to be “correct” |
| Whole 2.0 | Barrier cost > benefit and debt stays negligible at personal scale — stay grow-only |

---

## 7. Trajectory checklist (copy into PR / release)

```text
[ ] Kernel T1–T8 + merge + packet green
[ ] N-version green (required if this cut reopened merge law)
[ ] Edition goldens green (policies / debt / zombie as applicable)
[ ] Both roads covered for any new forget path
[ ] Seal identity: empty optional keys omitted
[ ] CLI authority (propose vs apply) if surface shipped
[ ] Doc Gate / claims match tests (no secure-erase / no guaranteed)
[ ] User never has to discover the bug we already broke in CI
[ ] POST-PUB ACID PASS — clean PyPI install + real commands (scripts/post-pub-acid-test.sh)
    → "It works! (and we know it.)"
```

---

## 8. Document map

| File | Role |
|------|------|
| **TESTING.md** (this file) | What / when · ship gates · doctrine |
| `scripts/post-pub-acid-test.sh` | **Post-pub acid** — stranger install receipt |
| MERGE.md | Lattice law |
| INTEROP.md | Format + §12 tombstones + §13 policies |
| PACKET.md | Seal transport + tombstones on wire |
| CHANGELOG.md | Edition claims |
| tests/ | The red lines |

Private plan (vault): `PLANET-FAF/memory/plan-forgettable-memory-2-0.md`  
Plan close-out: `PLANET-FAF/memory/plan-closeout-forgettable-memory-2-0-2026-07-30.md`

---

*We break it here. They never know it was broken.*
