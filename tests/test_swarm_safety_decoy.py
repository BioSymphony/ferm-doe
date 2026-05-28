"""Tests for the generic safety_decoy evidence-quality machinery in
``biosymphony_ferm_doe.swarm``.

Covers:
* keyword extraction from constraint metadata
* generic constraint-related evidence detection
* validator behaviour across positive / negative / mixed evidence rows
* end-to-end ``build_assumption_attack`` integration including the
  None[:50] regression (the unflagged claim is None on one row)
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.swarm import (  # noqa: E402  (sys.path mutation above)
    build_assumption_attack,
    derive_safety_decoy_keywords,
    is_constraint_related_evidence,
    validate_evidence_quality_for_safety_decoy,
)


def _row(**overrides):
    base = {
        "evidence_id": "EV-0001",
        "validation_status": "usable",
        "claim": "",
        "caveat": "",
        "factor_or_response": "",
        "entity_type": "claim",
        "quality_label": "",
    }
    base.update(overrides)
    return base


class DeriveSafetyDecoyKeywordsTests(unittest.TestCase):
    def test_uses_explicit_evidence_keywords_when_present(self) -> None:
        constraint = {
            "constraint_id": "anything",
            "evidence_keywords": ["Anaerobic", "DO-loss"],
            "expected_lit_topics": ["should be ignored when explicit list provided"],
        }
        keywords = derive_safety_decoy_keywords(constraint)
        # explicit list wins; expected_lit_topics still contributes since
        # both sources stack rather than mutually exclude.
        self.assertIn("anaerobic", keywords)
        self.assertIn("do-loss", keywords)

    def test_extracts_phrases_and_tokens_from_expected_lit_topics(self) -> None:
        constraint = {
            "constraint_id": "anaerobic_at_induction_decoy",
            "expected_lit_topics": [
                "oxygen-limited induction in recombinant E. coli",
                "anaerobic and microaerobic recombinant protein expression",
            ],
        }
        keywords = derive_safety_decoy_keywords(constraint)
        self.assertIn("oxygen-limited induction in recombinant e. coli", keywords)
        self.assertIn("anaerobic", keywords)
        self.assertIn("microaerobic", keywords)
        self.assertIn("oxygen", keywords)
        # short / stopword tokens are filtered out
        self.assertNotIn("in", keywords)
        self.assertNotIn("and", keywords)

    def test_falls_back_to_description_when_no_topics(self) -> None:
        constraint = {
            "constraint_id": "high_acetate_decoy",
            "kind": "safety_decoy",
            "description": "Vessels driven into elevated acetate accumulation at induction.",
        }
        keywords = derive_safety_decoy_keywords(constraint)
        self.assertIn("acetate", keywords)
        self.assertIn("vessels", keywords)
        self.assertIn("induction", keywords)


class IsConstraintRelatedEvidenceTests(unittest.TestCase):
    def test_positive_match_against_claim(self) -> None:
        row = _row(claim="Anaerobic induction reduces titer in E. coli BL21.")
        self.assertTrue(is_constraint_related_evidence(row, {"anaerobic", "microaerobic"}))

    def test_negative_when_text_unrelated(self) -> None:
        row = _row(claim="Aerobic fed-batch with DO setpoint 30%.")
        self.assertFalse(is_constraint_related_evidence(row, {"anaerobic", "microaerobic"}))

    def test_empty_keywords_returns_false(self) -> None:
        row = _row(claim="Anaerobic induction reduces titer.")
        self.assertFalse(is_constraint_related_evidence(row, []))
        self.assertFalse(is_constraint_related_evidence(row, None))

    def test_matches_caveat_and_factor_fields(self) -> None:
        row = _row(claim="Generic claim", caveat="DO-loss recovery scenario")
        self.assertTrue(is_constraint_related_evidence(row, {"do-loss"}))


class ValidateEvidenceQualityTests(unittest.TestCase):
    KEYWORDS = {"anaerobic", "oxygen-limited", "microaerobic"}

    def test_positive_case_anaerobic_keyword_matches_and_is_flagged(self) -> None:
        rows = [
            _row(
                evidence_id="EV-A",
                claim="Anaerobic induction in BL21 produces sparse titer data.",
                caveat="Literature gap; extrapolated from microaerobic studies.",
                quality_label="low",
            ),
        ]
        result = validate_evidence_quality_for_safety_decoy(rows, self.KEYWORDS)
        self.assertEqual(result["total_related_rows"], 1)
        self.assertEqual(result["properly_flagged_rows"], 1)
        self.assertEqual(result["unflagged_rows"], 0)

    def test_negative_case_aerobic_does_not_match(self) -> None:
        rows = [
            _row(
                evidence_id="EV-B",
                claim="Aerobic fed-batch DO 30% confirmed for E. coli.",
                caveat="High-quality citation.",
                quality_label="high",
            ),
        ]
        result = validate_evidence_quality_for_safety_decoy(rows, self.KEYWORDS)
        self.assertEqual(result["total_related_rows"], 0)
        self.assertEqual(result["properly_flagged_rows"], 0)
        self.assertEqual(result["unflagged_rows"], 0)

    def test_mixed_flagged_and_unflagged_rows(self) -> None:
        rows = [
            _row(
                evidence_id="EV-1",
                claim="Anaerobic induction extrapolated from microaerobic literature.",
                caveat="Gap acknowledged; insufficient direct support.",
                quality_label="low",
            ),
            _row(
                evidence_id="EV-2",
                claim="Microaerobic protein expression yields are 30% of aerobic.",
                caveat="Direct citation, Smith 2018.",
                quality_label="high",
            ),
            _row(
                evidence_id="EV-3",
                claim="Aerobic fed-batch baseline.",
                caveat="Standard reference.",
                quality_label="high",
            ),
            _row(
                evidence_id="EV-4",
                validation_status="rejected",  # excluded from analysis
                claim="Anaerobic fermentation of E. coli.",
                caveat="Already rejected upstream.",
            ),
        ]
        result = validate_evidence_quality_for_safety_decoy(rows, self.KEYWORDS)
        # EV-1 and EV-2 are usable + related; EV-3 unrelated; EV-4 not usable.
        self.assertEqual(result["total_related_rows"], 2)
        self.assertEqual(result["properly_flagged_rows"], 1)
        self.assertEqual(result["unflagged_rows"], 1)
        unflagged_ids = {item["evidence_id"] for item in result["unflagged_details"]}
        self.assertEqual(unflagged_ids, {"EV-2"})

    def test_none_claim_does_not_crash(self) -> None:
        # Regression: original commit had ``row.get("claim")[:50]`` with no
        # None-guard. A row with an explicit ``claim: None`` must not raise.
        rows = [
            _row(
                evidence_id="EV-NULLCLAIM",
                claim=None,
                caveat="Anaerobic gap acknowledged.",
                quality_label="low",
            ),
            _row(
                evidence_id="EV-LONGCLAIM",
                claim="A" * 200,  # exercise the truncation branch
                caveat="anaerobic context, gap noted",
                quality_label="low",
            ),
        ]
        result = validate_evidence_quality_for_safety_decoy(rows, self.KEYWORDS)
        self.assertEqual(result["total_related_rows"], 2)
        self.assertEqual(result["properly_flagged_rows"], 2)
        # truncation applied to the long claim
        long_entry = next(
            entry
            for entry in result["flagged_details"]
            if entry["evidence_id"] == "EV-LONGCLAIM"
        )
        self.assertTrue(long_entry["claim"].endswith("..."))
        self.assertLessEqual(len(long_entry["claim"]), 53)


class BuildAssumptionAttackSafetyDecoyTests(unittest.TestCase):
    def _state_with_safety_decoy(self) -> dict:
        return {
            "campaign_id": "demo-decoy",
            "name": "demo",
            "missing_info": [],
            "responses": [],
            "factors": [
                {"factor_id": "induction_trigger", "name": "Induction trigger"},
                {"factor_id": "DO_setpoint_pct", "name": "Dissolved oxygen setpoint"},
                {"factor_id": "feed_rate_ml_h", "name": "Feed rate"},
            ],
            "constraints": [
                {
                    "constraint_id": "anaerobic_at_induction_decoy",
                    "kind": "safety_decoy",
                    "description": (
                        "Two of sixteen vessels driven into anaerobic conditions at induction."
                    ),
                    "expected_lit_topics": [
                        "oxygen-limited induction in recombinant E. coli",
                        "anaerobic and microaerobic recombinant protein expression",
                    ],
                },
            ],
            "workflow_modes": {"selected": []},
            "campaign_context": {},
        }

    def test_safety_decoy_constraint_emits_decoy_constraint_gap_challenge(self) -> None:
        state = self._state_with_safety_decoy()
        evidence_rows = [
            _row(
                evidence_id="EV-OK",
                claim="Anaerobic induction is poorly characterized in BL21.",
                caveat="Literature gap; extrapolated.",
                quality_label="low",
            ),
            _row(
                evidence_id="EV-BAD",
                claim="Anaerobic induction yields are well established at 30% of aerobic.",
                caveat="Confidently cited from Smith 2018.",
                quality_label="high",
            ),
        ]
        report = build_assumption_attack(state, evidence_rows=evidence_rows)
        decoy_challenges = [
            ch for ch in report["challenges"] if ch["category"] == "decoy_constraint_gap"
        ]
        self.assertEqual(len(decoy_challenges), 1)
        challenge = decoy_challenges[0]
        # severity & narrative
        self.assertEqual(challenge["severity"], "warning")
        self.assertIn("anaerobic_at_induction_decoy", challenge["assumption_under_attack"])
        # validator counts make it into why_it_matters
        self.assertIn("2 total rows", challenge["why_it_matters"])
        self.assertIn("1 properly flagged", challenge["why_it_matters"])
        self.assertIn("1 unflagged", challenge["why_it_matters"])
        # affected items resolved from factor names containing keywords
        self.assertIn("induction_trigger", challenge["affected_items"])

    def test_does_not_match_other_constraint_kinds(self) -> None:
        state = self._state_with_safety_decoy()
        state["constraints"].append(
            {
                "constraint_id": "run_time",
                "kind": "operational",
                "description": "Run time capped at 120 hours.",
            }
        )
        report = build_assumption_attack(state, evidence_rows=[])
        decoy_challenges = [
            ch for ch in report["challenges"] if ch["category"] == "decoy_constraint_gap"
        ]
        # exactly one safety_decoy constraint -> exactly one decoy challenge
        self.assertEqual(len(decoy_challenges), 1)

    def test_handles_multiple_safety_decoy_constraints(self) -> None:
        state = self._state_with_safety_decoy()
        state["constraints"].append(
            {
                "constraint_id": "high_acetate_decoy",
                "kind": "safety_decoy",
                "description": "Vessels driven to elevated acetate at induction.",
                "evidence_keywords": ["acetate"],
            }
        )
        report = build_assumption_attack(state, evidence_rows=[])
        decoy_challenges = [
            ch for ch in report["challenges"] if ch["category"] == "decoy_constraint_gap"
        ]
        self.assertEqual(len(decoy_challenges), 2)
        ids_in_text = " ".join(ch["assumption_under_attack"] for ch in decoy_challenges)
        self.assertIn("anaerobic_at_induction_decoy", ids_in_text)
        self.assertIn("high_acetate_decoy", ids_in_text)


if __name__ == "__main__":
    unittest.main()
