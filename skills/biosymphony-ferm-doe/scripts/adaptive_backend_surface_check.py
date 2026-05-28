#!/usr/bin/env python3
"""Validate the public adaptive-backend evaluation surface."""

from __future__ import annotations

from _engine_path import ensure_src_path

ensure_src_path()

from biosymphony_ferm_doe.adaptive_backend_surface import main


if __name__ == "__main__":
    raise SystemExit(main())
