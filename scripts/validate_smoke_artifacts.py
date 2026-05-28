#!/usr/bin/env python3
"""Validate a backend smoke-test output directory against the 10-artifact contract.

Usage:
    python3 scripts/validate_smoke_artifacts.py <smoke-out-dir> [--strict]

Returns exit code 0 if all required artifacts exist and pass minimum shape checks,
non-zero otherwise. Used by post-smoke wrappers and public backend-evaluation
summary reports.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

CONTRACT_PATH = Path(__file__).parent.parent / "docs" / "schemas" / "smoke-artifact-contract.json"
VALID_STATUSES = {"PASS", "FAIL", "FAIL_CLOSED", "DEFERRED"}
VALID_ROUTE_SELECTIONS = {"primary", "fallback", "demoted", "skipped", "halted"}

REQUIRED = [
    "result.json",
    "route_report.json",
    "candidate_table.csv",
    "constraint_check.json",
    "fallback_report.json",
    "closed_loop_replay.json",
    "negative_control_report.json",
    "artifact_hashes.json",
    "license_note.md",
    "planning_boundary.md",
]


def check_artifact(path: Path, status: str | None = None) -> tuple[bool, str]:
    """Validate one artifact. `status` from result.json - when FAIL_CLOSED, empty
    candidate_table.csv data rows are acceptable (correct fail-closed behavior)."""
    if not path.exists():
        return False, "missing"
    if path.stat().st_size == 0:
        return False, "empty"
    if path.suffix == ".json":
        try:
            json.loads(path.read_text())
        except json.JSONDecodeError as e:
            return False, f"invalid json: {e}"
    elif path.suffix == ".csv":
        rows = list(csv.reader(path.read_text().splitlines()))
        if not rows:
            return False, "empty csv"
        if "run_id" not in rows[0]:
            return False, "missing run_id column"
        if len(rows) < 2:
            if status == "FAIL_CLOSED":
                return True, "ok (no data rows - fail-closed)"
            if status == "DEFERRED":
                return True, "ok (no data rows - deferred to RunPod per durable safety rule)"
            return False, "no data rows"
    elif path.suffix == ".md":
        lines = [l for l in path.read_text().splitlines() if l.strip()]
        if len(lines) < 3:
            return False, f"only {len(lines)} non-blank lines (need >=3)"
    return True, "ok"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--strict", action="store_true", help="Also verify artifact_hashes.json matches actual file hashes")
    args = parser.parse_args(argv)

    # First read result.json to determine fail-closed status (affects candidate_table.csv validation)
    status = None
    result_path = args.out_dir / "result.json"
    if result_path.exists():
        try:
            status = json.loads(result_path.read_text()).get("status")
        except json.JSONDecodeError:
            pass

    results = []
    for name in REQUIRED:
        ok, msg = check_artifact(args.out_dir / name, status=status)
        results.append((name, ok, msg))

    all_pass = all(ok for _, ok, _ in results)

    try:
        result_json = read_json(args.out_dir / "result.json")
        route_report = read_json(args.out_dir / "route_report.json")
        constraint_check = read_json(args.out_dir / "constraint_check.json")
        fallback_report = read_json(args.out_dir / "fallback_report.json")
        negative_control = read_json(args.out_dir / "negative_control_report.json")
    except (json.JSONDecodeError, OSError) as e:
        results.append(("semantic:json", False, f"could not load semantic checks: {e}"))
        all_pass = False
    else:
        result_status = result_json.get("status")
        route_selected = route_report.get("selected")
        any_violation = bool(constraint_check.get("any_violation"))
        native_constraints = bool(
            (result_json.get("summary") or {}).get("constraints_honored_natively")
        )

        if result_status not in VALID_STATUSES:
            results.append(("semantic:status", False, f"unknown status {result_status!r}"))
            all_pass = False
        else:
            results.append(("semantic:status", True, "ok"))

        if route_selected not in VALID_ROUTE_SELECTIONS:
            results.append(("semantic:route", False, f"unknown route selection {route_selected!r}"))
            all_pass = False
        else:
            results.append(("semantic:route", True, "ok"))

        if result_status == "PASS" and any_violation:
            results.append(
                (
                    "semantic:constraints",
                    False,
                    "PASS result cannot contain constraint_check.any_violation=true",
                )
            )
            all_pass = False
        else:
            results.append(("semantic:constraints", True, "ok"))

        if native_constraints and any_violation:
            results.append(
                (
                    "semantic:native_constraints",
                    False,
                    "constraints_honored_natively=true conflicts with constraint violations",
                )
            )
            all_pass = False
        else:
            results.append(("semantic:native_constraints", True, "ok"))

        if result_status == "PASS" and negative_control.get("passed") is False:
            results.append(
                (
                    "semantic:negative_control",
                    False,
                    "PASS result cannot have negative_control_report.passed=false",
                )
            )
            all_pass = False
        else:
            results.append(("semantic:negative_control", True, "ok"))

        if result_status == "PASS" and fallback_report.get("triggered"):
            results.append(
                (
                    "semantic:fallback",
                    False,
                    "PASS result cannot have fallback_report.triggered=true",
                )
            )
            all_pass = False
        else:
            results.append(("semantic:fallback", True, "ok"))

    if args.strict and (args.out_dir / "artifact_hashes.json").exists():
        try:
            hashes = json.loads((args.out_dir / "artifact_hashes.json").read_text())
            for fname, expected_hex in hashes.items():
                fpath = args.out_dir / fname
                if not fpath.exists():
                    results.append((f"hash:{fname}", False, "file missing"))
                    all_pass = False
                    continue
                actual = sha256_of(fpath)
                if actual != expected_hex:
                    results.append((f"hash:{fname}", False, f"mismatch (got {actual[:16]}...)"))
                    all_pass = False
                else:
                    results.append((f"hash:{fname}", True, "ok"))
        except (json.JSONDecodeError, OSError) as e:
            results.append(("artifact_hashes.json", False, f"hash check failed: {e}"))
            all_pass = False

    print(f"=== Smoke artifact contract validation: {args.out_dir} ===")
    for name, ok, msg in results:
        flag = "PASS" if ok else "FAIL"
        print(f"  [{flag}] {name:38s} {msg}")
    print(f"\nOverall: {'PASS' if all_pass else 'FAIL'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
