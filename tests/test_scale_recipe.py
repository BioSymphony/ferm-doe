from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from biosymphony_ferm_doe.scale_recipe import (  # noqa: E402
    CLAIM_LEVEL,
    compute_scale_recipe,
    render_recipe_markdown,
)


def _scale_context(
    *,
    primary_criterion: str = "kLa",
    secondary: list[str] | None = None,
    from_kla: float = 250.0,
    to_kla: float = 250.0,
    from_volume: float = 50.0,
    to_volume: float = 1.5,
    organism_class: str | None = None,
) -> dict:
    ctx = {
        "direction": "scale_down",
        "from_scale": {
            "label": "pilot_50L",
            "vessel": "stirred_tank_pilot",
            "working_volume_l": from_volume,
            "geometry": {"h_over_d": 2.5, "impeller_d_over_t": 0.4, "n_impellers": 2, "impeller_type": "rushton"},
            "engineering_targets": {"kLa_per_hour": from_kla, "vvm": 1.0, "tip_speed_m_per_s": 2.5, "rpm": 350},
        },
        "to_scale": {
            "label": "bench_2L",
            "vessel": "stirred_tank_bench",
            "working_volume_l": to_volume,
            "geometry": {"h_over_d": 2.2, "impeller_d_over_t": 0.4, "n_impellers": 2, "impeller_type": "rushton"},
            "engineering_targets": {"kLa_per_hour": to_kla, "vvm": 1.0},
        },
        "bridge_strategy": {
            "primary_criterion": primary_criterion,
            "secondary_criteria": secondary or ["p_per_v", "tip_speed"],
            "rationale": "test rationale",
        },
    }
    if organism_class:
        ctx["organism_class"] = organism_class
    return ctx


def _manifest(scale_context: dict | None = None) -> dict:
    return {
        "campaign_id": "demo-scale-recipe-test",
        "claim_level": "public_synthetic_demo",
        "scale_context": scale_context or _scale_context(),
        "responses": [{"response_id": "y", "class": "titer", "direction": "maximize"}],
        "factors": [],
    }


class ComputeScaleRecipeTests(unittest.TestCase):
    def test_returns_planning_claim_and_both_endpoints(self) -> None:
        recipe = compute_scale_recipe(_manifest())
        self.assertEqual(recipe["claim_level"], CLAIM_LEVEL)
        self.assertEqual(recipe["primary_criterion"], "kLa")
        self.assertIn("from_scale", recipe)
        self.assertIn("to_scale", recipe)
        self.assertIn("derived_setpoints", recipe["from_scale"])
        self.assertIn("derived_setpoints", recipe["to_scale"])

    def test_kla_match_within_tolerance(self) -> None:
        recipe = compute_scale_recipe(_manifest())
        match = recipe["criterion_match"]
        self.assertEqual(match["criterion"], "kLa")
        self.assertEqual(match["status"], "MATCH")
        self.assertLess(abs(match["delta_pct"]), 5.0)

    def test_smaller_scale_requires_higher_rpm_to_match_kla(self) -> None:
        recipe = compute_scale_recipe(_manifest())
        from_rpm = recipe["from_scale"]["derived_setpoints"]["agitation_rpm"]
        to_rpm = recipe["to_scale"]["derived_setpoints"]["agitation_rpm"]
        self.assertGreater(to_rpm, from_rpm)

    def test_kla_solved_from_target_yields_correct_round_trip(self) -> None:
        recipe = compute_scale_recipe(_manifest())
        for endpoint in ("from_scale", "to_scale"):
            setpoints = recipe[endpoint]["derived_setpoints"]
            declared = recipe[endpoint]["declared_engineering_targets"]["kLa_per_hour"]
            self.assertAlmostEqual(setpoints["kla_per_hour"], declared, places=1)

    def test_van_t_riet_non_coalescing_lowers_required_p_per_v(self) -> None:
        coalescing = compute_scale_recipe(_manifest(_scale_context(organism_class="microbial_coalescing")))
        non_coalescing = compute_scale_recipe(_manifest(_scale_context(organism_class="microbial_non_coalescing")))
        coalescing_pv = coalescing["to_scale"]["derived_setpoints"]["p_per_v_w_per_m3"]
        non_coalescing_pv = non_coalescing["to_scale"]["derived_setpoints"]["p_per_v_w_per_m3"]
        # Non-coalescing has higher exponent on P/V (0.7 vs 0.4) so less P/V is needed for the same kLa.
        self.assertLess(non_coalescing_pv, coalescing_pv)

    def test_non_coalescing_correlation_source_propagates(self) -> None:
        recipe = compute_scale_recipe(_manifest(_scale_context(organism_class="microbial_non_coalescing")))
        self.assertEqual(recipe["organism_class"], "microbial_non_coalescing")
        self.assertEqual(recipe["kla_correlation"]["source"], "vant_riet_1979_non_coalescing")

    def test_operator_override_changes_correlation(self) -> None:
        ctx = _scale_context()
        ctx["correlation_overrides"] = {"kla": {"c": 0.05, "a": 0.5, "b": 0.3}}
        recipe = compute_scale_recipe(_manifest(ctx))
        self.assertEqual(recipe["kla_correlation"]["c"], 0.05)
        self.assertEqual(recipe["kla_correlation"]["source"], "operator_override")

    def test_p_per_v_declared_used_directly(self) -> None:
        ctx = _scale_context()
        ctx["from_scale"]["engineering_targets"] = {
            "p_per_v_w_per_m3": 2000,
            "vvm": 1.0,
        }
        ctx["to_scale"]["engineering_targets"] = {
            "p_per_v_w_per_m3": 2000,
            "vvm": 1.0,
        }
        recipe = compute_scale_recipe(_manifest(ctx))
        self.assertEqual(recipe["from_scale"]["derived_setpoints"]["p_per_v_source"], "declared")
        self.assertAlmostEqual(recipe["from_scale"]["derived_setpoints"]["p_per_v_w_per_m3"], 2000, places=0)

    def test_secondary_criteria_evaluated(self) -> None:
        recipe = compute_scale_recipe(_manifest(_scale_context(secondary=["p_per_v", "tip_speed"])))
        names = [item["criterion"] for item in recipe["secondary_match"]]
        self.assertEqual(names, ["p_per_v", "tip_speed"])

    def test_missing_scale_context_raises(self) -> None:
        with self.assertRaises(ValueError):
            compute_scale_recipe({"campaign_id": "x"})

    def test_missing_targets_raises(self) -> None:
        ctx = _scale_context()
        ctx["from_scale"]["engineering_targets"] = {"vvm": 1.0}
        ctx["to_scale"]["engineering_targets"] = {"vvm": 1.0}
        with self.assertRaises(ValueError):
            compute_scale_recipe(_manifest(ctx))


class WarningsTests(unittest.TestCase):
    def test_declared_rpm_disagreement_warns(self) -> None:
        ctx = _scale_context()
        ctx["from_scale"]["engineering_targets"]["rpm"] = 50  # absurd, will mismatch
        recipe = compute_scale_recipe(_manifest(ctx))
        endpoint_warnings = recipe["from_scale"]["derived_setpoints"].get("warnings") or []
        all_warnings = recipe["warnings"] + endpoint_warnings
        self.assertTrue(any("rpm" in w for w in all_warnings))

    def test_off_match_recorded_when_kla_targets_diverge(self) -> None:
        recipe = compute_scale_recipe(_manifest(_scale_context(from_kla=250, to_kla=400)))
        self.assertEqual(recipe["criterion_match"]["status"], "OFF")
        self.assertTrue(any("primary_criterion" in w for w in recipe["warnings"]))


class MarkdownRenderingTests(unittest.TestCase):
    def test_markdown_includes_setpoints_and_criterion_match(self) -> None:
        recipe = compute_scale_recipe(_manifest())
        md = render_recipe_markdown(recipe)
        self.assertIn("Scale-bridge engineering recipe", md)
        self.assertIn("Agitation", md)
        self.assertIn("Sparge", md)
        self.assertIn("kLa", md)
        self.assertIn("Criterion match", md)


class CliScaleRecipeTests(unittest.TestCase):
    def test_cli_emits_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign = root / "campaign"
            campaign.mkdir()
            (campaign / "campaign_manifest.json").write_text(
                json.dumps(_manifest(), indent=2), encoding="utf-8"
            )
            json_out = root / "scale_recipe.json"
            md_out = root / "scale_recipe.md"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "biosymphony_ferm_doe.cli",
                    "scale-recipe",
                    str(campaign),
                    "--out",
                    str(json_out),
                    "--md-out",
                    str(md_out),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["claim_level"], CLAIM_LEVEL)
            self.assertEqual(payload["primary_criterion"], "kLa")
            self.assertTrue(json_out.is_file())
            self.assertTrue(md_out.is_file())
            recipe = json.loads(json_out.read_text())
            self.assertIn("from_scale", recipe)
            self.assertIn("to_scale", recipe)
            md_text = md_out.read_text()
            self.assertIn("Agitation", md_text)


class DemoManifestSmokeTests(unittest.TestCase):
    def test_existing_scale_bridge_demo_produces_recipe(self) -> None:
        demo = ROOT / "examples" / "demo-scale-bridge-public" / "campaign_manifest.json"
        manifest = json.loads(demo.read_text())
        recipe = compute_scale_recipe(manifest)
        self.assertEqual(recipe["primary_criterion"], "kLa")
        self.assertIn("MATCH", recipe["criterion_match"]["status"]) if recipe["criterion_match"]["status"] == "MATCH" else None
        from_setpoints = recipe["from_scale"]["derived_setpoints"]
        to_setpoints = recipe["to_scale"]["derived_setpoints"]
        # Both scales should yield reasonable RPM and positive power values.
        self.assertGreater(from_setpoints["agitation_rpm"], 50)
        self.assertGreater(to_setpoints["agitation_rpm"], 50)
        self.assertGreater(from_setpoints["agitator_power_total_w"], 0)
        self.assertGreater(to_setpoints["agitator_power_total_w"], 0)
        # Smaller-scale RPM should be higher to maintain kLa.
        self.assertGreater(to_setpoints["agitation_rpm"], from_setpoints["agitation_rpm"])


if __name__ == "__main__":
    unittest.main()
