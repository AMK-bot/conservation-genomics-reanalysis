# tools/ — built from source (not on bioconda/osx-64)

Built locally with the Xcode Command Line Tools (clang). Build artifacts are
git-ignored; this README is the build record.

## currentNe2  *(the N_e workhorse)*
Contemporary N_e from LD, **no genetic map required** → ideal for the peafowl sweep.
C++; build with `make`. Drives the Snakemake fragility cube (plan §5).

## GONE2  *(recent-trajectory context only)*
Recent-N_e trajectory. **Context only** — GBF guidance excludes it from the
contemporary N_e indicator.

## NeEstimator v2  *(manual cross-check only)*
Java GUI, not scriptable → used only to cross-check currentNe2's LD-N_e. Not part of
the automated DAG.

> Build commands are recorded here once the source URLs are confirmed and compiled
> on this machine (Phase 0).
