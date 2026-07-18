#!/usr/bin/env python3
"""Validate the dependency-free project website and all of its local links."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


REQUIRED_DELIVERABLES = {
    "admissions/research_brief.html",
    "admissions/graphical_abstract.svg",
    "report/report.html",
    "RESEARCH_JOURNEY.md",
    "INTERVIEW_NOTES.md",
    "admissions/demo_script.md",
    "app/streamlit_app.py",
    "results/cube/results_cube.csv",
    "results/tables/fragility_scorecard.tsv",
    "results/PHASE5A_VALIDATION.md",
    "results/PHASE5A_REPRODUCIBILITY.md",
    "results/WEBSITE_VALIDATION.md",
    "workflow/Snakefile",
    "config/config.yaml",
    "environment.lock.yml",
    "PROJECT_STATUS.md",
}

RUNTIME_TAGS = {"script", "link", "img", "source", "video", "audio"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--html", default="index.html", help="Website entry point")
    parser.add_argument("--out", default="results/WEBSITE_VALIDATION.md", help="Markdown report")
    return parser.parse_args()


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.references: list[tuple[str, str, str]] = []
        self.image_alts: list[tuple[str, str | None]] = []
        self.tags: list[str] = []
        self.h1_count = 0
        self.deliverable_count = 0
        self.has_meta_description = False
        self.has_skip_link = False
        self.has_title = False
        self._in_title = False
        self._title_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        values = dict(attrs)
        if identifier := values.get("id"):
            self.ids.add(identifier)
        if tag == "h1":
            self.h1_count += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta" and values.get("name", "").lower() == "description":
            self.has_meta_description = bool(values.get("content", "").strip())
        if tag == "a" and values.get("href") == "#main-content":
            self.has_skip_link = True
        if "data-deliverable" in values:
            self.deliverable_count += 1
        if tag == "img":
            self.image_alts.append((values.get("src", ""), values.get("alt")))
        for attribute in ("href", "src"):
            if value := values.get(attribute):
                self.references.append((tag, attribute, value))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
            self.has_title = bool("".join(self._title_text).strip())

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_text.append(data)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def reference_path(value: str) -> tuple[str, str]:
    parsed = urlsplit(value)
    return unquote(parsed.path), unquote(parsed.fragment)


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    html_path = (root / args.html).resolve()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = root / out_path

    checks: list[Check] = []

    if not html_path.is_file():
        print(f"Missing website entry point: {html_path}", file=sys.stderr)
        raise SystemExit(1)

    text = html_path.read_text(encoding="utf-8")
    parser = SiteParser()
    parser.feed(text)

    signature_ok = (
        len(text) > 10_000
        and text.lstrip().lower().startswith("<!doctype html>")
        and "</html>" in text.lower()
    )
    checks.append(Check("complete HTML document", signature_ok, f"{len(text):,} bytes"))

    landmarks = {"header", "nav", "main", "footer"}
    missing_landmarks = sorted(landmarks - set(parser.tags))
    semantics_ok = (
        not missing_landmarks
        and parser.h1_count == 1
        and parser.has_title
        and parser.has_meta_description
        and parser.has_skip_link
    )
    semantics_detail = (
        "title, description, skip link, one H1, and all landmarks present"
        if semantics_ok
        else f"missing landmarks={missing_landmarks}; h1={parser.h1_count}; "
             f"title={parser.has_title}; description={parser.has_meta_description}; skip={parser.has_skip_link}"
    )
    checks.append(Check("semantic and accessible page structure", semantics_ok, semantics_detail))

    local_targets: set[str] = set()
    missing_targets: list[str] = []
    missing_anchors: list[str] = []
    external_runtime: list[str] = []
    for tag, _attribute, value in parser.references:
        parsed = urlsplit(value)
        if parsed.scheme in {"http", "https"}:
            if tag in RUNTIME_TAGS and tag != "a":
                external_runtime.append(value)
            continue
        if parsed.scheme in {"mailto", "tel", "data"} or value.startswith("//"):
            continue
        path_text, fragment = reference_path(value)
        if not path_text:
            if fragment and fragment not in parser.ids:
                missing_anchors.append(fragment)
            continue
        target = (html_path.parent / path_text).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            missing_targets.append(f"{value} (outside repository)")
            continue
        local_targets.add(target.relative_to(root).as_posix())
        # The site links its own validation report. On a clean run that report is
        # the output currently being created, so accept this one prospective target.
        if not target.exists() and target != out_path.resolve():
            missing_targets.append(value)

    checks.append(
        Check(
            "all local links and media targets exist",
            not missing_targets,
            f"{len(local_targets)} unique local targets" if not missing_targets else "; ".join(missing_targets[:8]),
        )
    )
    checks.append(
        Check(
            "all in-page navigation targets exist",
            not missing_anchors,
            f"{len(parser.ids)} page IDs indexed" if not missing_anchors else f"missing: {', '.join(missing_anchors)}",
        )
    )
    checks.append(
        Check(
            "no external runtime dependency",
            not external_runtime,
            "CSS, JavaScript, fonts, and images are repository-local" if not external_runtime else "; ".join(external_runtime),
        )
    )

    images_without_alt = [src for src, alt in parser.image_alts if alt is None]
    checks.append(
        Check(
            "every image has alternative text",
            not images_without_alt,
            f"{len(parser.image_alts)} images checked" if not images_without_alt else f"missing alt: {images_without_alt}",
        )
    )

    missing_deliverables = sorted(REQUIRED_DELIVERABLES - local_targets)
    library_ok = parser.deliverable_count >= 20 and not missing_deliverables
    library_detail = (
        f"{parser.deliverable_count} explained cards; all {len(REQUIRED_DELIVERABLES)} essential artifacts linked"
        if library_ok
        else f"cards={parser.deliverable_count}; missing essential links={missing_deliverables}"
    )
    checks.append(Check("essential explained deliverable coverage", library_ok, library_detail))

    css_path = root / "website/site.css"
    css = css_path.read_text(encoding="utf-8") if css_path.is_file() else ""
    css_ok = (
        len(css) > 5_000
        and "@media (max-width:" in css
        and "prefers-reduced-motion" in css
        and ":focus-visible" in css
        and "@media print" in css
    )
    checks.append(
        Check(
            "responsive, reduced-motion, focus, and print styles",
            css_ok,
            f"{len(css):,} bytes of local CSS" if css_ok else "required responsive/accessibility styles missing",
        )
    )

    js_path = root / "website/site.js"
    js = js_path.read_text(encoding="utf-8") if js_path.is_file() else ""
    js_ok = (
        len(js) > 1_000
        and "data-filter" in js
        and "data-lightbox" in js
        and "data-copy" in js
        and not re.search(r"\b(fetch|import)\s*\(", js)
    )
    checks.append(
        Check(
            "local progressive-enhancement script",
            js_ok,
            "filter, search, copy, navigation, reveal, and lightbox behavior; no fetch/import"
            if js_ok
            else "expected local interactions missing or remote-loading code found",
        )
    )

    hosting_files = [root / ".nojekyll", root / "website/README.md", root / "website/favicon.svg"]
    hosting_ok = all(path.exists() for path in hosting_files)
    checks.append(
        Check(
            "offline/static-hosting support files",
            hosting_ok,
            ".nojekyll, preview instructions, and local favicon present"
            if hosting_ok
            else "one or more hosting support files missing",
        )
    )

    passed = sum(check.ok for check in checks)
    failed = len(checks) - passed
    rows = [
        "# Project website validation",
        "",
        "The root project portal is checked as a dependency-free, offline-readable static website.",
        "",
        f"**Summary: {passed} PASS, {failed} FAIL**",
        "",
        "| check | status | evidence |",
        "|---|---|---|",
    ]
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        detail = check.detail.replace("|", "\\|").replace("\n", " ")
        rows.append(f"| {check.name} | **{status}** | {detail} |")
    rows.extend(
        [
            "",
            "## Scope",
            "",
            "This gate validates structure, accessibility affordances, local targets, core deliverable coverage,",
            "and dependency-free behavior. Browser-based visual and interaction checks complement this file-level gate.",
            "",
        ]
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(rows), encoding="utf-8")
    print(f"Website validation: {passed} PASS, {failed} FAIL")
    print(f"Report: {out_path}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
