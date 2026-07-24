# Conservation Genomics Reanalysis

Assessing genetic status across the modern conservation-genomics toolkit — from the
new global biodiversity-treaty (GBF) indicators on an endangered SE Asian bird, to
realized-vs-masked genetic load in an inbred carnivore — and showing **how fragile
each verdict is to analyst choices**.

Two chapters:

1. **Green peafowl** (*Pavo muticus*) — GBF indicators, contemporary N_e, robustness,
   population structure, and a damage-aware museum–modern comparison that remains geographically
   confounded. Dryad `10.5061/dryad.ffbg79ctc`.
2. **Scandinavian wolf** (*Canis lupus*) — GERP-weighted load proxies (realized vs masked) and
   map-limited ROH autozygosity proxies. Dryad `10.5061/dryad.7m0cfxpzj`.

**[Open the complete project website](index.html)** — the admissions-facing summary, evidence gallery,
searchable deliverable library, reproducibility record, and links to every public artifact. It is a
dependency-free static site and works offline.

**Sendable website bundle:** `dist/conservation-genomics-portfolio.zip`. Phase 5B is the current,
cleanly verified release; its two isolated builds, bounded-memory evidence, science-hash comparison,
and no-op proof are recorded in [`results/PHASE5B_REPRODUCIBILITY.md`](results/PHASE5B_REPRODUCIBILITY.md).

**Personalize the website without editing HTML:** double-click `EDIT_WEBSITE.command`, click an
outlined heading or paragraph in the live preview, and choose **Save website text**. Keep the
Terminal window open while editing and press `Ctrl+C` when finished. Undo, restore-original, and
JSON import/export controls are included; scientific results, decision gates, links, figures, and
generated Phase-5B evidence remain locked. See [`EDIT_WEBSITE.md`](EDIT_WEBSITE.md).

## Understand the project in 60 seconds

![Graphical abstract: two public genome datasets are stress-tested across defensible analyst choices to separate robust conclusions from sensitive magnitudes.](admissions/graphical_abstract.svg)

- **Question:** do conservation-genomics conclusions survive defensible analyst choices, or does
  the reading move when filtering, population structure, GERP site classes, or ROH definitions move?
- **Green peafowl:** no sampled population confidently clears the GBF $N_e>500$ target under any
  filtering preset. The headline is robust, but population estimates and even estimator convergence
  are fragile at n = 7/10/5. In Phase 5B, **0/15** simulated sample-size × marker-density designs
  resolved both predeclared resolution truths ($N_e=250$ and $N_e=1{,}000$), so the study does not
  support an empirical sample prescription;
  only **1/4** museum–modern diversity metrics survived every damage and influence check, with
  geography still confounded and no upgrade to temporal-erosion language.
- **Scandinavian wolf:** all **15/15** predeclared GERP × ROH cells support a positive partial
  realized-load association after the generic-homozygosity control. This is association between
  genomic proxies, not fitness, individual harm, or causal inbreeding depression. The authorized
  §13.4 localization found **24/24** predeclared population × GERP cells at the 1.5-Mb cutoff beyond
  the circular-shift null; that is genomic colocalization, not a phenotypic or causal result.
- **Optional annotation study:** §13.5 is
  **`DEFER_DUPLICATES_SOURCE_STUDY`** because 0/1 independent annotation definitions were available
  and the local classes overlap the source study for 211/211 samples.
- **Contribution:** a config-driven Snakemake reanalysis, fail-closed scientific decision gates,
  and a read-only explorer that makes uncertainty visible instead of forcing uncertain estimates
  into pass/fail.
- **Boundary:** this demonstrates genomic-proxy association, conservation relevance, and analytical
  sensitivity, not measured fitness, inbreeding depression, individual harm, or a new field estimate.

Admissions-ready path: [project website](index.html) · [four-page project-wide illustrated brief](admissions/research_brief.html) ·
[research journey](RESEARCH_JOURNEY.md) · [interview notes](INTERVIEW_NOTES.md) ·
[2–3 minute demo script](admissions/demo_script.md) · [offline technical report](report/report.html)

## Deliverables

- **Reproducible repo** — one-command Phase-5B reproduction
  (`snakemake --snakefile workflow/Snakefile phase5b --cores 4 --resources mem_mb=7000`), pinned
  `environment.lock.yml` (R packages included — R is conda-owned), the Snakefile, a
  config of all thresholds, the results cube, all figures, and a paper-grade `report/report.qmd`.
- **Fragility explorer** (`app/streamlit_app.py`) — a live tool whose two knobs
  (filtering stringency × structure modeled/ignored) move the peafowl $N_e$ estimates and
  three-state per-population reading in real time; the pooled result is shown only as a cautionary
  structure contrast. The explorer also presents both GBF Goal-A indicators, a robustness
  matrix, and a GONE2 recent-trajectory context panel. (The N_e-method knob was dropped
  in Phase 2 — GONE2 measures a different time horizon, so it is context, not an axis.)
  Phase-5B panels add the peafowl damage falsification and scenario-based $N_e$ design landscape,
  plus the wolf individual-association and ROH-localization surfaces.
- **Static project website** (`index.html`) — an offline-readable portfolio with the scientific
  summary, visual evidence, searchable deliverable explanations, complete artifact index, and
  reproduction instructions. Its separate localhost editor changes only allowlisted narrative text
  and stores personalization outside the HTML. Validate both with
  `python scripts/python/validate_website.py`.
- **Sendable website bundle** (`dist/conservation-genomics-portfolio.zip`) — a deterministic,
  self-contained ZIP of the site and every local dependency/deliverable. Rebuild and verify it with
  `snakemake --snakefile workflow/Snakefile package_website --cores 4 --resources mem_mb=7000`, so
  Snakemake passes the complete fail-closed artifact inventory to the packager.

## Reproduction

```bash
# Build the pinned osx-64 toolchain. Classic conda OOM-kills on 8 GB RAM — use micromamba.
CONDA_SUBDIR=osx-64 micromamba create -n congen -f environment.lock.yml
micromamba activate congen
scripts/build_tools.sh                   # compile currentNe2 + GONE2 (pinned commits)
scripts/fetch_data.sh && scripts/extract_data.sh   # Dryad data (needs DRYAD_CLIENT_ID/SECRET)
snakemake --snakefile workflow/Snakefile phase5b --cores 4 --resources mem_mb=7000
streamlit run app/streamlit_app.py       # explore the verdict

# Optional explicit post-reproduction checks:
python -m unittest discover -s tests -v
report/render_report.sh
```

R packages (SNPRelate / dartR / hierfstat / adegenet) ship with the conda env — **R is
conda-owned** (renv not used); for exact pins use `environment.lock.yml`.

For release maintainers creating a reproducibility record from an otherwise record-free checkout,
`phase5b_science` is the non-release aggregate used in two isolated workspaces to collect real
timing, return-code, RSS, validator, and science-hash evidence. After writing that evidence to
`results/PHASE5B_REPRODUCIBILITY.md`, the canonical `phase5b` target above performs the synchronized
rendering, record validation, offline packaging, and delivery gate. The first-release bridge is
explicit: `SCIENCE_PASS` produces one release-content WARN until the canonical no-op is observed;
promotion to `PASS` requires that distinct no-op proof and returns the final gate to zero WARN.
Ordinary reproduction uses only the canonical `phase5b` command.

## Layout

```
config/      ALL filtering thresholds, N_e settings, paths (config.yaml)
workflow/    Snakefile + rules/ (qc, structure, ne, gbf, load) — builds the results cube
scripts/     python/ + R/ analysis scripts called by the rules
results/      cube/ (results_cube.parquet) + tables/ + figures/
app/          streamlit_app.py — the fragility explorer (reads the cube)
report/       report.qmd — paper-grade methods/results/limitations
website/      static-site CSS, JavaScript, favicon, and preview notes (entry point: index.html)
dist/         sendable, validated project-website ZIP
data/         raw VCFs + intermediates (symlinked to internal SSD; see data/README.md)
tools/        currentNe2 / GONE2 (built from source) — see tools/README.md
```

See **PROJECT_STATUS.md** for the current phase table, **CGplan.md** for the full execution plan,
and **SETUP.md** for environment setup status. **Phase 5B status: COMPLETE.** Sections 13.1, 13.2,
13.3, 13.4, and 13.6 are complete; §13.5 records the
evidence-backed `DEFER_DUPLICATES_SOURCE_STUDY` decision, with reopening requiring at least one
independent definition, at least 0.95 common-sample coverage, and at least 0.90 auditable
callable-denominator coverage. The synchronized report, explorer, static site, manifest, offline ZIP,
and release gates all pass; see the [clean verification record](results/PHASE5B_REPRODUCIBILITY.md).
