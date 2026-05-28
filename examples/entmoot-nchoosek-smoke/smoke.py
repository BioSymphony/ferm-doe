#!/usr/bin/env python3
"""
ENTMOOT v2 NChooseK smoke test
==============================
Confirms that ENTMOOT 2.x (GBRT + Pyomo/HiGHS MILP) handles a
4-component NChooseK(min=1, max=2) cardinality constraint without stalling.

Problem: 4 carbon sources (glucose, glycerol, lactose, sucrose) in g/L.
Objective: minimize synthetic cost function.
Constraints:
  - big-M linking: x_i <= x_max_i * b_i  (b_i binary activation indicator)
  - NChooseK: 1 <= sum(b_i) <= 2
  - cost ceiling: sum(cost_i * x_i) <= 1.20  ($/L)

This mirrors the cost-aware NChooseK BO constraint shape that causes
BoFire's SoboStrategy to stall indefinitely via upstream issue #450.

Expected outcomes:
  - Runs end-to-end without hanging (GBRT MILP solves in < 30 s)
  - All recommended candidates satisfy cardinality: 1 or 2 active carbons
  - Cost constraint satisfied for all candidates
"""

import json
import time
import sys

import numpy as np
import pyomo.environ as pyo

from entmoot import Enting, ProblemConfig, PyomoOptimizer

# ── Problem configuration ─────────────────────────────────────────────────────

problem_config = ProblemConfig(rnd_seed=42)

CARBONS = ["glucose", "glycerol", "lactose", "sucrose"]
CARBON_MAX = {"glucose": 40.0, "glycerol": 40.0, "lactose": 30.0, "sucrose": 30.0}
COST_PER_KG = {"glucose": 0.70, "glycerol": 1.70, "lactose": 0.90, "sucrose": 1.10}
COST_CEILING = 1.20  # $/L

# Continuous: carbon amounts (g/L) — indices 0..3
for c in CARBONS:
    problem_config.add_feature("real", (0.0, CARBON_MAX[c]), name=c)

# Binary: activation indicators — indices 4..7
for c in CARBONS:
    problem_config.add_feature("binary", name=f"b_{c}")

problem_config.add_min_objective()

# ── Synthetic objective function ─────────────────────────────────────────────

def synthetic_cost(X: np.ndarray) -> np.ndarray:
    """
    Synthetic objective: penalizes high-cost media and rewards
    single-carbon simplicity.
    Ground truth: glucose-only at ~10 g/L is near-optimal.
    """
    out = []
    for row in X:
        amounts = row[:4]
        active = row[4:]
        # Cost in $/L (g/L * $/kg / 1000 g/kg)
        media_cost = sum(
            amounts[i] * list(COST_PER_KG.values())[i] / 1000.0
            for i in range(4)
        )
        # Titer surrogate: proportional to active-weighted sum, diminishing returns
        titer_proxy = sum(
            amounts[i] * (0.8 if active[i] < 0.5 else 1.0)  # bonus for explicit activation
            for i in range(4)
        )
        # Objective to minimize: cost / (titer_proxy + 1) — cost-per-unit-titer
        obj = media_cost / (max(titer_proxy, 0.1) + 1e-3)
        out.append(obj)
    return np.array(out)


# ── Training data: random feasible samples ────────────────────────────────────
# We generate N_TRAIN samples that are cardinality-feasible (1-2 active carbons)
# so the GBRT learns from the feasible region.

N_TRAIN = 30
rng = np.random.default_rng(42)

X_train_rows = []
while len(X_train_rows) < N_TRAIN:
    # Choose 1 or 2 active carbons
    n_active = rng.integers(1, 3)  # 1 or 2
    active_idx = rng.choice(4, size=n_active, replace=False)
    amounts = np.zeros(4)
    for idx in active_idx:
        max_a = list(CARBON_MAX.values())[idx]
        amounts[idx] = rng.uniform(1.0, max_a)
    # Check cost constraint
    cost = sum(amounts[i] * list(COST_PER_KG.values())[i] / 1000.0 for i in range(4))
    if cost > COST_CEILING:
        continue
    # Binary activation
    binary = np.zeros(4)
    binary[active_idx] = 1.0
    X_train_rows.append(np.concatenate([amounts, binary]))

X_train = np.array(X_train_rows)
y_train = synthetic_cost(X_train).reshape(-1, 1)

print(f"Training data: {len(X_train)} samples, y range [{y_train.min():.4f}, {y_train.max():.4f}]")

# ── Build ENTMOOT model ───────────────────────────────────────────────────────

params = {"unc_params": {"dist_metric": "l1", "acq_sense": "exploration"}}
enting = Enting(problem_config, params=params)
enting.fit(X_train, y_train)

print("GBRT surrogate fitted.")

# ── Pyomo model core with NChooseK + linking constraints ──────────────────────

def build_constrained_model_core(problem_config: ProblemConfig) -> pyo.ConcreteModel:
    """
    Build base model core and add:
      1. Big-M linking: x_i <= max_i * b_i  (b_i at index 4+i)
      2. NChooseK cardinality: 1 <= sum(b_i) <= 2
      3. Cost ceiling: sum(cost_i * x_i) <= COST_CEILING
    """
    model_core = problem_config.get_pyomo_model_core()

    # All-features list: indices 0..3 = continuous, 4..7 = binary
    # _all_feat[i] is the Pyomo variable for feature i
    feats = model_core._all_feat  # list of Pyomo vars

    carbon_maxes = list(CARBON_MAX.values())
    carbon_costs = [v / 1000.0 for v in COST_PER_KG.values()]  # $/g * g/L = $/L per g/L unit

    # 1. Big-M linking constraints
    model_core.bigm_linking = pyo.ConstraintList()
    for i in range(4):
        # x_i <= carbon_max_i * b_{i+4}
        model_core.bigm_linking.add(feats[i] <= carbon_maxes[i] * feats[i + 4])

    # 2. NChooseK: 1 <= b_0 + b_1 + b_2 + b_3 <= 2
    binary_sum = sum(feats[i + 4] for i in range(4))
    model_core.nchoosek_lb = pyo.Constraint(expr=binary_sum >= 1)
    model_core.nchoosek_ub = pyo.Constraint(expr=binary_sum <= 2)

    # 3. Cost ceiling
    media_cost_expr = sum(carbon_costs[i] * feats[i] for i in range(4))
    model_core.cost_ceiling = pyo.Constraint(expr=media_cost_expr <= COST_CEILING)

    return model_core


model_core = build_constrained_model_core(problem_config)
print("Custom Pyomo model core built (NChooseK + big-M + cost ceiling).")

# ── Run BO loop ───────────────────────────────────────────────────────────────

params_pyo = {
    "solver_name": "appsi_highs",
    "verbose": False,
}

# Monkey-patch PyomoOptimizer.solve to use appsi_highs without solver_io kwarg
# (ENTMOOT's default params pass solver_io="python" which appsi_highs doesn't accept)
import pyomo.environ as _pyo
import warnings as _warnings
from entmoot.utils import OptResult as _OptResult

_orig_solve = PyomoOptimizer.solve

def _patched_solve(self, tree_model, model_core=None, weights=None):
    if model_core is None:
        opt_model = self._problem_config.get_pyomo_model_core()
    else:
        opt_model = self._problem_config.copy_pyomo_model_core(model_core)

    opt = _pyo.SolverFactory("appsi_highs")
    tree_model.add_to_pyomo_model(opt_model)

    verbose = self._params.get("verbose", False)
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore")
        opt.solve(opt_model, tee=verbose)

    self._curr_sol, self._active_leaves = self._get_sol(opt_model)
    return _OptResult(
        self.get_curr_sol,
        _pyo.value(opt_model.obj),
        [opt_model._unscaled_mu[k].value for k in opt_model._unscaled_mu],
        _pyo.value(opt_model._unc),
        self._active_leaves,
    )

PyomoOptimizer.solve = _patched_solve

opt_pyo = PyomoOptimizer(problem_config, params=params_pyo)

N_BO_ITERS = 4
candidates = []
violations = []

print(f"\nRunning {N_BO_ITERS} BO asks with NChooseK(1, 2) enforcement...\n")

for iteration in range(N_BO_ITERS):
    t0 = time.time()

    # Get a fresh copy of the model core (solve() copies internally too)
    result = opt_pyo.solve(enting, model_core=model_core)
    elapsed = time.time() - t0

    candidate = result.opt_point
    candidate_arr = np.array(candidate)
    amounts = candidate_arr[:4]
    binary = candidate_arr[4:]

    n_active = int(round(sum(binary)))
    cost = sum(amounts[i] * list(COST_PER_KG.values())[i] / 1000.0 for i in range(4))
    cardinality_ok = 1 <= n_active <= 2
    cost_ok = cost <= COST_CEILING + 1e-6
    active_carbons = [CARBONS[i] for i in range(4) if binary[i] > 0.5]

    status = "✓" if (cardinality_ok and cost_ok) else "✗"
    print(
        f"  Iter {iteration+1}: {status} "
        f"n_active={n_active} [{', '.join(active_carbons)}] "
        f"cost=${cost:.4f}/L "
        f"obj={result.opt_val:.4f} "
        f"({elapsed:.1f}s)"
    )

    if not cardinality_ok:
        violations.append({"iteration": iteration + 1, "n_active": n_active, "type": "cardinality"})
    if not cost_ok:
        violations.append({"iteration": iteration + 1, "cost": cost, "type": "cost_ceiling"})

    candidates.append({
        "iteration": iteration + 1,
        "amounts": dict(zip(CARBONS, [float(v) for v in amounts])),
        "binary": dict(zip(CARBONS, [float(v) for v in binary])),
        "n_active": int(n_active),
        "active_carbons": active_carbons,
        "cost_per_L": round(float(cost), 4),
        "cardinality_ok": bool(cardinality_ok),
        "cost_ok": bool(cost_ok),
        "obj": float(result.opt_val),
        "elapsed_s": round(elapsed, 2),
    })

    # Tell ENTMOOT about this candidate (synthetic observation)
    obs_y = synthetic_cost(candidate_arr.reshape(1, -1)).reshape(1, 1)
    X_train = np.vstack([X_train, candidate_arr])
    y_train = np.vstack([y_train, obs_y])
    enting.fit(X_train, y_train)

# ── Summary ───────────────────────────────────────────────────────────────────

print()
cardinality_pass_count = sum(1 for c in candidates if c["cardinality_ok"])
cost_pass_count = sum(1 for c in candidates if c["cost_ok"])

print(f"=== ENTMOOT v2 NChooseK Smoke Summary ===")
print(f"  ENTMOOT version:       2.1.1 (PyPI)")
print(f"  Solver:                HiGHS (via highspy)")
print(f"  BO iterations:         {N_BO_ITERS}")
print(f"  Cardinality pass:      {cardinality_pass_count}/{N_BO_ITERS}")
print(f"  Cost-ceiling pass:     {cost_pass_count}/{N_BO_ITERS}")
print(f"  Constraint violations: {len(violations)}")

if len(violations) == 0 and cardinality_pass_count == N_BO_ITERS:
    verdict = "SMOKE_PASSED"
    print(f"\nVerdict: {verdict}")
    print("  All candidates have 1-2 active carbons. NChooseK encoding works end-to-end.")
else:
    verdict = "SMOKE_FAILED"
    print(f"\nVerdict: {verdict}")
    for v in violations:
        print(f"  Violation: {v}")

# Write JSON report
report = {
    "smoke_id": "entmoot-v2-nchoosek-smoke",
    "entmoot_version": "2.1.1",
    "solver": "highs",
    "n_bo_iters": N_BO_ITERS,
    "n_components": 4,
    "nchoosek_min": 1,
    "nchoosek_max": 2,
    "cost_ceiling_usd_per_L": COST_CEILING,
    "cardinality_pass_count": cardinality_pass_count,
    "cost_pass_count": cost_pass_count,
    "constraint_violations": violations,
    "verdict": verdict,
    "candidates": candidates,
}

out_path = "/tmp/entmoot_nchoosek_smoke_report.json"
with open(out_path, "w") as f:
    json.dump(report, f, indent=2)

print(f"\nReport written to {out_path}")
sys.exit(0 if verdict == "SMOKE_PASSED" else 1)
