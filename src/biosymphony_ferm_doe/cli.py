"""Public CLI for BioSymphony Ferm DoE."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import __version__
from .adaptive import evaluate_assay_power, load_manifest, plan_wave2
from .analysis import analyze_results, render_analysis_markdown
from .bridge import compute_bridge_qualification, render_bridge_markdown
from .campaign_inspector import catalog_campaigns, inspect_campaign
from .contracts import check_dossier_contract
from .cost_rollup import compute_cost_rollup, render_cost_rollup_markdown
from .doe_generators import generate_design
from .doe_power import compute_doe_power, render_doe_power_markdown
from .doctor import run_doctor
from .family_recommender import recommend_family
from .finalize import compose_run_packet, render_run_packet_markdown
from .goals import formulate_goals
from .orchestration_brief import build_agent_brief, render_agent_brief_markdown
from .sampling import compute_sampling_plan, render_sampling_markdown
from .scale_recipe import compute_scale_recipe, render_recipe_markdown
from .task_request import load_task_request, validate_task_request
from .validators import audit_public_tree, summarize, validate_campaign


def _emit(payload: dict, out_path: str | None) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True)
    if out_path:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


_KNOWN_COMMANDS = {
    "analyze",
    "agent-brief",
    "assay-power",
    "audit",
    "bridge-qualification",
    "brief",
    "check-dossier",
    "cost-rollup",
    "catalog",
    "doctor",
    "doe-power",
    "engine",
    "finalize",
    "generate-design",
    "goals",
    "inspect",
    "inspect-campaign",
    "list-campaigns",
    "plan-wave2",
    "recommend-family",
    "sampling-plan",
    "scale-recipe",
    "tool-registry",
    "validate",
    "validate-task-request",
    "-h",
    "--help",
    "--version",
}


def _normalize_argv(argv: list[str] | None) -> list[str] | None:
    if not argv:
        return ["validate"]
    if argv and argv[0] not in _KNOWN_COMMANDS:
        return ["validate", *argv]
    return argv


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = _normalize_argv(argv)
    parser = argparse.ArgumentParser(prog="ferm-doe", description="Validate, audit, or plan public-safe Ferm DoE artifacts.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    validate_parser = subparsers.add_parser("validate", help="Validate a campaign directory.")
    validate_parser.add_argument("example_dir", nargs="?", default="examples/demo-xylanase-public", help="Campaign directory to validate.")
    validate_parser.add_argument("--summary", action="store_true", help="Emit a short summary instead of the full check list.")
    validate_parser.add_argument("--out", dest="out_path", default=None, help="Write JSON to this file instead of stdout.")

    audit_parser = subparsers.add_parser("audit", help="Scan a repo tree for public-safety blockers.")
    audit_parser.add_argument("root", nargs="?", default=".", help="Repository root to audit.")
    audit_parser.add_argument("--out", dest="out_path", default=None, help="Write JSON to this file instead of stdout.")

    doctor_parser = subparsers.add_parser("doctor", help="Report repo capability and optional backend readiness.")
    doctor_parser.add_argument("--root", default=".", help="Repository root to inspect.")
    doctor_parser.add_argument("--live-imports", action="store_true", help="Attempt live imports for adaptive evaluation backends.")
    doctor_parser.add_argument("--fail-on-stale", action="store_true", help="Treat stale tool-registry checks as failures.")
    doctor_parser.add_argument("--out", dest="out_path", default=None, help="Write JSON to this file instead of stdout.")

    inspect_parser = subparsers.add_parser("inspect-campaign", aliases=["inspect"], help="Summarize a campaign directory and suggested next commands.")
    inspect_parser.add_argument("example_dir", nargs="?", default="examples/demo-pb-screening-public", help="Campaign directory to inspect.")
    inspect_parser.add_argument("--out", dest="out_path", default=None, help="Write JSON to this file instead of stdout.")

    catalog_parser = subparsers.add_parser("list-campaigns", aliases=["catalog"], help="Catalog campaign manifests and capabilities under a root.")
    catalog_parser.add_argument("root", nargs="?", default="examples", help="Root directory or manifest to catalog.")
    catalog_parser.add_argument("--out", dest="out_path", default=None, help="Write JSON to this file instead of stdout.")

    brief_parser = subparsers.add_parser("agent-brief", aliases=["brief"], help="Build an agent kickoff brief for orchestration.")
    brief_parser.add_argument("example_dir", nargs="?", default="examples/demo-pb-screening-public", help="Campaign directory to brief.")
    brief_parser.add_argument("--goal", default="", help="Optional user goal text to include in the brief.")
    brief_parser.add_argument("--compute-policy", choices=("local-only", "local-first", "cloud-prep", "cloud-allowed"), default="local-first")
    brief_parser.add_argument("--tracker", choices=("none", "generic", "linear"), default="generic")
    brief_parser.add_argument("--out", dest="out_path", default=None, help="Write JSON to this file instead of stdout.")
    brief_parser.add_argument("--md-out", dest="md_out", default=None, help="Optional Markdown brief path.")

    task_parser = subparsers.add_parser("validate-task-request", help="Validate a public-safe task_request JSON contract.")
    task_parser.add_argument("path", help="Path to task_request JSON.")
    task_parser.add_argument("--out", dest="out_path", default=None, help="Write JSON to this file instead of stdout.")

    dossier_parser = subparsers.add_parser("check-dossier", help="Check the compact public dossier contract surface.")
    dossier_parser.add_argument("path", help="Campaign or dossier directory to check.")
    dossier_parser.add_argument("--out", dest="out_path", default=None, help="Write JSON to this file instead of stdout.")

    engine_parser = subparsers.add_parser("engine", help="Run the full dossier/campaign engine subcommands.")
    engine_parser.add_argument("engine_args", nargs=argparse.REMAINDER, help="Arguments passed to biosymphony_ferm_doe.engine_cli.")

    tool_registry_parser = subparsers.add_parser("tool-registry", help="Validate the curated external-tool registry at docs/tool-registry.json.")
    tool_registry_parser.add_argument("path", nargs="?", default="docs/tool-registry.json", help="Registry path (default: docs/tool-registry.json).")
    tool_registry_parser.add_argument("--out", dest="out_path", default=None, help="Optional JSON report path.")
    tool_registry_parser.add_argument("--md-out", dest="md_out", default=None, help="Optional Markdown summary path.")
    tool_registry_parser.add_argument("--pyproject", default=None, help="Optional pyproject.toml path to enforce against.")
    tool_registry_parser.add_argument("--noxfile", default=None, help="Optional noxfile.py path to enforce declared lanes against.")
    tool_registry_parser.add_argument("--repo-root", dest="repo_root", default=None, help="Optional repository root for relative lane paths.")
    tool_registry_parser.add_argument("--fail-on-stale", dest="fail_on_stale", action="store_true", help="Treat stale last_checked values as errors.")

    assay_parser = subparsers.add_parser("assay-power", help="Evaluate response-level assay-power policy.")
    assay_parser.add_argument("example_dir", nargs="?", default="examples/demo-xylanase-public", help="Campaign directory to evaluate.")
    assay_parser.add_argument("--strict", action="store_true", help="Treat missing assay-power policy as a failure.")
    assay_parser.add_argument("--out", dest="out_path", default=None, help="Write JSON to this file instead of stdout.")

    wave2_parser = subparsers.add_parser("plan-wave2", help="Plan the follow-up batch from first-batch result rows.")
    wave2_parser.add_argument("example_dir", help="Campaign directory containing campaign_manifest.json.")
    wave2_parser.add_argument("--results", required=True, help="First-batch results CSV.")
    wave2_parser.add_argument("--out-dir", required=True, help="Directory where follow-up artifacts will be written.")
    wave2_parser.add_argument("--selected-design", default=None, help="Optional selected first-batch design CSV for presence checking.")
    wave2_parser.add_argument("--remaining-budget", type=int, default=None, help="Optional maximum planned augment rows.")
    wave2_parser.add_argument("--backend", default="stdlib", choices=("stdlib", "botorch"), help="Follow-up backend: stdlib closed-loop or BoTorch BO.")
    wave2_parser.add_argument("--acquisition", default="qei", choices=("qei", "qucb"), help="BoTorch acquisition function (used only when --backend botorch).")
    wave2_parser.add_argument("--bo-n-candidates", type=int, default=3, help="Number of BO candidates to emit (used only when --backend botorch).")

    design_parser = subparsers.add_parser("generate-design", help="Generate a first-batch design from the campaign manifest.")
    design_parser.add_argument("example_dir", help="Campaign directory containing campaign_manifest.json.")
    design_parser.add_argument("--out", dest="out_path", required=True, help="Path to write the design CSV.")
    design_parser.add_argument("--metadata-out", dest="metadata_out", default=None, help="Optional path to write the design metadata JSON.")
    design_parser.add_argument("--seed", type=int, default=None, help="Optional RNG seed for randomized order and stochastic constructions.")

    recipe_parser = subparsers.add_parser("scale-recipe", help="Derive an engineering recipe at to_scale from the manifest's scale_context.")
    recipe_parser.add_argument("example_dir", help="Campaign directory containing campaign_manifest.json.")
    recipe_parser.add_argument("--out", dest="out_path", required=True, help="Path to write the scale recipe JSON.")
    recipe_parser.add_argument("--md-out", dest="md_out", default=None, help="Optional path to write a markdown rendering of the recipe.")

    goals_parser = subparsers.add_parser("goals", help="Formulate Derringer-Suich desirability goals from the manifest's responses + decision_rules.")
    goals_parser.add_argument("example_dir", help="Campaign directory containing campaign_manifest.json.")
    goals_parser.add_argument("--out", dest="out_path", required=True, help="Path to write the goals JSON.")

    cost_parser = subparsers.add_parser("cost-rollup", help="Roll up first-batch + sampling + follow-up estimate into a planning budget.")
    cost_parser.add_argument("example_dir", help="Campaign directory containing campaign_manifest.json.")
    cost_parser.add_argument("--out", dest="out_path", default=None, help="Optional path to write the rollup JSON.")
    cost_parser.add_argument("--md-out", dest="md_out", default=None, help="Optional path to write a markdown rendering.")
    cost_parser.add_argument("--per-run-cost", type=float, default=None, help="Override manifest's resource_costs.per_run_cost.")
    cost_parser.add_argument("--per-sample-cost", type=float, default=None, help="Override manifest's resource_costs.per_sample_cost.")
    cost_parser.add_argument("--per-volume-ml-cost", type=float, default=None, help="Override manifest's resource_costs.per_volume_ml_cost.")
    cost_parser.add_argument("--per-run-duration-h-cost", type=float, default=None, help="Override manifest's resource_costs.per_run_duration_h_cost.")
    cost_parser.add_argument("--wave2-runs-estimate", type=int, default=None, help="Override manifest's resource_costs.wave2_runs_estimate.")
    cost_parser.add_argument("--seed", type=int, default=0, help="RNG seed for design generation when n_runs is not declared.")

    doe_power_parser = subparsers.add_parser("doe-power", help="Per-coefficient MDE from the design matrix at target power.")
    doe_power_parser.add_argument("example_dir", help="Campaign directory containing campaign_manifest.json.")
    doe_power_parser.add_argument("--out", dest="out_path", default=None, help="Optional path to write the result JSON.")
    doe_power_parser.add_argument("--md-out", dest="md_out", default=None, help="Optional path to write a markdown rendering.")
    doe_power_parser.add_argument("--sigma", type=float, required=True, help="Residual standard deviation in the response's units.")
    doe_power_parser.add_argument("--alpha", type=float, default=0.05, help="Significance threshold (default: 0.05).")
    doe_power_parser.add_argument("--target-power", type=float, default=0.8, help="Target statistical power (default: 0.8).")
    doe_power_parser.add_argument("--seed", type=int, default=0, help="RNG seed for design generation.")

    sampling_parser = subparsers.add_parser("sampling-plan", help="Generate a per-sample schedule for fed-batch / perfusion runs.")
    sampling_parser.add_argument("example_dir", help="Campaign directory containing campaign_manifest.json.")
    sampling_parser.add_argument("--out", dest="out_path", required=True, help="Path to write the sampling schedule CSV.")
    sampling_parser.add_argument("--md-out", dest="md_out", default=None, help="Optional path to write a markdown rendering.")
    sampling_parser.add_argument("--json-out", dest="json_out", default=None, help="Optional path to write the full plan JSON sidecar.")
    sampling_parser.add_argument("--run-duration-h", dest="run_duration_h", type=float, default=None, help="Override total run duration in hours.")
    sampling_parser.add_argument("--frequency-h", dest="frequency_h", type=float, default=4.0, help="Default sampling frequency for unconfigured responses (default: 4 h).")
    sampling_parser.add_argument("--sample-volume-ml", dest="sample_volume_ml", type=float, default=1.0, help="Default sample volume for unconfigured responses (default: 1 mL).")

    bridge_parser = subparsers.add_parser("bridge-qualification", help="Generate qualification design rows that bridge from_arm to to_arm.")
    bridge_parser.add_argument("example_dir", help="Campaign directory containing campaign_manifest.json.")
    bridge_parser.add_argument("--out", dest="out_path", required=True, help="Path to write the qualification design CSV.")
    bridge_parser.add_argument("--md-out", dest="md_out", default=None, help="Optional path to write a markdown rendering.")
    bridge_parser.add_argument("--json-out", dest="json_out", default=None, help="Optional path to write the full plan JSON sidecar.")
    bridge_parser.add_argument("--from-arm", dest="from_arm", default=None, help="Reference arm id; defaults to the bridge_to target on the to_arm.")
    bridge_parser.add_argument("--to-arm", dest="to_arm", default=None, help="Qualification arm id; defaults to the first arm with a bridge_to.")
    bridge_parser.add_argument("--replicates", type=int, default=3, help="Number of recipe-matched center-point replicates.")
    bridge_parser.add_argument("--perturbation-pct", type=float, default=None, help="Optional ± perturbation percent on transferable factors.")

    rec_parser = subparsers.add_parser("recommend-family", help="Suggest a DoE family from manifest factors + profiles + priors.")
    rec_parser.add_argument("example_dir", help="Campaign directory containing campaign_manifest.json.")
    rec_parser.add_argument("--out", dest="out_path", default=None, help="Optional path to write the recommendation JSON.")
    rec_parser.add_argument("--budget", type=int, default=None, help="Optional run-count cap.")
    rec_parser.add_argument("--curvature-prior", default="unknown", choices=("yes", "no", "unknown"), help="Operator hint about curvature.")
    rec_parser.add_argument("--interactions-prior", default="unknown", choices=("yes", "no", "unknown"), help="Operator hint about interactions.")

    finalize_parser = subparsers.add_parser("finalize", help="Compose every available artifact into one shippable run-packet markdown + JSON.")
    finalize_parser.add_argument("example_dir", help="Campaign directory containing campaign_manifest.json.")
    finalize_parser.add_argument("--out", dest="out_path", required=True, help="Path to write the run packet markdown.")
    finalize_parser.add_argument("--json-out", dest="json_out", default=None, help="Optional path to write the run packet JSON sidecar.")
    finalize_parser.add_argument("--results", default=None, help="Optional first-batch results CSV; when provided the analysis section runs.")
    finalize_parser.add_argument("--seed", type=int, default=0, help="RNG seed for analysis inference.")

    analyze_parser = subparsers.add_parser("analyze", help="Fit OLS to first-batch results, emit effect estimates with permutation p-values and bootstrap CIs.")
    analyze_parser.add_argument("example_dir", help="Campaign directory containing campaign_manifest.json.")
    analyze_parser.add_argument("--results", required=True, help="First-batch results CSV.")
    analyze_parser.add_argument("--out", dest="out_path", required=True, help="Path to write the analysis JSON.")
    analyze_parser.add_argument("--md-out", dest="md_out", default=None, help="Optional path to write a markdown rendering.")
    analyze_parser.add_argument("--response", default=None, help="Response id to analyze (default: first assayed response).")
    analyze_parser.add_argument("--seed", type=int, default=0, help="RNG seed for permutation and bootstrap inference.")
    analyze_parser.add_argument("--permutations", type=int, default=1000, help="Number of permutation draws (default: 1000).")
    analyze_parser.add_argument("--bootstrap", type=int, default=500, help="Number of bootstrap draws for CIs (default: 500).")
    analyze_parser.add_argument("--alpha", type=float, default=0.05, help="Significance threshold (default: 0.05).")

    args = parser.parse_args(argv)

    if args.command in {None, "validate"}:
        result = validate_campaign(Path(args.example_dir))
        payload = summarize(result) if getattr(args, "summary", False) else result
        _emit(payload, getattr(args, "out_path", None))
        return 1 if result["error_count"] else 0
    if args.command == "audit":
        result = audit_public_tree(Path(args.root))
        _emit(result, getattr(args, "out_path", None))
        return 1 if result["issue_count"] else 0
    if args.command == "doctor":
        result = run_doctor(Path(args.root), live_imports=args.live_imports, fail_on_stale=args.fail_on_stale)
        _emit(result, getattr(args, "out_path", None))
        return 1 if result["status"] == "FAIL" else 0
    if args.command in {"inspect-campaign", "inspect"}:
        result = inspect_campaign(Path(args.example_dir), command_style="public")
        _emit(result, getattr(args, "out_path", None))
        return 0
    if args.command in {"list-campaigns", "catalog"}:
        result = catalog_campaigns(Path(args.root), command_style="public")
        _emit(result, getattr(args, "out_path", None))
        return 0
    if args.command in {"agent-brief", "brief"}:
        result = build_agent_brief(
            Path(args.example_dir),
            goal=args.goal,
            command_style="public",
            compute_policy=args.compute_policy,
            tracker=args.tracker,
        )
        if args.md_out:
            md_path = Path(args.md_out)
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text(render_agent_brief_markdown(result) + "\n", encoding="utf-8")
        _emit(result, getattr(args, "out_path", None))
        return 0
    if args.command == "validate-task-request":
        result = validate_task_request(load_task_request(Path(args.path)))
        _emit(result, getattr(args, "out_path", None))
        return 1 if result["error_count"] else 0
    if args.command == "check-dossier":
        result = check_dossier_contract(Path(args.path))
        _emit(result, getattr(args, "out_path", None))
        return 1 if result["error_count"] else 0
    if args.command == "engine":
        from .engine_cli import main as engine_main

        return engine_main(args.engine_args)
    if args.command == "tool-registry":
        from .tool_registry import main as tool_registry_main

        forwarded: list[str] = [args.path]
        if args.out_path:
            forwarded += ["--out", args.out_path]
        if args.md_out:
            forwarded += ["--md-out", args.md_out]
        if args.pyproject:
            forwarded += ["--pyproject", args.pyproject]
        if args.noxfile:
            forwarded += ["--noxfile", args.noxfile]
        if args.repo_root:
            forwarded += ["--repo-root", args.repo_root]
        if args.fail_on_stale:
            forwarded += ["--fail-on-stale"]
        return tool_registry_main(forwarded)
    if args.command == "assay-power":
        result = evaluate_assay_power(load_manifest(Path(args.example_dir)), strict=args.strict)
        _emit(result, getattr(args, "out_path", None))
        return 1 if result["status"] == "FAIL" else 0
    if args.command == "plan-wave2":
        if args.backend == "botorch":
            from .adapters import get_adapter

            adapter = get_adapter("botorch")
            if adapter is None:
                parser.error("BoTorch adapter not available. Install with `pip install biosymphony-ferm-doe[botorch]`.")
            manifest = load_manifest(Path(args.example_dir))
            usable_rows = _read_csv_rows(Path(args.results))
            bo_result = adapter.plan_bo_wave2(
                manifest,
                usable_rows,
                n_candidates=args.bo_n_candidates,
                acquisition=args.acquisition,
            )
            out_dir = Path(args.out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "bo_wave2_plan.json").write_text(
                json.dumps(bo_result, indent=2, sort_keys=True, default=str) + "\n",
                encoding="utf-8",
            )
            if bo_result.get("candidate_design"):
                rows = bo_result["candidate_design"]
                fieldnames = sorted({k for row in rows for k in row.keys()})
                with (out_dir / "bo_wave2_design.csv").open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in rows:
                        writer.writerow({k: row.get(k, "") for k in fieldnames})
            print(json.dumps(bo_result, indent=2, sort_keys=True, default=str))
            return 0
        result = plan_wave2(
            Path(args.example_dir),
            Path(args.results),
            Path(args.out_dir),
            selected_design_path=Path(args.selected_design) if args.selected_design else None,
            remaining_budget=args.remaining_budget,
        )
        _emit(result, None)
        return 0
    if args.command == "cost-rollup":
        manifest = load_manifest(Path(args.example_dir))
        rollup = compute_cost_rollup(
            manifest,
            per_run_cost=args.per_run_cost,
            per_sample_cost=args.per_sample_cost,
            per_volume_ml_cost=args.per_volume_ml_cost,
            per_run_duration_h_cost=args.per_run_duration_h_cost,
            wave2_runs_estimate=args.wave2_runs_estimate,
            seed=args.seed,
        )
        if args.out_path:
            out_path = Path(args.out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.md_out:
            md_path = Path(args.md_out)
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text(render_cost_rollup_markdown(rollup), encoding="utf-8")
        summary = {
            "claim_level": rollup["claim_level"],
            "currency": rollup["currency"],
            "wave1_total": rollup["wave1_total"],
            "wave2_total": rollup["wave2_total"],
            "campaign_total": rollup["campaign_total"],
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "doe-power":
        manifest = load_manifest(Path(args.example_dir))
        result = compute_doe_power(
            manifest,
            sigma=args.sigma,
            alpha=args.alpha,
            target_power=args.target_power,
            seed=args.seed,
        )
        if args.out_path:
            out_path = Path(args.out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.md_out:
            md_path = Path(args.md_out)
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text(render_doe_power_markdown(result), encoding="utf-8")
        summary = {
            "claim_level": result.get("claim_level"),
            "n_runs": result.get("n_runs"),
            "n_parameters": result.get("n_parameters"),
            "df_residual": result.get("df_residual"),
            "sigma": result.get("sigma"),
            "alpha": result.get("alpha"),
            "target_power": result.get("target_power"),
            "n_terms_passing_expected_effect": result.get("n_terms_passing_expected_effect"),
            "short_circuit_reason": result.get("short_circuit_reason"),
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "sampling-plan":
        manifest = load_manifest(Path(args.example_dir))
        plan = compute_sampling_plan(
            manifest,
            run_duration_h=args.run_duration_h,
            default_frequency_h=args.frequency_h,
            default_sample_volume_ml=args.sample_volume_ml,
        )
        out_path = Path(args.out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = ["sample_id", "time_h", "response_id", "phase", "sample_volume_ml", "rationale"]
        with out_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for sample in plan["samples"]:
                writer.writerow({k: sample.get(k, "") for k in fieldnames})
        if args.md_out:
            md_path = Path(args.md_out)
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text(render_sampling_markdown(plan), encoding="utf-8")
        if args.json_out:
            json_path = Path(args.json_out)
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json.dumps(plan, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        summary = {
            "claim_level": plan["claim_level"],
            "run_duration_h": plan["run_duration_h"],
            "n_samples": plan["totals"]["n_samples"],
            "total_volume_ml": plan["totals"]["total_volume_ml"],
            "samples_per_response": plan["totals"]["samples_per_response"],
            "schedule_csv": str(out_path),
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "bridge-qualification":
        manifest = load_manifest(Path(args.example_dir))
        plan = compute_bridge_qualification(
            manifest,
            from_arm_id=args.from_arm,
            to_arm_id=args.to_arm,
            n_replicates=args.replicates,
            perturbation_pct=args.perturbation_pct,
        )
        out_path = Path(args.out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        rows = plan["qualification_design"]
        all_keys: list[str] = []
        seen: set[str] = set()
        leading = ["design_run_id", "arm_id", "row_kind", "replicate_group", "criterion", "criterion_target"]
        for key in leading:
            if key not in seen:
                all_keys.append(key)
                seen.add(key)
        for row in rows:
            for key in row:
                if key not in seen:
                    all_keys.append(key)
                    seen.add(key)
        with out_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=all_keys)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in all_keys})
        if args.md_out:
            md_path = Path(args.md_out)
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text(render_bridge_markdown(plan), encoding="utf-8")
        if args.json_out:
            json_path = Path(args.json_out)
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json.dumps(plan, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        summary = {
            "claim_level": plan["claim_level"],
            "from_arm": plan["from_arm"]["arm_id"],
            "to_arm": plan["to_arm"]["arm_id"],
            "criterion": plan["criterion"],
            "n_runs": plan["n_runs"],
            "design_csv": str(out_path),
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "recommend-family":
        manifest = load_manifest(Path(args.example_dir))
        recommendation = recommend_family(
            manifest,
            budget=args.budget,
            curvature_prior=args.curvature_prior,
            interactions_prior=args.interactions_prior,
        )
        if args.out_path:
            out_path = Path(args.out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(recommendation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(recommendation, indent=2, sort_keys=True))
        return 0
    if args.command == "finalize":
        results_path = Path(args.results) if args.results else None
        packet = compose_run_packet(Path(args.example_dir), results_path=results_path, seed=args.seed)
        out_path = Path(args.out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_run_packet_markdown(packet), encoding="utf-8")
        if args.json_out:
            json_path = Path(args.json_out)
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json.dumps(packet, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        summary = {
            "campaign_id": packet["campaign_id"],
            "claim_level": packet["claim_level"],
            "sections_available": [
                name
                for name in (
                    "readiness",
                    "family_recommendation",
                    "goals",
                    "scale_recipe",
                    "bridge_qualification",
                    "assay_power",
                    "sampling_plan",
                    "wave1_design",
                    "wave1_results",
                    "wave1_analysis",
                    "wave2_plan",
                    "biosafety",
                )
                if isinstance(packet.get(name), dict) and packet[name].get("status") == "AVAILABLE"
            ],
            "out": str(out_path),
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "analyze":
        manifest = load_manifest(Path(args.example_dir))
        result_rows = _read_csv_rows(Path(args.results))
        analysis = analyze_results(
            manifest,
            result_rows,
            response_id=args.response,
            seed=args.seed,
            n_permutations=args.permutations,
            n_bootstrap=args.bootstrap,
            significance_alpha=args.alpha,
        )
        out_path = Path(args.out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.md_out:
            md_path = Path(args.md_out)
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text(render_analysis_markdown(analysis), encoding="utf-8")
        summary = {
            "claim_level": analysis.get("claim_level"),
            "response_id": analysis.get("response_id"),
            "n_runs_used": analysis.get("n_runs_used"),
            "active_factor_ids": analysis.get("active_factor_ids", []),
            "short_circuit_reason": analysis.get("short_circuit_reason"),
            "out": str(out_path),
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "goals":
        manifest = load_manifest(Path(args.example_dir))
        goals = formulate_goals(manifest)
        out_path = Path(args.out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if goals is None:
            payload = {
                "goals": None,
                "reason": "no_objective_bounds_declarable",
                "non_claim": "Goals require objective_lower / objective_upper / objective_target on responses[] or numeric thresholds in decision_rules[] scoped to a response.",
            }
        else:
            payload = goals
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summary = {
            "claim_level": payload.get("claim_level", "no_goals"),
            "n_objectives": len((payload.get("objectives") or [])) if goals else 0,
            "out": str(out_path),
        }
        if not goals:
            summary["reason"] = payload["reason"]
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.command == "scale-recipe":
        manifest = load_manifest(Path(args.example_dir))
        recipe = compute_scale_recipe(manifest)
        out_path = Path(args.out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(recipe, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.md_out:
            md_path = Path(args.md_out)
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.write_text(render_recipe_markdown(recipe), encoding="utf-8")
        print(
            json.dumps(
                {
                    "claim_level": recipe["claim_level"],
                    "primary_criterion": recipe["primary_criterion"],
                    "criterion_match_status": recipe["criterion_match"]["status"],
                    "from_scale_label": recipe["from_scale"]["label"],
                    "to_scale_label": recipe["to_scale"]["label"],
                    "warnings": recipe["warnings"],
                    "recipe_json": str(out_path),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "generate-design":
        manifest = load_manifest(Path(args.example_dir))
        design = generate_design(manifest, seed=args.seed)
        out_path = Path(args.out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_design_csv(design, out_path)
        if args.metadata_out:
            metadata_path = Path(args.metadata_out)
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            metadata_path.write_text(
                json.dumps(
                    {
                        "family": design["family"],
                        "claim_level": design["claim_level"],
                        "n_runs": design["n_runs"],
                        "factors": design["factors"],
                        "metadata": design["metadata"],
                        "warnings": design["warnings"],
                        "randomized": design["randomized"],
                        "seed": design["seed"],
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
        print(
            json.dumps(
                {
                    "family": design["family"],
                    "claim_level": design["claim_level"],
                    "n_runs": design["n_runs"],
                    "design_csv": str(out_path),
                    "warnings": design["warnings"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


def _read_csv_rows(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def _write_design_csv(design: dict, out_path: Path) -> None:
    factor_ids = list(design["factors"])
    fieldnames = ["design_run_id", "run_order", *factor_ids, "center_point", "claim_level"]
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in design["rows"]:
            payload = {
                "design_run_id": row["design_run_id"],
                "run_order": row["run_order"],
                "center_point": "true" if row.get("center_point") else "false",
                "claim_level": design["claim_level"],
            }
            for fid in factor_ids:
                payload[fid] = row.get(fid, "")
            writer.writerow(payload)


if __name__ == "__main__":
    sys.exit(main())
