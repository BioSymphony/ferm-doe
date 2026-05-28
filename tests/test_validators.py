from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from biosymphony_ferm_doe import validators as V  # noqa: E402
from biosymphony_ferm_doe.doe_families import minimum_runs  # noqa: E402
from biosymphony_ferm_doe.profiles import (  # noqa: E402
    PROFILE_REGISTRY,
    merge_advised_blocks,
    merge_required_blocks,
    resolve_profiles,
)


def _ids(checks: list[dict]) -> set[str]:
    return {c["id"] for c in checks}


def _failed(checks: list[dict]) -> list[dict]:
    return [c for c in checks if not c["ok"]]


class FactorValidatorTests(unittest.TestCase):
    def test_numeric_low_high_swap_is_error(self) -> None:
        manifest = {"factors": [{"factor_id": "x", "type": "numeric", "low": 5, "high": 1}]}
        checks: list[dict] = []
        V._validate_factors(manifest, checks)
        bad = [c for c in checks if c["id"] == "factor-bounds-coherent-x"]
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["severity"], "error")
        self.assertFalse(bad[0]["ok"])

    def test_numeric_missing_bounds_is_warning(self) -> None:
        manifest = {"factors": [{"factor_id": "x", "type": "numeric"}]}
        checks: list[dict] = []
        V._validate_factors(manifest, checks)
        c = next(c for c in checks if c["id"] == "factor-bounds-present-x")
        self.assertFalse(c["ok"])
        self.assertEqual(c["severity"], "warning")

    def test_mixture_without_components_is_warning(self) -> None:
        manifest = {"factors": [{"factor_id": "blend", "type": "mixture"}]}
        checks: list[dict] = []
        V._validate_factors(manifest, checks)
        c = next(c for c in checks if c["id"] == "factor-mixture-blend")
        self.assertFalse(c["ok"])
        self.assertEqual(c["severity"], "warning")

    def test_unknown_type_is_warning_not_error(self) -> None:
        manifest = {"factors": [{"factor_id": "x", "type": "fictional"}]}
        checks: list[dict] = []
        V._validate_factors(manifest, checks)
        c = next(c for c in checks if c["id"] == "factor-type-x")
        self.assertEqual(c["severity"], "warning")

    def test_categorical_one_level_is_warning(self) -> None:
        manifest = {"factors": [{"factor_id": "c", "type": "categorical", "levels": ["only_one"]}]}
        checks: list[dict] = []
        V._validate_factors(manifest, checks)
        c = next(c for c in checks if c["id"] == "factor-levels-c")
        self.assertFalse(c["ok"])
        self.assertEqual(c["severity"], "warning")


class ScaleContextValidatorTests(unittest.TestCase):
    def test_scale_profile_without_scale_context_is_error(self) -> None:
        manifest = {"scale_context": None}
        checks: list[dict] = []
        V._validate_scale_context(manifest, ["scale_down_qualification"], checks)
        bad = [c for c in checks if c["id"] == "scale-context-present" and not c["ok"]]
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["severity"], "error")

    def test_primary_criterion_target_match_warns(self) -> None:
        manifest = {
            "scale_context": {
                "from_scale": {"engineering_targets": {}},
                "to_scale": {"engineering_targets": {"kLa_per_hour": 250}},
                "bridge_strategy": {"primary_criterion": "kLa"},
            }
        }
        checks: list[dict] = []
        V._validate_scale_context(manifest, ["scale_up_bridge"], checks)
        from_check = next(c for c in checks if c["id"] == "scale-criterion-target-from_scale")
        self.assertFalse(from_check["ok"])
        self.assertEqual(from_check["severity"], "warning")

    def test_recapitulation_criterion_warned_when_missing(self) -> None:
        manifest = {"scale_context": {"from_scale": {}, "to_scale": {}, "bridge_strategy": {"primary_criterion": "kLa"}}}
        checks: list[dict] = []
        V._validate_scale_context(manifest, ["scale_down_qualification"], checks)
        c = next(c for c in checks if c["id"] == "scale-recap-criterion")
        self.assertFalse(c["ok"])
        self.assertEqual(c["severity"], "warning")


class DoeFamilyValidatorTests(unittest.TestCase):
    def test_min_runs_shortfall_is_warning(self) -> None:
        manifest = {
            "factors": [{"factor_id": "a", "type": "numeric", "low": 0, "high": 1}, {"factor_id": "b", "type": "numeric", "low": 0, "high": 1}],
            "doe": {"family": "definitive_screening", "n_runs": 3, "randomized": True, "claim": "heuristic"},
        }
        checks: list[dict] = []
        V._validate_doe(manifest, ROOT, checks)
        c = next(c for c in checks if c["id"] == "doe-min-runs")
        self.assertFalse(c["ok"])
        self.assertEqual(c["severity"], "warning")

    def test_unknown_family_is_warning(self) -> None:
        manifest = {"doe": {"family": "fictional", "n_runs": 8}}
        checks: list[dict] = []
        V._validate_doe(manifest, ROOT, checks)
        c = next(c for c in checks if c["id"] == "doe-family-known")
        self.assertFalse(c["ok"])
        self.assertEqual(c["severity"], "warning")

    def test_split_plot_requires_hard_to_change_factor(self) -> None:
        manifest = {
            "factors": [{"factor_id": "x", "type": "numeric", "low": 0, "high": 1}],
            "doe": {"family": "split_plot", "n_runs": 16, "randomized": True, "claim": "heuristic"},
        }
        checks: list[dict] = []
        V._validate_doe(manifest, ROOT, checks)
        c = next(c for c in checks if c["id"] == "doe-hard-to-change")
        self.assertFalse(c["ok"])
        self.assertEqual(c["severity"], "warning")


class DecisionStopRiskValidatorTests(unittest.TestCase):
    def test_decision_rule_missing_action_is_warning(self) -> None:
        manifest = {"decision_rules": [{"rule_id": "r1", "scope": "global", "comparator": "gt", "threshold": 0}]}
        checks: list[dict] = []
        V._validate_decision_rules(manifest, checks)
        c = next(c for c in checks if c["id"] == "decision-rule-r1")
        self.assertFalse(c["ok"])
        self.assertEqual(c["severity"], "warning")

    def test_stop_rule_invalid_action_is_warning(self) -> None:
        manifest = {"stop_rules": [{"rule_id": "s1", "condition": "x > y", "action": "delete_universe"}]}
        checks: list[dict] = []
        V._validate_stop_rules(manifest, checks)
        c = next(c for c in checks if c["id"] == "stop-rule-s1")
        self.assertFalse(c["ok"])
        self.assertEqual(c["severity"], "warning")

    def test_risk_missing_likelihood_is_warning(self) -> None:
        manifest = {"risk_register": [{"risk_id": "r1", "category": "scale_bridge", "impact": "high"}]}
        checks: list[dict] = []
        V._validate_risks(manifest, checks)
        c = next(c for c in checks if c["id"] == "risk-r1")
        self.assertFalse(c["ok"])
        self.assertEqual(c["severity"], "warning")


class ProfileResolutionTests(unittest.TestCase):
    def test_unknown_profile_falls_back_to_custom(self) -> None:
        self.assertEqual(resolve_profiles(["bogus"]), ["custom"])

    def test_multiple_profiles_keep_order(self) -> None:
        self.assertEqual(resolve_profiles(["screening", "scale_down_qualification"]), ["screening", "scale_down_qualification"])

    def test_merge_advised_blocks_unions(self) -> None:
        merged = merge_advised_blocks(["screening", "scale_down_qualification"])
        for slot in ("responses", "factors", "decision_rules", "scale_context", "arms"):
            self.assertIn(slot, merged)

    def test_merge_required_blocks_includes_scale_context(self) -> None:
        merged = merge_required_blocks(["scale_up_bridge"])
        self.assertIn("scale_context", merged)


class MinimumRunsTests(unittest.TestCase):
    def test_dsd(self) -> None:
        self.assertEqual(minimum_runs("definitive_screening", 5), 11)

    def test_full_factorial(self) -> None:
        self.assertEqual(minimum_runs("full_factorial", 3), 8)
        self.assertEqual(minimum_runs("full_factorial", 3, levels_per_factor=[2, 2, 3]), 12)

    def test_box_behnken(self) -> None:
        self.assertEqual(minimum_runs("box_behnken", 3, n_center=3), 15)
        self.assertIsNone(minimum_runs("box_behnken", 2, n_center=3))

    def test_custom_constrained_returns_none(self) -> None:
        self.assertIsNone(minimum_runs("custom_constrained", 4))


class ReadinessShapeTests(unittest.TestCase):
    def test_invalid_overall_warns(self) -> None:
        manifest = {"readiness": {"overall": "PURPLE"}}
        checks: list[dict] = []
        V._validate_readiness_object(manifest, checks)
        c = next(c for c in checks if c["id"] == "readiness-overall")
        self.assertFalse(c["ok"])
        self.assertEqual(c["severity"], "warning")

    def test_invalid_axis_state_warns(self) -> None:
        manifest = {"readiness": {"axes": {"doe": "almost_done"}}}
        checks: list[dict] = []
        V._validate_readiness_object(manifest, checks)
        c = next(c for c in checks if c["id"] == "readiness-axis-doe")
        self.assertFalse(c["ok"])

    def test_nested_axis_dict_validates_each_entry(self) -> None:
        manifest = {"readiness": {"axes": {"factors": {"x": "qualified", "y": "halfway"}}}}
        checks: list[dict] = []
        V._validate_readiness_object(manifest, checks)
        bad = [c for c in checks if c["id"] == "readiness-axis-factors-y" and not c["ok"]]
        self.assertEqual(len(bad), 1)


class AdaptiveFollowUpValidatorTests(unittest.TestCase):
    def test_assay_power_policy_passes_when_required_and_complete(self) -> None:
        manifest = {
            "adaptive_wave2": {"require_assay_power": True},
            "responses": [
                {
                    "response_id": "titer",
                    "measurement_type": "assayed",
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
                }
            ],
        }
        checks: list[dict] = []
        V._validate_assay_power_policy(manifest, checks)
        c = next(c for c in checks if c["id"] == "assay-power-titer")
        self.assertTrue(c["ok"])

    def test_missing_required_assay_power_is_error(self) -> None:
        manifest = {
            "adaptive_wave2": {"require_assay_power": True},
            "responses": [{"response_id": "titer", "measurement_type": "assayed", "assay_required": True}],
        }
        checks: list[dict] = []
        V._validate_assay_power_policy(manifest, checks)
        c = next(c for c in checks if c["id"] == "assay-power-titer")
        self.assertFalse(c["ok"])
        self.assertEqual(c["severity"], "error")

    def test_derived_response_with_assay_power_policy_warns(self) -> None:
        manifest = {
            "responses": [
                {
                    "response_id": "cost",
                    "class": "cost",
                    "measurement_type": "derived",
                    "assay_required": False,
                    "assay_power_policy": {"replicate_count": 3},
                }
            ]
        }
        checks: list[dict] = []
        V._validate_assay_power_policy(manifest, checks)
        c = next(c for c in checks if c["id"] == "assay-power-cost")
        self.assertFalse(c["ok"])
        self.assertEqual(c["severity"], "warning")

    def test_scale_or_downscale_without_bridge_policy_warns(self) -> None:
        manifest = {
            "adaptive_wave2": {
                "claim_level": "planned_wave2_design",
                "requested_action": "scale_or_downscale",
                "self_learning": {"enabled": True, "learning_ledger_path": "wave2/learning_ledger.csv"},
            }
        }
        checks: list[dict] = []
        V._validate_adaptive_wave2(manifest, ROOT, checks)
        c = next(c for c in checks if c["id"] == "adaptive-wave2-bridge-policy")
        self.assertFalse(c["ok"])
        self.assertEqual(c["severity"], "warning")


class AuditSkipMarkerTests(unittest.TestCase):
    def test_skip_re_matches_typical_marker(self) -> None:
        self.assertIsNotNone(V.AUDIT_SKIP_RE.search("# audit-skip: docs example"))
        self.assertIsNotNone(V.AUDIT_SKIP_RE.search("api_key=PLACEHOLDER  # audit-skip: doc"))
        self.assertIsNone(V.AUDIT_SKIP_RE.search("api_key=secret_value"))


if __name__ == "__main__":
    unittest.main()
