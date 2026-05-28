# Issue Pack Cookbook

Issue packs turn a campaign manifest into local Markdown issue bodies. They are useful for Linear, GitHub Issues, or any agent harness that wants a bounded work graph without calling a tracker API.

## Command Shape

```bash
ferm-doe engine generate-issue-pack \
  --manifest examples/reference-doe-custom-design/campaign_manifest.json \
  --out /tmp/ferm-doe-issues \
  --pack fermentation-readiness-v0
```

The command writes issue Markdown plus a manifest describing pack IDs, dependencies, and output files.

## Public Packs

| Pack | Issues | Use when |
|---|---:|---|
| `fermentation-readiness-v0` | 7 | You need the default campaign contract, data trust, factor space, assay, feasibility, tournament, and packet graph |
| `scientific-swarm-v0` | 11 | You need per-corpus evidence lanes and a single adjudication/dossier lane |
| `evidence-executor-v0` | 4 | You need bounded research workers to produce `evidence_table.csv` rows |
| `adaptive-wave2-assay-power-v0` | 5 | You have first-batch rows and need assay-power-gated follow-up planning |
| `campaign-arms-v1` | 4 | You have coupled plate/flask/reactor arms and need arm-scoped planning |
| `doe-parity-v0` | 7 | You want reference DOE parity work without changing the campaign product |
| `doe-parity-v1` | 9 | You want the broader custom-design, augment, profiler, export, and benchmark utility graph |

## Examples

```bash
ferm-doe engine generate-issue-pack \
  --manifest examples/demo-pb-screening-public/campaign_manifest.json \
  --out /tmp/issues-readiness \
  --pack fermentation-readiness-v0

ferm-doe engine generate-issue-pack \
  --manifest examples/yeast-isoprenoid-2l-fedbatch/campaign_manifest.json \
  --out /tmp/issues-swarm \
  --pack scientific-swarm-v0 \
  --pack evidence-executor-v0

ferm-doe engine generate-issue-pack \
  --manifest examples/reference-doe-custom-design/campaign_manifest.json \
  --out /tmp/issues-doe-parity \
  --pack doe-parity-v1
```

## Safety Boundary

Do not put private process records, customer data, unpublished sequences, API keys, or exact confidential recipes into issue bodies. Use sanitized manifest fields, source metadata, or secure-store references instead.
