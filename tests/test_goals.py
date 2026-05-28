from __future__ import annotations

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

from biosymphony_ferm_doe.adaptive import recommend_wave2  # noqa: E402
from biosymphony_ferm_doe.goals import (  # noqa: E402
    CLAIM_LEVEL,
    evaluate_desirability,
    formulate_goals,
)


def _maximize_response(rid: str, lower: float, upper: float, weight: float = 1.0) -> dict:
    return {
        "response_id": rid,
        "class": "titer",
        "direction": "maximize",
        "objective_lower": lower,
        "objective_upper": upper,
        "objective_weight": weight,
    }


def _minimize_response(rid: str, lower: float, upper: float, weight: float = 1.0) -> dict:
    return {
        "response_id": rid,
        "class": "cost",
        "direction": "minimize",
        "objective_lower": lower,
        "objective_upper": upper,
        "objective_weight": weight,
    }


def _target_response(rid: str, lower: float, target: float, upper: float, weight: float = 1.0) -> dict:
    return {
        "response_id": rid,
        "class": "metabolite",
        "direction": "target",
        "objective_lower": lower,
        "objective_upper": upper,
        "objective_target": target,
        "objective_weight": weight,
    }


def _manifest(*responses: dict, decision_rules: list[dict] | None = None) -> dict:
    return {
        "campaign_id": "demo-goals-test",
        "claim_level": "public_synthetic_demo",
        "responses": list(responses),
        "factors": [{"factor_id": "x", "type": "numeric", "low": 0, "high": 1}],
        "decision_rules": decision_rules or [],
    }


class FormulateGoalsTests(unittest.TestCase):
    def test_returns_none_when_no_bounds_declarable(self) -> None:
        manifest = _manifest({"response_id": "y", "direction": "maximize"})
        self.assertIsNone(formulate_goals(manifest))

    def test_explicit_objective_fields_used(self) -> None:
        manifest = _manifest(_maximize_response("titer", 5, 30))
        goals = formulate_goals(manifest)
        self.assertIsNotNone(goals)
        assert goals is not None  # for mypy
        self.assertEqual(goals["claim_level"], CLAIM_LEVEL)
        self.assertEqual(len(goals["objectives"]), 1)
        objective = goals["objectives"][0]
        self.assertEqual(objective["response_id"], "titer")
        self.assertEqual(objective["lower"], 5)
        self.assertEqual(objective["upper"], 30)
        self.assertEqual(objective["source"], "responses_objective_fields")

    def test_decision_rule_threshold_provides_bounds(self) -> None:
        manifest = _manifest(
            {"response_id": "titer", "direction": "maximize"},
            decision_rules=[
                {
                    "rule_id": "advance",
                    "scope": "response:titer",
                    "comparator": "ge",
                    "threshold": 10,
                    "action": "advance_to_next_wave",
                }
            ],
        )
        goals = formulate_goals(manifest)
        self.assertIsNotNone(goals)
        assert goals is not None
        self.assertEqual(goals["objectives"][0]["lower"], 10)
        self.assertEqual(goals["objectives"][0]["source"], "decision_rules")

    def test_mixed_directions_in_one_manifest(self) -> None:
        manifest = _manifest(
            _maximize_response("titer", 5, 30),
            _minimize_response("run_cost", 100, 1000),
            _target_response("ph", 6.0, 7.0, 8.0),
        )
        goals = formulate_goals(manifest)
        self.assertIsNotNone(goals)
        assert goals is not None
        directions = [obj["direction"] for obj in goals["objectives"]]
        self.assertEqual(sorted(directions), ["maximize", "minimize", "target"])


class EvaluateDesirabilityTests(unittest.TestCase):
    def test_value_above_upper_saturates_to_one(self) -> None:
        goals = formulate_goals(_manifest(_maximize_response("y", 0, 10)))
        result = evaluate_desirability(goals, {"y": 12})
        self.assertEqual(result["per_response"][0]["desirability"], 1.0)

    def test_value_below_lower_floors_at_zero(self) -> None:
        goals = formulate_goals(_manifest(_maximize_response("y", 0, 10)))
        result = evaluate_desirability(goals, {"y": -5})
        self.assertEqual(result["per_response"][0]["desirability"], 0.0)

    def test_linear_maximize_scores_at_midpoint(self) -> None:
        goals = formulate_goals(_manifest(_maximize_response("y", 0, 10)))
        result = evaluate_desirability(goals, {"y": 5})
        self.assertAlmostEqual(result["per_response"][0]["desirability"], 0.5)

    def test_minimize_low_value_high_desirability(self) -> None:
        goals = formulate_goals(_manifest(_minimize_response("cost", 0, 100)))
        result = evaluate_desirability(goals, {"cost": 25})
        self.assertAlmostEqual(result["per_response"][0]["desirability"], 0.75)

    def test_target_peaks_at_target_value(self) -> None:
        goals = formulate_goals(_manifest(_target_response("ph", 6.0, 7.0, 8.0)))
        result = evaluate_desirability(goals, {"ph": 7.0})
        self.assertEqual(result["per_response"][0]["desirability"], 1.0)
        result_off = evaluate_desirability(goals, {"ph": 6.5})
        self.assertAlmostEqual(result_off["per_response"][0]["desirability"], 0.5)

    def test_composite_geometric_mean(self) -> None:
        goals = formulate_goals(_manifest(_maximize_response("a", 0, 10), _maximize_response("b", 0, 10)))
        result = evaluate_desirability(goals, {"a": 5, "b": 5})
        self.assertAlmostEqual(result["composite"], 0.5)

    def test_composite_zero_when_any_response_at_zero_desirability(self) -> None:
        goals = formulate_goals(_manifest(_maximize_response("a", 0, 10), _maximize_response("b", 0, 10)))
        result = evaluate_desirability(goals, {"a": 8, "b": -1})
        self.assertEqual(result["composite"], 0.0)

    def test_missing_value_yields_none_desirability_and_excluded_from_composite(self) -> None:
        goals = formulate_goals(_manifest(_maximize_response("a", 0, 10), _maximize_response("b", 0, 10)))
        result = evaluate_desirability(goals, {"a": 5})  # b missing
        self.assertIsNone(result["per_response"][1]["desirability"])
        self.assertAlmostEqual(result["composite"], 0.5)

    def test_quadratic_shape_steeper_than_linear(self) -> None:
        manifest = _manifest({**_maximize_response("y", 0, 10), "objective_shape": "quadratic"})
        goals = formulate_goals(manifest)
        result = evaluate_desirability(goals, {"y": 5})
        self.assertAlmostEqual(result["per_response"][0]["desirability"], 0.25)


class FollowUpDesirabilityIntegrationTests(unittest.TestCase):
    def test_recommend_wave2_uses_desirability_when_goals_provided(self) -> None:
        manifest = _manifest(
            _maximize_response("titer", 0, 30, weight=1.0),
            _minimize_response("run_cost", 0, 100, weight=1.0),
        )
        manifest["adaptive_wave2"] = {
            "primary_response_id": "titer",
            "claim_level": "planned_wave2_design",
        }
        manifest["factors"] = [{"factor_id": "x", "type": "numeric", "low": 0, "high": 1}]
        rows = [
            {"design_run_id": "D1", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95",
             "titer": "20", "run_cost": "10", "x": "0.4"},
            {"design_run_id": "D2", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.96",
             "titer": "25", "run_cost": "90", "x": "0.6"},
            {"design_run_id": "D3", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.97",
             "titer": "15", "run_cost": "5", "x": "0.5"},
        ]
        goals = formulate_goals(manifest)
        legacy = recommend_wave2(manifest, rows)
        with_goals = recommend_wave2(manifest, rows, goals=goals)
        # Legacy maximizes titer alone — D2 wins.
        self.assertEqual(legacy["best_run_id"], "D2")
        self.assertEqual(legacy["scoring_mode"], "single_response")
        # With desirability, D2 has high titer but bad cost; D1 should beat D2.
        self.assertEqual(with_goals["scoring_mode"], "desirability")
        self.assertIn("best_desirability", with_goals)
        self.assertEqual(with_goals["best_run_id"], "D1")

    def test_recommend_wave2_falls_back_when_goals_none(self) -> None:
        manifest = {
            "campaign_id": "x",
            "claim_level": "public_synthetic_demo",
            "responses": [{"response_id": "titer", "direction": "maximize"}],
            "factors": [{"factor_id": "x", "type": "numeric", "low": 0, "high": 1}],
            "adaptive_wave2": {"primary_response_id": "titer"},
        }
        rows = [
            {"design_run_id": "D1", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.95",
             "titer": "10", "x": "0.5"},
            {"design_run_id": "D2", "qc_status": "pass", "inclusion_status": "include", "trust_score": "0.96",
             "titer": "20", "x": "0.5"},
        ]
        reco = recommend_wave2(manifest, rows, goals=None)
        self.assertEqual(reco["scoring_mode"], "single_response")


class CliGoalsTests(unittest.TestCase):
    def test_cli_emits_goals_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign = root / "campaign"
            campaign.mkdir()
            manifest = _manifest(_maximize_response("titer", 5, 30))
            (campaign / "campaign_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            out = root / "goals.json"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
            completed = subprocess.run(
                [sys.executable, "-m", "biosymphony_ferm_doe.cli", "goals", str(campaign), "--out", str(out)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            summary = json.loads(completed.stdout)
            self.assertEqual(summary["claim_level"], CLAIM_LEVEL)
            self.assertEqual(summary["n_objectives"], 1)
            payload = json.loads(out.read_text())
            self.assertEqual(payload["claim_level"], CLAIM_LEVEL)

    def test_cli_emits_null_goals_when_no_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign = root / "campaign"
            campaign.mkdir()
            manifest = _manifest({"response_id": "y", "direction": "maximize"})
            (campaign / "campaign_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            out = root / "goals.json"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
            completed = subprocess.run(
                [sys.executable, "-m", "biosymphony_ferm_doe.cli", "goals", str(campaign), "--out", str(out)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            summary = json.loads(completed.stdout)
            self.assertEqual(summary["reason"], "no_objective_bounds_declarable")
            payload = json.loads(out.read_text())
            self.assertIsNone(payload["goals"])


if __name__ == "__main__":
    unittest.main()
