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

from biosymphony_ferm_doe.analysis import (  # noqa: E402
    CLAIM_LEVEL,
    analyze_results,
    render_analysis_markdown,
)


def _manifest(*, model_terms: list[str] | None = None) -> dict:
    return {
        "campaign_id": "demo-analysis-test",
        "claim_level": "public_synthetic_demo",
        "responses": [
            {"response_id": "y", "class": "titer", "direction": "maximize", "assay_required": True},
        ],
        "factors": [
            {"factor_id": "x1", "type": "numeric", "low": 0.0, "high": 1.0},
            {"factor_id": "x2", "type": "numeric", "low": 0.0, "high": 1.0},
            {"factor_id": "x3", "type": "numeric", "low": 0.0, "high": 1.0},
        ],
        "doe": {
            "family": "fractional_factorial",
            "model_terms": model_terms or ["main_effects"],
        },
    }


def _two_level_rows(coefficients: tuple[float, float, float], intercept: float = 5.0) -> list[dict]:
    """Build 8 rows of a 2^3 full factorial with response y = intercept + sum(c_i * x_i_coded)."""
    rows = []
    for i, combo in enumerate([(-1, -1, -1), (1, -1, -1), (-1, 1, -1), (1, 1, -1),
                                (-1, -1, 1), (1, -1, 1), (-1, 1, 1), (1, 1, 1)]):
        b1, b2, b3 = combo
        x1 = 1.0 if b1 == 1 else 0.0
        x2 = 1.0 if b2 == 1 else 0.0
        x3 = 1.0 if b3 == 1 else 0.0
        y = intercept + coefficients[0] * b1 + coefficients[1] * b2 + coefficients[2] * b3
        rows.append({"design_run_id": f"D{i+1}", "x1": x1, "x2": x2, "x3": x3, "y": y})
    return rows


class OLSFitTests(unittest.TestCase):
    def test_recovers_main_effects_from_clean_2_3_factorial(self) -> None:
        rows = _two_level_rows((2.0, -1.0, 0.5), intercept=10.0)
        result = analyze_results(_manifest(), rows, seed=0, n_permutations=200, n_bootstrap=100)
        coefficients = {coef["term"]: coef for coef in result["coefficients"]}
        # Main effects in the analyzer are coded ±1; the data above used ±1 in the linear combo, so
        # the recovered estimate equals the coefficient (no halving).
        self.assertAlmostEqual(coefficients["x1"]["estimate"], 2.0, places=4)
        self.assertAlmostEqual(coefficients["x2"]["estimate"], -1.0, places=4)
        self.assertAlmostEqual(coefficients["x3"]["estimate"], 0.5, places=4)
        self.assertAlmostEqual(coefficients["intercept"]["estimate"], 10.0, places=4)

    def test_active_factor_list_excludes_intercept_and_picks_real_signal(self) -> None:
        rows = _two_level_rows((5.0, 0.0, 3.5))
        result = analyze_results(_manifest(), rows, seed=0, n_permutations=1000, n_bootstrap=100)
        active = set(result["active_factor_ids"])
        # With 8 runs the permutation null is discrete; x1 (largest) reliably crosses.
        self.assertIn("x1", active)
        self.assertNotIn("x2", active)

    def test_short_circuits_when_no_factors(self) -> None:
        manifest = _manifest()
        manifest["factors"] = []
        result = analyze_results(manifest, _two_level_rows((1, 1, 1)), seed=0, n_permutations=10, n_bootstrap=10)
        self.assertEqual(result["short_circuit_reason"], "manifest_has_no_factors")

    def test_short_circuits_when_underdetermined(self) -> None:
        manifest = _manifest(model_terms=["main_effects", "two_factor_interactions", "quadratic"])
        rows = _two_level_rows((1.0, 1.0, 1.0))[:3]
        result = analyze_results(manifest, rows, seed=0, n_permutations=10, n_bootstrap=10)
        self.assertTrue(result["short_circuit_reason"].startswith("underdetermined") or
                        result["short_circuit_reason"].startswith("insufficient"))


class DiagnosticsTests(unittest.TestCase):
    def test_r_squared_is_one_for_clean_linear_model(self) -> None:
        rows = _two_level_rows((1.5, 0.7, -0.3))
        result = analyze_results(_manifest(), rows, seed=0, n_permutations=100, n_bootstrap=50)
        self.assertAlmostEqual(result["diagnostics"]["r_squared"], 1.0, places=4)
        self.assertAlmostEqual(result["diagnostics"]["rmse"], 0.0, places=4)

    def test_lack_of_fit_not_available_without_replicates(self) -> None:
        rows = _two_level_rows((1, 1, 1))
        result = analyze_results(_manifest(), rows, seed=0, n_permutations=10, n_bootstrap=10)
        self.assertEqual(result["diagnostics"]["lack_of_fit"]["status"], "NOT_AVAILABLE")

    def test_lack_of_fit_available_with_center_points(self) -> None:
        rows = _two_level_rows((1, 1, 1))
        # Add 3 center-point replicates (all factors at 0.5)
        for i in range(3):
            rows.append({"design_run_id": f"C{i+1}", "x1": 0.5, "x2": 0.5, "x3": 0.5, "y": 1.0 + 0.05 * i})
        result = analyze_results(_manifest(), rows, seed=0, n_permutations=50, n_bootstrap=50)
        lof = result["diagnostics"]["lack_of_fit"]
        self.assertEqual(lof["status"], "AVAILABLE")
        self.assertGreaterEqual(lof["df_pure_error"], 1)


class HalfNormalAndFollowUpSignalTests(unittest.TestCase):
    def test_half_normal_plot_has_one_entry_per_non_intercept(self) -> None:
        rows = _two_level_rows((2.0, -1.0, 0.5))
        result = analyze_results(_manifest(), rows, seed=0, n_permutations=50, n_bootstrap=50)
        self.assertEqual(len(result["half_normal_plot"]), 3)
        for entry in result["half_normal_plot"]:
            self.assertIn("term", entry)
            self.assertIn("abs_effect", entry)
            self.assertIn("half_normal_quantile", entry)

    def test_wave2_signal_carries_per_factor_ascent_signs(self) -> None:
        rows = _two_level_rows((2.0, -1.0, 0.5))
        result = analyze_results(_manifest(), rows, seed=0, n_permutations=200, n_bootstrap=100)
        per_factor = {item["factor_id"]: item for item in result["wave2_signal"]["per_factor"]}
        self.assertEqual(per_factor["x1"]["ascent_sign"], 1)
        self.assertEqual(per_factor["x2"]["ascent_sign"], -1)

    def test_wave2_signal_inverts_sign_for_minimize_direction(self) -> None:
        manifest = _manifest()
        manifest["responses"][0]["direction"] = "minimize"
        rows = _two_level_rows((2.0, -1.0, 0.5))
        result = analyze_results(manifest, rows, seed=0, n_permutations=100, n_bootstrap=100)
        per_factor = {item["factor_id"]: item for item in result["wave2_signal"]["per_factor"]}
        self.assertEqual(per_factor["x1"]["ascent_sign"], -1)


class ModelTermsTests(unittest.TestCase):
    def test_two_factor_interactions_added_when_declared(self) -> None:
        manifest = _manifest(model_terms=["main_effects", "two_factor_interactions"])
        rows = _two_level_rows((1.0, 1.0, 1.0))
        # Add interaction signal: y += 0.3 * x1 * x2 in coded space
        for row in rows:
            x1 = 1.0 if float(row["x1"]) == 1.0 else -1.0
            x2 = 1.0 if float(row["x2"]) == 1.0 else -1.0
            row["y"] = float(row["y"]) + 0.3 * x1 * x2
        result = analyze_results(manifest, rows, seed=0, n_permutations=200, n_bootstrap=100)
        terms = {coef["term"]: coef for coef in result["coefficients"]}
        self.assertIn("x1:x2", terms)
        self.assertAlmostEqual(terms["x1:x2"]["estimate"], 0.3, places=4)


class MarkdownRenderingTests(unittest.TestCase):
    def test_markdown_renders_for_normal_run(self) -> None:
        rows = _two_level_rows((2.0, -1.0, 0.5))
        result = analyze_results(_manifest(), rows, seed=0, n_permutations=100, n_bootstrap=50)
        md = render_analysis_markdown(result)
        self.assertIn("first-batch analysis", md)
        self.assertIn("Coefficients", md)
        self.assertIn("Active factors", md)

    def test_markdown_renders_for_short_circuit(self) -> None:
        manifest = _manifest()
        manifest["factors"] = []
        result = analyze_results(manifest, _two_level_rows((1, 1, 1)), seed=0, n_permutations=10, n_bootstrap=10)
        md = render_analysis_markdown(result)
        self.assertIn("Not run", md)


class CliAnalyzeTests(unittest.TestCase):
    def test_cli_runs_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign = root / "campaign"
            campaign.mkdir()
            manifest = _manifest()
            (campaign / "campaign_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            results = root / "results.csv"
            rows = _two_level_rows((2.0, -1.0, 0.5))
            with results.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["design_run_id", "x1", "x2", "x3", "y"])
                writer.writeheader()
                writer.writerows(rows)
            out = root / "analysis.json"
            md_out = root / "analysis.md"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
            completed = subprocess.run(
                [
                    sys.executable, "-m", "biosymphony_ferm_doe.cli", "analyze",
                    str(campaign), "--results", str(results), "--out", str(out),
                    "--md-out", str(md_out), "--seed", "0",
                    "--permutations", "200", "--bootstrap", "100",
                ],
                cwd=ROOT, env=env, text=True, capture_output=True, check=True,
            )
            summary = json.loads(completed.stdout)
            self.assertEqual(summary["claim_level"], CLAIM_LEVEL)
            self.assertEqual(summary["response_id"], "y")
            payload = json.loads(out.read_text())
            self.assertEqual(len(payload["coefficients"]), 4)  # intercept + 3 mains
            self.assertIn("first-batch analysis", md_out.read_text())


if __name__ == "__main__":
    unittest.main()
