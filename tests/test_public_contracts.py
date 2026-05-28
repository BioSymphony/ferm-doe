from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.cli import main as cli_main  # noqa: E402
from biosymphony_ferm_doe.contracts import (  # noqa: E402
    check_dossier_contract,
    load_public_task_request,
    validate_public_task_request,
)


class PublicTaskRequestContractTests(unittest.TestCase):
    def test_template_public_task_request_passes(self) -> None:
        request = load_public_task_request(ROOT / "templates" / "task_request.template.json")
        result = validate_public_task_request(request)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["error_count"], 0)

    def test_private_path_fails_public_task_request(self) -> None:
        request = load_public_task_request(ROOT / "templates" / "task_request.template.json")
        request["inputs"][0]["path"] = "/" + "Users/example/private/campaign_manifest.json"
        result = validate_public_task_request(request)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("task_request-input-1", result["failed_check_ids"])
        self.assertIn("task_request-text-public-safe", result["failed_check_ids"])

    def test_provider_mutation_command_fails_public_task_request(self) -> None:
        request = load_public_task_request(ROOT / "templates" / "task_request.template.json")
        request["validation_commands"] = ["providerctl create-pod demo"]
        result = validate_public_task_request(request)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("task_request-validation-commands-public-safe", result["failed_check_ids"])


class PublicDossierContractTests(unittest.TestCase):
    def test_xylanase_public_demo_contract_passes(self) -> None:
        result = check_dossier_contract(ROOT / "examples" / "demo-xylanase-public")
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["error_count"], 0)

    def test_overclaim_in_public_run_packet_fails(self) -> None:
        source = ROOT / "examples" / "demo-xylanase-public"
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "campaign"
            shutil.copytree(source, target)
            run_packet = target / "expected" / "run_packet.md"
            run_packet.write_text(run_packet.read_text(encoding="utf-8") + "\nThis is approved for execution.\n", encoding="utf-8")
            result = check_dossier_contract(target)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("unsupported claim language" in error for error in result["errors"]))

    def test_cli_public_contract_commands(self) -> None:
        commands = [
            ["validate-task-request", "templates/task_request.template.json"],
            ["check-dossier", "examples/demo-xylanase-public"],
            ["validate", "examples/demo-xylanase-public", "--summary"],
        ]
        for command in commands:
            with self.subTest(command=command[0]):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    code = cli_main(command)
                self.assertEqual(code, 0)
                payload = json.loads(stdout.getvalue())
                self.assertIn(payload["status"], {"PASS", "GREEN", "YELLOW"})


if __name__ == "__main__":
    unittest.main()
