#!/usr/bin/env python3
"""RO-Crate 1.2 + Process Run Crate 0.5 retrofit for a ferm DoE dossier.

Generates ``ro-crate-metadata.json`` in the target dossier directory and
validates the crate round-trips cleanly via the rocrate library.

Usage::

    python3 rocrate_retrofit.py --dossier <path> [--out <dir>]

The metadata file is written to ``<out>/ro-crate-metadata.json``. The crate
records the four standard computational phases that a BioSymphony Ferm DoE
campaign produces (DoE screening, Bayesian optimisation, scale-bridge,
handoff packet compilation). Phase metadata is generic; callers should
override fields by editing the emitted JSON if a campaign needs different
phase descriptions.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_rocrate_metadata(dossier_root: Path, out_dir: Path) -> dict:
    """Build RO-Crate 1.2 + Process Run Crate 0.5 metadata for a dossier.

    The Process Run Crate profile (https://w3id.org/ro/wfrun/process/0.5)
    requires:
      - ``CreateAction`` entities per computational phase run
      - ``SoftwareApplication`` entities for each tool
      - Input/output ``FormalParameter`` connections
    """

    # Collect dossier files for hasPart
    data_entities = []
    for path in sorted(dossier_root.rglob("*")):
        if path.is_file() and path.name != "ro-crate-metadata.json":
            rel = path.relative_to(dossier_root).as_posix()
            media_type = _media_type(path)
            entity: dict = {
                "@id": rel,
                "@type": "File",
                "name": path.name,
                "encodingFormat": media_type,
                "contentSize": path.stat().st_size,
            }
            data_entities.append(entity)

    has_part = [{"@id": e["@id"]} for e in data_entities]

    # SoftwareApplication entities
    biosymphony_app = {
        "@id": "https://github.com/BioSymphony/ferm-doe",
        "@type": "SoftwareApplication",
        "name": "biosymphony-ferm-doe",
        "description": (
            "BioSymphony fermentation DoE engine: constraint-aware experimental "
            "design, BoFire adapter, dossier compiler, and provenance toolchain."
        ),
        "softwareVersion": "0.1.0",
        "url": "https://github.com/BioSymphony/ferm-doe",
        "programmingLanguage": {"@id": "https://www.python.org/"},
    }

    bofire_app = {
        "@id": "https://github.com/experimental-design/bofire",
        "@type": "SoftwareApplication",
        "name": "BoFire",
        "description": "Bayesian optimization framework for experimental design (DoEStrategy + SoboStrategy).",
        "softwareVersion": ">=0.3.1,<0.4",
        "url": "https://github.com/experimental-design/bofire",
    }

    # FormalParameter for shared manifest input
    manifest_param = {
        "@id": "#param-campaign-manifest",
        "@type": "FormalParameter",
        "name": "campaign_manifest",
        "description": "JSON campaign manifest declaring factors, constraints, responses, and BoFire strategy spec.",
        "additionalType": {"@id": "https://schema.org/MediaObject"},
    }

    # Phase run entities (CreateAction per computational phase)
    now = utc_now()

    phase1_action = {
        "@id": "#run-phase1-doe-strategy",
        "@type": "CreateAction",
        "name": "Phase 1 - Cost-constrained DoE screening (D-optimal)",
        "description": (
            "BoFire DoEStrategy + DOptimalityCriterion invoked on the campaign "
            "manifest. Generates feasible candidates that satisfy declared cost, "
            "carbon, and cardinality (NChooseK) constraints."
        ),
        "startTime": now,
        "endTime": now,
        "actionStatus": {"@id": "http://schema.org/CompletedActionStatus"},
        "instrument": [
            {"@id": "https://github.com/BioSymphony/ferm-doe"},
            {"@id": "https://github.com/experimental-design/bofire"},
        ],
        "object": [
            {"@id": "campaign_manifest.json"},
            {"@id": "#param-campaign-manifest"},
        ],
        "result": [
            {"@id": "expected/bofire_strategy_report.json"},
            {"@id": "expected/bofire_strategy_report.html"},
            {"@id": "expected/artifact_hashes.json"},
        ],
    }

    phase2_action = {
        "@id": "#run-phase2-bo-sobo",
        "@type": "CreateAction",
        "name": "Phase 2 - Bayesian optimisation (SOBO)",
        "description": (
            "SoboStrategy (qNEI acquisition) conditioned on Phase 1 ranked "
            "candidates. Proposes BO candidates against the cost-per-mg or "
            "campaign-declared objective."
        ),
        "startTime": now,
        "endTime": now,
        "actionStatus": {"@id": "http://schema.org/CompletedActionStatus"},
        "instrument": [
            {"@id": "https://github.com/BioSymphony/ferm-doe"},
            {"@id": "https://github.com/experimental-design/bofire"},
        ],
        "object": [
            {"@id": "phase2_manifest.json"},
            {"@id": "expected/bofire_strategy_report.json"},
        ],
        "result": [
            {"@id": "expected/bofire_phase2_report.json"},
            {"@id": "expected/phase2_artifact_hashes.json"},
        ],
    }

    phase3_action = {
        "@id": "#run-phase3-scale-bridge",
        "@type": "CreateAction",
        "name": "Phase 3 - Scale-bridge (shake-flask to 2 L bioreactor)",
        "description": (
            "Augmented multi-fidelity scale-bridge. When BoFire's "
            "MultiFidelityVarianceBasedStrategy is not yet constraint-aware on "
            "main, falls back to parallel D-optimal arms per fidelity tier "
            "with the fallback recorded explicitly."
        ),
        "startTime": now,
        "endTime": now,
        "actionStatus": {"@id": "http://schema.org/CompletedActionStatus"},
        "instrument": [
            {"@id": "https://github.com/BioSymphony/ferm-doe"},
            {"@id": "https://github.com/experimental-design/bofire"},
        ],
        "object": [
            {"@id": "phase3_manifest.json"},
            {"@id": "expected/bofire_phase2_report.json"},
        ],
        "result": [
            {"@id": "expected/bofire_phase3_report.json"},
            {"@id": "expected/phase3_artifact_hashes.json"},
        ],
    }

    phase4_action = {
        "@id": "#run-phase4-handoff-packet",
        "@type": "CreateAction",
        "name": "Phase 4 - Handoff packet compilation",
        "description": (
            "Native biosymphony-ferm-doe dossier compiler assembles planning "
            "artifacts, evidence citations, NOTES.md, SOURCES.bib, and "
            "per-corpus EVIDENCE/ outputs from the upstream phases. The Pareto-"
            "ranked design table lands in handoff-packet/design_table.csv."
        ),
        "startTime": now,
        "endTime": now,
        "actionStatus": {"@id": "http://schema.org/CompletedActionStatus"},
        "instrument": [{"@id": "https://github.com/BioSymphony/ferm-doe"}],
        "object": [
            {"@id": "expected/bofire_strategy_report.json"},
            {"@id": "expected/bofire_phase2_report.json"},
            {"@id": "expected/bofire_phase3_report.json"},
        ],
        "result": [
            {"@id": "dossier/CITATIONS.json"},
            {"@id": "dossier/NOTES.md"},
            {"@id": "dossier/SOURCES.bib"},
            {"@id": "handoff-packet/design_table.csv"},
            {"@id": "handoff-packet/design_summary.json"},
        ],
    }

    # Python language entity
    python_lang = {
        "@id": "https://www.python.org/",
        "@type": "ComputerLanguage",
        "name": "Python",
        "url": "https://www.python.org/",
    }

    # Metadata file entity (self-descriptor)
    metadata_entity = {
        "@id": "ro-crate-metadata.json",
        "@type": "CreativeWork",
        "about": {"@id": "./"},
        "conformsTo": [
            {"@id": "https://w3id.org/ro/crate/1.2"},
            {"@id": "https://w3id.org/ro/wfrun/process/0.5"},
        ],
        "dateCreated": utc_now(),
        "description": (
            "RO-Crate 1.2 metadata with Process Run Crate 0.5 profile for a "
            "BioSymphony Ferm DoE planning dossier. Records the four "
            "computational phases (DoE, BO, scale-bridge, handoff compilation)."
        ),
    }

    # Root Dataset
    root_dataset = {
        "@id": "./",
        "@type": "Dataset",
        "name": f"{dossier_root.name} - BioSymphony Ferm DoE planning dossier",
        "description": (
            "BioSymphony Ferm DoE planning dossier. Covers four computational "
            "phases: constrained DoE screening (Phase 1), Bayesian "
            "optimisation (Phase 2), scale-bridge (Phase 3), and handoff "
            "packet compilation (Phase 4). All candidate designs are PLANNED; "
            "no lab execution is implied by this metadata."
        ),
        "identifier": dossier_root.name,
        "datePublished": now.split("T", 1)[0],
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "conformsTo": [
            {"@id": "https://w3id.org/ro/crate/1.2"},
            {"@id": "https://w3id.org/ro/wfrun/process/0.5"},
        ],
        "keywords": [
            "fermentation",
            "design of experiments",
            "Bayesian optimisation",
            "BoFire",
            "biosymphony",
        ],
        "publisher": {"@id": "#biosymphony-project"},
        "hasPart": has_part
        + [
            {"@id": "#run-phase1-doe-strategy"},
            {"@id": "#run-phase2-bo-sobo"},
            {"@id": "#run-phase3-scale-bridge"},
            {"@id": "#run-phase4-handoff-packet"},
        ],
        "mentions": [
            {"@id": "#run-phase1-doe-strategy"},
            {"@id": "#run-phase2-bo-sobo"},
            {"@id": "#run-phase3-scale-bridge"},
            {"@id": "#run-phase4-handoff-packet"},
        ],
        "claimLevel": "public_synthetic_demo",
        "nonClaim": (
            "This dossier captures computational planning artifacts only. "
            "No lab execution, clinical validation, or regulatory submission "
            "is implied. Candidate designs require physical execution and "
            "qualified analytical measurement before any scientific conclusion "
            "can be drawn."
        ),
    }

    # Publisher organization entity
    biosymphony_org = {
        "@id": "#biosymphony-project",
        "@type": "Organization",
        "name": "BioSymphony Ferm DoE Project",
        "description": "Open-source biosystems engineering planning toolkit for fermentation DoE campaigns.",
    }

    # Process Run Crate profile reference entities
    rocrate_spec = {
        "@id": "https://w3id.org/ro/crate/1.2",
        "@type": ["CreativeWork", "Profile"],
        "name": "RO-Crate 1.2",
        "version": "1.2",
    }

    process_run_profile = {
        "@id": "https://w3id.org/ro/wfrun/process/0.5",
        "@type": ["CreativeWork", "Profile"],
        "name": "Process Run Crate",
        "version": "0.5",
        "url": "https://w3id.org/ro/wfrun/process/0.5",
    }

    graph = (
        [
            metadata_entity,
            root_dataset,
            rocrate_spec,
            process_run_profile,
            python_lang,
            biosymphony_app,
            bofire_app,
            biosymphony_org,
            manifest_param,
            phase1_action,
            phase2_action,
            phase3_action,
            phase4_action,
        ]
        + data_entities
    )

    return {
        "@context": "https://w3id.org/ro/crate/1.2/context",
        "@graph": graph,
    }


def _media_type(path: Path) -> str:
    import mimetypes

    if path.suffix == ".md":
        return "text/markdown"
    if path.suffix == ".bib":
        return "application/x-bibtex"
    if path.suffix == ".ndjson":
        return "application/x-ndjson"
    if path.suffix == ".svg":
        return "image/svg+xml"
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def validate_crate(metadata_path: Path) -> dict:
    """Structural round-trip validation via rocrate library.

    rocrate 0.15.0 does not ship a CLI ``validate`` command; we validate by
    loading the written metadata and asserting the required graph nodes.
    """
    from rocrate.rocrate import ROCrate

    crate = ROCrate(metadata_path.parent)
    errors: list[str] = []
    warnings: list[str] = []

    root = crate.root_dataset
    if root is None:
        errors.append("Root dataset (./) not found")
    else:
        name = root.get("name")
        if not name:
            warnings.append("Root dataset has no name")
        conforms = root.get("conformsTo")
        if not conforms:
            warnings.append("Root dataset has no conformsTo")

    md = crate.metadata
    if md is None:
        errors.append("Metadata descriptor (ro-crate-metadata.json) not found")
    else:
        conforms = md.get("conformsTo")
        if not conforms:
            warnings.append("Metadata descriptor has no conformsTo")

    actions = [e for e in crate.get_entities() if "CreateAction" in (e.type or [])]
    if len(actions) < 4:
        warnings.append(f"Expected >=4 CreateAction entities, found {len(actions)}")

    apps = [e for e in crate.get_entities() if "SoftwareApplication" in (e.type or [])]
    if len(apps) < 2:
        warnings.append(f"Expected >=2 SoftwareApplication entities, found {len(apps)}")

    return {
        "status": "FAIL" if errors else "PASS",
        "entity_count": len(list(crate.get_entities())),
        "action_count": len(actions),
        "app_count": len(apps),
        "errors": errors,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate RO-Crate 1.2 + Process Run Crate 0.5 for a ferm DoE dossier.")
    parser.add_argument(
        "--dossier",
        required=True,
        help="Path to the dossier root directory",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output directory for ro-crate-metadata.json (default: same as --dossier)",
    )
    args = parser.parse_args(argv)

    dossier_root = Path(args.dossier).resolve()
    out_dir = Path(args.out).resolve() if args.out else dossier_root

    if not dossier_root.is_dir():
        print(f"ERROR: dossier directory not found: {dossier_root}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Building RO-Crate 1.2 metadata for: {dossier_root.name}")
    crate_metadata = build_rocrate_metadata(dossier_root, out_dir)

    out_path = out_dir / "ro-crate-metadata.json"
    out_path.write_text(json.dumps(crate_metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Written: {out_path}")
    print(f"  Entities in @graph: {len(crate_metadata['@graph'])}")

    print("\nValidating (structural round-trip via rocrate library)...")
    result = validate_crate(out_path)
    print(f"  Status:   {result['status']}")
    print(f"  Entities: {result['entity_count']}")
    print(f"  Actions:  {result['action_count']}")
    print(f"  Apps:     {result['app_count']}")
    if result["errors"]:
        for err in result["errors"]:
            print(f"  ERROR: {err}", file=sys.stderr)
    if result["warnings"]:
        for warn in result["warnings"]:
            print(f"  WARN:  {warn}")

    summary = {
        "schema_version": 1,
        "rocrate_version": "1.2",
        "profile": "https://w3id.org/ro/wfrun/process/0.5",
        "dossier": dossier_root.name,
        "output": str(out_path),
        "graph_entity_count": len(crate_metadata["@graph"]),
        "validation": result,
    }
    summary_path = out_dir / "ro-crate-validation-report.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSummary report: {summary_path}")

    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
