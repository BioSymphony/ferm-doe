#!/usr/bin/env python3
"""Validate a full Ferm DoE dossier."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _engine_path import ensure_src_path

ensure_src_path()

from biosymphony_ferm_doe.dossier import check_dossier


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--out")
    args = parser.parse_args()
    result = check_dossier(Path(args.path))
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "errors": len(result["errors"])}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
