from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.doe import propose_candidate_designs
from biosymphony_ferm_doe.model_matrix import diagnose_design
from biosymphony_ferm_doe.tournament import run_design_tournament
from biosymphony_ferm_doe.utilities.custom_optimal import run_custom_optimal_utility


DOE_REFERENCE_MANIFEST = ROOT / "examples/reference-doe-custom-design/campaign_manifest.json"


class DoeParityV1Tests(unittest.TestCase):
    def test_rsm_intent_rejects_rank_deficient_designs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "rsm.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "campaign_id": "rank-deficient-rsm",
                        "name": "Rank deficient RSM",
                        "objective": {"primary": "Fit RSM", "direction": "maximize", "response_id": "titer"},
                        "readiness_target": "YELLOW",
                        "design_policy": {"run_budget": 5, "design_intent": "rsm_fit"},
                        "model_terms": {"interactions": True, "quadratics": True},
                        "sources": [],
                        "inputs": [],
                        "constraints": [],
                        "responses": [{"response_id": "titer", "name": "Titer", "unit": "g/L", "direction": "maximize", "class": "titer", "sample_fraction": "whole_broth", "assay_method": "hplc", "calibration": "external"}],
                        "factors": [
                            {"factor_id": "temp", "type": "continuous", "min": 20, "max": 30},
                            {"factor_id": "ph", "type": "continuous", "min": 5, "max": 7},
                            {"factor_id": "feed", "type": "continuous", "min": 1, "max": 5},
                        ],
                    }
                )
            )
            tournament = run_design_tournament(manifest, out_dir=Path(tmp) / "out", run_budget=5)
            self.assertEqual(tournament["verdict"], "no_accepted_design")
            self.assertTrue(any("requires a full-rank" in reason for item in tournament["candidates"] for reason in item["rejection_reasons"]))

    def test_truncated_full_factorial_is_not_exact(self) -> None:
        designs = propose_candidate_designs(DOE_REFERENCE_MANIFEST, run_budget=8)
        full = next(candidate for candidate in designs["candidates"] if candidate["design_id"] == "full_factorial")
        self.assertEqual(full["exactness"], "heuristic")
        self.assertIn("truncated", full["backend_status"])

    def test_minimum_exactness_rejects_stdlib_like_generators(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = json.loads(DOE_REFERENCE_MANIFEST.read_text())
            source["campaign_id"] = "exact-required"
            source["design_policy"]["run_budget"] = 8
            source["design_policy"]["minimum_exactness"] = "exact"
            manifest = Path(tmp) / "exact.json"
            manifest.write_text(json.dumps(source))
            tournament = run_design_tournament(manifest, out_dir=Path(tmp) / "out", run_budget=8)
            self.assertTrue(any("below required exact" in reason for item in tournament["candidates"] for reason in item["rejection_reasons"]))

    def test_available_numpy_is_not_reported_as_backend_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "custom"
            run_custom_optimal_utility(DOE_REFERENCE_MANIFEST, out, run_budget=6, backend="auto")
            manifest = json.loads((out / "utility_manifest.json").read_text())
            self.assertFalse(manifest["backend"]["adapter_executed"])
            self.assertNotEqual(manifest["backend"]["status"], "adapter_backed")

    def test_categorical_aliasing_uses_cramers_v(self) -> None:
        factors = [
            {"factor_id": "media", "type": "categorical", "levels": ["a", "b"]},
            {"factor_id": "operator_block", "type": "categorical", "levels": ["x", "y"]},
        ]
        rows = [
            {"run_id": "R1", "media": "a", "operator_block": "x"},
            {"run_id": "R2", "media": "a", "operator_block": "x"},
            {"run_id": "R3", "media": "b", "operator_block": "y"},
            {"run_id": "R4", "media": "b", "operator_block": "y"},
        ]
        diagnostics = diagnose_design(rows, factors, [], {"interactions": False, "quadratics": False})
        self.assertEqual(diagnostics["categorical_aliasing"]["flagged_pairs"][0]["cramers_v"], 1.0)

    def test_constant_factor_is_reported(self) -> None:
        factors = [
            {"factor_id": "temp", "type": "continuous", "min": 20, "max": 30},
            {"factor_id": "ph", "type": "continuous", "min": 5, "max": 7},
        ]
        rows = [
            {"run_id": "R1", "temp": "25", "ph": "5"},
            {"run_id": "R2", "temp": "25", "ph": "7"},
        ]
        diagnostics = diagnose_design(rows, factors, [], {"interactions": False, "quadratics": False})
        self.assertIn("temp", diagnostics["factor_variance_report"]["constant_factors"])

    def test_user_supplied_design_is_imported_validated_and_claim_labeled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            design = tmp_path / "user_design.csv"
            design.write_text("run_id,temp,ph\nU1,20,5\nU2,30,5\nU3,20,7\nU4,30,7\n")
            manifest = tmp_path / "user_design_manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "campaign_id": "user-supplied-design-demo",
                        "name": "User supplied design demo",
                        "objective": {"primary": "Validate imported rows", "direction": "maximize", "response_id": "titer"},
                        "readiness_target": "YELLOW",
                        "product_class": "extracellular enzyme",
                        "assay_method": "hplc",
                        "sample_fraction": "whole_broth",
                        "standard_curve": "external standard",
                        "matrix_effects_policy": "spike recovery before execution",
                        "design_policy": {
                            "design_intent": "user_supplied_design",
                            "user_supplied_design": "user_design.csv",
                            "user_supplied_exactness": "heuristic",
                        },
                        "sources": [],
                        "inputs": [],
                        "constraints": [],
                        "responses": [{"response_id": "titer", "name": "Titer", "unit": "g/L", "direction": "maximize", "class": "titer", "sample_fraction": "whole_broth", "assay_method": "hplc", "calibration": "external", "matrix_effects_policy": "spike recovery before execution"}],
                        "factors": [
                            {"factor_id": "temp", "type": "continuous", "min": 20, "max": 30},
                            {"factor_id": "ph", "type": "continuous", "min": 5, "max": 7},
                        ],
                    }
                )
            )

            designs = propose_candidate_designs(manifest)
            imported = next(candidate for candidate in designs["candidates"] if candidate["design_id"] == "user_supplied_design")
            self.assertEqual(imported["method_family"], "user_supplied_design")
            self.assertEqual(imported["backend_used"], "user_csv_import")
            self.assertEqual(imported["claim_level"], "planned_heuristic_design")
            self.assertEqual(imported["diagnostics"]["constraint_violations"], [])

            tournament = run_design_tournament(manifest, out_dir=tmp_path / "out")
            self.assertEqual(tournament["selected_design_id"], "user_supplied_design")
            self.assertTrue(tournament["selected"]["accepted"], tournament["selected"]["rejection_reasons"])


if __name__ == "__main__":
    unittest.main()
