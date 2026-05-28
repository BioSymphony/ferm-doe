"""Dossier artifact hashes and minimal RO-Crate metadata."""

from __future__ import annotations

import hashlib
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io_utils import write_json


HASH_MANIFEST = "artifact_hashes.json"
RO_CRATE_METADATA = "ro-crate-metadata.json"
PROVENANCE_ARTIFACTS = [HASH_MANIFEST, RO_CRATE_METADATA]


def write_dossier_provenance(
    out_dir: Path,
    state: dict[str, Any],
    *,
    source_manifest_path: Path | None = None,
    private_public_classification: str = "public_or_synthetic_demo",
) -> dict[str, Any]:
    """Write hash and RO-Crate sidecars for a compiled dossier."""

    hashes = build_artifact_hashes(out_dir, exclude={HASH_MANIFEST, RO_CRATE_METADATA})
    hash_payload = {
        "schema_version": 1,
        "artifact_hash_kind": "ferm_doe_dossier_sha256_manifest",
        "campaign_id": state.get("campaign_id"),
        "generated_at": utc_now(),
        "algorithm": "sha256",
        "artifact_count": len(hashes),
        "artifacts": hashes,
    }
    write_json(out_dir / HASH_MANIFEST, hash_payload)

    crate = build_ro_crate_metadata(
        out_dir,
        state,
        hash_payload,
        source_manifest_path=source_manifest_path,
        private_public_classification=private_public_classification,
    )
    write_json(out_dir / RO_CRATE_METADATA, crate)
    return {
        "hash_manifest": HASH_MANIFEST,
        "ro_crate_metadata": RO_CRATE_METADATA,
        "artifact_count": len(hashes),
    }


def build_artifact_hashes(out_dir: Path, *, exclude: set[str] | None = None) -> list[dict[str, Any]]:
    excluded = set(exclude or set())
    artifacts = []
    for path in sorted(item for item in out_dir.rglob("*") if item.is_file()):
        relative_path = path.relative_to(out_dir).as_posix()
        if path.name in excluded or relative_path in excluded:
            continue
        artifacts.append(
            {
                "path": relative_path,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "media_type": media_type(path),
            }
        )
    return artifacts


def verify_artifact_hashes(out_dir: Path) -> dict[str, Any]:
    manifest_path = out_dir / HASH_MANIFEST
    errors: list[str] = []
    warnings: list[str] = []
    if not manifest_path.exists():
        return {
            "schema_version": 1,
            "artifact_hash_check_kind": "ferm_doe_dossier_sha256_check",
            "status": "FAIL",
            "checked_artifacts": 0,
            "errors": [f"missing {HASH_MANIFEST}"],
            "warnings": [],
        }
    try:
        import json

        manifest = json.loads(manifest_path.read_text())
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "schema_version": 1,
            "artifact_hash_check_kind": "ferm_doe_dossier_sha256_check",
            "status": "FAIL",
            "checked_artifacts": 0,
            "errors": [f"invalid {HASH_MANIFEST}: {exc}"],
            "warnings": [],
        }

    artifacts = manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        artifacts = []
        errors.append(f"{HASH_MANIFEST} artifacts must be a list")
    checked_paths: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict):
            errors.append(f"{HASH_MANIFEST} contains a non-object artifact entry")
            continue
        raw_path = str(item.get("path") or "")
        if not raw_path:
            errors.append(f"{HASH_MANIFEST} contains an artifact without path")
            continue
        if Path(raw_path).is_absolute() or ".." in Path(raw_path).parts:
            errors.append(f"{HASH_MANIFEST} contains unsafe artifact path: {raw_path}")
            continue
        target = out_dir / raw_path
        checked_paths.add(raw_path)
        if not target.exists():
            errors.append(f"hash manifest references missing artifact: {raw_path}")
            continue
        if not target.is_file():
            errors.append(f"hash manifest references non-file artifact: {raw_path}")
            continue
        expected_sha = str(item.get("sha256") or "")
        actual_sha = sha256_file(target)
        if expected_sha != actual_sha:
            errors.append(f"sha256 mismatch for {raw_path}")
        expected_size = item.get("size_bytes")
        if expected_size is not None and int(expected_size) != target.stat().st_size:
            errors.append(f"size mismatch for {raw_path}")

    current_paths = {
        path.relative_to(out_dir).as_posix()
        for path in out_dir.rglob("*")
        if path.is_file() and path.name not in set(PROVENANCE_ARTIFACTS)
    }
    for extra_path in sorted(current_paths - checked_paths):
        warnings.append(f"file is not listed in {HASH_MANIFEST}: {extra_path}")

    return {
        "schema_version": 1,
        "artifact_hash_check_kind": "ferm_doe_dossier_sha256_check",
        "status": "FAIL" if errors else "PASS",
        "checked_artifacts": len(checked_paths),
        "errors": errors,
        "warnings": warnings,
    }


def build_ro_crate_metadata(
    out_dir: Path,
    state: dict[str, Any],
    hash_payload: dict[str, Any],
    *,
    source_manifest_path: Path | None,
    private_public_classification: str,
) -> dict[str, Any]:
    artifact_by_path = {item["path"]: item for item in hash_payload.get("artifacts", [])}
    graph: list[dict[str, Any]] = [
        {
            "@id": RO_CRATE_METADATA,
            "@type": "CreativeWork",
            "about": {"@id": "./"},
            "conformsTo": [
                {"@id": "https://w3id.org/ro/crate/1.2"},
                {"@id": "https://w3id.org/ro/wfrun/process/0.5"},
            ],
        },
        {
            "@id": "https://w3id.org/ro/crate/1.2",
            "@type": ["CreativeWork", "Profile"],
            "name": "RO-Crate 1.2",
            "version": "1.2",
        },
        {
            "@id": "https://w3id.org/ro/wfrun/process/0.5",
            "@type": ["CreativeWork", "Profile"],
            "name": "Process Run Crate",
            "version": "0.5",
            "url": "https://w3id.org/ro/wfrun/process/0.5",
        },
        {
            "@id": "./",
            "@type": "Dataset",
            "name": f"BioSymphony Ferm DoE dossier: {state.get('campaign_id', 'campaign')}",
            "identifier": str(state.get("campaign_id") or ""),
            "description": "Compiled BioSymphony fermentation DoE planning dossier with artifact hashes and claim-boundary metadata.",
            "datePublished": utc_now(),
            "license": str(state.get("license") or "unspecified"),
            "privatePublicClassification": private_public_classification,
            "conformsTo": [
                {"@id": "https://w3id.org/ro/crate/1.2"},
                {"@id": "https://w3id.org/ro/wfrun/process/0.5"},
            ],
            "hasPart": [{"@id": item["path"]} for item in hash_payload.get("artifacts", [])] + [{"@id": HASH_MANIFEST}],
            "sourceManifest": str(source_manifest_path) if source_manifest_path else "",
        },
    ]
    for path_name, artifact in artifact_by_path.items():
        graph.append(
            {
                "@id": path_name,
                "@type": "File",
                "name": path_name,
                "encodingFormat": artifact.get("media_type", "application/octet-stream"),
                "contentSize": artifact.get("size_bytes", 0),
                "sha256": artifact.get("sha256", ""),
            }
        )
    graph.append(
        {
            "@id": HASH_MANIFEST,
            "@type": "File",
            "name": HASH_MANIFEST,
            "encodingFormat": "application/json",
            "description": "Machine-readable SHA-256 manifest for dossier files.",
            "contentSize": (out_dir / HASH_MANIFEST).stat().st_size if (out_dir / HASH_MANIFEST).exists() else 0,
            "sha256": sha256_file(out_dir / HASH_MANIFEST) if (out_dir / HASH_MANIFEST).exists() else "",
        }
    )
    return {
        "@context": "https://w3id.org/ro/crate/1.2/context",
        "@graph": graph,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def media_type(path: Path) -> str:
    if path.suffix == ".md":
        return "text/markdown"
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
