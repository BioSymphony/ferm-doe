from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.provenance import verify_artifact_hashes, write_dossier_provenance  # noqa: E402


class DossierProvenanceTests(unittest.TestCase):
    def test_writes_hash_manifest_and_ro_crate_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "campaign_state.json").write_text('{"campaign_id":"demo"}\n')
            (out / "readiness_verdict.md").write_text("# Verdict\n")
            (out / "design_candidates").mkdir()
            (out / "design_candidates" / "candidate.json").write_text('{"design_id":"demo"}\n')

            result = write_dossier_provenance(out, {"campaign_id": "demo"}, source_manifest_path=out / "source.json")
            hashes = json.loads((out / "artifact_hashes.json").read_text())
            crate = json.loads((out / "ro-crate-metadata.json").read_text())

        self.assertEqual(result["artifact_count"], 3)
        self.assertEqual(hashes["artifact_hash_kind"], "ferm_doe_dossier_sha256_manifest")
        self.assertEqual(hashes["artifact_count"], 3)
        self.assertIn("design_candidates/candidate.json", {item["path"] for item in hashes["artifacts"]})
        self.assertEqual(crate["@context"], "https://w3id.org/ro/crate/1.2/context")
        graph_ids = {item["@id"] for item in crate["@graph"]}
        self.assertIn("./", graph_ids)
        self.assertIn("artifact_hashes.json", graph_ids)

    def test_verifies_artifact_hashes_and_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "campaign_state.json").write_text('{"campaign_id":"demo"}\n')
            write_dossier_provenance(out, {"campaign_id": "demo"})
            clean = verify_artifact_hashes(out)
            (out / "campaign_state.json").write_text('{"campaign_id":"changed"}\n')
            tampered = verify_artifact_hashes(out)

        self.assertEqual(clean["status"], "PASS")
        self.assertEqual(tampered["status"], "FAIL")
        self.assertTrue(any("sha256 mismatch" in item for item in tampered["errors"]))


if __name__ == "__main__":
    unittest.main()
