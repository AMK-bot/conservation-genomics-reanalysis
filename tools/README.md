# tools/ — built from source (not on bioconda/osx-64)

Build artifacts are git-ignored; reproduce them with **`scripts/build_tools.sh`**
(requires `conda activate congen` for libomp + Xcode CLT). Built 2026-06-18 on
Apple M1, **x86_64** (to match the osx-64 env), linking the env's `libomp` via rpath.

## currentNe2  *(the N_e workhorse)* — ✅ built
`github.com/esrud/currentNe2` @ **`4ee170d`** (pinned). Contemporary N_e from LD, **no
genetic map required** → drives the Snakemake fragility cube (plan §5).
**Build note:** Apple clang rejects one VLA brace-initialization
(`int valid_idx[contaloc2] = {0};`, line ~1682); `build_tools.sh` rewrites it to a
plain VLA + zero-loop. Compiled `-std=c++14 -O3 -Xpreprocessor -fopenmp`.

## GONE2  *(recent-trajectory context only)* — ✅ built
`github.com/esrud/GONE2` @ **`5896504`** (pinned). Recent-N_e trajectory; **context only** — GBF guidance
excludes it from the contemporary N_e indicator. Built via its `macos` Makefile
target with the env's libomp (`make macos`), `-std=c++11`.

## NeEstimator v2  *(manual cross-check only)* — not built
Java GUI, not scriptable → planned as an optional manual comparison with currentNe2's
LD-N_e, but not built or run. Not part of the automated DAG.
