# Swarm Contract And Artifact Schema

## Summary

Define the Scientific Swarm artifact contract for one campaign and compile the local dry-run graph.

## Inputs

- `campaign_state.json`
- Selected campaign manifest
- Upstream swarm artifacts listed in dependencies

## Expected Artifacts

- `evidence_swarm_plan.json`
- `symphony_agent_graph.json`

## Acceptance Criteria

- Artifact schemas, lane responsibilities, and parallelism policy are explicit.
- No Linear API calls, Symphony launch, RunPod launch, or GxP/GMP scope is introduced.
- Downstream lanes have non-overlapping touched areas.

## Validation Commands

```bash
python3 skills/biosymphony-ferm-doe/scripts/compile_swarm_plan.py --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json --out /tmp/biosymphony-swarm-contract
test -f /tmp/biosymphony-swarm-contract/symphony_agent_graph.json
```

## Touched Areas

- `ferm-doe-dossier/swarm/`

## Dependencies

- None

## Risk Notes

Do not store secrets, private strain data, customer batch records, unpublished sequences, or confidential media formulations.

<!-- symphony:schema
schema_version: 1
pack_id: scientific-swarm-v0
pack_issue_id: SW-W0-01
touched_areas:
  - ferm-doe-dossier/swarm/
complexity: medium
-->
