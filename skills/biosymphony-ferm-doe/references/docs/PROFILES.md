# Profiles

A profile describes what *kind* of campaign this is. Profiles are composable: a manifest can declare multiple profiles in `profiles[]` (e.g. `["screening", "scale_down_qualification"]`) and the validator unions their advised inputs, advised expected artifacts, and required blocks.

Profiles are advisory by design. A missing advised block emits a warning, not an error. A profile may mark a small number of fields as `required_blocks`; those become errors when absent, reserved for cases where the campaign is structurally unable to do what the profile claims.

Public safety is orthogonal: it is driven by `claim_level == 'public_synthetic_demo'`, not by profile.

## Registry

| Profile | When to use | Required blocks | Default DoE families |
|---|---|---|---|
| `screening` | First-pass DoE to identify active factors | (none) | DSD, PB, fractional factorial |
| `optimization_rsm` | RSM after screening identifies active factors | `responses`, `factors` | CCD, BBD, optimal_i |
| `mixture` | Blend / formulation optimization | `factors` (≥1 mixture) | Scheffé, extreme vertices |
| `split_plot_fed_batch` | Fed-batch with hard-to-change setpoints | `responses`, `factors` (≥1 hard_to_change) | split_plot |
| `scale_up_bridge` | Plan a scale-up with explicit bridge criterion | `scale_context` | DSD, CCD, BBD |
| `scale_down_qualification` | Build a small-scale model that recapitulates a larger scale | `scale_context`, recapitulation_criterion | full factorial, DSD |
| `confirmation` | Confirm predicted optimum | (none) | custom_constrained, full factorial |
| `sequential_augmentation` | Augment a prior wave | `doe.previous_wave_ref` | sequential_augmentation, optimal_d |
| `custom` | Free-form / outside the named profiles | (none) | (none) |

## Composing profiles

A scale-down qualification campaign that also runs a screening at the new bench arm declares both:

```json
"profiles": ["screening", "scale_down_qualification"]
```

The validator unions advised inputs (historical_run_ledger, evidence_table, equipment_inventory) and required blocks (`scale_context`, recapitulation_criterion, plus the screening profile's reasonable factor count).

## Choosing a profile

Pick the profile that captures the *structural* commitment of the campaign:

- if the campaign cannot answer its question without a defensible scale bridge, declare a scale profile
- if the campaign's design must respect a randomization restriction (hard-to-change factors), declare `split_plot_fed_batch`
- otherwise the screening / optimization / confirmation sequence covers most flask-and-bench work

When in doubt, declare `custom` and let the agent build out structure as the campaign matures. Profiles can be added later; the validator re-evaluates on every run.
