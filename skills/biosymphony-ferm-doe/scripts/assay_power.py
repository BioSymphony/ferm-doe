#!/usr/bin/env python3
"""Assess response-level assay-power policy for a Ferm DoE campaign."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _engine_path import ensure_src_path

ensure_src_path()

from biosymphony_ferm_doe.utilities.assay_power import run_assay_power_utility


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-state", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--results")
    parser.add_argument("--backend", default="auto")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    result = run_assay_power_utility(
        Path(args.campaign_state),
        Path(args.out),
        results_path=Path(args.results) if args.results else None,
        backend=args.backend,
        strict=args.strict,
    )
    print(json.dumps({"status": result["status"], "primary_status": result["primary_status"], "score": result["score"]}, sort_keys=True))
    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
