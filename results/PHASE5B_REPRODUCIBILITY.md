# Phase 5B reproducibility record

**Status: PASS**

**Science no-op dry-run: PASS**

**No-op dry-run: PASS**

## Scope

PASS records the verified science target, two isolated executions, reconciled validators, matching
scientific hashes, frozen-input manifests, and the canonical full-release target as a no-op.

The seven persisted science-validator TSVs reconcile to 169 PASS, 0 WARN, and 0 FAIL. The
release-content audit reconciles to 42 PASS, 0 WARN, and 0 FAIL in the promoted state.

## Reproduction commands

Science execution and dry-run:

```bash
snakemake --snakefile workflow/Snakefile phase5b_science --cores 4 --resources mem_mb=7000
snakemake --snakefile workflow/Snakefile phase5b_science --cores 4 --resources mem_mb=7000 --dry-run
```

Science dry-run result: Nothing to be done (all requested files are present and up to date).

Canonical root-level release command:

```bash
snakemake --snakefile workflow/Snakefile phase5b --cores 4 --resources mem_mb=7000
snakemake --snakefile workflow/Snakefile phase5b --cores 4 --resources mem_mb=7000 --dry-run
```

Canonical dry-run result: Nothing to be done (all requested files are present and up to date).

## Isolated-workspace method and resource evidence

Both disposable workspaces were initialized without generated Phase-5B outputs and each completed a
95-job clean science execution. After release preflight exposed a host-specific executable path in
runtime provenance, the final 101-file source inventory at the science-verification freeze was
synchronized to both workspaces and all affected dependencies were recomputed in place. The
correction records the portable `tabix` command token while retaining the exact executable SHA-256;
it does not alter the localization scientific hash. At that freeze, the workspace and both isolated
copies had identical 101-file source inventories.

The run table records wrapper telemetry for the two 95-job clean executions. Subsequent
dependency-driven final-source reconciliations are not folded into those clean-execution timing or
RSS measurements; the validator counts and hashes below were collected only after every
reconciliation. Peak RSS is aggregate process-tree RSS converted from KiB to MiB and remained below
the declared 7000-MB workflow budget.

### Post-verification admissions revision

After the science-verification freeze, the admissions brief was expanded from two pages to a
four-page, project-wide research journey. This presentation-only revision adds four deterministic
local SVG diagrams, restructures the narrative and CSS, synchronizes release-facing copy, and
strengthens the delivery validator's page contract. It does not change frozen scientific inputs,
result tables, provenance scientific hashes, decisions, or the clean-run evidence below. The current
main-workspace release is rebuilt and revalidated; the isolated workspaces remain historical
science-verification evidence rather than mirrors of this later presentation layer.

| run_id | started_at | ended_at | elapsed_seconds | jobs | return_code | peak_rss_mb |
|---|---|---|---:|---:|---:|---:|
| isolated_run_1 | 2026-07-19T07:02:02.081Z | 2026-07-19T08:26:54.506Z | 5092.426 | 95 | 0 | 1053.102 |
| isolated_run_2 | 2026-07-19T08:47:24.479Z | 2026-07-19T10:10:21.987Z | 4977.509 | 95 | 0 | 1104.035 |

## Validator reconciliation

Each row was counted independently from the corresponding persisted TSV after final-source
reconciliation.

| validator | pass | warn | fail |
|---|---:|---:|---:|
| results/tables/validation_wolf_robustness.tsv | 24 | 0 | 0 |
| results/tables/validation_peafowl_damage.tsv | 30 | 0 | 0 |
| results/tables/validation_peafowl_ne_design.tsv | 36 | 0 | 0 |
| results/tables/validation_phase5b_core_integration.tsv | 14 | 0 | 0 |
| results/tables/validation_phase5b_decisions.tsv | 7 | 0 | 0 |
| results/tables/validation_wolf_roh_localization.tsv | 38 | 0 | 0 |
| results/tables/validation_phase5b.tsv | 20 | 0 | 0 |

## Scientific-hash reconciliation

Runtime-bearing provenance uses stored runtime-excluded scientific hashes. Deterministic tabular
artifacts use whole-file SHA-256. The workspace column denotes the main workspace after its final
science refresh; run 1 denotes its post-reconciliation state.

| component | artifact | hash_method | workspace_science_sha256 | run_1_science_sha256 | run_2_science_sha256 |
|---|---|---|---|---|---|
| wolf_froh_load_association | results/provenance/wolf_froh_load.json | json_pointer:/scientific_hash | 0d179e62439cd33b99a9562a71b4ac7116e7f33a051c2c6eea99522208c0eecb | 0d179e62439cd33b99a9562a71b4ac7116e7f33a051c2c6eea99522208c0eecb | 0d179e62439cd33b99a9562a71b4ac7116e7f33a051c2c6eea99522208c0eecb |
| peafowl_damage_falsification | results/tables/peafowl_damage_effects.tsv | file_sha256 | a938aeb0d0b1a7b21716ee89bae98b744b1360534cca5ae99c602d8a4a759bd5 | a938aeb0d0b1a7b21716ee89bae98b744b1360534cca5ae99c602d8a4a759bd5 | a938aeb0d0b1a7b21716ee89bae98b744b1360534cca5ae99c602d8a4a759bd5 |
| peafowl_ne_scenario | results/provenance/peafowl_ne_design.json | json_pointer:/scientific_hashes/scenario_runtime_excluded_sha256 | c512a5bdde92fa4e719620d80eaaff7e4988e578f2774067b7bc699c24279f39 | c512a5bdde92fa4e719620d80eaaff7e4988e578f2774067b7bc699c24279f39 | c512a5bdde92fa4e719620d80eaaff7e4988e578f2774067b7bc699c24279f39 |
| peafowl_ne_empirical | results/provenance/peafowl_ne_design.json | json_pointer:/scientific_hashes/empirical_runtime_excluded_sha256 | d19c0b9b1caf0b4c2884ca8066c3dd93e1c45f035a08be76d87347ffc8cb0950 | d19c0b9b1caf0b4c2884ca8066c3dd93e1c45f035a08be76d87347ffc8cb0950 | d19c0b9b1caf0b4c2884ca8066c3dd93e1c45f035a08be76d87347ffc8cb0950 |
| wolf_roh_localization | results/provenance/wolf_roh_localization.json | json_pointer:/scientific_hash | 5822727e0cc5a6f91f9eeeb836bd1bb5a0b195315d0dbca590ba1695fb15ea05 | 5822727e0cc5a6f91f9eeeb836bd1bb5a0b195315d0dbca590ba1695fb15ea05 | 5822727e0cc5a6f91f9eeeb836bd1bb5a0b195315d0dbca590ba1695fb15ea05 |
| phase5b_synthesis | results/tables/phase5b_claim_trace.tsv | file_sha256 | cb202673a0f85ad7162b164f87edd20cd940c3e673e2164ba82b983cdacb4c33 | cb202673a0f85ad7162b164f87edd20cd940c3e673e2164ba82b983cdacb4c33 | cb202673a0f85ad7162b164f87edd20cd940c3e673e2164ba82b983cdacb4c33 |

## Frozen-input manifests

Each digest below is the SHA-256 of canonical, path-sorted `file_sha256`, two-space, `path`, newline
records. The persisted TSV header is excluded from the aggregate.

| manifest_class | entries | workspace_sha256 | run_1_sha256 | run_2_sha256 | status |
|---|---:|---|---|---|---|
| frozen_upstream_inputs | 123 | 8ac4e5f69221a1dfd245af1b67ba97502dbdac5fd53140095ac7d45b376f3740 | 8ac4e5f69221a1dfd245af1b67ba97502dbdac5fd53140095ac7d45b376f3740 | 8ac4e5f69221a1dfd245af1b67ba97502dbdac5fd53140095ac7d45b376f3740 | PASS |
| external_source_leaves | 7 | 5714afb526b82b81aa2d95a8563cbec6e6b334874734cbfb84c797e37a88a737 | 5714afb526b82b81aa2d95a8563cbec6e6b334874734cbfb84c797e37a88a737 | 5714afb526b82b81aa2d95a8563cbec6e6b334874734cbfb84c797e37a88a737 | PASS |

## Release, browser, and package verification

The canonical target completed in the main workspace and both isolated workspaces after the final
science-source reconciliation. Each exact canonical dry-run then reported that all requested files
were present and up to date. At that freeze, the rendered report and then-current research brief were
byte-identical across the three workspaces. The later four-page admissions revision is intentionally
verified in the current main-workspace release rather than retrofitted into the historical clean
science workspaces. The release-content, website, bundle, delivery, application-smoke, and Phase-5A
gates reported their declared passing totals; the promoted release-content state is 42 PASS, 0 WARN,
and 0 FAIL.

Interactive browser verification exercised all four no-install scientific panels at their defaults
and at changed assumptions, all deliverable filters and searches, the six claim traces, the image
lightbox, lazy-loaded figures, and the self-contained report. The normal site had no horizontal
overflow or console errors. Missing generated data disabled all 11 controls while preserving the six
static claim summaries, and a missing graphical abstract produced one accessible fallback message
while the other 10 images decoded. The browser security policy did not permit a `file://` navigation;
the direct-file case was instead closed by the delivery validator's exact local-reference audit.

The archive passed CRC and path-safety preflight, exact `MANIFEST.sha256` coverage for every
non-manifest member, local dependency closure, and the extracted website's 27-check validation. A
fresh loopback-served extraction loaded the local Phase-5B payload and returned the same changed-row
explorer values as the workspace site. Deterministic package construction is verified again after
this final record is synchronized so that the attested record itself is part of the tested input set.

## Scientific findings and boundaries

- Section 13.1: all 15 primary and all 15 generic-homozygosity-controlled realized-load
  associations had cohort-bootstrap confidence intervals entirely above zero. These are
  associations among genomic proxies, not measurements of fitness, inbreeding depression, or
  causation.
- Section 13.2: 0 of 15 simulated sample-size and marker designs met the predeclared two-sided
  decision-resolution rule. The neutral scenarios calibrate this pipeline and do not prescribe a
  guaranteed empirical sampling design.
- Section 13.3: 1 of 4 diversity metrics retained a museum-higher direction through all numerical
  damage and individual-influence checks. Geography remains confounded with collection period, so
  the comparison does not support a temporal interpretation; diversity is not fitness.
- Section 13.4: the localization gate was IMPLEMENT. At the predeclared 1.5-Mb cutoff, 24 of 24
  population-by-GERP cells exceeded the circular-shift null upper bound with two-sided permutation
  p at most 0.05. This is spatial colocalization of genomic proxies, not demonstrated mechanism,
  phenotypic consequence, fitness evidence, or causation. Denominators are eligible calls at
  assayed SNP records rather than callable genomic bases.
- Section 13.5: the local deposited annotation inventory matched the source analysis with a
  211-of-211 common-sample intersection, but supplied 0 annotation definitions independent of that
  source against a threshold of at least 1. The evidence-backed decision is
  DEFER_DUPLICATES_SOURCE_STUDY.
- Section 13.6: machine-readable result tables, provenance, validator traces, report anchors,
  explorer anchors, and workflow-rule links expose the findings and their stated boundaries.

## Verified science-stage deliverables

Verified artifacts include the association, damage-falsification, Ne-design, localization,
optional-decision, and six-claim synthesis tables; their provenance JSON; all seven validator TSVs;
and the two exact-path persisted manifests. The canonical target governs synchronized presentation,
delivery checks, and deterministic package construction during final release verification.
