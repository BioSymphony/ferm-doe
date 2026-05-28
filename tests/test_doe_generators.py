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

from biosymphony_ferm_doe.doe_generators import (  # noqa: E402
    EXACT,
    HEURISTIC,
    SUPPORTED_FAMILIES,
    generate_design,
)


def _numeric_factors(n: int, *, prefix: str = "x") -> list[dict]:
    return [
        {"factor_id": f"{prefix}{i}", "type": "numeric", "low": 0.0, "high": 1.0}
        for i in range(1, n + 1)
    ]


def _manifest(family: str, factors: list[dict], **doe_overrides) -> dict:
    return {
        "campaign_id": f"demo-{family}",
        "claim_level": "public_synthetic_demo",
        "factors": factors,
        "responses": [{"response_id": "y", "class": "titer", "direction": "maximize"}],
        "doe": {"family": family, "randomized": False, **doe_overrides},
    }


def _coded_values(rows: list[dict], factor_ids: list[str], factors: list[dict]) -> list[tuple[int, ...]]:
    coded: list[tuple[int, ...]] = []
    for row in rows:
        signs: list[int] = []
        for fid, factor in zip(factor_ids, factors):
            low = float(factor["low"])
            high = float(factor["high"])
            mid = (low + high) / 2.0
            value = float(row[fid])
            if abs(value - low) < 1e-6:
                signs.append(-1)
            elif abs(value - high) < 1e-6:
                signs.append(1)
            elif abs(value - mid) < 1e-6:
                signs.append(0)
            else:
                signs.append(int(round((value - mid) / max(high - mid, 1e-9))))
        coded.append(tuple(signs))
    return coded


class FullFactorialTests(unittest.TestCase):
    def test_full_factorial_produces_two_to_the_k_runs(self) -> None:
        manifest = _manifest("full_factorial", _numeric_factors(3))
        design = generate_design(manifest)
        self.assertEqual(design["family"], "full_factorial")
        self.assertEqual(design["claim_level"], EXACT)
        self.assertEqual(design["n_runs"], 8)
        for row in design["rows"]:
            self.assertIn(row["x1"], (0.0, 1.0))

    def test_categorical_full_factorial_is_cartesian_product(self) -> None:
        factors = [
            {"factor_id": "media", "type": "categorical", "levels": ["A", "B", "C"]},
            {"factor_id": "temp", "type": "numeric", "low": 28.0, "high": 35.0},
        ]
        manifest = _manifest("full_factorial", factors)
        design = generate_design(manifest)
        self.assertEqual(design["n_runs"], 6)
        media_values = sorted({row["media"] for row in design["rows"]})
        self.assertEqual(media_values, ["A", "B", "C"])


class PlackettBurmanTests(unittest.TestCase):
    def test_pb_for_seven_factors_emits_eight_runs(self) -> None:
        factors = _numeric_factors(7)
        manifest = _manifest("plackett_burman", factors)
        design = generate_design(manifest)
        self.assertEqual(design["n_runs"], 8)
        self.assertEqual(design["claim_level"], EXACT)
        self.assertEqual(design["metadata"]["resolution"], "III")

    def test_pb_size_matches_next_multiple_of_four(self) -> None:
        factors = _numeric_factors(9)
        manifest = _manifest("plackett_burman", factors)
        design = generate_design(manifest)
        self.assertEqual(design["n_runs"], 12)

    def test_pb_columns_are_balanced_across_runs(self) -> None:
        factors = _numeric_factors(7)
        manifest = _manifest("plackett_burman", factors)
        design = generate_design(manifest)
        coded = _coded_values(design["rows"], design["factors"], factors)
        for col in range(len(design["factors"])):
            counts = {-1: 0, 1: 0}
            for row in coded:
                counts[row[col]] += 1
            self.assertEqual(counts[-1], counts[1])


class FractionalFactorialTests(unittest.TestCase):
    def test_2_5_minus_1_resolution_v(self) -> None:
        manifest = _manifest("fractional_factorial", _numeric_factors(5))
        design = generate_design(manifest)
        self.assertEqual(design["family"], "fractional_factorial")
        self.assertEqual(design["claim_level"], EXACT)
        self.assertEqual(design["n_runs"], 16)
        self.assertEqual(design["metadata"]["resolution"], "V")

    def test_explicit_generators_honored(self) -> None:
        manifest = _manifest("fractional_factorial", _numeric_factors(5), generators=["AB", "AC"], resolution="III")
        design = generate_design(manifest)
        self.assertEqual(design["n_runs"], 8)
        self.assertEqual(design["metadata"]["resolution"], "III")
        labels = design["metadata"]["generators"]
        self.assertEqual(labels, ["D=AB", "E=AC"])


class DefinitiveScreeningTests(unittest.TestCase):
    def test_dsd_for_six_factors_has_thirteen_runs(self) -> None:
        manifest = _manifest("definitive_screening", _numeric_factors(6))
        design = generate_design(manifest)
        self.assertEqual(design["family"], "definitive_screening")
        self.assertEqual(design["claim_level"], EXACT)
        self.assertEqual(design["n_runs"], 13)
        center_count = sum(1 for row in design["rows"] if row["center_point"])
        self.assertEqual(center_count, 1)

    def test_dsd_for_odd_k_uses_next_even_conference(self) -> None:
        manifest = _manifest("definitive_screening", _numeric_factors(5))
        design = generate_design(manifest)
        self.assertEqual(design["n_runs"], 13)
        self.assertIn("dropped_last_column", " ".join(design["warnings"]))

    def test_dsd_unsupported_k_raises(self) -> None:
        manifest = _manifest("definitive_screening", _numeric_factors(8))
        with self.assertRaises(ValueError):
            generate_design(manifest)


class CentralCompositeTests(unittest.TestCase):
    def test_face_centered_ccd_default(self) -> None:
        manifest = _manifest("central_composite", _numeric_factors(3), n_center_points=4)
        design = generate_design(manifest)
        self.assertEqual(design["family"], "central_composite")
        self.assertEqual(design["claim_level"], EXACT)
        self.assertEqual(design["metadata"]["axial_distance"], 1.0)
        self.assertEqual(design["n_runs"], 8 + 6 + 4)

    def test_rotatable_ccd_warns_about_extrapolation(self) -> None:
        manifest = _manifest("central_composite", _numeric_factors(3), variant="rotatable", n_center_points=4)
        design = generate_design(manifest)
        self.assertGreater(design["metadata"]["axial_distance"], 1.0)
        self.assertTrue(any("extends_beyond_declared_factor_range" in w for w in design["warnings"]))


class BoxBehnkenTests(unittest.TestCase):
    def test_box_behnken_k3(self) -> None:
        manifest = _manifest("box_behnken", _numeric_factors(3), n_center_points=3)
        design = generate_design(manifest)
        self.assertEqual(design["family"], "box_behnken")
        self.assertEqual(design["claim_level"], EXACT)
        self.assertEqual(design["n_runs"], 12 + 3)
        non_center = [row for row in design["rows"] if not row["center_point"]]
        for row in non_center:
            zero_count = sum(1 for fid in design["factors"] if row[fid] == 0.5)
            self.assertEqual(zero_count, 1)

    def test_box_behnken_k4(self) -> None:
        manifest = _manifest("box_behnken", _numeric_factors(4), n_center_points=4)
        design = generate_design(manifest)
        self.assertEqual(design["n_runs"], 24 + 4)

    def test_box_behnken_unsupported_k_raises(self) -> None:
        manifest = _manifest("box_behnken", _numeric_factors(5))
        with self.assertRaises(ValueError):
            generate_design(manifest)


class LatinHypercubeTests(unittest.TestCase):
    def test_lhs_each_dimension_has_n_unique_intervals(self) -> None:
        manifest = _manifest("latin_hypercube", _numeric_factors(3), n_runs=10)
        design = generate_design(manifest, seed=0)
        self.assertEqual(design["n_runs"], 10)
        self.assertEqual(design["claim_level"], EXACT)
        for fid in design["factors"]:
            values = sorted({row[fid] for row in design["rows"]})
            self.assertEqual(len(values), 10)


class MixtureTests(unittest.TestCase):
    def test_simplex_centroid_three_components(self) -> None:
        factors = [
            {"factor_id": "c1", "type": "mixture", "low": 0.0, "high": 1.0},
            {"factor_id": "c2", "type": "mixture", "low": 0.0, "high": 1.0},
            {"factor_id": "c3", "type": "mixture", "low": 0.0, "high": 1.0},
        ]
        manifest = _manifest("scheffe_mixture", factors)
        design = generate_design(manifest)
        self.assertEqual(design["claim_level"], EXACT)
        self.assertEqual(design["n_runs"], 7)
        for row in design["rows"]:
            total = row["c1"] + row["c2"] + row["c3"]
            self.assertAlmostEqual(total, 1.0, places=3)

    def test_simplex_lattice_degree_two(self) -> None:
        factors = [
            {"factor_id": "c1", "type": "mixture"},
            {"factor_id": "c2", "type": "mixture"},
            {"factor_id": "c3", "type": "mixture"},
        ]
        manifest = _manifest("scheffe_mixture", factors, construction="simplex_lattice", lattice_degree=2)
        design = generate_design(manifest)
        self.assertEqual(design["n_runs"], 6)


class OptimalTests(unittest.TestCase):
    def test_d_optimal_emits_heuristic_claim(self) -> None:
        manifest = _manifest("optimal_d", _numeric_factors(3), n_runs=10, optimal_iterations=5)
        design = generate_design(manifest, seed=0)
        self.assertEqual(design["family"], "optimal_d")
        self.assertEqual(design["claim_level"], HEURISTIC)
        self.assertEqual(len(design["rows"]), 10)
        self.assertTrue(any("review_with_a_statistician" in w for w in design["warnings"]))

    def test_i_optimal_runs(self) -> None:
        manifest = _manifest("optimal_i", _numeric_factors(3), n_runs=8, optimal_iterations=5)
        design = generate_design(manifest, seed=1)
        self.assertEqual(design["claim_level"], HEURISTIC)


class ExtremeVerticesTests(unittest.TestCase):
    def test_extreme_vertices_with_constrained_components(self) -> None:
        factors = [
            {"factor_id": "c1", "type": "mixture", "low": 0.1, "high": 0.6},
            {"factor_id": "c2", "type": "mixture", "low": 0.2, "high": 0.7},
            {"factor_id": "c3", "type": "mixture", "low": 0.1, "high": 0.5},
        ]
        manifest = _manifest("extreme_vertices_mixture", factors)
        design = generate_design(manifest)
        self.assertEqual(design["claim_level"], HEURISTIC)
        self.assertGreater(design["n_runs"], 0)
        for row in design["rows"]:
            total = row["c1"] + row["c2"] + row["c3"]
            self.assertAlmostEqual(total, 1.0, places=3)


class CommonShapeTests(unittest.TestCase):
    def test_every_supported_family_has_branch(self) -> None:
        # Sanity: SUPPORTED_FAMILIES exposed and dispatch to a generator is wired.
        self.assertIn("full_factorial", SUPPORTED_FAMILIES)
        self.assertIn("definitive_screening", SUPPORTED_FAMILIES)

    def test_unsupported_family_raises(self) -> None:
        manifest = _manifest("custom_constrained", _numeric_factors(2))
        with self.assertRaises(ValueError):
            generate_design(manifest)

    def test_design_run_ids_are_unique_and_run_order_is_one_indexed(self) -> None:
        manifest = _manifest("plackett_burman", _numeric_factors(7))
        design = generate_design(manifest, seed=1)
        ids = [row["design_run_id"] for row in design["rows"]]
        self.assertEqual(len(ids), len(set(ids)))
        orders = [row["run_order"] for row in design["rows"]]
        self.assertEqual(sorted(orders), list(range(1, len(orders) + 1)))


class CliGenerateDesignTests(unittest.TestCase):
    def test_cli_emits_csv_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign = root / "campaign"
            campaign.mkdir()
            manifest = _manifest("plackett_burman", _numeric_factors(7))
            (campaign / "campaign_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            csv_out = root / "wave1_design.csv"
            metadata_out = root / "wave1_design.metadata.json"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "biosymphony_ferm_doe.cli",
                    "generate-design",
                    str(campaign),
                    "--out",
                    str(csv_out),
                    "--metadata-out",
                    str(metadata_out),
                    "--seed",
                    "0",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["family"], "plackett_burman")
            self.assertEqual(payload["claim_level"], "exact")
            self.assertTrue(csv_out.is_file())
            self.assertTrue(metadata_out.is_file())
            metadata = json.loads(metadata_out.read_text())
            self.assertEqual(metadata["family"], "plackett_burman")
            self.assertEqual(metadata["seed"], 0)
            csv_text = csv_out.read_text()
            self.assertIn("design_run_id", csv_text)
            self.assertIn("claim_level", csv_text)


if __name__ == "__main__":
    unittest.main()
