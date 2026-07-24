#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

QUARTO_BIN="$(command -v quarto || true)"
if [[ -z "${QUARTO_BIN}" ]]; then
  echo "report/render_report.sh: activate the congen environment (quarto is required)" >&2
  exit 1
fi

# conda-forge installs Quarto's executables in bin/ and resources in share/quarto/, while the
# upstream launcher assumes they are bundled under bin/tools/.  These overrides are harmless for
# a normally bundled Quarto and make the split conda package relocatable.
# Resolve the tool prefix from the selected Quarto executable.  A caller can put the
# locked environment first on PATH while still inheriting a stale/base CONDA_PREFIX;
# trusting that unrelated variable would skip these overrides and make Quarto look for
# its bundled Deno under a nonexistent architecture-specific tools directory.
ENV_PREFIX="$(cd "$(dirname "${QUARTO_BIN}")/.." && pwd)"
[[ -d "${ENV_PREFIX}/share/quarto" ]] && export QUARTO_SHARE_PATH="${ENV_PREFIX}/share/quarto"
[[ -x "${ENV_PREFIX}/bin/deno" ]] && export QUARTO_DENO="${ENV_PREFIX}/bin/deno"
[[ -x "${ENV_PREFIX}/bin/pandoc" ]] && export QUARTO_PANDOC="${ENV_PREFIX}/bin/pandoc"
[[ -x "${ENV_PREFIX}/bin/sass" ]] && export QUARTO_DART_SASS="${ENV_PREFIX}/bin/sass"
[[ -x "${ENV_PREFIX}/bin/esbuild" ]] && export QUARTO_ESBUILD="${ENV_PREFIX}/bin/esbuild"
[[ -x "${ENV_PREFIX}/bin/typst" ]] && export QUARTO_TYPST="${ENV_PREFIX}/bin/typst"
[[ -x "${ENV_PREFIX}/bin/python" ]] && export QUARTO_PYTHON="${ENV_PREFIX}/bin/python"
[[ -f "${ENV_PREFIX}/lib/deno_dom.dylib" ]] && export QUARTO_DENO_DOM="${ENV_PREFIX}/lib/deno_dom.dylib"

export RENV_CONFIG_AUTOLOADER_ENABLED=FALSE

REPORT_RUNTIME_DIR="${TMPDIR:-/tmp}/cg-report-jupyter-runtime"
mkdir -p "${REPORT_RUNTIME_DIR}"
export JUPYTER_RUNTIME_DIR="${REPORT_RUNTIME_DIR}"

cd "${PROJECT_ROOT}"
"${QUARTO_BIN}" render report/report.qmd --to html "$@"

# Quarto's generated HTML contains version-dependent trailing spaces in embedded
# scripts. Normalizing line endings keeps the tracked artifact diff-clean without
# changing markup or rendered content.
perl -pi -e 's/[ \t]+$//' "${PROJECT_ROOT}/report/report.html"
