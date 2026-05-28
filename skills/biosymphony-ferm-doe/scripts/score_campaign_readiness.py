#!/usr/bin/env python3
"""Score Ferm DoE campaign readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _engine_path import ensure_src_path

ensure_src_path()

from biosymphony_ferm_doe.readiness import score_campaign_readiness


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = score_campaign_readiness(Path(args.manifest), out_path=Path(args.out))
    print(json.dumps({"status": result["status"], "score": result["score"], "out": args.out}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
