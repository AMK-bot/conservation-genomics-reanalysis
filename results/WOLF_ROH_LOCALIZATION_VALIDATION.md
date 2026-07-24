# Wolf ROH-localization validation

Acceptance status: **PASS** (38/38 checks passed).

The validation independently rebuilds raw ROH unions, checks eligible SNP-genotype burden partitions and Phase-4 reconciliation, directly re-parses VCF/GERP/RG assignment for six chromosomes and three deterministic individuals per cohort, independently reconstructs sampled raw circular-shift null allocations, recomputes cohort summaries, and verifies deterministic collation.

| Check | Status | Detail |
|---|---:|---|
| all ROH-localization inputs and final artifacts exist | **PASS** | 20 required paths |
| all 38 chromosome observed/null/QC intermediates exist | **PASS** | 114 files |
| validated §13.4 offline decision explicitly authorizes IMPLEMENT | **PASS** | decision=IMPLEMENT; observed=15 >= 12; decision validation PASS=7/7 |
| final provenance directly hashes the validated implementation gate | **PASS** | gate provenance present=True |
| frozen localization design is the declared 38 x 211 x 3 x 5 grid | **PASS** | chromosomes=38, individuals=211, thresholds=[2.0, 3.0, 4.0], cutoffs=[0.1, 0.5, 1.0, 1.5, 2.0], reps=199 |
| predeclared callable-opportunity circular-shift null is retained | **PASS** | seed=1304, null=within_chromosome_circular_roh_shift, denominator=eligible_polarized_gerp_threshold_snp_genotype_calls |
| Phase-4 load and F_ROH source cubes are complete and unique | **PASS** | load rows=633, ROH rows=1055, duplicate keys=0/0 |
| chromosome intermediate schemas and cardinalities | **PASS** | expected rows/file observed=3165, null=23880; schema_ok=True, cardinality_ok=True |
| chromosome burden/copy/call partitions are nonnegative and exact | **PASS** | 38 observed and null chromosome partitions checked |
| chromosome worker seeds and implementation-gate hashes independently reproduce | **PASS** | base_seed=1304; derivation=sha256(base_seed\|chromosome\|CHROM); gate=IMPLEMENT |
| chromosome null failures are explicitly represented | **PASS** | allowed statuses=ok/nonconvergent; every failure requires a reason |
| each chromosome reconciles to Phase-4 raw load totals | **PASS** | max absolute deltas burden/copies/calls=0/0/0 |
| individual table has the complete 211 x 3 x 5 cube | **PASS** | rows=3165, unique keys=3165, expected=3165 |
| individual eligible-genotype denominators and enrichment arithmetic are exact | **PASS** | max derived-metric delta=0; failures=0 |
| inside plus outside reconciles exactly to genome-wide Phase-4 load | **PASS** | max absolute deltas burden/copies/calls=2.33e-10/0/0 |
| genome-wide totals are invariant across the five ROH cutoffs | **PASS** | non-invariant groups=0 |
| raw RG coordinates independently pass 1-based-inclusive audits | **PASS** | records=224538; audit failures=0 |
| raw RG unions independently reproduce every individual/cutoff result | **PASS** | max deltas n/raw/union/overlap=0/0/0/0 |
| independent RG coverage reconciles exactly to Phase-4 F_ROH | **PASS** | max deltas F_ROH/n_ROH/span_Mb=0/0/0 |
| independent raw VCF/GERP/RG audit reproduces interval-assigned opportunity and burden | **PASS** | chromosomes=['1', '8', '16', '23', '31', '38'] (6/38); individuals=24/211 (3/cohort); cells=2160; VCF records=1444294; AA REF/ALT=656375/189752; max integer/burden delta=0/1.53e-10 |
| independent raw circular-shift audit reproduces sampled chromosome null rows | **PASS** | chromosomes=['1', '38']; cohorts=['1983-1990', '2007-2014S', 'Russia']; individuals=49; replicates={'1': 120, '38': 172}; cohort cells=90/90; individual-grid assignments=1470; wrapped interval-cutoff assignments=125; max integer/burden delta=0/5.62e-08; metadata_ok=True; comparisons_ok=True |
| final null table contains all 199 replicates for all 8 x 3 x 5 cells | **PASS** | rows=23880/23880; cells=120; incomplete=0 |
| circular-shift null preserves totals and reports every failure | **PASS** | partition_ok=True; failed rows=0 |
| each null replicate preserves cohort opportunity, copies, and burden | **PASS** | max absolute deltas calls/copies/burden=0/0/7.45e-09 |
| cohort table contains the complete 8 x 3 x 5 grid | **PASS** | rows=120/120; duplicate cells=0 |
| cohort observed values independently aggregate from individuals | **PASS** | maximum aggregate delta=0 |
| cohort null medians, intervals, and two-sided permutation p-values independently reproduce | **PASS** | maximum summary delta=0; invalid p-values=0 |
| all 38 chromosome QC rows pass coordinates, reconciliation, seed, and memory checks | **PASS** | rows=38, PASS=38; max memory=493,647,093 bytes |
| chromosome QC hashes every raw GERP/ROH/Phase-4 worker input | **PASS** | hash columns=7; chromosomes=38 |
| figure-values table exactly reproduces cohort cells for ribbon and forest | **PASS** | ribbon=120/120, forest=24/24, max delta=0, labels_ok=True |
| forest and ribbon are valid nontrivial PNGs | **PASS** | forest=(2700, 1170),113226B; ribbon=(2880, 1026),249735B |
| provenance records settings, denominator semantics, claim boundary, and coordinates | **PASS** | settings_ok=True, counts_ok=True, tabix_ok=True, opportunity_ok=True, analysis=wolf_roh_localized_realized_burden |
| provenance exposes all per-chromosome raw source hashes | **PASS** | declared chromosomes=38/38 |
| scientific hash independently reproduces from deterministic TSV bytes | **PASS** | calculated=5822727e0cc5a6f91f9eeeb836bd1bb5a0b195315d0dbca590ba1695fb15ea05; declared=5822727e0cc5a6f91f9eeeb836bd1bb5a0b195315d0dbca590ba1695fb15ea05 |
| provenance input and output SHA-256 hashes reconcile | **PASS** | output mismatches=[]; input mismatches=[] |
| independent-null seed and allocation perturbation regressions pass | **PASS** | returncode=0 |
| synthetic coordinate, circular-shift, nested-cutoff, and gate tests pass | **PASS** | returncode=0 |
| deterministic temporary re-collation | **PASS** | returncode=0; byte mismatches=[]; hash_ok=True; stderr_tail=W20260719 23:43:36.240873 0x203429240 cpu_info.cc:242] IOError: sysctlbyname failed for 'hw.optional.avx512vl'. Detail: [errno 1] Operation not permitted |

Claim boundary: localization is genomic mechanistic support only; it is not a measured fitness effect, individual harm estimate, or causal inbreeding-depression result. The opportunity denominator counts eligible calls at assayed SNP records, not callable genomic bases, so ascertainment remains.
