#!/usr/bin/env python3
"""Generate dry-run Linear issue bodies for a Ferm DoE campaign."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _engine_path import ensure_src_path

ensure_src_path()

from biosymphony_ferm_doe.linear_dry_run import generate_issue_pack


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--pack", action="append", default=[])
    args = parser.parse_args()
    result = generate_issue_pack(Path(args.manifest), Path(args.out), args.pack)
    print(json.dumps({"status": "OK", "issues": len(result["issues"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
