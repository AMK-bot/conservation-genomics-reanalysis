# scripts/R/

R analysis scripts called by the Snakemake rules (targeted learning goal).
SNPRelate (PCA/GDS), dartR, hierfstat (F-statistics, diversity).
R and its packages are pinned in the conda-owned `environment.lock.yml`; there is no
project `renv.lock`. Workflow rules use `Rscript --vanilla` so the active environment is
the only package source.
