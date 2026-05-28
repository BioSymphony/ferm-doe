"""Command line interface for BioSymphony Ferm DoE."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .adaptive_wave2 import plan_adaptive_wave2
from .analysis import analyze_results, render_analysis_markdown
from .bridge import compute_bridge_qualification, render_bridge_markdown
from .compiler import compile_campaign_state
from .contract import contract_self_check
from .cost_rollup import compute_cost_rollup, render_cost_rollup_markdown
from .doe import propose_candidate_designs
from .doe_power import compute_doe_power, render_doe_power_markdown
from .dossier import check_dossier, compile_dossier
from .family_recommender import recommend_family
from .goals import formulate_goals
from .ingest import ingest_wave_results
from .linear_dry_run import generate_issue_pack
from .readiness import score_campaign_readiness
from .sampling import compute_sampling_plan, render_sampling_markdown
from .scale_recipe import compute_scale_recipe, render_recipe_markdown
from .swarm import compile_swarm_plan
from .task_router import load_task_request, route_task_request
from .tournament import design_comparison, run_design_tournament
from .utilities.assay_power import run_assay_power_utility
from .utilities.augment_design import run_augment_design_utility
from .utilities.benchmark import run_benchmark_doe_utility
from .utilities.custom_optimal import run_custom_optimal_utility
from .utilities.deps import dependency_status
from .utilities.doe_compat import run_doe_export_utility
from .utilities.profiler import run_profiler_utility
from .utilities.simulate import run_simulate_design_utility


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ferm-doe", description="BioSymphony Ferm DoE local engine")
    sub = parser.add_subparsers(dest="command", required=True)

    compile_state = sub.add_parser("compile-state", help="Compile manifest into campaign state")
    compile_state.add_argument("--manifest", required=True)
    compile_state.add_argument("--out", required=True)
    compile_state.add_argument("--mode", action="append", default=[])
    compile_state.add_argument("--enable-swarm", action="store_true")

    readiness = sub.add_parser("score-readiness", aliases=["readiness"], help="Score campaign readiness")
    readiness.add_argument("--manifest", required=True)
    readiness.add_argument("--out")

    designs = sub.add_parser("propose-design", aliases=["propose-designs"], help="Generate candidate DOE designs")
    designs.add_argument("--manifest", required=True)
    designs.add_argument("--out", required=True)
    designs.add_argument("--run-budget", type=int)

    tournament = sub.add_parser("compare-designs", aliases=["tournament"], help="Run design tournament and adjudication")
    tournament.add_argument("--manifest", required=True)
    tournament.add_argument("--out", required=True)
    tournament.add_argument("--run-budget", type=int)

    dossier = sub.add_parser("compile-dossier", help="Compile complete Ferm DoE dossier")
    dossier.add_argument("--manifest", required=True)
    dossier.add_argument("--out", required=True)
    dossier.add_argument("--run-budget", type=int)
    dossier.add_argument("--enable-swarm", action="store_true")

    swarm = sub.add_parser("compile-swarm-plan", help="Compile optional Scientific Swarm planning artifacts")
    swarm.add_argument("--manifest", required=True)
    swarm.add_argument("--out", required=True)
    swarm.add_argument("--evidence-table", action="append", default=[])

    dossier_check = sub.add_parser("check-dossier", help="Validate complete Ferm DoE dossier")
    dossier_check.add_argument("path")
    dossier_check.add_argument("--out")

    contract_check = sub.add_parser("contract-self-check", aliases=["self-check"], help="Join dossier artifacts and audit claims")
    contract_check.add_argument("path")
    contract_check.add_argument("--require-execution", action="store_true")
    contract_check.add_argument("--out")

    task_request = sub.add_parser("route-task-request", aliases=["task-request"], help="Validate and route a task request contract")
    task_request.add_argument("path")
    task_request.add_argument("--out")

    issues = sub.add_parser("generate-issue-pack", aliases=["generate-issues"], help="Generate dry-run Linear issue bodies")
    issues.add_argument("--manifest", required=True)
    issues.add_argument("--out", required=True)
    issues.add_argument("--pack", action="append", default=[])

    ingest = sub.add_parser("ingest-results", help="Ingest completed batch results and recommend a follow-up action")
    ingest.add_argument("--campaign-state", required=True)
    ingest.add_argument("--results", required=True)
    ingest.add_argument("--out", required=True)
    ingest.add_argument("--selected-design")

    wave2 = sub.add_parser("plan-wave2", help="Plan the adaptive follow-up batch from joined first-batch results")
    wave2.add_argument("--campaign-state", required=True)
    wave2.add_argument("--results", required=True)
    wave2.add_argument("--out", required=True)
    wave2.add_argument("--selected-design")
    wave2.add_argument("--remaining-budget", type=int)
    wave2.add_argument("--backend", default="auto")

    scale_recipe = sub.add_parser("scale-recipe", help="Derive scale-bridge engineering recipe from scale_context")
    scale_recipe.add_argument("campaign", help="Campaign directory or manifest JSON")
    scale_recipe.add_argument("--out", required=True)
    scale_recipe.add_argument("--md-out")

    bridge = sub.add_parser("bridge-qualification", help="Generate bridge-qualification design rows")
    bridge.add_argument("campaign", help="Campaign directory or manifest JSON")
    bridge.add_argument("--out", required=True, help="CSV output path")
    bridge.add_argument("--md-out")
    bridge.add_argument("--json-out")
    bridge.add_argument("--from-arm")
    bridge.add_argument("--to-arm")
    bridge.add_argument("--replicates", type=int, default=3)
    bridge.add_argument("--perturbation-pct", type=float)

    goals = sub.add_parser("goals", help="Formulate response desirability goals")
    goals.add_argument("campaign", help="Campaign directory or manifest JSON")
    goals.add_argument("--out", required=True)

    sampling = sub.add_parser("sampling-plan", help="Generate response sampling schedule")
    sampling.add_argument("campaign", help="Campaign directory or manifest JSON")
    sampling.add_argument("--out", required=True, help="CSV output path")
    sampling.add_argument("--md-out")
    sampling.add_argument("--json-out")
    sampling.add_argument("--run-duration-h", type=float)
    sampling.add_argument("--frequency-h", type=float, default=4.0)
    sampling.add_argument("--sample-volume-ml", type=float, default=1.0)

    cost = sub.add_parser("cost-rollup", help="Roll up planning costs from resource_costs and sampling")
    cost.add_argument("campaign", help="Campaign directory or manifest JSON")
    cost.add_argument("--out")
    cost.add_argument("--md-out")
    cost.add_argument("--per-run-cost", type=float)
    cost.add_argument("--per-sample-cost", type=float)
    cost.add_argument("--per-volume-ml-cost", type=float)
    cost.add_argument("--per-run-duration-h-cost", type=float)
    cost.add_argument("--wave2-runs-estimate", type=int)
    cost.add_argument("--seed", type=int, default=0)

    doe_power = sub.add_parser("doe-power", help="Estimate design-level coefficient MDEs")
    doe_power.add_argument("campaign", help="Campaign directory or manifest JSON")
    doe_power.add_argument("--sigma", type=float, required=True)
    doe_power.add_argument("--alpha", type=float, default=0.05)
    doe_power.add_argument("--target-power", type=float, default=0.8)
    doe_power.add_argument("--seed", type=int, default=0)
    doe_power.add_argument("--out")
    doe_power.add_argument("--md-out")

    recommend = sub.add_parser("recommend-family", help="Recommend a DOE family from manifest factors and profiles")
    recommend.add_argument("campaign", help="Campaign directory or manifest JSON")
    recommend.add_argument("--out")
    recommend.add_argument("--budget", type=int)
    recommend.add_argument("--curvature-prior", default="unknown", choices=("yes", "no", "unknown"))
    recommend.add_argument("--interactions-prior", default="unknown", choices=("yes", "no", "unknown"))

    analyze = sub.add_parser("analyze", help="Analyze first-batch result rows with stdlib OLS")
    analyze.add_argument("campaign", help="Campaign directory or manifest JSON")
    analyze.add_argument("--results", required=True)
    analyze.add_argument("--out", required=True)
    analyze.add_argument("--md-out")
    analyze.add_argument("--response")
    analyze.add_argument("--seed", type=int, default=0)
    analyze.add_argument("--permutations", type=int, default=1000)
    analyze.add_argument("--bootstrap", type=int, default=500)
    analyze.add_argument("--alpha", type=float, default=0.05)

    utility = sub.add_parser("utility", help="Run optional reference DOE utilities")
    utility_sub = utility.add_subparsers(dest="utility_command", required=True)

    deps = utility_sub.add_parser("check-deps", help="Report optional utility dependency status")
    deps.add_argument("--out")

    custom = utility_sub.add_parser("custom-optimal", help="Run optional custom-optimal design utility")
    custom.add_argument("--manifest", required=True)
    custom.add_argument("--out", required=True)
    custom.add_argument("--run-budget", type=int)
    custom.add_argument("--criterion")
    custom.add_argument("--backend", default="auto")
    custom.add_argument("--fixed-runs")

    augment = utility_sub.add_parser("augment-design", help="Generate actual augment-design rows")
    augment.add_argument("--campaign-state", required=True)
    augment.add_argument("--results", required=True)
    augment.add_argument("--out", required=True)
    augment.add_argument("--remaining-budget", type=int)
    augment.add_argument("--criterion")
    augment.add_argument("--backend", default="auto")

    profiler = utility_sub.add_parser("profiler", help="Fit local profiler and operating-window report")
    profiler.add_argument("--campaign-state", required=True)
    profiler.add_argument("--results", required=True)
    profiler.add_argument("--out", required=True)
    profiler.add_argument("--backend", default="auto")
    profiler.add_argument("--grid-size", type=int, default=64)

    simulate = utility_sub.add_parser("simulate-design", help="Run deterministic design simulation and power proxy")
    simulate.add_argument("--manifest", required=True)
    simulate.add_argument("--out", required=True)
    simulate.add_argument("--run-budget", type=int)
    simulate.add_argument("--iterations", type=int, default=200)
    simulate.add_argument("--seed", type=int)
    simulate.add_argument("--effect-size", type=float, default=1.0)
    simulate.add_argument("--noise-sd", type=float, default=1.0)
    simulate.add_argument("--backend", default="auto")

    assay_power = utility_sub.add_parser("assay-power", help="Assess response-level assay power policy")
    assay_power.add_argument("--campaign-state", required=True)
    assay_power.add_argument("--out", required=True)
    assay_power.add_argument("--results")
    assay_power.add_argument("--backend", default="auto")
    assay_power.add_argument("--strict", action="store_true")

    doe_export = utility_sub.add_parser("doe-export", help="Export/import simple DOE CSV artifacts")
    doe_export.add_argument("--manifest", required=True)
    doe_export.add_argument("--out", required=True)
    doe_export.add_argument("--backend", default="auto")
    doe_export.add_argument("--import-factors")
    doe_export.add_argument("--import-design")
    doe_export.add_argument("--import-results")

    benchmark = utility_sub.add_parser("benchmark-doe", help="Run synthetic reference DOE benchmark harness")
    benchmark.add_argument("--manifest", required=True)
    benchmark.add_argument("--out", required=True)
    benchmark.add_argument("--backend", default="auto")

    args = parser.parse_args(argv)

    if args.command == "compile-state":
        state = compile_campaign_state(Path(args.manifest), Path(args.out), args.mode, enable_swarm=args.enable_swarm)
        print(json.dumps({"status": "OK", "campaign_id": state["campaign_id"], "out": args.out}, sort_keys=True))
    elif args.command in {"score-readiness", "readiness"}:
        result = score_campaign_readiness(Path(args.manifest), out_path=Path(args.out) if args.out else None)
        print(json.dumps({"status": result["status"], "score": result["score"]}, sort_keys=True))
    elif args.command in {"propose-design", "propose-designs"}:
        result = propose_candidate_designs(Path(args.manifest), out_dir=Path(args.out), run_budget=args.run_budget)
        print(json.dumps({"status": "OK", "candidate_count": result["candidate_count"]}, sort_keys=True))
    elif args.command in {"compare-designs", "tournament"}:
        result = run_design_tournament(Path(args.manifest), out_dir=Path(args.out), run_budget=args.run_budget)
        comparison = design_comparison(result)
        print(json.dumps({"status": result["verdict"], "selected_design_id": result["selected_design_id"], "compared": len(comparison["rows"])}, sort_keys=True))
    elif args.command == "compile-dossier":
        result = compile_dossier(Path(args.manifest), Path(args.out), args.run_budget, enable_swarm=args.enable_swarm)
        print(json.dumps({"status": result["readiness_status"], "selected_design_id": result["selected_design_id"]}, sort_keys=True))
    elif args.command == "compile-swarm-plan":
        result = compile_swarm_plan(Path(args.manifest), Path(args.out), force=True, evidence_tables=[Path(path) for path in args.evidence_table])
        print(json.dumps({"status": "OK", "campaign_id": result["campaign_id"], "artifacts": result["artifact_count"]}, sort_keys=True))
    elif args.command == "check-dossier":
        result = check_dossier(Path(args.path))
        if args.out:
            Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"status": result["status"], "errors": len(result["errors"])}, sort_keys=True))
        return 0 if result["status"] == "PASS" else 1
    elif args.command in {"contract-self-check", "self-check"}:
        result = contract_self_check(Path(args.path), require_execution=args.require_execution, write_outputs=True)
        if args.out:
            Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"status": result["status"], "errors": len(result["errors"]), "claim_level": result["claim_level"]}, sort_keys=True))
        return 0 if result["status"] == "PASS" else 1
    elif args.command in {"route-task-request", "task-request"}:
        result = route_task_request(load_task_request(Path(args.path)))
        if args.out:
            Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "task_class": result["classification"]["task_class"],
                    "recommended_issue_pack": result["routing"]["recommended_issue_pack"],
                    "recommended_lane": result["routing"]["recommended_lane"],
                    "errors": len(result["errors"]),
                },
                sort_keys=True,
            )
        )
        return 0 if result["status"] == "OK" else 1
    elif args.command in {"generate-issue-pack", "generate-issues"}:
        result = generate_issue_pack(Path(args.manifest), Path(args.out), args.pack)
        print(json.dumps({"status": "OK", "issues": len(result["issues"])}, sort_keys=True))
    elif args.command == "ingest-results":
        result = ingest_wave_results(
            Path(args.campaign_state),
            Path(args.results),
            Path(args.out),
            selected_design_path=Path(args.selected_design) if args.selected_design else None,
        )
        print(json.dumps({"status": "OK", "recommended_action": result["recommended_action"]}, sort_keys=True))
    elif args.command == "plan-wave2":
        result = plan_adaptive_wave2(
            Path(args.campaign_state),
            Path(args.results),
            Path(args.out),
            selected_design_path=Path(args.selected_design) if args.selected_design else None,
            remaining_budget=args.remaining_budget,
            backend=args.backend,
        )
        print(json.dumps({"status": "OK", "recommended_action": result["recommended_action"], "claim_level": result["claim_level"]}, sort_keys=True))
    elif args.command == "scale-recipe":
        manifest = _load_manifest_arg(args.campaign)
        recipe = compute_scale_recipe(manifest)
        _write_json_arg(args.out, recipe)
        if args.md_out:
            _write_text_arg(args.md_out, render_recipe_markdown(recipe))
        print(
            json.dumps(
                {
                    "claim_level": recipe["claim_level"],
                    "primary_criterion": recipe["primary_criterion"],
                    "criterion_match_status": recipe["criterion_match"]["status"],
                    "warnings": recipe["warnings"],
                },
                sort_keys=True,
            )
        )
    elif args.command == "bridge-qualification":
        manifest = _load_manifest_arg(args.campaign)
        plan = compute_bridge_qualification(
            manifest,
            from_arm_id=args.from_arm,
            to_arm_id=args.to_arm,
            n_replicates=args.replicates,
            perturbation_pct=args.perturbation_pct,
        )
        _write_rows_csv_arg(args.out, plan["qualification_design"])
        if args.md_out:
            _write_text_arg(args.md_out, render_bridge_markdown(plan))
        if args.json_out:
            _write_json_arg(args.json_out, plan)
        print(
            json.dumps(
                {
                    "claim_level": plan["claim_level"],
                    "from_arm": plan["from_arm"]["arm_id"],
                    "to_arm": plan["to_arm"]["arm_id"],
                    "criterion": plan["criterion"],
                    "n_runs": plan["n_runs"],
                },
                sort_keys=True,
            )
        )
    elif args.command == "goals":
        manifest = _load_manifest_arg(args.campaign)
        goals_payload = formulate_goals(manifest)
        if goals_payload is None:
            payload = {
                "goals": None,
                "reason": "no_objective_bounds_declarable",
                "non_claim": "Goals require response objective fields or numeric response-scoped decision-rule thresholds.",
            }
            summary = {"claim_level": "no_goals", "n_objectives": 0, "reason": payload["reason"]}
        else:
            payload = goals_payload
            summary = {
                "claim_level": goals_payload["claim_level"],
                "n_objectives": len(goals_payload.get("objectives") or []),
            }
        _write_json_arg(args.out, payload)
        print(json.dumps(summary, sort_keys=True))
    elif args.command == "sampling-plan":
        manifest = _load_manifest_arg(args.campaign)
        plan = compute_sampling_plan(
            manifest,
            run_duration_h=args.run_duration_h,
            default_frequency_h=args.frequency_h,
            default_sample_volume_ml=args.sample_volume_ml,
        )
        _write_rows_csv_arg(
            args.out,
            plan["samples"],
            headers=["sample_id", "time_h", "response_id", "phase", "sample_volume_ml", "rationale"],
        )
        if args.md_out:
            _write_text_arg(args.md_out, render_sampling_markdown(plan))
        if args.json_out:
            _write_json_arg(args.json_out, plan)
        print(
            json.dumps(
                {
                    "claim_level": plan["claim_level"],
                    "run_duration_h": plan["run_duration_h"],
                    "n_samples": plan["totals"]["n_samples"],
                    "total_volume_ml": plan["totals"]["total_volume_ml"],
                },
                sort_keys=True,
            )
        )
    elif args.command == "cost-rollup":
        manifest = _load_manifest_arg(args.campaign)
        rollup = compute_cost_rollup(
            manifest,
            per_run_cost=args.per_run_cost,
            per_sample_cost=args.per_sample_cost,
            per_volume_ml_cost=args.per_volume_ml_cost,
            per_run_duration_h_cost=args.per_run_duration_h_cost,
            wave2_runs_estimate=args.wave2_runs_estimate,
            seed=args.seed,
        )
        if args.out:
            _write_json_arg(args.out, rollup)
        if args.md_out:
            _write_text_arg(args.md_out, render_cost_rollup_markdown(rollup))
        print(
            json.dumps(
                {
                    "claim_level": rollup["claim_level"],
                    "currency": rollup["currency"],
                    "wave1_total": rollup["wave1_total"],
                    "wave2_total": rollup["wave2_total"],
                    "campaign_total": rollup["campaign_total"],
                },
                sort_keys=True,
            )
        )
    elif args.command == "doe-power":
        manifest = _load_manifest_arg(args.campaign)
        result = compute_doe_power(
            manifest,
            sigma=args.sigma,
            alpha=args.alpha,
            target_power=args.target_power,
            seed=args.seed,
        )
        if args.out:
            _write_json_arg(args.out, result)
        if args.md_out:
            _write_text_arg(args.md_out, render_doe_power_markdown(result))
        print(
            json.dumps(
                {
                    "claim_level": result.get("claim_level"),
                    "n_runs": result.get("n_runs"),
                    "n_parameters": result.get("n_parameters"),
                    "df_residual": result.get("df_residual"),
                    "sigma": result.get("sigma"),
                    "short_circuit_reason": result.get("short_circuit_reason"),
                },
                sort_keys=True,
            )
        )
    elif args.command == "recommend-family":
        manifest = _load_manifest_arg(args.campaign)
        recommendation = recommend_family(
            manifest,
            budget=args.budget,
            curvature_prior=args.curvature_prior,
            interactions_prior=args.interactions_prior,
        )
        if args.out:
            _write_json_arg(args.out, recommendation)
        print(json.dumps(recommendation, sort_keys=True))
    elif args.command == "analyze":
        manifest = _load_manifest_arg(args.campaign)
        analysis = analyze_results(
            manifest,
            _read_csv_rows_arg(args.results),
            response_id=args.response,
            seed=args.seed,
            n_permutations=args.permutations,
            n_bootstrap=args.bootstrap,
            significance_alpha=args.alpha,
        )
        _write_json_arg(args.out, analysis)
        if args.md_out:
            _write_text_arg(args.md_out, render_analysis_markdown(analysis))
        print(
            json.dumps(
                {
                    "claim_level": analysis.get("claim_level"),
                    "response_id": analysis.get("response_id"),
                    "n_runs_used": analysis.get("n_runs_used"),
                    "active_factor_ids": analysis.get("active_factor_ids", []),
                    "short_circuit_reason": analysis.get("short_circuit_reason"),
                },
                sort_keys=True,
            )
        )
    elif args.command == "utility":
        return run_utility_command(args)
    else:  # pragma: no cover
        parser.error(f"unknown command: {args.command}")
    return 0


def run_utility_command(args: argparse.Namespace) -> int:
    if args.utility_command == "check-deps":
        result = dependency_status()
        if args.out:
            Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        available = [name for name, item in result["backends"].items() if item["available"]]
        print(json.dumps({"status": "OK", "available": available}, sort_keys=True))
        return 0
    if args.utility_command == "custom-optimal":
        result = run_custom_optimal_utility(
            Path(args.manifest),
            Path(args.out),
            run_budget=args.run_budget,
            criterion=args.criterion,
            backend=args.backend,
            fixed_runs_path=Path(args.fixed_runs) if args.fixed_runs else None,
        )
        print(json.dumps({"status": "OK", "rows": len(result["rows"]), "criterion": result["criterion"]}, sort_keys=True))
        return 0
    if args.utility_command == "augment-design":
        result = run_augment_design_utility(
            Path(args.campaign_state),
            Path(args.results),
            Path(args.out),
            remaining_budget=args.remaining_budget,
            criterion=args.criterion,
            backend=args.backend,
        )
        print(json.dumps({"status": "OK", "rows": result["augment_run_count"], "recommended_action": result["recommended_action"]}, sort_keys=True))
        return 0
    if args.utility_command == "profiler":
        result = run_profiler_utility(Path(args.campaign_state), Path(args.results), Path(args.out), backend=args.backend, grid_size=args.grid_size)
        print(json.dumps({"status": "OK", "training_rows": result["training_rows"], "operating_window_count": result["operating_window_count"]}, sort_keys=True))
        return 0
    if args.utility_command == "simulate-design":
        result = run_simulate_design_utility(
            Path(args.manifest),
            Path(args.out),
            run_budget=args.run_budget,
            iterations=args.iterations,
            seed=args.seed,
            effect_size=args.effect_size,
            noise_sd=args.noise_sd,
            backend=args.backend,
        )
        print(json.dumps({"status": "OK", "best_design_id": result["best_design_id"], "items": len(result["items"])}, sort_keys=True))
        return 0
    if args.utility_command == "assay-power":
        result = run_assay_power_utility(
            Path(args.campaign_state),
            Path(args.out),
            results_path=Path(args.results) if args.results else None,
            backend=args.backend,
            strict=args.strict,
        )
        print(json.dumps({"status": result["status"], "primary_status": result["primary_status"], "score": result["score"]}, sort_keys=True))
        return 0 if result["status"] != "FAIL" else 1
    if args.utility_command == "doe-export":
        result = run_doe_export_utility(
            Path(args.manifest),
            Path(args.out),
            backend=args.backend,
            import_factors=Path(args.import_factors) if args.import_factors else None,
            import_design=Path(args.import_design) if args.import_design else None,
            import_results=Path(args.import_results) if args.import_results else None,
        )
        print(json.dumps({"status": "OK", "selected_design_id": result["selected_design_id"], "exported_files": len(result["exported_files"])}, sort_keys=True))
        return 0
    if args.utility_command == "benchmark-doe":
        result = run_benchmark_doe_utility(Path(args.manifest), Path(args.out), backend=args.backend)
        print(json.dumps({"status": result["status"], "checks": len(result["checks"])}, sort_keys=True))
        return 0 if result["status"] == "PASS" else 1
    raise ValueError(f"unknown utility command: {args.utility_command}")


def _load_manifest_arg(raw_path: str) -> dict[str, object]:
    path = Path(raw_path)
    manifest_path = path / "campaign_manifest.json" if path.is_dir() else path
    data = json.loads(manifest_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"expected manifest JSON object: {manifest_path}")
    return data


def _write_json_arg(raw_path: str, payload: object) -> None:
    path = Path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")


def _write_text_arg(raw_path: str, text: str) -> None:
    path = Path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _read_csv_rows_arg(raw_path: str) -> list[dict[str, str]]:
    with Path(raw_path).open(newline="") as handle:
        return list(csv.DictReader(handle))


def _write_rows_csv_arg(
    raw_path: str,
    rows: list[dict[str, object]],
    headers: list[str] | None = None,
) -> None:
    path = Path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if headers is None:
        headers = []
        for row in rows:
            for key in row:
                if key not in headers:
                    headers.append(key)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
