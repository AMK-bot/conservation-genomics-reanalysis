# Conservation Genomics Reanalysis

Assessing genetic status across the modern conservation-genomics toolkit — from the
new global biodiversity-treaty (GBF) indicators on an endangered SE Asian bird, to
realized-vs-masked genetic load in an inbred carnivore — and showing **how fragile
each verdict is to analyst choices**.

Two chapters:

1. **Green peafowl** (*Pavo muticus*) — GBF indicators, contemporary N_e, robustness,
   population structure, temporal erosion (museum vs modern). Dryad
   `10.5061/dryad.ffbg79ctc`.
2. **Scandinavian wolf** (*Canis lupus*) — genetic load (realized vs masked) and ROH
   inbreeding history. Dryad `10.5061/dryad.7m0cfxpzj`.

## Deliverables

- **Reproducible repo** — one-command reproduction (`snakemake --cores N`), pinned
  `environment.lock.yml` (R packages included — R is conda-owned), the Snakefile, a
  config of all thresholds, the results cube, all figures, and a paper-grade `report/report.qmd`.
- **Fragility explorer** (`app/streamlit_app.py`) — a live tool whose three knobs
  (filtering stringency × N_e method × structure modeled/ignored) wiggle the peafowl
  N_e / GBF pass-fail verdict in real time.

## Reproduction

```bash
# Build the osx-64 toolchain. Classic conda OOM-kills on 8 GB RAM — use micromamba.
CONDA_SUBDIR=osx-64 micromamba create -p "$(conda info --base)/envs/congen" -f environment.yml
conda activate congen                    # env lives in the anaconda envs dir
scripts/build_tools.sh                   # compile currentNe2 + GONE2 (pinned commits)
scripts/fetch_data.sh && scripts/extract_data.sh   # Dryad data (needs DRYAD_CLIENT_ID/SECRET)
snakemake --cores 4                      # build results/cube/results_cube.parquet
streamlit run app/streamlit_app.py       # explore the verdict
```

R packages (SNPRelate / dartR / hierfstat / adegenet) ship with the conda env — **R is
conda-owned** (renv not used); for exact pins use `environment.lock.yml`.

## Layout

```
config/      ALL filtering thresholds, N_e settings, paths (config.yaml)
workflow/    Snakefile + rules/ (qc, structure, ne, gbf, load) — builds the results cube
scripts/     python/ + R/ analysis scripts called by the rules
results/      cube/ (results_cube.parquet) + tables/ + figures/
app/          streamlit_app.py — the fragility explorer (reads the cube)
report/       report.qmd — paper-grade methods/results/limitations
data/         raw VCFs + intermediates (symlinked to internal SSD; see data/README.md)
tools/        currentNe2 / GONE2 (built from source) — see tools/README.md
```

See **CGplan.md** for the full execution plan and **SETUP.md** for environment setup
status. Project status: **Phase 0 complete → Phase 1 (peafowl QC → structure → diversity).**
