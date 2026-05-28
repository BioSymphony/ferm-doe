from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.adaptive_wave2 import plan_adaptive_wave2  # noqa: E402
from biosymphony_ferm_doe.bridge import compute_bridge_qualification  # noqa: E402
from biosymphony_ferm_doe.compiler import compile_campaign_state  # noqa: E402
from biosymphony_ferm_doe.contract import contract_self_check  # noqa: E402
from biosymphony_ferm_doe.dossier import check_dossier, compile_dossier  # noqa: E402
from biosymphony_ferm_doe.scale_recipe import compute_scale_recipe  # noqa: E402


MANIFEST = ROOT / "examples/engine-multi-arm-scale-transfer-public/campaign_manifest.json"
SHAKE_TO_2L_MANIFEST = ROOT / "examples/demo-shakeflask-to-2l-bofire/campaign_manifest.json"


class FlagshipScaleTransferExampleTests(unittest.TestCase):
    def test_flagship_example_compiles_dossier_and_bridge_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            dossier = out / "ferm-doe-dossier"
            compile_dossier(MANIFEST, dossier, run_budget=10)

            setup = json.loads((dossier / "experimental_setup.json").read_text())
            horizontal = _read_csv(dossier / "horizontal_doe.csv")
            self.assertEqual(setup["scale_direction"], "coupled_scale_up_downscale")
            self.assertEqual({arm["arm_id"] for arm in setup["arms"]}, {"plate_downscale", "ambr_reactor"})
            self.assertEqual({row["arm_id"] for row in horizontal}, {"plate_downscale", "ambr_reactor"})
            self.assertTrue(all(row["optimization_goal"] for row in horizontal))
            self.assertEqual(check_dossier(dossier)["status"], "PASS")
            self.assertEqual(contract_self_check(dossier)["status"], "PASS")

            manifest = json.loads(MANIFEST.read_text())
            recipe = compute_scale_recipe(manifest)
            bridge = compute_bridge_qualification(
                manifest,
                from_arm_id="plate_downscale",
                to_arm_id="ambr_reactor",
                n_replicates=2,
                perturbation_pct=10,
            )
            self.assertEqual(recipe["claim_level"], "engineering_recipe_planned")
            self.assertEqual(bridge["claim_level"], "bridge_qualification_planning")
            self.assertGreaterEqual(bridge["n_runs"], 2)

    def test_flagship_example_allows_adaptive_scale_or_downscale_when_bridge_policy_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state = compile_campaign_state(MANIFEST, tmp_path / "state")
            results = tmp_path / "results.csv"
            _write_results(results, state)

            plan = plan_adaptive_wave2(
                tmp_path / "state/campaign_state.json",
                results,
                tmp_path / "wave2",
                remaining_budget=2,
            )

            self.assertEqual(plan["recommended_action"], "scale_or_downscale")
            self.assertEqual(plan["bridge_eligibility_status"], "PASS")
            self.assertTrue((tmp_path / "wave2/adaptive_wave2_plan.json").exists())
            self.assertTrue((tmp_path / "wave2/wave2_manifest.patch.json").exists())

    @unittest.skip(
        "BoFire constrained-DoE adapter currently produces selected designs "
        "that the contract self-check flags as constraint violations on the "
        "shake-flask-to-2L example. Tracked alongside the BoFire issue #450 "
        "trap documented in docs/BOFIRE_POSITIONING.md."
    )
    def test_shake_flask_to_2l_bofire_demo_compiles_valid_dossier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp) / "ferm-doe-dossier"
            compile_dossier(SHAKE_TO_2L_MANIFEST, dossier)

            check = check_dossier(dossier)
            selected = _read_csv(dossier / "campaign_arms/bioreactor_2l/selected_wave_1_design.csv")

        self.assertEqual(check["status"], "PASS", check)
        self.assertTrue(selected)
        self.assertNotIn(selected[0]["glucose_g_l"], {"low", "center", "high"})


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _write_results(path: Path, state: dict[str, object]) -> None:
    headers = [
        "run_id",
        "arm_id",
        "soluble_titer_mg_l",
        "specific_productivity_mg_g_h",
        "media_cost_usd_l",
        "acetate_g_l",
        "bridge_delta_pct",
        "production_temperature_c",
        "induction_time_h",
        "trust_score",
        "qc_status",
        "inclusion_status",
    ]
    rows = [
        ("plate_downscale:R1", "plate_downscale", 300, 12, 18, 0.8, 18, 24, 18),
        ("plate_downscale:R2", "plate_downscale", 420, 16, 22, 1.3, 12, 27, 22),
        ("ambr_reactor:R1", "ambr_reactor", 310, 13, 25, 0.7, 10, 24, 18),
        ("ambr_reactor:R2", "ambr_reactor", 450, 17, 30, 1.2, 8, 27, 22),
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for run_id, arm_id, titer, productivity, cost, acetate, bridge_delta, temp, induction in rows:
            writer.writerow(
                {
                    "run_id": run_id,
                    "arm_id": arm_id,
                    "soluble_titer_mg_l": titer,
                    "specific_productivity_mg_g_h": productivity,
                    "media_cost_usd_l": cost,
                    "acetate_g_l": acetate,
                    "bridge_delta_pct": bridge_delta,
                    "production_temperature_c": temp,
                    "induction_time_h": induction,
                    "trust_score": "0.95",
                    "qc_status": "pass",
                    "inclusion_status": "trusted",
                }
            )


if __name__ == "__main__":
    unittest.main()
