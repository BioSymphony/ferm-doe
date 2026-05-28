from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.compiler import compile_campaign_state  # noqa: E402
from biosymphony_ferm_doe.contract import contract_self_check  # noqa: E402
from biosymphony_ferm_doe.doe import propose_candidate_designs  # noqa: E402
from biosymphony_ferm_doe.dossier import check_dossier, compile_dossier  # noqa: E402


FIXTURES = ROOT / "tests/fixtures/campaign_arms"
INLINE_MULTI_ARM = FIXTURES / "inline_multi_arm_manifest.json"
ACTIVE_PLATE = FIXTURES / "active_plate_manifest.json"
LEGACY_SINGLE_ARM = FIXTURES / "legacy_single_arm_manifest.json"


class CampaignArmsV1Tests(unittest.TestCase):
    def test_inline_multi_arm_without_active_arm_cannot_generate_chimeric_executable_design(self) -> None:
        state = compile_campaign_state(INLINE_MULTI_ARM)
        self.assertEqual(state["readiness_precheck"]["status"], "RED")
        self.assertTrue(_has_issue(state, "active_factor_space_required"))

        with tempfile.TemporaryDirectory() as tmp:
            try:
                designs = propose_candidate_designs(INLINE_MULTI_ARM, state, Path(tmp) / "designs", run_budget=8)
            except ValueError as exc:
                self.assertRegex(str(exc), "active|arm|multi|chimeric|executable")
                return

        executable = [candidate for candidate in designs["candidates"] if candidate.get("rows") and candidate.get("design_id") != "skeptical_audit"]
        self.assertEqual(executable, [], "multi-arm campaigns without an active arm must not emit executable candidates")

    def test_active_arm_projects_only_that_arm(self) -> None:
        state = compile_campaign_state(ACTIVE_PLATE)
        factors = {factor["factor_id"]: factor for factor in state["factors"]}

        self.assertEqual(set(factors), {"plate_ph", "plate_fill_ul"})
        self.assertTrue(all(factor.get("arm_id") == "plate" for factor in factors.values()))
        self.assertEqual(state["design_policy"].get("active_factor_space"), "plate")

        designs = propose_candidate_designs(ACTIVE_PLATE, state, run_budget=6)
        for candidate in _executable_candidates(designs):
            self.assertEqual(_row_field_names(candidate["rows"]), {"run_id", "plate_ph", "plate_fill_ul"})
            self.assertTrue(all(str(row.get("run_id", "")).startswith("plate:") for row in candidate["rows"]))

    def test_per_arm_coordinator_outputs_separate_candidates(self) -> None:
        state = compile_campaign_state(INLINE_MULTI_ARM)
        designs = propose_candidate_designs(INLINE_MULTI_ARM, state, run_budget=8)

        self.assertEqual(designs.get("campaign_arm_mode"), "per_arm")
        per_arm = designs.get("campaign_arms")
        self.assertIsInstance(per_arm, list)
        self.assertEqual({arm["arm_id"] for arm in per_arm}, {"plate", "reactor"})

        for arm in per_arm:
            self.assertGreater(arm.get("candidate_count", 0), 0)
            self.assertTrue(arm.get("candidates"), arm)
            for candidate in _executable_candidates(arm):
                factor_fields = _row_field_names(candidate["rows"]) - {"run_id"}
                self.assertTrue(factor_fields)
                self.assertTrue(all(field.startswith(f"{arm['arm_id']}_") for field in factor_fields))
                self.assertTrue(all(str(row.get("run_id", "")).startswith(f"{arm['arm_id']}:") for row in candidate["rows"]))

    def test_per_arm_dossier_artifacts_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp) / "dossier"
            manifest = compile_dossier(INLINE_MULTI_ARM, dossier, run_budget=8)

            self.assertEqual(manifest["dossier_kind"], "ferm_doe_dossier")
            self.assertEqual(manifest.get("campaign_arm_mode"), "per_arm")
            self.assertEqual({arm["arm_id"] for arm in manifest.get("campaign_arms", [])}, {"plate", "reactor"})

            for arm_id in ["plate", "reactor"]:
                arm_dir = dossier / "campaign_arms" / arm_id
                self.assertTrue((arm_dir / "candidate_designs.json").exists())
                self.assertTrue((arm_dir / "design_adjudication.json").exists())
                self.assertTrue((arm_dir / "selected_wave_1_design.csv").exists())
                self.assertTrue((arm_dir / "run-sheet.tsv").exists())

            self.assertTrue((dossier / "per_arm_projection_summary.json").exists())
            summary = json.loads((dossier / "per_arm_projection_summary.json").read_text())
            self.assertEqual({arm["arm_id"] for arm in summary["arms"]}, {"plate", "reactor"})
            setup = json.loads((dossier / "experimental_setup.json").read_text())
            self.assertEqual({arm["arm_id"] for arm in setup["arms"]}, {"plate", "reactor"})
            horizontal = _read_csv(dossier / "horizontal_doe.csv")
            self.assertEqual({row["arm_id"] for row in horizontal}, {"plate", "reactor"})
            self.assertTrue(all(row["condition_set_kind"] == "new_planned_condition" for row in horizontal))
            self.assertTrue(all(row["optimization_goal"] for row in horizontal))

    def test_horizontal_doe_joins_per_arm_index_but_executable_csvs_stay_arm_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp) / "dossier"
            compile_dossier(INLINE_MULTI_ARM, dossier, run_budget=8)

            horizontal_rows, horizontal_headers = _read_csv_with_headers(dossier / "horizontal_doe.csv")
            horizontal_json = json.loads((dossier / "horizontal_doe.json").read_text())
            index_rows = _read_csv(dossier / "selected_wave_1_design.csv")
            self.assertEqual(horizontal_json["row_count"], len(index_rows))
            self.assertEqual(horizontal_json["row_count"], len(horizontal_rows))
            self.assertEqual(
                {(row["arm_id"], row["run_id"]) for row in horizontal_rows},
                {(row["arm_id"], row["run_id"]) for row in index_rows},
            )
            self.assertIn("Per-arm executable CSVs remain the authority", " ".join(horizontal_json["notes"]))

            factors_by_arm = {
                "plate": {"plate_ph", "plate_fill_ul"},
                "reactor": {"reactor_temp_c", "reactor_feed_ml_h"},
            }
            self.assertTrue(set().union(*factors_by_arm.values()) <= set(horizontal_headers))
            for row in horizontal_rows:
                arm_id = row["arm_id"]
                own_factors = factors_by_arm[arm_id]
                other_factors = set().union(*(items for other, items in factors_by_arm.items() if other != arm_id))
                self.assertTrue(all(row.get(factor_id) not in {"", None} for factor_id in own_factors))
                self.assertTrue(all(row.get(factor_id, "") == "" for factor_id in other_factors))

            for index_row in index_rows:
                arm_id = index_row["arm_id"]
                executable = dossier / index_row["executable_artifact"]
                self.assertTrue(executable.exists(), index_row)
                executable_rows, executable_headers = _read_csv_with_headers(executable)
                self.assertIn(index_row["run_id"], {row["run_id"] for row in executable_rows})
                self.assertTrue(factors_by_arm[arm_id] <= set(executable_headers))
                other_factors = set().union(*(items for other, items in factors_by_arm.items() if other != arm_id))
                self.assertTrue(other_factors.isdisjoint(executable_headers))

    def test_run_ids_are_namespaced_by_arm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp) / "dossier"
            compile_dossier(INLINE_MULTI_ARM, dossier, run_budget=8)

            all_ids: list[str] = []
            for arm_id in ["plate", "reactor"]:
                selected = dossier / "campaign_arms" / arm_id / "selected_wave_1_design.csv"
                rows = _read_csv(selected)
                self.assertTrue(rows)
                run_ids = [row["run_id"] for row in rows]
                self.assertTrue(all(run_id.startswith(f"{arm_id}:") for run_id in run_ids))
                self.assertEqual(len(run_ids), len(set(run_ids)))
                all_ids.extend(run_ids)
            self.assertEqual(len(all_ids), len(set(all_ids)))

    def test_legacy_single_arm_compatibility_stays_intact(self) -> None:
        state = compile_campaign_state(LEGACY_SINGLE_ARM)
        self.assertEqual(state["campaign_id"], "legacy-single-arm-demo")
        self.assertEqual({factor["factor_id"] for factor in state["factors"]}, {"temperature_c", "ph_setpoint"})

        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp) / "dossier"
            manifest = compile_dossier(LEGACY_SINGLE_ARM, dossier, run_budget=6)

            self.assertEqual(manifest["campaign_id"], "legacy-single-arm-demo")
            self.assertNotIn("campaign_arm_mode", manifest)
            self.assertFalse((dossier / "campaign_arms").exists())
            self.assertEqual(check_dossier(dossier)["status"], "PASS")
            self.assertEqual(contract_self_check(dossier)["status"], "PASS")
            rows = _read_csv(dossier / "selected_wave_1_design.csv")
            self.assertTrue(rows)
            self.assertTrue(all(":" not in row["run_id"] for row in rows))


def _executable_candidates(designs: dict[str, object]) -> list[dict[str, object]]:
    return [
        candidate
        for candidate in designs.get("candidates", [])
        if isinstance(candidate, dict) and candidate.get("rows") and candidate.get("design_id") != "skeptical_audit"
    ]


def _row_field_names(rows: list[dict[str, object]]) -> set[str]:
    fields: set[str] = set()
    for row in rows:
        fields.update(key for key, value in row.items() if value not in {"", None})
    return fields


def _has_issue(state: dict[str, object], code: str) -> bool:
    haystacks = [state.get("input_conflicts", []), state.get("missing_info", [])]
    return any(code in json.dumps(item, sort_keys=True) for items in haystacks for item in items)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _read_csv_with_headers(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


if __name__ == "__main__":
    unittest.main()
