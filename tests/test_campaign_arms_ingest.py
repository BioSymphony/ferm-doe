from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.compiler import compile_campaign_state  # noqa: E402
from biosymphony_ferm_doe.ingest import ingest_wave_results  # noqa: E402


INLINE_MULTI_ARM = ROOT / "tests/fixtures/campaign_arms/inline_multi_arm_manifest.json"


class CampaignArmsIngestTests(unittest.TestCase):
    def test_multi_arm_results_require_arm_id_for_join(self) -> None:
        state = compile_campaign_state(INLINE_MULTI_ARM)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_path = tmp_path / "state.json"
            selected_path = tmp_path / "selected.csv"
            results_path = tmp_path / "results.csv"
            state_path.write_text(json.dumps(state))
            selected_path.write_text("arm_id,run_id,titer_mg_l\nplate,plate:LHS-001,\n")
            results_path.write_text("run_id,titer_mg_l\nplate:LHS-001,10\n")

            result = ingest_wave_results(state_path, results_path, tmp_path / "out", selected_path)

        self.assertEqual(result["recommended_action"], "pause")
        self.assertTrue(any("lack arm_id" in issue for issue in result["issues"]))
        self.assertEqual(result["execution_join_report"]["arm_aware"], True)

    def test_multi_arm_join_uses_arm_id_and_run_id(self) -> None:
        state = compile_campaign_state(INLINE_MULTI_ARM)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_path = tmp_path / "state.json"
            selected_path = tmp_path / "selected.csv"
            results_path = tmp_path / "results.csv"
            state_path.write_text(json.dumps(state))
            selected_path.write_text("arm_id,run_id,titer_mg_l\nplate,R-001,\n")
            results_path.write_text("arm_id,run_id,titer_mg_l\nreactor,R-001,10\n")

            result = ingest_wave_results(state_path, results_path, tmp_path / "out", selected_path)

        self.assertEqual(result["recommended_action"], "pause")
        self.assertTrue(any("reactor/R-001" in issue for issue in result["issues"]))

    def test_negative_memory_is_arm_scoped(self) -> None:
        state = compile_campaign_state(INLINE_MULTI_ARM)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_path = tmp_path / "state.json"
            selected_path = tmp_path / "selected.csv"
            results_path = tmp_path / "results.csv"
            state_path.write_text(json.dumps(state))
            selected_path.write_text("arm_id,run_id,titer_mg_l\nplate,plate:R1,\nplate,plate:R2,\nplate,plate:R3,\n")
            results_path.write_text("arm_id,run_id,titer_mg_l\nplate,plate:R1,100\nplate,plate:R2,20\nplate,plate:R3,80\n")

            result = ingest_wave_results(state_path, results_path, tmp_path / "out", selected_path)

        memory = result["negative_result_memory"]
        self.assertEqual(len(memory), 1)
        self.assertEqual(memory[0]["arm_id"], "plate")
        self.assertEqual(memory[0]["run_id"], "plate:R2")

    def test_cross_arm_factor_values_pause_ingestion(self) -> None:
        state = compile_campaign_state(INLINE_MULTI_ARM)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_path = tmp_path / "state.json"
            selected_path = tmp_path / "selected.csv"
            results_path = tmp_path / "results.csv"
            state_path.write_text(json.dumps(state))
            selected_path.write_text("arm_id,run_id,titer_mg_l\nplate,plate:R1,\nplate,plate:R2,\nplate,plate:R3,\n")
            results_path.write_text(
                "arm_id,run_id,plate_ph,reactor_temp_c,titer_mg_l\n"
                "plate,plate:R1,7.0,28,10\n"
                "plate,plate:R2,7.1,,12\n"
                "plate,plate:R3,7.2,,14\n"
            )

            result = ingest_wave_results(state_path, results_path, tmp_path / "out", selected_path)

        self.assertEqual(result["recommended_action"], "pause")
        self.assertTrue(any("outside its arm" in issue for issue in result["issues"]))

    def test_scale_or_downscale_request_requires_bridge_eligibility(self) -> None:
        state = compile_campaign_state(INLINE_MULTI_ARM)
        state["design_policy"]["requested_next_action"] = "scale_or_downscale"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_path = tmp_path / "state.json"
            selected_path = tmp_path / "selected.csv"
            results_path = tmp_path / "results.csv"
            state_path.write_text(json.dumps(state))
            selected_path.write_text("arm_id,run_id,titer_mg_l\nplate,plate:R1,\nplate,plate:R2,\nplate,plate:R3,\n")
            results_path.write_text("arm_id,run_id,titer_mg_l\nplate,plate:R1,100\nplate,plate:R2,70\nplate,plate:R3,80\n")

            result = ingest_wave_results(state_path, results_path, tmp_path / "out", selected_path)

        self.assertEqual(result["recommended_action"], "pause")
        self.assertFalse(result["bridge_eligibility_report"]["scale_or_downscale_allowed"])
        self.assertTrue(any("scale_or_downscale" in issue for issue in result["issues"]))

    def test_scale_or_downscale_request_passes_with_bridge_eligibility(self) -> None:
        state = compile_campaign_state(INLINE_MULTI_ARM)
        state["design_policy"]["requested_next_action"] = "scale_or_downscale"
        state["arm_bridge_policy"] = _passing_bridge_policy()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_path = tmp_path / "state.json"
            selected_path = tmp_path / "selected.csv"
            results_path = tmp_path / "results.csv"
            state_path.write_text(json.dumps(state))
            selected_path.write_text("arm_id,run_id,titer_mg_l\nplate,plate:R1,\nplate,plate:R2,\nplate,plate:R3,\n")
            results_path.write_text("arm_id,run_id,titer_mg_l\nplate,plate:R1,100\nplate,plate:R2,70\nplate,plate:R3,80\n")

            result = ingest_wave_results(state_path, results_path, tmp_path / "out", selected_path)

        self.assertEqual(result["recommended_action"], "scale_or_downscale")
        self.assertTrue(result["bridge_eligibility_report"]["scale_or_downscale_allowed"])
        self.assertEqual(result["bridge_eligibility_report"]["status"], "PASS")
        self.assertEqual(result["augment_design_recommendation"]["strategy"], "scale_or_downscale_after_transfer_gate")
        self.assertFalse(any("No declared bridge" in issue for issue in result["issues"]))


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
                "claim_boundary": "planning_prior_only",
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
