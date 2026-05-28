#!/usr/bin/env python3
"""Validate CSV table contracts for BioSymphony Ferm DoE."""

from __future__ import annotations

from _engine_path import ensure_src_path

ensure_src_path()

from biosymphony_ferm_doe.table_contracts import main


if __name__ == "__main__":
    raise SystemExit(main())
