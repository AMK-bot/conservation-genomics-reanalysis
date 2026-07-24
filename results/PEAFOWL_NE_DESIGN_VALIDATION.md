# Peafowl N_e sample-design validation

Generated: 2026-07-19T10:24:41.728839+00:00

Overall: **PASS** (36 PASS, 0 FAIL)

This gate independently reconciles the simulated scenario grid, bounded empirical sensitivity grid, raw currentNe2 90% CI parser state, repeated pilot, summaries, figure bridge, and provenance. Scenario calibration is not a guarantee that an exact real sample size will resolve N_e > 500.

| Check | Status | Details |
|---|---:|---|
| `required_artifacts` | **PASS** | missing=none |
| `predeclared_synthesis_thresholds` | **PASS** | none |
| `currentne2_ci_configuration` | **PASS** | ci_pct=90.0; genome_size_morgans=32.0 |
| `independent_pedigree_haldane_golden` | **PASS** | observed=6fb3c1b84e3a98bcce1768949108df6637cb0455429de0ac46db924b2921d60f; expected=6fb3c1b84e3a98bcce1768949108df6637cb0455429de0ac46db924b2921d60f |
| `schema_scenario` | **PASS** | expected=42 columns; actual=42; missing=[]; extra=[] |
| `schema_pilot` | **PASS** | expected=45 columns; actual=45; missing=[]; extra=[] |
| `schema_empirical` | **PASS** | expected=35 columns; actual=35; missing=[]; extra=[] |
| `schema_summary` | **PASS** | expected=58 columns; actual=58; missing=[]; extra=[] |
| `schema_figure_values` | **PASS** | expected=13 columns; actual=13; missing=[]; extra=[] |
| `scenario_grid_60_cells_by_replicates` | **PASS** | rows=720 expected=720; duplicate=0; missing=0; extra=0 |
| `scenario_truth_seed_outcome_traceability` | **PASS** | checked=720; errors=none |
| `scenario_independent_pedigree_haldane_vcf_replay` | **PASS** | unique_panels=48; errors=none |
| `boundary_ne500_never_correct_or_incorrect` | **PASS** | boundary_rows=180 expected=180; bad=0 |
| `scenario_raw_hash_parser_and_analyzed_dimensions` | **PASS** | rows=720 parsed_raw=720 successful=720; errors=none |
| `pilot_two_complete_seeded_runs` | **PASS** | none |
| `pilot_scientific_hash_repeatability` | **PASS** | independent_primary=0a29b81c0cc33b0fb3b13bbef2987e6ccb6731efa33cf2d48399b8d3ade3689b; independent_repeat=0a29b81c0cc33b0fb3b13bbef2987e6ccb6731efa33cf2d48399b8d3ade3689b; stored_match=True |
| `pilot_four_outcome_blind_expansion_gates` | **PASS** | repeat=True; integrity=True; runtime=True; wilson=True; status=expanded; mismatches=[] |
| `pilot_cache_invariant_runtime_and_wilson_reconciliation` | **PASS** | currentNe2=95.878407; simulation=6.558744; projected=614.622905 |
| `pilot_primary_retained_in_scenario_table` | **PASS** | scenario_pilot=0a29b81c0cc33b0fb3b13bbef2987e6ccb6731efa33cf2d48399b8d3ade3689b; primary=0a29b81c0cc33b0fb3b13bbef2987e6ccb6731efa33cf2d48399b8d3ade3689b |
| `pilot_independent_input_replay` | **PASS** | rows=240; errors=none |
| `pilot_raw_hash_parser_traceability` | **PASS** | pilot_rows=240 parsed_raw=240; errors=none |
| `empirical_grid_n5_through_observed` | **PASS** | rows=180 expected=180; duplicate=False; missing=0; extra=0 |
| `empirical_bounds_subsets_seeds_unknown_truth` | **PASS** | populations={Thailand:5, Vietnam:10, Yunnan:7}; errors=none |
| `empirical_independent_reservoir_strict80_vcf_replay` | **PASS** | rows=180; strict_rule=called*5>samples*4; errors=none |
| `empirical_raw_hash_parser_and_analyzed_dimensions` | **PASS** | rows=180 parsed_raw=180 successful=180; errors=none |
| `failures_and_nonconvergence_are_explicit_rows` | **PASS** | execution_failures=0; successful_nonconverged=234; both categories retained in denominators |
| `summary_exact_reconciliation` | **PASS** | rows=90 expected=90; errors=none |
| `summary_outcome_denominators_partition` | **PASS** | none |
| `figure_values_exact_summary_bridge` | **PASS** | rows=390 expected=390; errors=none |
| `empirical_figure_axis_n5_through_each_observed_n` | **PASS** | observed=[('Thailand', 5), ('Vietnam', 5), ('Vietnam', 6), ('Vietnam', 7), ('Vietnam', 8), ('Vietnam', 9), ('Vietnam', 10), ('Yunnan', 5), ('Yunnan', 6), ('Yunnan', 7)]; expected=[('Thailand', 5), ('Vietnam', 5), ('Vietnam', 6), ('Vietnam', 7), ('Vietnam', 8), ('Vietnam', 9), ('Vietnam', 10), ('Yunnan', 5), ('Yunnan', 6), ('Yunnan', 7)] |
| `scenario_empirical_visual_separation` | **PASS** | panel_types={'empirical_sensitivity': {'empirical'}, 'scenario_design_target': {'scenario'}, 'scenario_outcome_audit': {'scenario'}} |
| `figure_png_rendered` | **PASS** | bytes=228579 dimensions=2700x1530 |
| `provenance_inputs_binary_parser_model_outputs` | **PASS** | none |
| `bounded_laptop_runtime_projection` | **PASS** | projected_full_seconds=614.6229047826491; configured_max=3600.0; gate=True |
| `cache_manifest_sidecars_timing_telemetry_and_inventories` | **PASS** | expected_attempts=1020; errors=none |
| `public_tables_provenance_manifest_path_privacy` | **PASS** | none |
