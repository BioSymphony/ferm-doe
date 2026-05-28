#!/usr/bin/env python3
"""Plan adaptive follow-up from joined first-batch results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _engine_path import ensure_src_path

ensure_src_path()

from biosymphony_ferm_doe.adaptive_wave2 import plan_adaptive_wave2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-state", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--selected-design")
    parser.add_argument("--remaining-budget", type=int)
    parser.add_argument("--backend", default="auto")
    args = parser.parse_args()
    result = plan_adaptive_wave2(
        Path(args.campaign_state),
        Path(args.results),
        Path(args.out),
        selected_design_path=Path(args.selected_design) if args.selected_design else None,
        remaining_budget=args.remaining_budget,
        backend=args.backend,
    )
    print(json.dumps({"status": "OK", "recommended_action": result["recommended_action"], "claim_level": result["claim_level"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
