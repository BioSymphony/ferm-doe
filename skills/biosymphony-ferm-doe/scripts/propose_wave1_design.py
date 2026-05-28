#!/usr/bin/env python3
"""Generate candidate first-batch DOE designs and scorecards."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _engine_path import ensure_src_path

ensure_src_path()

from biosymphony_ferm_doe.doe import propose_candidate_designs
from biosymphony_ferm_doe.tournament import run_design_tournament


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--run-budget", type=int)
    args = parser.parse_args()
    propose_candidate_designs(Path(args.manifest), out_dir=Path(args.out) / "design_candidates", run_budget=args.run_budget)
    result = run_design_tournament(Path(args.manifest), out_dir=Path(args.out), run_budget=args.run_budget)
    print(json.dumps({"status": result["verdict"], "selected_design_id": result["selected_design_id"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
