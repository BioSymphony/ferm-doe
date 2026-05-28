"""PubMed MCP adapter for dossier citation enrichment.

Thin adapter layer that normalises PubMed API records into the
biosymphony-ferm-doe CITATIONS.json schema.

Two runtime modes
-----------------
1. **Fixture mode** — reads a local JSON fixture that mirrors the PubMed
   response shape.  Used for CI, offline development, and subagent contexts
   where the MCP plugin (``mcp__plugin_pubmed_PubMed__*``) is not available.
   This is the primary path exercised by tests.

2. **MCP mode** (future) — calls ``mcp__plugin_pubmed_PubMed__search_articles``
   when invoked from an MCP-aware context that has the PubMed plugin wired in.
   The hook point is :func:`_try_mcp_fetch`; replace its body with a real
   bridge call when the MCP runtime is available.

Fallback
--------
If neither fixture nor MCP is reachable, the adapter returns the existing
``CITATIONS.json`` records from the dossier directory unchanged (no new
citations added, compilation still succeeds).

Public API
----------
- :func:`fetch_citations` — main entry point
- :func:`normalize_pubmed_record` — maps PubMed or pre-normalised records
- :func:`is_available` — probes fixture existence
- :data:`CITATION_FIELDS` — canonical field list matching CITATIONS.json schema
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Schema version consumed by the dossier harvester and compile_ferm_doe_dossier
CITATION_SCHEMA_VERSION = 1

# Canonical field names that must appear in every CITATIONS.json entry.
# Consumers (harvester, dossier renderer, BibTeX exporter) depend on this order.
CITATION_FIELDS = [
    "id",
    "type",
    "title",
    "authors",
    "year",
    "venue",
    "doi",
    "url",
    "phase_used",
    "claim_supported",
    "non_claim",
]


def normalize_pubmed_record(record: dict[str, Any]) -> dict[str, Any]:
    """Normalise a PubMed-shaped or pre-normalised record into a CITATIONS.json entry.

    Accepts two input shapes:

    **Pre-normalised** (already in CITATIONS.json schema):
      Fields ``"type"`` *and* ``"claim_supported"`` both present.
      Passed through with missing optional fields filled with safe defaults.

    **PubMed MCP shape** (from ``mcp__plugin_pubmed_PubMed__get_article_metadata``):
      Fields ``"pmid"`` / ``"uid"``, ``"authors"`` as a list of dicts with
      ``{"name": ..., "authtype": ...}``, ``"source"`` for journal name,
      ``"pubdate"`` for year.  Mapped to our schema.

    Parameters
    ----------
    record:
        Raw record dict in either shape.

    Returns
    -------
    dict
        Normalised citation record with all :data:`CITATION_FIELDS` present.
    """
    # --- Pre-normalised passthrough ---
    if "type" in record and "claim_supported" in record:
        out: dict[str, Any] = {field: record.get(field) for field in CITATION_FIELDS}
        out.setdefault("type", "article")
        out.setdefault("phase_used", [])
        out.setdefault("claim_supported", "")
        out.setdefault("non_claim", "")
        # Keep doi key even when None so consumers can do record["doi"] safely
        return out

    # --- PubMed MCP shape mapping ---
    pmid = str(record.get("pmid") or record.get("uid") or "").strip()

    authors_raw = record.get("authors") or []
    if isinstance(authors_raw, list) and authors_raw and isinstance(authors_raw[0], dict):
        # PubMed returns [{"name": "Last FM", "authtype": "Author"}, ...]
        authors: list[str] = [a.get("name", "") for a in authors_raw if isinstance(a, dict)]
    else:
        authors = [str(a) for a in authors_raw]

    doi_raw = str(record.get("doi") or record.get("elocationid") or "").strip()
    # Strip "doi: " prefix that some PubMed responses include
    doi = doi_raw.lstrip("doi:").strip() if doi_raw else ""
    url = (
        f"https://doi.org/{doi}"
        if doi
        else (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "")
    )

    year_raw = record.get("pubdate") or record.get("year") or ""
    try:
        year: int | None = int(str(year_raw)[:4])
    except (ValueError, TypeError):
        year = None

    record_id = record.get("id") or (f"pubmed_{pmid}" if pmid else "pubmed_unknown")

    return {
        "id": record_id,
        "type": "article",
        "title": record.get("title") or "",
        "authors": authors,
        "year": year,
        "venue": (
            record.get("source")
            or record.get("fulljournalname")
            or record.get("journal")
            or ""
        ),
        "doi": doi or None,
        "url": url,
        "phase_used": record.get("phase_used") or [],
        "claim_supported": record.get("claim_supported") or "",
        "non_claim": record.get("non_claim") or "",
    }


# ---------------------------------------------------------------------------
# Internal loaders
# ---------------------------------------------------------------------------

def _load_fixture(fixture_path: Path) -> list[dict[str, Any]]:
    """Load and validate a PubMed fixture JSON file.

    The fixture may be a bare JSON array **or** a ``{"records": [...]}``
    wrapper (which allows future metadata fields alongside the records).
    """
    raw = json.loads(fixture_path.read_text())
    if isinstance(raw, list):
        records = raw
    elif isinstance(raw, dict) and "records" in raw:
        records = raw["records"]
    else:
        raise ValueError(
            f"Fixture at {fixture_path} must be a JSON array or "
            '{"records": [...], ...}'
        )
    return [normalize_pubmed_record(r) for r in records]


def _load_fallback(fallback_path: Path | None) -> list[dict[str, Any]]:
    """Load existing CITATIONS.json as the last-resort fallback.

    Returns an empty list (not an error) when the path is None or absent —
    the adapter must degrade gracefully so dossier compilation never hard-fails
    just because PubMed is unreachable.
    """
    if fallback_path is None:
        return []
    if not fallback_path.exists():
        log.warning(
            "Fallback CITATIONS.json not found at %s; returning empty citation list",
            fallback_path,
        )
        return []
    try:
        raw = json.loads(fallback_path.read_text())
        if isinstance(raw, list):
            return raw
        log.warning(
            "CITATIONS.json at %s is not a JSON array; ignoring",
            fallback_path,
        )
        return []
    except Exception as exc:
        log.warning(
            "Could not parse fallback CITATIONS.json at %s: %s",
            fallback_path,
            exc,
        )
        return []


# ---------------------------------------------------------------------------
# MCP hook point
# ---------------------------------------------------------------------------

def _try_mcp_fetch(query: str, max_results: int) -> list[dict[str, Any]] | None:
    """Attempt to call the PubMed MCP plugin.

    **Current status:** stub — returns ``None`` so callers fall through to the
    fixture or fallback.  The PubMed MCP plugin
    (``mcp__plugin_pubmed_PubMed__search_articles``) is callable only from the
    Claude Code harness as a tool; it is not importable as a Python module.

    When a future MCP bridge is available, replace the body with::

        from biosymphony_ferm_doe.adapters._mcp_bridge import call_tool
        raw = call_tool(
            "mcp__plugin_pubmed_PubMed__search_articles",
            {"query": query, "max_results": max_results},
        )
        return [normalize_pubmed_record(r) for r in raw.get("articles", [])]

    The function signature and return type must remain stable so callers need
    no changes when the bridge lands.

    Returns
    -------
    list[dict] or None
        Normalised records on success, ``None`` if the MCP plugin is
        unavailable (triggers fallback in :func:`fetch_citations`).
    """
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_citations(
    query: str = "",
    *,
    fixture_path: Path | str | None = None,
    fallback_citations_path: Path | str | None = None,
    max_results: int = 20,
) -> dict[str, Any]:
    """Fetch PubMed citations and return a normalised result bundle.

    Resolution order
    ----------------
    1. **Fixture** — ``fixture_path`` provided and the file exists.
       Used in CI and offline/subagent contexts.
    2. **PubMed MCP plugin** — ``_try_mcp_fetch`` resolves to real records
       when the Claude Code harness wires in the PubMed tool at runtime.
    3. **Fallback CITATIONS.json** — existing campaign citations returned
       unchanged when neither fixture nor MCP is reachable.

    Parameters
    ----------
    query:
        Free-text PubMed search query (used in MCP mode; ignored in fixture
        and fallback modes).
    fixture_path:
        Path to a local JSON fixture file in PubMed or CITATIONS.json shape.
        If provided and the file exists, takes priority over MCP.
    fallback_citations_path:
        Path to an existing ``CITATIONS.json`` to serve as last-resort content
        when neither fixture nor MCP is available.
    max_results:
        Maximum number of PubMed results to fetch in MCP mode.

    Returns
    -------
    dict with keys:

    - ``source`` — ``"fixture"`` | ``"mcp"`` | ``"fallback"``
    - ``query`` — the query string used (or ``""`` for fixture/fallback)
    - ``records`` — list of normalised citation dicts matching CITATIONS.json schema
    - ``record_count`` — ``len(records)``
    - ``fixture_path`` — str path used, or ``None``
    - ``caveat`` — human-readable explanation of the source used
    """
    fp = Path(fixture_path) if fixture_path else None
    fb = Path(fallback_citations_path) if fallback_citations_path else None

    # 1. Fixture
    if fp is not None and fp.exists():
        try:
            records = _load_fixture(fp)
            return {
                "source": "fixture",
                "query": query,
                "records": records,
                "record_count": len(records),
                "fixture_path": str(fp),
                "caveat": (
                    f"PubMed results loaded from fixture {fp.name}. "
                    "Substitute mcp__plugin_pubmed_PubMed__search_articles "
                    "for live data in an MCP-aware context."
                ),
            }
        except Exception as exc:
            log.warning(
                "Failed to load fixture %s: %s — falling through to MCP/fallback",
                fp,
                exc,
            )

    # 2. MCP shim
    try:
        records_mcp = _try_mcp_fetch(query, max_results)
        if records_mcp is not None:
            return {
                "source": "mcp",
                "query": query,
                "records": records_mcp,
                "record_count": len(records_mcp),
                "fixture_path": None,
                "caveat": (
                    f"Live PubMed results via MCP plugin for query: {query!r}"
                ),
            }
    except Exception as exc:
        log.info("PubMed MCP not available or raised: %s", exc)

    # 3. Fallback
    records_fb = _load_fallback(fb)
    return {
        "source": "fallback",
        "query": query,
        "records": records_fb,
        "record_count": len(records_fb),
        "fixture_path": None,
        "caveat": (
            "PubMed MCP and fixture both unavailable. "
            "Returning existing CITATIONS.json as citation list. "
            "Wire a fixture_path or MCP context for enriched results."
        ),
    }


def is_available(fixture_path: Path | str | None = None) -> bool:
    """Return True if at least one non-fallback citation source is reachable.

    With a ``fixture_path`` provided, checks whether that file exists.
    Without a path, returns False — MCP availability cannot be probed
    without executing a live call, and probing eagerly would violate the
    lightweight-adapter contract.

    Parameters
    ----------
    fixture_path:
        Optional path to a fixture file to probe.
    """
    if fixture_path is not None:
        return Path(fixture_path).exists()
    # Without a fixture, we cannot confirm MCP is wired without a live call
    return False


__all__ = [
    "CITATION_FIELDS",
    "CITATION_SCHEMA_VERSION",
    "fetch_citations",
    "is_available",
    "normalize_pubmed_record",
]
