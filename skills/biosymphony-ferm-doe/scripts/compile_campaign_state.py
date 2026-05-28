#!/usr/bin/env python3
"""Compile a campaign manifest into typed Ferm DoE campaign state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _engine_path import ensure_src_path

ensure_src_path()

from biosymphony_ferm_doe.compiler import compile_campaign_state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--mode", action="append", default=[])
    parser.add_argument("--enable-swarm", action="store_true")
    args = parser.parse_args()
    state = compile_campaign_state(Path(args.manifest), Path(args.out), args.mode, enable_swarm=args.enable_swarm)
    print(json.dumps({"status": "OK", "campaign_id": state["campaign_id"], "out": args.out}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
