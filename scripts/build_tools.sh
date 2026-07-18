#!/usr/bin/env bash
# Build the N_e tools from source into tools/ (Apple Silicon / osx-64 via Rosetta).
# Reproducible build record for currentNe2 + GONE2 (both git-ignored under tools/).
#
# Requires: the congen env ACTIVE (provides libomp) + Xcode CLT (clang++).
#   conda activate congen
#   scripts/build_tools.sh
#
# NeEstimator v2 is a Java GUI (manual cross-check only) and is NOT built here.
set -euo pipefail

PREFIX="${CONDA_PREFIX:?activate the env first: conda activate congen}"
TOOLS="$(cd "$(dirname "$0")/.." && pwd)/tools"
# macOS clang + libomp incantation, compiled x86_64 to match the osx-64 env:
OMP="-Xpreprocessor -fopenmp -I$PREFIX/include -L$PREFIX/lib -lomp -Wl,-rpath,$PREFIX/lib"

echo "== currentNe2 (N_e workhorse) =="
# pinned commit for reproducibility (built + verified 2026-06-19)
if [ ! -d "$TOOLS/currentNe2" ]; then
  git clone https://github.com/esrud/currentNe2 "$TOOLS/currentNe2"
  git -C "$TOOLS/currentNe2" checkout 4ee170d369fbf7b4111b4d44b689fe7ae15d40c0
fi
cd "$TOOLS/currentNe2"
# Apple clang rejects VLA brace-initialization; rewrite the one offending line (idempotent).
if grep -q 'int valid_idx\[contaloc2\] = {0};' currentne2.cpp; then
  perl -0pi -e 's/  int valid_idx\[contaloc2\] = \{0\};/  int valid_idx[contaloc2];\n  for (int _zi = 0; _zi < contaloc2; _zi++) valid_idx[_zi] = 0;  \/\/ clang: VLA can'\''t be brace-initialized/' currentne2.cpp
fi
# Shrink the 4 GB static genotype array (char indi[MAXIND][MAXLOCI]) to sizes our data needs.
# Upstream builds with -mcmodel=medium for the 4 GB BSS; build_tools.sh dropped that flag, so on
# x86_64 the small code model can't address it -> segfault on EVERY run (not just large data).
# 22 peafowl, <=1.05M loci -> MAXIND 64 / MAXLOCI 1,100,000 keeps it ~70 MB and 8 GB-safe. (idempotent)
sed -i.bak -E 's/^#define MAXIND 2000$/#define MAXIND 64/; s/^#define MAXLOCI 2000000$/#define MAXLOCI 1100000/' currentne2.cpp && rm -f currentne2.cpp.bak
# Deterministic RNG: seed mt19937 from a fixed value (was std::random_device) so the seeded -s SNP
# subsampling is REPRODUCIBLE (the cube must re-run identically). (idempotent)
perl -0pi -e 's/std::mt19937 g\(rd\(\)\);\n  g\.seed\(rd\(\)\);/std::mt19937 g(42);  \/\/ fixed seed -> reproducible -s subsampling (was rd())\n  g.seed(42);/' currentne2.cpp
# Fail loudly if any patch silently no-op'd (upstream source drifted) — a missed RNG patch would
# make -s subsampling non-deterministic, breaking the "cube re-runs identically" guarantee.
grep -q 'g.seed(42)'            currentne2.cpp || { echo "ERROR: RNG-seed patch did not apply (source drifted?)"; exit 1; }
grep -q '#define MAXLOCI 1100000' currentne2.cpp || { echo "ERROR: MAXLOCI patch did not apply"; exit 1; }
grep -q '#define MAXIND 64'     currentne2.cpp || { echo "ERROR: MAXIND patch did not apply"; exit 1; }
clang++ -arch x86_64 -std=c++14 -O3 -w $OMP -o currentne2 currentne2.cpp lib/*.cpp
echo "  -> $TOOLS/currentNe2/currentne2"

echo "== GONE2 (recent-trajectory context only) =="
if [ ! -d "$TOOLS/GONE2" ]; then
  git clone https://github.com/esrud/GONE2 "$TOOLS/GONE2"
  git -C "$TOOLS/GONE2" checkout 5896504c8f0f870debf274c1499ee4e491a4116e
fi
cd "$TOOLS/GONE2"
# Upstream's -S option seeds the optimizer RNG, but the earlier SNP/locus shuffle is
# initialized independently from std::random_device. Re-seed that mt19937 after
# HandleInput has parsed -S so a recorded GONE2 command reproduces the same trajectory.
# The guard keeps this source patch idempotent when build_tools.sh is run again.
if ! grep -q 'deterministic -S locus shuffle' gone2.cpp; then
  perl -0pi -e 's/  HandleInput\(argc, argv, &params\);/  HandleInput(argc, argv, \&params);\n\n  g.seed(static_cast<std::mt19937::result_type>(params.semilla));  \/\/ deterministic -S locus shuffle/' gone2.cpp
fi
grep -q 'deterministic -S locus shuffle' gone2.cpp || { echo "ERROR: GONE2 RNG-seed patch did not apply"; exit 1; }
make macos CC='clang++ -arch x86_64' MAC_FLAGS="-w $OMP -std=c++11"
echo "  -> $TOOLS/GONE2/gone2"

echo "== verify =="
file "$TOOLS/currentNe2/currentne2" "$TOOLS/GONE2/gone2"
