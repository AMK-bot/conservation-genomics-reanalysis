# scripts/python/

Python analysis scripts called by the Snakemake rules (user's strength).
scikit-allel supports PCA, diversity, and chromosome-localized wolf calculations; pandas supports
cube assembly, validation, and the report/explorer data contracts. The Streamlit smoke runner and
static-website tools keep the communication layer reproducible as well as the analyses.

## Phase 5B execution contract

`workflow/rules/phase5b.smk` encodes the locked CGplan Section 13 order through validator TSVs used
as dependencies. A failed validator stops the next section of the DAG:

1. **13.1 — wolf robustness:** `wolf_froh_load_robustness.py` evaluates the frozen GERP-threshold ×
   ROH-cutoff surface, bootstrap/permutation uncertainty, the generic-homozygosity control, and rank
   stability. `validate_wolf_robustness.py` independently reconciles its tables, figures, and
   provenance.
2. **13.3 — peafowl damage falsification:** `peafowl_damage_falsification.py` compares the all-SNP
   and transversion-only analyses, exact temporal-label allocations, block uncertainty, equal-size
   rarefaction, and leave-one-individual-out influence. `validate_peafowl_damage.py` independently checks
   the classifications, allocations, uncertainty, figures, and provenance.
3. **13.2 — peafowl effective-population-size design:** `peafowl_ne_design.py` runs the bounded,
   seeded pilot/repeat/expansion simulations and empirical rarefactions through the local
   `currentNe2` executable, retaining failures as results. The known-truth calibration uses an
   explicit ideal monoecious diploid Wright–Fisher pedigree with shared parental genomes, 32
   one-Morgan chromosomes, Haldane recombination, nested panels, and n=5 ascertainment. Empirical
   loci must be strictly more than 80% called for each subset. `validate_peafowl_ne_design.py`
   independently replays the pedigree, VCF bytes, strict missingness boundary, estimator parser,
   decision rule, summaries, and restart manifest rather than importing analysis helpers.
4. **13.6 — core communication gate:** `phase5b_core_integration.py` freezes the three core numeric
   claim contracts and their question → prediction → stress test → result → correction → falsifier
   → conservation-consequence paths. `validate_phase5b_core_integration.py` reconciles those claims
   with the analysis tables and checks their report, explorer, and static-site implementations.
5. **Optional-study gate:** `phase5b_optional_decisions.py` applies the predeclared 13.4 reopening
   threshold and records the evidence-bounded 13.5 implementation/deferral decision plus annotation
   inventory. `validate_phase5b_decisions.py` checks both decisions numerically. The final decisions
   are §13.4 **`IMPLEMENT`** and §13.5 **`DEFER_DUPLICATES_SOURCE_STUDY`**. A deferral is a valid
   scientific output; it is not converted into a positive claim.
6. **13.4 — wolf ROH localization, only if authorized:** `wolf_roh_localization.py chromosome`
   streams one autosome at a time after the validated gate says `IMPLEMENT`. Its `collate` command
   reconciles all 38 partitions, estimates the within-chromosome circular-shift null, and produces
   individual/cohort tables and figures. `validate_wolf_roh_localization.py` independently audits
   interval coordinates, eligible polarized GERP-threshold SNP-genotype partitions, null
   replicates, Phase 4 reconciliation, figures, and provenance. Its separate bcftools text parser
   also recomputes raw VCF/GERP/ROH assignment for six spaced chromosomes and three deterministic
   individuals per cohort (all 3 × 5 cells), without analysis helpers. This is an assayed-variant
   opportunity denominator, not callable genomic bases.
7. **Final scientific synthesis:** `phase5b_synthesis.py` assembles the claim trace, fragility
   scorecard, data dictionary, and local browser payload without selecting or upgrading scientific
   results. `validate_phase5b.py` is the numeric, traceability, report, explorer, and offline-data
   scientific gate. `validate_phase5b_release_content.py` separately checks synchronized release
   surfaces and the clean reproducibility record; the rendered-site, deterministic-package, and
   delivery checks then close the release contract.

Analysis products are machine-readable TSVs with explicit uncertainty and JSON provenance; their
paired validators emit a TSV gate and a Markdown audit. Their presence alone is not evidence of a
successful run—consult the applicable validator and require zero `FAIL` rows.

## Current scientific outcome

**Phase 5B status: COMPLETE.** The frozen results and their clean-build evidence are recorded in
[`results/PHASE5B_REPRODUCIBILITY.md`](../../results/PHASE5B_REPRODUCIBILITY.md); the upstream
release-content gate and downstream delivery gate emit `results/PHASE5B_RELEASE_CONTENT_VALIDATION.md`
and `results/PHASE5B_DELIVERY_VALIDATION.md` respectively. The frozen scientific outcomes are:

- **13.1 wolf association:** 15/15 predeclared cells have positive group-adjusted partial
  realized-load bootstrap intervals. This is association between genomic proxies, not fitness,
  individual harm, or causal inbreeding depression.
- **13.2 peafowl $N_e$ design:** 0/15 sample-size × marker-density designs resolve both predeclared
  resolution truths ($N_e=250$ and $N_e=1{,}000$), so the scenario analysis does not establish an
  empirical sample prescription.
- **13.3 damage falsification:** 1/4 museum–modern diversity metrics is fully robust; geography
  remains confounded and the result is not upgraded to temporal erosion.
- **13.4 localization:** the `IMPLEMENT` gate was followed. At the predeclared 1.5-Mb cutoff,
  24/24 population × GERP cells are beyond the circular-shift null rule. This is genomic
  colocalization, not a fitness, harm, or causal result.
- **13.5 annotation triangulation:** `DEFER_DUPLICATES_SOURCE_STUDY`; 0/1 independent annotation
  definitions are available and the common sample intersection is 211/211. Reopening requires at
  least one independent definition, at least 0.95 common-sample coverage, and at least 0.90 auditable
  callable-denominator coverage.
- **13.6 core integration:** the scientific communication contract, synchronized rendering,
  deterministic offline packaging, and delivery validation are complete.

## Running Phase 5B

From the repository root in the locked project environment:

```bash
snakemake --snakefile workflow/Snakefile phase5b --cores 4 --resources mem_mb=7000
```

Do not omit the `mem_mb` resource limit for a laptop run. Each 13.4 chromosome job is deliberately
single-threaded but reserves two scheduler cores and 3,500 MB, so four cores admit at most two such
workers and the declared concurrent memory stays at 7,000 MB (below the 8-GB ceiling). Collation and
validation run as single jobs. If Snakemake cannot write its default cache, set a writable cache
location, for example `XDG_CACHE_HOME=/tmp/cg-snake-cache`, before the same command.

The 38 regenerable localization partitions are written under
`results/wolf/localization/chr*.observed.tsv`, `chr*.null.tsv`, and `chr*.qc.tsv`. They make the
calculation restartable and auditable without loading the whole genome at once. They are not needed
by website recipients and are excluded from the sendable ZIP; the collated tables, figures,
provenance, and validation records are the portable deliverables.

The N_e branch is restartable at individual estimator attempts. Publicly auditable sanitized
raw/log copies, row checkpoints, private exact-execution copies, and panel timing sidecars live under
`results/ne/design/`; Snakemake declares only the atomically-last
`results/ne/design/CACHE_MANIFEST.json` as its internal completion marker. A cache row is reused only
when its regenerated input/sample/marker hashes, seed and panel bindings, binary/settings hashes,
raw parser state, and logs reconcile. Mismatches are quarantined and rerun. The entire cache tree and
manifest are regenerable private audit material and are intentionally excluded from the sendable ZIP;
the collated tables, figure, provenance, and validator are public deliverables.

The `phase5b` target runs only from local inputs and bounded local simulations. Fetching public raw
data and building third-party tools are separate setup operations documented at the repository
root.
