"""Path helper for repo-local engine scripts."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_src_path() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
