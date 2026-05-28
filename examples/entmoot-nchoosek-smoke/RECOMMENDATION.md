# ENTMOOT v2 Phase 2 BO Integration Recommendation

**Produced by:** ENTMOOT swap smoke, 2026-05-16  
**Smoke status:** SMOKE_PASSED (4/4 NChooseK cardinality respected; see `result.json`)

---

## What the smoke confirmed

ENTMOOT 2.1.1 (GBRT + Pyomo MILP via HiGHS) ran a 4-iteration BO loop on a
4-component NChooseK(1, 2) problem without stalling. All four recommended
candidates had exactly 2 active carbon sources. Median wall time per ask: ~2 s
on a laptop CPU (M-series, single-threaded).

This directly addresses the BoFire Phase 2 failure mode: `SoboStrategy` with
`NChooseK` in the BoFire Domain hits the `_sample_with_nchoosek` enumeration
path (issue #450) and stalls indefinitely on CPU. ENTMOOT encodes NChooseK as
a MILP cardinality constraint (`sum(b_i) ∈ [k_min, k_max]`) and the HiGHS
solver handles it in seconds.

---

## Integration footprint

| Component | Effort | Notes |
|---|---|---|
| `pip install entmoot highspy` | < 1 min | No Gurobi license needed; HiGHS is free |
| `adapters/entmoot_strategy.py` | ~150 lines | New adapter, mirrors `bofire_strategy.py` structure |
| `ProblemConfig` wiring | ~50 lines | Map campaign manifest factors[] to ENTMOOT real/binary features |
| Big-M linking + NChooseK constraints | ~30 lines | Pyomo `ConstraintList` + `nchoosek_lb/ub` |
| `PyomoOptimizer` monkey-patch | ~20 lines | Needed until ENTMOOT adds `solver_io=None` support for APPSI |
| Surrogate fit loop | ~20 lines | `enting.fit(X, y)` after each tell |
| Unit test | ~40 lines | Assert cardinality on all returned candidates |

**Total new code:** ~310 lines. No changes to existing campaign manifest schema.

---

## Recommendation: LATER (not now)

**Swap ENTMOOT in for Phase 2 BO: not yet. Do it when the integration design
doc lands alongside a validated adapter.**

### Why not now

1. **Phase 2 BO null result is documented but not blocking.** The Phase 1
   D-optimal design is the operational handoff; Phase 2 is experimental.
   Swapping the surrogate at this stage introduces risk without changing the
   handed-off design table.

2. **ENTMOOT still uses `SoboStrategy`-like GP internally.** The tree surrogate
   (GBRT) is new, but the cardinality fix is purely in the acquisition-function
   MIP encoding. The surrogate's quality on 16 observations is unvalidated for
   this specific domain.

3. **Monkey-patch required.** `PyomoOptimizer` hardcodes `solver_io="python"`
   which breaks APPSI/HiGHS. Until ENTMOOT exposes a clean `solver_factory_kwargs`
   param, the patch is fragile across ENTMOOT version upgrades.

4. **An integration design doc is the right home.** That doc is the
   canonical venue for deciding surrogate swap criteria, test coverage, and
   migration path.

### Why ENTMOOT is real signal (not noise)

- The cardinality encoding is genuinely superior to the post-hoc filter approach.
- Median 2 s per ask vs. potentially-infinite for SoboStrategy+NChooseK.
- HiGHS is production-grade (open-source, used in OR-Tools + scipy.optimize).
- The MILP formulation naturally admits cost-ceiling + total-carbon constraints
  as linear constraints alongside cardinality, with no separate filtering needed.

### Recommended path

| Step | Owner | Target |
|---|---|---|
| Integration design doc delivers ENTMOOT adapter spec | follow-on session | Before adapter work begins |
| Adapter coded + unit-tested | next campaign sprint | Before the next BO-driven campaign |
| Phase 2 re-run with ENTMOOT adapter | next BO-driven campaign | When results land |

**Bottom line:** ENTMOOT is the right tool for NChooseK BO. Swap in on the
next BO-driven campaign with a real adapter and test suite. Do not swap
ad-hoc on an already-sealed campaign.
