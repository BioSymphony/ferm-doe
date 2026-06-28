from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.engine_cli import main as engine_main
from biosymphony_ferm_doe.task_router import classify_task_request, route_task_request, schema_path, validate_task_request


def valid_request(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": 1,
        "request_kind": "ferm_doe_task_request",
        "request_id": "tr-demo-readiness",
        "title": "Wave 0 readiness check for public synthetic campaign",
        "summary": "Score readiness, assay risk, equipment capacity, and stop/go gates before Wave 1.",
        "data_classification": "synthetic",
        "campaign": {
            "campaign_id": "demo-xylanase-public",
            "objective": "Prepare a public-safe planning packet from synthetic demo inputs.",
            "organism_or_host": "synthetic host",
            "product_or_response": "enzyme activity",
            "current_format": "shake flask",
            "target_format": "screening plate",
        },
        "task": {
            "intent": "readiness_audit",
            "priority": "high",
            "requested_outputs": ["readiness_summary.json", "readiness_verdict.md"],
        },
        "inputs": [
            {
                "kind": "campaign_manifest",
                "path": "examples/demo-xylanase-public/campaign_manifest.json",
                "required": True,
                "data_classification": "synthetic",
            }
        ],
        "routing": {
            "preferred_lane": "codex",
            "activate_first_wave_only": True,
            "remote_compute_allowed": False,
        },
        "safety": {
            "contains_secrets": False,
            "contains_private_process_data": False,
            "private_data_handling": "not_applicable",
        },
    }
    data.update(overrides)
    return data


class TaskRouterTests(unittest.TestCase):
    def test_engine_schema_file_is_valid_json(self) -> None:
        schema = json.loads(schema_path().read_text())
        self.assertEqual(schema["title"], "BioSymphony Ferm DoE Engine Task Request")
        self.assertIn("task_intent", schema["$defs"])

    def test_template_routes_to_readiness_wave0(self) -> None:
        request = json.loads((ROOT / "templates" / "engine_task_request.template.json").read_text())
        self.assertEqual(validate_task_request(request), [])
        route = route_task_request(request)
        self.assertEqual(route["status"], "OK")
        self.assertEqual(route["classification"]["task_class"], "readiness_audit")
        self.assertEqual(route["routing"]["recommended_issue_pack"], "fermentation-readiness-v0")
        self.assertEqual(route["routing"]["recommended_lane"], "codex")
        self.assertEqual(route["routing"]["active_wave"], "wave0")
        self.assertFalse(route["routing"]["requires_remote_compute"])

    def test_keyword_classification_when_intent_unknown(self) -> None:
        request = valid_request(
            task={
                "intent": "unknown",
                "requested_outputs": ["evidence_table.csv", "source_ledger.md"],
                "notes": "Use public literature and vendor protocol sources, then write a normalized evidence table.",
            }
        )
        classification = classify_task_request(request)
        self.assertEqual(classification["task_class"], "evidence_execution")
        route = route_task_request(request)
        self.assertEqual(route["routing"]["recommended_issue_pack"], "evidence-executor-v0")
        self.assertTrue(route["routing"]["requires_evidence_executor"])

    def test_private_and_secret_safety_errors_block_route(self) -> None:
        request = valid_request(
            safety={
                "contains_secrets": True,
                "contains_private_process_data": True,
                "private_data_handling": "not_applicable",
            },
        )
        errors = validate_task_request(request)
        self.assertIn("safety.contains_secrets must be false for repository-stored task requests", errors)
        self.assertIn("safety.private_data_handling must describe sensitive process-data handling", errors)
        route = route_task_request(request)
        self.assertEqual(route["status"], "FAIL")
        self.assertEqual(route["safety_status"], "BLOCKED")

    def test_external_compute_route_requires_explicit_remote_permission(self) -> None:
        request = valid_request(
            task={
                "intent": "compute_handoff",
                "requested_outputs": ["provider_handoff.json"],
            },
            routing={
                "preferred_lane": "runpod",
                "activate_first_wave_only": True,
                "remote_compute_allowed": False,
            },
        )
        route = route_task_request(request)
        self.assertEqual(route["classification"]["task_class"], "compute_handoff")
        self.assertEqual(route["status"], "FAIL")
        self.assertIn("routing.remote_compute_allowed must be true for external compute handoff routes", route["errors"])

    def test_engine_cli_routes_task_request_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            request_path = Path(tmp) / "task_request.json"
            out_path = Path(tmp) / "route.json"
            request_path.write_text(json.dumps(valid_request(), indent=2) + "\n")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = engine_main(["route-task-request", str(request_path), "--out", str(out_path)])
            self.assertEqual(code, 0)
            summary = json.loads(stdout.getvalue())
            self.assertEqual(summary["status"], "OK")
            self.assertEqual(summary["task_class"], "readiness_audit")
            route = json.loads(out_path.read_text())
            self.assertEqual(route["routing"]["recommended_issue_pack"], "fermentation-readiness-v0")


if __name__ == "__main__":
    unittest.main()
