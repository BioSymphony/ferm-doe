from __future__ import annotations

import contextlib
import csv
import io
import itertools
import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.analysis import analyze_results  # noqa: E402
from biosymphony_ferm_doe.bridge import compute_bridge_qualification  # noqa: E402
from biosymphony_ferm_doe.cli import main as cli_main  # noqa: E402
from biosymphony_ferm_doe.cost_rollup import compute_cost_rollup  # noqa: E402
from biosymphony_ferm_doe.doe_power import compute_doe_power  # noqa: E402
from biosymphony_ferm_doe.family_recommender import recommend_family  # noqa: E402
from biosymphony_ferm_doe.goals import formulate_goals  # noqa: E402
from biosymphony_ferm_doe.profiles import PROFILE_REGISTRY, resolve_profiles  # noqa: E402
from biosymphony_ferm_doe.sampling import compute_sampling_plan  # noqa: E402
from biosymphony_ferm_doe.scale_recipe import compute_scale_recipe  # noqa: E402


def _manifest() -> dict:
    return {
        "schema_version": 1,
        "campaign_id": "public-backport-smoke",
        "name": "Public backport smoke",
        "profiles": ["screening"],
        "responses": [
            {
                "response_id": "titer",
                "direction": "maximize",
                "assay_required": True,
                "measurement_type": "assayed",
                "objective_lower": 5,
                "objective_upper": 30,
                "assay_power_policy": {"expected_effect_size": 5},
            }
        ],
        "factors": [
            {"factor_id": "x1", "type": "numeric", "low": 0.0, "high": 1.0},
            {"factor_id": "x2", "type": "numeric", "low": 0.0, "high": 1.0},
            {"factor_id": "x3", "type": "numeric", "low": 0.0, "high": 1.0},
            {"factor_id": "stir_rpm_bench", "type": "numeric", "low": 400, "high": 900},
        ],
        "doe": {"family": "plackett_burman", "n_runs": 8, "model_terms": ["main_effects"], "randomized": False},
        "resource_costs": {"per_run_cost": 100, "wave2_runs_estimate": 2},
        "sampling_policy": {"run_duration_h": 24},
        "arms": [
            {"arm_id": "pilot_reference", "scale_tier": "pilot_50L", "purpose": "reference"},
            {
                "arm_id": "bench_qualification",
                "scale_tier": "bench_2L",
                "purpose": "downscale_target",
                "bridge_to": {"arm_id": "pilot_reference", "criterion": "kLa"},
            },
        ],
        "scale_context": {
            "direction": "scale_down",
            "from_scale": {
                "label": "pilot_50L",
                "vessel": "stirred_tank_pilot",
                "working_volume_l": 50,
                "geometry": {"h_over_d": 2.5, "impeller_d_over_t": 0.4, "n_impellers": 2, "impeller_type": "rushton"},
                "engineering_targets": {"kLa_per_hour": 250, "vvm": 1.0},
            },
            "to_scale": {
                "label": "bench_2L",
                "vessel": "stirred_tank_bench",
                "working_volume_l": 1.5,
                "geometry": {"h_over_d": 2.2, "impeller_d_over_t": 0.4, "n_impellers": 2, "impeller_type": "rushton"},
                "engineering_targets": {"kLa_per_hour": 250, "vvm": 1.0},
            },
            "bridge_strategy": {"primary_criterion": "kLa", "secondary_criteria": ["p_per_v"]},
            "bridge_factors": {
                "transferable": ["x1", "x2"],
                "needs_retuning": ["stir_rpm_bench"],
                "not_applicable": [],
            },
            "recapitulation_criterion": {"metric": "titer_ratio", "tolerance": 0.85, "status": "planned"},
        },
    }


def _result_rows() -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for index, combo in enumerate(itertools.product([0.0, 1.0], repeat=4), start=1):
        x1, x2, x3, stir_unit = combo
        stir = 400 + stir_unit * 500
        rows.append(
            {
                "design_run_id": f"D{index:03d}",
                "x1": x1,
                "x2": x2,
                "x3": x3,
                "stir_rpm_bench": stir,
                "titer": 10 + 5 * x1 - 2 * x2 + 0.002 * stir,
            }
        )
    return rows


class PublicBackportAdapterTests(unittest.TestCase):
    def test_importable_modules_compute_planning_artifacts(self) -> None:
        manifest = _manifest()
        self.assertIn("scale_down_qualification", PROFILE_REGISTRY)
        self.assertEqual(resolve_profiles(["missing"]), ["custom"])

        recipe = compute_scale_recipe(manifest)
        self.assertEqual(recipe["claim_level"], "engineering_recipe_planned")
        bridge = compute_bridge_qualification(manifest, perturbation_pct=10)
        self.assertEqual(bridge["to_arm"]["arm_id"], "bench_qualification")
        self.assertGreater(bridge["n_runs"], 3)

        goals = formulate_goals(manifest)
        self.assertIsNotNone(goals)
        sampling = compute_sampling_plan(manifest)
        self.assertGreater(sampling["totals"]["n_samples"], 0)
        cost = compute_cost_rollup(manifest)
        self.assertEqual(cost["wave1_n_runs"], 8)
        recommendation = recommend_family(manifest, curvature_prior="yes")
        self.assertEqual(recommendation["claim_level"], "family_recommendation_planning")

        power = compute_doe_power(manifest, sigma=1.0)
        self.assertEqual(power["claim_level"], "doe_power_planning")
        self.assertGreater(power["n_parameters"], 1)

        analysis = analyze_results(manifest, _result_rows(), seed=0, n_permutations=20, n_bootstrap=20)
        self.assertEqual(analysis["claim_level"], "wave1_analysis_planned")
        self.assertEqual(analysis["response_id"], "titer")

    def test_cli_affordances_write_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign = root / "campaign"
            campaign.mkdir()
            (campaign / "campaign_manifest.json").write_text(json.dumps(_manifest()))
            results = root / "results.csv"
            with results.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["design_run_id", "x1", "x2", "x3", "stir_rpm_bench", "titer"])
                writer.writeheader()
                writer.writerows(_result_rows())

            commands = [
                ["scale-recipe", str(campaign), "--out", str(root / "scale.json"), "--md-out", str(root / "scale.md")],
                ["bridge-qualification", str(campaign), "--out", str(root / "bridge.csv"), "--json-out", str(root / "bridge.json")],
                ["goals", str(campaign), "--out", str(root / "goals.json")],
                ["sampling-plan", str(campaign), "--out", str(root / "sampling.csv"), "--json-out", str(root / "sampling.json")],
                ["cost-rollup", str(campaign), "--out", str(root / "cost.json")],
                ["doe-power", str(campaign), "--sigma", "1.0", "--out", str(root / "power.json")],
                ["recommend-family", str(campaign), "--out", str(root / "family.json")],
                [
                    "analyze",
                    str(campaign),
                    "--results",
                    str(results),
                    "--out",
                    str(root / "analysis.json"),
                    "--permutations",
                    "20",
                    "--bootstrap",
                    "20",
                ],
            ]
            for command in commands:
                with self.subTest(command=command[0]):
                    stdout = io.StringIO()
                    with contextlib.redirect_stdout(stdout):
                        self.assertEqual(cli_main(command), 0)
                    self.assertTrue(stdout.getvalue().strip())

            for expected in (
                "scale.json",
                "scale.md",
                "bridge.csv",
                "bridge.json",
                "goals.json",
                "sampling.csv",
                "sampling.json",
                "cost.json",
                "power.json",
                "family.json",
                "analysis.json",
            ):
                self.assertTrue((root / expected).is_file(), expected)


if __name__ == "__main__":
    unittest.main()
