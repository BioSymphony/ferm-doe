# Public Contracts

BioSymphony Ferm DoE keeps public contracts small and file-based. They are
designed for long-running agents and generic issue trackers without embedding
private tracker ids, provider launches, private paths, or unpublished artifacts.

## Task Request

`schemas/task_request.schema.json` defines one bounded work request. The matching
stdlib validator is exposed as:

```bash
PYTHONPATH=src python3 -m biosymphony_ferm_doe.cli validate-task-request templates/task_request.template.json
```

Required fields:

- `schema_version: 1`
- `request_kind: ferm_doe_task_request`
- `task_request_id`
- `campaign_id`
- `title`
- `public_safety`
- `expected_artifacts`
- `acceptance_criteria`
- `validation_commands`
- `touched_areas`

Public-safe requests set:

```json
{
  "privacy": "synthetic_or_public_only",
  "private_data_allowed": false,
  "provider_mutation_allowed": false,
  "tracker_specific_ids_allowed": false
}
```

The validator rejects absolute private paths, secret-like text, private
tracker-specific fields, and provider-mutation command tokens.

The repo-local preflight wrapper also recognizes task requests:

```bash
python3 skills/biosymphony-ferm-doe/scripts/preflight_check.py templates/task_request.template.json
```

## Dossier Contract Check

The public package has a compact dossier check, not the full private
orchestration self-check. It validates the minimum public handoff surface:

- `campaign_manifest.json`
- `expected/readiness_summary.json`
- `expected/AGENTS.md`
- optional `expected/selected_wave_1_design.csv`
- optional `expected/run_packet.md`
- evidence table provenance headers when a manifest declares `inputs.evidence_table`

Run it with:

```bash
PYTHONPATH=src python3 -m biosymphony_ferm_doe.cli check-dossier examples/demo-xylanase-public
```

For a compact demo, the preflight wrapper should be pointed at the campaign
directory. It will also route the directory's `campaign_manifest.json` back to
the directory-level dossier contract when the `expected/` contract files are
present:

```bash
python3 skills/biosymphony-ferm-doe/scripts/preflight_check.py examples/demo-xylanase-public
```

The check fails for missing required files, invalid readiness status, malformed
evidence provenance, duplicate selected-design run ids, and unsupported claims
such as validated optimization, production readiness, or execution approval.

## Claim Boundary

These contracts prove artifact shape and public safety. They do not prove lab-execution,
assay validation, optimized conditions, validated scale transfer, or
GxP batch-record readiness.
