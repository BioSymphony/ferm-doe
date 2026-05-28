from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.contract import contract_self_check
from biosymphony_ferm_doe.dossier import compile_dossier
from biosymphony_ferm_doe.execution_plan import (
    EXECUTION_PLAN_FIELDS,
    RUN_SHEET_EXECUTION_FIELDS,
    build_execution_plan,
)


class ExecutionPlanTests(unittest.TestCase):
    def test_full_randomization_is_seeded_and_deterministic(self) -> None:
        state = {
            "campaign_id": "execution-plan-demo",
            "design_policy": {"execution_plan": {"mode": "full_randomization", "seed": 17}},
            "factors": [],
        }
        selected = {"design_id": "demo_design", "rows": [{"run_id": f"R{index}"} for index in range(1, 7)]}

        first = build_execution_plan(state, selected, "demo_design")
        second = build_execution_plan(state, selected, "demo_design")

        self.assertEqual(first, second)
        self.assertEqual(first["policy"]["mode"], "full_randomization")
        self.assertEqual(first["policy"]["seed"], 17)
        self.assertEqual({row["design_run_id"] for row in first["rows"]}, {f"R{index}" for index in range(1, 7)})
        self.assertEqual([row["execution_order"] for row in first["rows"]], [1, 2, 3, 4, 5, 6])
        self.assertEqual({row["randomization_group"] for row in first["rows"]}, {"all_runs"})

    def test_blocked_and_split_plot_modes_group_rows_before_randomizing_within_group(self) -> None:
        blocked_state = {
            "campaign_id": "blocked-demo",
            "design_policy": {"execution_plan": {"mode": "blocked_randomization", "seed": 5}},
            "factors": [],
        }
        selected = {
            "design_id": "blocked_design",
            "rows": [
                {"run_id": "R1", "block": "B"},
                {"run_id": "R2", "block": "A"},
                {"run_id": "R3", "block": "B"},
                {"run_id": "R4", "block": "A"},
            ],
        }

        blocked = build_execution_plan(blocked_state, selected, "blocked_design")
        blocked_sequence = [row["block_id"] for row in blocked["rows"]]
        self.assertEqual(blocked_sequence[:2], ["block_a", "block_a"])
        self.assertEqual(blocked_sequence[2:], ["block_b", "block_b"])

        split_state = {
            "campaign_id": "split-demo",
            "design_policy": {"execution_plan": {"mode": "split_plot_like", "seed": 9}},
            "factors": [{"factor_id": "day", "type": "hard_to_change"}],
        }
        split_selected = {
            "design_id": "split_design",
            "rows": [
                {"run_id": "R1", "day": "1"},
                {"run_id": "R2", "day": "2"},
                {"run_id": "R3", "day": "1"},
                {"run_id": "R4", "day": "2"},
            ],
        }
        split = build_execution_plan(split_state, split_selected, "split_design")

        self.assertEqual({row["block_id"] for row in split["rows"]}, {"whole_plot_day_1", "whole_plot_day_2"})
        for row in split["rows"]:
            self.assertEqual(row["randomization_group"], row["block_id"])

    def test_manual_locked_order_can_pin_selected_run_ids(self) -> None:
        state = {
            "campaign_id": "manual-demo",
            "design_policy": {"execution_plan": {"mode": "manual_locked_order", "seed": 1, "manual_order": ["R3", "R1"]}},
            "factors": [],
        }
        selected = {"design_id": "manual_design", "rows": [{"run_id": "R1"}, {"run_id": "R2"}, {"run_id": "R3"}]}

        plan = build_execution_plan(state, selected, "manual_design")

        self.assertEqual([row["design_run_id"] for row in plan["rows"]], ["R3", "R1", "R2"])
        self.assertEqual({row["randomization_group"] for row in plan["rows"]}, {"manual_locked"})

    def test_dossier_writes_execution_plan_without_polluting_selected_design_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = write_manifest(tmp_path / "manifest.json", mode="manual_locked_order")
            dossier = tmp_path / "dossier"

            compile_dossier(manifest, dossier, run_budget=6)

            selected_rows, selected_headers = read_csv(dossier / "selected_wave_1_design.csv")
            self.assertTrue(selected_rows)
            for field in EXECUTION_PLAN_FIELDS:
                self.assertNotIn(field, selected_headers)

            run_sheet_rows, run_sheet_headers = read_tsv(dossier / "run-sheet.tsv")
            for field in RUN_SHEET_EXECUTION_FIELDS:
                self.assertIn(field, run_sheet_headers)
            self.assertEqual(len(run_sheet_rows), len(selected_rows))
            self.assertEqual({row["design_run_id"] for row in run_sheet_rows}, {row["run_id"] for row in selected_rows})
            self.assertEqual([row["vessel_id_or_slot"] for row in run_sheet_rows[:4]], ["V1", "V2", "V1", "V2"])
            self.assertTrue(all(row["operator_actual_start"] == "" for row in run_sheet_rows))
            self.assertTrue(all(row["operator_actual_end"] == "" for row in run_sheet_rows))
            self.assertTrue(all(row["operator_notes"] == "" for row in run_sheet_rows))

            execution_plan = json.loads((dossier / "execution_plan.json").read_text())
            self.assertEqual(execution_plan["plan_kind"], "ferm_doe_execution_plan")
            self.assertEqual(execution_plan["policy"]["mode"], "manual_locked_order")
            contract = contract_self_check(dossier)
            self.assertEqual(contract["status"], "PASS", contract)

    def test_contract_self_check_uses_design_run_id_join_for_run_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest = write_manifest(tmp_path / "manifest.json", mode="full_randomization")
            dossier = tmp_path / "dossier"
            compile_dossier(manifest, dossier, run_budget=5)

            run_sheet_path = dossier / "run-sheet.tsv"
            rows, headers = read_tsv(run_sheet_path)
            rows[0]["design_run_id"] = "NOT-IN-SELECTED-DESIGN"
            with run_sheet_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=headers, delimiter="\t")
                writer.writeheader()
                writer.writerows(rows)

            contract = contract_self_check(dossier)
            self.assertEqual(contract["status"], "FAIL")
            self.assertTrue(any("run-sheet.tsv" in error for error in contract["errors"]))


def write_manifest(path: Path, mode: str) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "campaign_id": "execution-plan-dossier-demo",
                "name": "Execution plan dossier demo",
                "objective": {"primary": "Maximize titer", "direction": "maximize", "response_id": "titer_mg_l"},
                "readiness_target": "YELLOW",
                "sources": [],
                "inputs": [],
                "constraints": [{"constraint_id": "budget", "description": "6 run budget"}],
                "responses": [
                    {
                        "response_id": "titer_mg_l",
                        "name": "Titer",
                        "unit": "mg/L",
                        "direction": "maximize",
                        "class": "titer",
                        "sample_fraction": "whole_broth",
                        "assay_method": "HPLC",
                    }
                ],
                "factors": [
                    {"factor_id": "temperature_c", "type": "continuous", "min": 24, "max": 32},
                    {"factor_id": "ph", "type": "continuous", "min": 5.5, "max": 7.0},
                ],
                "design_policy": {
                    "run_budget": 6,
                    "execution_plan": {
                        "mode": mode,
                        "seed": 23,
                        "vessel_slots": ["V1", "V2"],
                        "setup_batch_size": 2,
                    },
                },
            }
        )
    )
    return path


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def read_tsv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [{key: value or "" for key, value in row.items()} for row in reader], list(reader.fieldnames or [])


if __name__ == "__main__":
    unittest.main()
