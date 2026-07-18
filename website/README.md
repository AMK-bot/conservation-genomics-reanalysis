# Project website

The project portal is [`../index.html`](../index.html). It is a dependency-free static site that
reuses the repository's tracked figures, screenshots, reports, tables, and documentation in place.
There is no build step and no network dependency.

## Preview

From the repository root:

```bash
python -m http.server 8000
```

Open `http://localhost:8000/`. Directly opening `index.html` also works; serving over HTTP gives the
closest preview of static hosting.

## Files

- `index.html` — semantic page content and complete deliverable index.
- `website/site.css` — responsive presentation, print styles, and reduced-motion behavior.
- `website/site.js` — optional navigation, filtering, search, copy buttons, and image lightbox.
- `website/favicon.svg` — local site icon.
- `.nojekyll` — keeps repository filenames and static assets unchanged on GitHub Pages.

Run `python scripts/python/validate_website.py` to check local links, required page landmarks,
accessible image descriptions, and the absence of external runtime dependencies.

## Sendable bundle

Build the single-file portfolio package from the repository root:

```bash
python scripts/python/package_website.py
```

This creates `dist/conservation-genomics-portfolio.zip` and
`results/WEBSITE_BUNDLE_VALIDATION.md`. The ZIP contains the complete site, all 83 linked local
targets, `requirements.txt` for the optional explorer, a recipient-facing `README_FIRST.txt`, and
an exact `MANIFEST.sha256`. Raw genomic datasets and regenerable intermediates are excluded because
they are not needed to open or review the website.
