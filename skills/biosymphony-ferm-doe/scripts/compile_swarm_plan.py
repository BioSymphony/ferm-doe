#!/usr/bin/env python3
"""Compile Scientific Swarm planning artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _engine_path import ensure_src_path

ensure_src_path()

from biosymphony_ferm_doe.swarm import compile_swarm_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--evidence-table", action="append", default=[])
    args = parser.parse_args()
    result = compile_swarm_plan(Path(args.manifest), Path(args.out), force=True, evidence_tables=[Path(path) for path in args.evidence_table])
    print(json.dumps({"status": "OK", "campaign_id": result["campaign_id"], "artifacts": result["artifact_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
