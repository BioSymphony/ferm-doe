#!/usr/bin/env python3
"""Run the BoFire-routed constrained-DoE smoke against a manifest.

The script:

1. Loads the supplied manifest JSON
2. Optionally loads usable prior result rows from ``--results``
3. Calls ``plan_bofire_wave2`` (translates manifest -> BoFire Domain, runs
   ``DoEStrategy``/``MoboStrategy``/etc., emits candidate rows)
4. Writes the report JSON to ``--out-json``
5. Renders the single-file HTML report to ``--out-html``
6. Records SHA-256 hashes of both artifacts in ``--out-hashes``
7. Emits a one-line JSON status to stdout

Exits 0 on routing+translation+render success, even if BoFire is not
installed (status: not_available), unless strict execution flags are set.
Exits 2 if the manifest does not declare any non-box constraint or
multi-objective response (status: not_routed). Exits 3 on render failure.
Exits 4 when strict execution requirements are not met after artifacts are
written.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from _engine_path import ensure_src_path

ensure_src_path()

from biosymphony_ferm_doe.adapters import bofire_strategy
from biosymphony_ferm_doe.reporters import bofire_html


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, help="Path to campaign_manifest.json")
    parser.add_argument("--out-json", required=True, help="Path to write bofire_strategy_report.json")
    parser.add_argument("--out-html", required=True, help="Path to write bofire_strategy_report.html")
    parser.add_argument("--out-hashes", default=None, help="Optional path to write artifact SHA-256 hashes")
    parser.add_argument("--results", help="Optional CSV of usable prior result rows for adaptive/multi-fidelity smokes")
    parser.add_argument("--budget", type=int, default=12, help="Candidate design size for ask()")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--require-executed", action="store_true", help="Fail unless adapter_status is executed.")
    parser.add_argument("--require-candidates", action="store_true", help="Fail unless at least one candidate row is emitted.")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    out_json = Path(args.out_json)
    out_html = Path(args.out_html)

    manifest = json.loads(manifest_path.read_text())
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_html.parent.mkdir(parents=True, exist_ok=True)

    usable_rows = _read_rows(Path(args.results)) if args.results else []
    decision = bofire_strategy.routing_decision(manifest, usable_rows)
    if not decision["should_route"]:
        print(
            json.dumps(
                {"status": "not_routed", "reasons": decision.get("reasons", []), "manifest": str(manifest_path)},
                sort_keys=True,
            )
        )
        return 2

    report = bofire_strategy.plan_bofire_wave2(
        manifest, usable_rows, backend="bofire", remaining_budget=args.budget, seed=args.seed
    )
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True))

    try:
        html_text = bofire_html.render_to_string(report, manifest=manifest)
        out_html.write_text(html_text, encoding="utf-8")
    except Exception as exc:
        print(
            json.dumps(
                {"status": "render_failed", "error": f"{type(exc).__name__}: {exc}"},
                sort_keys=True,
            )
        )
        return 3

    hashes = {
        "report_json_sha256": _sha256(out_json),
        "report_html_sha256": _sha256(out_html),
        "manifest_sha256": _sha256(manifest_path),
    }
    if args.out_hashes:
        hashes_path = Path(args.out_hashes)
        hashes_path.parent.mkdir(parents=True, exist_ok=True)
        hashes_path.write_text(json.dumps(hashes, indent=2, sort_keys=True))

    strict_errors = strict_execution_errors(
        report,
        require_executed=args.require_executed,
        require_candidates=args.require_candidates,
    )
    if strict_errors:
        print(
            json.dumps(
                {
                    "status": "strict_failed",
                    "adapter_status": report.get("adapter_status"),
                    "candidate_count": report.get("candidate_design_count", 0),
                    "errors": strict_errors,
                    "report_json": str(out_json),
                    "report_html": str(out_html),
                    "hashes": hashes,
                },
                sort_keys=True,
            )
        )
        return 4

    print(
        json.dumps(
            {
                "status": "OK",
                "adapter_status": report.get("adapter_status"),
                "strategy_kind": report.get("strategy_kind"),
                "candidate_count": report.get("candidate_design_count", 0),
                "usable_rows": len(usable_rows),
                "report_json": str(out_json),
                "report_html": str(out_html),
                "hashes": hashes,
            },
            sort_keys=True,
        )
    )
    return 0


def strict_execution_errors(
    report: dict[str, object],
    *,
    require_executed: bool = False,
    require_candidates: bool = False,
) -> list[str]:
    errors: list[str] = []
    if require_executed and report.get("adapter_status") != "executed":
        errors.append(f"adapter_status must be executed, got {report.get('adapter_status')}")
    if require_candidates:
        try:
            candidate_count = int(report.get("candidate_design_count", 0) or 0)
        except (TypeError, ValueError):
            candidate_count = 0
        if candidate_count <= 0:
            errors.append("candidate_design_count must be greater than zero")
    return errors


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return [{key: (value or "").strip() for key, value in row.items()} for row in reader]


if __name__ == "__main__":
    raise SystemExit(main())
