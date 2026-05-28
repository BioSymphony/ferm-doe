#!/usr/bin/env python3
"""Compile a full runnable Ferm DoE dossier."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _engine_path import ensure_src_path

ensure_src_path()

from biosymphony_ferm_doe.dossier import compile_dossier


def _run_pubmed_fixture(fixture_path: Path, out_dir: Path) -> dict:
    """Fetch citations from a PubMed fixture and write pubmed_citations.json.

    This is the fixture-driven counterpart to the live MCP path. When
    ``--use-pubmed-fixture`` is supplied, the compiler:

    1. Calls :func:`~biosymphony_ferm_doe.adapters.pubmed_mcp.fetch_citations`
       with the fixture path.
    2. Writes the normalised records to ``<out>/pubmed_citations.json``.
    3. Returns a summary dict that is merged into the top-level CLI output.

    When ``--use-pubmed-fixture`` is absent the step is skipped entirely and
    the dossier compiles without any PubMed enrichment (graceful degradation).

    Parameters
    ----------
    fixture_path:
        Path to a fixture JSON file accepted by the pubmed_mcp adapter
        (bare JSON array or ``{"records": [...]}`` wrapper).
    out_dir:
        Dossier output directory (must already exist).

    Returns
    -------
    dict
        ``{"pubmed_source": ..., "pubmed_record_count": ..., "pubmed_out": ...}``
    """
    from biosymphony_ferm_doe.adapters.pubmed_mcp import fetch_citations

    result = fetch_citations(fixture_path=fixture_path)
    out_path = out_dir / "pubmed_citations.json"
    out_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pubmed_citations_kind": "ferm_doe_pubmed_citations",
                "source": result["source"],
                "fixture_path": result.get("fixture_path"),
                "record_count": result["record_count"],
                "caveat": result["caveat"],
                "records": result["records"],
            },
            indent=2,
        )
    )
    return {
        "pubmed_source": result["source"],
        "pubmed_record_count": result["record_count"],
        "pubmed_out": str(out_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile a full runnable Ferm DoE dossier."
    )
    parser.add_argument("--manifest", required=True, help="Path to campaign manifest JSON.")
    parser.add_argument("--out", required=True, help="Output directory for dossier files.")
    parser.add_argument("--run-budget", type=int, help="Max design candidates to generate.")
    parser.add_argument("--enable-swarm", action="store_true", help="Enable swarm review step.")
    parser.add_argument(
        "--use-pubmed-fixture",
        metavar="FIXTURE_PATH",
        default=None,
        help=(
            "Path to a PubMed fixture JSON file (bare array or {\"records\": [...]} wrapper). "
            "When provided, the adapter fetches citations from the fixture and writes "
            "pubmed_citations.json to the output directory. "
            "Omit to skip PubMed enrichment entirely (dossier still compiles). "
            "See tests/fixtures/pubmed/ for canonical smoke fixtures."
        ),
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    result = compile_dossier(
        Path(args.manifest), out_dir, args.run_budget, enable_swarm=args.enable_swarm
    )

    pubmed_summary: dict = {}
    if args.use_pubmed_fixture:
        fixture_path = Path(args.use_pubmed_fixture)
        try:
            pubmed_summary = _run_pubmed_fixture(fixture_path, out_dir)
        except Exception as exc:
            # Graceful degradation: PubMed enrichment failure must not crash the dossier.
            pubmed_summary = {
                "pubmed_source": "error",
                "pubmed_record_count": 0,
                "pubmed_error": str(exc),
            }

    output = {
        "status": result["readiness_status"],
        "selected_design_id": result["selected_design_id"],
    }
    output.update(pubmed_summary)
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
