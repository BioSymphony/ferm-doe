"""Check local Markdown links without network access."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".runtime",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "app://")


@dataclass(frozen=True)
class MissingLink:
    path: Path
    line: int
    target: str

    def render(self, root: Path) -> str:
        try:
            rel = self.path.relative_to(root)
        except ValueError:
            rel = self.path
        return f"{rel}:{self.line}: missing {self.target}"


def check_markdown_links(paths: list[Path], *, root: Path, excluded_dirs: set[str]) -> list[MissingLink]:
    missing: list[MissingLink] = []
    for path in iter_markdown_files(paths, excluded_dirs):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in LINK_RE.finditer(line):
                target = normalize_target(match.group(1))
                if should_skip_target(target):
                    continue
                candidate = (path.parent / target).resolve()
                try:
                    candidate.relative_to(root)
                except ValueError:
                    continue
                if not candidate.exists():
                    missing.append(MissingLink(path=path, line=line_number, target=match.group(1)))
    return missing


def iter_markdown_files(paths: list[Path], excluded_dirs: set[str]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix.lower() == ".md":
            files.append(path)
            continue
        if not path.is_dir():
            continue
        for child in path.rglob("*.md"):
            if any(part in excluded_dirs for part in child.parts):
                continue
            files.append(child)
    return sorted({path.resolve() for path in files})


def normalize_target(raw: str) -> str:
    target = raw.split("#", 1)[0].strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    return target


def should_skip_target(target: str) -> bool:
    return not target or target.startswith(EXTERNAL_PREFIXES)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local Markdown links.")
    parser.add_argument("paths", nargs="*", default=["."], help="Files or directories to scan.")
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Directory name to exclude. May be passed more than once.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = Path.cwd().resolve()
    excluded_dirs = set(DEFAULT_EXCLUDED_DIRS)
    excluded_dirs.update(args.exclude_dir)
    paths = [Path(path).resolve() for path in args.paths]
    missing = check_markdown_links(paths, root=root, excluded_dirs=excluded_dirs)
    if missing:
        for item in missing:
            print(item.render(root))
        print(f"FAIL: {len(missing)} missing local Markdown link(s)")
        return 1
    print("OK: local Markdown links resolved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
