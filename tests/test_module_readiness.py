from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from biosymphony_ferm_doe.validators import validate_campaign  # noqa: E402


def _failed(result: dict, check_id: str) -> bool:
    return any(
        c.get("id") == check_id and not c.get("ok")
        for c in (result.get("checks") or [])
    )


class GoalsReadinessTests(unittest.TestCase):
    def test_warns_when_no_objective_bounds_or_numeric_decision_rules(self) -> None:
        # Use the warnings-walkthrough demo which has minimal manifest.
        result = validate_campaign(ROOT / "examples" / "demo-warnings-walkthrough-public")
        # That demo declares a maximize response without bounds; goals readiness should fire.
        self.assertTrue(_failed(result, "module-readiness-goals"))

    def test_passes_when_xylanase_demo_has_objective_bounds(self) -> None:
        result = validate_campaign(ROOT / "examples" / "demo-xylanase-public")
        self.assertFalse(_failed(result, "module-readiness-goals"))


class SamplingReadinessTests(unittest.TestCase):
    def test_passes_for_xylanase_demo_with_assayed_response(self) -> None:
        result = validate_campaign(ROOT / "examples" / "demo-xylanase-public")
        self.assertFalse(_failed(result, "module-readiness-sampling-plan"))


class ScaleRecipeReadinessTests(unittest.TestCase):
    def test_passes_for_scale_bridge_demo_with_kla_target(self) -> None:
        result = validate_campaign(ROOT / "examples" / "demo-scale-bridge-public")
        self.assertFalse(_failed(result, "module-readiness-scale-recipe"))


class BridgeQualificationReadinessTests(unittest.TestCase):
    def test_passes_for_scale_bridge_demo_with_arms_and_scale_context(self) -> None:
        result = validate_campaign(ROOT / "examples" / "demo-scale-bridge-public")
        self.assertFalse(_failed(result, "module-readiness-bridge-qualification"))


class CostRollupReadinessTests(unittest.TestCase):
    def test_skipped_when_resource_costs_block_absent(self) -> None:
        # PB screening demo doesn't declare resource_costs, so the readiness check
        # is silent (not even emitted) — module stays available, just doesn't sum.
        result = validate_campaign(ROOT / "examples" / "demo-pb-screening-public")
        self.assertFalse(_failed(result, "module-readiness-cost-rollup"))


if __name__ == "__main__":
    unittest.main()
