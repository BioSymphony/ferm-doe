from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe import materialization  # noqa: E402
from biosymphony_ferm_doe.compiler import compile_campaign_state  # noqa: E402
from biosymphony_ferm_doe.materialization import materialize_manifest_inputs  # noqa: E402


FIXTURES = ROOT / "tests/fixtures/materialization"


class MaterializationTests(unittest.TestCase):
    def test_json_factor_space_and_constraint_set_materialize_into_state(self) -> None:
        manifest = _manifest(
            inputs=[
                _input("factor_space", FIXTURES / "factor_space.json"),
                _input("constraint_set", FIXTURES / "constraint_set.json"),
            ],
            responses=[],
        )

        state = _compile_temp_manifest(manifest)

        self.assertEqual({factor["factor_id"] for factor in state["factors"]}, {"temp_c", "feed_strategy"})
        self.assertEqual({response["response_id"] for response in state["responses"]}, {"titer_mg_l"})
        self.assertEqual({constraint["constraint_id"] for constraint in state["constraints"]}, {"max_temp", "avoid_feed_temp_corner"})
        self.assertEqual(len(state["materialized_inputs"]), 2)
        self.assertEqual(state["input_conflicts"], [])
        self.assertTrue(all(factor["source"].startswith("input:") for factor in state["factors"]))

    def test_csv_factor_space_and_constraint_set_materialize_without_yaml_dependency(self) -> None:
        manifest = _manifest(
            inputs=[
                _input("factor_space", FIXTURES / "factor_space.csv"),
                _input("constraint_set", FIXTURES / "constraint_set.csv"),
            ],
        )

        state = _compile_temp_manifest(manifest)
        factors = {factor["factor_id"]: factor for factor in state["factors"]}

        self.assertEqual(set(factors), {"ph_setpoint", "carbon_source"})
        self.assertEqual(factors["carbon_source"]["levels"], ["glucose", "glycerol"])
        self.assertEqual({constraint["constraint_id"] for constraint in state["constraints"]}, {"ph_window", "no_glycerol_low_ph"})

    def test_manifest_inline_values_win_and_conflicts_are_recorded(self) -> None:
        manifest = _manifest(
            inputs=[
                _input("factor_space", FIXTURES / "factor_space.json"),
                _input("constraint_set", FIXTURES / "constraint_set.json"),
            ],
            factors=[
                {
                    "factor_id": "temp_c",
                    "name": "Production temperature",
                    "unit": "C",
                    "type": "continuous",
                    "min": 25,
                    "max": 37,
                    "phase": "production",
                }
            ],
            constraints=[
                {
                    "constraint_id": "max_temp",
                    "type": "hard",
                    "description": "Inline temperature ceiling wins.",
                }
            ],
        )

        state = _compile_temp_manifest(manifest)
        factors = {factor["factor_id"]: factor for factor in state["factors"]}
        constraints = {constraint["constraint_id"]: constraint for constraint in state["constraints"]}

        self.assertEqual(factors["temp_c"]["max"], 37)
        self.assertEqual(constraints["max_temp"]["description"], "Inline temperature ceiling wins.")
        self.assertIn("feed_strategy", factors)
        self.assertIn("avoid_feed_temp_corner", constraints)
        conflict_keys = {(conflict.get("section"), conflict.get("record_id"), conflict.get("field")) for conflict in state["input_conflicts"]}
        self.assertIn(("factors", "temp_c", "max"), conflict_keys)
        self.assertIn(("constraints", "max_temp", "description"), conflict_keys)
        self.assertTrue(all(conflict.get("resolution") == "manifest_inline_wins" for conflict in state["input_conflicts"]))

    def test_multi_arm_factor_space_requires_active_factor_space_for_flattening(self) -> None:
        manifest = _manifest(inputs=[_input("factor_space", FIXTURES / "multi_arm_factor_space.json")], responses=[])

        with tempfile.TemporaryDirectory() as tmp:
            result = materialize_manifest_inputs(manifest, Path(tmp) / "campaign_manifest.json")

        self.assertEqual(result["factors"], [])
        input_summary = result["materialized_inputs"][0]
        self.assertTrue(input_summary["preserved_multi_arm"])
        self.assertEqual(input_summary["arms"], ["plate", "reactor"])
        self.assertEqual(len(input_summary["factor_space"]["arms"]), 2)
        blockers = [issue for issue in result["input_conflicts"] if issue["severity"] == "blocker"]
        self.assertTrue(any(issue["code"] == "active_factor_space_required" for issue in blockers))

        state = _compile_temp_manifest(manifest)
        self.assertEqual(state["factors"], [])
        self.assertEqual(state["readiness_precheck"]["status"], "RED")
        self.assertIn("factors must be a non-empty list", state["schema_errors"])

    def test_active_factor_space_flattens_only_selected_arm(self) -> None:
        manifest = _manifest(
            inputs=[_input("factor_space", FIXTURES / "multi_arm_factor_space.json")],
            design_policy={"active_factor_space": "reactor"},
            responses=[],
        )

        state = _compile_temp_manifest(manifest)
        factors = {factor["factor_id"]: factor for factor in state["factors"]}

        self.assertEqual(set(factors), {"reactor_temp_c", "feed_rate_ml_h"})
        self.assertTrue(all(factor["arm_id"] == "reactor" for factor in factors.values()))
        self.assertEqual(state["materialized_inputs"][0]["active_factor_space"], "reactor")
        self.assertEqual(state["materialized_inputs"][0]["flattening"], "active_arm")

    def test_yaml_stdlib_fallback_materializes_when_pyyaml_is_unavailable(self) -> None:
        manifest = _manifest(inputs=[_input("factor_space", FIXTURES / "factor_space.yaml")])

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(materialization.importlib, "import_module", side_effect=ImportError("no yaml")):
                result = materialize_manifest_inputs(manifest, Path(tmp) / "campaign_manifest.json")

        self.assertEqual({factor["factor_id"] for factor in result["factors"]}, {"oxygen_pct"})
        self.assertEqual({response["response_id"] for response in result["responses"]}, {"titer_mg_l"})
        self.assertEqual(result["input_conflicts"], [])

    def test_yaml_factor_space_materializes_when_pyyaml_is_available(self) -> None:
        try:
            __import__("yaml")
        except ImportError:
            self.skipTest("PyYAML is not installed")

        manifest = _manifest(inputs=[_input("factor_space", FIXTURES / "factor_space.yaml")], responses=[])
        state = _compile_temp_manifest(manifest)

        self.assertEqual({factor["factor_id"] for factor in state["factors"]}, {"oxygen_pct"})
        self.assertEqual({response["response_id"] for response in state["responses"]}, {"titer_mg_l"})


def _input(input_id: str, path: Path) -> dict[str, str]:
    return {"input_id": input_id, "kind": input_id, "path": str(path)}


def _manifest(
    *,
    inputs: list[dict[str, str]],
    factors: list[dict[str, object]] | None = None,
    responses: list[dict[str, object]] | None = None,
    constraints: list[dict[str, object]] | None = None,
    design_policy: dict[str, object] | None = None,
) -> dict[str, object]:
    manifest: dict[str, object] = {
        "schema_version": 1,
        "campaign_id": "materialization-test",
        "name": "Materialization test",
        "objective": {
            "primary": "Maximize titer.",
            "direction": "maximize",
            "response_id": "titer_mg_l",
        },
        "readiness_target": "YELLOW",
        "sources": [],
        "inputs": inputs,
    }
    if factors is not None:
        manifest["factors"] = factors
    if responses is None:
        responses = [
            {
                "response_id": "titer_mg_l",
                "name": "Titer",
                "unit": "mg/L",
                "direction": "maximize",
                "class": "titer",
                "sample_fraction": "whole_broth",
                "assay_method": "hplc",
            }
        ]
    if responses is not None:
        manifest["responses"] = responses
    if constraints is not None:
        manifest["constraints"] = constraints
    if design_policy is not None:
        manifest["design_policy"] = design_policy
    return manifest


def _compile_temp_manifest(manifest: dict[str, object]) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        manifest_path = Path(tmp) / "campaign_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        return compile_campaign_state(manifest_path)


if __name__ == "__main__":
    unittest.main()
