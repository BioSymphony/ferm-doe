#!/usr/bin/env python3
"""Scan release material for private BioSymphony Ferm DoE deployment markers."""

from __future__ import annotations

from _engine_path import ensure_src_path

ensure_src_path()

from biosymphony_ferm_doe.public_release import main


if __name__ == "__main__":
    raise SystemExit(main())
