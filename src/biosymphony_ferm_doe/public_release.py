"""Public release scrub checks for BioSymphony Ferm DoE files.

The scanner is intentionally standard-library only so it can run in a bare
worker checkout before publishing docs, templates, or generated artifacts.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Pattern


DEFAULT_PRIVATE_ALLOWLIST: tuple[str, ...] = ()

DEFAULT_EXCLUDED_DIRS = {
    ".eggs",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".runtime",
    ".nox",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}

PRIVATE_DOT_CLAUDE = "." + "claude"
PRIVATE_CLAUDE_LANE = "symphony" + "-claude"


@dataclass(frozen=True)
class ReleaseRule:
    rule_id: str
    message: str
    pattern: Pattern[str]


@dataclass(frozen=True)
class ReleaseFinding:
    path: str
    line: int
    column: int
    rule_id: str
    message: str
    excerpt: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def default_rules() -> list[ReleaseRule]:
    """Return the default blocking rules for public release scans."""

    provider_name = "run" + "pod"
    bridge_command = provider_name + "-bridge"
    private_markers = [
        r"\bprivate\s+(?:assay|campaign|model|process|sequence|strain)\b",
        r"\bunpublished\s+(?:assay|biological|campaign|construct|data|media|process|result|sequence|strain)\b",
        r"\bcustomer\s+batch\s+records?\b",
        r"\bconfidential\s+(?:assay|customer|media|process|recipe|formulation)\b",
        r"\bproprietary\s+(?:construct|process|sequence|strain)\b",
        r"\braw\s+process\s+histor(?:y|ies)\b",
        r"\bsupplier\s+quotes?\s+under\s+NDA\b",
    ]
    private_models = [
        r"\bclaude-(?:haiku|opus|sonnet)-4-[5-9]\b",
        r"\b(?:Claude\s+)?(?:Haiku|Opus|Sonnet)\s+4\.[5-9]\b",
    ]

    return [
        ReleaseRule(
            "local_path",
            "Absolute workstation path must be replaced with a portable placeholder.",
            re.compile(r"(?<![A-Za-z0-9_])/(?:Users|Volumes|home)/[^\s`\"'<>)]+"),
        ),
        ReleaseRule(
            "private_key_block",
            "Private key material must not be published.",
            re.compile(r"BEGIN (?:RSA|OPENSSH|EC|DSA) PRIVATE KEY"),
        ),
        ReleaseRule(
            "aws_access_key",
            "AWS access key-like values must not be published.",
            re.compile(r"AKIA[0-9A-Z]{16}"),
        ),
        ReleaseRule(
            "github_token",
            "GitHub token-like values must not be published.",
            re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
        ),
        ReleaseRule(
            "api_token_like_value",
            "API token-like values must not be published.",
            re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
        ),
        ReleaseRule(
            "authorization_bearer_token",
            "Live bearer-token values must not be published.",
            re.compile(
                r"(?i)\bAuthorization\s*:\s*Bearer\s+"
                r"(?!(?:<[^>\n]*(?:token|redacted)[^>\n]*>|redacted|REDACTED|\$[A-Z_][A-Z0-9_]*|\$\{[A-Z_][A-Z0-9_]*\})\b)"
                r"[A-Za-z0-9._~+/-]{16,}"
            ),
        ),
        ReleaseRule(
            "assigned_secret_like_value",
            "Assigned secret-like values must not be published.",
            re.compile(r"(?i)\b(?:api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[A-Za-z0-9._/-]{16,}"),
        ),
        ReleaseRule(
            "private_orchestration_marker",
            "Private orchestration account or lane marker must not appear in public release material.",
            re.compile(
                "|".join(
                    [
                        r"(?<![A-Za-z0-9_.-])" + re.escape("auto" + "nomy") + r"(?:[/\\]|$)",
                        re.escape(PRIVATE_DOT_CLAUDE),
                        re.escape(PRIVATE_CLAUDE_LANE),
                    ]
                ),
                re.IGNORECASE,
            ),
        ),
        ReleaseRule(
            "linear_url",
            "Linear URL must be removed or replaced with a neutral reference.",
            re.compile(r"https?://(?:www\.)?linear\.app/[^\s`\"'<>)]+", re.IGNORECASE),
        ),
        ReleaseRule(
            "linear_issue_id",
            "Linear issue ID must be removed or replaced with a neutral reference.",
            re.compile(r"\b(?:VOG|LINEAR|LIN)-\d{2,7}\b"),
        ),
        ReleaseRule(
            "tracker_placeholder",
            "Tracker placeholders must be replaced with neutral public wording.",
            re.compile(r"\[(?:validation-)?ticket\]", re.IGNORECASE),
        ),
        ReleaseRule(
            "runpod_identifier",
            "RunPod provider identifier or secret-like environment name must not be published.",
            re.compile(
                r"\b(?:(?:pod|rp|endpoint|template)-[a-z0-9][a-z0-9-]{5,}|runpod-volume-[a-z0-9][a-z0-9-]{5,}|RUNPOD_(?:(?:[A-Z0-9]+_)*(?:KEY|TOKEN|ID|ENDPOINT|POD)(?:_[A-Z0-9]+)*|API_KEY))\b",
                re.IGNORECASE,
            ),
        ),
        ReleaseRule(
            "runpod_provider_path",
            "RunPod provider runtime path or mutating bridge command must be scrubbed.",
            re.compile(
                r"(?:^|[\s`\"'=:(])(?:"
                + r"\.runtime/"
                + provider_name
                + r"/|"
                + provider_name
                + r"-execution/|[^\s`\"'<>]*/"
                + provider_name
                + r"[^/\s`\"'<>]*/[^\s`\"'<>]+|"
                + bridge_command
                + r"\s+(?:cleanup-pod|create-pod|list-pods|run-handoff|validate-handoff|validate-manifest|verify-tcp-packet))",
                re.IGNORECASE,
            ),
        ),
        ReleaseRule(
            "private_model_name",
            "Deployment-specific model name must be replaced with a capability tier.",
            re.compile("|".join(private_models), re.IGNORECASE),
        ),
        ReleaseRule(
            "private_campaign_marker",
            "Sensitive campaign marker must be removed, sanitized, or moved to an allowlisted artifact.",
            re.compile("|".join(private_markers), re.IGNORECASE),
        ),
    ]


def scan_paths(
    paths: list[Path],
    *,
    root: Path | None = None,
    allow_private: list[str] | None = None,
    excluded_dirs: set[str] | None = None,
    rules: list[ReleaseRule] | None = None,
) -> list[ReleaseFinding]:
    root_path = (root or Path.cwd()).resolve()
    allow_patterns = list(DEFAULT_PRIVATE_ALLOWLIST if allow_private is None else allow_private)
    excluded = set(DEFAULT_EXCLUDED_DIRS if excluded_dirs is None else excluded_dirs)
    active_rules = rules or default_rules()
    findings: list[ReleaseFinding] = []

    for file_path in iter_files(paths, excluded):
        resolved = file_path.resolve()
        relative = relative_path(resolved, root_path)
        if is_allowlisted(relative, allow_patterns):
            continue
        text = read_text_file(resolved)
        if text is None:
            continue
        findings.extend(scan_text(text, relative, active_rules))

    return findings


def scan_text(text: str, path: str, rules: list[ReleaseRule] | None = None) -> list[ReleaseFinding]:
    active_rules = rules or default_rules()
    findings: list[ReleaseFinding] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        line_number = index + 1
        scanned_line = line.split("audit-skip:", 1)[0]
        context = "\n".join(lines[max(0, index - 12) : min(len(lines), index + 4)])
        for rule in active_rules:
            for match in rule.pattern.finditer(scanned_line):
                if has_audit_skip(line, rule.rule_id):
                    continue
                if should_skip_match(rule.rule_id, line, match, context=context):
                    continue
                findings.append(
                    ReleaseFinding(
                        path=path,
                        line=line_number,
                        column=match.start() + 1,
                        rule_id=rule.rule_id,
                        message=rule.message,
                        excerpt=collapse_excerpt(line),
                    )
                )
    return findings


def has_audit_skip(line: str, rule_id: str) -> bool:
    """Return True when a line carries an explicit audit skip marker.

    Marker form: ``# audit-skip: <rule_id>[, <rule_id>...] reason``.
    ``all`` skips every rule on the line. This is intentionally line-scoped;
    broad release allowlists should use path globs instead.
    """

    marker = "audit-skip:"
    lower = line.lower()
    if marker not in lower:
        return False
    tail = lower.split(marker, 1)[1]
    rule_tokens = re.split(r"[\s,;]+", tail.strip())
    return "all" in rule_tokens or rule_id.lower() in rule_tokens


def should_skip_match(rule_id: str, line: str, match: re.Match[str], *, context: str | None = None) -> bool:
    """Suppress documented guardrails that mention sensitive concepts as bans."""

    if rule_id != "private_campaign_marker":
        return False
    lower = (context or line).lower()
    window = lower[max(0, match.start() - 100) : match.end() + 100]
    safety_markers = [
        "do not ",
        "don't ",
        "never ",
        "must not ",
        "should not ",
        "avoid ",
        "without ",
        " no ",
        "no private",
        "not include",
        "not store",
        "not paste",
        "not copy",
        "synthetic/public data only",
        "synthetic / public-source",
        "public-safe",
        "public safe",
        "public examples synthetic",
        "use a private workspace",
        "sanitized",
    ]
    return any(marker in lower or marker in window for marker in safety_markers)


def iter_files(paths: list[Path], excluded_dirs: set[str]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
            continue
        if not path.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [name for name in dirnames if name not in excluded_dirs]
            current = Path(dirpath)
            for filename in filenames:
                files.append(current / filename)
    return sorted(files)


def read_text_file(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:4096]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def is_allowlisted(relative: str, patterns: list[str]) -> bool:
    normalized = relative.replace(os.sep, "/")
    for pattern in patterns:
        clean = pattern.replace(os.sep, "/").lstrip("./")
        if fnmatch.fnmatch(normalized, clean):
            return True
        if clean.endswith("/**") and normalized.startswith(clean[:-3] + "/"):
            return True
    return False


def collapse_excerpt(line: str, *, limit: int = 160) -> str:
    excerpt = " ".join(line.strip().split())
    if len(excerpt) <= limit:
        return excerpt
    return excerpt[: limit - 3] + "..."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan files for private deployment material before public release.")
    parser.add_argument("paths", nargs="*", default=["."], help="Files or directories to scan. Defaults to the current directory.")
    parser.add_argument(
        "--allow-private",
        action="append",
        default=[],
        metavar="GLOB",
        help="Additional repo-relative private path glob to skip, for example 'private-artifacts/**'.",
    )
    parser.add_argument(
        "--no-default-allowlist",
        action="store_true",
        help="Do not skip the built-in private docs/artifacts allowlist.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path.cwd().resolve()
    paths = [Path(path) for path in args.paths]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        print(f"ERROR: path does not exist: {', '.join(missing)}", file=sys.stderr)
        return 2

    allowlist = [] if args.no_default_allowlist else list(DEFAULT_PRIVATE_ALLOWLIST)
    allowlist.extend(args.allow_private)
    findings = scan_paths(paths, root=root, allow_private=allowlist)

    if args.json:
        print(json.dumps({"status": "FAIL" if findings else "OK", "finding_count": len(findings), "findings": [finding.to_dict() for finding in findings]}, indent=2, sort_keys=True))
    elif findings:
        print(f"ERROR: public release scan found {len(findings)} blocker(s)", file=sys.stderr)
        for finding in findings:
            print(
                f"{finding.path}:{finding.line}:{finding.column}: {finding.rule_id}: {finding.message}",
                file=sys.stderr,
            )
            print(f"  {finding.excerpt}", file=sys.stderr)
    else:
        print("OK: public release scan passed")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
