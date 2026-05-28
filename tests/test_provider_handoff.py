from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.provider_handoff import prepare_provider_handoff  # noqa: E402
from biosymphony_ferm_doe.public_release import scan_text  # noqa: E402


class ProviderHandoffTests(unittest.TestCase):
    def test_handoff_uses_portable_paths_and_generic_provider_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bundle_path = tmp_path / "launch_bundle.json"
            manifest_path = tmp_path / "launch_manifest.json"
            out_dir = tmp_path / "handoff"
            bundle_path.write_text(
                json.dumps(
                    {
                        "run_id": "public-demo",
                        "expected_outputs": ["remote-execution/artifacts/summary.json"],
                    }
                )
                + "\n"
            )
            manifest_path.write_text(
                json.dumps(
                    {
                        "run_id": "public-demo",
                        "remote_launch_allowed": True,
                        "provider": {
                            "name": "example-provider",
                            "resource_name_prefix": "public-demo-resource",
                            "ports": ["9001/tcp"],
                        },
                        "budget": {"max_estimated_cost_usd": 2},
                    }
                )
                + "\n"
            )

            old_cwd = Path.cwd()
            try:
                os.chdir(tmp_path)
                handoff = prepare_provider_handoff(
                    Path("launch_bundle.json"),
                    Path("handoff"),
                    launch_manifest_path=Path("launch_manifest.json"),
                    provider_bridge="provider-bridge",
                    tracker_issue="TASK-001",
                )
            finally:
                os.chdir(old_cwd)

        text = json.dumps(handoff, sort_keys=True)
        self.assertEqual(handoff["files"]["launch_manifest"], "launch_manifest.json")
        self.assertEqual(handoff["source_contracts"]["launch_bundle"]["path"], "launch_bundle.json")
        self.assertEqual(handoff["provider"], "example-provider")
        self.assertIn("create-resource launch_manifest.json", text)
        self.assertIn(".runtime/provider/public-demo", text)
        self.assertIn("$RESOURCE_ID", text)
        self.assertNotIn(str(tmp_path), text)
        self.assertNotIn("/Users/", text)
        self.assertEqual([], scan_text(text, "provider_handoff.json"))


if __name__ == "__main__":
    unittest.main()
