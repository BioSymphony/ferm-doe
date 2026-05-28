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


class EngineSuperpowersPublicTests(unittest.TestCase):
    def test_public_multi_arm_example_compiles_full_dossier_surface(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
        manifest = ROOT / "examples" / "engine-multi-arm-scale-transfer-public" / "campaign_manifest.json"

        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp) / "ferm-doe-dossier"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "biosymphony_ferm_doe.cli",
                    "engine",
                    "compile-dossier",
                    "--manifest",
                    str(manifest),
                    "--out",
                    str(dossier),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                [sys.executable, "-m", "biosymphony_ferm_doe.cli", "engine", "check-dossier", str(dossier)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )

            required = [
                "campaign_arms.json",
                "experimental_setup.json",
                "experimental_setup.md",
                "horizontal_doe.csv",
                "horizontal_doe.json",
                "claim_audit.json",
                "contract_self_check.json",
                "wave_2_decision_rules.json",
            ]
            for rel_path in required:
                self.assertTrue((dossier / rel_path).is_file(), rel_path)

            setup = json.loads((dossier / "experimental_setup.json").read_text(encoding="utf-8"))
            horizontal = json.loads((dossier / "horizontal_doe.json").read_text(encoding="utf-8"))
            arms = json.loads((dossier / "campaign_arms.json").read_text(encoding="utf-8"))
            contract = json.loads((dossier / "contract_self_check.json").read_text(encoding="utf-8"))

        self.assertEqual("planned_experimental_setup_only", setup["claim_boundary"])
        self.assertGreaterEqual(setup["planned_run_count"], 10)
        self.assertEqual("ferm_doe_horizontal_planned_conditions", horizontal["doe_kind"])
        self.assertEqual(horizontal["row_count"], len(horizontal["rows"]))
        self.assertGreaterEqual(horizontal["row_count"], 10)
        self.assertGreaterEqual(len(arms["arms"]), 2)
        self.assertEqual("PASS", contract["status"])


if __name__ == "__main__":
    unittest.main()
