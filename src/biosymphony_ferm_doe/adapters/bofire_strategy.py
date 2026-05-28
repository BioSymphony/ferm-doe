"""BoFire routed adapter for constrained and structured sequential planning.

The module stays importable without BoFire installed. That is deliberate:
BioSymphony can explain when a campaign would benefit from BoFire while
falling back to deterministic local planning unless the optional dependency
is present.
"""

from __future__ import annotations

import importlib.util
from typing import Any

from ..constraints import design_factors
from ..io_utils import parse_number


CLAIM_LEVEL = "bofire_adapter_planning"
BOFIRE_ROUTE_REASONS = (
    "non_box_constraints",
    "multi_objective_responses",
    "scale_fidelity_structure",
    "operator_requested_bofire",
)
NON_CLAIM = (
    "BoFire-backed candidates are planned model-based suggestions. They do "
    "not validate assay readiness, scale transfer, or physical execution; "
    "BioSymphony readiness gates and dossier checks remain authoritative."
)


def is_available() -> bool:
    return importlib.util.find_spec("bofire") is not None


def routing_decision(
    state: dict[str, Any],
    usable_rows: list[dict[str, Any]] | None = None,
    *,
    backend: str | None = None,
) -> dict[str, Any]:
    """Return whether this campaign should try the BoFire adapter."""

    requested = str(backend or "auto").lower()
    hard_off = requested in {"stdlib", "numpy", "scipy", "pydoe", "pydoe3", "botorch"}
    reasons: list[str] = []
    if requested == "bofire":
        reasons.append(BOFIRE_ROUTE_REASONS[3])
    if _has_executable_non_box_constraint(state):
        reasons.append(BOFIRE_ROUTE_REASONS[0])
    if _has_multi_objective_responses(state):
        reasons.append(BOFIRE_ROUTE_REASONS[1])
    if _has_scale_fidelity_structure(state, usable_rows or []):
        reasons.append(BOFIRE_ROUTE_REASONS[2])

    return {
        "schema_version": 1,
        "route_kind": "bofire_adapter_route",
        "backend_requested": requested,
        "should_route": bool(reasons) and not hard_off,
        "adapter_available": is_available(),
        "reasons": reasons,
        "strategy_kind": _strategy_kind(reasons),
        "fallback": "stdlib_augment_design" if not is_available() else "",
    }


def plan_bofire_wave2(
    state: dict[str, Any],
    usable_rows: list[dict[str, Any]],
    *,
    remaining_budget: int | None = None,
    backend: str | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """Plan sequential candidates with BoFire when installed, else emit route report."""

    route = routing_decision(state, usable_rows, backend=backend)
    domain_spec = build_domain_spec(state)
    budget = int(remaining_budget or _policy(state).get("augment_remaining_budget") or max(1, min(8, len(domain_spec["inputs"]) + 2)))

    report: dict[str, Any] = {
        "schema_version": 1,
        "adapter_kind": "bofire_strategy",
        "claim_level": CLAIM_LEVEL,
        "non_claim": NON_CLAIM,
        "campaign_id": state.get("campaign_id"),
        "route": route,
        "strategy_kind": route["strategy_kind"],
        "remaining_run_budget": budget,
        "domain_spec": domain_spec,
        "candidate_design": [],
        "candidate_design_count": 0,
        "adapter_status": "not_routed" if not route["should_route"] else "not_available",
        "issues": [],
    }
    if not route["should_route"]:
        report["issues"].append("BoFire routing rule did not fire for this campaign.")
        return report
    if not route["adapter_available"]:
        report["issues"].append("BoFire is not installed; stdlib augment-design fallback remains authoritative.")
        return report
    if domain_spec["unsupported_constraints"]:
        report["adapter_status"] = "translation_blocked"
        report["issues"].append(
            "BoFire route fired, but this adapter cannot yet translate every declared constraint; "
            "stdlib fallback remains authoritative."
        )
        return report

    try:
        candidates = _execute_bofire(state, usable_rows, domain_spec, budget, route["strategy_kind"], seed)
    except Exception as exc:  # pragma: no cover - only exercised with optional dependency installed
        report["adapter_status"] = "execution_failed"
        report["issues"].append(f"BoFire execution failed; stdlib fallback required: {type(exc).__name__}: {exc}")
        return report

    report["adapter_status"] = "executed"
    report["candidate_design"] = candidates
    report["candidate_design_count"] = len(candidates)
    if route["strategy_kind"] == "multi_fidelity" and budget > 1 and len(candidates) < budget:
        report["issues"].append("BoFire MultiFidelityStrategy is sequential in the inspected API; emitted the next candidate only.")
    if not candidates:
        report["issues"].append("BoFire executed but returned no candidate rows; stdlib fallback required.")
    return report


def build_domain_spec(state: dict[str, Any]) -> dict[str, Any]:
    factors = design_factors(state.get("factors", []))
    return {
        "inputs": [_factor_spec(factor) for factor in factors],
        "outputs": [_response_spec(response) for response in _objective_responses(state)],
        "constraints": _constraint_specs(state.get("constraints", [])),
        "fidelity": _fidelity_spec(state),
        "unsupported_constraints": _unsupported_constraint_ids(state.get("constraints", [])),
    }


def _execute_bofire(
    state: dict[str, Any],
    usable_rows: list[dict[str, Any]],
    domain_spec: dict[str, Any],
    budget: int,
    strategy_kind: str,
    seed: int,
) -> list[dict[str, Any]]:
    # Lazy imports keep the base engine dependency-free.
    import pandas as pd
    from bofire.data_models.acquisition_functions.api import qLogNEHVI
    from bofire.data_models.domain.api import Domain
    from bofire.data_models.strategies.api import DOptimalityCriterion
    from bofire.strategies.api import DoEStrategy, MoboStrategy, MultiFidelityStrategy, SoboStrategy

    domain = Domain.from_lists(
        inputs=_bofire_inputs(domain_spec),
        outputs=_bofire_outputs(domain_spec),
        constraints=_bofire_constraints(domain_spec),
    )
    if strategy_kind == "multi_fidelity":
        strategy = MultiFidelityStrategy.make(domain=domain, seed=seed)
    elif strategy_kind == "multi_objective":
        strategy = MoboStrategy.make(domain=domain, acquisition_function=qLogNEHVI(), seed=seed)
    elif usable_rows and len(_objective_responses(state)) == 1:
        strategy = SoboStrategy.make(domain=domain, seed=seed)
    else:
        strategy = DoEStrategy.make(domain=domain, criterion=DOptimalityCriterion(formula="linear"), seed=seed)

    experiments = _experiments_dataframe(state, usable_rows, domain_spec)
    if len(experiments) and strategy_kind != "constrained_doe":
        strategy.tell(experiments=experiments, replace=True)
    ask_count = 1 if strategy_kind == "multi_fidelity" else max(1, budget)
    asked = strategy.ask(candidate_count=ask_count, raise_validation_error=False)
    assert isinstance(asked, pd.DataFrame)
    return _candidate_rows_from_dataframe(asked, state)


def _bofire_inputs(domain_spec: dict[str, Any]) -> list[Any]:
    from bofire.data_models.features.api import CategoricalInput, ContinuousInput, DiscreteInput, TaskInput

    inputs = []
    for spec in _all_input_specs(domain_spec):
        if spec["type"] == "continuous":
            inputs.append(ContinuousInput(key=spec["key"], bounds=[spec["low"], spec["high"]], allow_zero=spec.get("allow_zero", False)))
        elif spec["type"] == "discrete":
            inputs.append(DiscreteInput(key=spec["key"], values=spec["values"]))
        elif spec["type"] == "task":
            inputs.append(TaskInput(key=spec["key"], categories=spec["categories"], fidelities=spec["fidelities"]))
        elif spec["type"] == "categorical":
            inputs.append(CategoricalInput(key=spec["key"], categories=spec["categories"]))
    return inputs


def _bofire_outputs(domain_spec: dict[str, Any]) -> list[Any]:
    from bofire.data_models.features.api import ContinuousOutput
    from bofire.data_models.objectives.api import MaximizeObjective, MinimizeObjective

    outputs = []
    for spec in domain_spec["outputs"]:
        objective = MinimizeObjective(w=1.0) if spec["direction"] == "minimize" else MaximizeObjective(w=1.0)
        outputs.append(ContinuousOutput(key=spec["key"], unit=spec.get("unit") or None, objective=objective))
    return outputs


def _bofire_constraints(domain_spec: dict[str, Any]) -> list[Any]:
    from bofire.data_models.constraints.api import (
        LinearEqualityConstraint,
        LinearInequalityConstraint,
        NChooseKConstraint,
    )

    constraints = []
    for spec in domain_spec["constraints"]:
        if spec["type"] == "linear":
            if spec["operator"] in {">=", ">"}:
                constraints.append(LinearInequalityConstraint.from_greater_equal(spec["features"], spec["coefficients"], spec["rhs"]))
            elif spec["operator"] in {"==", "="}:
                constraints.append(LinearEqualityConstraint(features=spec["features"], coefficients=spec["coefficients"], rhs=spec["rhs"]))
            else:
                constraints.append(LinearInequalityConstraint.from_smaller_equal(spec["features"], spec["coefficients"], spec["rhs"]))
        elif spec["type"] == "nchoosek":
            constraints.append(
                NChooseKConstraint(
                    features=spec["features"],
                    min_count=spec.get("min_count", 0),
                    max_count=spec["max_count"],
                    none_also_valid=spec.get("none_also_valid", True),
                )
            )
    return constraints


def _experiments_dataframe(
    state: dict[str, Any],
    usable_rows: list[dict[str, Any]],
    domain_spec: dict[str, Any],
) -> Any:
    import pandas as pd

    input_keys = [item["key"] for item in _all_input_specs(domain_spec)]
    output_keys = [item["key"] for item in domain_spec["outputs"]]
    records = []
    for row in usable_rows:
        record: dict[str, Any] = {}
        ok = True
        for key in input_keys:
            if key == "scale_fidelity":
                record[key] = str(row.get("arm_id") or row.get("scale_fidelity") or _target_fidelity_category(state))
                continue
            if key not in row:
                ok = False
                break
            record[key] = row.get(key)
        for key in output_keys:
            value = parse_number(row.get(key))
            if value is None:
                ok = False
                break
            record[key] = value
            record[f"valid_{key}"] = True
        if ok:
            records.append(record)
    return pd.DataFrame(records)


def _candidate_rows_from_dataframe(frame: Any, state: dict[str, Any]) -> list[dict[str, Any]]:
    factors = design_factors(state.get("factors", []))
    factor_ids = [factor["factor_id"] for factor in factors if factor.get("factor_id")]
    rows = []
    for index, raw in frame.reset_index(drop=True).iterrows():
        row = {
            "run_id": f"BOFIRE-{index + 1:03d}",
            "claim_level": CLAIM_LEVEL,
            "scoring_mode": "bofire_strategy",
        }
        for factor_id in factor_ids:
            if factor_id in raw:
                row[factor_id] = raw[factor_id]
        if "scale_fidelity" in raw:
            row["arm_id"] = raw["scale_fidelity"]
        rows.append(row)
    return rows


def _all_input_specs(domain_spec: dict[str, Any]) -> list[dict[str, Any]]:
    specs = list(domain_spec["inputs"])
    fidelity = domain_spec.get("fidelity")
    if isinstance(fidelity, dict) and fidelity:
        specs.append(fidelity)
    return specs


def _factor_spec(factor: dict[str, Any]) -> dict[str, Any]:
    key = str(factor.get("factor_id") or "")
    factor_type = str(factor.get("type") or "continuous").lower()
    levels = factor.get("levels") if isinstance(factor.get("levels"), list) else []
    low = parse_number(factor.get("min", factor.get("low")))
    high = parse_number(factor.get("max", factor.get("high")))
    if factor_type in {"categorical", "block", "hard_to_change"} and levels:
        return {"key": key, "type": "categorical", "categories": [str(item) for item in levels]}
    if factor_type in {"ordinal", "discrete"} and levels:
        numeric_levels = [parse_number(level) for level in levels]
        if all(level is not None for level in numeric_levels):
            return {"key": key, "type": "discrete", "values": [float(level) for level in numeric_levels if level is not None]}
        return {"key": key, "type": "categorical", "categories": [str(item) for item in levels]}
    if low is None or high is None or low == high:
        return {"key": key, "type": "categorical", "categories": [str(factor.get("fixed_value", "fixed"))]}
    return {
        "key": key,
        "type": "continuous",
        "low": float(low),
        "high": float(high),
        "allow_zero": bool(factor.get("allow_zero") or factor_type == "mixture"),
    }


def _response_spec(response: dict[str, Any]) -> dict[str, Any]:
    direction = str(response.get("direction") or "maximize").lower()
    if direction not in {"maximize", "minimize"}:
        direction = "maximize"
    return {"key": str(response.get("response_id") or ""), "direction": direction, "unit": response.get("unit", "")}


def _constraint_specs(constraints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs = []
    for constraint in constraints:
        kind = _constraint_kind(constraint)
        if kind == "linear":
            coeffs = constraint.get("coefficients")
            rhs = parse_number(constraint.get("rhs"))
            if isinstance(coeffs, dict) and rhs is not None:
                features = [str(key) for key in coeffs]
                values = [float(parse_number(coeffs[key]) or 0.0) for key in coeffs]
                specs.append({"id": _constraint_id(constraint), "type": "linear", "features": features, "coefficients": values, "rhs": float(rhs), "operator": str(constraint.get("operator") or constraint.get("op") or "<=")})
        elif kind == "nchoosek":
            features = constraint.get("features")
            max_count = parse_number(constraint.get("max_count"))
            if isinstance(features, list) and max_count is not None:
                specs.append(
                    {
                        "id": _constraint_id(constraint),
                        "type": "nchoosek",
                        "features": [str(item) for item in features],
                        "min_count": int(parse_number(constraint.get("min_count")) or 0),
                        "max_count": int(max_count),
                        "none_also_valid": bool(constraint.get("none_also_valid", True)),
                    }
                )
        elif kind == "conditional":
            linearized = _conditional_linear_spec(constraint)
            if linearized is not None:
                specs.append(linearized)
    return specs


def _fidelity_spec(state: dict[str, Any]) -> dict[str, Any]:
    scale_context = state.get("scale_context") if isinstance(state.get("scale_context"), dict) else {}
    arms = state.get("campaign_arms") if isinstance(state.get("campaign_arms"), list) else []
    if not arms and isinstance(state.get("arms"), list):
        arms = state["arms"]
    categories = []
    for arm in arms:
        if isinstance(arm, dict):
            categories.append(str(arm.get("arm_id") or arm.get("id") or arm.get("name") or ""))
    categories = [item for item in categories if item]
    if not categories and scale_context:
        from_scale = scale_context.get("from_scale")
        to_scale = scale_context.get("to_scale")
        for item in [from_scale, to_scale]:
            if isinstance(item, dict):
                categories.append(str(item.get("scale_id") or item.get("name") or item.get("vessel") or "scale"))
            elif item:
                categories.append(str(item))
    if not categories:
        return {}
    fidelities = list(reversed(range(len(categories))))
    target = _target_fidelity_category(state, categories)
    if target in categories:
        target_index = categories.index(target)
        fidelities[target_index] = 0
        next_level = 1
        for index in range(len(fidelities)):
            if index != target_index:
                fidelities[index] = next_level
                next_level += 1
    return {"key": "scale_fidelity", "type": "task", "categories": categories, "fidelities": fidelities}


def _target_fidelity_category(state: dict[str, Any], categories: list[str] | None = None) -> str:
    scale_context = state.get("scale_context") if isinstance(state.get("scale_context"), dict) else {}
    raw = scale_context.get("to_scale")
    if isinstance(raw, dict):
        return str(raw.get("scale_id") or raw.get("name") or raw.get("vessel") or "")
    if raw:
        return str(raw)
    return categories[-1] if categories else ""


def _objective_responses(state: dict[str, Any]) -> list[dict[str, Any]]:
    responses = []
    for response in state.get("responses", []) or []:
        if not isinstance(response, dict):
            continue
        if str(response.get("direction") or "").lower() in {"maximize", "minimize"}:
            responses.append(response)
    if responses:
        return responses
    objective = state.get("objective") if isinstance(state.get("objective"), dict) else {}
    response_id = objective.get("response_id")
    if response_id:
        return [{"response_id": response_id, "direction": objective.get("direction", "maximize")}]
    return []


def _has_executable_non_box_constraint(state: dict[str, Any]) -> bool:
    return any(_constraint_kind(constraint) in {"linear", "nchoosek", "forbidden", "conditional"} for constraint in state.get("constraints", []) or [] if isinstance(constraint, dict))


def _has_multi_objective_responses(state: dict[str, Any]) -> bool:
    return len(_objective_responses(state)) >= 2


def _has_scale_fidelity_structure(state: dict[str, Any], usable_rows: list[dict[str, Any]]) -> bool:
    if not isinstance(state.get("scale_context"), dict):
        return False
    if isinstance(state.get("campaign_arms"), list) and len(state.get("campaign_arms") or []) >= 2:
        return True
    if isinstance(state.get("arms"), list) and len(state.get("arms") or []) >= 2:
        return True
    observed = {str(row.get("arm_id") or "").strip() for row in usable_rows if str(row.get("arm_id") or "").strip()}
    return len(observed) >= 2


def _constraint_kind(constraint: dict[str, Any]) -> str:
    kind = str(constraint.get("type") or constraint.get("constraint_type") or constraint.get("kind") or "").lower()
    if kind in {"linear", "linear_constraint"} or "coefficients" in constraint:
        return "linear"
    if kind in {"nchoosek", "n_choose_k", "n-choose-k"} or {"features", "max_count"} <= set(constraint):
        return "nchoosek"
    if kind in {"forbidden", "forbidden_combination"} or "when" in constraint:
        return "forbidden"
    if kind in {"conditional", "conditional_infeasibility"}:
        return "conditional"
    return kind


def _constraint_id(constraint: dict[str, Any]) -> str:
    return str(constraint.get("constraint_id") or constraint.get("id") or "constraint")


def _conditional_linear_spec(constraint: dict[str, Any]) -> dict[str, Any] | None:
    condition = constraint.get("if") or constraint.get("when")
    requirement = constraint.get("then") or constraint.get("requires")
    if not isinstance(condition, dict) or not isinstance(requirement, dict):
        return None
    if len(condition) != 1 or len(requirement) != 1:
        return None

    gate_feature, gate_value = next(iter(condition.items()))
    gate_numeric = parse_number(gate_value)
    if gate_numeric != 1.0:
        return None

    required_feature, raw_rule = next(iter(requirement.items()))
    if not isinstance(raw_rule, dict) or len(raw_rule) != 1:
        return None
    operator, raw_threshold = next(iter(raw_rule.items()))
    threshold = parse_number(raw_threshold)
    if threshold is None or str(operator).strip() not in {">=", ">"}:
        return None

    return {
        "id": _constraint_id(constraint),
        "type": "linear",
        "features": [str(required_feature), str(gate_feature)],
        "coefficients": [1.0, -float(threshold)],
        "rhs": 0.0,
        "operator": ">=",
        "source_type": "conditional_binary_threshold",
    }


def _unsupported_constraint_ids(constraints: list[dict[str, Any]]) -> list[str]:
    unsupported = []
    for constraint in constraints:
        if not isinstance(constraint, dict):
            continue
        kind = _constraint_kind(constraint)
        if kind in {"linear", "nchoosek"}:
            continue
        if kind == "conditional" and _conditional_linear_spec(constraint) is not None:
            continue
        if kind in {"forbidden", "conditional"}:
            unsupported.append(_constraint_id(constraint))
    return unsupported


def _strategy_kind(reasons: list[str]) -> str:
    if "scale_fidelity_structure" in reasons:
        return "multi_fidelity"
    if "multi_objective_responses" in reasons:
        return "multi_objective"
    if "non_box_constraints" in reasons:
        return "constrained_doe"
    if "operator_requested_bofire" in reasons:
        return "single_objective"
    return "not_routed"


def _policy(state: dict[str, Any]) -> dict[str, Any]:
    return state.get("design_policy") if isinstance(state.get("design_policy"), dict) else {}


__all__ = [
    "CLAIM_LEVEL",
    "NON_CLAIM",
    "build_domain_spec",
    "is_available",
    "plan_bofire_wave2",
    "routing_decision",
]
