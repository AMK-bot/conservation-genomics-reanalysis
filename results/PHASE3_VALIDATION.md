# Phase 3 — validation report

Asserts the GBF indicator tables are **well-formed** and **reconcile with the cube** they derive from, and **reports** the scientific result (0/3 pass, PM, verdict fragility) without over-asserting it — the honest fragility finding.

| check | status | detail |
|---|---|---|
| gbf_ne500 has one row per preset | **PASS** | presets=['lenient', 'standard', 'strict'] vs config ['lenient', 'standard', 'strict'] |
| ne500 counts sum to n_pops | **PASS** | pass+fail+indeterminate == n_pops (all rows) |
| ne500 fraction_pass = n_pass/n_pops | **PASS** | fraction matches its counts (all rows) |
| ne500 counts reconcile with the cube | **PASS** | lenient: cube 0 pass/1 indet; standard: cube 0 pass/2 indet; strict: cube 0 pass/3 indet |
| robustness has one row per population | **PASS** | ['Thailand', 'Vietnam', 'Yunnan'] |
| robustness `stable` flag correct | **PASS** | stable == (verdict identical across presets) |
| PM band brackets headline and is in [0,1] | **PASS** | headline=0.7, band=0.7-0.7 |
| PM per-country flags in {yes,no,swing} | **PASS** | flags=['no', 'yes'] |
| summary has headline indicator keys | **PASS** | all present |
| N_e>500 fraction pass (per_population) | **WARN** | lenient: 0/3 pass, 1 indet; standard: 0/3 pass, 2 indet; strict: 0/3 pass, 3 indet |
| Populations Maintained | **WARN** | PM=0.7 (band 0.7-0.7) |
| verdict fragility across presets | **WARN** | 2/3 populations change verdict across presets (estimates preset-fragile; the angle-C finding) |

**0 FAIL**, 3 WARN (reported-not-asserted), 9 PASS.

**N_e>500 indicator (per preset):**

```
filter_preset  n_pops  n_pass  n_fail  n_indeterminate  fraction_pass  fraction_not_fail  ne_threshold
      lenient       3       0       2                1            0.0              0.333           500
     standard       3       0       1                2            0.0              0.667           500
       strict       3       0       0                3            0.0              1.000           500
```

**Robustness (angle C — verdict across presets):**

```
population       lenient      standard        strict  stable
  Thailand          fail indeterminate indeterminate   False
   Vietnam indeterminate indeterminate indeterminate    True
    Yunnan          fail          fail indeterminate   False
```
