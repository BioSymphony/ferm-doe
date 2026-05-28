"""DoE family recommender — decision tree over factors / goals / priors.

Public API: :func:`recommend_family`.

Reads the campaign manifest's factors, profiles, and (optionally) operator-
declared priors, and returns a ranked list of family candidates with stated
reasons and expected run counts. The recommender is *advice*, not gating —
the agent and the operator make the final call.

The decision tree treats three canonical paths as exclusive:

1. **Mixture path.** When any factor has ``type: mixture``, recommend
   ``scheffe_mixture`` for the unconstrained simplex and
   ``extreme_vertices_mixture`` when any component carries non-trivial
   bounds (low > 0 or high < total). Mixture and non-mixture designs do
   not share a generator.

2. **Split-plot path.** When any factor carries ``hard_to_change: true``,
   recommend ``split_plot`` regardless of other priors — the run order
   constraint dominates the choice.

3. **Main path.** Otherwise, branch on goal × n_factors × curvature_prior
   × interactions_prior × budget:

   - Screening + suspected curvature, k in {4..6} → ``definitive_screening``
   - Screening + many factors (k >= 8) → ``plackett_burman``
   - Screening + interactions of interest, 4 <= k <= 7 → ``fractional_factorial``
   - Small k (<= 3) → ``full_factorial``
   - Optimization, k <= 5 → ``central_composite`` (alt: ``box_behnken``)
   - Optimization, k > 5 → ``optimal_d``
   - Scale-bridge → ``confirmation`` plus ``sequential_augmentation``

Output is labeled ``claim_level: family_recommendation_planning``. The
recommender does not generate any design; it just labels the choice. After
the operator picks, ``ferm-doe generate-design`` produces the runnable rows.
"""

from __future__ import annotations

from typing import Any

CLAIM_LEVEL = "family_recommendation_planning"
NON_CLAIM = (
    "Family recommendation is decision-tree guidance, not a statistical "
    "claim. Confirm the choice with a statistician and align with the "
    "campaign's run budget, factor priors, and analysis goals before "
    "locking the design."
)

VALID_PRIORS = frozenset({"yes", "no", "unknown"})


def recommend_family(
    manifest: dict[str, Any],
    *,
    budget: int | None = None,
    curvature_prior: str = "unknown",
    interactions_prior: str = "unknown",
) -> dict[str, Any]:
    """Recommend a DoE family from manifest factors + profiles + priors.

    ``budget`` is an optional cap on total runs. ``curvature_prior`` and
    ``interactions_prior`` are operator hints — values: ``yes`` | ``no`` |
    ``unknown``. Returns a dict with the recommended family, ranked
    alternatives, the inputs that drove the decision, and an explanation
    trail the agent can record in ``assumptions[]``.
    """
    if curvature_prior not in VALID_PRIORS:
        curvature_prior = "unknown"
    if interactions_prior not in VALID_PRIORS:
        interactions_prior = "unknown"

    factors = manifest.get("factors") or []
    profiles = manifest.get("profiles") or []

    summary = _summarize_factors(factors)
    goal = _classify_goal(profiles)

    candidates: list[dict[str, Any]] = []
    decision_path: list[str] = []

    if summary["n_mixture"] > 0:
        decision_path.append("mixture_factors_present")
        constrained = any(_is_constrained_mixture(f) for f in factors if f.get("type") == "mixture")
        if constrained:
            decision_path.append("constrained_components_detected")
            candidates.append(_candidate("extreme_vertices_mixture", "constrained mixture components require enumeration of feasible vertices", "varies_with_constraints"))
            candidates.append(_candidate("scheffe_mixture", "alternative if you relax component bounds to the full simplex", _scheffe_runs(summary["n_mixture"])))
        else:
            decision_path.append("unconstrained_simplex")
            candidates.append(_candidate("scheffe_mixture", "unconstrained simplex; simplex-centroid covers all blends evenly", _scheffe_runs(summary["n_mixture"])))
            candidates.append(_candidate("extreme_vertices_mixture", "alternative if you later add component bounds", "varies_with_constraints"))
    elif summary["n_hard_to_change"] > 0:
        decision_path.append("hard_to_change_factors_present")
        candidates.append(_candidate("split_plot", "run order constraint dominates the family choice; whole-plot replication preserves error structure", "depends_on_whole_plot_count"))
    else:
        n_total = summary["n_total"]
        decision_path.append(f"goal={goal}")
        decision_path.append(f"k={n_total}")
        if goal == "scale_bridge":
            candidates.append(_candidate("confirmation", "fixed-setpoint qualification of the bridged scale", "operator_specified"))
            candidates.append(_candidate("sequential_augmentation", "extend a prior wave's design with a small bridge cohort", "operator_specified"))
        elif goal == "optimization":
            if n_total <= 5:
                ccd_runs = (2 ** n_total) + (2 * n_total) + max(3, n_total)
                candidates.append(_candidate("central_composite", f"RSM with curvature, k <= 5; face-centered keeps points in declared range", f"~{ccd_runs}"))
                if n_total in {3, 4}:
                    bb_runs = 12 if n_total == 3 else 24
                    bb_runs += max(3, n_total)
                    candidates.append(_candidate("box_behnken", "alternative when corner points are infeasible (extreme combos off-limits)", f"~{bb_runs}"))
            else:
                candidates.append(_candidate("optimal_d", f"RSM with k > 5; coordinate-exchange D-optimal labeled heuristic", "operator_specified"))
                candidates.append(_candidate("optimal_i", "alternative if prediction variance over the region matters more than coefficient variance", "operator_specified"))
        else:  # screening (default)
            if n_total <= 3:
                candidates.append(_candidate("full_factorial", "small k; full coverage feasible and supports all interactions", f"{2 ** n_total}"))
                if n_total == 3 and curvature_prior == "yes":
                    candidates.append(_candidate("definitive_screening", "alternative if curvature is suspected at k=3", "13"))
            elif curvature_prior == "yes" and 4 <= n_total <= 6:
                runs = 2 * n_total + 1 if n_total % 2 == 0 else 2 * (n_total + 1) + 1
                candidates.append(_candidate("definitive_screening", f"screening with suspected curvature, k in {{4..6}}", f"{runs}"))
                candidates.append(_candidate("plackett_burman", "alternative if curvature is later ruled out", f"{_pb_runs(n_total)}"))
            elif n_total >= 8:
                candidates.append(_candidate("plackett_burman", "many factors, main effects only — smallest run count for resolution III", f"{_pb_runs(n_total)}"))
                candidates.append(_candidate("fractional_factorial", "alternative if interactions matter and you can afford more runs", "2^(k-p)_per_resolution"))
            elif interactions_prior == "yes" and 4 <= n_total <= 7:
                candidates.append(_candidate("fractional_factorial", f"moderate k with interactions of interest; pick resolution IV+ to keep main effects clear", "2^(k-p)_per_resolution"))
                candidates.append(_candidate("plackett_burman", "alternative if main effects only", f"{_pb_runs(n_total)}"))
            else:
                candidates.append(_candidate("plackett_burman", "default screening for moderate k with main effects only", f"{_pb_runs(n_total)}"))
                candidates.append(_candidate("definitive_screening", "alternative if curvature might matter and you can afford 2k+1 runs", f"{(2 * n_total + 1) if n_total % 2 == 0 else (2 * (n_total + 1) + 1)}"))

    if budget is not None:
        decision_path.append(f"budget_cap={budget}")
        candidates = _filter_by_budget(candidates, budget, decision_path)

    recommended = candidates[0]["family"] if candidates else None
    return {
        "claim_level": CLAIM_LEVEL,
        "non_claim": NON_CLAIM,
        "recommended_family": recommended,
        "candidates": candidates,
        "factor_summary": summary,
        "goal": goal,
        "curvature_prior": curvature_prior,
        "interactions_prior": interactions_prior,
        "budget": budget,
        "decision_path": decision_path,
    }


# =====================================================================
# Helpers
# =====================================================================


def _summarize_factors(factors: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        "n_numeric": 0,
        "n_categorical": 0,
        "n_ordinal": 0,
        "n_mixture": 0,
        "n_temporal_profile": 0,
        "n_block": 0,
        "n_hard_constraint": 0,
        "n_hard_to_change": 0,
    }
    for factor in factors:
        ftype = factor.get("type", "numeric")
        if ftype == "numeric":
            counts["n_numeric"] += 1
        elif ftype == "categorical":
            counts["n_categorical"] += 1
        elif ftype == "ordinal":
            counts["n_ordinal"] += 1
        elif ftype == "mixture":
            counts["n_mixture"] += 1
        elif ftype == "temporal_profile":
            counts["n_temporal_profile"] += 1
        elif ftype == "block":
            counts["n_block"] += 1
        elif ftype == "hard_constraint":
            counts["n_hard_constraint"] += 1
        if factor.get("hard_to_change"):
            counts["n_hard_to_change"] += 1
    counts["n_total"] = counts["n_numeric"] + counts["n_categorical"] + counts["n_ordinal"]
    return counts


def _classify_goal(profiles: list[str]) -> str:
    """Map declared profiles to a coarse goal label."""
    if not profiles:
        return "screening"
    profiles_lower = {p.lower() for p in profiles}
    if profiles_lower & {"scale_up_bridge", "scale_down_qualification"}:
        return "scale_bridge"
    if profiles_lower & {"optimization_rsm", "confirmation"}:
        return "optimization"
    if profiles_lower & {"split_plot_fed_batch"}:
        return "split_plot"
    if profiles_lower & {"mixture"}:
        return "mixture"
    return "screening"


def _is_constrained_mixture(factor: dict[str, Any]) -> bool:
    low = factor.get("low")
    high = factor.get("high")
    try:
        low_v = float(low) if low is not None else None
        high_v = float(high) if high is not None else None
    except (TypeError, ValueError):
        return False
    return (low_v is not None and low_v > 0) or (high_v is not None and high_v < 1.0)


def _candidate(family: str, reason: str, expected_runs: str | int) -> dict[str, Any]:
    entry: dict[str, Any] = {"family": family, "reason": reason, "expected_runs": expected_runs}
    from .adapters import nist_citations

    reference = nist_citations.lookup(family)
    if reference is not None:
        entry["reference"] = reference
    return entry


def _pb_runs(k: int) -> int:
    n = 4
    while n - 1 < k:
        n += 4
    return n


def _scheffe_runs(q: int) -> str:
    if q < 1:
        return "operator_specified"
    centroid = (1 << q) - 1  # 2^q - 1
    return f"{centroid}_simplex_centroid"


def _filter_by_budget(
    candidates: list[dict[str, Any]], budget: int, decision_path: list[str]
) -> list[dict[str, Any]]:
    """Drop candidates whose expected_runs (when an integer string) exceed the budget."""
    fits: list[dict[str, Any]] = []
    drops: list[str] = []
    for candidate in candidates:
        runs = candidate["expected_runs"]
        runs_int = _coerce_int(runs)
        if runs_int is not None and runs_int > budget:
            drops.append(f"{candidate['family']}_drops_at_{runs_int}_runs")
            continue
        fits.append(candidate)
    if drops:
        decision_path.append("budget_drops=" + ",".join(drops))
    return fits or candidates  # never return empty; if budget kills all, keep originals with the warning recorded


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    stripped = value.strip().lstrip("~")
    if stripped.isdigit():
        return int(stripped)
    return None


__all__ = ["recommend_family", "CLAIM_LEVEL", "NON_CLAIM"]
