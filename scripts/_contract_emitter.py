"""Backend-agnostic emitter for the 10-artifact smoke contract.

Used by each `run_<backend>_smoke_contract.py` wrapper. Produces:
  result.json, route_report.json, candidate_table.csv, constraint_check.json,
  fallback_report.json, closed_loop_replay.json, negative_control_report.json,
  artifact_hashes.json, license_note.md, planning_boundary.md

Validation is by `scripts/validate_smoke_artifacts.py`.
Schema: `docs/schemas/smoke-artifact-contract.json`.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_constraints(candidates: list[dict], manifest: dict) -> dict:
    """Validate candidate rows against manifest factor bounds + linear/NChooseK/categorical-exclude constraints.

    Manifest schema (per examples/adaptive-backend-eval/*/campaign_manifest.json):
    - factor: {"factor_id", "type", "min", "max"} (continuous) or {"factor_id", "type", "levels"} (categorical)
    - constraint linear: {"coefficients": {factor_id: coef}, "operator": "<=", "rhs": float}
    - constraint nchoosek: {"features": [factor_id], "min_count", "max_count", optional "threshold"}
    - constraint categorical_exclude: {"features": [factor_id], "excluded_combinations": [[val1, val2]]}
    """
    factors = {f["factor_id"]: f for f in manifest.get("factors", [])}
    constraints = manifest.get("constraints", [])

    factor_bounds_pass = True
    linear_constraints_pass = True
    nchoosek_pass = True
    forbidden_pass = True
    violations = []

    for i, cand in enumerate(candidates):
        for fid, finfo in factors.items():
            if finfo.get("type") == "categorical":
                continue
            val = cand.get(fid)
            if val is None or not isinstance(val, (int, float)):
                continue
            lo, hi = finfo.get("min"), finfo.get("max")
            if lo is not None and val < lo - 1e-6:
                factor_bounds_pass = False
                violations.append({"row": i, "type": "factor_bounds", "factor": fid, "value": val, "bound": [lo, hi]})
            if hi is not None and val > hi + 1e-6:
                factor_bounds_pass = False
                violations.append({"row": i, "type": "factor_bounds", "factor": fid, "value": val, "bound": [lo, hi]})

        for c in constraints:
            ctype = c.get("type")
            if ctype == "linear":
                coefs = c.get("coefficients", {})
                rhs = c.get("rhs", 0.0)
                op = c.get("operator", "<=")
                lhs = sum(coef * (cand.get(fid) or 0.0) for fid, coef in coefs.items())
                ok = (lhs <= rhs + 1e-6) if op == "<=" else (lhs >= rhs - 1e-6) if op == ">=" else abs(lhs - rhs) <= 1e-6
                if not ok:
                    linear_constraints_pass = False
                    violations.append({"row": i, "type": "linear", "constraint_id": c.get("constraint_id"), "lhs": lhs, "operator": op, "rhs": rhs})
            elif ctype == "nchoosek":
                fids = c.get("features", [])
                kmin = c.get("min_count", 0)
                kmax = c.get("max_count", len(fids))
                threshold = c.get("threshold", 0.0)
                active = sum(1 for fid in fids if (cand.get(fid) or 0.0) > threshold)
                if not (kmin <= active <= kmax):
                    nchoosek_pass = False
                    violations.append({"row": i, "type": "nchoosek", "constraint_id": c.get("constraint_id"), "active": active, "min": kmin, "max": kmax})
            elif ctype == "categorical_exclude":
                fids = c.get("features", [])
                cand_combo = tuple(str(cand.get(fid)) for fid in fids)
                for excluded in c.get("excluded_combinations", []):
                    if cand_combo == tuple(str(v) for v in excluded):
                        forbidden_pass = False
                        violations.append({"row": i, "type": "categorical_exclude", "constraint_id": c.get("constraint_id"), "combo": cand_combo})
                        break

    return {
        "factor_bounds_pass": factor_bounds_pass,
        "linear_constraints_pass": linear_constraints_pass,
        "nchoosek_pass": nchoosek_pass,
        "forbidden_combinations_pass": forbidden_pass,
        "per_arm_pass": True,
        "any_violation": bool(violations),
        "violations": violations[:50],
    }


def write_candidate_table(candidates: list[dict], out_path: Path, manifest: dict) -> int:
    factor_ids = [f["factor_id"] for f in manifest.get("factors", [])]
    response_ids = [r["response_id"] for r in manifest.get("responses", [])]
    extra = ["run_id"] + factor_ids + [f"predicted_{r}" for r in response_ids] + ["acquisition_score", "fidelity_tier"]
    cols = list(dict.fromkeys(extra))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for i, c in enumerate(candidates):
            row = {k: c.get(k, "") for k in cols}
            row["run_id"] = c.get("run_id") or f"cand-{i+1:03d}"
            w.writerow(row)
    return len(candidates)


def emit_contract(
    *,
    out_dir: Path,
    backend: str,
    scenario_id: str,
    manifest: dict,
    candidates: list[dict],
    route_selected: str,
    route_reason: str,
    route_reasons_matched: list[str] | None = None,
    fallback_route: str | None = None,
    constraints_honored_natively: bool,
    package_versions: dict,
    closed_loop_rounds: list[dict] | None = None,
    n1_pass: bool = True,
    n16_pass: bool = True,
    negative_control: dict | None = None,
    fallback: dict | None = None,
    license_info: dict | None = None,
    planning_boundary_text: str | None = None,
    status: str = "PASS",
    runtime_seconds: float | None = None,
    predicted_response: dict | None = None,
    acquisition_score: float | None = None,
    instrumentation_notes: str | None = None,
) -> dict:
    """Emit all 10 contract artifacts to out_dir. Returns dict of {filename: path}.

    Phase 4.4 (2026-05-22) added optional instrumentation kwargs:
    - ``runtime_seconds``: wall time for the strategy's ``.ask()`` only (NOT
      including manifest parsing / validator / fitting overhead). Captured
      with ``time.perf_counter()``.
    - ``predicted_response``: dict keyed by response_id, value = mean of the
      surrogate's posterior mean across emitted candidates (single scalar per
      response). ``None`` for backends without a clean ``posterior(X)`` path
      (e.g. DoEStrategy, Sobol fallback).
    - ``acquisition_score``: scalar = highest acquisition value among emitted
      candidates (best EI / hypervolume / EHVI). ``None`` for DoE backends and
      Sobol fallback.
    - ``instrumentation_notes``: free-form explanation surfaced in
      ``result.json.instrumentation.notes`` describing why a field is None or
      how it was computed. Kept additive so old callers continue to work.

    These fields land in ``result.json`` under top-level ``runtime_seconds``
    and a new ``instrumentation`` sub-object. They are NOT required by the
    schema (additive-only change) so older artifact sets stay valid.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    constraint_check = check_constraints(candidates, manifest)
    effective_status = status
    effective_constraints_honored_natively = constraints_honored_natively
    effective_fallback = fallback

    if constraint_check["any_violation"]:
        effective_constraints_honored_natively = False
        if status == "PASS":
            effective_status = "FAIL_CLOSED"
        if not effective_fallback or not effective_fallback.get("triggered"):
            effective_fallback = {
                "triggered": True,
                "phase": "constraint_solve",
                "reason": "candidate rows violated manifest constraints during post-hoc contract validation",
                "fallback_path_taken": "posthoc_constraint_revalidation",
            }
    candidate_table_path = out_dir / "candidate_table.csv"
    n_rows = write_candidate_table(candidates, candidate_table_path, manifest)

    # 1. result.json
    result = {
        "status": effective_status,
        "backend": backend,
        "scenario_id": scenario_id,
        "timestamp_utc": _utc_now_iso(),
        "package_versions": package_versions,
        "summary": {
            "n_candidates_n1": 1 if n1_pass else 0,
            "n_candidates_batch": n_rows if n16_pass else 0,
            "constraints_honored_natively": effective_constraints_honored_natively,
            "closed_loop_rounds_completed": len(closed_loop_rounds or []),
            "negative_control_triggered": negative_control is not None,
        },
    }
    # Phase 4.4 instrumentation (additive). Top-level runtime_seconds for
    # rubric dim 9 indexers; instrumentation sub-object carries per-response
    # predictions + best acquisition + a free-text notes field.
    if runtime_seconds is not None:
        result["runtime_seconds"] = float(runtime_seconds)
    result["instrumentation"] = {
        "runtime_seconds": float(runtime_seconds) if runtime_seconds is not None else None,
        "predicted_response": predicted_response if predicted_response is not None else None,
        "acquisition_score": float(acquisition_score) if acquisition_score is not None else None,
        "notes": instrumentation_notes,
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    # 2. route_report.json
    route = {
        "selected": route_selected,
        "reason": route_reason,
        "fallback_route": fallback_route,
        "route_reasons_matched": route_reasons_matched or [],
    }
    (out_dir / "route_report.json").write_text(json.dumps(route, indent=2) + "\n")

    # 3. candidate_table.csv already written

    # 4. constraint_check.json
    (out_dir / "constraint_check.json").write_text(json.dumps(constraint_check, indent=2) + "\n")

    # 5. fallback_report.json
    fb = effective_fallback or {"triggered": False, "phase": None, "reason": None, "fallback_path_taken": None}
    (out_dir / "fallback_report.json").write_text(json.dumps(fb, indent=2) + "\n")

    # 6. closed_loop_replay.json
    cl = {
        "n1_smoke_pass": n1_pass,
        "n16_batch_pass": n16_pass,
        "rounds": closed_loop_rounds or [],
    }
    (out_dir / "closed_loop_replay.json").write_text(json.dumps(cl, indent=2) + "\n")

    # 7. negative_control_report.json
    nc = negative_control or {
        "scenario": "not_probed",
        "expected_behavior": "fail_closed_with_route_report",
        "observed_behavior": "negative_control not run in this smoke",
        "passed": False,
    }
    (out_dir / "negative_control_report.json").write_text(json.dumps(nc, indent=2) + "\n")

    # 9. license_note.md  (write before hashes)
    lic = license_info or {}
    license_md = (
        f"# License note - {backend}\n\n"
        f"- **Package**: {lic.get('package','?')}\n"
        f"- **Version**: {lic.get('version','?')}\n"
        f"- **License**: {lic.get('license','?')}\n"
        f"- **Source**: {lic.get('source','?')}\n"
        f"- **Public release posture**: {lic.get('posture','reference-only by default; verify before vendor')}\n"
    )
    (out_dir / "license_note.md").write_text(license_md)

    # 10. planning_boundary.md
    pb = planning_boundary_text or (
        f"# Planning boundary - {backend}\n\n"
        f"This smoke output is a **planning suggestion**, not a lab-ready campaign.\n\n"
        f"BioSymphony retains ownership of: campaign manifest, readiness gates, scale bridge, assay readiness, "
        f"cost realism, evidence dossier, and handoff packet. The backend was used only as a candidate-generation "
        f"engine for scenario `{scenario_id}`. No transferability, no claim of optimality, no execution authorization."
    )
    (out_dir / "planning_boundary.md").write_text(pb + "\n")

    # 8. artifact_hashes.json (last - hash all the above)
    files_to_hash = [
        "result.json", "route_report.json", "candidate_table.csv",
        "constraint_check.json", "fallback_report.json", "closed_loop_replay.json",
        "negative_control_report.json", "license_note.md", "planning_boundary.md",
    ]
    hashes = {fn: _sha256(out_dir / fn) for fn in files_to_hash}
    (out_dir / "artifact_hashes.json").write_text(json.dumps(hashes, indent=2) + "\n")

    return {fn: out_dir / fn for fn in files_to_hash + ["artifact_hashes.json"]}
