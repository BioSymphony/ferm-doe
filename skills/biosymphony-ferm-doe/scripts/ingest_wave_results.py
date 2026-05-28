#!/usr/bin/env python3
"""Ingest batch results and recommend follow-up action."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _engine_path import ensure_src_path

ensure_src_path()

from biosymphony_ferm_doe.ingest import ingest_wave_results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-state", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--selected-design")
    args = parser.parse_args()
    result = ingest_wave_results(
        Path(args.campaign_state),
        Path(args.results),
        Path(args.out),
        selected_design_path=Path(args.selected_design) if args.selected_design else None,
    )
    print(json.dumps({"status": "OK", "recommended_action": result["recommended_action"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
