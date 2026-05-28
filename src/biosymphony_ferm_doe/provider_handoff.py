"""Provider handoff contract generation for remote execution lanes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


# Default placeholder for the provider bridge binary. Callers should supply
# the actual command name appropriate to their deployment. Absolute paths are
# deliberately not written into the public handoff artifact.
DEFAULT_PROVIDER_BRIDGE = "<provider_bridge_bin>"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def portable_path(path: Path) -> str:
    """Return a repository-relative path, or a placeholder for external paths."""

    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return f"<external_artifact_root>/{path.name}"


def manifest_provider_name(manifest: dict[str, Any]) -> str:
    provider = manifest.get("provider")
    if isinstance(provider, str) and provider.strip():
        return provider.strip()
    if isinstance(provider, dict):
        for key in ("name", "kind", "provider"):
            value = provider.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "external-provider"


def manifest_resource_name(manifest: dict[str, Any], fallback: str) -> str:
    provider_config = manifest.get("provider")
    if isinstance(provider_config, dict):
        for key in ("name", "resource_name", "resource_name_prefix"):
            value = provider_config.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    runpod = manifest.get("runpod")
    if isinstance(runpod, dict):
        for key in ("name", "pod_name"):
            value = runpod.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    worker = manifest.get("worker_coordination")
    if isinstance(worker, dict):
        value = worker.get("resource_name_prefix")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def manifest_budget(manifest: dict[str, Any]) -> float | int | None:
    budget = manifest.get("budget")
    if isinstance(budget, dict):
        value = budget.get("max_estimated_cost_usd")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    return None


def expected_artifact_paths(launch_bundle: dict[str, Any], launch_manifest: dict[str, Any]) -> list[str]:
    manifest_artifacts = launch_manifest.get("expected_artifacts")
    if isinstance(manifest_artifacts, list) and manifest_artifacts:
        paths: list[str] = []
        for artifact in manifest_artifacts:
            if isinstance(artifact, dict) and isinstance(artifact.get("path"), str):
                paths.append(artifact["path"])
            elif isinstance(artifact, str):
                paths.append(artifact)
        if paths:
            egress = launch_manifest.get("artifact_egress")
            if isinstance(egress, dict) and isinstance(egress.get("archive_path"), str):
                paths.append(egress["archive_path"])
            return paths

    bundle_artifacts = launch_bundle.get("expected_outputs")
    paths = []
    if isinstance(bundle_artifacts, list):
        for artifact in bundle_artifacts:
            if isinstance(artifact, dict) and isinstance(artifact.get("path"), str):
                paths.append(artifact["path"])
            elif isinstance(artifact, str):
                paths.append(artifact)
    return paths


def prepare_provider_handoff(
    launch_bundle_path: Path,
    out_dir: Path,
    *,
    launch_manifest_path: Path,
    provider_bridge: str = DEFAULT_PROVIDER_BRIDGE,
    reason: str = "worker_provider_api_unreachable",
    tracker_issue: str | None = None,
    runpod_bridge: str | None = None,
    linear_issue: str | None = None,
) -> dict[str, Any]:
    """Generate a provider handoff artifact for orchestrator-side remote mutation.

    The handoff intentionally stores commands and artifact expectations, not
    provider credentials. It lets a worker stop after local validation while a
    trusted orchestrator performs create/verify/cleanup.

    Pass ``provider_bridge`` as the command name that the orchestrator should
    invoke. The default value is a placeholder and not a valid command.
    """

    launch_bundle = load_json(launch_bundle_path)
    launch_manifest = load_json(launch_manifest_path)
    bridge_command = runpod_bridge or provider_bridge
    provider_name = manifest_provider_name(launch_manifest)
    run_id = str(launch_manifest.get("run_id") or launch_bundle.get("run_id") or "provider-handoff")
    resource_prefix = manifest_resource_name(launch_manifest, fallback=run_id)
    budget = manifest_budget(launch_manifest)
    max_spend = f" --max-spend-usd {budget:g}" if isinstance(budget, (int, float)) else ""
    runtime_dir = f".runtime/provider/{run_id}"
    handoff_path = out_dir / "provider_handoff.json"
    launch_bundle_ref = portable_path(launch_bundle_path)
    launch_manifest_ref = portable_path(launch_manifest_path)
    handoff_ref = portable_path(handoff_path)
    tcp_port = 8000

    access = launch_manifest.get("access")
    if isinstance(access, dict):
        provider_block = launch_manifest.get("provider") if isinstance(launch_manifest.get("provider"), dict) else {}
        legacy_runpod_block = launch_manifest.get("runpod") if isinstance(launch_manifest.get("runpod"), dict) else {}
        ports_required = provider_block.get("ports") or legacy_runpod_block.get("ports") or []
        if isinstance(ports_required, list):
            for port in ports_required:
                text = str(port)
                if text.endswith("/tcp"):
                    try:
                        tcp_port = int(text.split("/", 1)[0])
                    except ValueError:
                        tcp_port = 8000
                    break

    handoff = {
        "schema_version": 1,
        "sidecar_kind": "provider_handoff",
        "handoff_kind": "external_provider_handoff",
        "id": f"provider-handoff-{run_id}",
        "name": f"Provider handoff for {run_id}",
        "interface": {
            "name": "biosymphony-ferm-doe.sidecar",
            "version": 1,
            "slots": ["provider_handoff"],
        },
        "provider": provider_name,
        "status": "ready_for_orchestrator" if launch_manifest.get("remote_launch_allowed") is True else "blocked",
        "run_id": run_id,
        "resource_name_prefix": resource_prefix,
        "claim_level": "remote_artifact_execution_only",
        "handoff_reason": reason,
        "reason": reason,
        "tracker_issue": tracker_issue or linear_issue or "",
        "remote_execution_by": "orchestrator",
        "worker": {
            "id": "",
            "role": "validator",
            "may_create_paid_resources": False,
        },
        "files": {
            "launch_manifest": launch_manifest_ref,
            "local_preflight": "",
            "startup": "",
        },
        "manifest": {
            "sha256": sha256_file(launch_manifest_path),
            "validation": {
                "external_command": f"{bridge_command} validate-manifest {launch_manifest_ref} --json",
            },
        },
        "remote_execution": {
            "verification_mode": "tcp",
            "port": tcp_port,
            "timeout_seconds": 300,
            "interval_seconds": 10,
            "cleanup_action": "delete",
        },
        "linear_closeout": {
            "remote_execution_by": "orchestrator",
            "claim_level": "artifact_execution_only",
            "requires_cleanup_status": True,
            "requires_artifact_hashes": True,
        },
        "source_contracts": {
            "launch_bundle": {
                "path": launch_bundle_ref,
                "sha256": sha256_file(launch_bundle_path),
            },
            "launch_manifest": {
                "path": launch_manifest_ref,
                "sha256": sha256_file(launch_manifest_path),
                "required_for_remote_mutation": True,
            },
        },
        "execution_boundary": {
            "worker_role": "validate_prepare_only",
            "cloud_mutation_role": "orchestrator",
            "paid_resource_mutation_allowed_in_worker": False,
            "no_silent_provider_fallback": True,
        },
        "worker_reachability_preflight": {
            "required_before_mutation": True,
            "command": f"{bridge_command} list-resources --name-prefix {resource_prefix} --json",
            "on_failure": "write_provider_handoff_and_stop",
        },
        "orchestrator_actions": [
            {
                "action": "validate_manifest",
                "command": f"{bridge_command} validate-manifest {launch_manifest_ref} --json",
            },
            {
                "action": "duplicate_check",
                "command": f"{bridge_command} list-resources --name-prefix {resource_prefix} --json",
            },
            {
                "action": "create_resource",
                "command": (
                    f"{bridge_command} create-resource {launch_manifest_ref} --out-dir {runtime_dir}/remote"
                    f"{max_spend} --execute --json"
                ),
            },
            {
                "action": "verify_tcp_packet",
                "command": (
                    f"{bridge_command} verify-tcp-packet {launch_manifest_ref} $RESOURCE_ID --port {tcp_port} "
                    f"--out-dir {runtime_dir}/tcp --timeout-seconds 300 --interval-seconds 10 --json"
                ),
            },
            {
                "action": "cleanup_resource",
                "command": (
                    f"{bridge_command} cleanup-resource $RESOURCE_ID --action delete --out-dir {runtime_dir}/remote "
                    "--execute --json"
                ),
            },
            {
                "action": "post_cleanup_prefix_check",
                "command": f"{bridge_command} list-resources --name-prefix {resource_prefix} --json",
            },
        ],
        "closeout_requirements": {
            "artifact_verification_required": True,
            "cleanup_verification_required": True,
            "linear_outcome_required": True,
            "claim_level_required": True,
            "post_cleanup_prefix_check_required": True,
        },
        "expected_artifacts": expected_artifact_paths(launch_bundle, launch_manifest),
        "validation_commands": [
            f"python3 skills/biosymphony-ferm-doe/scripts/sidecar_check.py {launch_bundle_ref}",
            f"{bridge_command} validate-manifest {launch_manifest_ref} --json",
            f"{bridge_command} validate-handoff {handoff_ref} --json",
        ],
        "secrets_policy": {
            "no_literal_secrets": True,
            "runtime_env_only": ["PROVIDER_API_KEY", "TRACKER_API_KEY"],
        },
    }
    write_json(handoff_path, handoff)
    return handoff
