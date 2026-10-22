#!/usr/bin/env python3
"""Fail-closed downstream validation for the complete Phase-5B delivery.

This gate is intentionally downstream of the scientific validators, report
render, Streamlit smoke test, static-site validation, and ZIP construction.  It
does not recompute scientific analyses.  Instead, it independently reconciles
the delivered gates, rendered values, portable archive, documentation, and
checksum-bearing provenance records.  Missing or malformed inputs become FAIL
rows so a partial delivery cannot pass by omission.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
import unicodedata
from urllib.parse import unquote, urlsplit
import zipfile


ROOT = Path(__file__).resolve().parents[2]

VALIDATOR_PATHS = (
    "results/tables/validation_wolf_robustness.tsv",
    "results/tables/validation_peafowl_damage.tsv",
    "results/tables/validation_peafowl_ne_design.tsv",
    "results/tables/validation_phase5b_core_integration.tsv",
    "results/tables/validation_phase5b_decisions.tsv",
    "results/tables/validation_wolf_roh_localization.tsv",
    "results/tables/validation_phase5b.tsv",
    "results/tables/validation_phase5b_release_content.tsv",
)

VALIDATOR_DOCUMENTS = (
    "results/WOLF_ROBUSTNESS_VALIDATION.md",
    "results/PEAFOWL_DAMAGE_VALIDATION.md",
    "results/PEAFOWL_NE_DESIGN_VALIDATION.md",
    "results/PHASE5B_CORE_INTEGRATION_VALIDATION.md",
    "results/PHASE5B_DECISIONS_VALIDATION.md",
    "results/WOLF_ROH_LOCALIZATION_VALIDATION.md",
    "results/PHASE5B_VALIDATION.md",
    "results/PHASE5B_RELEASE_CONTENT_VALIDATION.md",
    "results/PHASE5B_DATA_DICTIONARY.md",
)

PROVENANCE_PATHS = (
    "results/provenance/wolf_froh_load.json",
    "results/provenance/peafowl_damage.json",
    "results/provenance/peafowl_ne_design.json",
    "results/provenance/phase5b_core_integration.json",
    "results/provenance/phase5b_optional_decisions.json",
    "results/provenance/wolf_roh_localization.json",
    "results/provenance/phase5b_synthesis.json",
)

CORE_DELIVERY_PATHS = (
    "EDIT_WEBSITE.command",
    "EDIT_WEBSITE.md",
    "brief/research_brief.md",
    "brief/research_brief.html",
    "brief/graphical_abstract.svg",
    "brief/walkthrough.md",
    "RESEARCH_JOURNEY.md",
    "FAQ.md",
    "report/report.html",
    "app/streamlit_app.py",
    "editor.html",
    "index.html",
    "scripts/python/edit_website.py",
    "website/apply-content.js",
    "website/content-overrides.js",
    "website/content-overrides.json",
    "website/editor.css",
    "website/editor.js",
    "website/site.css",
    "website/site.js",
    "website/phase5b-data.js",
    "results/tables/phase5b_claim_trace.tsv",
    "results/tables/phase5b_fragility_scorecard.tsv",
    "results/tables/phase5b_data_dictionary.tsv",
    "results/APP_SMOKE.md",
    "results/logs/app_smoke.log",
    "results/WEBSITE_VALIDATION.md",
    "results/WEBSITE_BUNDLE_VALIDATION.md",
    "results/PHASE5B_REPRODUCIBILITY.md",
    "dist/conservation-genomics-reanalysis.zip",
    "README.md",
    "PROJECT_STATUS.md",
    "CGplan.md",
)

REQUIRED_REPORT_ANCHORS = {
    "damage-aware-falsification",
    "ne-sample-design-calibration",
    "wolf-individual-association",
    "wolf-roh-localization",
    "optional-study-decisions",
}

CLAIM_REQUIRED_COLUMNS = {
    "claim_id",
    "headline",
    "claim_status",
    "estimate",
    "observed_value",
    "result_table",
    "provenance",
    "validator",
    "report_anchor",
    "explorer_anchor",
    "workflow_rule",
}

SUMMARY_RE = re.compile(
    r"^\*\*Summary:\s*(\d+)\s+PASS"
    r"(?:,\s*(\d+)\s+WARN)?"
    r",\s*(\d+)\s+FAIL\*\*\s*$",
    re.MULTILINE,
)
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
CSS_URL_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE | re.DOTALL)
CSS_IMPORT_RE = re.compile(
    r"@import\s+(?:url\(\s*)?['\"]?([^'\"\s\)]+)", re.IGNORECASE
)
DYNAMIC_EXTERNAL_RUNTIME_RE = re.compile(
    r"""
    (?:
        \.\s*(?:src|srcset|poster)\s*=
      | \[\s*['\"](?:src|srcset|poster)['\"]\s*\]\s*=
      | \bsetAttribute\s*\(\s*['\"](?:src|srcset|poster)['\"]\s*,
      | \b(?:fetch|import|importScripts)\s*\(
      | \bnew\s+(?:Worker|SharedWorker|WebSocket|EventSource)\s*\(
      | \.\s*open\s*\(\s*['\"][A-Z]+['\"]\s*,
    )
    (?:\s|/\*[\s\S]*?\*/|//[^\r\n]*(?:\r?\n|$))*['\"`]\s*(?:https?:)?//
    """,
    re.IGNORECASE | re.VERBOSE,
)
DYNAMIC_RUNTIME_ELEMENT_RE = re.compile(
    r"""
    \b(?P<variable>[A-Za-z_$][\w$]*)\s*=\s*
    (?:document\s*\.\s*)?createElement\s*\(\s*
    ['\"](?P<tag>script|link|img|source|video|audio|iframe|object|embed|input)['\"]\s*\)
    """,
    re.IGNORECASE | re.VERBOSE,
)
DYNAMIC_RUNTIME_ELEMENT_ATTRIBUTES = {
    "script": {"src"},
    "link": {"href"},
    "img": {"src", "srcset"},
    "source": {"src", "srcset"},
    "video": {"src", "poster"},
    "audio": {"src"},
    "iframe": {"src"},
    "object": {"data"},
    "embed": {"src"},
    "input": {"src"},
}
JS_GAP = r"(?:\s|/\*[\s\S]*?\*/|//[^\r\n]*(?:\r?\n|$))*"
JS_REMOTE_LITERAL = r"['\"`]\s*(?:https?:)?//"

RUNTIME_ATTRIBUTES = {
    "script": {"src"},
    "img": {"src", "srcset"},
    "source": {"src", "srcset"},
    "video": {"src", "poster"},
    "audio": {"src"},
    "iframe": {"src"},
    "object": {"data"},
    "embed": {"src"},
    "input": {"src"},
    "image": {"href", "xlink:href"},
}
RUNTIME_LINK_RELS = {"stylesheet", "icon", "preload", "modulepreload", "manifest"}
ALLOWED_EMBEDDED_SCHEMES = {"data", "blob"}
ALLOWED_NONRUNTIME_SCHEMES = {"http", "https", "mailto", "tel", "data"}


class DeliveryError(RuntimeError):
    """A validation condition that should be reported as a FAIL row."""


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class Summary:
    passed: int
    warned: int
    failed: int


class DeliveryHTMLParser(HTMLParser):
    """Collect identifiers, visible text, references, and embedded styles."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.references: list[tuple[str, str, str, bool]] = []
        self.visible: list[str] = []
        self.styles: list[str] = []
        self.section_text: dict[str, list[str]] = {}
        self.brief_pages: list[tuple[str, str, str]] = []
        self.brief_diagrams: list[tuple[str, str]] = []
        self._hidden_depth = 0
        self._style_depth = 0
        self._active_section: str | None = None
        self._section_stack: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        values = {key.lower(): value or "" for key, value in attrs}
        classes = set(values.get("class", "").split())
        if "brief-page" in classes:
            self.brief_pages.append(
                (tag, values.get("data-page", ""), values.get("aria-label", ""))
            )
        if tag == "img" and "model-diagram" in classes:
            self.brief_diagrams.append((values.get("src", ""), values.get("alt", "")))
        if values.get("id"):
            self.ids.add(values["id"])
        if values.get("name") and tag == "a":
            self.ids.add(values["name"])
        if tag == "section":
            self._section_stack.append(self._active_section)
            if values.get("id"):
                self._active_section = values["id"]
                self.section_text.setdefault(self._active_section, [])
        if re.fullmatch(r"h[1-6]", tag):
            if values.get("id"):
                self._active_section = values["id"]
                self.section_text.setdefault(self._active_section, [])
            elif not self._section_stack:
                self._active_section = None

        runtime_attrs = set(RUNTIME_ATTRIBUTES.get(tag, set()))
        if tag == "link":
            rels = {part.lower() for part in values.get("rel", "").split()}
            if rels & RUNTIME_LINK_RELS:
                runtime_attrs.add("href")
        for attribute in ("href", "src", "srcset", "poster", "data", "xlink:href"):
            value = values.get(attribute, "").strip()
            if value:
                self.references.append((tag, attribute, value, attribute in runtime_attrs))

        if tag in {"script", "style", "template", "noscript"}:
            self._hidden_depth += 1
        if tag == "style":
            self._style_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "style" and self._style_depth:
            self._style_depth -= 1
        if tag in {"script", "style", "template", "noscript"} and self._hidden_depth:
            self._hidden_depth -= 1
        if tag == "section" and self._section_stack:
            self._active_section = self._section_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._style_depth:
            self.styles.append(data)
        if not self._hidden_depth:
            self.visible.append(data)
            if self._active_section:
                self.section_text.setdefault(self._active_section, []).append(data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT), help="project root")
    parser.add_argument(
        "--out-tsv", default="results/tables/validation_phase5b_delivery.tsv"
    )
    parser.add_argument(
        "--out-md", default="results/PHASE5B_DELIVERY_VALIDATION.md"
    )
    parser.add_argument(
        "--science-files",
        nargs="*",
        default=[],
        help="Complete workflow-owned Phase-5B scientific artifact inventory",
    )
    parser.add_argument("--self-test", action="store_true", help="run parser/safety tests")
    return parser.parse_args()


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = re.sub(r"\s*/\s*", "/", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_unique_summary(text: str) -> Summary:
    matches = list(SUMMARY_RE.finditer(text))
    if len(matches) != 1:
        raise DeliveryError(f"expected exactly one parseable Summary line; found {len(matches)}")
    match = matches[0]
    return Summary(int(match.group(1)), int(match.group(2) or 0), int(match.group(3)))


def markdown_table_statuses(text: str) -> list[str]:
    statuses: list[str] = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) < 2:
            continue
        match = re.fullmatch(r"\*\*(PASS|WARN|FAIL)\*\*", cells[1], re.IGNORECASE)
        if match:
            statuses.append(match.group(1).upper())
    return statuses


def validate_markdown_gate(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    summary = parse_unique_summary(text)
    statuses = markdown_table_statuses(text)
    if not statuses:
        raise DeliveryError("validation table has no PASS/WARN/FAIL rows")
    counts = {status: statuses.count(status) for status in ("PASS", "WARN", "FAIL")}
    if (summary.passed, summary.warned, summary.failed) != (
        counts["PASS"], counts["WARN"], counts["FAIL"]
    ):
        raise DeliveryError(
            "Summary/table mismatch: "
            f"summary={summary.passed}/{summary.warned}/{summary.failed}, "
            f"rows={counts['PASS']}/{counts['WARN']}/{counts['FAIL']}"
        )
    if summary.passed <= 0 or summary.failed != 0:
        raise DeliveryError(
            f"gate summary is {summary.passed} PASS, {summary.warned} WARN, {summary.failed} FAIL"
        )
    return f"{summary.passed} PASS, {summary.warned} WARN, 0 FAIL; table reconciles"


def validate_validator_tsv(path: Path) -> str:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames or "status" not in reader.fieldnames:
            raise DeliveryError("missing tabular status column")
        rows = list(reader)
    if not rows:
        raise DeliveryError("validator contains zero checks")
    statuses = [str(row.get("status", "")).strip().upper() for row in rows]
    unknown = sorted({status for status in statuses if status not in {"PASS", "WARN", "FAIL"}})
    failures = statuses.count("FAIL")
    if unknown or failures:
        raise DeliveryError(f"rows={len(rows)}; FAIL={failures}; unknown={unknown}")
    return f"{statuses.count('PASS')} PASS, {statuses.count('WARN')} WARN, 0 FAIL, 0 unknown"


def read_claims(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = set(reader.fieldnames or [])
        missing = sorted(CLAIM_REQUIRED_COLUMNS - fields)
        if missing:
            raise DeliveryError(f"claim trace missing columns: {missing}")
        rows = [{key: str(value or "").strip() for key, value in row.items()} for row in reader]
    if not rows:
        raise DeliveryError("claim trace contains zero claims")
    ids = [row["claim_id"] for row in rows]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise DeliveryError("claim IDs are empty or duplicated")
    empty = [
        row["claim_id"]
        for row in rows
        if any(not row[column] for column in CLAIM_REQUIRED_COLUMNS)
    ]
    if empty:
        raise DeliveryError(f"claims have empty required fields: {empty}")
    return rows


def strip_fragment(value: str) -> str:
    return unquote(urlsplit(value.strip()).path)


def parse_html(text: str) -> DeliveryHTMLParser:
    parser = DeliveryHTMLParser()
    parser.feed(text)
    parser.close()
    return parser


def split_srcset(value: str) -> list[str]:
    remaining = value.strip()
    candidates: list[str] = []
    while remaining:
        remaining = remaining.lstrip(" \t\r\n,")
        if not remaining:
            break
        is_data = remaining.lower().startswith("data:")
        match = re.match(r"\S+" if is_data else r"[^\s,]+", remaining)
        if match is None:
            break
        token = match.group(0)
        consumed_delimiter = is_data and token.endswith(",")
        candidate = token[:-1] if consumed_delimiter else token
        if candidate:
            candidates.append(candidate)
        remaining = remaining[match.end():]
        if consumed_delimiter:
            continue
        stripped = remaining.lstrip()
        if stripped.startswith(","):
            remaining = stripped[1:]
            continue
        delimiter = remaining.find(",")
        if delimiter < 0:
            break
        remaining = remaining[delimiter + 1:]
    candidates.extend(
        match.group(1)
        for match in re.finditer(r"(?:^|,)\s*((?:https?:)?//[^\s,]+)", value, re.IGNORECASE)
    )
    return list(dict.fromkeys(candidates))


def reference_values(attribute: str, value: str) -> list[str]:
    return split_srcset(value) if attribute == "srcset" else [value]


def nonembedded_runtime_references(parser: DeliveryHTMLParser) -> list[str]:
    problems: list[str] = []
    for tag, attribute, raw, runtime in parser.references:
        if not runtime:
            continue
        for value in reference_values(attribute, raw):
            parsed = urlsplit(value.strip())
            if value.strip().startswith("//") or parsed.netloc:
                problems.append(f"{tag}[{attribute}]={value[:120]}")
                continue
            if not value or (not parsed.path and not parsed.scheme):
                continue
            if parsed.scheme.lower() in ALLOWED_EMBEDDED_SCHEMES:
                continue
            problems.append(f"{tag}[{attribute}]={value[:120]}")
    for style in parser.styles:
        for match in CSS_URL_RE.finditer(style):
            value = match.group(2).strip()
            parsed = urlsplit(value)
            if value and not value.startswith("#") and parsed.scheme.lower() not in ALLOWED_EMBEDDED_SCHEMES:
                problems.append(f"style url={value[:120]}")
        for match in CSS_IMPORT_RE.finditer(style):
            value = match.group(1).strip()
            if urlsplit(value).scheme.lower() not in ALLOWED_EMBEDDED_SCHEMES:
                problems.append(f"style import={value[:120]}")
    return problems


def dynamic_external_runtime_references(text: str) -> list[str]:
    """Find literal remote URLs assigned to executable browser-loading APIs."""
    matches = [match.group(0).strip() for match in DYNAMIC_EXTERNAL_RUNTIME_RE.finditer(text)]
    for declaration in DYNAMIC_RUNTIME_ELEMENT_RE.finditer(text):
        variable = re.escape(declaration.group("variable"))
        attributes = "|".join(
            sorted(DYNAMIC_RUNTIME_ELEMENT_ATTRIBUTES[declaration.group("tag").lower()])
        )
        use_re = re.compile(
            rf"""
            \b{variable}\s*(?:\.\s*(?:{attributes})|\[\s*['\"](?:{attributes})['\"]\s*\])
            \s*=\s*{JS_GAP}{JS_REMOTE_LITERAL}
            |
            \b{variable}\s*\.\s*setAttribute\s*\(\s*['\"](?:{attributes})['\"]\s*,
            {JS_GAP}{JS_REMOTE_LITERAL}
            """,
            re.IGNORECASE | re.VERBOSE,
        )
        matches.extend(match.group(0).strip() for match in use_re.finditer(text))
    return list(dict.fromkeys(matches))


def validate_report_self_contained(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if "<html" not in text.lower() or "</html>" not in text.lower():
        raise DeliveryError("render is not a complete HTML document")
    parser = parse_html(text)
    problems = nonembedded_runtime_references(parser)
    problems.extend(
        f"dynamic runtime={value[:120]}"
        for value in dynamic_external_runtime_references(text)
    )
    if problems:
        raise DeliveryError(f"non-embedded runtime assets: {problems[:6]}")
    return f"complete {path.stat().st_size:,}-byte HTML; all runtime assets embedded"


def validate_brief_page_contract(text: str, parser: DeliveryHTMLParser) -> str:
    """Require the project-wide brief to be exactly four fixed A4 pages with diagrams."""
    expected_pages = ["1", "2", "3", "4"]
    page_numbers = [page for _tag, page, _label in parser.brief_pages]
    page_tags = [tag for tag, _page, _label in parser.brief_pages]
    labels = [normalized_text(label).casefold() for _tag, _page, label in parser.brief_pages]
    expected_labels = [f"page {page} of 4" for page in expected_pages]
    if page_numbers != expected_pages or page_tags != ["div"] * 4:
        raise DeliveryError(
            f"brief page wrappers must be four ordered divs; tags={page_tags}, pages={page_numbers}"
        )
    if any(expected not in label for expected, label in zip(expected_labels, labels)):
        raise DeliveryError(f"brief page aria labels do not identify Page 1-4 of 4: {labels}")

    visible = normalized_text(" ".join(parser.visible)).casefold()
    visible_words = re.sub(r"[_-]+", " ", visible)
    if "project wide" not in visible_words or "research journey" not in visible_words:
        raise DeliveryError("brief does not identify itself as a project-wide research journey")
    if re.search(r"\btwo[ -]page\b|\bpage\s+[12]\s+of\s+2\b", visible):
        raise DeliveryError("stale two-page wording remains in the rendered brief")

    if len(parser.brief_diagrams) != 4:
        raise DeliveryError(
            f"brief must contain one model diagram per page; found {len(parser.brief_diagrams)}"
        )
    missing_alt = [index + 1 for index, (_src, alt) in enumerate(parser.brief_diagrams) if not alt.strip()]
    if missing_alt:
        raise DeliveryError(f"brief model diagrams missing alternative text: {missing_alt}")

    css = re.sub(r"\s+", "", "".join(parser.styles).casefold())
    page_rule = re.search(r"\.brief-page\{([^}]*)\}", css)
    required_page_fragments = {
        "width:210mm",
        "height:297mm",
        "overflow:hidden",
        "break-after:page",
        "page-break-after:always",
    }
    missing_css = sorted(
        fragment
        for fragment in required_page_fragments
        if page_rule is None or fragment not in page_rule.group(1)
    )
    if "@page{size:a4;margin:0;}" not in css or missing_css:
        raise DeliveryError(
            f"brief lacks the fixed four-page A4 print contract; missing={missing_css}"
        )
    return "exactly four ordered fixed-A4 pages; four accessible model diagrams"


def validate_research_brief(path: Path, claims: list[dict[str, str]]) -> str:
    """Require the sendable brief to carry every final machine-derived headline."""
    text = path.read_text(encoding="utf-8")
    self_contained = validate_report_self_contained(path)
    parser = parse_html(text)
    page_contract = validate_brief_page_contract(text, parser)
    visible = normalized_text(" ".join(parser.visible)).casefold()
    visible_words = re.sub(r"[_-]+", " ", visible)
    if "phase 5b" not in visible_words:
        raise DeliveryError("rendered research brief does not identify the Phase 5B extension")
    missing: list[str] = []
    for claim in claims:
        markers = headline_markers(claim)
        if not any(
            normalized_text(marker).casefold() in visible
            or re.sub(r"[_-]+", " ", normalized_text(marker).casefold()) in visible_words
            for marker in markers
            if normalized_text(marker)
        ):
            missing.append(f"{claim['claim_id']}:{markers[:3]}")
    if missing:
        raise DeliveryError(f"machine-derived Phase-5B headlines absent from brief: {missing}")
    return (
        f"{self_contained}; {page_contract}; "
        f"all {len(claims)} final claim headlines represented"
    )


def headline_markers(claim: dict[str, str]) -> list[str]:
    headline = normalized_text(claim["headline"])
    fractions = [
        f"{left}/{right}"
        for left, right in re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)(?![\d.])", headline)
    ]
    if fractions:
        return list(dict.fromkeys(fractions))
    status = normalized_text(claim["claim_status"])
    if status:
        return [status, status.replace("_", " ")]
    estimate = normalized_text(claim["estimate"])
    return [estimate] if estimate else []


def validate_report_claims(report_path: Path, claims: list[dict[str, str]]) -> str:
    parser = parse_html(report_path.read_text(encoding="utf-8"))
    trace_anchors: set[str] = set()
    missing_targets: list[str] = []
    missing_values: list[str] = []
    for claim in claims:
        parsed = urlsplit(claim["report_anchor"])
        if parsed.path not in {"report/report.html", "./report/report.html"} or not parsed.fragment:
            missing_targets.append(f"{claim['claim_id']}:invalid target")
            continue
        trace_anchors.add(unquote(parsed.fragment))
        fragment = unquote(parsed.fragment)
        if fragment not in parser.ids:
            missing_targets.append(f"{claim['claim_id']}:{parsed.fragment}")

        markers = headline_markers(claim)
        section = normalized_text(" ".join(parser.section_text.get(fragment, [])))
        section_folded = section.casefold()
        section_words = re.sub(r"[_-]+", " ", section_folded)
        marker_found = False
        for marker in markers:
            normalized = normalized_text(marker).casefold()
            if normalized and (
                normalized in section_folded
                or re.sub(r"[_-]+", " ", normalized) in section_words
            ):
                marker_found = True
                break
        if not marker_found:
            missing_values.append(f"{claim['claim_id']}:{markers[:3]}")

    missing_required = sorted(REQUIRED_REPORT_ANCHORS - trace_anchors)
    missing_rendered = sorted(REQUIRED_REPORT_ANCHORS - parser.ids)
    if missing_targets or missing_required or missing_rendered or missing_values:
        raise DeliveryError(
            f"missing trace anchors={missing_targets}; required-in-trace={missing_required}; "
            f"required-in-render={missing_rendered}; headline-values={missing_values}"
        )
    return (
        f"{len(claims)} claim rows resolve to rendered anchors and machine-derived headline markers; "
        f"{len(REQUIRED_REPORT_ANCHORS)} required Phase-5B sections present"
    )


def parse_unique_int(text: str, pattern: str, label: str) -> int:
    values = re.findall(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if len(values) != 1:
        raise DeliveryError(f"expected one {label}; found {len(values)}")
    return int(values[0])


def validate_app_smoke(md_path: Path, log_path: Path) -> str:
    md = md_path.read_text(encoding="utf-8")
    log = log_path.read_text(encoding="utf-8")
    statuses = re.findall(r"^-\s+\*\*Status:\*\*\s+\*\*(PASS|FAIL)\*\*\s*$", md, re.I | re.M)
    if len(statuses) != 1 or statuses[0].upper() != "PASS":
        raise DeliveryError(f"Markdown smoke status is not unique PASS: {statuses}")
    md_count = parse_unique_int(md, r"^-\s+\*\*Tests run:\*\*\s+(\d+)\s*$", "Markdown test count")
    md_code = parse_unique_int(md, r"^-\s+\*\*Return code:\*\*\s+`?(\d+)`?\s*$", "Markdown return code")
    log_count = parse_unique_int(log, r"^Ran\s+(\d+)\s+tests?\s+in", "log test count")
    log_code = parse_unique_int(log, r"^Return code:\s*(\d+)\s*$", "log return code")
    ok_lines = re.findall(r"^OK\s*$", log, flags=re.MULTILINE)
    failed_lines = re.findall(r"^(?:FAILED|FAILURES?|ERRORS?)\b", log, flags=re.I | re.M)
    if md_count <= 0 or md_count != log_count or md_code != 0 or log_code != 0:
        raise DeliveryError(
            f"smoke reconciliation failed: md_count={md_count}, log_count={log_count}, "
            f"md_code={md_code}, log_code={log_code}"
        )
    if len(ok_lines) != 1 or failed_lines:
        raise DeliveryError(f"log OK lines={len(ok_lines)}; failure markers={failed_lines[:4]}")
    return f"PASS; {md_count} tests; Markdown/log return code 0; unittest OK"


def safe_member_names(infos: list[zipfile.ZipInfo]) -> tuple[str, set[str]]:
    names = [info.filename for info in infos]
    if not names:
        raise DeliveryError("ZIP contains no members")
    if len(names) != len(set(names)):
        raise DeliveryError("ZIP has duplicate member names")
    if len(names) != len({name.casefold() for name in names}):
        raise DeliveryError("ZIP has case-insensitive member collisions")

    roots: set[str] = set()
    file_names: set[str] = set()
    for info in infos:
        name = info.filename
        path = PurePosixPath(name)
        minimum_parts = 1 if info.is_dir() else 2
        if (
            not name
            or "\x00" in name
            or "\\" in name
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or len(path.parts) < minimum_parts
        ):
            raise DeliveryError(f"unsafe ZIP member path: {name!r}")
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            raise DeliveryError(f"symlink ZIP member: {name}")
        roots.add(path.parts[0])
        if not info.is_dir():
            file_names.add(name)
    if len(roots) != 1:
        raise DeliveryError(f"ZIP must have exactly one top-level folder; found {sorted(roots)}")
    return next(iter(roots)), file_names


def parse_manifest(text: str) -> dict[str, str]:
    records: dict[str, str] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        digest, separator, relative = line.partition("  ")
        if (
            not separator
            or not SHA256_RE.fullmatch(digest)
            or not relative
            or "\\" in relative
            or PurePosixPath(relative).is_absolute()
            or any(part in {"", ".", ".."} for part in PurePosixPath(relative).parts)
            or relative in records
        ):
            raise DeliveryError(f"malformed/unsafe manifest row {line_number}: {line[:100]!r}")
        records[relative] = digest.lower()
    if not records:
        raise DeliveryError("manifest contains zero records")
    return records


def validate_manifest_payload(payload: dict[str, bytes], manifest_text: str) -> str:
    records = parse_manifest(manifest_text)
    if set(records) != set(payload):
        missing = sorted(set(payload) - set(records))
        extra = sorted(set(records) - set(payload))
        raise DeliveryError(f"manifest coverage mismatch; missing={missing[:6]}, extra={extra[:6]}")
    mismatches = [relative for relative, content in payload.items() if sha256_bytes(content) != records[relative]]
    if mismatches:
        raise DeliveryError(f"manifest SHA-256 mismatches: {mismatches[:8]}")
    return f"exact coverage and SHA-256 match for all {len(payload)} non-manifest files"


def inspect_zip_safety(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as archive:
        bad = archive.testzip()
        if bad is not None:
            raise DeliveryError(f"CRC failure: {bad}")
        root, files = safe_member_names(archive.infolist())
    return f"CRC clean; one safe root {root!r}; {len(files)} files; no links/collisions/traversal"


def zip_relative_payload(archive: zipfile.ZipFile, root: str) -> dict[str, bytes]:
    payload: dict[str, bytes] = {}
    prefix = root + "/"
    for info in archive.infolist():
        if info.is_dir():
            continue
        relative = info.filename[len(prefix):]
        if relative != "MANIFEST.sha256":
            payload[relative] = archive.read(info)
    return payload


def validate_zip_manifest(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as archive:
        root, files = safe_member_names(archive.infolist())
        manifest_name = f"{root}/MANIFEST.sha256"
        if manifest_name not in files:
            raise DeliveryError("root MANIFEST.sha256 is missing")
        payload = zip_relative_payload(archive, root)
        manifest_text = archive.read(manifest_name).decode("utf-8")
    return validate_manifest_payload(payload, manifest_text)


def claim_local_paths(claims: list[dict[str, str]]) -> set[str]:
    paths: set[str] = set()
    for claim in claims:
        for column in (
            "result_table", "provenance", "validator", "report_anchor",
            "explorer_anchor", "workflow_rule",
        ):
            path = strip_fragment(claim[column])
            parsed = urlsplit(claim[column])
            if parsed.scheme or claim[column].startswith("//") or not path:
                raise DeliveryError(f"claim {claim['claim_id']} has non-local {column}: {claim[column]}")
            paths.add(path.lstrip("./"))
    return paths


def required_zip_paths(
    claims: list[dict[str, str]], science_paths: set[str] | None = None,
) -> set[str]:
    required = {
        "EDIT_WEBSITE.command",
        "EDIT_WEBSITE.md",
        "README_FIRST.txt",
        "editor.html",
        "index.html",
        "brief/research_brief.md",
        "brief/research_brief.html",
        "brief/graphical_abstract.svg",
        "brief/walkthrough.md",
        "RESEARCH_JOURNEY.md",
        "FAQ.md",
        "report/report.html",
        "app/streamlit_app.py",
        "scripts/python/edit_website.py",
        "website/apply-content.js",
        "website/content-overrides.js",
        "website/content-overrides.json",
        "website/editor.css",
        "website/editor.js",
        "website/site.css",
        "website/site.js",
        "website/phase5b-data.js",
        "results/APP_SMOKE.md",
        "results/WEBSITE_VALIDATION.md",
        "results/PHASE5B_REPRODUCIBILITY.md",
        "results/tables/phase5b_claim_trace.tsv",
        "results/tables/phase5b_fragility_scorecard.tsv",
        "results/tables/phase5b_data_dictionary.tsv",
        "README.md",
        "PROJECT_STATUS.md",
        "CGplan.md",
        *VALIDATOR_PATHS,
        *VALIDATOR_DOCUMENTS,
        *PROVENANCE_PATHS,
    }
    return required | claim_local_paths(claims) | set(science_paths or ())


def validate_zip_required(
    path: Path, claims: list[dict[str, str]], science_paths: set[str] | None = None,
) -> str:
    with zipfile.ZipFile(path, "r") as archive:
        root, _files = safe_member_names(archive.infolist())
        payload = zip_relative_payload(archive, root)
    required = required_zip_paths(claims, science_paths)
    missing = sorted(required - set(payload))
    if missing:
        raise DeliveryError(f"ZIP lacks required delivery members: {missing[:12]}")
    return f"all {len(required)} required report/app/site/claim/data/validator/provenance/docs files present"


def validate_zip_workspace_sync(
    path: Path,
    project_root: Path,
    claims: list[dict[str, str]],
    science_paths: set[str],
) -> str:
    """Prove that the internally valid ZIP is the current workspace delivery."""
    with zipfile.ZipFile(path, "r") as archive:
        root, _files = safe_member_names(archive.infolist())
        payload = zip_relative_payload(archive, root)
    required = required_zip_paths(claims, science_paths) - {"README_FIRST.txt"}
    return compare_workspace_payload(project_root, payload, required)


def compare_workspace_payload(
    project_root: Path, payload: dict[str, bytes], required: set[str]
) -> str:
    """Compare an extracted archive payload with current required workspace bytes."""
    missing_workspace: list[str] = []
    missing_archive: list[str] = []
    mismatched: list[str] = []
    for relative in sorted(required):
        workspace_path = project_root / relative
        if not workspace_path.is_file():
            missing_workspace.append(relative)
            continue
        if relative not in payload:
            missing_archive.append(relative)
            continue
        if payload[relative] != workspace_path.read_bytes():
            mismatched.append(relative)
    if missing_workspace or missing_archive or mismatched:
        raise DeliveryError(
            "ZIP/workspace synchronization failed; "
            f"workspace_missing={missing_workspace[:8]}; "
            f"archive_missing={missing_archive[:8]}; mismatched={mismatched[:8]}"
        )
    return f"all {len(required)} required workspace artifacts are byte-identical in the ZIP"


def resolve_archive_reference(source: str, value: str) -> str:
    parsed = urlsplit(value.strip())
    decoded = unquote(parsed.path)
    if not decoded:
        return source
    if decoded.startswith("/"):
        candidate = decoded.lstrip("/")
    else:
        candidate = posixpath.join(posixpath.dirname(source), decoded)
    normalized = posixpath.normpath(candidate)
    if normalized == ".." or normalized.startswith("../") or normalized.startswith("/"):
        raise DeliveryError(f"archive reference escapes root: {source} -> {value}")
    return normalized


def validate_css_references(source: str, text: str, members: set[str]) -> list[str]:
    problems: list[str] = []
    values = [match.group(2).strip() for match in CSS_URL_RE.finditer(text)]
    values += [match.group(1).strip() for match in CSS_IMPORT_RE.finditer(text)]
    for value in values:
        if not value or value.startswith("#"):
            continue
        parsed = urlsplit(value)
        if value.startswith("//") or parsed.netloc:
            problems.append(f"{source}: external CSS runtime {value[:120]}")
            continue
        if parsed.scheme:
            if parsed.scheme.lower() not in ALLOWED_EMBEDDED_SCHEMES:
                problems.append(f"{source}: external CSS runtime {value[:120]}")
            continue
        try:
            target = resolve_archive_reference(source, value)
        except DeliveryError as exc:
            problems.append(str(exc))
            continue
        if target not in members:
            problems.append(f"{source}: missing CSS target {target}")
    return problems


def validate_zip_offline(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as archive:
        root, _files = safe_member_names(archive.infolist())
        members = zip_relative_payload(archive, root)
    names = set(members)
    problems: list[str] = []
    checked_references = 0
    for source, payload in members.items():
        suffix = PurePosixPath(source).suffix.lower()
        if suffix in {".js", ".mjs"}:
            text = payload.decode("utf-8", errors="replace")
            problems.extend(
                f"{source}: dynamic external runtime {value[:120]}"
                for value in dynamic_external_runtime_references(text)
            )
            continue
        if suffix not in {".html", ".htm", ".svg", ".css"}:
            continue
        text = payload.decode("utf-8", errors="replace")
        if suffix == ".css":
            problems.extend(validate_css_references(source, text, names))
            continue
        parser = parse_html(text)
        problems.extend(
            f"{source}: dynamic external runtime {value[:120]}"
            for value in dynamic_external_runtime_references(text)
        )
        for style in parser.styles:
            problems.extend(validate_css_references(source, style, names))
        for tag, attribute, raw, runtime in parser.references:
            for value in reference_values(attribute, raw):
                checked_references += 1
                parsed = urlsplit(value.strip())
                scheme = parsed.scheme.lower()
                if value.strip().startswith("//") or parsed.netloc:
                    if runtime:
                        problems.append(f"{source}: external runtime {tag}[{attribute}]={value[:120]}")
                    continue
                if scheme:
                    if runtime and scheme not in ALLOWED_EMBEDDED_SCHEMES:
                        problems.append(f"{source}: external runtime {tag}[{attribute}]={value[:120]}")
                    elif not runtime and scheme not in ALLOWED_NONRUNTIME_SCHEMES:
                        problems.append(f"{source}: unsafe link scheme {scheme}")
                    continue
                if not parsed.path:
                    continue
                try:
                    target = resolve_archive_reference(source, value)
                except DeliveryError as exc:
                    problems.append(str(exc))
                    continue
                if target not in names:
                    problems.append(f"{source}: missing local target {target}")

    site_js = members.get("website/site.js", b"").decode("utf-8", errors="replace")
    network_apis = re.findall(
        r"\b(?:fetch|XMLHttpRequest|WebSocket|EventSource)\s*\(|\bimport\s*\(", site_js
    )
    if network_apis:
        problems.append(f"website/site.js contains network/dynamic-loading APIs: {network_apis[:6]}")
    if problems:
        raise DeliveryError(f"offline closure/runtime problems ({len(problems)}): {problems[:10]}")
    return f"{checked_references} HTML/SVG references close locally; no external runtime assets or site network APIs"


def validate_zip_no_host_paths(path: Path, project_root: Path) -> str:
    """Reject recipient-facing text that leaks a build host or private temp path."""
    text_suffixes = {
        ".css", ".csv", ".html", ".js", ".json", ".md", ".py", ".qmd",
        ".r", ".sh", ".smk", ".tsv", ".txt", ".yaml", ".yml",
    }
    forbidden = {
        str(project_root),
        str(project_root.parent),
        "/" + "Users/",
        "/private/" + "var/folders/",
    }
    problems: list[str] = []
    checked = 0
    with zipfile.ZipFile(path, "r") as archive:
        root, _files = safe_member_names(archive.infolist())
        payload = zip_relative_payload(archive, root)
    for relative, content in payload.items():
        if PurePosixPath(relative).suffix.lower() not in text_suffixes:
            continue
        checked += 1
        text = content.decode("utf-8", errors="replace")
        hits = sorted(marker for marker in forbidden if marker and marker in text)
        if hits:
            problems.append(f"{relative}:{hits}")
    if problems:
        raise DeliveryError(f"host-specific paths leaked into portable text: {problems[:10]}")
    return f"{checked} text artifacts contain no workspace, macOS home, or private-temp paths"


def validate_bundle_report_digest(report_path: Path, archive_path: Path) -> str:
    text = report_path.read_text(encoding="utf-8")
    matches = re.findall(r"^-\s+SHA-256:\s+`([0-9a-fA-F]{64})`\s*$", text, re.MULTILINE)
    if len(matches) != 1:
        raise DeliveryError(f"expected one bundle SHA-256 line; found {len(matches)}")
    actual = sha256_file(archive_path)
    if matches[0].lower() != actual:
        raise DeliveryError(f"bundle report digest {matches[0].lower()} != archive {actual}")
    return f"bundle report and ZIP agree at SHA-256 {actual}"


def phase5b_completion(text: str) -> str:
    matches = list(re.finditer(r"(?:phase[\s-]*5b|\b5b\b)", text, re.IGNORECASE))
    if not matches:
        raise DeliveryError("no Phase 5B marker")
    complete_windows: list[str] = []
    stale_windows: list[str] = []
    for match in matches:
        window = text[match.start(): match.end() + 700]
        if re.search(r"(?:\bcomplete(?:d)?\b|\b100\s*%)", window, re.IGNORECASE):
            complete_windows.append(normalized_text(window)[:180])
        if re.search(r"\bPLANNED\b\s*(?:/|-)\s*0\s*%|\bStatus:\s*PLANNED\b", window, re.IGNORECASE):
            stale_windows.append(normalized_text(window)[:180])
    if not complete_windows:
        raise DeliveryError("Phase 5B has no nearby COMPLETE/100% marker")
    if stale_windows:
        raise DeliveryError(f"stale PLANNED/0% Phase-5B marker remains: {stale_windows[:2]}")
    return "Phase 5B has a completion marker and no stale PLANNED/0% marker"


def has_canonical_command(text: str) -> str:
    blocks = re.findall(r"```(?:bash|sh|shell|zsh)?\s*\n(.*?)```", text, re.IGNORECASE | re.DOTALL)
    candidates = blocks + [line for line in text.splitlines() if "snakemake" in line.lower()]
    for candidate in candidates:
        compact = normalized_text(candidate.replace("\\\n", " "))
        if (
            re.search(r"\bsnakemake\b", compact)
            and re.search(r"(?:--snakefile|-s)(?:=|\s+)workflow/Snakefile\b", compact)
            and re.search(r"\bphase5b\b", compact)
            and re.search(r"--cores(?:=|\s+)4\b", compact)
            and re.search(r"--resources(?:=|\s+)[^\n]{0,160}\bmem_mb=7000\b", compact)
        ):
            return compact
    raise DeliveryError(
        "README lacks a root-runnable Phase-5B command with --snakefile workflow/Snakefile, "
        "--cores 4, and --resources mem_mb=7000"
    )


def iter_strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_strings(child)


def validate_provenance(paths: list[Path]) -> str:
    details: list[str] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not payload:
            raise DeliveryError(f"{path.name} is not a nonempty JSON object")
        digests = {text.lower() for text in iter_strings(payload) if SHA256_RE.fullmatch(text)}
        if not digests:
            raise DeliveryError(f"{path.name} contains no SHA-256 digest")
        details.append(f"{path.name}:{len(digests)}")
    return f"{len(paths)} valid provenance objects with checksum fields ({', '.join(details)})"


def validate_artifact_presence(
    root: Path, claims: list[dict[str, str]], science_paths: set[str] | None = None,
) -> str:
    paths = set(CORE_DELIVERY_PATHS) | set(VALIDATOR_PATHS) | set(VALIDATOR_DOCUMENTS) | set(PROVENANCE_PATHS)
    paths |= claim_local_paths(claims)
    paths |= set(science_paths or ())
    missing = sorted(path for path in paths if not resolve(root, path).is_file())
    if missing:
        raise DeliveryError(f"missing required artifacts: {missing[:15]}")
    return f"all {len(paths)} required delivery, trace, validation, provenance, and checksum artifacts exist"


class Audit:
    def __init__(self) -> None:
        self.checks: list[Check] = []

    def run(self, name: str, function) -> None:
        try:
            detail = function()
        except Exception as exc:  # fail closed while preserving a complete audit table
            self.checks.append(Check(name, "FAIL", f"{type(exc).__name__}: {exc}"))
        else:
            self.checks.append(Check(name, "PASS", str(detail)))


def write_outputs(checks: list[Check], out_tsv: Path, out_md: Path) -> None:
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    with out_tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["check", "status", "detail"])
        writer.writerows((check.name, check.status, check.detail) for check in checks)

    passed = sum(check.status == "PASS" for check in checks)
    failed = sum(check.status == "FAIL" for check in checks)
    lines = [
        "# Phase 5B downstream delivery validation",
        "",
        "This fail-closed gate runs after the scientific analyses, rendering, app smoke test, static-site gate, and offline ZIP construction.",
        "",
        f"**Summary: {passed} PASS, 0 WARN, {failed} FAIL**",
        "",
        "| check | status | evidence |",
        "|---|---|---|",
    ]
    for check in checks:
        detail = check.detail.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {check.name} | **{check.status}** | {detail} |")
    lines.extend(
        [
            "",
            "A PASS here means the completed scientific gates, rendered communication layers, and sendable archive reconcile. It does not expand the causal or fitness claims permitted by the underlying analyses.",
            "",
        ]
    )
    out_md.write_text("\n".join(lines), encoding="utf-8")


def expect_delivery_error(function) -> None:
    try:
        function()
    except DeliveryError:
        return
    raise AssertionError("expected DeliveryError")


def self_test() -> None:
    summary = parse_unique_summary("**Summary: 17 PASS, 2 WARN, 0 FAIL**\n")
    assert summary == Summary(17, 2, 0)
    expect_delivery_error(
        lambda: parse_unique_summary(
            "**Summary: 1 PASS, 0 FAIL**\n**Summary: 1 PASS, 0 FAIL**\n"
        )
    )

    valid_infos = [
        zipfile.ZipInfo("bundle/index.html"),
        zipfile.ZipInfo("bundle/MANIFEST.sha256"),
    ]
    root, names = safe_member_names(valid_infos)
    assert root == "bundle" and "bundle/index.html" in names
    expect_delivery_error(lambda: safe_member_names([zipfile.ZipInfo("bundle/../escape")]))
    expect_delivery_error(lambda: safe_member_names([zipfile.ZipInfo("/absolute/path")]))
    expect_delivery_error(lambda: safe_member_names([zipfile.ZipInfo("bundle\\evil")]))

    payload = {"index.html": b"<html></html>", "README_FIRST.txt": b"read me"}
    manifest = "\n".join(
        f"{sha256_bytes(content)}  {relative}" for relative, content in sorted(payload.items())
    ) + "\n"
    assert "exact coverage" in validate_manifest_payload(payload, manifest)
    expect_delivery_error(
        lambda: validate_manifest_payload({**payload, "extra.txt": b"x"}, manifest)
    )
    expect_delivery_error(
        lambda: parse_manifest(f"{'0' * 64}  ../escape\n")
    )

    parser = parse_html('<html><script src="https://cdn.example/a.js"></script></html>')
    assert nonembedded_runtime_references(parser)
    protocol_relative = parse_html('<html><img src="//cdn.example/a.png"></html>')
    assert nonembedded_runtime_references(protocol_relative)
    embedded = parse_html('<html><img src="data:image/png;base64,AA=="></html>')
    assert not nonembedded_runtime_references(embedded)
    assert dynamic_external_runtime_references(
        '<script>const loader = document.createElement("script"); '
        'loader.src = /* delayed */ "https://cdn.example/runtime.js";</script>'
    )
    assert dynamic_external_runtime_references(
        '<script>fetch("//api.example/runtime.json")</script>'
    )
    assert not dynamic_external_runtime_references(
        '<a href="https://doi.org/10.1000/example">citation</a>'
    )
    assert dynamic_external_runtime_references(
        '<script>const loader = document.createElement("link"); '
        'loader.setAttribute("href", "https://cdn.example/theme.css");</script>'
    )
    assert not dynamic_external_runtime_references(
        '<script>const citation = document.createElement("a"); '
        'citation.setAttribute("href", "https://doi.org/10.1000/example");</script>'
    )
    assert not dynamic_external_runtime_references(
        '<script>const link = document.createElement("a"); '
        'link.href = "https://doi.org/10.1000/example";</script>'
    )
    mixed_srcset = parse_html(
        '<img srcset="data:image/png;base64,AA== 1x, '
        'https://cdn.example/mixed.png 2x">'
    )
    assert nonembedded_runtime_references(mixed_srcset)
    sections = parse_html('<h2 id="one">Result 2/4</h2><p>bounded</p><h2 id="two">Other</h2>')
    assert normalized_text(" ".join(sections.section_text["one"])) == "Result 2/4 bounded"
    quarto = parse_html('<section id="one"><h2>Heading</h2><p>Result 2/4</p></section>')
    assert normalized_text(" ".join(quarto.section_text["one"])) == "Heading Result 2/4"
    brief_style = (
        "@page{size:A4;margin:0;}"
        ".brief-page{width:210mm;height:297mm;overflow:hidden;"
        "break-after:page;page-break-after:always;}"
    )
    brief_pages = "".join(
        f'<div class="brief-page" data-page="{page}" aria-label="Page {page} of 4">'
        f'<img class="model-diagram" src="data:image/svg+xml;base64,AA==" alt="Model {page}">'
        "</div>"
        for page in range(1, 5)
    )
    brief_html = (
        f"<html><style>{brief_style}</style><body>"
        "<p>Project-wide research journey</p>"
        f"{brief_pages}</body></html>"
    )
    brief_parser = parse_html(brief_html)
    assert "exactly four" in validate_brief_page_contract(brief_html, brief_parser)
    expect_delivery_error(
        lambda: validate_brief_page_contract(
            brief_html.replace('data-page="4"', 'data-page="5"'),
            parse_html(brief_html.replace('data-page="4"', 'data-page="5"')),
        )
    )
    expect_delivery_error(
        lambda: validate_brief_page_contract(
            brief_html.replace("Project-wide research journey", "Two-page research journey"),
            parse_html(brief_html.replace("Project-wide research journey", "Two-page research journey")),
        )
    )
    expect_delivery_error(
        lambda: validate_brief_page_contract(
            brief_html.replace("overflow:hidden;", "overflow:visible;"),
            parse_html(brief_html.replace("overflow:hidden;", "overflow:visible;")),
        )
    )
    assert "completion marker" in phase5b_completion("| 5B | **100%** | complete delivery |")
    expect_delivery_error(lambda: phase5b_completion("Phase 5B Status: PLANNED / 0%"))
    assert "snakemake" in has_canonical_command(
        "```bash\nsnakemake -s workflow/Snakefile phase5b --cores 4 --resources mem_mb=7000\n```"
    )
    assert "results/tables/unlinked.tsv" in required_zip_paths(
        [], {"results/tables/unlinked.tsv"}
    )
    import tempfile
    with tempfile.TemporaryDirectory(prefix="cg-delivery-self-test-") as temporary_name:
        fixture_root = Path(temporary_name)
        artifact = fixture_root / "artifact.tsv"
        artifact.write_bytes(b"value\n1\n")
        payload = {"artifact.tsv": b"value\n1\n"}
        assert "byte-identical" in compare_workspace_payload(
            fixture_root, payload, {"artifact.tsv"}
        )
        artifact.write_bytes(b"value\n2\n")
        expect_delivery_error(
            lambda: compare_workspace_payload(fixture_root, payload, {"artifact.tsv"})
        )
        dynamic_archive = fixture_root / "dynamic-runtime.zip"
        with zipfile.ZipFile(dynamic_archive, "w") as archive:
            archive.writestr(
                "bundle/index.html",
                '<html><script src="website/site.js"></script></html>',
            )
            archive.writestr(
                "bundle/website/site.js",
                'const loader = document.createElement("script"); '
                'loader.src = "https://cdn.example/runtime.js";',
            )
        expect_delivery_error(lambda: validate_zip_offline(dynamic_archive))
    print("validate_phase5b_delivery self-test: OK")


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return

    if not args.science_files:
        raise SystemExit(
            "--science-files must contain the complete workflow-owned Phase-5B artifact inventory"
        )

    root = Path(args.root).resolve()
    science_paths: set[str] = set()
    for raw in args.science_files:
        relative = PurePosixPath(raw).as_posix()
        if (
            not relative
            or PurePosixPath(relative).is_absolute()
            or ".." in PurePosixPath(relative).parts
        ):
            raise SystemExit(f"unsafe --science-files path: {raw!r}")
        science_paths.add(relative)
    out_tsv = resolve(root, args.out_tsv)
    out_md = resolve(root, args.out_md)
    audit = Audit()

    claims_path = root / "results/tables/phase5b_claim_trace.tsv"
    audit.run(
        "claim trace is complete and locally addressable",
        lambda: f"{len(read_claims(claims_path))} unique claims with complete delivery traces",
    )

    for relative in VALIDATOR_PATHS:
        audit.run(
            f"scientific validator has no FAIL or unknown status — {Path(relative).name}",
            lambda relative=relative: validate_validator_tsv(root / relative),
        )

    report_path = root / "report/report.html"
    audit.run("rendered report is a self-contained HTML document", lambda: validate_report_self_contained(report_path))
    audit.run(
        "rendered report anchors and machine-derived headline values reconcile",
        lambda: validate_report_claims(report_path, read_claims(claims_path)),
    )
    audit.run(
        "research brief is self-contained and carries every final Phase-5B headline",
        lambda: validate_research_brief(
            root / "brief/research_brief.html", read_claims(claims_path)
        ),
    )
    audit.run(
        "Streamlit smoke Markdown and log show zero failures",
        lambda: validate_app_smoke(root / "results/APP_SMOKE.md", root / "results/logs/app_smoke.log"),
    )
    audit.run(
        "static website validation has one reconciled zero-FAIL summary",
        lambda: validate_markdown_gate(root / "results/WEBSITE_VALIDATION.md"),
    )
    audit.run(
        "offline bundle validation has one reconciled zero-FAIL summary",
        lambda: validate_markdown_gate(root / "results/WEBSITE_BUNDLE_VALIDATION.md"),
    )

    archive_path = root / "dist/conservation-genomics-reanalysis.zip"
    audit.run("ZIP CRC, paths, root, collisions, and link modes are safe", lambda: inspect_zip_safety(archive_path))
    audit.run("ZIP MANIFEST.sha256 has exact coverage and hashes", lambda: validate_zip_manifest(archive_path))
    audit.run(
        "ZIP contains every required Phase-5B delivery member",
        lambda: validate_zip_required(
            archive_path, read_claims(claims_path), science_paths
        ),
    )
    audit.run(
        "ZIP scientific and delivery members match the current workspace byte-for-byte",
        lambda: validate_zip_workspace_sync(
            archive_path, root, read_claims(claims_path), science_paths
        ),
    )
    audit.run("ZIP has a closed local dependency graph and no external runtime assets", lambda: validate_zip_offline(archive_path))
    audit.run(
        "ZIP text artifacts contain no build-host paths",
        lambda: validate_zip_no_host_paths(archive_path, root),
    )
    audit.run(
        "bundle report checksum matches the delivered ZIP",
        lambda: validate_bundle_report_digest(root / "results/WEBSITE_BUNDLE_VALIDATION.md", archive_path),
    )

    for relative in ("README.md", "PROJECT_STATUS.md", "CGplan.md"):
        audit.run(
            f"{relative} marks Phase 5B complete",
            lambda relative=relative: phase5b_completion((root / relative).read_text(encoding="utf-8")),
        )
    audit.run(
        "README contains the canonical laptop-safe Phase-5B command",
        lambda: has_canonical_command((root / "README.md").read_text(encoding="utf-8")),
    )
    audit.run(
        "provenance records are valid JSON with checksum fields",
        lambda: validate_provenance([root / relative for relative in PROVENANCE_PATHS]),
    )
    audit.run(
        "claim, provenance, checksum, validation, report, app, site, and documentation artifacts exist",
        lambda: validate_artifact_presence(
            root, read_claims(claims_path), science_paths
        ),
    )

    write_outputs(audit.checks, out_tsv, out_md)
    passed = sum(check.status == "PASS" for check in audit.checks)
    failed = sum(check.status == "FAIL" for check in audit.checks)
    print(f"Phase-5B delivery validation: {passed} PASS, {failed} FAIL")
    print(f"TSV: {out_tsv}")
    print(f"Markdown: {out_md}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
