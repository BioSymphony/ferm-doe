from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "skills" / "biosymphony-ferm-doe" / "scripts" / "preflight_check.py"


def _run_preflight(path: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, str(PREFLIGHT), str(path)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


class PreflightCheckTests(unittest.TestCase):
    def test_private_manifest_public_demo_task_request_and_sidecar_pass(self) -> None:
        targets = [
            ROOT / "examples" / "xylanase-wxz1-2012" / "campaign_manifest.json",
            ROOT / "examples" / "demo-xylanase-public",
            ROOT / "examples" / "demo-xylanase-public" / "campaign_manifest.json",
            ROOT / "templates" / "task_request.template.json",
            ROOT / "templates" / "sidecar-campaign-goal.json",
        ]
        for target in targets:
            with self.subTest(target=target.relative_to(ROOT)):
                result = _run_preflight(target)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("OK:", result.stdout)

    def test_all_example_manifests_pass_current_lightweight_preflight(self) -> None:
        targets = sorted(
            path
            for pattern in ("campaign_manifest.json", "phase2_manifest.json", "phase3_manifest.json")
            for path in (ROOT / "examples").rglob(pattern)
        )
        self.assertTrue(targets)
        for target in targets:
            with self.subTest(target=target.relative_to(ROOT)):
                result = _run_preflight(target)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_bad_public_task_request_fails(self) -> None:
        request = json.loads((ROOT / "templates" / "task_request.template.json").read_text(encoding="utf-8"))
        request["inputs"][0]["path"] = "/" + "Users/example/private/campaign_manifest.json"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "task_request.json"
            path.write_text(json.dumps(request), encoding="utf-8")
            result = _run_preflight(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("task_request-text-public-safe", result.stderr)


if __name__ == "__main__":
    unittest.main()
