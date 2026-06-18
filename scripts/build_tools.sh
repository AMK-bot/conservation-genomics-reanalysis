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
[ -d "$TOOLS/currentNe2" ] || git clone --depth 1 https://github.com/esrud/currentNe2 "$TOOLS/currentNe2"
cd "$TOOLS/currentNe2"
# Apple clang rejects VLA brace-initialization; rewrite the one offending line (idempotent).
if grep -q 'int valid_idx\[contaloc2\] = {0};' currentne2.cpp; then
  perl -0pi -e 's/  int valid_idx\[contaloc2\] = \{0\};/  int valid_idx[contaloc2];\n  for (int _zi = 0; _zi < contaloc2; _zi++) valid_idx[_zi] = 0;  \/\/ clang: VLA can'\''t be brace-initialized/' currentne2.cpp
fi
clang++ -arch x86_64 -std=c++14 -O3 -w $OMP -o currentne2 currentne2.cpp lib/*.cpp
echo "  -> $TOOLS/currentNe2/currentne2"

echo "== GONE2 (recent-trajectory context only) =="
[ -d "$TOOLS/GONE2" ] || git clone --depth 1 https://github.com/esrud/GONE2 "$TOOLS/GONE2"
cd "$TOOLS/GONE2"
make macos CC='clang++ -arch x86_64' MAC_FLAGS="-w $OMP -std=c++11"
echo "  -> $TOOLS/GONE2/gone2"

echo "== verify =="
file "$TOOLS/currentNe2/currentne2" "$TOOLS/GONE2/gone2"
