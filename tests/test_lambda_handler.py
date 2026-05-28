from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
LAMBDA_DIR = ROOT / "deploy" / "aws-lambda"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(LAMBDA_DIR))

from handlers.handler import handler  # noqa: E402


def _invoke(action: str, **kwargs) -> dict:
    event = {"action": action, **kwargs}
    return handler(event, context=None)


class DispatchTests(unittest.TestCase):
    def test_unknown_action_returns_400(self) -> None:
        response = _invoke("not-a-real-action")
        self.assertEqual(response["statusCode"], 400)

    def test_recommend_family_returns_200(self) -> None:
        manifest = {
            "factors": [{"factor_id": f"x{i}", "type": "numeric", "low": 0, "high": 1} for i in range(7)],
            "profiles": ["screening"],
        }
        response = _invoke("recommend-family", manifest=manifest)
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["recommended_family"], "plackett_burman")

    def test_validate_inline_manifest_returns_200(self) -> None:
        manifest = {
            "campaign_id": "x",
            "claim_level": "public_synthetic_demo",
            "responses": [{"response_id": "y", "direction": "maximize", "assay_required": True, "objective_lower": 0, "objective_upper": 10}],
            "factors": [{"factor_id": "x1", "type": "numeric", "low": 0, "high": 1}],
            "doe": {"family": "plackett_burman"},
        }
        response = _invoke("validate", manifest=manifest, args={"summary": True})
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertIn("status", body)

    def test_generate_design_returns_design_rows(self) -> None:
        manifest = {
            "campaign_id": "x",
            "claim_level": "public_synthetic_demo",
            "responses": [{"response_id": "y", "direction": "maximize"}],
            "factors": [{"factor_id": f"x{i}", "type": "numeric", "low": 0, "high": 1} for i in range(1, 4)],
            "doe": {"family": "full_factorial", "randomized": False},
        }
        response = _invoke("generate-design", manifest=manifest, args={"seed": 0})
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["family"], "full_factorial")
        self.assertEqual(body["n_runs"], 8)

    def test_goals_returns_null_when_no_bounds(self) -> None:
        manifest = {
            "responses": [{"response_id": "y", "direction": "maximize"}],
            "factors": [{"factor_id": "x1", "type": "numeric", "low": 0, "high": 1}],
        }
        response = _invoke("goals", manifest=manifest)
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertIsNone(body["goals"])
        self.assertEqual(body["reason"], "no_objective_bounds_declarable")

    def test_apigateway_event_shape_is_unwrapped(self) -> None:
        # Simulate API Gateway POST with body as a string
        event = {
            "httpMethod": "POST",
            "path": "/v1/recommend-family",
            "body": json.dumps({
                "action": "recommend-family",
                "manifest": {
                    "factors": [{"factor_id": "x1", "type": "numeric", "low": 0, "high": 1}],
                    "profiles": ["screening"],
                },
            }),
        }
        response = handler(event, context=None)
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertIsNotNone(body.get("recommended_family"))


if __name__ == "__main__":
    unittest.main()
