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

from biosymphony_ferm_doe.doe_power import (  # noqa: E402
    CLAIM_LEVEL,
    compute_doe_power,
    render_doe_power_markdown,
)


def _manifest(family: str = "plackett_burman", k: int = 7, expected_effect: float = 5.0) -> dict:
    factors = [
        {"factor_id": f"x{i}", "type": "numeric", "low": 0.0, "high": 10.0}
        for i in range(1, k + 1)
    ]
    return {
        "campaign_id": "demo-doe-power-test",
        "claim_level": "public_synthetic_demo",
        "responses": [
            {
                "response_id": "y",
                "class": "titer",
                "direction": "maximize",
                "assay_required": True,
                "assay_power_policy": {"expected_effect_size": expected_effect},
            }
        ],
        "factors": factors,
        "doe": {"family": family, "model_terms": ["main_effects"], "randomized": False},
    }


class ComputeDoePowerTests(unittest.TestCase):
    def test_pb_8_runs_7_factors_returns_per_coef_table(self) -> None:
        result = compute_doe_power(_manifest(), sigma=2.0)
        self.assertEqual(result["claim_level"], CLAIM_LEVEL)
        self.assertEqual(result["n_runs"], 8)
        self.assertEqual(result["n_parameters"], 8)  # intercept + 7 mains
        self.assertEqual(result["df_residual"], 0)
        self.assertEqual(len(result["coefficients"]), 8)
        for coef in result["coefficients"]:
            self.assertGreater(coef["mde_at_target_power"], 0.0)

    def test_main_effects_have_uniform_se_for_pb(self) -> None:
        # PB designs are orthogonal — main-effect SE should be identical.
        result = compute_doe_power(_manifest(), sigma=1.0)
        main_se = [coef["se"] for coef in result["coefficients"] if coef["kind"] == "main_numeric"]
        for se in main_se[1:]:
            self.assertAlmostEqual(se, main_se[0], places=4)

    def test_sigma_scales_mde_linearly(self) -> None:
        a = compute_doe_power(_manifest(), sigma=1.0)
        b = compute_doe_power(_manifest(), sigma=4.0)
        for coef_a, coef_b in zip(a["coefficients"], b["coefficients"]):
            self.assertAlmostEqual(coef_b["mde_at_target_power"], 4.0 * coef_a["mde_at_target_power"], places=4)

    def test_expected_effect_passes_when_mde_below_expected(self) -> None:
        # 7-factor PB with σ=0.5 keeps MDE well below an expected effect of 5.
        result = compute_doe_power(_manifest(expected_effect=5.0), sigma=0.5)
        passing = [c for c in result["coefficients"] if c.get("expected_passes_mde")]
        self.assertEqual(len(passing), 7)  # 7 main-effect coefficients all pass

    def test_expected_effect_fails_when_sigma_dwarfs_signal(self) -> None:
        result = compute_doe_power(_manifest(expected_effect=1.0), sigma=10.0)
        passing = [c for c in result["coefficients"] if c.get("expected_passes_mde")]
        self.assertEqual(len(passing), 0)

    def test_alpha_and_power_change_mde(self) -> None:
        baseline = compute_doe_power(_manifest(), sigma=1.0, alpha=0.05, target_power=0.8)
        stricter = compute_doe_power(_manifest(), sigma=1.0, alpha=0.01, target_power=0.95)
        for c_base, c_strict in zip(baseline["coefficients"], stricter["coefficients"]):
            self.assertGreater(c_strict["mde_at_target_power"], c_base["mde_at_target_power"])

    def test_invalid_sigma_raises(self) -> None:
        with self.assertRaises(ValueError):
            compute_doe_power(_manifest(), sigma=0.0)

    def test_invalid_alpha_raises(self) -> None:
        with self.assertRaises(ValueError):
            compute_doe_power(_manifest(), sigma=1.0, alpha=0.0)


class CcdPowerTests(unittest.TestCase):
    def test_ccd_with_quadratic_terms(self) -> None:
        manifest = {
            "campaign_id": "demo-ccd-power",
            "claim_level": "public_synthetic_demo",
            "responses": [
                {"response_id": "y", "direction": "maximize", "assay_required": True,
                 "assay_power_policy": {"expected_effect_size": 5.0}}
            ],
            "factors": [
                {"factor_id": "x1", "type": "numeric", "low": 0, "high": 10},
                {"factor_id": "x2", "type": "numeric", "low": 0, "high": 10},
                {"factor_id": "x3", "type": "numeric", "low": 0, "high": 10},
            ],
            "doe": {
                "family": "central_composite",
                "model_terms": ["main_effects", "two_factor_interactions", "quadratic"],
                "randomized": False,
            },
        }
        result = compute_doe_power(manifest, sigma=1.0)
        kinds = {coef["kind"] for coef in result["coefficients"]}
        self.assertIn("intercept", kinds)
        self.assertIn("main_numeric", kinds)
        self.assertIn("two_factor", kinds)
        self.assertIn("quadratic", kinds)
        self.assertGreater(result["df_residual"], 0)


class MarkdownTests(unittest.TestCase):
    def test_markdown_renders(self) -> None:
        result = compute_doe_power(_manifest(), sigma=1.0)
        md = render_doe_power_markdown(result)
        self.assertIn("DoE-level power", md)
        self.assertIn("Term", md)
        self.assertIn("MDE", md)


class CliDoePowerTests(unittest.TestCase):
    def test_cli_emits_summary_and_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign = root / "campaign"
            campaign.mkdir()
            (campaign / "campaign_manifest.json").write_text(json.dumps(_manifest()), encoding="utf-8")
            out = root / "doe_power.json"
            md_out = root / "doe_power.md"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
            completed = subprocess.run(
                [
                    sys.executable, "-m", "biosymphony_ferm_doe.cli", "doe-power",
                    str(campaign), "--out", str(out), "--md-out", str(md_out),
                    "--sigma", "1.5", "--alpha", "0.05", "--target-power", "0.8",
                ],
                cwd=ROOT, env=env, text=True, capture_output=True, check=True,
            )
            summary = json.loads(completed.stdout)
            self.assertEqual(summary["claim_level"], CLAIM_LEVEL)
            self.assertEqual(summary["sigma"], 1.5)
            self.assertEqual(summary["n_runs"], 8)
            self.assertTrue(out.is_file())
            self.assertTrue(md_out.is_file())


if __name__ == "__main__":
    unittest.main()
