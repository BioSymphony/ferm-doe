from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.adaptive_wave2 import plan_adaptive_wave2
from biosymphony_ferm_doe.cli import main as cli_main
from biosymphony_ferm_doe.compiler import compile_campaign_state
from biosymphony_ferm_doe.contract import contract_self_check
from biosymphony_ferm_doe.dossier import compile_dossier
from biosymphony_ferm_doe.ingest import ingest_wave_results
from biosymphony_ferm_doe.tournament import run_design_tournament


_SKIP_REASON_CLI_SURFACE_DRIFT = (
    "Test exercises the local repo's richer CLI surface (`utility assay-power`, "
    "`plan-wave2 --campaign-state`) or `adaptive_wave2.bofire_strategy` module "
    "wiring. The public repo carries the simpler subset (`assay-power`, "
    "`plan-wave2 example_dir --results --out-dir`) by design; library functions "
    "are exercised by sibling tests."
)


class AdaptiveFollowUpAssayPowerTests(unittest.TestCase):
    @unittest.skip(_SKIP_REASON_CLI_SURFACE_DRIFT)
    def test_assay_power_utility_passes_and_derived_responses_are_not_assay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = _write_manifest(tmp_path / "manifest.json", policy=_strong_power_policy(), include_derived=True)
            compile_campaign_state(manifest, tmp_path / "state")
            out = tmp_path / "assay_power"

            self.assertEqual(cli_main(["utility", "assay-power", "--campaign-state", str(tmp_path / "state/campaign_state.json"), "--out", str(out)]), 0)
            result = json.loads((out / "assay_power_results.json").read_text())
            self.assertEqual(result["status"], "PASS")
            by_response = {item["response_id"]: item for item in result["items"]}
            self.assertEqual(by_response["media_cost_usd_l"]["status"], "NOT_APPLICABLE")
            self.assertTrue((out / "assay_power_summary.csv").exists())

    @unittest.skip(_SKIP_REASON_CLI_SURFACE_DRIFT)
    def test_assay_power_fails_for_missing_loq_high_cv_weak_recovery_and_replicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            weak = {
                "minimum_detectable_effect": 10,
                "expected_effect_size": 10,
                "cv_percent": 40,
                "replicate_count": 1,
                "target_power": 0.8,
                "lod": 1,
                "dynamic_range": [0, 100],
                "matrix_recovery_min": 60,
                "turnaround_h": 48,
            }
            manifest = _write_manifest(tmp_path / "manifest.json", policy=weak, design_policy={"require_assay_power": True})
            compile_campaign_state(manifest, tmp_path / "state")
            out = tmp_path / "assay_power"

            self.assertEqual(cli_main(["utility", "assay-power", "--campaign-state", str(tmp_path / "state/campaign_state.json"), "--out", str(out), "--strict"]), 1)
            result = json.loads((out / "assay_power_results.json").read_text())
            fields = {issue["field"] for item in result["items"] for issue in item.get("issues", [])}
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("loq", fields)
            self.assertIn("cv_percent", fields)
            self.assertIn("matrix_recovery_min", fields)
            self.assertIn("replicate_count", fields)

    @unittest.skip(_SKIP_REASON_CLI_SURFACE_DRIFT)
    def test_plan_wave2_emits_required_artifacts_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = _write_manifest(tmp_path / "manifest.json", policy=_strong_power_policy())
            state = compile_campaign_state(manifest, tmp_path / "state")
            results = _write_results(
                tmp_path / "results.csv",
                state,
                [
                    ("R1", 10, 24, 5.8),
                    ("R2", 12, 26, 6.0),
                    ("R3", 20, 24.5, 6.2),
                    ("R4", 50, 25, 6.1),
                ],
            )
            first = tmp_path / "first"
            second = tmp_path / "second"

            one = plan_adaptive_wave2(tmp_path / "state/campaign_state.json", results, first, remaining_budget=2)
            two = plan_adaptive_wave2(tmp_path / "state/campaign_state.json", results, second, remaining_budget=2)
            cli_out = tmp_path / "cli"
            self.assertEqual(
                cli_main([
                    "plan-wave2",
                    "--campaign-state",
                    str(tmp_path / "state/campaign_state.json"),
                    "--results",
                    str(results),
                    "--out",
                    str(cli_out),
                    "--remaining-budget",
                    "2",
                ]),
                0,
            )

            self.assertEqual(one["claim_level"], "planned_wave2_design")
            self.assertEqual(one["recommended_action"], "narrow")
            self.assertEqual(one, two)
            self.assertTrue((cli_out / "adaptive_wave2_plan.json").exists())
            for name in [
                "adaptive_wave2_plan.json",
                "result_ingestion_report.json",
                "wave2_recommendation.json",
                "locked_prior_runs.csv",
                "augment_design.csv",
                "adaptive_trace.json",
                "learning_ledger.csv",
                "hiccup_review.md",
                "negative_result_memory.json",
                "wave2_manifest.patch.json",
                "assay_power_results.json",
            ]:
                self.assertTrue((first / name).exists(), name)
            with (first / "learning_ledger.csv").open() as handle:
                learning_rows = list(csv.DictReader(handle))
            self.assertTrue(learning_rows)
            self.assertEqual(learning_rows[0]["claim_boundary"], "planned_wave2_design_only")

    def test_plan_wave2_action_coverage_materializes_action_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = _write_manifest(tmp_path / "manifest.json", policy=_strong_power_policy())
            state = compile_campaign_state(manifest, tmp_path / "state")
            cases = [
                ("pause", [("R1", "", 25, 6.0), ("R2", "", 26, 6.2), ("R3", "", 24, 5.8)], 0),
                ("stop", [("R1", 10, 25, 6.0), ("R2", 10.1, 26, 6.2), ("R3", 10.2, 24, 5.8)], 0),
                ("expand", [("R1", 10, 25, 6.0), ("R2", 12, 26, 6.2), ("R3", 50, 20, 6.1)], 1),
                ("confirm", [("R1", 10, 24, 5.8), ("R2", 12, 26, 6.2), ("R3", 14, 25, 6.0)], 1),
                ("narrow", [("R1", 10, 24, 5.8), ("R2", 12, 26, 6.2), ("R3", 50, 25, 6.0)], 1),
            ]
            for expected_action, rows, min_augment_rows in cases:
                with self.subTest(action=expected_action):
                    results = _write_results(tmp_path / f"{expected_action}.csv", state, rows)
                    out = tmp_path / f"wave2-{expected_action}"
                    plan = plan_adaptive_wave2(tmp_path / "state/campaign_state.json", results, out, remaining_budget=2)
                    recommendation = json.loads((out / "wave2_recommendation.json").read_text())
                    augment_rows = _read_csv_rows(out / "augment_design.csv")
                    learning_rows = _read_csv_rows(out / "learning_ledger.csv")

                    self.assertEqual(plan["recommended_action"], expected_action)
                    self.assertEqual(recommendation["recommended_action"], expected_action)
                    self.assertGreaterEqual(len(augment_rows), min_augment_rows)
                    if expected_action in {"pause", "stop"}:
                        self.assertEqual(augment_rows, [])
                        self.assertTrue(any(row["event_type"] == "adaptive_stop_or_pause" for row in learning_rows))

    def test_ingest_recommendation_actions_are_intent_aware(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = _write_manifest(tmp_path / "manifest.json", policy=_strong_power_policy())
            state = compile_campaign_state(manifest, tmp_path / "state")
            cases = [
                ("flat", [("R1", 10, 25, 6), ("R2", 10.1, 26, 6.2), ("R3", 10.2, 24, 5.8)], "stop"),
                ("boundary", [("R1", 10, 25, 6), ("R2", 12, 26, 6.2), ("R3", 50, 20, 5.8)], "expand"),
                ("strong", [("R1", 10, 24, 5.8), ("R2", 12, 26, 6.2), ("R3", 50, 25, 6)], "narrow"),
                ("modest", [("R1", 10, 24, 5.8), ("R2", 12, 26, 6.2), ("R3", 14, 25, 6)], "confirm"),
            ]
            for label, rows, expected in cases:
                with self.subTest(label=label):
                    results = _write_results(tmp_path / f"{label}.csv", state, rows)
                    result = ingest_wave_results(tmp_path / "state/campaign_state.json", results, tmp_path / label)
                    self.assertEqual(result["recommended_action"], expected)
            weak = _write_results(tmp_path / "weak.csv", state, [("R1", "", 25, 6), ("R2", "", 26, 6.2), ("R3", "", 24, 5.8)])
            self.assertEqual(ingest_wave_results(tmp_path / "state/campaign_state.json", weak, tmp_path / "weak")["recommended_action"], "pause")

    def test_plan_wave2_ignores_qc_failed_and_low_trust_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = _write_manifest(tmp_path / "manifest.json", policy=_strong_power_policy())
            state = compile_campaign_state(manifest, tmp_path / "state")
            results = _write_results(
                tmp_path / "results.csv",
                state,
                [
                    ("BAD-TRUST", 100, 20, 5.5, {"trust_score": "0.1"}),
                    ("BAD-QC", 90, 30, 6.5, {"qc_status": "failed"}),
                    ("R1", 10, 24, 5.8, {"trust_score": "0.9"}),
                    ("R2", 11, 25, 6.0, {"trust_score": "0.9"}),
                    ("R3", 12, 26, 6.2, {"trust_score": "0.9"}),
                ],
            )

            plan = plan_adaptive_wave2(tmp_path / "state/campaign_state.json", results, tmp_path / "wave2", remaining_budget=2)
            recommendation = json.loads((tmp_path / "wave2/wave2_recommendation.json").read_text())
            report = json.loads((tmp_path / "wave2/result_ingestion_report.json").read_text())

            self.assertEqual(plan["recommended_action"], "confirm")
            self.assertEqual(recommendation["best_run_id"], "R3")
            self.assertEqual(report["low_trust_row_count"], 1)
            self.assertEqual(report["qc_failed_row_count"], 1)

    def test_multi_arm_results_do_not_drive_global_narrowing_and_memory_is_arm_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = _write_multi_arm_manifest(tmp_path / "manifest.json")
            compile_campaign_state(manifest, tmp_path / "state")
            results = tmp_path / "results.csv"
            results.write_text(
                "arm_id,run_id,titer,temp_plate,fill_volume_ml,temp_reactor,do_percent,trust_score\n"
                "plate,P1,10,25,1.0,,,0.9\n"
                "plate,P2,50,26,1.2,,,0.9\n"
                "plate,P3,5,24,0.8,,,0.9\n"
                "reactor,B1,8,,,28,35,0.9\n"
                "reactor,B2,9,,,30,40,0.9\n"
                "reactor,B3,7,,,29,45,0.9\n"
            )

            plan = plan_adaptive_wave2(tmp_path / "state/campaign_state.json", results, tmp_path / "wave2", remaining_budget=2)
            memory = json.loads((tmp_path / "wave2/negative_result_memory.json").read_text())["items"]

            self.assertNotEqual(plan["recommended_action"], "narrow")
            self.assertTrue(plan["per_arm_recommendations"])
            self.assertTrue({item["arm_id"] for item in memory} <= {"plate", "reactor"})

    @unittest.skip(_SKIP_REASON_CLI_SURFACE_DRIFT)
    def test_plan_wave2_can_materialize_bofire_adapter_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = _write_manifest(tmp_path / "manifest.json", policy=_strong_power_policy())
            state = compile_campaign_state(manifest, tmp_path / "state")
            results = _write_results(
                tmp_path / "results.csv",
                state,
                [
                    ("R1", 10, 24, 5.8),
                    ("R2", 12, 26, 6.0),
                    ("R3", 20, 24.5, 6.2),
                    ("R4", 50, 25, 6.1),
                ],
            )
            fake_report = {
                "schema_version": 1,
                "adapter_kind": "bofire_strategy",
                "adapter_status": "executed",
                "claim_level": "bofire_adapter_planning",
                "non_claim": "planned only",
                "strategy_kind": "multi_objective",
                "route": {"reasons": ["multi_objective_responses"]},
                "candidate_design": [
                    {
                        "run_id": "BOFIRE-001",
                        "temp": 24.0,
                        "ph": 6.0,
                        "claim_level": "bofire_adapter_planning",
                        "scoring_mode": "bofire_strategy",
                    }
                ],
                "candidate_design_count": 1,
                "issues": [],
            }

            with mock.patch(
                "biosymphony_ferm_doe.adaptive_wave2.bofire_strategy.routing_decision",
                return_value={"should_route": True},
            ), mock.patch(
                "biosymphony_ferm_doe.adaptive_wave2.bofire_strategy.plan_bofire_wave2",
                return_value=fake_report,
            ):
                plan = plan_adaptive_wave2(tmp_path / "state/campaign_state.json", results, tmp_path / "wave2", remaining_budget=1)

            augment_rows = _read_csv_rows(tmp_path / "wave2/augment_design.csv")
            trace = json.loads((tmp_path / "wave2/adaptive_trace.json").read_text())
            bofire_step = next(step for step in trace["steps"] if step["step"] == "bofire_adapter")
            augment_step = next(step for step in trace["steps"] if step["step"] == "augment_design")

            self.assertIn("bofire_strategy_report.json", plan["artifacts"])
            self.assertEqual(augment_rows[0]["run_id"], "BOFIRE-001")
            self.assertEqual(bofire_step["status"], "executed")
            self.assertEqual(augment_step["status"], "PLANNED_BOFIRE")
            self.assertFalse(trace["determinism"]["stdlib_fallback"])

    def test_scale_or_downscale_is_blocked_without_bridge_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = _write_manifest(
                tmp_path / "manifest.json",
                policy=_strong_power_policy(),
                design_policy={"requested_next_action": "scale_or_downscale"},
            )
            state = compile_campaign_state(manifest, tmp_path / "state")
            results = _write_results(tmp_path / "results.csv", state, [("R1", 10, 24, 5.8), ("R2", 12, 26, 6.2), ("R3", 50, 25, 6)])

            plan = plan_adaptive_wave2(tmp_path / "state/campaign_state.json", results, tmp_path / "wave2")

            self.assertEqual(plan["recommended_action"], "pause")
            recommendation = json.loads((tmp_path / "wave2/wave2_recommendation.json").read_text())
            self.assertTrue(any("scale_or_downscale" in issue for issue in recommendation["issues"]))

    def test_scale_or_downscale_is_allowed_with_passing_bridge_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = _write_manifest(
                tmp_path / "manifest.json",
                policy=_strong_power_policy(),
                design_policy={"run_budget": 8, "requested_next_action": "scale_or_downscale"},
            )
            state = compile_campaign_state(manifest, tmp_path / "state")
            state["arm_bridge_policy"] = _passing_bridge_policy()
            (tmp_path / "state/campaign_state.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
            results = _write_results(tmp_path / "results.csv", state, [("R1", 10, 24, 5.8), ("R2", 12, 26, 6.2), ("R3", 50, 25, 6.0)])

            plan = plan_adaptive_wave2(tmp_path / "state/campaign_state.json", results, tmp_path / "wave2", remaining_budget=2)

            recommendation = json.loads((tmp_path / "wave2/wave2_recommendation.json").read_text())
            trace = json.loads((tmp_path / "wave2/adaptive_trace.json").read_text())
            bridge_step = next(step for step in trace["steps"] if step["step"] == "bridge_eligibility")
            self.assertEqual(plan["recommended_action"], "scale_or_downscale")
            self.assertEqual(plan["bridge_eligibility_status"], "PASS")
            self.assertEqual(recommendation["recommended_action"], "scale_or_downscale")
            self.assertTrue(bridge_step["scale_or_downscale_allowed"])
            self.assertFalse(any("No declared bridge" in issue for issue in recommendation["issues"]))

    def test_tournament_rejects_strong_claim_intent_when_assay_power_is_weak(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            weak = {
                "minimum_detectable_effect": 10,
                "expected_effect_size": 10,
                "cv_percent": 40,
                "replicate_count": 1,
                "target_power": 0.8,
                "lod": 1,
                "loq": 2,
                "dynamic_range": [0, 100],
                "matrix_recovery_min": 60,
                "turnaround_h": 48,
            }
            manifest = _write_manifest(
                tmp_path / "manifest.json",
                policy=weak,
                design_policy={"design_intent": "confirmatory", "require_assay_power": True, "run_budget": 8},
            )

            tournament = run_design_tournament(manifest, out_dir=tmp_path / "tournament", run_budget=8)

            self.assertTrue(
                any("Assay-power" in reason or "assay power" in reason for item in tournament["candidates"] for reason in item["rejection_reasons"])
            )

    def test_contract_self_check_rejects_formal_assay_power_claim_without_backing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = _write_manifest(tmp_path / "manifest.json", policy=_strong_power_policy())
            dossier = tmp_path / "dossier"
            compile_dossier(manifest, dossier, run_budget=6)
            rules = dossier / "wave_2_decision_rules.md"
            rules.write_text(rules.read_text() + "\nThis campaign is powered to detect the target effect.\n")

            check = contract_self_check(dossier)

            self.assertEqual(check["status"], "FAIL")
            self.assertTrue(any("formal assay-power" in error for error in check["errors"]))


def _strong_power_policy() -> dict[str, object]:
    return {
        "minimum_detectable_effect": 5,
        "expected_effect_size": 20,
        "noise_sd": 5,
        "replicate_count": 4,
        "target_power": 0.8,
        "lod": 0.5,
        "loq": 1,
        "dynamic_range": [1, 200],
        "matrix_recovery_min": 90,
        "turnaround_h": 24,
    }


def _passing_bridge_policy() -> dict[str, object]:
    return {
        "schema_version": 1,
        "policy_kind": "ferm_doe_arm_bridge_policy",
        "status": "declared",
        "bridges": [
            {
                "source_arm_id": "plate",
                "target_arm_id": "reactor",
                "bridge_kind": "downscale_to_bioreactor_prior",
                "eligibility_status": "passed",
                "minimum_evidence": {"status": "PASS"},
                "assay_comparability": {"status": "PASS"},
                "claim_boundary": "planned_transfer_prior_only",
            }
        ],
    }


def _write_manifest(
    path: Path,
    *,
    policy: dict[str, object],
    design_policy: dict[str, object] | None = None,
    include_derived: bool = False,
) -> Path:
    responses = [
        {
            "response_id": "titer",
            "name": "Titer",
            "unit": "mg/L",
            "direction": "maximize",
            "class": "titer",
            "sample_fraction": "whole_broth",
            "assay_method": "hplc",
            "calibration": "external_standard_curve",
            "matrix_effects_policy": "spike recovery before execution",
            "assay_power_policy": policy,
        }
    ]
    if include_derived:
        responses.append(
            {
                "response_id": "media_cost_usd_l",
                "name": "Media cost",
                "unit": "USD/L",
                "direction": "minimize",
                "class": "cost",
                "measurement_type": "calculated",
                "assay_required": False,
            }
        )
    payload = {
        "schema_version": 1,
        "campaign_id": "adaptive-wave2-demo",
        "name": "Adaptive follow-up demo",
        "objective": {"primary": "Maximize titer", "direction": "maximize", "response_id": "titer"},
        "readiness_target": "YELLOW",
        "product_class": "fermentation product",
        "sources": [],
        "inputs": [{"input_id": "equipment_capacity", "kind": "capacity", "path": "capacity.md"}, {"input_id": "reagent_inventory", "kind": "reagent", "path": "reagents.md"}],
        "constraints": [],
        "responses": responses,
        "factors": [
            {"factor_id": "temp", "type": "continuous", "min": 20, "max": 30},
            {"factor_id": "ph", "type": "continuous", "min": 5.5, "max": 6.5},
        ],
        "design_policy": design_policy or {"run_budget": 8},
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def _write_multi_arm_manifest(path: Path) -> Path:
    payload = {
        "schema_version": 1,
        "campaign_id": "multi-arm-wave2-demo",
        "name": "Multi-arm follow-up demo",
        "objective": {"primary": "Maximize titer", "direction": "maximize", "response_id": "titer"},
        "readiness_target": "YELLOW",
        "responses": [
            {
                "response_id": "titer",
                "name": "Titer",
                "unit": "mg/L",
                "direction": "maximize",
                "class": "titer",
                "sample_fraction": "whole_broth",
                "assay_method": "hplc",
                "calibration": "external",
                "matrix_effects_policy": "spike recovery",
                "assay_power_policy": _strong_power_policy(),
            }
        ],
        "factors": [
            {"factor_id": "temp_plate", "type": "continuous", "min": 20, "max": 30, "arm_id": "plate"},
            {"factor_id": "fill_volume_ml", "type": "continuous", "min": 0.5, "max": 1.5, "arm_id": "plate"},
            {"factor_id": "temp_reactor", "type": "continuous", "min": 26, "max": 32, "arm_id": "reactor"},
            {"factor_id": "do_percent", "type": "continuous", "min": 30, "max": 50, "arm_id": "reactor"},
        ],
        "campaign_arms": [
            {"arm_id": "plate", "purpose": "screening", "run_budget": 12, "factor_ids": ["temp_plate", "fill_volume_ml"], "response_ids": ["titer"]},
            {"arm_id": "reactor", "purpose": "bridge", "run_budget": 6, "factor_ids": ["temp_reactor", "do_percent"], "response_ids": ["titer"]},
        ],
        "inputs": [],
        "sources": [],
        "constraints": [],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def _write_results(path: Path, state: dict[str, object], rows: list[tuple[object, object, object, object] | tuple[object, object, object, object, dict[str, str]]]) -> Path:
    headers = ["run_id", "titer", "temp", "ph", "trust_score", "qc_status", "inclusion_status"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for item in rows:
            run_id, value, temp, ph = item[:4]
            extra = item[4] if len(item) > 4 else {}
            row = {"run_id": run_id, "titer": value, "temp": temp, "ph": ph, "trust_score": "0.9", "qc_status": "pass", "inclusion_status": "trusted"}
            row.update(extra)
            writer.writerow(row)
    return path


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    unittest.main()
