# Demo: Public Scale-Bridge (Pilot 50 L to Bench 2 L)

This is the second public-safe BioSymphony Ferm DoE demo. It illustrates a **downscale qualification** workflow: build a small-scale model that recapitulates a pilot reference using kLa-matched scale-down with P/V and mixing time as secondary criteria.

Profile: `scale_down_qualification`.

Scope:

- two arms (pilot reference, benchtop qualification target)
- explicit `scale_context` with from_scale + to_scale, geometry, engineering targets, bridge strategy, bridge_factors, known_offsets, qualification evidence, recapitulation criterion
- five tunable factors at the bench arm
- DSD-shaped 11-run first batch design at bench
- decision rules, stop rules, risk register, assumptions

Non-goals:

- no private process data
- no production-scale physical-execution validation claims
- numerical engineering targets are illustrative placeholders, not measured values from a real bioreactor

Current verdict: `YELLOW`. The recapitulation criterion is declared but not executed; bench-side kLa-vs-RPM curve and assay linearity must be qualified before physical-execution runs.

Run:

```bash
PYTHONPATH=src python3 -m biosymphony_ferm_doe.cli validate examples/demo-scale-bridge-public
```

Citations referenced in `inputs/evidence_table.csv`:

- Garcia-Ochoa & Gomez 2009, Biotechnology Advances (kLa review)
- Junker 2004, Journal of Bioscience and Bioengineering (scale-up review)

These are cited for methodology only; no article text is reproduced.
