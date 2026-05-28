"""Generate local Linear issue bodies without calling Linear."""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .compiler import compile_campaign_state
from .io_utils import slug, write_json
from .materialization import simple_yaml_load

REPO_ROOT = Path(__file__).resolve().parents[2]
ISSUE_PACK_ROOT = REPO_ROOT / "packs" / "issue-packs"


DEFAULT_ISSUES = [
    ("W0-01", "Campaign contract and safety gate", []),
    ("W1-01", "Data trust and source audit", ["W0-01"]),
    ("W1-02", "Factor, assay, and feasibility readiness", ["W0-01"]),
    ("W2-01", "Multi-agent design tournament", ["W1-01", "W1-02"]),
    ("W3-01", "first-batch run packet", ["W2-01"]),
    ("W4-01", "follow-up decision rules and provenance", ["W3-01"]),
]


@dataclass(frozen=True)
class LoadedIssue:
    issue_id: str
    title: str
    body: str
    source_file: Path
    wave: str
    depends_on: list[str]
    blocks: list[str]
    artifacts: list[str]


@dataclass(frozen=True)
class LoadedIssuePack:
    pack_id: str
    root: Path
    metadata_path: Path
    metadata: dict[str, Any]
    issues: list[LoadedIssue]


def generate_issue_pack(manifest_path: Path, out_dir: Path, packs: list[str] | None = None) -> dict[str, Any]:
    state = compile_campaign_state(manifest_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    requested_packs = [str(pack) for pack in packs or [] if str(pack).strip()]
    if not requested_packs:
        return _generate_legacy_default_issue_pack(state, out_dir)
    return _generate_loaded_issue_packs(state, out_dir, requested_packs)


def _generate_legacy_default_issue_pack(state: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    requested_packs = ["fermentation-readiness-v0"]
    issues = []
    for issue_id, title, dependencies in DEFAULT_ISSUES:
        filename = f"{issue_id.lower()}-{slug(title)}.md"
        pack_id = _pack_id_for_issue(issue_id)
        body = issue_body(issue_id, title, dependencies, state, pack_id)
        (out_dir / filename).write_text(body)
        issues.append({"issue_id": issue_id, "title": title, "file": filename, "depends_on": dependencies, "pack_id": pack_id})
    graph = {
        "schema_version": 1,
        "graph_kind": "ferm_doe_linear_dry_run",
        "campaign_id": state["campaign_id"],
        "requested_packs": requested_packs,
        "issues": issues,
        "parallelism_policy": {},
        "note": "Dry-run only. No Linear API calls were made.",
    }
    write_json(out_dir / "dependency_graph.json", graph)
    write_json(out_dir / "linear-map.json", {"schema_version": 1, "mappings": {}, "status": "dry_run_uncreated"})
    return graph


def _generate_loaded_issue_packs(state: dict[str, Any], out_dir: Path, requested_packs: list[str]) -> dict[str, Any]:
    loaded_packs = [_load_issue_pack(pack_ref) for pack_ref in requested_packs]
    issues = []
    used_filenames: set[str] = set()
    parallelism_policy: dict[str, Any] = {}
    for issue_pack in loaded_packs:
        pack_parallelism = issue_pack.metadata.get("parallelism_policy")
        if isinstance(pack_parallelism, dict):
            parallelism_policy.update({str(wave): value for wave, value in pack_parallelism.items()})
        for issue in issue_pack.issues:
            filename = _issue_output_filename(issue_pack.pack_id, issue.issue_id, issue.title, used_filenames)
            body = _render_loaded_issue_body(issue_pack, issue, state)
            (out_dir / filename).write_text(body)
            issues.append(
                {
                    "issue_id": issue.issue_id,
                    "title": issue.title,
                    "file": filename,
                    "depends_on": issue.depends_on,
                    "blocks": issue.blocks,
                    "pack_id": issue_pack.pack_id,
                    "wave": issue.wave,
                    "source_file": _display_path(issue.source_file),
                }
            )
    graph = {
        "schema_version": 1,
        "graph_kind": "ferm_doe_linear_dry_run",
        "campaign_id": state["campaign_id"],
        "requested_packs": requested_packs,
        "packs": [_pack_summary(issue_pack) for issue_pack in loaded_packs],
        "issues": issues,
        "parallelism_policy": parallelism_policy,
        "note": "Dry-run only. No Linear API calls were made.",
    }
    write_json(out_dir / "dependency_graph.json", graph)
    write_json(out_dir / "linear-map.json", {"schema_version": 1, "mappings": {}, "status": "dry_run_uncreated"})
    return graph


def _load_issue_pack(pack_ref: str) -> LoadedIssuePack:
    metadata_path = _resolve_pack_metadata_path(pack_ref)
    root = metadata_path.parent
    metadata = _load_pack_metadata(metadata_path)
    if not isinstance(metadata, dict):
        raise ValueError(f"issue pack metadata must be an object: {metadata_path}")
    pack_id = str(metadata.get("pack_id") or root.name)
    if metadata.get("pack_type") not in {None, "issue_pack"}:
        raise ValueError(f"unsupported pack_type for {pack_id}: {metadata.get('pack_type')}")
    raw_issues = metadata.get("issues")
    if not isinstance(raw_issues, list) or not raw_issues:
        raise ValueError(f"issue pack {pack_id} must define at least one issue")
    dependency_map = _issue_dependency_map(raw_issues)
    issues: list[LoadedIssue] = []
    for raw_issue in raw_issues:
        if not isinstance(raw_issue, dict):
            raise ValueError(f"issue entries in {pack_id} must be objects")
        issue_id = str(raw_issue.get("id") or raw_issue.get("issue_id") or "").strip()
        if not issue_id:
            raise ValueError(f"issue entry in {pack_id} is missing id")
        raw_file = str(raw_issue.get("file") or raw_issue.get("body_template_path") or "").strip()
        if not raw_file:
            raise ValueError(f"issue {issue_id} in {pack_id} is missing file")
        source_file = _resolve_issue_file(root, raw_file)
        body = source_file.read_text()
        title = str(raw_issue.get("title") or _extract_markdown_title(body) or _title_from_id(issue_id))
        wave = str(raw_issue.get("wave") or "").strip()
        blocks = [str(item) for item in raw_issue.get("blocks", [])]
        dependencies = [str(item) for item in raw_issue.get("depends_on", dependency_map.get(issue_id, []))]
        issues.append(
            LoadedIssue(
                issue_id=issue_id,
                title=title,
                body=body,
                source_file=source_file,
                wave=wave,
                depends_on=dependencies,
                blocks=blocks,
                artifacts=_extract_expected_artifacts(body),
            )
        )
    return LoadedIssuePack(pack_id=pack_id, root=root, metadata_path=metadata_path, metadata=metadata, issues=issues)


def _resolve_pack_metadata_path(pack_ref: str) -> Path:
    candidate = Path(pack_ref).expanduser()
    if candidate.is_absolute() or candidate.exists() or "/" in pack_ref:
        if not candidate.is_absolute():
            candidate = (Path.cwd() / candidate).resolve()
        if candidate.is_dir():
            return _find_pack_metadata(candidate)
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(f"issue pack path does not exist: {pack_ref}")
    pack_dir = ISSUE_PACK_ROOT / pack_ref
    if not pack_dir.exists():
        raise FileNotFoundError(f"unknown issue pack {pack_ref!r}; expected {pack_dir}")
    return _find_pack_metadata(pack_dir)


def _find_pack_metadata(pack_dir: Path) -> Path:
    for filename in ("pack.yaml", "pack.yml", "pack.json"):
        path = pack_dir / filename
        if path.exists():
            return path
    raise FileNotFoundError(f"no pack.yaml, pack.yml, or pack.json found in {pack_dir}")


def _load_pack_metadata(path: Path) -> Any:
    text = path.read_text()
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        yaml = importlib.import_module("yaml")
    except ImportError:
        return simple_yaml_load(text)
    return yaml.safe_load(text)


def _issue_dependency_map(raw_issues: list[Any]) -> dict[str, list[str]]:
    dependencies: dict[str, list[str]] = {}
    for raw_issue in raw_issues:
        if not isinstance(raw_issue, dict):
            continue
        issue_id = str(raw_issue.get("id") or raw_issue.get("issue_id") or "").strip()
        if not issue_id:
            continue
        dependencies.setdefault(issue_id, [])
        for blocked_id in raw_issue.get("blocks", []) or []:
            blocked = str(blocked_id).strip()
            if blocked:
                dependencies.setdefault(blocked, []).append(issue_id)
    return dependencies


def _resolve_issue_file(pack_root: Path, raw_file: str) -> Path:
    source_file = (pack_root / raw_file).resolve()
    root = pack_root.resolve()
    if not source_file.is_relative_to(root):
        raise ValueError(f"issue file escapes pack root: {raw_file}")
    if not source_file.exists():
        raise FileNotFoundError(f"issue file does not exist: {source_file}")
    return source_file


def _issue_output_filename(pack_id: str, issue_id: str, title: str, used_filenames: set[str]) -> str:
    base = f"{slug(issue_id)}-{slug(title)}.md"
    candidates = [base, f"{slug(pack_id)}-{base}"]
    for candidate in candidates:
        if candidate not in used_filenames:
            used_filenames.add(candidate)
            return candidate
    index = 2
    while True:
        candidate = f"{slug(pack_id)}-{slug(issue_id)}-{index}-{slug(title)}.md"
        if candidate not in used_filenames:
            used_filenames.add(candidate)
            return candidate
        index += 1


def _render_loaded_issue_body(issue_pack: LoadedIssuePack, issue: LoadedIssue, state: dict[str, Any]) -> str:
    body = issue.body.rstrip()
    if "<!-- symphony-outcome" not in body:
        body = f"{body}\n\n{_loaded_issue_outcome(issue_pack.pack_id, issue, state)}".rstrip()
    return body + "\n"


def _loaded_issue_outcome(pack_id: str, issue: LoadedIssue, state: dict[str, Any]) -> str:
    artifacts = issue.artifacts or ["pending"]
    artifacts_yaml = "\n".join(f"  - {artifact}" for artifact in artifacts)
    wave_line = f"wave: {issue.wave}" if issue.wave else "wave: pending"
    return f"""<!-- symphony-outcome
outcome_version: 1
status: pending
pack_id: {pack_id}
pack_issue_id: {issue.issue_id}
{wave_line}
artifacts:
{artifacts_yaml}
validation_summary: pending
compute_profile: {state.get('compute_policy', {}).get('default_profile', 'local-stdlib')}
remote_launch: not_requested
claim_level: pending
scientific_caveats:
  - pending
suggested_action: pending
-->"""


def _extract_markdown_title(body: str) -> str | None:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped[2:].strip()
    return None


def _extract_expected_artifacts(body: str) -> list[str]:
    artifacts: list[str] = []
    in_section = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped.lower() == "## expected artifacts"
            continue
        if not in_section or not stripped.startswith("- "):
            continue
        artifact = stripped[2:].strip().strip("`")
        if " - " in artifact:
            artifact = artifact.split(" - ", 1)[0].strip().strip("`")
        if artifact:
            artifacts.append(artifact)
    return artifacts


def _title_from_id(issue_id: str) -> str:
    return issue_id.replace("-", " ").replace("_", " ").title()


def _pack_summary(issue_pack: LoadedIssuePack) -> dict[str, Any]:
    metadata = issue_pack.metadata
    summary: dict[str, Any] = {
        "pack_id": issue_pack.pack_id,
        "name": metadata.get("name", issue_pack.pack_id),
        "pack_type": metadata.get("pack_type", "issue_pack"),
        "schema_version": metadata.get("schema_version"),
        "source": _display_path(issue_pack.metadata_path),
        "issue_count": len(issue_pack.issues),
    }
    for key in ("activation_policy", "parallelism_policy", "labels"):
        if key in metadata:
            summary[key] = metadata[key]
    return summary


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _pack_id_for_issue(issue_id: str) -> str:
    if issue_id.startswith("DOE-"):
        return "doe-parity-v0"
    if issue_id.startswith("AW2-"):
        return "adaptive-wave2-assay-power-v0"
    return "ferm-doe-campaign-v1"


def issue_body(issue_id: str, title: str, dependencies: list[str], state: dict[str, Any], pack_id: str) -> str:
    touched = "ferm-doe-dossier/"
    return f"""# {title}

## Summary

Campaign `{state['campaign_id']}` dry-run issue `{issue_id}` for BioSymphony Ferm DoE.

## Inputs

- `campaign_state.json`
- `ferm-doe-dossier/`

## Acceptance Criteria

- Required artifacts for this wave are present.
- `dossier_check.py` and `ferm_doe_contract_self_check.py` pass before success is claimed.
- Caveats and readiness status are recorded.
- Compute profile and remote-launch status are stated when remote work is in scope.
- No private process data or secrets are copied into the issue.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/dossier_check.py ferm-doe-dossier
python3 skills/biosymphony-ferm-doe/scripts/ferm_doe_contract_self_check.py ferm-doe-dossier
```

## Touched Areas

- `{touched}`

## Dependencies

{chr(10).join(f"- {dep}" for dep in dependencies) if dependencies else "- None"}

## Risk Notes

Do not store secrets, private strain data, customer batch records, unpublished sequences, or confidential media formulations in Linear.

<!-- symphony:schema
schema_version: 1
pack_id: {pack_id}
pack_issue_id: {issue_id}
touched_areas:
  - {touched}
complexity: medium
-->

<!-- symphony-outcome
outcome_version: 1
status: pending
pack_id: {pack_id}
pack_issue_id: {issue_id}
artifacts:
  - ferm-doe-dossier/
validation_summary: pending
compute_profile: {state.get('compute_policy', {}).get('default_profile', 'local-stdlib')}
remote_launch: not_requested
claim_level: pending
scientific_caveats:
  - pending
suggested_action: pending
-->
"""
