"""AWS Lambda dispatch handler for the lightweight (stdlib) subcommands.

Single Lambda function that routes by ``event['action']`` to the
appropriate Python entrypoint. The biosymphony_ferm_doe package is
stdlib-only, so the deployment package is tiny (~50 MB) and cold start
is ~200 ms.

Event shape (POST /v1/{action} via API Gateway, or direct Lambda invoke):

    {
      "action": "validate" | "generate-design" | "analyze" | ...,
      "manifest": {...},                         // inline JSON
      "results": [{...}, ...] | null,            // optional rows for analyze / plan-wave2
      "args": {                                  // subcommand-specific kwargs
        "seed": 0,
        "alpha": 0.05,
        "sigma": 1.0,
        ...
      }
    }

Response:

    {
      "statusCode": 200,
      "body": "{...subcommand result JSON...}",
      "headers": {"Content-Type": "application/json"}
    }

The handler does not write to S3 directly; the caller can persist
manifests / results in S3 and pass them inline, or extend this dispatch
to accept ``manifest_s3_url`` and use boto3 to fetch.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 1_000_000
MAX_RESULT_ROWS = 1_000


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        body = _parse_body(event)
        action = body.get("action") or event.get("path", "").rsplit("/", 1)[-1]
        if not action:
            return _response(400, {"error": "missing_action"})
        result = _dispatch(action, body)
        return _response(200, result)
    except ValueError as exc:
        return _response(400, {"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        logger.exception("ferm-doe lambda dispatch failed")
        return _response(500, {"error": "internal_error", "request_id": getattr(context, "aws_request_id", None)})


def _parse_body(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body")
    if isinstance(body, str):
        if len(body.encode("utf-8")) > MAX_BODY_BYTES:
            raise ValueError("request_too_large")
        return json.loads(body)
    if isinstance(body, dict):
        return body
    if len(json.dumps(event, separators=(",", ":"), default=str).encode("utf-8")) > MAX_BODY_BYTES:
        raise ValueError("request_too_large")
    return event  # direct Lambda invoke (no API Gateway wrapper)


def _dispatch(action: str, body: dict[str, Any]) -> dict[str, Any]:
    manifest = body.get("manifest") or {}
    args = body.get("args") or {}
    results = body.get("results") or []
    _ensure_request_shape(manifest, args, results)

    if action == "validate":
        return _validate(manifest, args)
    if action == "audit":
        return _audit_inline(body)
    if action == "generate-design":
        from biosymphony_ferm_doe.doe_generators import generate_design
        return generate_design(manifest, seed=args.get("seed"))
    if action == "scale-recipe":
        from biosymphony_ferm_doe.scale_recipe import compute_scale_recipe
        return compute_scale_recipe(manifest)
    if action == "goals":
        from biosymphony_ferm_doe.goals import formulate_goals
        goals = formulate_goals(manifest)
        return goals or {"goals": None, "reason": "no_objective_bounds_declarable"}
    if action == "assay-power":
        from biosymphony_ferm_doe.adaptive import evaluate_assay_power
        return evaluate_assay_power(manifest, strict=bool(args.get("strict", False)))
    if action == "analyze":
        from biosymphony_ferm_doe.analysis import analyze_results
        return analyze_results(
            manifest, results,
            response_id=args.get("response_id"),
            seed=args.get("seed", 0),
            n_permutations=args.get("permutations", 1000),
            n_bootstrap=args.get("bootstrap", 500),
            significance_alpha=args.get("alpha", 0.05),
        )
    if action == "doe-power":
        from biosymphony_ferm_doe.doe_power import compute_doe_power
        return compute_doe_power(
            manifest,
            sigma=float(args.get("sigma")),
            alpha=args.get("alpha", 0.05),
            target_power=args.get("target_power", 0.8),
            seed=args.get("seed", 0),
        )
    if action == "recommend-family":
        from biosymphony_ferm_doe.family_recommender import recommend_family
        return recommend_family(
            manifest,
            budget=args.get("budget"),
            curvature_prior=args.get("curvature_prior", "unknown"),
            interactions_prior=args.get("interactions_prior", "unknown"),
        )
    if action == "bridge-qualification":
        from biosymphony_ferm_doe.bridge import compute_bridge_qualification
        return compute_bridge_qualification(
            manifest,
            from_arm_id=args.get("from_arm"),
            to_arm_id=args.get("to_arm"),
            n_replicates=args.get("replicates", 3),
            perturbation_pct=args.get("perturbation_pct"),
        )
    if action == "sampling-plan":
        from biosymphony_ferm_doe.sampling import compute_sampling_plan
        return compute_sampling_plan(
            manifest,
            run_duration_h=args.get("run_duration_h"),
            default_frequency_h=args.get("frequency_h", 4.0),
            default_sample_volume_ml=args.get("sample_volume_ml", 1.0),
        )
    if action == "cost-rollup":
        from biosymphony_ferm_doe.cost_rollup import compute_cost_rollup
        return compute_cost_rollup(
            manifest,
            per_run_cost=args.get("per_run_cost"),
            per_sample_cost=args.get("per_sample_cost"),
            per_volume_ml_cost=args.get("per_volume_ml_cost"),
            per_run_duration_h_cost=args.get("per_run_duration_h_cost"),
            wave2_runs_estimate=args.get("wave2_runs_estimate"),
            seed=args.get("seed", 0),
        )
    if action == "plan-wave2":
        return _plan_wave2_stdlib(manifest, results, args)

    raise ValueError(f"unknown_action_{action}")


def _ensure_request_shape(manifest: Any, args: Any, results: Any) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("manifest_must_be_object")
    if not isinstance(args, dict):
        raise ValueError("args_must_be_object")
    if not isinstance(results, list) or not all(isinstance(row, dict) for row in results):
        raise ValueError("results_must_be_list_of_objects")
    if len(results) > MAX_RESULT_ROWS:
        raise ValueError("too_many_result_rows")


def _validate(manifest: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    """Validate from an inline manifest.

    The library's ``validate_campaign`` reads from disk; we materialize the
    manifest into a temp dir and call it.
    """
    import tempfile
    from pathlib import Path

    from biosymphony_ferm_doe.validators import summarize, validate_campaign

    with tempfile.TemporaryDirectory() as tmp:
        campaign = Path(tmp)
        (campaign / "campaign_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = validate_campaign(campaign)
    return summarize(result) if args.get("summary") else result


def _audit_inline(body: dict[str, Any]) -> dict[str, Any]:
    """The audit subcommand walks the filesystem; not meaningful in Lambda.

    Returns a stub response advising the operator to run audit locally
    or against an S3 sync of the repo. Not exposing audit is intentional —
    it scans for unredacted paths and is a CI-time check, not a runtime check.
    """
    return {
        "status": "NOT_APPLICABLE",
        "reason": "audit_runs_against_local_filesystem_use_locally_or_in_ci",
    }


def _plan_wave2_stdlib(
    manifest: dict[str, Any],
    results: list[dict[str, Any]],
    args: dict[str, Any],
) -> dict[str, Any]:
    """Stdlib closed-loop follow-up plan inline.

    The library's plan_wave2 writes artifacts to disk. We materialize results
    to a temp file, run it, then read every artifact back into the response
    payload. Heavy responses are chunked by the API Gateway 6 MB body limit
    in practice — for typical campaigns (n_runs < 50, k < 10) the response is
    well under that. The BoTorch backend lives in the Modal scaffold, not
    here.
    """
    import csv
    import tempfile
    from pathlib import Path

    from biosymphony_ferm_doe.adaptive import plan_wave2

    with tempfile.TemporaryDirectory() as tmp:
        campaign = Path(tmp) / "campaign"
        campaign.mkdir()
        (campaign / "campaign_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        results_path = Path(tmp) / "results.csv"
        if results:
            fieldnames = list({k for row in results for k in row.keys()})
            with results_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for row in results:
                    writer.writerow({k: row.get(k, "") for k in fieldnames})
        out_dir = Path(tmp) / "wave2"
        plan = plan_wave2(
            campaign,
            results_path,
            out_dir,
            remaining_budget=args.get("remaining_budget"),
        )
        artifacts: dict[str, Any] = {}
        for artifact_name in plan.get("artifacts") or []:
            path = out_dir / artifact_name
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            artifacts[artifact_name] = text
    return {"plan": plan, "artifacts": artifacts}


def _response(status: int, body: Any) -> dict[str, Any]:
    return {
        "statusCode": status,
        "body": json.dumps(body, default=str),
        "headers": {"Content-Type": "application/json"},
    }
