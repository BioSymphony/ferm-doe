"""Optional reference DOE utilities for BioSymphony Ferm DoE."""

from __future__ import annotations

__all__ = [
    "SUPPORTED_BACKENDS",
]

SUPPORTED_BACKENDS = ["auto", "stdlib", "numpy", "scipy", "pydoe", "bofire", "botorch"]
