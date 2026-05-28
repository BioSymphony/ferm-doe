from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, check=True)


class ScaleBridgeDemoTests(unittest.TestCase):
    def test_validates_yellow_clean(self) -> None:
        result = _run([sys.executable, "-m", "biosymphony_ferm_doe.cli", "validate", "examples/demo-scale-bridge-public"])
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "YELLOW")
        self.assertEqual(payload["error_count"], 0)
        self.assertEqual(payload["warning_count"], 0)
        self.assertIn("scale_down_qualification", payload["profiles"])

    def test_summary_shape(self) -> None:
        result = _run([sys.executable, "-m", "biosymphony_ferm_doe.cli", "validate", "examples/demo-scale-bridge-public", "--summary"])
        payload = json.loads(result.stdout)
        for key in ("campaign_id", "status", "claim_level", "profiles", "error_count", "warning_count", "worst_axis", "failed_check_ids"):
            self.assertIn(key, payload)


class SplitPlotDemoTests(unittest.TestCase):
    def test_validates_yellow_clean(self) -> None:
        result = _run([sys.executable, "-m", "biosymphony_ferm_doe.cli", "validate", "examples/demo-split-plot-fedbatch-public"])
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "YELLOW")
        self.assertEqual(payload["error_count"], 0)
        self.assertEqual(payload["warning_count"], 0)
        self.assertIn("split_plot_fed_batch", payload["profiles"])


class DiagnosticWalkthroughTests(unittest.TestCase):
    def test_surfaces_warnings(self) -> None:
        result = _run([sys.executable, "-m", "biosymphony_ferm_doe.cli", "validate", "examples/demo-warnings-walkthrough-public", "--summary"])
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "YELLOW")
        self.assertEqual(payload["error_count"], 0)
        self.assertGreater(payload["warning_count"], 0, "diagnostic demo must surface at least one warning")
        failed_ids = set(payload["failed_check_ids"])
        for expected in (
            "input-advised-equipment_inventory",
            "profile-advised-block-decision_rules",
            "profile-advised-block-stop_rules",
            "assay-contract-incomplete_titer",
            "factor-mixture-media_blend",
            "doe-min-runs",
        ):
            self.assertIn(expected, failed_ids, f"expected diagnostic warning '{expected}' missing from failed_check_ids")


class JsonSchemaPresenceTests(unittest.TestCase):
    def test_schema_file_exists(self) -> None:
        path = ROOT / "schemas" / "campaign_manifest.schema.json"
        self.assertTrue(path.is_file())

    def test_schema_is_valid_json(self) -> None:
        payload = json.loads((ROOT / "schemas" / "campaign_manifest.schema.json").read_text())
        self.assertEqual(payload.get("$schema"), "https://json-schema.org/draft/2020-12/schema")
        self.assertIn("properties", payload)
        for slot in ("scale_context", "arms", "doe", "adaptive_wave2", "decision_rules", "stop_rules", "risk_register", "assumptions", "readiness", "waves", "profiles"):
            self.assertIn(slot, payload["properties"], slot)
        self.assertIn("assay_power_policy", payload["$defs"])


class ProfileRegistryTests(unittest.TestCase):
    def test_profiles_module_imports(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from biosymphony_ferm_doe.profiles import PROFILE_REGISTRY, resolve_profiles
            self.assertIn("scale_down_qualification", PROFILE_REGISTRY)
            self.assertIn("split_plot_fed_batch", PROFILE_REGISTRY)
            self.assertIn("scale_up_bridge", PROFILE_REGISTRY)
            self.assertEqual(resolve_profiles(None), ["custom"])
            self.assertEqual(resolve_profiles(["screening"]), ["screening"])
            self.assertEqual(resolve_profiles(["bogus_profile"]), ["custom"])
        finally:
            sys.path.remove(str(SRC))


class DoeFamilyTests(unittest.TestCase):
    def test_family_registry_has_expected_families(self) -> None:
        sys.path.insert(0, str(SRC))
        try:
            from biosymphony_ferm_doe.doe_families import FAMILY_REGISTRY, minimum_runs
            for fam in ("definitive_screening", "plackett_burman", "fractional_factorial", "full_factorial", "central_composite", "box_behnken", "split_plot", "scheffe_mixture", "custom_constrained", "sequential_augmentation"):
                self.assertIn(fam, FAMILY_REGISTRY)
            self.assertEqual(minimum_runs("definitive_screening", 5), 11)
            self.assertEqual(minimum_runs("full_factorial", 3), 8)
            self.assertEqual(minimum_runs("box_behnken", 3, n_center=3), 2 * 3 * 2 + 3)
        finally:
            sys.path.remove(str(SRC))


class AuditSkipMarkerTests(unittest.TestCase):
    def test_audit_skip_marker_suppresses_match(self) -> None:
        sample = ROOT / "tests" / "_audit_skip_fixture.txt"
        try:
            sample.write_text(
                "api_key=PLACEHOLDER_NEVER_COMMIT  # audit-skip: assigned_secret_like_value documentation example\n"
            )
            result = _run([sys.executable, "-m", "biosymphony_ferm_doe.cli", "audit", str(ROOT)])
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["issue_count"], 0)
        finally:
            if sample.exists():
                sample.unlink()


if __name__ == "__main__":
    unittest.main()
