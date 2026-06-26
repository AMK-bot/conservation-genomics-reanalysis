# Phase 2 — validation report

Asserts the cube is **well-formed** (shape/schema/states/inf) and **reports** the scientific direction (Wahlund bias, GBF fraction) without over-asserting it — at n = 7/10/5 most verdicts are indeterminate/fail *by design* (the fragility thesis).

| check | status | detail |
|---|---|---|
| cube has 12 rows | **PASS** | got 12, expected 12 = 3 presets x (3 pops + 1 pooled) |
| schema columns present | **PASS** | all present |
| every preset has 3 per_population + 1 pooled(ALL) | **PASS** | all presets complete |
| ne_method == [currentNe2] | **PASS** | got ['currentNe2'] |
| gbf_state in {pass,fail,indeterminate} | **PASS** | got ['fail', 'indeterminate'] |
| ne_basis matches convergence | **PASS** | 7 cross_chromosome (headline), 0 whole_genome (fallback), 5 non-converged (basis=none) |
| unbounded upper CIs stored as inf | **WARN** | 0/12 cells have ci_high = inf (expected at n=7/10/5) |
| pass/fail cells have a point estimate | **PASS** | ok |
| Wahlund direction (pooled vs per-pop) | **WARN** | lenient: pooled=52 vs per-pop median=76; standard: pooled=89 vs per-pop median=88 |
| GBF fraction N_e>500 (per_population) | **WARN** | lenient: 0/3 pass, 1 indeterminate; standard: 0/3 pass, 2 indeterminate; strict: 0/3 pass, 3 indeterminate |
| GONE2 context trajectory present | **PASS** | results/tables/gone2_trajectory.tsv ok |
| metapop -x cross-check table present | **PASS** | results/tables/ne_metapop_xcheck.tsv present |

**0 FAIL**, 3 WARN (reported-not-asserted), 9 PASS.

**Cube (per-population rows feed the GBF fraction; pooled = ALL is the Wahlund contrast, never a GBF input):**

```
filter_preset structure_mode population  ne_method  ne_point  ci_low  ci_high  n_ind  n_snps    k         ne_basis     gbf_state
      lenient per_population   Thailand currentNe2     75.60   17.87   319.79      5   25000  NaN cross_chromosome          fail
      lenient per_population    Vietnam currentNe2   2292.80  139.09 37794.98     10   25000 0.00 cross_chromosome indeterminate
      lenient per_population     Yunnan currentNe2     55.32   20.10   152.26      7   25000  NaN cross_chromosome          fail
      lenient         pooled        ALL currentNe2     52.00   33.54    80.61     22   25000 0.00 cross_chromosome          fail
     standard per_population   Thailand currentNe2       NaN     NaN      NaN      5   25000  NaN             none indeterminate
     standard per_population    Vietnam currentNe2       NaN     NaN      NaN     10   25000  NaN             none indeterminate
     standard per_population     Yunnan currentNe2     88.40   26.92   290.31      7   25000 0.00 cross_chromosome          fail
     standard         pooled        ALL currentNe2     88.80   50.68   155.61     22   25000 1.54 cross_chromosome          fail
       strict per_population   Thailand currentNe2       NaN     NaN      NaN      5   22911  NaN             none indeterminate
       strict per_population    Vietnam currentNe2       NaN     NaN      NaN     10   25000  NaN             none indeterminate
       strict per_population     Yunnan currentNe2       NaN     NaN      NaN      7   25000  NaN             none indeterminate
       strict         pooled        ALL currentNe2    107.78   64.52   180.07     22   25000  NaN cross_chromosome          fail
```
