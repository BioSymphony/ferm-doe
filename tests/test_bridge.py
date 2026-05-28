from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from biosymphony_ferm_doe.bridge import (  # noqa: E402
    CLAIM_LEVEL,
    compute_bridge_qualification,
    render_bridge_markdown,
)


def _manifest() -> dict:
    return {
        "campaign_id": "demo-bridge-test",
        "claim_level": "public_synthetic_demo",
        "responses": [{"response_id": "y", "direction": "maximize"}],
        "factors": [
            {"factor_id": "temperature_c", "type": "numeric", "low": 30, "high": 37},
            {"factor_id": "initial_ph", "type": "numeric", "low": 6.5, "high": 7.2},
            {"factor_id": "do_setpoint_pct", "type": "numeric", "low": 20, "high": 40},
            {"factor_id": "stir_rpm_bench", "type": "numeric", "low": 400, "high": 900},
        ],
        "arms": [
            {"arm_id": "pilot_reference", "scale_tier": "pilot_50L", "purpose": "reference"},
            {
                "arm_id": "benchtop_qualification",
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
            "bridge_strategy": {
                "primary_criterion": "kLa",
                "secondary_criteria": ["p_per_v"],
                "rationale": "test",
            },
            "bridge_factors": {
                "transferable": ["temperature_c", "initial_ph", "do_setpoint_pct"],
                "needs_retuning": ["stir_rpm_bench"],
                "not_applicable": [],
            },
            "recapitulation_criterion": {"metric": "titer_ratio", "tolerance": 0.85, "status": "planned"},
        },
    }


class BridgeQualificationTests(unittest.TestCase):
    def test_default_pair_inferred_from_bridge_to(self) -> None:
        plan = compute_bridge_qualification(_manifest())
        self.assertEqual(plan["claim_level"], CLAIM_LEVEL)
        self.assertEqual(plan["to_arm"]["arm_id"], "benchtop_qualification")
        self.assertEqual(plan["from_arm"]["arm_id"], "pilot_reference")
        self.assertEqual(plan["criterion"], "kLa")

    def test_default_replicate_count(self) -> None:
        plan = compute_bridge_qualification(_manifest())
        self.assertEqual(plan["n_replicates"], 3)
        self.assertEqual(plan["n_runs"], 3)
        for row in plan["qualification_design"]:
            self.assertEqual(row["row_kind"], "matched_center")
            self.assertEqual(row["arm_id"], "benchtop_qualification")
            self.assertEqual(row["criterion"], "kLa")
            # Transferable factors held at midpoint.
            self.assertAlmostEqual(float(row["temperature_c"]), 33.5, places=4)

    def test_perturbation_adds_two_rows_per_transferable_factor(self) -> None:
        plan = compute_bridge_qualification(_manifest(), perturbation_pct=10)
        # 3 center + 3 transferable factors * 2 perturbations = 9 rows
        self.assertEqual(plan["n_runs"], 9)
        kinds = [row["row_kind"] for row in plan["qualification_design"]]
        self.assertEqual(kinds.count("matched_center"), 3)
        self.assertEqual(kinds.count("perturbation"), 6)

    def test_retuned_setpoint_pulled_from_recipe(self) -> None:
        plan = compute_bridge_qualification(_manifest())
        # stir_rpm_bench should map to recipe's agitation_rpm (not a verbatim match by name);
        # since the manifest's needs_retuning lists stir_rpm_bench (not "agitation_rpm"),
        # the retuned_setpoints dict will fall back to operator_to_supply_at_run_time.
        self.assertIn("stir_rpm_bench", plan["retuned_setpoints"])

    def test_explicit_arm_ids_override_inference(self) -> None:
        manifest = _manifest()
        # Add a third arm to make sure explicit selection still works.
        manifest["arms"].append({
            "arm_id": "second_qual_arm",
            "scale_tier": "bench_2L",
            "purpose": "downscale_target",
            "bridge_to": {"arm_id": "pilot_reference", "criterion": "kLa"},
        })
        plan = compute_bridge_qualification(manifest, to_arm_id="second_qual_arm")
        self.assertEqual(plan["to_arm"]["arm_id"], "second_qual_arm")

    def test_invalid_arm_raises(self) -> None:
        with self.assertRaises(ValueError):
            compute_bridge_qualification(_manifest(), to_arm_id="nonexistent_arm")


class MarkdownRenderingTests(unittest.TestCase):
    def test_markdown_includes_arm_summary_and_criterion(self) -> None:
        plan = compute_bridge_qualification(_manifest(), perturbation_pct=10)
        md = render_bridge_markdown(plan)
        self.assertIn("Bridge qualification plan", md)
        self.assertIn("from_arm", md)
        self.assertIn("to_arm", md)
        self.assertIn("kLa", md)
        self.assertIn("Qualification design", md)


class CliBridgeQualificationTests(unittest.TestCase):
    def test_cli_emits_csv_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign = root / "campaign"
            campaign.mkdir()
            (campaign / "campaign_manifest.json").write_text(json.dumps(_manifest()), encoding="utf-8")
            csv_out = root / "qual.csv"
            md_out = root / "qual.md"
            json_out = root / "qual.json"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
            completed = subprocess.run(
                [
                    sys.executable, "-m", "biosymphony_ferm_doe.cli", "bridge-qualification",
                    str(campaign), "--out", str(csv_out), "--md-out", str(md_out),
                    "--json-out", str(json_out), "--replicates", "4", "--perturbation-pct", "10",
                ],
                cwd=ROOT, env=env, text=True, capture_output=True, check=True,
            )
            summary = json.loads(completed.stdout)
            self.assertEqual(summary["claim_level"], CLAIM_LEVEL)
            self.assertEqual(summary["from_arm"], "pilot_reference")
            self.assertEqual(summary["to_arm"], "benchtop_qualification")
            self.assertEqual(summary["n_runs"], 4 + 6)
            self.assertTrue(csv_out.is_file())
            self.assertTrue(md_out.is_file())
            self.assertTrue(json_out.is_file())
            with csv_out.open("r", newline="", encoding="utf-8") as handle:
                reader = list(csv.DictReader(handle))
            self.assertEqual(len(reader), 10)
            self.assertEqual(reader[0]["arm_id"], "benchtop_qualification")


class DemoSmokeTests(unittest.TestCase):
    def test_existing_scale_bridge_demo_produces_qualification_plan(self) -> None:
        demo_path = ROOT / "examples" / "demo-scale-bridge-public" / "campaign_manifest.json"
        manifest = json.loads(demo_path.read_text())
        plan = compute_bridge_qualification(manifest)
        self.assertEqual(plan["criterion"], "kLa")
        self.assertEqual(plan["to_arm"]["arm_id"], "benchtop_qualification")
        self.assertEqual(plan["n_runs"], 3)


if __name__ == "__main__":
    unittest.main()
