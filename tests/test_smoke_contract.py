from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from _contract_emitter import emit_contract  # noqa: E402
from validate_smoke_artifacts import main as validate_smoke_artifacts  # noqa: E402


def _manifest() -> dict:
    return {
        "factors": [
            {"factor_id": "x", "type": "continuous", "min": 0.0, "max": 1.0},
        ],
        "responses": [{"response_id": "y", "direction": "maximize"}],
        "constraints": [
            {
                "constraint_id": "x_le_one",
                "type": "linear",
                "coefficients": {"x": 1.0},
                "operator": "<=",
                "rhs": 1.0,
            }
        ],
    }


def _negative_control() -> dict:
    return {
        "scenario": "infeasible_constraints",
        "expected_behavior": "fail_closed_with_route_report",
        "observed_behavior": "not exercised in unit test",
        "passed": True,
    }


def test_emit_contract_demotes_pass_when_candidate_violates_constraints(tmp_path: Path) -> None:
    emit_contract(
        out_dir=tmp_path,
        backend="demo",
        scenario_id="semantic-guard",
        manifest=_manifest(),
        candidates=[{"run_id": "bad-001", "x": 2.0}],
        route_selected="primary",
        route_reason="unit test",
        constraints_honored_natively=True,
        package_versions={"python": "test"},
        closed_loop_rounds=[],
        n1_pass=True,
        n16_pass=True,
        negative_control=_negative_control(),
        fallback=None,
        status="PASS",
    )

    result = json.loads((tmp_path / "result.json").read_text())
    fallback = json.loads((tmp_path / "fallback_report.json").read_text())
    constraint_check = json.loads((tmp_path / "constraint_check.json").read_text())

    assert result["status"] == "FAIL_CLOSED"
    assert result["summary"]["constraints_honored_natively"] is False
    assert fallback["triggered"] is True
    assert fallback["phase"] == "constraint_solve"
    assert constraint_check["any_violation"] is True


def test_validator_rejects_pass_with_constraint_violations(tmp_path: Path) -> None:
    emit_contract(
        out_dir=tmp_path,
        backend="demo",
        scenario_id="semantic-guard",
        manifest=_manifest(),
        candidates=[{"run_id": "bad-001", "x": 2.0}],
        route_selected="primary",
        route_reason="unit test",
        constraints_honored_natively=True,
        package_versions={"python": "test"},
        closed_loop_rounds=[],
        n1_pass=True,
        n16_pass=True,
        negative_control=_negative_control(),
        fallback=None,
        status="PASS",
    )

    result_path = tmp_path / "result.json"
    result = json.loads(result_path.read_text())
    result["status"] = "PASS"
    result["summary"]["constraints_honored_natively"] = True
    result_path.write_text(json.dumps(result, indent=2) + "\n")

    fallback_path = tmp_path / "fallback_report.json"
    fallback_path.write_text(
        json.dumps(
            {
                "triggered": False,
                "phase": None,
                "reason": None,
                "fallback_path_taken": None,
            },
            indent=2,
        )
        + "\n"
    )

    assert validate_smoke_artifacts([str(tmp_path)]) == 1


def test_validator_rejects_unknown_route_selection(tmp_path: Path) -> None:
    emit_contract(
        out_dir=tmp_path,
        backend="demo",
        scenario_id="semantic-guard",
        manifest=_manifest(),
        candidates=[{"run_id": "ok-001", "x": 0.5}],
        route_selected="primary",
        route_reason="unit test",
        constraints_honored_natively=True,
        package_versions={"python": "test"},
        closed_loop_rounds=[],
        n1_pass=True,
        n16_pass=True,
        negative_control=_negative_control(),
        fallback=None,
        status="PASS",
    )

    route_path = tmp_path / "route_report.json"
    route = json.loads(route_path.read_text())
    route["selected"] = "mystery"
    route_path.write_text(json.dumps(route, indent=2) + "\n")

    assert validate_smoke_artifacts([str(tmp_path)]) == 1
