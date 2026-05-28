"""Tests for the PubMed MCP adapter (fixture-driven path).

Coverage:
- normalize_pubmed_record: pre-normalised passthrough and PubMed-MCP-shape mapping
- fetch_citations: fixture source, fallback source, absent-fixture fallback, empty fallback
- is_available: fixture-absent and fixture-present
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biosymphony_ferm_doe.adapters.pubmed_mcp import (  # noqa: E402
    CITATION_FIELDS,
    fetch_citations,
    is_available,
    normalize_pubmed_record,
)

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "pubmed" / "sample-pubmed-fixture.json"
FALLBACK_PATH = ROOT / "tests" / "fixtures" / "pubmed" / "sample-fallback-citations.json"

EXPECTED_FIXTURE_COUNT = 6


# ---------------------------------------------------------------------------
# normalize_pubmed_record
# ---------------------------------------------------------------------------

class NormalizeRecordTests(unittest.TestCase):
    def test_pre_normalised_record_passthrough(self) -> None:
        """A record already in CITATIONS.json schema passes through unchanged."""
        record = {
            "id": "test001",
            "type": "article",
            "title": "Test xylanase paper",
            "authors": ["Author, Alice", "Bauthor, Bob"],
            "year": 2024,
            "venue": "Test Journal",
            "doi": "10.1234/test.2024",
            "url": "https://doi.org/10.1234/test.2024",
            "phase_used": [1, 2],
            "claim_supported": "A test claim.",
            "non_claim": "A test non-claim.",
        }
        result = normalize_pubmed_record(record)
        self.assertEqual(result["id"], "test001")
        self.assertEqual(result["type"], "article")
        self.assertEqual(result["title"], "Test xylanase paper")
        self.assertEqual(result["authors"], ["Author, Alice", "Bauthor, Bob"])
        self.assertEqual(result["year"], 2024)
        self.assertEqual(result["phase_used"], [1, 2])

    def test_pre_normalised_missing_optional_fields_get_defaults(self) -> None:
        """Optional fields receive safe defaults when absent."""
        record = {
            "id": "minimal",
            "type": "article",
            "title": "Minimal paper",
            "authors": ["X, Y"],
            "year": 2020,
            "venue": "J",
            "doi": None,
            "url": "",
            "phase_used": [],
            "claim_supported": "Something.",
            "non_claim": "Nothing.",
        }
        result = normalize_pubmed_record(record)
        self.assertEqual(result["non_claim"], "Nothing.")
        self.assertEqual(result["phase_used"], [])
        # doi key must be present (even if None) so consumers can do record["doi"]
        self.assertIn("doi", result)

    def test_pubmed_mcp_shape_authors_as_dicts(self) -> None:
        """PubMed MCP returns authors as [{"name": ..., "authtype": ...}]; map to list."""
        record = {
            "pmid": "12345678",
            "title": "A xylanase paper",
            "authors": [
                {"name": "Smith, John A.", "authtype": "Author"},
                {"name": "Jones, Beth C.", "authtype": "Author"},
            ],
            "source": "Nature Methods",
            "pubdate": "2022",
            "doi": "10.1038/s41592-022-00001-1",
        }
        result = normalize_pubmed_record(record)
        self.assertEqual(result["id"], "pubmed_12345678")
        self.assertEqual(result["authors"], ["Smith, John A.", "Jones, Beth C."])
        self.assertEqual(result["venue"], "Nature Methods")
        self.assertEqual(result["year"], 2022)
        self.assertEqual(result["doi"], "10.1038/s41592-022-00001-1")
        self.assertIn("doi.org", result["url"])

    def test_pubmed_mcp_shape_no_doi_falls_back_to_pubmed_url(self) -> None:
        """When DOI is absent, URL falls back to PubMed link."""
        record = {"pmid": "99887766", "title": "Old paper"}
        result = normalize_pubmed_record(record)
        self.assertIsNone(result["doi"])
        self.assertIn("pubmed", result["url"])
        self.assertIn("99887766", result["url"])

    def test_pubmed_mcp_shape_missing_pmid_gives_unknown_id(self) -> None:
        """Records with no PMID get a safe fallback ID."""
        result = normalize_pubmed_record({"title": "No identifier"})
        self.assertEqual(result["id"], "pubmed_unknown")

    def test_pubmed_mcp_shape_year_parsed_from_pubdate_prefix(self) -> None:
        """Year is extracted from a 'YYYY Mon DD' pubdate string."""
        record = {"pmid": "11111111", "pubdate": "2019 Jun 15"}
        result = normalize_pubmed_record(record)
        self.assertEqual(result["year"], 2019)

    def test_pubmed_mcp_shape_unparseable_year_is_none(self) -> None:
        """Unparseable year becomes None rather than raising."""
        record = {"pmid": "22222222", "pubdate": "unparseable"}
        result = normalize_pubmed_record(record)
        self.assertIsNone(result["year"])

    def test_all_canonical_fields_present_in_output(self) -> None:
        """Every CITATION_FIELDS key appears in normalised output."""
        record = {
            "pmid": "33333333",
            "title": "Complete coverage",
            "authors": [{"name": "A, B", "authtype": "Author"}],
            "source": "J",
            "pubdate": "2021",
            "doi": "10.1234/x",
        }
        result = normalize_pubmed_record(record)
        for field in CITATION_FIELDS:
            self.assertIn(field, result, f"Missing canonical field: {field}")


# ---------------------------------------------------------------------------
# fetch_citations — fixture source
# ---------------------------------------------------------------------------

class FetchCitationsFixtureTests(unittest.TestCase):
    def test_source_is_fixture_when_path_given(self) -> None:
        result = fetch_citations("xylanase fermentation Penicillium", fixture_path=FIXTURE_PATH)
        self.assertEqual(result["source"], "fixture")

    def test_record_count_matches_expected(self) -> None:
        result = fetch_citations(fixture_path=FIXTURE_PATH)
        self.assertEqual(result["record_count"], EXPECTED_FIXTURE_COUNT)
        self.assertEqual(len(result["records"]), EXPECTED_FIXTURE_COUNT)

    def test_fixture_path_echoed_in_result(self) -> None:
        result = fetch_citations(fixture_path=FIXTURE_PATH)
        self.assertIsNotNone(result["fixture_path"])
        self.assertIn("sample-pubmed-fixture.json", result["fixture_path"])

    def test_all_records_have_required_fields(self) -> None:
        required = {"id", "type", "title", "authors", "year", "venue", "phase_used"}
        result = fetch_citations(fixture_path=FIXTURE_PATH)
        for record in result["records"]:
            missing = required - set(record.keys())
            self.assertFalse(
                missing,
                f"Record {record.get('id')!r} is missing fields: {missing}",
            )

    def test_fixture_ids_are_unique(self) -> None:
        result = fetch_citations(fixture_path=FIXTURE_PATH)
        ids = [r["id"] for r in result["records"]]
        self.assertEqual(len(ids), len(set(ids)), "Fixture contains duplicate IDs")

    def test_authors_are_non_empty_lists(self) -> None:
        result = fetch_citations(fixture_path=FIXTURE_PATH)
        for record in result["records"]:
            self.assertIsInstance(
                record["authors"],
                list,
                f"authors not a list in {record['id']!r}",
            )
            self.assertGreater(
                len(record["authors"]),
                0,
                f"Empty authors list in {record['id']!r}",
            )

    def test_years_are_integers(self) -> None:
        result = fetch_citations(fixture_path=FIXTURE_PATH)
        for record in result["records"]:
            self.assertIsInstance(
                record.get("year"),
                int,
                f"year is not int in {record['id']!r}",
            )

    def test_dois_are_strings_or_none(self) -> None:
        result = fetch_citations(fixture_path=FIXTURE_PATH)
        for record in result["records"]:
            doi = record.get("doi")
            self.assertTrue(
                doi is None or isinstance(doi, str),
                f"doi is neither None nor str in {record['id']!r}",
            )

    def test_caveat_mentions_fixture(self) -> None:
        result = fetch_citations(fixture_path=FIXTURE_PATH)
        caveat = result.get("caveat", "")
        self.assertTrue(caveat, "caveat is empty")
        self.assertIn("fixture", caveat.lower())

    def test_phase_used_are_lists(self) -> None:
        result = fetch_citations(fixture_path=FIXTURE_PATH)
        for record in result["records"]:
            self.assertIsInstance(
                record.get("phase_used"),
                list,
                f"phase_used is not a list in {record['id']!r}",
            )

    def test_claim_supported_is_non_empty_string(self) -> None:
        result = fetch_citations(fixture_path=FIXTURE_PATH)
        for record in result["records"]:
            self.assertIsInstance(
                record.get("claim_supported"),
                str,
                f"claim_supported not str in {record['id']!r}",
            )
            self.assertTrue(
                record["claim_supported"].strip(),
                f"claim_supported is blank in {record['id']!r}",
            )


# ---------------------------------------------------------------------------
# fetch_citations — fallback source
# ---------------------------------------------------------------------------

class FetchCitationsFallbackTests(unittest.TestCase):
    def test_fallback_when_fixture_path_absent(self) -> None:
        """When fixture_path points to a non-existent file, fallback is used."""
        result = fetch_citations(
            "xylanase fermentation",
            fixture_path="/tmp/definitely_absent_pubmed_fixture.json",
            fallback_citations_path=FALLBACK_PATH,
        )
        self.assertEqual(result["source"], "fallback")
        self.assertGreater(result["record_count"], 0)

    def test_fallback_record_count_matches_citations_json(self) -> None:
        """Fallback returns exactly the records in CITATIONS.json."""
        expected = json.loads(FALLBACK_PATH.read_text())
        result = fetch_citations(fallback_citations_path=FALLBACK_PATH)
        self.assertEqual(result["record_count"], len(expected))

    def test_fallback_returns_empty_when_both_missing(self) -> None:
        """When fixture and fallback are both absent, records is [] not an error."""
        result = fetch_citations(
            fixture_path="/tmp/absent_fixture.json",
            fallback_citations_path="/tmp/absent_citations.json",
        )
        self.assertEqual(result["source"], "fallback")
        self.assertEqual(result["record_count"], 0)
        self.assertEqual(result["records"], [])

    def test_fallback_caveat_is_non_empty(self) -> None:
        result = fetch_citations(fallback_citations_path=FALLBACK_PATH)
        self.assertTrue(result.get("caveat", ""))

    def test_no_fixture_no_fallback_source_is_fallback(self) -> None:
        """Calling with no paths at all still returns a valid result dict."""
        result = fetch_citations()
        self.assertEqual(result["source"], "fallback")
        self.assertIn("records", result)
        self.assertIn("record_count", result)
        self.assertIn("caveat", result)


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------

class IsAvailableTests(unittest.TestCase):
    def test_true_when_fixture_exists(self) -> None:
        self.assertTrue(is_available(fixture_path=FIXTURE_PATH))

    def test_false_when_fixture_absent(self) -> None:
        self.assertFalse(is_available(fixture_path="/tmp/no_such_fixture.json"))

    def test_false_with_no_args(self) -> None:
        """Without a fixture path, is_available returns False (cannot probe MCP without a live call)."""
        self.assertFalse(is_available())


if __name__ == "__main__":
    unittest.main()
