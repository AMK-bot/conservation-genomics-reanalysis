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

- **Reproducible repo** — one-command reproduction (`snakemake --use-conda`), pinned
  `environment.yml` + `renv.lock`, the Snakefile, a config of all thresholds, the
  results cube, all figures, and a paper-grade `report/report.qmd`.
- **Fragility explorer** (`app/streamlit_app.py`) — a live tool whose three knobs
  (filtering stringency × N_e method × structure modeled/ignored) wiggle the peafowl
  N_e / GBF pass-fail verdict in real time.

## One-command reproduction (target)

```bash
conda env create -f environment.yml      # build the osx-64 toolchain
conda activate congen
Rscript -e 'renv::restore()'             # restore pinned R packages
snakemake --use-conda --cores 4          # build results/cube/results_cube.parquet
streamlit run app/streamlit_app.py       # explore the verdict
```

## Layout

```
config/      ALL filtering thresholds, N_e settings, paths (config.yaml)
workflow/    Snakefile + rules/ (qc, structure, ne, gbf, load) — builds the results cube
scripts/     python/ + R/ analysis scripts called by the rules
results/      cube/ (results_cube.parquet) + tables/ + figures/
app/          streamlit_app.py — the fragility explorer (reads the cube)
report/       report.qmd — paper-grade methods/results/limitations
data/         raw VCFs + intermediates (symlinked to USB; see data/README.md)
tools/        currentNe2 / GONE2 (built from source) — see tools/README.md
```

See **CGplan.md** for the full execution plan and **SETUP.md** for environment setup
status. Project status: **Phase 0 (setup & verification).**
