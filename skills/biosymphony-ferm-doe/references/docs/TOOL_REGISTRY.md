# BioSymphony Tool Registry

- Status: `PASS`
- Tools: `47`
- Findings: `0 errors`, `0 warnings`
- Checked on: `2026-06-21`
- Pyproject alignment: `10` packages across `15` extras
- Action lanes: `4` nox lanes, `0` remote lanes

| Tool | Priority | Status | Extra | Claim | Route |
| --- | --- | --- | --- | --- | --- |
| bofire | P0 | adopted_optional | bofire | bofire_adapter_planning | non_box_constraints, multi_objective_responses, scale_fidelity_structure, ... |
| frictionless | P0 | adopted_optional | contracts | contract_validation | table_contracts |
| nox | P0 | adopted_optional | dev | execution_lane | local_validation, optional_lanes |
| pubmed_mcp_adapter | P0 | adopted_optional |  | live_citation_enrichment | dossier_citation_enrichment, bibtex_export |
| ro_crate | P0 | adopted_optional |  | provenance_metadata | compile_dossier, workflow_run_provenance, profile_validation_candidate |
| salib | P0 | adopted_optional | sensitivity | sensitivity_screening | sensitivity_screening, assumption_attack, scale_recipe_uncertainty |
| ax | P1 | evaluate_next | backend-eval | not_yet_evaluated | adaptive_orchestration_pilot, custom_generation_strategy, botorch_infrastructure |
| baybe | P1 | evaluate_next | backend-eval | not_yet_evaluated | bofire_alternative_adapter, categorical_substance_encoding, transfer_learning_across_campaigns, ... |
| biosteam | P1 | evaluate_next |  | economic_context_sidecar | cost_rollup_sidecar, downstream_context |
| botorch | P1 | adopted_optional | botorch | experimental_adapter | experimental_adaptive_adapter |
| cwl | P1 | watch |  | workflow_provenance_sidecar | provider_handoff_bundle |
| eln_file_format | P1 | evaluate_next |  | interchange_candidate | eln_export_candidate, run_packet_interchange, ro_crate_profile_reference |
| entmoot | P1 | adopted_optional | entmoot | adapter_backed_nchoosek_bo | nchoosek_cardinality_bo, tree_based_surrogate, in_repo_adapter |
| fedbatchdesigner | P1 | evaluate_next |  | reference_sidecar | fed_batch_reference_example |
| grobid_fulltext | P1 | evaluate_next |  | evidence_extraction_sidecar | public_pdf_structuring, dossier_evidence_harvest, citation_context_extraction |
| omlt | P1 | adopted_optional | omlt | omlt_adapter_planning | mip_surrogate_optimization, nchoosek_cardinality_bo, optional_in_repo_adapter |
| petab_libpetab | P1 | evaluate_next |  | calibration_contract_candidate | mechanistic_model_contract, parameter_estimation_fixture, petab_validation |
| pixi | P1 | watch |  | developer_tooling | dependency_locking |
| pseudobatch | P1 | evaluate_next |  | preprocessing_candidate | fed_batch_sample_withdrawal, ledger_preprocessing, growth_rate_transform_reference |
| pydoe | P1 | watch |  | adapter_backed_classical_doe | screening, rsm_fit, space_filling_scout |
| pydoe3 | P1 | compatibility_only | pydoe3 | compatibility_adapter | extended_box_behnken, latin_hypercube_maximin, legacy_pydoe3_adapter |
| pyomo_dae | P1 | evaluate_next |  | deterministic_feasibility_sidecar | fed_batch_feasibility, dynamic_constraints |
| pypesto | P1 | evaluate_next |  | calibration_sidecar_candidate | mechanistic_parameter_estimation, uncertainty_quantification_sidecar, petab_sbml_pipeline |
| pyplate | P1 | evaluate_next |  | execution_recipe_sidecar | plate_arm_manifest, plate_recipe_export |
| sbml_runtime_stack | P1 | evaluate_next |  | simulation_sidecar | mechanistic_model_sidecar |
| xopt | P1 | evaluate_next |  | not_yet_evaluated | adaptive_backend_comparison, constrained_bo, multi_objective_bo, ... |
| atlas | P2 | watch |  | not_yet_evaluated | categorical_aware_bo |
| bletl | P2 | boundary_only |  | external_reference | external_biolector_ingest |
| botorch_direct | P2 | watch |  | not_yet_evaluated | cost_aware_acquisition, direct_surrogate_control |
| cadet | P2 | boundary_only |  | external_reference | downstream_external_sidecar |
| cobrapy | P2 | boundary_only |  | evidence_sidecar | metabolic_evidence_sidecar |
| dwsim | P2 | boundary_only |  | external_reference | external_flowsheet_export |
| estim8 | P2 | boundary_only |  | external_reference | fmi_modelica_parameter_estimation, external_bioprocess_model_ingest |
| europe_pmc_api | P2 | watch |  | metadata_harvest_watch | public_life_science_search, open_fulltext_lookup, annotation_harvest |
| llambo | P2 | watch |  | not_yet_evaluated | llm_warmstart_first_batch, optuna_sampler_pilot |
| nextflow | P2 | watch |  | workflow_sidecar | large_compute_pipeline |
| obsidian_apo | P2 | boundary_only |  | external_reference | dash_ui_reference, shap_explanation_reference |
| openalex_official | P2 | watch |  | metadata_harvest_watch | public_literature_context, citation_graph_harvest |
| processoptimizer | P2 | watch |  | not_yet_evaluated | scikit_optimize_migration_target |
| pymoo | P2 | evaluate_next |  | candidate_table_diagnostic | pareto_report, design_tournament |
| smt | P2 | evaluate_next |  | surrogate_diagnostic | scale_bridge_diagnostic |
| snakemake | P2 | watch |  | workflow_sidecar | batch_benchmark_dag |
| tabicl_v2 | P2 | watch |  | watch_only | foundation_model_surrogate_watch, tabpfn_comparison, larger_table_regression_watch |
| tabpfn_v2 | P2 | adopted_optional | tabpfn | tabpfn_adapter_planning | foundation_model_surrogate_pilot, small_data_tabular_regression, optional_in_repo_adapter |
| trieste | P2 | watch |  | watch_only | complex_acquisition_reference, ask_tell_bo_watch, multi_fidelity_bo_watch |
| pysamoo | Avoid | avoid |  | not_applicable |  |
| scikit_optimize | Avoid | avoid |  | not_applicable |  |
