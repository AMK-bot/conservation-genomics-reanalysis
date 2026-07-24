# Phase 5B data dictionary

Generated from the final workflow tables. Row counts and storage types therefore describe the delivered artifacts, not a hand-maintained schema draft.

## `results/tables/wolf_froh_load_associations.tsv`

60 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `analysis_id` | `str` | 60/60 | Stable identifier for one analysis result. |
| `cell_id` | `str` | 60/60 | Stable identifier for a frozen parameter-grid cell. |
| `gerp_threshold` | `int64` | 60/60 | GERP RS cutoff defining the wolf load subset. |
| `roh_cutoff_mb` | `float64` | 60/60 | Minimum ROH length in megabases. |
| `outcome` | `str` | 60/60 | Outcome or decision category evaluated in the row. |
| `model` | `str` | 60/60 | Predeclared association model. |
| `n_ind` | `int64` | 60/60 | N ind. |
| `n_pop` | `int64` | 60/60 | N pop. |
| `coefficient` | `float64` | 60/60 | Within-cohort rank association coefficient. |
| `ci_low` | `float64` | 60/60 | Lower bound of the stated confidence interval. |
| `ci_high` | `float64` | 60/60 | Upper bound of the stated confidence interval. |
| `ci_pct` | `int64` | 60/60 | Confidence level in percent. |
| `permutation_p_two_sided` | `float64` | 60/60 | Two-sided permutation p-value with plus-one correction. |
| `expected_direction` | `int64` | 60/60 | Expected direction. |
| `direction_matches_expected` | `bool` | 60/60 | Direction matches expected. |
| `bootstrap_reps` | `int64` | 60/60 | Number of requested bootstrap replicates. |
| `bootstrap_valid` | `int64` | 60/60 | Bootstrap valid. |
| `bootstrap_failed` | `int64` | 60/60 | Bootstrap failed. |
| `permutation_reps` | `int64` | 60/60 | Number of requested permutation replicates. |
| `permutation_valid` | `int64` | 60/60 | Permutation valid. |
| `permutation_failed` | `int64` | 60/60 | Permutation failed. |
| `bootstrap_seed` | `int64` | 60/60 | Bootstrap seed. |
| `permutation_seed` | `int64` | 60/60 | Permutation seed. |
| `negative_control` | `str` | 60/60 | Negative control. |

## `results/tables/wolf_froh_load_rank_stability.tsv`

420 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `pair_id` | `str` | 420/420 | Pair id. |
| `cell_a_id` | `str` | 420/420 | Cell a id. |
| `cell_b_id` | `str` | 420/420 | Cell b id. |
| `gerp_a` | `int64` | 420/420 | Gerp a. |
| `roh_a_mb` | `float64` | 420/420 | Roh a mb. |
| `gerp_b` | `int64` | 420/420 | Gerp b. |
| `roh_b_mb` | `float64` | 420/420 | Roh b mb. |
| `n_ind` | `int64` | 420/420 | N ind. |
| `spearman_rho` | `float64` | 420/420 | Spearman rho. |
| `spearman_p` | `float64` | 420/420 | Spearman p. |
| `kendall_tau` | `float64` | 420/420 | Kendall tau. |
| `kendall_p` | `float64` | 420/420 | Kendall p. |
| `top_percentile` | `int64` | 420/420 | Top percentile. |
| `top_n` | `int64` | 420/420 | Top n. |
| `top_overlap_n` | `int64` | 420/420 | Top overlap n. |
| `top_overlap_fraction` | `float64` | 420/420 | Top overlap fraction. |
| `top_jaccard` | `float64` | 420/420 | Top jaccard. |

## `results/tables/wolf_froh_load_individual_scores.tsv`

3,165 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `cell_id` | `str` | 3165/3165 | Stable identifier for a frozen parameter-grid cell. |
| `gerp_threshold` | `int64` | 3165/3165 | GERP RS cutoff defining the wolf load subset. |
| `roh_cutoff_mb` | `float64` | 3165/3165 | Minimum ROH length in megabases. |
| `IND` | `str` | 3165/3165 | IND. |
| `POP` | `str` | 3165/3165 | POP. |
| `F_ROH` | `float64` | 3165/3165 | F ROH. |
| `REALIZED_LOAD` | `float64` | 3165/3165 | REALIZED LOAD. |
| `MASKED_LOAD` | `float64` | 3165/3165 | MASKED LOAD. |
| `generic_homozygosity` | `float64` | 3165/3165 | Generic homozygosity. |
| `froh_within_pop_rank` | `float64` | 3165/3165 | Froh within pop rank. |
| `realized_within_pop_rank` | `float64` | 3165/3165 | Realized within pop rank. |
| `masked_within_pop_rank` | `float64` | 3165/3165 | Masked within pop rank. |
| `inverse_masked_within_pop_rank` | `float64` | 3165/3165 | Inverse masked within pop rank. |
| `generic_homozygosity_within_pop_rank` | `float64` | 3165/3165 | Generic homozygosity within pop rank. |
| `composite_risk_proxy_score` | `float64` | 3165/3165 | Composite risk proxy score. |
| `composite_global_rank` | `float64` | 3165/3165 | Composite global rank. |
| `composite_risk_percentile` | `float64` | 3165/3165 | Composite risk percentile. |

## `results/tables/wolf_froh_load_figure_values.tsv`

528 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `figure` | `str` | 528/528 | Figure. |
| `panel` | `str` | 528/528 | Panel. |
| `record_type` | `str` | 528/528 | Record type. |
| `cell_id` | `str` | 528/528 | Stable identifier for a frozen parameter-grid cell. |
| `gerp_threshold` | `int64` | 528/528 | GERP RS cutoff defining the wolf load subset. |
| `roh_cutoff_mb` | `float64` | 528/528 | Minimum ROH length in megabases. |
| `outcome` | `str` | 528/528 | Outcome or decision category evaluated in the row. |
| `model` | `str` | 528/528 | Predeclared association model. |
| `IND` | `str` | 422/528 | IND. |
| `POP` | `str` | 438/528 | POP. |
| `x_value` | `float64` | 438/528 | X value. |
| `y_value` | `float64` | 438/528 | Y value. |
| `estimate` | `float64` | 90/528 | Estimate. |
| `ci_low` | `float64` | 90/528 | Lower bound of the stated confidence interval. |
| `ci_high` | `float64` | 90/528 | Upper bound of the stated confidence interval. |
| `n` | `int64` | 528/528 | Number of observations represented by the figure-value row: one for an individual point and the relevant sample size for an aggregate. |

## `results/tables/validation_wolf_robustness.tsv`

24 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `check` | `str` | 24/24 | Human-readable validation assertion. |
| `status` | `str` | 24/24 | PASS, WARN, or FAIL validator status. |
| `detail` | `str` | 24/24 | Machine-derived validation evidence. |

## `results/tables/wolf_roh_localization_individual.tsv`

3,165 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `IND` | `str` | 3165/3165 | IND. |
| `POP` | `str` | 3165/3165 | POP. |
| `gerp_threshold` | `int64` | 3165/3165 | GERP RS cutoff defining the wolf load subset. |
| `roh_cutoff_mb` | `float64` | 3165/3165 | Minimum ROH length in megabases. |
| `n_roh` | `int64` | 3165/3165 | N roh. |
| `roh_raw_span_bp` | `int64` | 3165/3165 | Roh raw span bp. |
| `roh_union_bp` | `int64` | 3165/3165 | Roh union bp. |
| `roh_overlap_bp` | `int64` | 3165/3165 | Roh overlap bp. |
| `froh_recomputed` | `float64` | 3165/3165 | Froh recomputed. |
| `F_ROH_phase4` | `float64` | 3165/3165 | F ROH phase4. |
| `froh_delta` | `float64` | 3165/3165 | Froh delta. |
| `inside_eligible_genotype_calls` | `int64` | 3165/3165 | Eligible polarized GERP-threshold SNP genotype calls inside the selected ROH intervals. |
| `outside_eligible_genotype_calls` | `int64` | 3165/3165 | Eligible polarized GERP-threshold SNP genotype calls outside the selected ROH intervals. |
| `total_eligible_genotype_calls` | `int64` | 3165/3165 | Inside plus outside eligible polarized GERP-threshold SNP genotype calls; an assayed-variant opportunity count, not callable genomic bases. |
| `inside_hom_derived_copies` | `int64` | 3165/3165 | Inside hom derived copies. |
| `outside_hom_derived_copies` | `int64` | 3165/3165 | Outside hom derived copies. |
| `total_hom_derived_copies` | `int64` | 3165/3165 | Total hom derived copies. |
| `inside_hom_del_sum` | `float64` | 3165/3165 | GERP-weighted homozygous-derived burden inside the selected ROH intervals. |
| `outside_hom_del_sum` | `float64` | 3165/3165 | GERP-weighted homozygous-derived burden outside the selected ROH intervals. |
| `total_hom_del_sum` | `float64` | 3165/3165 | Total hom del sum. |
| `all_polarized_gerp_genotype_calls` | `int64` | 3165/3165 | Nonmissing diploid genotype calls at exact GERP-matched, validly polarized allSNPs records before applying a GERP threshold. |
| `inside_burden_rate` | `float64` | 3165/3165 | Inside-ROH homozygous-derived burden per eligible polarized GERP-threshold SNP genotype call. |
| `outside_burden_rate` | `float64` | 3165/3165 | Outside-ROH homozygous-derived burden per eligible polarized GERP-threshold SNP genotype call. |
| `rate_ratio` | `float64` | 3165/3165 | Inside-ROH burden rate divided by the outside-ROH burden rate. |
| `log2_enrichment` | `float64` | 3165/3165 | Base-2 logarithm of the inside/outside burden-per-eligible-genotype-call ratio. |
| `phase4_burden_delta` | `float64` | 3165/3165 | Phase4 burden delta. |
| `phase4_copy_delta` | `int64` | 3165/3165 | Phase4 copy delta. |
| `phase4_genotype_call_delta` | `int64` | 3165/3165 | Difference between the threshold-independent polarized GERP genotype-call count and the validated Phase-4 call total. |
| `status` | `str` | 3165/3165 | PASS, WARN, or FAIL validator status. |
| `failure_reason` | `float64` | 0/3165 | Failure reason. |

## `results/tables/wolf_roh_localization_cohort.tsv`

120 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `POP` | `str` | 120/120 | POP. |
| `gerp_threshold` | `int64` | 120/120 | GERP RS cutoff defining the wolf load subset. |
| `roh_cutoff_mb` | `float64` | 120/120 | Minimum ROH length in megabases. |
| `n_ind` | `int64` | 120/120 | N ind. |
| `inside_eligible_genotype_calls` | `int64` | 120/120 | Eligible polarized GERP-threshold SNP genotype calls inside the selected ROH intervals. |
| `outside_eligible_genotype_calls` | `int64` | 120/120 | Eligible polarized GERP-threshold SNP genotype calls outside the selected ROH intervals. |
| `inside_hom_derived_copies` | `int64` | 120/120 | Inside hom derived copies. |
| `outside_hom_derived_copies` | `int64` | 120/120 | Outside hom derived copies. |
| `inside_hom_del_sum` | `float64` | 120/120 | GERP-weighted homozygous-derived burden inside the selected ROH intervals. |
| `outside_hom_del_sum` | `float64` | 120/120 | GERP-weighted homozygous-derived burden outside the selected ROH intervals. |
| `inside_burden_rate` | `float64` | 120/120 | Inside-ROH homozygous-derived burden per eligible polarized GERP-threshold SNP genotype call. |
| `outside_burden_rate` | `float64` | 120/120 | Outside-ROH homozygous-derived burden per eligible polarized GERP-threshold SNP genotype call. |
| `rate_ratio` | `float64` | 120/120 | Inside-ROH burden rate divided by the outside-ROH burden rate. |
| `log2_enrichment` | `float64` | 120/120 | Base-2 logarithm of the inside/outside burden-per-eligible-genotype-call ratio. |
| `null_valid_reps` | `int64` | 120/120 | Number of finite circular-shift null replicates in the cell. |
| `null_failed_reps` | `int64` | 120/120 | Number of requested circular-shift null replicates that failed in the cell. |
| `null_median_log2_enrichment` | `float64` | 120/120 | Median log2 enrichment under within-chromosome circular ROH shifts. |
| `null_ci_low` | `float64` | 120/120 | Lower percentile bound of the circular-shift null distribution. |
| `null_ci_high` | `float64` | 120/120 | Upper percentile bound of the circular-shift null distribution. |
| `observed_minus_null_median` | `float64` | 120/120 | Observed log2 enrichment minus the circular-shift null median. |
| `permutation_p_two_sided` | `float64` | 120/120 | Two-sided permutation p-value with plus-one correction. |
| `direction` | `str` | 120/120 | Sign classification of the reported effect. |
| `status` | `str` | 120/120 | PASS, WARN, or FAIL validator status. |
| `failure_reason` | `float64` | 0/120 | Failure reason. |

## `results/tables/wolf_roh_localization_null.tsv`

23,880 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `POP` | `str` | 23880/23880 | POP. |
| `replicate` | `int64` | 23880/23880 | Replicate. |
| `base_seed` | `int64` | 23880/23880 | Base seed. |
| `gerp_threshold` | `int64` | 23880/23880 | GERP RS cutoff defining the wolf load subset. |
| `roh_cutoff_mb` | `float64` | 23880/23880 | Minimum ROH length in megabases. |
| `inside_eligible_genotype_calls` | `int64` | 23880/23880 | Eligible polarized GERP-threshold SNP genotype calls inside the selected ROH intervals. |
| `outside_eligible_genotype_calls` | `int64` | 23880/23880 | Eligible polarized GERP-threshold SNP genotype calls outside the selected ROH intervals. |
| `total_eligible_genotype_calls` | `int64` | 23880/23880 | Inside plus outside eligible polarized GERP-threshold SNP genotype calls; an assayed-variant opportunity count, not callable genomic bases. |
| `inside_hom_derived_copies` | `int64` | 23880/23880 | Inside hom derived copies. |
| `outside_hom_derived_copies` | `int64` | 23880/23880 | Outside hom derived copies. |
| `total_hom_derived_copies` | `int64` | 23880/23880 | Total hom derived copies. |
| `inside_hom_del_sum` | `float64` | 23880/23880 | GERP-weighted homozygous-derived burden inside the selected ROH intervals. |
| `outside_hom_del_sum` | `float64` | 23880/23880 | GERP-weighted homozygous-derived burden outside the selected ROH intervals. |
| `total_hom_del_sum` | `float64` | 23880/23880 | Total hom del sum. |
| `inside_burden_rate` | `float64` | 23880/23880 | Inside-ROH homozygous-derived burden per eligible polarized GERP-threshold SNP genotype call. |
| `outside_burden_rate` | `float64` | 23880/23880 | Outside-ROH homozygous-derived burden per eligible polarized GERP-threshold SNP genotype call. |
| `rate_ratio` | `float64` | 23880/23880 | Inside-ROH burden rate divided by the outside-ROH burden rate. |
| `log2_enrichment` | `float64` | 23880/23880 | Base-2 logarithm of the inside/outside burden-per-eligible-genotype-call ratio. |
| `status` | `str` | 23880/23880 | PASS, WARN, or FAIL validator status. |
| `failure_reason` | `float64` | 0/23880 | Failure reason. |

## `results/tables/wolf_roh_localization_qc.tsv`

38 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `chrom` | `int64` | 38/38 | Chrom. |
| `coordinate_semantics` | `str` | 38/38 | Coordinate semantics. |
| `gerp_bed_records` | `int64` | 38/38 | Gerp bed records. |
| `gerp_wrong_chromosome_rows` | `int64` | 38/38 | Gerp wrong chromosome rows. |
| `gerp_duplicate_positions` | `int64` | 38/38 | Gerp duplicate positions. |
| `gerp_bounds_failures` | `int64` | 38/38 | Gerp bounds failures. |
| `rg_records` | `int64` | 38/38 | Rg records. |
| `rg_wrong_chromosome_rows` | `int64` | 38/38 | Rg wrong chromosome rows. |
| `rg_unknown_samples` | `int64` | 38/38 | Rg unknown samples. |
| `rg_length_mismatches` | `int64` | 38/38 | Rg length mismatches. |
| `rg_bounds_failures` | `int64` | 38/38 | Rg bounds failures. |
| `rg_overlap_pairs` | `int64` | 38/38 | Rg overlap pairs. |
| `rg_adjacent_pairs` | `int64` | 38/38 | Rg adjacent pairs. |
| `rg_overlap_bp` | `int64` | 38/38 | Rg overlap bp. |
| `vcf_variants` | `int64` | 38/38 | Vcf variants. |
| `gerp_positions_matched` | `int64` | 38/38 | Gerp positions matched. |
| `valid_gerp_ancestral_sites` | `int64` | 38/38 | Valid gerp ancestral sites. |
| `invalid_ancestral_sites` | `int64` | 38/38 | Invalid ancestral sites. |
| `estimated_array_bytes` | `int64` | 38/38 | Estimated array bytes. |
| `n_samples` | `int64` | 38/38 | N samples. |
| `n_cohorts` | `int64` | 38/38 | N cohorts. |
| `permutation_reps` | `int64` | 38/38 | Number of requested permutation replicates. |
| `base_seed` | `int64` | 38/38 | Base seed. |
| `chrom_seed` | `int64` | 38/38 | Chrom seed. |
| `gate_decision` | `str` | 38/38 | Gate decision. |
| `gate_observed_value` | `int64` | 38/38 | Gate observed value. |
| `gate_required_operator` | `str` | 38/38 | Gate required operator. |
| `gate_required_value` | `int64` | 38/38 | Gate required value. |
| `gate_denominator` | `int64` | 38/38 | Gate denominator. |
| `gate_decision_table_sha256` | `str` | 38/38 | Gate decision table sha256. |
| `gate_decision_validation_sha256` | `str` | 38/38 | Gate decision validation sha256. |
| `input_gerp_bed_sha256` | `str` | 38/38 | Input gerp bed sha256. |
| `input_rg_sha256` | `str` | 38/38 | Input rg sha256. |
| `input_phase4_chrom_load_sha256` | `str` | 38/38 | Input phase4 chrom load sha256. |
| `input_samples_sha256` | `str` | 38/38 | Input samples sha256. |
| `input_popmap_sha256` | `str` | 38/38 | Input popmap sha256. |
| `input_lengths_sha256` | `str` | 38/38 | Input lengths sha256. |
| `input_config_sha256` | `str` | 38/38 | Input config sha256. |
| `phase4_join_rows` | `int64` | 38/38 | Phase4 join rows. |
| `phase4_unmatched_rows` | `int64` | 38/38 | Phase4 unmatched rows. |
| `phase4_max_abs_burden_delta` | `float64` | 38/38 | Phase4 max abs burden delta. |
| `phase4_max_abs_copy_delta` | `int64` | 38/38 | Phase4 max abs copy delta. |
| `phase4_max_abs_genotype_call_delta` | `int64` | 38/38 | Phase4 max abs genotype call delta. |
| `status` | `str` | 38/38 | PASS, WARN, or FAIL validator status. |

## `results/tables/wolf_roh_localization_figure_values.tsv`

144 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `figure` | `str` | 144/144 | Figure. |
| `record_type` | `str` | 144/144 | Record type. |
| `panel` | `str` | 144/144 | Panel. |
| `POP` | `str` | 144/144 | POP. |
| `gerp_threshold` | `int64` | 144/144 | GERP RS cutoff defining the wolf load subset. |
| `roh_cutoff_mb` | `float64` | 144/144 | Minimum ROH length in megabases. |
| `estimate` | `float64` | 144/144 | Estimate. |
| `null_median` | `float64` | 144/144 | Null median. |
| `ci_low` | `float64` | 144/144 | Lower bound of the stated confidence interval. |
| `ci_high` | `float64` | 144/144 | Upper bound of the stated confidence interval. |
| `permutation_p_two_sided` | `float64` | 144/144 | Two-sided permutation p-value with plus-one correction. |
| `n_ind` | `int64` | 144/144 | N ind. |

## `results/tables/validation_wolf_roh_localization.tsv`

38 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `check` | `str` | 38/38 | Human-readable validation assertion. |
| `status` | `str` | 38/38 | PASS, WARN, or FAIL validator status. |
| `detail` | `str` | 38/38 | Machine-derived validation evidence. |

## `results/tables/peafowl_damage_effects.tsv`

8 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `analysis_id` | `str` | 8/8 | Stable identifier for one analysis result. |
| `variant_set` | `str` | 8/8 | All-SNP or damage-reduced transversion-only variant set. |
| `metric` | `str` | 8/8 | Diversity, estimator, or decision metric. |
| `basis` | `str` | 8/8 | Basis. |
| `museum_n` | `int64` | 8/8 | Museum n. |
| `modern_n` | `int64` | 8/8 | Modern n. |
| `rarefy_n` | `int64` | 8/8 | Rarefy n. |
| `n_sites` | `int64` | 8/8 | N sites. |
| `opportunity_bp` | `int64` | 8/8 | Opportunity bp. |
| `museum_value` | `float64` | 8/8 | Museum value. |
| `modern_value` | `float64` | 8/8 | Modern value. |
| `effect_museum_minus_modern` | `float64` | 8/8 | Museum value minus modern value on the metric scale. |
| `ci_pct` | `int64` | 8/8 | Confidence level in percent. |
| `ci_low` | `float64` | 8/8 | Lower bound of the stated confidence interval. |
| `ci_high` | `float64` | 8/8 | Upper bound of the stated confidence interval. |
| `bootstrap_reps` | `int64` | 8/8 | Number of requested bootstrap replicates. |
| `bootstrap_seed` | `int64` | 8/8 | Bootstrap seed. |
| `direction` | `str` | 8/8 | Sign classification of the reported effect. |
| `exact_permutation_p_two_sided` | `float64` | 8/8 | Two-sided p-value from all 462 label allocations. |
| `exact_permutation_percentile` | `float64` | 8/8 | Exact permutation percentile. |
| `n_exact_allocations` | `int64` | 8/8 | N exact allocations. |
| `equal_n_same_direction_n` | `int64` | 8/8 | Equal n same direction n. |
| `equal_n_cases_n` | `int64` | 8/8 | Equal n cases n. |
| `leave_one_same_direction_n` | `int64` | 8/8 | Leave one same direction n. |
| `leave_one_cases_n` | `int64` | 8/8 | Leave one cases n. |
| `equal_n_effect_min` | `float64` | 8/8 | Equal n effect min. |
| `equal_n_effect_max` | `float64` | 8/8 | Equal n effect max. |
| `leave_one_effect_min` | `float64` | 8/8 | Leave one effect min. |
| `leave_one_effect_max` | `float64` | 8/8 | Leave one effect max. |
| `geographic_mismatch_caveat` | `bool` | 8/8 | Whether geography remains confounded with collection period. |
| `same_direction_all_snp_vs_transversion` | `bool` | 8/8 | Same direction all snp vs transversion. |
| `museum_higher_concordant_metrics_n` | `int64` | 8/8 | Museum higher concordant metrics n. |
| `supports_temporal_erosion_upgrade` | `bool` | 8/8 | Global design-aware claim-upgrade decision. |

## `results/tables/peafowl_damage_permutations.tsv`

3,696 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `allocation_id` | `str` | 3696/3696 | Allocation id. |
| `museum_samples` | `str` | 3696/3696 | Museum samples. |
| `modern_samples` | `str` | 3696/3696 | Modern samples. |
| `is_observed_allocation` | `bool` | 3696/3696 | Is observed allocation. |
| `variant_set` | `str` | 3696/3696 | All-SNP or damage-reduced transversion-only variant set. |
| `metric` | `str` | 3696/3696 | Diversity, estimator, or decision metric. |
| `basis` | `str` | 3696/3696 | Basis. |
| `museum_n` | `int64` | 3696/3696 | Museum n. |
| `modern_n` | `int64` | 3696/3696 | Modern n. |
| `rarefy_n` | `int64` | 3696/3696 | Rarefy n. |
| `n_sites` | `int64` | 3696/3696 | N sites. |
| `museum_value` | `float64` | 3696/3696 | Museum value. |
| `modern_value` | `float64` | 3696/3696 | Modern value. |
| `effect_museum_minus_modern` | `float64` | 3696/3696 | Museum value minus modern value on the metric scale. |
| `direction` | `str` | 3696/3696 | Sign classification of the reported effect. |

## `results/tables/peafowl_damage_influence.tsv`

136 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `case_id` | `str` | 136/136 | Case id. |
| `case_type` | `str` | 136/136 | Case type. |
| `left_out_sample` | `str` | 136/136 | Left out sample. |
| `left_out_group` | `str` | 136/136 | Left out group. |
| `museum_samples` | `str` | 136/136 | Museum samples. |
| `modern_samples` | `str` | 136/136 | Modern samples. |
| `museum_n` | `int64` | 136/136 | Museum n. |
| `modern_n` | `int64` | 136/136 | Modern n. |
| `rarefy_n` | `int64` | 136/136 | Rarefy n. |
| `variant_set` | `str` | 136/136 | All-SNP or damage-reduced transversion-only variant set. |
| `metric` | `str` | 136/136 | Diversity, estimator, or decision metric. |
| `basis` | `str` | 136/136 | Basis. |
| `n_sites` | `int64` | 136/136 | N sites. |
| `museum_value` | `float64` | 136/136 | Museum value. |
| `modern_value` | `float64` | 136/136 | Modern value. |
| `effect_museum_minus_modern` | `float64` | 136/136 | Museum value minus modern value on the metric scale. |
| `direction` | `str` | 136/136 | Sign classification of the reported effect. |
| `same_direction_as_baseline` | `bool` | 136/136 | Same direction as baseline. |

## `results/tables/peafowl_damage_blocks.tsv`

2,076 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `basis` | `str` | 2076/2076 | Basis. |
| `variant_set` | `str` | 2076/2076 | All-SNP or damage-reduced transversion-only variant set. |
| `metric` | `str` | 2076/2076 | Diversity, estimator, or decision metric. |
| `chrom` | `str` | 2076/2076 | Chrom. |
| `block_index` | `int64` | 2076/2076 | Block index. |
| `block_start_bp` | `int64` | 2076/2076 | Block start bp. |
| `block_end_bp` | `int64` | 2076/2076 | Block end bp. |
| `opportunity_bp` | `int64` | 2076/2076 | Opportunity bp. |
| `n_sites` | `int64` | 2076/2076 | N sites. |
| `museum_sum` | `float64` | 2076/2076 | Museum sum. |
| `modern_sum` | `float64` | 2076/2076 | Modern sum. |
| `museum_n` | `int64` | 2076/2076 | Museum n. |
| `modern_n` | `int64` | 2076/2076 | Modern n. |
| `rarefy_n` | `int64` | 2076/2076 | Rarefy n. |
| `denominator` | `str` | 2076/2076 | Denominator. |

## `results/tables/peafowl_damage_classification.tsv`

16 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `basis` | `str` | 16/16 | Basis. |
| `input_path` | `str` | 16/16 | Input path. |
| `variant_class` | `str` | 16/16 | Variant class. |
| `n_records` | `int64` | 16/16 | N records. |
| `n_complete_11` | `int64` | 16/16 | N complete 11. |
| `n_incomplete_11` | `int64` | 16/16 | N incomplete 11. |
| `used_all_snp_records` | `int64` | 16/16 | Used all snp records. |
| `used_transversion_records` | `int64` | 16/16 | Used transversion records. |
| `n_samples` | `int64` | 16/16 | N samples. |
| `n_contigs_in_header` | `int64` | 16/16 | N contigs in header. |
| `genomic_opportunity_bp` | `int64` | 16/16 | Genomic opportunity bp. |

## `results/tables/peafowl_damage_figure_values.tsv`

144 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `panel` | `str` | 144/144 | Panel. |
| `series_id` | `str` | 144/144 | Series id. |
| `case_id` | `str` | 144/144 | Case id. |
| `case_type` | `str` | 144/144 | Case type. |
| `variant_set` | `str` | 144/144 | All-SNP or damage-reduced transversion-only variant set. |
| `metric` | `str` | 144/144 | Diversity, estimator, or decision metric. |
| `x_order` | `float64` | 144/144 | X order. |
| `label` | `str` | 144/144 | Label. |
| `estimate` | `float64` | 144/144 | Estimate. |
| `ci_low` | `float64` | 8/144 | Lower bound of the stated confidence interval. |
| `ci_high` | `float64` | 8/144 | Upper bound of the stated confidence interval. |
| `display_effect_pct_of_modern` | `float64` | 144/144 | Display effect pct of modern. |
| `display_ci_low_pct_of_modern` | `float64` | 8/144 | Display ci low pct of modern. |
| `display_ci_high_pct_of_modern` | `float64` | 8/144 | Display ci high pct of modern. |

## `results/tables/validation_peafowl_damage.tsv`

30 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `check` | `str` | 30/30 | Human-readable validation assertion. |
| `status` | `str` | 30/30 | PASS, WARN, or FAIL validator status. |
| `detail` | `str` | 30/30 | Machine-derived validation evidence. |

## `results/tables/peafowl_ne_design_replicates.tsv`

720 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `analysis_type` | `str` | 720/720 | Analysis type. |
| `scenario_id` | `str` | 720/720 | Scenario id. |
| `replicate` | `int64` | 720/720 | Replicate. |
| `true_ne` | `int64` | 720/720 | Known simulated effective population size; absent for empirical rows. |
| `truth_class` | `str` | 720/720 | Known side of the Ne=500 boundary; unknown for empirical rows. |
| `sample_size` | `int64` | 720/720 | Number of sampled diploid individuals. |
| `marker_density` | `int64` | 720/720 | Number of input SNP markers requested from currentNe2. |
| `seed` | `int64` | 720/720 | Seed. |
| `simulation_attempt` | `int64` | 720/720 | Simulation attempt. |
| `candidate_loci` | `int64` | 720/720 | Candidate loci. |
| `panel_seed` | `int64` | 720/720 | Panel seed. |
| `simulation_runtime_seconds` | `float64` | 720/720 | Simulation runtime seconds. |
| `simulation_generations` | `int64` | 720/720 | Simulation generations. |
| `initial_maf_low` | `float64` | 720/720 | Initial maf low. |
| `initial_maf_high` | `float64` | 720/720 | Initial maf high. |
| `input_vcf_sha256` | `str` | 720/720 | Input vcf sha256. |
| `marker_ids_sha256` | `str` | 720/720 | Marker ids sha256. |
| `sample_ids_sha256` | `str` | 720/720 | Sample ids sha256. |
| `command` | `str` | 720/720 | Command. |
| `exit_code` | `int64` | 720/720 | Exit code. |
| `timed_out` | `bool` | 720/720 | Timed out. |
| `runtime_seconds` | `float64` | 720/720 | Runtime seconds. |
| `raw_output_path` | `str` | 720/720 | Raw output path. |
| `raw_output_sha256` | `str` | 720/720 | Raw output sha256. |
| `log_path` | `str` | 720/720 | Log path. |
| `log_sha256` | `str` | 720/720 | Log sha256. |
| `parse_error` | `float64` | 0/720 | Parse error. |
| `execution_failure_reason` | `float64` | 0/720 | Execution failure reason. |
| `ne_point` | `float64` | 593/720 | Ne point. |
| `ci_low` | `float64` | 593/720 | Lower bound of the stated confidence interval. |
| `ci_high` | `float64` | 593/720 | Upper bound of the stated confidence interval. |
| `ci_width` | `float64` | 593/720 | Ci width. |
| `interval_covers_true` | `object` | 593/720 | Interval covers true. |
| `n_ind` | `int64` | 720/720 | N ind. |
| `n_snps` | `int64` | 720/720 | N snps. |
| `k` | `float64` | 593/720 | Estimated number of full-sibling counterparts for a randomly selected individual, as reported by currentNe2 for the chosen estimation basis. |
| `ne_basis` | `str` | 720/720 | Ne basis. |
| `converged` | `bool` | 720/720 | Converged. |
| `gbf_state` | `str` | 720/720 | Gbf state. |
| `outcome_class` | `str` | 720/720 | Outcome class. |
| `pilot_member` | `bool` | 720/720 | Pilot member. |
| `expansion_status` | `str` | 720/720 | Expansion status. |

## `results/tables/peafowl_ne_design_pilot.tsv`

240 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `analysis_type` | `str` | 240/240 | Analysis type. |
| `scenario_id` | `str` | 240/240 | Scenario id. |
| `replicate` | `int64` | 240/240 | Replicate. |
| `true_ne` | `int64` | 240/240 | Known simulated effective population size; absent for empirical rows. |
| `truth_class` | `str` | 240/240 | Known side of the Ne=500 boundary; unknown for empirical rows. |
| `sample_size` | `int64` | 240/240 | Number of sampled diploid individuals. |
| `marker_density` | `int64` | 240/240 | Number of input SNP markers requested from currentNe2. |
| `seed` | `int64` | 240/240 | Seed. |
| `simulation_attempt` | `int64` | 240/240 | Simulation attempt. |
| `candidate_loci` | `int64` | 240/240 | Candidate loci. |
| `panel_seed` | `int64` | 240/240 | Panel seed. |
| `simulation_runtime_seconds` | `float64` | 240/240 | Simulation runtime seconds. |
| `simulation_generations` | `int64` | 240/240 | Simulation generations. |
| `initial_maf_low` | `float64` | 240/240 | Initial maf low. |
| `initial_maf_high` | `float64` | 240/240 | Initial maf high. |
| `input_vcf_sha256` | `str` | 240/240 | Input vcf sha256. |
| `marker_ids_sha256` | `str` | 240/240 | Marker ids sha256. |
| `sample_ids_sha256` | `str` | 240/240 | Sample ids sha256. |
| `command` | `str` | 240/240 | Command. |
| `exit_code` | `int64` | 240/240 | Exit code. |
| `timed_out` | `bool` | 240/240 | Timed out. |
| `runtime_seconds` | `float64` | 240/240 | Runtime seconds. |
| `raw_output_path` | `str` | 240/240 | Raw output path. |
| `raw_output_sha256` | `str` | 240/240 | Raw output sha256. |
| `log_path` | `str` | 240/240 | Log path. |
| `log_sha256` | `str` | 240/240 | Log sha256. |
| `parse_error` | `float64` | 0/240 | Parse error. |
| `execution_failure_reason` | `float64` | 0/240 | Execution failure reason. |
| `ne_point` | `float64` | 198/240 | Ne point. |
| `ci_low` | `float64` | 198/240 | Lower bound of the stated confidence interval. |
| `ci_high` | `float64` | 198/240 | Upper bound of the stated confidence interval. |
| `ci_width` | `float64` | 198/240 | Ci width. |
| `interval_covers_true` | `object` | 198/240 | Interval covers true. |
| `n_ind` | `int64` | 240/240 | N ind. |
| `n_snps` | `int64` | 240/240 | N snps. |
| `k` | `float64` | 198/240 | Estimated number of full-sibling counterparts for a randomly selected individual, as reported by currentNe2 for the chosen estimation basis. |
| `ne_basis` | `str` | 240/240 | Ne basis. |
| `converged` | `bool` | 240/240 | Converged. |
| `gbf_state` | `str` | 240/240 | Gbf state. |
| `outcome_class` | `str` | 240/240 | Outcome class. |
| `pilot_member` | `bool` | 240/240 | Pilot member. |
| `expansion_status` | `str` | 240/240 | Expansion status. |
| `pilot_run` | `str` | 240/240 | Pilot run. |
| `pilot_batch_hash` | `str` | 240/240 | Pilot batch hash. |
| `repeatability_match` | `bool` | 240/240 | Repeatability match. |

## `results/tables/peafowl_ne_design_summary.tsv`

90 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `analysis_type` | `str` | 90/90 | Analysis type. |
| `population` | `str` | 30/90 | Population. |
| `true_ne` | `float64` | 60/90 | Known simulated effective population size; absent for empirical rows. |
| `truth_class` | `str` | 90/90 | Known side of the Ne=500 boundary; unknown for empirical rows. |
| `sample_size` | `int64` | 90/90 | Number of sampled diploid individuals. |
| `marker_density` | `int64` | 90/90 | Number of input SNP markers requested from currentNe2. |
| `reps_planned` | `int64` | 90/90 | Reps planned. |
| `n_attempted` | `int64` | 90/90 | N attempted. |
| `n_executed` | `int64` | 90/90 | N executed. |
| `n_execution_failure` | `int64` | 90/90 | N execution failure. |
| `execution_failure_rate` | `int64` | 90/90 | Fraction of attempts with an execution or parsing failure. |
| `execution_failure_ci_low` | `int64` | 90/90 | Execution failure ci low. |
| `execution_failure_ci_high` | `float64` | 90/90 | Execution failure ci high. |
| `n_converged` | `int64` | 90/90 | N converged. |
| `convergence_rate` | `float64` | 90/90 | Fraction of all attempts yielding a converged estimator result. |
| `convergence_ci_low` | `float64` | 90/90 | Convergence ci low. |
| `convergence_ci_high` | `float64` | 90/90 | Convergence ci high. |
| `n_correct_confident` | `int64` | 90/90 | N correct confident. |
| `correct_confident_rate` | `float64` | 90/90 | Fraction of attempts confidently on the correct side of Ne=500. |
| `correct_confident_ci_low` | `float64` | 90/90 | Correct confident ci low. |
| `correct_confident_ci_high` | `float64` | 90/90 | Correct confident ci high. |
| `n_incorrect_confident` | `int64` | 90/90 | N incorrect confident. |
| `incorrect_confident_rate` | `float64` | 90/90 | Fraction of attempts confidently on the wrong side of Ne=500. |
| `incorrect_confident_ci_low` | `float64` | 90/90 | Incorrect confident ci low. |
| `incorrect_confident_ci_high` | `float64` | 90/90 | Incorrect confident ci high. |
| `n_indeterminate` | `int64` | 90/90 | N indeterminate. |
| `indeterminate_rate` | `float64` | 90/90 | Fraction of attempts whose interval cannot resolve the Ne=500 decision. |
| `indeterminate_ci_low` | `float64` | 90/90 | Indeterminate ci low. |
| `indeterminate_ci_high` | `float64` | 90/90 | Indeterminate ci high. |
| `n_boundary_confident_pass` | `int64` | 90/90 | N boundary confident pass. |
| `boundary_confident_pass_rate` | `float64` | 90/90 | For true Ne=500 only, fraction of attempts with a confident GBF pass; never scored correct or incorrect. |
| `boundary_confident_pass_ci_low` | `float64` | 90/90 | Boundary confident pass ci low. |
| `boundary_confident_pass_ci_high` | `float64` | 90/90 | Boundary confident pass ci high. |
| `n_boundary_confident_fail` | `int64` | 90/90 | N boundary confident fail. |
| `boundary_confident_fail_rate` | `float64` | 90/90 | For true Ne=500 only, fraction of attempts with a confident GBF fail; never scored correct or incorrect. |
| `boundary_confident_fail_ci_low` | `float64` | 90/90 | Boundary confident fail ci low. |
| `boundary_confident_fail_ci_high` | `float64` | 90/90 | Boundary confident fail ci high. |
| `n_pass` | `int64` | 90/90 | N pass. |
| `pass_rate` | `float64` | 90/90 | Pass rate. |
| `pass_ci_low` | `float64` | 90/90 | Pass ci low. |
| `pass_ci_high` | `float64` | 90/90 | Pass ci high. |
| `n_fail` | `int64` | 90/90 | N fail. |
| `fail_rate` | `float64` | 90/90 | Fail rate. |
| `fail_ci_low` | `float64` | 90/90 | Fail ci low. |
| `fail_ci_high` | `float64` | 90/90 | Fail ci high. |
| `n_intervals` | `int64` | 90/90 | N intervals. |
| `n_interval_covers_true` | `int64` | 90/90 | N interval covers true. |
| `coverage_rate` | `float64` | 60/90 | Fraction of reported estimator intervals covering the known simulated truth, including unbounded intervals; n_unbounded_ci reports those intervals separately. |
| `coverage_ci_low` | `float64` | 60/90 | Coverage ci low. |
| `coverage_ci_high` | `float64` | 60/90 | Coverage ci high. |
| `n_unbounded_ci` | `int64` | 90/90 | N unbounded ci. |
| `mean_ci_width` | `float64` | 81/90 | Mean ci width. |
| `median_ci_width` | `float64` | 81/90 | Median ci width. |
| `median_ne_point` | `float64` | 81/90 | Median ne point. |
| `mean_runtime_seconds` | `float64` | 90/90 | Mean runtime seconds. |
| `total_runtime_seconds` | `float64` | 90/90 | Total runtime seconds. |
| `monte_carlo_ci_pct` | `int64` | 90/90 | Monte carlo ci pct. |
| `expansion_status` | `str` | 90/90 | Expansion status. |

## `results/tables/peafowl_ne_design_empirical.tsv`

180 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `analysis_type` | `str` | 180/180 | Analysis type. |
| `empirical_id` | `str` | 180/180 | Empirical id. |
| `population` | `str` | 180/180 | Population. |
| `observed_n` | `int64` | 180/180 | Observed n. |
| `sample_size` | `int64` | 180/180 | Number of sampled diploid individuals. |
| `marker_density` | `int64` | 180/180 | Number of input SNP markers requested from currentNe2. |
| `replicate` | `int64` | 180/180 | Replicate. |
| `seed` | `int64` | 180/180 | Seed. |
| `subset_seed` | `int64` | 180/180 | Subset seed. |
| `subset_reused` | `bool` | 180/180 | Subset reused. |
| `sample_ids` | `str` | 180/180 | Sample ids. |
| `sample_ids_sha256` | `str` | 180/180 | Sample ids sha256. |
| `input_vcf_sha256` | `str` | 180/180 | Input vcf sha256. |
| `marker_ids_sha256` | `str` | 180/180 | Marker ids sha256. |
| `command` | `str` | 180/180 | Command. |
| `exit_code` | `int64` | 180/180 | Exit code. |
| `timed_out` | `bool` | 180/180 | Timed out. |
| `runtime_seconds` | `float64` | 180/180 | Runtime seconds. |
| `raw_output_path` | `str` | 180/180 | Raw output path. |
| `raw_output_sha256` | `str` | 180/180 | Raw output sha256. |
| `log_path` | `str` | 180/180 | Log path. |
| `log_sha256` | `str` | 180/180 | Log sha256. |
| `parse_error` | `float64` | 0/180 | Parse error. |
| `execution_failure_reason` | `float64` | 0/180 | Execution failure reason. |
| `ne_point` | `float64` | 73/180 | Ne point. |
| `ci_low` | `float64` | 73/180 | Lower bound of the stated confidence interval. |
| `ci_high` | `float64` | 73/180 | Upper bound of the stated confidence interval. |
| `ci_width` | `float64` | 73/180 | Ci width. |
| `n_ind` | `int64` | 180/180 | N ind. |
| `n_snps` | `int64` | 180/180 | N snps. |
| `k` | `float64` | 49/180 | Estimated number of full-sibling counterparts for a randomly selected individual, as reported by currentNe2 for the chosen estimation basis. |
| `ne_basis` | `str` | 180/180 | Ne basis. |
| `converged` | `bool` | 180/180 | Converged. |
| `gbf_state` | `str` | 180/180 | Gbf state. |
| `outcome_class` | `str` | 180/180 | Outcome class. |

## `results/tables/peafowl_ne_design_figure_values.tsv`

390 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `panel` | `str` | 390/390 | Panel. |
| `analysis_type` | `str` | 390/390 | Analysis type. |
| `population` | `str` | 150/390 | Population. |
| `true_ne` | `float64` | 240/390 | Known simulated effective population size; absent for empirical rows. |
| `truth_class` | `str` | 390/390 | Known side of the Ne=500 boundary; unknown for empirical rows. |
| `sample_size` | `int64` | 390/390 | Number of sampled diploid individuals. |
| `marker_density` | `int64` | 390/390 | Number of input SNP markers requested from currentNe2. |
| `metric` | `str` | 390/390 | Diversity, estimator, or decision metric. |
| `value` | `float64` | 390/390 | Value. |
| `ci_low` | `float64` | 390/390 | Lower bound of the stated confidence interval. |
| `ci_high` | `float64` | 390/390 | Upper bound of the stated confidence interval. |
| `n_attempted` | `int64` | 390/390 | N attempted. |
| `target_outcome` | `str` | 390/390 | Target outcome. |

## `results/tables/validation_peafowl_ne_design.tsv`

36 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `check_id` | `str` | 36/36 | Check id. |
| `status` | `str` | 36/36 | PASS, WARN, or FAIL validator status. |
| `details` | `str` | 36/36 | Details. |

## `results/tables/phase5b_optional_decisions.tsv`

2 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `section` | `float64` | 2/2 | CGplan section governed by the row. |
| `study` | `str` | 2/2 | Study. |
| `decision` | `str` | 2/2 | Gate outcome; negative and deferred outcomes are valid scientific results. |
| `gate_metric` | `str` | 2/2 | Gate metric. |
| `observed_value` | `int64` | 2/2 | Observed numeric gate value. |
| `secondary_observed_value` | `float64` | 2/2 | Secondary observed value. |
| `required_operator` | `str` | 2/2 | Comparison operator in the predeclared gate. |
| `required_value` | `int64` | 2/2 | Predeclared numeric threshold. |
| `denominator` | `int64` | 2/2 | Denominator. |
| `unit` | `str` | 2/2 | Unit. |
| `evidence` | `str` | 2/2 | Evidence. |
| `source_trace` | `str` | 2/2 | Source trace. |
| `reopen_condition` | `str` | 2/2 | Exact evidence condition that would reopen or change the decision. |
| `scientific_boundary` | `str` | 2/2 | Scientific boundary. |

## `results/tables/phase5b_annotation_inventory.tsv`

10 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `definition` | `str` | 10/10 | Definition. |
| `scope` | `str` | 10/10 | Scope. |
| `annotation_class` | `str` | 10/10 | Annotation class. |
| `n_unique_sites` | `int64` | 10/10 | N unique sites. |
| `duplicate_site_keys` | `int64` | 10/10 | Duplicate site keys. |
| `source_file` | `str` | 10/10 | Source file. |

## `results/tables/validation_phase5b_decisions.tsv`

7 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `check` | `str` | 7/7 | Human-readable validation assertion. |
| `status` | `str` | 7/7 | PASS, WARN, or FAIL validator status. |
| `detail` | `str` | 7/7 | Machine-derived validation evidence. |

## `results/tables/phase5b_claim_trace.tsv`

6 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `claim_id` | `str` | 6/6 | Claim id. |
| `section` | `str` | 6/6 | CGplan section governed by the row. |
| `headline` | `str` | 6/6 | Headline. |
| `claim_status` | `str` | 6/6 | Claim status. |
| `estimate` | `str` | 6/6 | Estimate. |
| `uncertainty` | `str` | 6/6 | Uncertainty. |
| `result_table` | `str` | 6/6 | Result table. |
| `result_filter` | `str` | 6/6 | Result filter. |
| `provenance` | `str` | 6/6 | Provenance. |
| `validator` | `str` | 6/6 | Validator. |
| `report_anchor` | `str` | 6/6 | Report anchor. |
| `explorer_anchor` | `str` | 6/6 | Explorer anchor. |
| `workflow_rule` | `str` | 6/6 | Workflow rule. |
| `source_trace` | `str` | 6/6 | Source trace. |
| `change_operator` | `str` | 6/6 | Change operator. |
| `change_threshold` | `object` | 6/6 | Change threshold. |
| `observed_value` | `int64` | 6/6 | Observed numeric gate value. |
| `unit` | `str` | 6/6 | Unit. |
| `what_changes_mind` | `str` | 6/6 | What changes mind. |
| `scientific_boundary` | `str` | 6/6 | Scientific boundary. |

## `results/tables/phase5b_fragility_scorecard.tsv`

4 rows.

| column | type | complete | definition |
|---|---|---:|---|
| `conclusion_id` | `str` | 4/4 | Conclusion id. |
| `section` | `str` | 4/4 | CGplan section governed by the row. |
| `classification` | `str` | 4/4 | Classification. |
| `conclusion` | `str` | 4/4 | Conclusion. |
| `settings_supporting` | `int64` | 4/4 | Settings supporting. |
| `settings_tested` | `int64` | 4/4 | Settings tested. |
| `dominant_uncertainty` | `str` | 4/4 | Dominant uncertainty. |
| `evidence_needed` | `str` | 4/4 | Evidence needed. |
| `machine_result` | `str` | 4/4 | Machine result. |
