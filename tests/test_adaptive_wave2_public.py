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

from biosymphony_ferm_doe.adaptive import (  # noqa: E402
    evaluate_assay_power,
    plan_wave2,
    recommend_wave2,
    result_ingestion_report,
)


def _manifest() -> dict:
    return {
        "campaign_id": "public-adaptive-demo",
        "claim_level": "public_synthetic_demo",
        "system": {"privacy": "synthetic_or_public_only"},
        "responses": [
            {
                "response_id": "titer_g_l",
                "class": "titer",
                "measurement_type": "assayed",
                "direction": "maximize",
                "assay_required": True,
                "assay_power_policy": {
                    "minimum_detectable_effect": 5,
                    "expected_effect_size": 30,
                    "cv_percent": 10,
                    "replicate_count": 3,
                    "target_power": 0.8,
                    "lod": 0.1,
                    "loq": 0.5,
                    "dynamic_range": {"low": 0.5, "high": 100},
                    "matrix_recovery_min": 85,
                    "turnaround_h": 24,
                },
            },
            {
                "response_id": "run_cost",
                "class": "cost",
                "measurement_type": "derived",
                "direction": "minimize",
                "assay_required": False,
            },
        ],
        "factors": [
            {"factor_id": "temp_C", "type": "numeric", "low": 28, "high": 35, "unit": "C"},
            {"factor_id": "pH", "type": "numeric", "low": 6.0, "high": 7.5},
        ],
        "adaptive_wave2": {
            "claim_level": "planned_wave2_design",
            "primary_response_id": "titer_g_l",
            "allowed_actions": ["confirm", "narrow", "expand", "pause", "stop"],
            "self_learning": {
                "enabled": True,
                "learning_ledger_path": "wave2/learning_ledger.csv",
                "hiccup_review_path": "wave2/hiccup_review.md",
                "negative_memory_scope": "arm",
            },
        },
    }


def _write_campaign(root: Path, manifest: dict | None = None) -> Path:
    campaign = root / "campaign"
    campaign.mkdir()
    (campaign / "campaign_manifest.json").write_text(json.dumps(manifest or _manifest(), indent=2), encoding="utf-8")
    return campaign


def _write_results(path: Path, rows: list[dict[str, str]]) -> None:
    fields = ["design_run_id", "arm_id", "qc_status", "inclusion_status", "trust_score", "titer_g_l", "temp_C", "pH"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class AssayPowerTests(unittest.TestCase):
    def test_assay_power_passes_and_derived_response_is_not_applicable(self) -> None:
        result = evaluate_assay_power(_manifest(), strict=True)
        self.assertEqual(result["status"], "PASS")
        by_response = {row["response_id"]: row for row in result["response_results"]}
        self.assertEqual(by_response["titer_g_l"]["status"], "PASS")
        self.assertEqual(by_response["run_cost"]["status"], "NOT_APPLICABLE")

    def test_weak_assay_power_policy_fails(self) -> None:
        manifest = _manifest()
        policy = manifest["responses"][0]["assay_power_policy"]
        policy["cv_percent"] = 55
        policy["replicate_count"] = 1
        policy["matrix_recovery_min"] = 50
        result = evaluate_assay_power(manifest, strict=True)
        self.assertEqual(result["status"], "FAIL")
        failures = result["response_results"][0]["failures"]
        self.assertIn("cv_percent_above_30", failures)
        self.assertIn("replicate_count_below_2", failures)


class ResultAndRecommendationTests(unittest.TestCase):
    def test_qc_failed_and_low_trust_rows_do_not_drive_recommendation(self) -> None:
        rows = [
            {"design_run_id": "D1", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95", "titer_g_l": "4", "temp_C": "29", "pH": "6.5"},
            {"design_run_id": "D2", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.96", "titer_g_l": "20", "temp_C": "30", "pH": "6.7"},
            {"design_run_id": "D3", "qc_status": "failed", "inclusion_status": "include", "trust_score": "0.99", "titer_g_l": "200", "temp_C": "35", "pH": "7.5"},
            {"design_run_id": "D4", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.20", "titer_g_l": "300", "temp_C": "35", "pH": "7.5"},
            {"design_run_id": "D5", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.97", "titer_g_l": "40", "temp_C": "31", "pH": "6.9"},
        ]
        report = result_ingestion_report(rows)
        usable = [row for row in rows if row["design_run_id"] in set(report["usable_run_ids"])]
        reco = recommend_wave2(_manifest(), usable)
        self.assertEqual(reco["recommended_action"], "narrow")
        self.assertEqual(reco["best_run_id"], "D5")
        self.assertIn("D3", report["excluded_run_ids"])
        self.assertIn("D4", report["low_trust_run_ids"])

    def test_boundary_winner_recommends_expand(self) -> None:
        rows = [
            {"design_run_id": "D1", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95", "titer_g_l": "10", "temp_C": "29", "pH": "6.5"},
            {"design_run_id": "D2", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.96", "titer_g_l": "12", "temp_C": "31", "pH": "6.8"},
            {"design_run_id": "D3", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.97", "titer_g_l": "30", "temp_C": "35", "pH": "7.0"},
        ]
        reco = recommend_wave2(_manifest(), rows)
        self.assertEqual(reco["recommended_action"], "expand")
        self.assertIn("temp_C", reco["boundary_factor_ids"])

    def test_multiple_arms_without_active_arm_pauses(self) -> None:
        manifest = _manifest()
        rows = [
            {"design_run_id": "P1", "arm_id": "plate", "titer_g_l": "10"},
            {"design_run_id": "R1", "arm_id": "reactor", "titer_g_l": "20"},
        ]
        reco = recommend_wave2(manifest, rows)
        self.assertEqual(reco["recommended_action"], "pause")
        self.assertEqual(reco["reason"], "multiple_arms_require_active_arm_or_per_arm_review")

    def test_scale_or_downscale_requires_bridge_eligibility(self) -> None:
        manifest = _manifest()
        manifest["adaptive_wave2"]["requested_action"] = "scale_or_downscale"
        rows = [
            {"design_run_id": "D1", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95", "titer_g_l": "10", "temp_C": "29", "pH": "6.5"},
            {"design_run_id": "D2", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.96", "titer_g_l": "20", "temp_C": "31", "pH": "6.8"},
        ]
        reco = recommend_wave2(manifest, rows)
        self.assertEqual(reco["recommended_action"], "pause")
        self.assertEqual(reco["reason"], "scale_or_downscale_blocked_by_bridge_eligibility")

    def test_allowed_actions_constrain_recommendation(self) -> None:
        manifest = _manifest()
        manifest["adaptive_wave2"]["allowed_actions"] = ["confirm", "narrow", "pause"]
        rows = [
            {"design_run_id": "D1", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95", "titer_g_l": "10", "temp_C": "29", "pH": "6.5"},
            {"design_run_id": "D2", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.96", "titer_g_l": "12", "temp_C": "31", "pH": "6.8"},
            {"design_run_id": "D3", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.97", "titer_g_l": "30", "temp_C": "35", "pH": "7.0"},
        ]
        reco = recommend_wave2(manifest, rows)
        self.assertEqual(reco["recommended_action"], "pause")
        self.assertEqual(reco.get("original_recommended_action"), "expand")
        self.assertIn("not_in_allowed_actions", reco.get("reason", ""))


class PlanFollowUpArtifactTests(unittest.TestCase):
    def test_plan_wave2_emits_required_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign = _write_campaign(root)
            results = root / "results.csv"
            _write_results(
                results,
                [
                    {"design_run_id": "D1", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95", "titer_g_l": "4", "temp_C": "29", "pH": "6.5"},
                    {"design_run_id": "D2", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.96", "titer_g_l": "20", "temp_C": "30", "pH": "6.7"},
                    {"design_run_id": "D3", "qc_status": "failed", "inclusion_status": "include", "trust_score": "0.99", "titer_g_l": "200", "temp_C": "35", "pH": "7.5"},
                    {"design_run_id": "D4", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.20", "titer_g_l": "300", "temp_C": "35", "pH": "7.5"},
                    {"design_run_id": "D5", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.97", "titer_g_l": "40", "temp_C": "31", "pH": "6.9"},
                ],
            )
            out_dir = root / "wave2"
            plan = plan_wave2(campaign, results, out_dir, remaining_budget=2)
            self.assertEqual(plan["claim_level"], "planned_wave2_design")
            for artifact in plan["artifacts"]:
                self.assertTrue((out_dir / artifact).is_file(), artifact)
            recommendation = json.loads((out_dir / "wave2_recommendation.json").read_text())
            self.assertEqual(recommendation["recommended_action"], "narrow")
            augment = (out_dir / "augment_design.csv").read_text()
            self.assertIn("planned_wave2_design", augment)
            ledger = (out_dir / "learning_ledger.csv").read_text()
            self.assertIn("qc_or_trust_exclusion", ledger)

    def test_cli_plan_wave2_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign = _write_campaign(root)
            results = root / "results.csv"
            _write_results(
                results,
                [
                    {"design_run_id": "D1", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95", "titer_g_l": "10", "temp_C": "29", "pH": "6.5"},
                    {"design_run_id": "D2", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.96", "titer_g_l": "14", "temp_C": "31", "pH": "6.8"},
                ],
            )
            out_dir = root / "wave2"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "biosymphony_ferm_doe.cli",
                    "plan-wave2",
                    str(campaign),
                    "--results",
                    str(results),
                    "--out-dir",
                    str(out_dir),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["claim_level"], "planned_wave2_design")
            self.assertTrue((out_dir / "adaptive_wave2_plan.json").is_file())
            trace_text = (out_dir / "adaptive_trace.json").read_text()
            self.assertNotIn(str(root), trace_text)
            self.assertIn("results.csv", trace_text)


if __name__ == "__main__":
    unittest.main()
