#!/usr/bin/env python3
"""Validate the BioSymphony Ferm DoE tool registry."""

from __future__ import annotations

from _engine_path import ensure_src_path

ensure_src_path()

from biosymphony_ferm_doe.tool_registry import main


if __name__ == "__main__":
    raise SystemExit(main())
