"""Optional design simulation and power utility."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from ..compiler import compile_campaign_state
from ..doe import propose_candidate_designs
from ..io_utils import markdown_table, write_csv, write_json
from ..model_matrix import build_model_matrix
from .common import utility_manifest


def run_simulate_design_utility(
    manifest_path: Path,
    out_dir: Path,
    run_budget: int | None = None,
    iterations: int = 200,
    seed: int | None = None,
    effect_size: float = 1.0,
    noise_sd: float = 1.0,
    backend: str | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    state = compile_campaign_state(manifest_path)
    policy = state.get("design_policy") if isinstance(state.get("design_policy"), dict) else {}
    sim_policy = policy.get("simulation_policy") if isinstance(policy.get("simulation_policy"), dict) else {}
    seed = int(seed if seed is not None else sim_policy.get("seed", policy.get("seed", 17)))
    iterations = int(sim_policy.get("iterations", iterations))
    effect_size = float(sim_policy.get("effect_size", effect_size))
    noise_sd = float(sim_policy.get("noise_sd", noise_sd))
    designs = propose_candidate_designs(manifest_path, state, run_budget=run_budget)
    rng = random.Random(seed)
    summaries = []
    for candidate in designs["candidates"]:
        if not candidate.get("rows"):
            continue
        matrix_bundle = build_model_matrix(candidate["rows"], state.get("factors", []), state.get("model_terms", {}))
        matrix = matrix_bundle["matrix"]
        if not matrix:
            continue
        signal_scores = []
        for _ in range(iterations):
            effects = [0.0] + [rng.choice([-1.0, 1.0]) * effect_size for _ in range(len(matrix_bundle["columns"]) - 1)]
            y_values = [sum(value * effects[index] for index, value in enumerate(row)) + rng.gauss(0, noise_sd) for row in matrix]
            spread = max(y_values) - min(y_values)
            signal_scores.append(spread / max(noise_sd, 1e-9))
        diagnostics = candidate.get("diagnostics", {})
        power = min(1.0, (sum(1 for score in signal_scores if score >= 2.0) / max(1, iterations)) * (diagnostics.get("rank", 0) / max(1, diagnostics.get("model_term_count", 1))))
        summaries.append(
            {
                "design_id": candidate["design_id"],
                "lane": candidate["lane"],
                "run_count": diagnostics.get("run_count", 0),
                "rank": diagnostics.get("rank", 0),
                "model_term_count": diagnostics.get("model_term_count", 0),
                "effect_size": effect_size,
                "noise_sd": noise_sd,
                "iterations": iterations,
                "power_proxy": round(power, 4),
                "median_signal_to_noise": round(sorted(signal_scores)[len(signal_scores) // 2], 4),
                "label": "deterministic_monte_carlo_power_proxy",
            }
        )
    summaries.sort(key=lambda row: row["power_proxy"], reverse=True)
    result = {
        "schema_version": 1,
        "utility_result_kind": "simulate_design",
        "campaign_id": state.get("campaign_id"),
        "seed": seed,
        "iterations": iterations,
        "effect_size": effect_size,
        "noise_sd": noise_sd,
        "items": summaries,
        "best_design_id": summaries[0]["design_id"] if summaries else "",
    }
    write_json(out_dir / "simulation_results.json", result)
    write_csv(out_dir / "power_summary.csv", summaries)
    (out_dir / "simulation_report.md").write_text(render_simulation_report(result))
    utility_manifest(
        utility="simulate-design",
        out_dir=out_dir,
        inputs={"manifest": str(manifest_path)},
        backend=backend or policy.get("utility_backend"),
        artifacts=["simulation_results.json", "power_summary.csv", "simulation_report.md"],
        metric_labels={"power_proxy": "heuristic_deterministic_monte_carlo"},
        caveats=["Power proxy is useful for design comparison, not a formal regulatory power calculation."],
    )
    return result


def render_simulation_report(result: dict[str, Any]) -> str:
    rows = [
        [
            item["design_id"],
            item["run_count"],
            item["rank"],
            item["model_term_count"],
            item["power_proxy"],
            item["median_signal_to_noise"],
        ]
        for item in result.get("items", [])[:12]
    ]
    return (
        "# Simulation Report\n\n"
        f"- Campaign: {result.get('campaign_id')}\n"
        f"- Seed: {result.get('seed')}\n"
        f"- Iterations: {result.get('iterations')}\n"
        f"- Effect size: {result.get('effect_size')}\n"
        f"- Noise SD: {result.get('noise_sd')}\n"
        f"- Best design: {result.get('best_design_id')}\n\n"
        + markdown_table(["Design", "Runs", "Rank", "Terms", "Power proxy", "Median S/N"], rows)
        + "\n"
    )
