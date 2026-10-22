# Project website

The project portal is [`../index.html`](../index.html). It is a dependency-free static site that
reuses the repository's tracked figures, screenshots, reports, tables, and documentation in place.
There is no browser-side build step and no runtime network dependency. External DOI links use the
network only if a reader chooses to open them.

Phase 5B's interactive tables are precomputed by the scientific workflow. Run the locked Phase 5B
DAG before validating or packaging a refreshed site:

```bash
snakemake --snakefile workflow/Snakefile phase5b --cores 4 --resources mem_mb=7000
```

The workflow order is 13.1 → 13.3 → 13.2 → 13.6 core communication gate → optional-study gate →
authorized 13.4 localization → final synthesis. Validator TSV dependencies enforce this order.
**Phase 5B status: COMPLETE.** The synchronized render, release-content verification, deterministic
package, and delivery checks pass. The current evidence is the
[Phase-5B reproducibility record](../results/PHASE5B_REPRODUCIBILITY.md).

The frozen Phase-5B website claims are:

- wolf individual association: **15/15** predeclared cells, interpreted only as association between
  genomic proxies;
- damage-aware peafowl comparison: **1/4** metrics fully robust, with geography confounded and no
  temporal-erosion upgrade;
- peafowl $N_e$ calibration: **0/15** designs resolving both predeclared resolution truths
  ($N_e=250$ and $N_e=1{,}000$), and therefore no empirical sample prescription;
- §13.4 **`IMPLEMENT`** followed by **24/24** predeclared population × GERP cells at the 1.5-Mb
  cutoff beyond the circular-shift null rule—genomic colocalization, not fitness, harm, or causation;
- §13.5 **`DEFER_DUPLICATES_SOURCE_STUDY`** from 0/1 independent definitions and 211/211 source
  overlap. Reopen only with at least one independent definition, at least 0.95 common-sample
  coverage, and at least 0.90 auditable callable-denominator coverage.

## Preview

From the repository root:

```bash
python -m http.server 8000
```

Open `http://localhost:8000/`. Directly opening `index.html` also works; serving over HTTP gives the
closest preview of static hosting.

## Files

- `index.html` — semantic page content and complete deliverable index.
- `editor.html` — the private localhost editing interface and live website preview.
- `website/site.css` — responsive presentation, print styles, and reduced-motion behavior.
- `website/site.js` — optional navigation, filtering, search, copy buttons, image lightbox, and
  native-select Phase 5B interactions.
- `website/editor.css` and `website/editor.js` — the visual editor interface and local save controls.
- `website/content-overrides.json` — versioned saved narrative text and its revision hash.
- `website/content-overrides.js` and `website/apply-content.js` — the generated static personalization
  layer and its text-only application code; do not edit the generated JavaScript by hand.
- `website/phase5b-data.js` — generated, local-only JSON assignment consumed by `site.js`; do not
  edit it by hand.
- `website/favicon.svg` — local site icon.
- `.nojekyll` — keeps repository filenames and static assets unchanged on GitHub Pages.

`scripts/python/phase5b_synthesis.py` writes `website/phase5b-data.js` as a single
`window.PHASE5B_DATA` assignment. It contains the frozen wolf robustness grid, wolf localization
grid, damage results, effective-population-size design grid, optional decisions, and claim traces.
The browser code does not use `fetch`, dynamic imports, XHR, sockets, or a remote API: opening
`index.html` from an extracted folder is sufficient.

The generated claim trace links each displayed conclusion to its result table, provenance,
validator, report anchor, explorer anchor, and workflow rule. If the payload is absent, the site
keeps the static explanations and table links readable, reports that local Phase 5B data are
unavailable, and disables the affected selectors. A missing grid cell is labelled `missing cell`;
a failed image retains an alt-derived text fallback. The `<noscript>` claim-table link remains
available when JavaScript is disabled.

Do not substitute an empty or hand-written payload to make the controls render: the validator
checks the exact grid cardinalities, schema, numeric gates, local trace targets, script order,
missing-data fallbacks, and absence of network-loading code.

## Personalize website text

From the repository root, double-click `EDIT_WEBSITE.command`. Alternatively, run:

```bash
python3 scripts/python/edit_website.py
```

The launcher opens a private editor on `127.0.0.1`. Keep its Terminal window open, click an outlined
heading or paragraph in the live preview, edit normally, and choose **Save website text**. The editor
also provides discard, undo, restore-original, and JSON import/export controls. Press `Ctrl+C` in
Terminal to stop it.

Personalization is stored separately in `website/content-overrides.json` and its generated JavaScript
mirror, so saving does not rewrite `index.html`. Only allowlisted narrative leaves are editable.
Scientific measurements, status and decision labels, Phase-5B claims, model controls, links, figures,
and generated evidence remain locked. Python's standard library is needed to save edits; no packages
or internet connection are required. The static website remains directly readable without Python.

## Offline validation

From the repository root, run the file-level website gate with explicit paths:

```bash
python scripts/python/validate_website.py \
  --root . \
  --html index.html \
  --out results/WEBSITE_VALIDATION.md
```

This checks local links and anchors, required landmarks, accessible image descriptions, responsive
and reduced-motion behavior, Phase 5B grids and claim traces, readable failure fallbacks, and the
absence of external runtime dependencies. A nonzero exit or any reported `FAIL` blocks packaging.

## Sendable bundle

Build and verify the single-file portfolio package through Snakemake so the complete scientific
artifact inventory is passed to the fail-closed packager:

```bash
snakemake --snakefile workflow/Snakefile package_website --cores 4 --resources mem_mb=7000
```

This creates `dist/conservation-genomics-reanalysis.zip` and
`results/WEBSITE_BUNDLE_VALIDATION.md`. The packager builds the archive twice to check deterministic
bytes, rejects external runtime dependencies and unsafe paths, verifies CRCs and the exact
`MANIFEST.sha256`, extracts into a fresh temporary directory, and reruns the website validator from
that extraction. The ZIP contains the complete site's local dependency closure,
`requirements.txt` for the optional explorer, a recipient-facing `README_FIRST.txt`, and the
manifest. Counts are derived at packaging time rather than asserted here.

Raw genomic datasets and regenerable intermediates—including the per-chromosome localization
partitions—are excluded because they are not needed to open or review the website. Collated
Phase-5B result tables, figures, provenance, validators, and the generated browser payload are
included through the site's local links and claim trace.

For an additional manual check after copying the ZIP, extract the whole archive and run inside its
top-level `conservation-genomics-reanalysis` folder:

```bash
shasum -a 256 -c MANIFEST.sha256
python scripts/python/validate_website.py \
  --root . \
  --html index.html \
  --out /tmp/extracted-website-validation.md
```

Then open `index.html` directly. No installation or internet connection is required for the static
site; only the separate optional Streamlit explorer requires the packages in `requirements.txt`.
