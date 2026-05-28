# Benchmark Harness

## Summary

Broaden the DOE benchmark harness so local fallback behavior and optional adapter behavior are both verified.

## Inputs

- `src/biosymphony_ferm_doe/utilities/benchmark.py` - benchmark runner
- `examples/reference-doe-custom-design/campaign_manifest.json` - reference fixture
- `examples/scfv-fusion-acf-fedbatch-v0/campaign_manifest.json` - multi-arm fixture

## Acceptance Criteria

- [ ] Benchmark reports include exactness, backend-used, backend-available, and diagnostic verdict columns.
- [ ] Stdlib-only benchmark remains valid without optional dependencies.
- [ ] Optional adapters, when present, are labeled as adapter-backed only on executed adapter paths.
- [ ] Benchmark fixture includes at least one rank-deficient negative case and one executable custom-constrained case.

## Validation Commands

```bash
PYTHONPATH=src python3 -m unittest tests.test_engine.EngineTests.test_utility_benchmark_doe_passes -v
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Touched Areas

- `src/biosymphony_ferm_doe/utilities/benchmark.py` - harness output
- `examples/` - benchmark fixtures
- `tests/` - benchmark smoke tests

## Dependencies

Blocked by: adapters-and-generators, diagnostics-verdicts

## Risk Notes

- Keep benchmark data synthetic or public-reference only.
- Do not benchmark against private commercial DOE outputs unless reuse and license status are explicit.
- Do not store secrets, private process records, unpublished biology, or confidential media formulas.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
pack_id: doe-parity-v1
pack_issue_id: benchmark-harness
touched_areas:
  - src/biosymphony_ferm_doe/utilities/benchmark.py
  - examples/
  - tests/
complexity: medium
-->
