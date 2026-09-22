# Adapter Map

Use this map to select a callable tool. The [registry](TOOL_REGISTRY.md) records implementation status and reviewed sources; the [README](https://github.com/BioSymphony/ferm-doe#optional-extras) lists installation extras.

## CLI Calls

| Capability | Command | Extra |
|---|---|---|
| Classical designs | `generate-design` | Base package; `pydoe3` extends selected families |
| Analysis and design power | `analyze`, `doe-power` | Base package; `scipy` adds t-distribution calculations |
| Rule-based follow-up | `plan-wave2` | Base package |
| Gaussian-process candidates | `plan-wave2 --backend botorch` | `botorch` |
| Engine design comparison | `engine propose-design`, `engine compare-designs` | Base package with optional method support |

Commands in the table follow `ferm-doe`. See the [CLI reference](CLI_REFERENCE.md) for required inputs.

The public `plan-wave2` command accepts `stdlib` and `botorch`. The BoTorch branch writes a separate candidate report and does not run the stdlib follow-up workflow. See [BoTorch inputs and outputs](WAVE2_BOTORCH.md).

BoFire, ENTMOOT, OMLT, and TabPFN are Python adapter calls in this checkout. Passing their names to `engine plan-wave2 --backend` does not execute those adapters: that engine utility still generates candidates through its stdlib implementation.

## Python Calls

Import these modules from `biosymphony_ferm_doe.adapters`. The function links identify the implementation and accepted arguments.

| Tool | Entry point | Inputs and use |
|---|---|---|
| BoFire | [`plan_bofire_wave2`](https://github.com/BioSymphony/ferm-doe/blob/main/src/biosymphony_ferm_doe/adapters/bofire_strategy.py) | Compiled state and usable result rows; constrained or multi-fidelity candidates |
| ENTMOOT | [`plan_entmoot_wave2`](https://github.com/BioSymphony/ferm-doe/blob/main/src/biosymphony_ferm_doe/adapters/entmoot_strategy.py) | Compiled state and usable rows; tree surrogate with linear or NChooseK constraints |
| OMLT | [`plan_omlt_wave2`](https://github.com/BioSymphony/ferm-doe/blob/main/src/biosymphony_ferm_doe/adapters/omlt_strategy.py) | Compiled state and usable rows; solver-backed surrogate planning |
| TabPFN | [`plan_tabpfn_wave2`](https://github.com/BioSymphony/ferm-doe/blob/main/src/biosymphony_ferm_doe/adapters/tabpfn_strategy.py) | Compiled state and usable rows; foundation-model surrogate |
| BoTorch | [`plan_bo_wave2`](https://github.com/BioSymphony/ferm-doe/blob/main/src/biosymphony_ferm_doe/adapters/botorch_wave2.py) | Campaign manifest and prepared rows; numeric-factor Gaussian-process candidates |
| SALib | [`pawn_indices`, `delta_indices`, `sobol_indices`](https://github.com/BioSymphony/ferm-doe/blob/main/src/biosymphony_ferm_doe/adapters/salib_sensitivity.py) | Factor definitions and numeric arrays; Sobol analysis requires a matching sampling design |
| PubMed records | [`fetch_citations`](https://github.com/BioSymphony/ferm-doe/blob/main/src/biosymphony_ferm_doe/adapters/pubmed_mcp.py) | Normalize local citation fixtures; live retrieval belongs to the agent harness |

### Example: Call The BoFire Adapter

Compile a synthetic campaign into state:

```bash
ferm-doe engine compile-state \
  --manifest examples/demo-media-cost-bofire/campaign_manifest.json \
  --out /tmp/media-tool-demo
```

Call the adapter and inspect its report. An empty result list requests candidates without prior observations:

```python
import json
from pathlib import Path
from biosymphony_ferm_doe.adapters.bofire_strategy import plan_bofire_wave2

state = json.loads(Path("/tmp/media-tool-demo/campaign_state.json").read_text())
report = plan_bofire_wave2(state, [], backend="bofire", remaining_budget=3)
Path("/tmp/media-tool-demo/bofire_report.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print(report["adapter_status"], report["candidate_design_count"])
```

With the optional dependency absent, this call returns `not_available`. A successful call returns `executed`; inspect `candidate_design`, `route`, and `issues` before using the candidates. The report does not execute a second tool for you.

For follow-up calls, prepare usable result rows with the campaign's run IDs, response columns, trust rules, and QC checks. Pass the rows in the adapter's input format. Your agent can save the report, compare candidates with another method, and choose its next call.

## Availability And Constraints

`ferm-doe doctor` reports dependency and configuration checks. An installed dependency alone does not establish that a particular adapter ran. Utility reports distinguish `adapter_executed` from availability; direct adapter reports carry their own status and issues.

BoFire, ENTMOOT, OMLT, and TabPFN modules can report unavailable dependencies. Solver routes also require a compatible solver; TabPFN requires model access. BoTorch and SALib imports require their extras. Check each call's output rather than assuming a universal fallback.

The supported BoFire adapter retains the Bayesian `SoboStrategy` + `NChooseK` compatibility limit recorded in [ENTMOOT routing guidance](ENTMOOT_SWAP_DESIGN.md). ENTMOOT and OMLT provide separate solver-backed candidate routes. Inspect constraint coverage and candidate feasibility before accepting a design.

## Evaluation Candidates

BayBE and Ax have comparison fixtures under [adaptive backend evaluation](https://github.com/BioSymphony/ferm-doe/tree/main/examples/adaptive-backend-eval). Other registry entries describe research or external tools. A registry entry is neither an installed dependency nor a callable adapter. Read `status`, `package`, `route`, and `docs_in_repo` before choosing a tool.
