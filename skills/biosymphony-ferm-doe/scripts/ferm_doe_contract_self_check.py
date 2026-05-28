#!/usr/bin/env python3
"""Run the joined artifact and claim self-check for a Ferm DoE dossier."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _engine_path import ensure_src_path

ensure_src_path()

from biosymphony_ferm_doe.contract import contract_self_check


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--require-execution", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args()
    result = contract_self_check(Path(args.path), require_execution=args.require_execution, write_outputs=True)
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "errors": len(result["errors"]), "claim_level": result["claim_level"]}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
