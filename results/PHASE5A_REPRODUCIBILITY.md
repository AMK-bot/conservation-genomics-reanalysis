# Phase 5A — clean-clone/local-data reproducibility record

- **Status: PASS**
- **Full run result:** **SUCCESS — 162/162 Snakemake jobs completed; 0 failed**
- **Scientific gates:** **32 PASS, 12 WARN, 0 FAIL** across Phases 1–4
- **Scorecard gate:** **10 PASS, 0 FAIL**
- **Application smoke:** **PASS — 3 tests, return code 0**

This record covers the Phase-5A local completion gate. It uses the already verified public-data
deposits and source-built tools cached on the same Apple M1 / 8 GB laptop. It does not claim a
forced redownload, a different machine, or a public deployment.

## Full clean-clone run

| field | recorded value |
|---|---|
| clean clone | `/tmp/cg-phase5a-clone2.dTPBLP/repo` |
| source revision | `88892d76bbd85346107c69fe97afd957c710c8e6` |
| fresh runtime-source cache | `/tmp/cg-phase5a-source-cache2.IzAcKF` |
| started | 2026-07-18 14:06:55 +07 |
| finished | 2026-07-18 14:53:06 +07 |
| elapsed | 46 minutes 11 seconds |
| Snakemake result | 162/162 jobs completed successfully; 0 failed |
| run log | `.snakemake/log/2026-07-18T140655.661313.snakemake.log` inside the clone |

Exact command, run from the clean-clone root:

```bash
~/opt/anaconda3/bin/conda run -n congen --no-capture-output \
  snakemake -s workflow/Snakefile \
  phase1 phase2 phase3 phase4 phase5a1 \
  render_report_html render_research_brief app_smoke \
  --cores 4 --forceall --rerun-incomplete --rerun-triggers mtime \
  --runtime-source-cache-path /tmp/cg-phase5a-source-cache2.IzAcKF
```

The clean clone used local-data links rather than duplicating large archives:

- peafowl deposit directories/files were linked individually (`Modern_genomic_dataset_all`,
  `Modern_genomic_dataset_unlinked_neutral`, `raw`, GFF, and reference FASTA);
- `data/peafowl/intermediates` remained inside the clone, so generated files could not alter the
  source worktree;
- the verified wolf deposit was linked at `data/wolf`;
- the pinned, source-built `currentNe2` and `GONE2` tool directories were linked under `tools/`.

## What the clean run caught and how it was resolved

The first clean-clone attempt at revision `d2d6cbdf919dabc68d9b5fb03d50bde1199ee7dc`
stopped at 31/162 jobs. `diversity_perpop` raised `ModuleNotFoundError: No module named 'numpy'`
because a macOS Framework `python3` executable preceded the activated conda environment on `PATH`.
Workflow rules now invoke the activated environment's `python`; the same diversity step passed in
the fresh clone at 14:15:44, and the full run then succeeded.

The successful run also exposed that upstream GONE2 used its recorded `-S 42` seed for the optimizer
but not for the earlier locus shuffle. That made the context trajectory vary while leaving the
currentNe2 cube and GBF verdict unchanged. Revision
`ce80205` patches the pinned GONE2 build recipe to seed both stages, pins the report date, and
normalizes generated HTML whitespace. Two independent forced GONE2 runs then matched byte for byte:

| deterministic artifact | SHA-256 |
|---|---|
| `results/tables/gone2_trajectory.tsv` | `7cd8f5dc844281bc7b1519ac25f344acecfdf2d1fa73a00905d3cc1c6f182e5e` |
| `results/figures/gone2_trajectory.png` | `eb731d5ae6f0dcfb8e7b5bff07b18374f75f00c0ad8b7c6730709462db877d5d` |
| twice-rendered `report/report.html` | `c2e5b5ebca848ace6afe2edb0ed47679ff1d7fca3147b2bef4404acd262c101c` |

The canonical GONE2 context curve is approximately 3,577 at generation 417 to 176 recently. It is
still labelled context-only and does not feed the contemporary-$N_e$ badge or GBF calculation.

## Reproduced validation summary

| gate | PASS | WARN | FAIL | interpretation |
|---|---:|---:|---:|---|
| Phase 1 | 7 | 3 | 0 | QC, structure, diversity, and temporal contrast valid |
| Phase 2 | 9 | 3 | 0 | 12-row currentNe2 cube and context outputs valid |
| Phase 3 | 9 | 3 | 0 | GBF indicators and robustness tables reconcile |
| Phase 4 | 7 | 3 | 0 | wolf load/ROH outputs and source anchor reconcile |
| Phase 5A.1 | 10 | 0 | 0 | scorecard reconciles with Phases 2–4 |

The 12 WARN rows are reported-not-asserted biological findings and caveats, not failed checks.
After the deterministic correction, a 105-job affected-output consistency pass completed every
scientific job and the 3-test app smoke successfully. The report target initially encountered only a
Codex sandbox denial for Quarto's user-library kernel log; the isolated rerun with normal log access
completed, and two identical-input renders produced the same hash above.

The final source-tree reconciliation then ran `snakemake -s workflow/Snakefile all --cores 4` and
completed the only three pending DAG actions (NeEstimator input refresh, final Phase-5A validation,
and the aggregate `all` target). A dry-run using the brand-new source cache
`/tmp/cg-final-dryrun-cache` at 15:42:05 +07 returned:

```text
Nothing to be done (all requested files are present and up to date).
```

## Completion claim

The full clean-clone/local-data Snakemake run successfully produced the tracked cube, tables,
figures, fragility scorecard, self-contained research brief, report, and app smoke evidence. All
scientific and scorecard validators have **0 FAIL**. No remaining required Phase-5A work needs new
hardware, an external researcher, fieldwork, an ML model, or a publication process.
