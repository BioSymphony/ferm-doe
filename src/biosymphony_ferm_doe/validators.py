"""Validators for BioSymphony Ferm DoE manifests. Guidance-mode by default."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from .adaptive import ADAPTIVE_ACTIONS, PLANNED_WAVE2_CLAIM, evaluate_assay_power, response_requires_assay
from .doe_families import FAMILY_REGISTRY, minimum_runs
from .profiles import (
    PROFILE_REGISTRY,
    PUBLIC_SAFETY_RULES,
    merge_advised_blocks,
    merge_advised_expected,
    merge_advised_inputs,
    merge_required_blocks,
    resolve_profiles,
)


VALID_VERDICTS = {"GREEN", "YELLOW", "RED"}
VALID_READINESS_STATES = {
    "not_started",
    "planned",
    "in_progress",
    "qualified",
    "qualified_with_caveats",
    "failed",
}
TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".cff",
    ".csv",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}
SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".runtime",
    ".nox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "venv",
}
FORBIDDEN_FILE_NAMES = {".env", ".env.local", ".envrc"}
AUDIT_SKIP_RE = re.compile(r"#\s*audit-skip:")
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private-home-path", re.compile(r"(?<![A-Za-z0-9_./-])/(?:Users|home)/[A-Za-z0-9._-]+(?=[/\s'\"]|$)")),
    ("windows-user-profile-path", re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+")),
    ("private-key-block", re.compile(r"BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY")),
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}")),
    ("api-token-like-value", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    (
        "assigned-secret-like-value",
        re.compile(r"(?i)\b(?:api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[A-Za-z0-9._/-]{16,}"),
    ),
]


def _add(checks: list[dict[str, Any]], check_id: str, ok: bool, detail: str, severity: str = "error", axis: str | None = None) -> None:
    entry: dict[str, Any] = {"id": check_id, "ok": ok, "severity": severity, "detail": detail}
    if axis:
        entry["axis"] = axis
    checks.append(entry)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _public_path_label(path: Path) -> str:
    if path.is_absolute():
        return path.name or "<absolute_path_redacted>"
    return path.as_posix()


def _factor_lookup(factors: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for factor in factors:
        if isinstance(factor, dict) and isinstance(factor.get("factor_id"), str):
            out[factor["factor_id"]] = factor
    return out


def _list_factors(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    factors = manifest.get("factors", [])
    return factors if isinstance(factors, list) else []


def _list_responses(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    responses = manifest.get("responses", [])
    return responses if isinstance(responses, list) else []


def _list_arms(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    arms = manifest.get("arms", [])
    return arms if isinstance(arms, list) else []


def _validate_structural(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    _add(checks, "campaign-id", isinstance(manifest.get("campaign_id"), str) and bool(manifest["campaign_id"]), "Manifest declares a campaign_id.")
    _add(checks, "claim-level", isinstance(manifest.get("claim_level"), str) and bool(manifest["claim_level"]), "Manifest declares a claim_level.")


def _validate_public_safety(manifest: dict[str, Any], tables: dict[str, list[dict[str, str]]], checks: list[dict[str, Any]]) -> None:
    if manifest.get("claim_level") != PUBLIC_SAFETY_RULES["claim_level_value"]:
        return
    privacy = manifest.get("system", {}).get("privacy") if isinstance(manifest.get("system"), dict) else None
    _add(checks, "public-safety-privacy", privacy == PUBLIC_SAFETY_RULES["privacy_value"], f"Public-safe campaigns declare privacy = {PUBLIC_SAFETY_RULES['privacy_value']}.")

    for row_kind, label_id in (("historical_run_ledger", "historical-source-labels"), ("evidence_table", "evidence-source-labels")):
        rows = tables.get(row_kind, [])
        if not rows:
            continue
        unlabeled = [row for row in rows if row.get("source_type") not in PUBLIC_SAFETY_RULES["public_source_types"]]
        _add(checks, label_id, not unlabeled, f"{row_kind} rows are labeled synthetic or public-source.")

    historical = tables.get("historical_run_ledger", [])
    if historical:
        bad = []
        for row in historical:
            try:
                score = float(row.get("trust_score", ""))
                if not 0.0 <= score <= 1.0:
                    bad.append(row.get("run_id", "<missing>"))
            except (TypeError, ValueError):
                bad.append(row.get("run_id", "<missing>"))
        _add(checks, "historical-trust-scores", not bad, "Historical rows have trust scores in [0, 1].")

    evidence = tables.get("evidence_table", [])
    if evidence:
        unresolved = [row.get("evidence_id", "<missing>") for row in evidence if row.get("review_status") == "needs_source"]
        _add(checks, "evidence-source-review", not unresolved, "Evidence rows with placeholder source references are clearly flagged.", severity="warning")


def _validate_inputs(manifest: dict[str, Any], example_dir: Path, profiles: list[str], checks: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    loaded: dict[str, list[dict[str, str]]] = {}
    inputs = manifest.get("inputs", {})
    if not isinstance(inputs, dict):
        _add(checks, "input-map", False, "Manifest 'inputs' must be an object.")
        return loaded

    for key, relative_path in sorted(inputs.items()):
        if not isinstance(relative_path, str):
            _add(checks, f"input-path-{key}", False, f"Input path for {key} is not a string.")
            continue
        path = example_dir / relative_path
        _add(checks, f"input-file-{key}", path.is_file(), f"Input file exists: {relative_path}")
        if path.is_file() and path.suffix == ".csv":
            rows = _read_csv(path)
            loaded[key] = rows
            _add(checks, f"input-rows-{key}", len(rows) > 0, f"Input file {relative_path} has {len(rows)} data row(s).", severity="warning")

    public_demo = manifest.get("claim_level") == PUBLIC_SAFETY_RULES["claim_level_value"]
    required = list(PUBLIC_SAFETY_RULES["required_inputs"]) if public_demo else []
    advised = merge_advised_inputs(profiles)
    if public_demo:
        for item in PUBLIC_SAFETY_RULES["advised_inputs"]:
            if item not in advised:
                advised.append(item)

    for item in required:
        _add(checks, f"input-required-{item}", item in inputs, f"Public-safe campaigns declare {item} input.")
    for item in advised:
        if item in required:
            continue
        _add(checks, f"input-advised-{item}", item in inputs, f"Profile advises {item} input.", severity="warning")

    return loaded


def _validate_expected_artifacts(manifest: dict[str, Any], example_dir: Path, profiles: list[str], checks: list[dict[str, Any]]) -> None:
    public_demo = manifest.get("claim_level") == PUBLIC_SAFETY_RULES["claim_level_value"]
    required = list(PUBLIC_SAFETY_RULES["required_expected"]) if public_demo else []
    advised = merge_advised_expected(profiles)
    if public_demo:
        for item in PUBLIC_SAFETY_RULES["advised_expected"]:
            if item not in advised:
                advised.append(item)

    for item in required:
        path = example_dir / "expected" / item
        _add(checks, f"expected-required-{item}", path.is_file(), f"Required expected artifact exists: expected/{item}")
    for item in advised:
        if item in required:
            continue
        path = example_dir / "expected" / item
        _add(checks, f"expected-advised-{item}", path.is_file(), f"Advised expected artifact exists: expected/{item}", severity="warning")


def _validate_required_blocks(manifest: dict[str, Any], profiles: list[str], checks: list[dict[str, Any]]) -> None:
    required = merge_required_blocks(profiles)
    advised = merge_advised_blocks(profiles)
    for block in required:
        present = manifest.get(block) not in (None, [], {})
        _add(checks, f"profile-required-block-{block}", present, f"Profile requires manifest.{block}.", axis=block)
    for block in advised:
        if block in required:
            continue
        present = manifest.get(block) not in (None, [], {})
        _add(checks, f"profile-advised-block-{block}", present, f"Profile advises manifest.{block}.", severity="warning", axis=block)


def _validate_responses(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    responses = _list_responses(manifest)
    _add(checks, "responses-present", len(responses) > 0, "Manifest defines at least one response.", severity="warning")
    for response in responses:
        if not isinstance(response, dict):
            _add(checks, "response-shape", False, "Response entries must be objects.")
            continue
        rid = response.get("response_id", "<missing>")
        if response.get("measurement_type") == "assayed":
            missing = [field for field in ("assay_method", "sample_fraction", "standard_curve", "matrix_effects_policy") if not response.get(field)]
            ok = not missing and response.get("assay_required") is True
            _add(checks, f"assay-contract-{rid}", ok, f"Assayed response {rid} has method, sample fraction, calibration, and matrix policy.", severity="warning" if missing else "error", axis=f"response:{rid}")


def _validate_assay_power_policy(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    adaptive = manifest.get("adaptive_wave2") if isinstance(manifest.get("adaptive_wave2"), dict) else {}
    responses = _list_responses(manifest)
    has_policy = any(isinstance(response, dict) and isinstance(response.get("assay_power_policy"), dict) for response in responses)
    require_power = bool(adaptive.get("require_assay_power"))
    if not has_policy and not require_power:
        return

    result = evaluate_assay_power(manifest, strict=require_power)
    for item in result.get("response_results", []):
        if not isinstance(item, dict):
            continue
        rid = item.get("response_id", "<missing>")
        status = item.get("status")
        if status == "NOT_APPLICABLE":
            warnings = item.get("warnings", [])
            if warnings:
                _add(checks, f"assay-power-{rid}", False, f"Non-assay response {rid} should not carry lab-assay power requirements.", severity="warning", axis=f"response:{rid}")
            continue
        if status == "PASS":
            _add(checks, f"assay-power-{rid}", True, f"Assay-power policy for {rid} passes public planning checks.", severity="warning", axis=f"response:{rid}")
        else:
            severity = "error" if require_power and status == "FAIL" else "warning"
            detail = f"Assay-power policy for {rid} is {status}; review missing fields, CV, recovery, replicate count, and power proxy."
            _add(checks, f"assay-power-{rid}", False, detail, severity=severity, axis=f"response:{rid}")


def _validate_factors(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    factors = _list_factors(manifest)
    for factor in factors:
        if not isinstance(factor, dict):
            _add(checks, "factor-shape", False, "Factor entries must be objects.")
            continue
        fid = factor.get("factor_id", "<missing>")
        ftype = factor.get("type")
        if ftype == "numeric":
            has_bounds = isinstance(factor.get("low"), (int, float)) and isinstance(factor.get("high"), (int, float))
            _add(checks, f"factor-bounds-present-{fid}", has_bounds, f"Numeric factor {fid} declares low and high.", severity="warning", axis=f"factor:{fid}")
            if has_bounds:
                _add(checks, f"factor-bounds-coherent-{fid}", factor["low"] <= factor["high"], f"Numeric factor {fid} has low ≤ high.", axis=f"factor:{fid}")
        elif ftype == "categorical":
            levels = factor.get("levels")
            ok = isinstance(levels, list) and len(levels) >= 2
            _add(checks, f"factor-levels-{fid}", ok, f"Categorical factor {fid} declares ≥2 levels.", severity="warning", axis=f"factor:{fid}")
        elif ftype == "ordinal":
            levels = factor.get("levels")
            ok = isinstance(levels, list) and len(levels) >= 2
            _add(checks, f"factor-ordinal-{fid}", ok, f"Ordinal factor {fid} declares ordered levels.", severity="warning", axis=f"factor:{fid}")
        elif ftype == "mixture":
            components = factor.get("components")
            ok = isinstance(components, list) and len(components) >= 2
            _add(checks, f"factor-mixture-{fid}", ok, f"Mixture factor {fid} declares components.", severity="warning", axis=f"factor:{fid}")
        elif ftype == "temporal_profile":
            keys = factor.get("profile_keys")
            ok = isinstance(keys, list) and len(keys) >= 2
            _add(checks, f"factor-profile-{fid}", ok, f"Temporal profile factor {fid} declares profile_keys.", severity="warning", axis=f"factor:{fid}")
        elif ftype == "block":
            levels = factor.get("levels")
            ok = isinstance(levels, list) and len(levels) >= 2
            _add(checks, f"factor-block-{fid}", ok, f"Block factor {fid} declares ≥2 levels.", severity="warning", axis=f"factor:{fid}")
        elif ftype == "hard_constraint":
            ok = isinstance(factor.get("expression"), str) and bool(factor["expression"])
            _add(checks, f"factor-constraint-{fid}", ok, f"Hard-constraint factor {fid} declares an expression.", severity="warning", axis=f"factor:{fid}")
        else:
            _add(checks, f"factor-type-{fid}", False, f"Factor {fid} has unknown type '{ftype}'.", severity="warning", axis=f"factor:{fid}")


def _validate_arms(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    arms = _list_arms(manifest)
    if not arms:
        return
    seen: set[str] = set()
    for arm in arms:
        if not isinstance(arm, dict):
            _add(checks, "arm-shape", False, "Arm entries must be objects.")
            continue
        aid = arm.get("arm_id")
        if not isinstance(aid, str) or not aid:
            _add(checks, "arm-id", False, "Each arm declares an arm_id.")
            continue
        if aid in seen:
            _add(checks, f"arm-unique-{aid}", False, f"Duplicate arm_id: {aid}.")
        seen.add(aid)
        _add(checks, f"arm-scale-tier-{aid}", isinstance(arm.get("scale_tier"), str), f"Arm {aid} declares a scale_tier.", severity="warning", axis=f"arm:{aid}")


def _validate_scale_context(manifest: dict[str, Any], profiles: list[str], checks: list[dict[str, Any]]) -> None:
    scale = manifest.get("scale_context")
    needs_scale = any("scale_up_bridge" == p or "scale_down_qualification" == p for p in profiles)
    if scale is None:
        if needs_scale:
            _add(checks, "scale-context-present", False, "Scale-bridge profile requires scale_context.")
        return
    if not isinstance(scale, dict):
        _add(checks, "scale-context-shape", False, "scale_context must be an object.")
        return

    bridge = scale.get("bridge_strategy", {})
    primary = bridge.get("primary_criterion") if isinstance(bridge, dict) else None
    _add(checks, "scale-primary-criterion", bool(primary), "scale_context.bridge_strategy.primary_criterion declared.", severity="warning")

    for endpoint in ("from_scale", "to_scale"):
        ep = scale.get(endpoint)
        _add(checks, f"scale-endpoint-{endpoint}", isinstance(ep, dict), f"scale_context.{endpoint} declared.", severity="warning", axis="scale_context")
        if isinstance(ep, dict) and isinstance(primary, str):
            target_field = {
                "kLa": ("engineering_targets", "kLa_per_hour"),
                "p_per_v": ("engineering_targets", "p_per_v_w_per_m3"),
                "tip_speed": ("engineering_targets", "tip_speed_m_per_s"),
                "mix_time": ("engineering_targets", "mix_time_s"),
                "do_control": ("engineering_targets", "do_setpoint_pct"),
                "our": ("engineering_targets", "our_mmol_per_l_per_h"),
                "rq": ("engineering_targets", "rq"),
                "vvm": ("engineering_targets", "vvm"),
            }.get(primary)
            if target_field:
                section = ep.get(target_field[0]) if isinstance(ep.get(target_field[0]), dict) else {}
                value_present = section.get(target_field[1]) is not None
                _add(checks, f"scale-criterion-target-{endpoint}", value_present, f"{endpoint} declares {primary} target ({target_field[1]}).", severity="warning", axis="scale_context")

    bridge_factors = scale.get("bridge_factors")
    _add(checks, "scale-bridge-factors", isinstance(bridge_factors, dict) and any(bridge_factors.get(k) for k in ("transferable", "needs_retuning", "not_applicable")), "scale_context.bridge_factors splits factors into transferable / needs_retuning / not_applicable.", severity="warning", axis="scale_context")

    if "scale_down_qualification" in profiles:
        recap = scale.get("recapitulation_criterion")
        _add(checks, "scale-recap-criterion", isinstance(recap, dict) and bool(recap.get("metric")), "scale_down_qualification declares a recapitulation_criterion.metric.", severity="warning", axis="scale_context")


def _validate_doe(manifest: dict[str, Any], example_dir: Path, checks: list[dict[str, Any]]) -> None:
    doe = manifest.get("doe")
    if not isinstance(doe, dict):
        return
    family = doe.get("family")
    info = FAMILY_REGISTRY.get(family) if isinstance(family, str) else None
    _add(checks, "doe-family-known", info is not None, f"DoE family '{family}' is recognized.", severity="warning", axis="doe")
    if not info:
        return

    factors = _list_factors(manifest)
    k = len(factors)
    n_runs = doe.get("n_runs")
    estimate = minimum_runs(family, k, n_center=doe.get("n_center_points", 3), p=doe.get("fraction_p", 0))
    if isinstance(n_runs, int) and isinstance(estimate, int):
        _add(checks, "doe-min-runs", n_runs >= estimate, f"Declared n_runs ({n_runs}) ≥ family minimum ({estimate}) for k={k}.", severity="warning", axis="doe")

    if info.get("requires_resolution"):
        _add(checks, "doe-resolution", isinstance(doe.get("resolution"), str), f"Family '{family}' expects resolution declared.", severity="warning", axis="doe")
    if info.get("expects_alias_structure") is True:
        _add(checks, "doe-alias-structure", doe.get("alias_structure") not in (None, ""), f"Family '{family}' expects an alias structure to be declared.", severity="warning", axis="doe")
    if info.get("expects_center_points") is True:
        n_center = doe.get("n_center_points", 0)
        min_center = info.get("min_center_points", 1)
        _add(checks, "doe-center-points", isinstance(n_center, int) and n_center >= min_center, f"Family '{family}' expects ≥{min_center} center points.", severity="warning", axis="doe")
    if info.get("requires_mixture_factors"):
        has_mix = any(f.get("type") == "mixture" for f in factors if isinstance(f, dict))
        _add(checks, "doe-mixture-factors", has_mix, f"Family '{family}' requires at least one mixture factor.", severity="warning", axis="doe")
    if info.get("requires_hard_to_change_factors"):
        has_htc = any(isinstance(f, dict) and f.get("hard_to_change") is True for f in factors)
        _add(checks, "doe-hard-to-change", has_htc, f"Family '{family}' requires at least one hard_to_change factor.", severity="warning", axis="doe")
    if info.get("requires_previous_wave_ref"):
        _add(checks, "doe-previous-wave", isinstance(doe.get("previous_wave_ref"), str), f"Family '{family}' requires previous_wave_ref.", severity="warning", axis="doe")

    _add(checks, "doe-randomized", doe.get("randomized") is True, "DoE declares randomized run order.", severity="warning", axis="doe")
    _add(checks, "doe-claim-level", isinstance(doe.get("claim"), str), "DoE declares a statistical claim level (exact|adapter_backed|approximate|heuristic).", severity="warning", axis="doe")


def _validate_design_table(manifest: dict[str, Any], example_dir: Path, checks: list[dict[str, Any]]) -> None:
    doe = manifest.get("doe") if isinstance(manifest.get("doe"), dict) else {}
    declared_path = doe.get("design_table_path")
    candidates: list[Path] = []
    if isinstance(declared_path, str) and declared_path:
        candidates.append(example_dir / declared_path)
    fallback = example_dir / "expected" / "selected_wave_1_design.csv"
    if fallback not in candidates and fallback.exists():
        candidates.append(fallback)

    for arm in _list_arms(manifest):
        if not isinstance(arm, dict):
            continue
        arm_doe = arm.get("doe") if isinstance(arm.get("doe"), dict) else {}
        arm_path = arm_doe.get("design_table_path")
        if isinstance(arm_path, str) and arm_path:
            candidates.append(example_dir / arm_path)

    if not candidates:
        return

    factors = _factor_lookup(_list_factors(manifest))
    arm_factor_lookups: dict[str, dict[str, dict[str, Any]]] = {}
    for arm in _list_arms(manifest):
        if isinstance(arm, dict) and isinstance(arm.get("arm_id"), str):
            af = arm.get("factors", [])
            if isinstance(af, list) and af:
                arm_factor_lookups[arm["arm_id"]] = _factor_lookup(af)

    for path in candidates:
        if not path.is_file():
            _add(checks, f"design-file-{path.name}", False, f"Design table file exists: {path.relative_to(example_dir)}.", severity="warning", axis="doe")
            continue
        rows = _read_csv(path)
        _add(checks, f"design-rows-{path.name}", len(rows) > 0, f"Design table {path.name} has {len(rows)} row(s).", severity="warning", axis="doe")

        errors: list[str] = []
        for row in rows:
            run_id = row.get("run_id", "<missing>")
            arm_id = row.get("arm_id")
            lookup = arm_factor_lookups.get(arm_id, factors) if arm_id else factors
            for fid, factor in lookup.items():
                if fid not in row:
                    continue
                value = row[fid]
                ftype = factor.get("type")
                if ftype == "numeric":
                    try:
                        nv = float(value)
                    except (TypeError, ValueError):
                        errors.append(f"{run_id}:{fid}:not-numeric")
                        continue
                    if "low" in factor and nv < float(factor["low"]):
                        errors.append(f"{run_id}:{fid}:below-low")
                    if "high" in factor and nv > float(factor["high"]):
                        errors.append(f"{run_id}:{fid}:above-high")
                elif ftype == "categorical":
                    if value not in factor.get("levels", []):
                        errors.append(f"{run_id}:{fid}:unknown-level")
                elif ftype == "mixture":
                    pass
        _add(checks, f"design-bounds-{path.name}", not errors, f"Design rows in {path.name} respect manifest factor bounds.", axis="doe")

        mixture_factors = [f for f in _list_factors(manifest) if isinstance(f, dict) and f.get("type") == "mixture"]
        if mixture_factors:
            _validate_mixture_rows(rows, mixture_factors, path.name, checks)


def _validate_mixture_rows(rows: list[dict[str, str]], mixture_factors: list[dict[str, Any]], path_label: str, checks: list[dict[str, Any]]) -> None:
    for factor in mixture_factors:
        components = factor.get("components", [])
        if not components:
            continue
        tol = float(factor.get("mixture_tolerance", 0.01))
        violations: list[str] = []
        for row in rows:
            try:
                total = sum(float(row.get(comp, "0") or 0) for comp in components)
            except (TypeError, ValueError):
                violations.append(row.get("run_id", "<missing>"))
                continue
            if abs(total - 1.0) > tol:
                violations.append(row.get("run_id", "<missing>"))
        _add(checks, f"design-mixture-{factor['factor_id']}-{path_label}", not violations, f"Mixture factor {factor['factor_id']} components sum to 1.0 ± {tol} in {path_label}.", severity="warning", axis="doe")


def _validate_decision_rules(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    rules = manifest.get("decision_rules", [])
    if not isinstance(rules, list) or not rules:
        return
    valid_actions = {"advance_to_next_wave", "augment", "pause", "abort", "escalate", "narrow_factor_space", "expand_factor_space", "switch_arm"}
    for rule in rules:
        rid = rule.get("rule_id", "<missing>") if isinstance(rule, dict) else "<bad>"
        ok = isinstance(rule, dict) and all(k in rule for k in ("rule_id", "scope", "comparator", "threshold", "action")) and rule.get("action") in valid_actions
        _add(checks, f"decision-rule-{rid}", ok, f"Decision rule {rid} has rule_id, scope, comparator, threshold, and a valid action.", severity="warning", axis="decision_rules")


def _validate_stop_rules(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    rules = manifest.get("stop_rules", [])
    if not isinstance(rules, list) or not rules:
        return
    valid_actions = {"pause", "abort", "escalate"}
    for rule in rules:
        rid = rule.get("rule_id", "<missing>") if isinstance(rule, dict) else "<bad>"
        ok = isinstance(rule, dict) and all(k in rule for k in ("rule_id", "condition", "action")) and rule.get("action") in valid_actions
        _add(checks, f"stop-rule-{rid}", ok, f"Stop rule {rid} has rule_id, condition, and a valid action.", severity="warning", axis="stop_rules")


def _validate_risks(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    risks = manifest.get("risk_register", [])
    if not isinstance(risks, list) or not risks:
        return
    for risk in risks:
        rid = risk.get("risk_id", "<missing>") if isinstance(risk, dict) else "<bad>"
        ok = isinstance(risk, dict) and all(k in risk for k in ("risk_id", "category", "likelihood", "impact"))
        _add(checks, f"risk-{rid}", ok, f"Risk {rid} declares category, likelihood, impact.", severity="warning", axis="risk_register")


def _validate_assumptions(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    assumptions = manifest.get("assumptions", [])
    if not isinstance(assumptions, list) or not assumptions:
        return
    for a in assumptions:
        aid = a.get("assumption_id", "<missing>") if isinstance(a, dict) else "<bad>"
        ok = isinstance(a, dict) and bool(a.get("statement")) and bool(a.get("status"))
        _add(checks, f"assumption-{aid}", ok, f"Assumption {aid} has a statement and a status.", severity="warning", axis="assumptions")


def _validate_readiness_object(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    readiness = manifest.get("readiness")
    if readiness is None:
        return
    if not isinstance(readiness, dict):
        _add(checks, "readiness-shape", False, "readiness must be an object.")
        return
    overall = readiness.get("overall")
    if overall is not None:
        _add(checks, "readiness-overall", overall in VALID_VERDICTS, "readiness.overall is GREEN | YELLOW | RED.", severity="warning")
    axes = readiness.get("axes", {})
    if isinstance(axes, dict):
        for axis_name, payload in axes.items():
            if isinstance(payload, str):
                _add(checks, f"readiness-axis-{axis_name}", payload in VALID_READINESS_STATES, f"readiness.axes.{axis_name} is a valid state.", severity="warning")
            elif isinstance(payload, dict):
                for sub_id, state in payload.items():
                    _add(checks, f"readiness-axis-{axis_name}-{sub_id}", state in VALID_READINESS_STATES, f"readiness.axes.{axis_name}.{sub_id} is a valid state.", severity="warning")


def _validate_adaptive_wave2(manifest: dict[str, Any], example_dir: Path, checks: list[dict[str, Any]]) -> None:
    adaptive = manifest.get("adaptive_wave2")
    if adaptive is None:
        return
    if not isinstance(adaptive, dict):
        _add(checks, "adaptive-wave2-shape", False, "adaptive_wave2 must be an object.")
        return

    claim = adaptive.get("claim_level")
    if claim is not None:
        _add(checks, "adaptive-wave2-claim", claim == PLANNED_WAVE2_CLAIM, f"adaptive_wave2.claim_level should be {PLANNED_WAVE2_CLAIM}.", severity="warning", axis="adaptive_wave2")

    for key in ("recommended_action", "requested_action", "target_action"):
        action = adaptive.get(key)
        if action is None:
            continue
        _add(checks, f"adaptive-wave2-action-{key}", action in ADAPTIVE_ACTIONS, f"adaptive_wave2.{key} is a supported follow-up action.", severity="warning", axis="adaptive_wave2")

    allowed = adaptive.get("allowed_actions")
    if allowed is not None:
        ok = isinstance(allowed, list) and all(item in ADAPTIVE_ACTIONS for item in allowed)
        _add(checks, "adaptive-wave2-allowed-actions", ok, "adaptive_wave2.allowed_actions only contains supported actions.", severity="warning", axis="adaptive_wave2")

    primary = adaptive.get("primary_response_id")
    if isinstance(primary, str):
        response_ids = {response.get("response_id") for response in _list_responses(manifest) if isinstance(response, dict)}
        _add(checks, "adaptive-wave2-primary-response", primary in response_ids, "adaptive_wave2.primary_response_id references a declared response.", severity="warning", axis="adaptive_wave2")

    result_path = adaptive.get("result_table_path")
    if isinstance(result_path, str) and result_path:
        _add(checks, "adaptive-wave2-result-table", (example_dir / result_path).is_file(), f"adaptive_wave2.result_table_path exists: {result_path}", severity="warning", axis="adaptive_wave2")

    self_learning = adaptive.get("self_learning")
    if isinstance(self_learning, dict) and self_learning.get("enabled") is True:
        has_ledger = bool(self_learning.get("learning_ledger_path") or self_learning.get("hiccup_review_path"))
        _add(checks, "adaptive-wave2-self-learning-ledger", has_ledger, "Self-learning setup declares a learning ledger or hiccup review path.", severity="warning", axis="adaptive_wave2")

    requested_actions = {adaptive.get("recommended_action"), adaptive.get("requested_action"), adaptive.get("target_action")}
    if "scale_or_downscale" in requested_actions:
        has_bridge = isinstance(adaptive.get("bridge_policy"), dict) or isinstance(manifest.get("arm_bridge_policy"), dict)
        _add(checks, "adaptive-wave2-bridge-policy", has_bridge, "scale_or_downscale planning declares bridge policy before transfer claims.", severity="warning", axis="adaptive_wave2")

    if adaptive.get("require_assay_power") is True:
        assayed = [response for response in _list_responses(manifest) if isinstance(response, dict) and response_requires_assay(response)]
        _add(checks, "adaptive-wave2-assay-power-targets", bool(assayed), "require_assay_power has at least one assayed response target.", severity="warning", axis="adaptive_wave2")


def _validate_module_readiness(manifest: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    """Surface warnings when downstream module commands will short-circuit.

    These are guidance, not gating. They flag manifests where one of the
    advanced subcommands (goals, scale-recipe, bridge-qualification,
    sampling-plan, cost-rollup) cannot produce useful output as-declared.
    The agent reads these from ``failed_check_ids`` and either fixes the
    manifest or accepts the limitation.
    """
    responses = manifest.get("responses") or []
    decision_rules = manifest.get("decision_rules") or []
    arms = manifest.get("arms") or []
    scale_context = manifest.get("scale_context") if isinstance(manifest.get("scale_context"), dict) else None

    has_objective_bounds = any(
        isinstance(r, dict)
        and (r.get("objective_lower") is not None or r.get("objective_upper") is not None or r.get("objective_target") is not None)
        for r in responses
    )
    has_numeric_decision_rule = any(
        isinstance(r, dict)
        and isinstance(r.get("scope"), str)
        and r.get("scope", "").startswith("response:")
        and isinstance(r.get("threshold"), (int, float))
        for r in decision_rules
    )
    _add(
        checks,
        "module-readiness-goals",
        has_objective_bounds or has_numeric_decision_rule,
        "Optimization goals can be formulated (responses[] carry objective bounds OR decision_rules[] have numeric scoped thresholds).",
        severity="warning",
    )

    if scale_context:
        from_scale = scale_context.get("from_scale") if isinstance(scale_context.get("from_scale"), dict) else {}
        from_targets = from_scale.get("engineering_targets") if isinstance(from_scale.get("engineering_targets"), dict) else {}
        has_criterion_value = any(
            from_targets.get(key) is not None
            for key in ("kLa_per_hour", "p_per_v_w_per_m3", "tip_speed_m_per_s")
        )
        _add(
            checks,
            "module-readiness-scale-recipe",
            has_criterion_value,
            "scale-recipe can derive setpoints (from_scale.engineering_targets carries kLa, P/V, or tip_speed).",
            severity="warning",
        )

    arm_with_bridge = any(
        isinstance(a, dict) and isinstance(a.get("bridge_to"), dict) and a["bridge_to"].get("arm_id")
        for a in arms
    )
    if arm_with_bridge:
        _add(
            checks,
            "module-readiness-bridge-qualification",
            scale_context is not None,
            "bridge-qualification can run (arms[] declare bridge_to AND scale_context is present).",
            severity="warning",
        )

    sampleable = any(
        isinstance(r, dict)
        and (
            r.get("assay_required")
            or str(r.get("measurement_type", "")).lower() in {"assayed", "instrument"}
        )
        for r in responses
    )
    _add(
        checks,
        "module-readiness-sampling-plan",
        sampleable,
        "sampling-plan has at least one assayed or instrument response to schedule.",
        severity="warning",
    )

    resource_costs = manifest.get("resource_costs") if isinstance(manifest.get("resource_costs"), dict) else None
    if resource_costs is not None:
        any_unit_cost = any(
            resource_costs.get(key) for key in ("per_run_cost", "per_sample_cost", "per_volume_ml_cost", "per_run_duration_h_cost")
        )
        _add(
            checks,
            "module-readiness-cost-rollup",
            any_unit_cost,
            "cost-rollup carries at least one non-zero unit cost (per-run, per-sample, per-volume, per-hour).",
            severity="warning",
        )


def _validate_expected_summary(manifest: dict[str, Any], example_dir: Path, checks: list[dict[str, Any]]) -> None:
    summary_path = example_dir / "expected" / "readiness_summary.json"
    if not summary_path.is_file():
        return
    try:
        summary = _read_json(summary_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _add(checks, "readiness-summary-json", False, f"Cannot read readiness summary: {exc}")
        return
    status = summary.get("status")
    _add(checks, "readiness-status-valid", status in VALID_VERDICTS, "Readiness summary status is GREEN, YELLOW, or RED.")
    expected_status = manifest.get("readiness_expectation")
    if expected_status:
        _add(checks, "readiness-status-matches-manifest", status == expected_status, "Readiness summary status matches manifest expectation.")
    reasons = summary.get("reasons")
    _add(checks, "readiness-caveats-present", isinstance(reasons, list) and len(reasons) > 0, "Readiness summary includes explicit caveats or reasons.", severity="warning")


def validate_campaign(example_dir: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    manifest_path = example_dir / "campaign_manifest.json"
    _add(checks, "manifest-present", manifest_path.is_file(), "Campaign manifest is present.")
    if not manifest_path.is_file():
        return _build_result(example_dir, {}, checks, [])
    try:
        manifest = _read_json(manifest_path)
        _add(checks, "manifest-json", True, "Campaign manifest is valid JSON.")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _add(checks, "manifest-json", False, f"Cannot read campaign manifest: {exc}")
        return _build_result(example_dir, {}, checks, [])

    _validate_structural(manifest, checks)
    profiles = resolve_profiles(manifest.get("profiles"))
    tables = _validate_inputs(manifest, example_dir, profiles, checks)
    _validate_public_safety(manifest, tables, checks)
    _validate_expected_artifacts(manifest, example_dir, profiles, checks)
    _validate_required_blocks(manifest, profiles, checks)
    _validate_responses(manifest, checks)
    _validate_assay_power_policy(manifest, checks)
    _validate_factors(manifest, checks)
    _validate_arms(manifest, checks)
    _validate_scale_context(manifest, profiles, checks)
    _validate_doe(manifest, example_dir, checks)
    _validate_design_table(manifest, example_dir, checks)
    _validate_decision_rules(manifest, checks)
    _validate_stop_rules(manifest, checks)
    _validate_risks(manifest, checks)
    _validate_assumptions(manifest, checks)
    _validate_readiness_object(manifest, checks)
    _validate_adaptive_wave2(manifest, example_dir, checks)
    _validate_module_readiness(manifest, checks)
    _validate_expected_summary(manifest, example_dir, checks)

    return _build_result(example_dir, manifest, checks, profiles)


def _build_result(example_dir: Path, manifest: dict[str, Any], checks: list[dict[str, Any]], profiles: list[str]) -> dict[str, Any]:
    errors = [c for c in checks if not c["ok"] and c["severity"] == "error"]
    warnings = [c for c in checks if not c["ok"] and c["severity"] == "warning"]
    expected = manifest.get("readiness_expectation")
    if errors:
        status = "RED"
    elif warnings or expected == "YELLOW":
        status = "YELLOW"
    else:
        status = "GREEN"
    if expected == "RED":
        status = "RED"
    return {
        "campaign_id": manifest.get("campaign_id"),
        "status": status,
        "claim_level": manifest.get("claim_level"),
        "profiles": profiles,
        "example_dir": _public_path_label(example_dir),
        "checks": checks,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "non_claim": "This validation does not verify physical execution or assay results.",
    }


def summarize(result: dict[str, Any]) -> dict[str, Any]:
    failed = [c for c in result.get("checks", []) if not c.get("ok")]
    by_axis: dict[str, int] = {}
    for c in failed:
        by_axis[c.get("axis", "general")] = by_axis.get(c.get("axis", "general"), 0) + 1
    worst_axis = max(by_axis, key=by_axis.get) if by_axis else None
    return {
        "campaign_id": result.get("campaign_id"),
        "status": result.get("status"),
        "claim_level": result.get("claim_level"),
        "profiles": result.get("profiles"),
        "error_count": result.get("error_count"),
        "warning_count": result.get("warning_count"),
        "worst_axis": worst_axis,
        "failed_check_ids": [c["id"] for c in failed],
        "non_claim": result.get("non_claim"),
    }


def _line_skips_audit(line: str) -> bool:
    return AUDIT_SKIP_RE.search(line) is not None


def audit_public_tree(root: Path) -> dict[str, Any]:
    root = root.resolve()
    issues: list[dict[str, str]] = []
    for path in root.rglob("*"):
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if path.is_file() and path.name in FORBIDDEN_FILE_NAMES:
            issues.append({"kind": "forbidden-file", "path": path.relative_to(root).as_posix(), "detail": "Environment/config secret file must not be published."})

    from .public_release import scan_paths

    for finding in scan_paths([root], root=root):
        issues.append(
            {
                "kind": finding.rule_id,
                "path": finding.path,
                "line": str(finding.line),
                "detail": finding.message,
            }
        )
    return {"root": _public_path_label(root), "status": "PASS" if not issues else "FAIL", "issue_count": len(issues), "issues": issues}
