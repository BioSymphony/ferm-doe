#!/usr/bin/env python3
"""Emit a provider handoff artifact for orchestrator-side remote execution.

The handoff captures the validated launch bundle and manifest plus the
reason the worker is asking the orchestrator to perform paid provider
mutation (resource create, artifact verify, cleanup). It uses portable
paths, does not contain provider secrets, and should still pass the public
release scan before being committed alongside planning artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _engine_path import ensure_src_path

ensure_src_path()

from biosymphony_ferm_doe.provider_handoff import prepare_provider_handoff


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--launch-bundle", required=True)
    parser.add_argument("--launch-manifest", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--provider-bridge",
        default="provider-bridge",
        help="Command or path used by the orchestrator to mutate the provider (default: provider-bridge)",
    )
    parser.add_argument(
        "--reason",
        default="worker_provider_api_unreachable",
        help="Why the worker is handing provider mutation to the orchestrator",
    )
    parser.add_argument(
        "--ticket",
        default=None,
        help="Optional opaque ticket identifier for the handoff record",
    )
    args = parser.parse_args()

    handoff = prepare_provider_handoff(
        Path(args.launch_bundle),
        Path(args.out),
        launch_manifest_path=Path(args.launch_manifest),
        provider_bridge=args.provider_bridge,
        reason=args.reason,
        tracker_issue=args.ticket,
    )
    print(
        json.dumps(
            {
                "status": "OK",
                "run_id": handoff["run_id"],
                "out": str(Path(args.out) / "provider_handoff.json"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
