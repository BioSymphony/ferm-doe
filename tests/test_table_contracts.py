from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.table_contracts import validate_table_contracts  # noqa: E402


class TableContractTests(unittest.TestCase):
    def test_repo_table_contracts_pass_current_targets(self) -> None:
        report = validate_table_contracts(ROOT / "schemas" / "tables", ROOT)
        self.assertEqual(report["status"], "PASS")
        self.assertGreaterEqual(report["checked_files"], 1)

    def test_missing_required_field_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema_dir = root / "schemas" / "tables"
            schema_dir.mkdir(parents=True)
            data_dir = root / "data"
            data_dir.mkdir()
            (schema_dir / "minimal.schema.json").write_text(
                json.dumps(
                    {
                        "name": "minimal",
                        "fields": [
                            {"name": "run_id", "type": "string", "constraints": {"required": True}},
                            {"name": "trust_score", "type": "number", "constraints": {"minimum": 0, "maximum": 1}},
                        ],
                        "x-biosymphony": {"targets": ["data/*.csv"]},
                    }
                )
            )
            (data_dir / "bad.csv").write_text("trust_score\n1.4\n")

            report = validate_table_contracts(schema_dir, root)

        self.assertEqual(report["status"], "FAIL")
        messages = [finding["message"] for finding in report["findings"]]
        self.assertIn("missing required field: run_id", messages)

    def test_duplicate_primary_key_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema_dir = root / "schemas" / "tables"
            schema_dir.mkdir(parents=True)
            data_dir = root / "data"
            data_dir.mkdir()
            (schema_dir / "evidence.schema.json").write_text(
                json.dumps(
                    {
                        "name": "evidence",
                        "fields": [
                            {"name": "evidence_id", "type": "string", "constraints": {"required": True}},
                            {"name": "claim", "type": "string", "constraints": {"required": True}},
                        ],
                        "primaryKey": "evidence_id",
                        "x-biosymphony": {"targets": ["data/*.csv"]},
                    }
                )
            )
            (data_dir / "bad.csv").write_text("evidence_id,claim\nev-1,first\nev-1,second\n")

            report = validate_table_contracts(schema_dir, root)

        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any("duplicate primaryKey value" in finding["message"] for finding in report["findings"]))


if __name__ == "__main__":
    unittest.main()
