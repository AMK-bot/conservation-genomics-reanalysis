#!/usr/bin/env python3
"""Validate the dependency-free Phase-5B portal and all of its local links."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
from html import unescape
from html.parser import HTMLParser
from itertools import product
import json
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
    "results/PHASE5B_VALIDATION.md",
    "results/PHASE5B_DATA_DICTIONARY.md",
    "results/PHASE5B_RELEASE_CONTENT_VALIDATION.md",
    "results/tables/validation_phase5b_release_content.tsv",
    "results/tables/phase5b_claim_trace.tsv",
    "results/tables/phase5b_fragility_scorecard.tsv",
    "results/provenance/wolf_froh_load.json",
    "results/provenance/peafowl_damage.json",
    "results/provenance/peafowl_ne_design.json",
    "results/provenance/phase5b_core_integration.json",
    "results/provenance/phase5b_optional_decisions.json",
    "results/provenance/wolf_roh_localization.json",
    "results/provenance/phase5b_synthesis.json",
    "results/WEBSITE_VALIDATION.md",
    "workflow/Snakefile",
    "config/config.yaml",
    "environment.lock.yml",
    "PROJECT_STATUS.md",
}

EDITOR_REQUIRED_ARTIFACTS = {
    "EDIT_WEBSITE.command",
    "EDIT_WEBSITE.md",
    "editor.html",
    "scripts/python/edit_website.py",
    "website/apply-content.js",
    "website/content-overrides.js",
    "website/content-overrides.json",
    "website/editor.css",
    "website/editor.js",
}

# This is deliberately a closed narrative-only contract. Expanding it requires
# an explicit release change so evidence values, scientific decisions, model
# outputs, and claim boundaries cannot accidentally become editable.
ALLOWED_EDITABLE_TEXT_KEYS = frozenset({
    "contribution.body",
    "contribution.prefix",
    "contribution.title",
    "corrections.eyebrow",
    "corrections.title",
    "decision_boundaries.eyebrow",
    "decision_boundaries.summary",
    "decision_boundaries.title",
    "deliverables.eyebrow",
    "deliverables.summary",
    "deliverables.title",
    "evidence.eyebrow",
    "evidence.summary",
    "evidence.title",
    "explorer.eyebrow",
    "explorer.launch_body",
    "explorer.launch_title",
    "explorer.summary",
    "explorer.title",
    "findings.eyebrow",
    "findings.summary",
    "findings.title",
    "footer.summary",
    "hero.diagram_caption",
    "hero.diagram_label",
    "hero.eyebrow",
    "hero.summary",
    "hero.title",
    "limitations.closing_quote",
    "limitations.eyebrow",
    "limitations.summary",
    "limitations.title",
    "question.eyebrow",
    "question.summary",
    "question.title",
    "reproduce.eyebrow",
    "reproduce.title",
})

REQUIRED_EDITABLE_TEXT_KEYS = frozenset({
    "contribution.body",
    "contribution.title",
    "explorer.summary",
    "explorer.title",
    "findings.summary",
    "findings.title",
    "hero.summary",
    "hero.title",
    "limitations.summary",
    "limitations.title",
    "question.summary",
    "question.title",
})

EDITABLE_LEAF_TAGS = frozenset(
    {"div", "figcaption", "h1", "h2", "h3", "p", "span", "strong"}
)
PROTECTED_EDITABLE_TAGS = frozenset(
    {"a", "button", "code", "input", "option", "select", "textarea"}
)
PROTECTED_EDITABLE_CLASSES = frozenset({
    "causal-chain",
    "correction-grid",
    "lab-boundary",
    "lab-result",
    "mind-card",
    "science-path",
    "static-claim-summary",
})
PROTECTED_EDITABLE_ATTRIBUTES = frozenset({
    "data-claim-id",
    "data-claim-trace-list",
    "data-decision",
    "data-deliverable",
    "data-phase5b-status",
    "data-result-count",
    "data-status",
})

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

SCIENCE_PATH = (
    "question",
    "prediction",
    "stress test",
    "result",
    "correction",
    "falsifier",
    "conservation consequence",
)

PHASE5B_DATA_PATH = "website/phase5b-data.js"

PHASE5B_SELECT_OPTIONS = {
    "data-wolf-gerp": {"2", "3", "4"},
    "data-wolf-roh": {"0.1", "0.5", "1", "1.5", "2"},
    "data-wolf-outcome": {"realized_load", "masked_load"},
    "data-wolf-model": {"primary", "partial_generic_homozygosity_control"},
    "data-damage-variant": {"all_snp", "transversion_only"},
    "data-ne-truth": {"100", "250", "500", "1000"},
    "data-ne-sample": {"5", "10", "15", "20", "30"},
    "data-ne-markers": {"250", "500", "1000"},
    "data-localization-pop": {
        "1983-1990", "1991-1998", "1999-2006", "2007-2014I",
        "2007-2014S", "Finland", "Immigrants", "Russia",
    },
    "data-localization-gerp": {"2", "3", "4"},
    "data-localization-roh": {"0.1", "0.5", "1", "1.5", "2"},
}

CLAIM_TRACE_FIELDS = (
    "result_table",
    "provenance",
    "validator",
    "report_anchor",
    "explorer_anchor",
    "workflow_rule",
)


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
        self.references: list[tuple[str, str, str, bool]] = []
        self.image_alts: list[tuple[str, str | None]] = []
        self.tags: list[str] = []
        self.h1_count = 0
        self.deliverable_count = 0
        self.has_meta_description = False
        self.has_skip_link = False
        self.has_title = False
        self.buttons: list[dict[str, str | None]] = []
        self.edit_keys: list[str] = []
        self.editable_nodes: list[dict[str, object]] = []
        self._element_stack: list[tuple[str, bool, dict[str, object] | None]] = []
        self._in_title = False
        self._title_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        values = dict(attrs)
        for _ancestor_tag, _protected, editable in self._element_stack:
            if editable is not None:
                editable["has_child"] = True

        classes = set((values.get("class") or "").split())
        attribute_names = set(values)
        protected_here = bool(
            tag in PROTECTED_EDITABLE_TAGS
            or classes & PROTECTED_EDITABLE_CLASSES
            or attribute_names & PROTECTED_EDITABLE_ATTRIBUTES
            or values.get("role") == "status"
            or "aria-live" in attribute_names
            or any(
                name.startswith(
                    (
                        "data-claim-",
                        "data-damage-",
                        "data-localization-",
                        "data-ne-",
                        "data-wolf-",
                    )
                )
                for name in attribute_names
            )
        )
        protected_context = protected_here or any(
            protected for _ancestor_tag, protected, _editable in self._element_stack
        )
        editable_node: dict[str, object] | None = None
        if edit_key := values.get("data-edit-key"):
            self.edit_keys.append(edit_key)
            editable_node = {
                "key": edit_key,
                "tag": tag,
                "has_child": False,
                "protected_context": protected_context,
                "text": [],
            }
            self.editable_nodes.append(editable_node)
        self._element_stack.append((tag, protected_context, editable_node))

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
        if tag == "button":
            self.buttons.append(values)
        runtime_attrs = set(RUNTIME_ATTRIBUTES.get(tag, set()))
        if tag == "link":
            rels = {part.lower() for part in values.get("rel", "").split()}
            if rels & RUNTIME_LINK_RELS:
                runtime_attrs.add("href")
        for attribute in ("href", "src", "srcset", "poster", "data", "xlink:href"):
            if value := values.get(attribute):
                candidates = split_srcset(value) if attribute == "srcset" else [value]
                self.references.extend(
                    (tag, attribute, candidate, attribute in runtime_attrs)
                    for candidate in candidates
                )

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
            self.has_title = bool("".join(self._title_text).strip())
        for index in range(len(self._element_stack) - 1, -1, -1):
            if self._element_stack[index][0] == tag:
                del self._element_stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_text.append(data)
        for _tag, _protected, editable in self._element_stack:
            if editable is not None:
                text_parts = editable["text"]
                if isinstance(text_parts, list):
                    text_parts.append(data)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def visible_text(fragment: str) -> str:
    """Return normalized human-visible text from a small HTML fragment."""
    fragment = re.sub(r"(?is)<(?:script|style)\b[^>]*>.*?</(?:script|style)>", " ", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", unescape(fragment)).strip()


def element_blocks(source: str, tag: str, class_name: str | None = None) -> list[tuple[str, str]]:
    """Extract non-self-nested blocks, optionally filtering on a CSS class."""
    blocks: list[tuple[str, str]] = []
    pattern = re.compile(rf"(?is)<{re.escape(tag)}\b([^>]*)>(.*?)</{re.escape(tag)}\s*>")
    for match in pattern.finditer(source):
        attrs, inner = match.groups()
        if class_name is not None:
            class_match = re.search(r"(?is)\bclass\s*=\s*(['\"])(.*?)\1", attrs)
            classes = class_match.group(2).split() if class_match else []
            if class_name not in classes:
                continue
        blocks.append((attrs, inner))
    return blocks


def first_block(source: str, tag: str, class_name: str) -> tuple[str, str] | None:
    blocks = element_blocks(source, tag, class_name)
    return blocks[0] if blocks else None


def attribute_value(attrs: str, name: str) -> str | None:
    match = re.search(
        rf"(?is)(?<![-\w]){re.escape(name)}(?![-\w])\s*=\s*(['\"])(.*?)\1",
        attrs,
    )
    return unescape(match.group(2)) if match else None


def has_attribute(attrs: str, name: str) -> bool:
    return bool(re.search(rf"(?is)(?<![-\w]){re.escape(name)}(?![-\w])", attrs))


def select_options(source: str, data_attribute: str) -> set[str]:
    for attrs, inner in element_blocks(source, "select"):
        if not has_attribute(attrs, data_attribute):
            continue
        values: set[str] = set()
        for option_attrs, option_inner in element_blocks(inner, "option"):
            value = attribute_value(option_attrs, "value")
            values.add((value if value is not None else visible_text(option_inner)).strip())
        return values
    return set()


def has_labelled_select(source: str, data_attribute: str) -> bool:
    """Accept a native select nested in a label or joined by for/id."""
    selected_attrs: str | None = None
    for attrs, _inner in element_blocks(source, "select"):
        if has_attribute(attrs, data_attribute):
            selected_attrs = attrs
            break
    if selected_attrs is None:
        return False
    for _label_attrs, label_inner in element_blocks(source, "label"):
        for select_attrs, _select_inner in element_blocks(label_inner, "select"):
            if has_attribute(select_attrs, data_attribute):
                return bool(visible_text(label_inner))
    identifier = attribute_value(selected_attrs, "id")
    if not identifier:
        return False
    for label_attrs, label_inner in element_blocks(source, "label"):
        if attribute_value(label_attrs, "for") == identifier and visible_text(label_inner):
            return True
    return False


def css_media_block(source: str, condition: str) -> str:
    """Extract one @media block with brace balancing."""
    match = re.search(rf"@media\s*\(\s*{re.escape(condition)}\s*\)\s*\{{", source, re.I)
    if not match:
        return ""
    start = match.end()
    depth = 1
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index]
    return ""


def parse_phase5b_payload(source: str) -> dict[str, object]:
    match = re.search(r"(?s)window\.PHASE5B_DATA\s*=\s*(\{.*\})\s*;\s*$", source)
    if not match:
        raise ValueError("expected one window.PHASE5B_DATA JSON assignment")
    payload = json.loads(match.group(1))
    if not isinstance(payload, dict):
        raise ValueError("Phase-5B browser payload is not an object")
    return payload


def normalized_numeric(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def phase5b_payload_grid_errors(payload: dict[str, object]) -> list[str]:
    """Check that every native control combination has a precomputed row."""
    errors: list[str] = []
    expected_lists = {
        "wolfAssociations": 60,
        "wolfLocalization": 120,
        "damageEffects": 8,
        "neDesign": 60,
        "claims": 6,
        "optionalDecisions": 2,
    }
    for key, minimum in expected_lists.items():
        value = payload.get(key)
        if not isinstance(value, list) or len(value) < minimum:
            row_count = len(value) if isinstance(value, list) else "no"
            errors.append(f"{key} has {row_count} rows; expected >= {minimum}")

    wolf = payload.get("wolfAssociations")
    if isinstance(wolf, list):
        observed = {
            (
                normalized_numeric(row.get("gerp_threshold")),
                normalized_numeric(row.get("roh_cutoff_mb")),
                row.get("outcome"),
                row.get("model"),
            )
            for row in wolf
            if isinstance(row, dict)
        }
        expected = set(
            product(
                (2.0, 3.0, 4.0),
                (0.1, 0.5, 1.0, 1.5, 2.0),
                ("realized_load", "masked_load"),
                ("primary", "partial_generic_homozygosity_control"),
            )
        )
        if observed != expected or len(wolf) != 60:
            errors.append(f"wolf grid has {len(observed)} unique cells across {len(wolf)} rows; expected 60/60")

    damage = payload.get("damageEffects")
    if isinstance(damage, list):
        observed = {
            (row.get("variant_set"), row.get("metric"))
            for row in damage
            if isinstance(row, dict)
        }
        expected = set(
            product(
                ("all_snp", "transversion_only"),
                ("pi", "Ho", "He", "allelic_richness"),
            )
        )
        if observed != expected or len(damage) != 8:
            errors.append(f"damage grid has {len(observed)} unique cells across {len(damage)} rows; expected 8/8")

    localization = payload.get("wolfLocalization")
    if isinstance(localization, list):
        observed = {
            (
                row.get("POP"),
                normalized_numeric(row.get("gerp_threshold")),
                normalized_numeric(row.get("roh_cutoff_mb")),
            )
            for row in localization
            if isinstance(row, dict)
        }
        expected = set(
            product(
                (
                    "1983-1990", "1991-1998", "1999-2006", "2007-2014I",
                    "2007-2014S", "Finland", "Immigrants", "Russia",
                ),
                (2.0, 3.0, 4.0),
                (0.1, 0.5, 1.0, 1.5, 2.0),
            )
        )
        boolean_flags = all(
            isinstance(row, dict) and isinstance(row.get("beyond_null"), bool)
            for row in localization
        )
        denominator_schema = all(
            isinstance(row, dict)
            and isinstance(row.get("inside_eligible_genotype_calls"), (int, float))
            and isinstance(row.get("outside_eligible_genotype_calls"), (int, float))
            and "inside_callable_sites" not in row
            and "outside_callable_sites" not in row
            for row in localization
        )
        if (
            observed != expected
            or len(localization) != 120
            or not boolean_flags
            or not denominator_schema
        ):
            errors.append(
                f"localization grid has {len(observed)} unique cells across "
                f"{len(localization)} rows; expected 120/120 with boolean flags and "
                "eligible-genotype-call denominator fields"
            )

    ne_design = payload.get("neDesign")
    if isinstance(ne_design, list):
        scenario_rows = [
            row
            for row in ne_design
            if isinstance(row, dict) and row.get("analysis_type") == "scenario"
        ]
        observed = {
            (
                normalized_numeric(row.get("true_ne")),
                normalized_numeric(row.get("sample_size")),
                normalized_numeric(row.get("marker_density")),
            )
            for row in scenario_rows
        }
        expected = set(
            product(
                (100.0, 250.0, 500.0, 1000.0),
                (5.0, 10.0, 15.0, 20.0, 30.0),
                (250.0, 500.0, 1000.0),
            )
        )
        if observed != expected or len(scenario_rows) != 60:
            errors.append(
                f"N_e scenario grid has {len(observed)} unique cells across "
                f"{len(scenario_rows)} rows; expected 60/60"
            )
        boundary_rows = [
            row for row in scenario_rows if normalized_numeric(row.get("true_ne")) == 500.0
        ]
        boundary_fields = (
            "boundary_confident_pass_rate", "boundary_confident_fail_rate",
            "indeterminate_rate", "execution_failure_rate", "correct_confident_rate",
            "incorrect_confident_rate",
        )
        boundary_values_ok = len(boundary_rows) == 15
        for row in boundary_rows:
            values = {field: normalized_numeric(row.get(field)) for field in boundary_fields}
            boundary_values_ok = boundary_values_ok and all(
                value is not None for value in values.values()
            )
            if not boundary_values_ok:
                break
            boundary_values_ok = (
                abs(
                    values["boundary_confident_pass_rate"]
                    + values["boundary_confident_fail_rate"]
                    + values["indeterminate_rate"]
                    + values["execution_failure_rate"]
                    - 1.0
                ) <= 1e-12
                and values["correct_confident_rate"] == 0.0
                and values["incorrect_confident_rate"] == 0.0
                and str(row.get("truth_class")) == "boundary"
            )
            if not boundary_values_ok:
                break
        nonboundary_values_ok = all(
            normalized_numeric(row.get("boundary_confident_pass_rate")) == 0.0
            and normalized_numeric(row.get("boundary_confident_fail_rate")) == 0.0
            for row in scenario_rows
            if normalized_numeric(row.get("true_ne")) != 500.0
        )
        if not boundary_values_ok or not nonboundary_values_ok:
            errors.append(
                "N_e boundary payload must contain 15 true-Ne=500 rows partitioned into "
                "boundary pass/fail, indeterminate, and execution failure with zero "
                "correct/incorrect rates; non-boundary boundary rates must be zero"
            )
    claims = payload.get("claims")
    if isinstance(claims, list) and len(claims) != 6:
        errors.append(f"claims has {len(claims)} rows; expected exactly 6")
    decisions = payload.get("optionalDecisions")
    if isinstance(decisions, list) and len(decisions) != 2:
        errors.append(f"optionalDecisions has {len(decisions)} rows; expected exactly 2")
    return errors


def phase5b_claim_errors(root: Path, claims: object) -> list[str]:
    """Validate trace fields and every dynamic local target/anchor."""
    if not isinstance(claims, list):
        return ["claims is not a list"]
    errors: list[str] = []
    required_evidence = {
        "claim_id",
        "headline",
        "estimate",
        "uncertainty",
        "change_operator",
        "change_threshold",
        "observed_value",
        "unit",
        "what_changes_mind",
        "scientific_boundary",
        *CLAIM_TRACE_FIELDS,
    }
    for index, claim in enumerate(claims, start=1):
        if not isinstance(claim, dict):
            errors.append(f"claim {index} is not an object")
            continue
        missing = sorted(
            field
            for field in required_evidence
            if field not in claim or claim[field] is None or str(claim[field]).strip() == ""
        )
        if missing:
            errors.append(f"claim {index} missing {','.join(missing)}")
            continue
        for field in CLAIM_TRACE_FIELDS:
            value = str(claim[field]).strip()
            parsed = urlsplit(value)
            if parsed.scheme or parsed.netloc or not parsed.path:
                errors.append(f"claim {index} {field} is not repository-local: {value}")
                continue
            target = (root / unquote(parsed.path)).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                errors.append(f"claim {index} {field} escapes repository: {value}")
                continue
            if not target.is_file():
                errors.append(f"claim {index} {field} is missing: {value}")
                continue
            fragment = unquote(parsed.fragment)
            if not fragment:
                continue
            target_text = target.read_text(encoding="utf-8", errors="replace")
            if target.suffix.lower() in {".html", ".htm"}:
                identifiers = set(
                    re.findall(r"(?is)\bid\s*=\s*['\"]([^'\"]+)['\"]", target_text)
                )
                if fragment not in identifiers:
                    errors.append(f"claim {index} {field} anchor is missing: {value}")
            elif target.suffix.lower() == ".smk":
                if not re.search(rf"(?m)^\s*rule\s+{re.escape(fragment)}\s*:", target_text):
                    errors.append(f"claim {index} {field} rule is missing: {value}")
    return errors


def reference_path(value: str) -> tuple[str, str]:
    parsed = urlsplit(value)
    return unquote(parsed.path), unquote(parsed.fragment)


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


def dynamic_external_runtime_references(text: str) -> list[str]:
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


def css_external_runtime_references(text: str) -> list[str]:
    values = [match.group(2).strip() for match in CSS_URL_RE.finditer(text)]
    values.extend(match.group(1).strip() for match in CSS_IMPORT_RE.finditer(text))
    external: list[str] = []
    for value in values:
        parsed = urlsplit(value)
        if value.startswith("//") or parsed.netloc:
            external.append(value)
        elif parsed.scheme and parsed.scheme.lower() not in {"data", "blob"}:
            external.append(value)
    return external


def editor_contract_checks(root: Path, index_source: str, parser: SiteParser) -> list[Check]:
    """Validate the editor's narrow content contract and local-write boundary."""

    editable_errors: list[str] = []
    counts = Counter(parser.edit_keys)
    duplicate_keys = sorted(key for key, count in counts.items() if count > 1)
    if duplicate_keys:
        editable_errors.append("duplicate keys: " + ", ".join(duplicate_keys))
    actual_keys = set(parser.edit_keys)
    unexpected_keys = sorted(actual_keys - ALLOWED_EDITABLE_TEXT_KEYS)
    missing_keys = sorted(ALLOWED_EDITABLE_TEXT_KEYS - actual_keys)
    missing_core = sorted(REQUIRED_EDITABLE_TEXT_KEYS - actual_keys)
    if unexpected_keys:
        editable_errors.append("unapproved keys: " + ", ".join(unexpected_keys))
    if missing_keys:
        editable_errors.append("allowlisted keys absent: " + ", ".join(missing_keys))
    if missing_core:
        editable_errors.append("required core keys absent: " + ", ".join(missing_core))

    for node in parser.editable_nodes:
        key = str(node.get("key", ""))
        tag = str(node.get("tag", ""))
        if tag not in EDITABLE_LEAF_TAGS:
            editable_errors.append(f"{key} uses unsupported <{tag}> element")
        if node.get("has_child"):
            editable_errors.append(f"{key} is not a text-only leaf")
        if node.get("protected_context"):
            editable_errors.append(f"{key} is inside protected scientific/status content")
        text_parts = node.get("text")
        visible = "".join(text_parts) if isinstance(text_parts, list) else ""
        if not visible.strip():
            editable_errors.append(f"{key} has no canonical text")

    script_sources = [
        value
        for tag, attribute, value, _runtime in parser.references
        if tag == "script" and attribute == "src"
    ]
    content_script = "website/content-overrides.js"
    apply_script = "website/apply-content.js"
    for source in (content_script, apply_script):
        if source not in script_sources:
            editable_errors.append(f"index lacks {source}")
        deferred = re.search(
            rf"(?is)<script\b(?=[^>]*\bdefer\b)"
            rf"(?=[^>]*\bsrc\s*=\s*['\"]{re.escape(source)}['\"])[^>]*>",
            index_source,
        )
        if deferred is None:
            editable_errors.append(f"index does not load {source} with defer")
    if content_script in script_sources and apply_script in script_sources:
        if script_sources.index(content_script) > script_sources.index(apply_script):
            editable_errors.append("apply-content.js loads before content-overrides.js")
    site_script = "website/site.js"
    if apply_script in script_sources and site_script in script_sources:
        if script_sources.index(apply_script) > script_sources.index(site_script):
            editable_errors.append("site.js loads before the narrative overrides are applied")

    editable_ok = not editable_errors
    editable_detail = (
        f"exactly {len(actual_keys)} unique allowlisted text-only narrative leaves; "
        "scientific/status contexts remain locked"
        if editable_ok
        else "; ".join(editable_errors[:10])
    )

    state_errors: list[str] = []
    override_values: dict[str, str] | None = None
    missing_artifacts = sorted(
        relative for relative in EDITOR_REQUIRED_ARTIFACTS if not (root / relative).is_file()
    )
    if missing_artifacts:
        state_errors.append("missing artifacts: " + ", ".join(missing_artifacts))

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key {key}")
            result[key] = value
        return result

    state_path = root / "website/content-overrides.json"
    if state_path.is_file():
        try:
            state = json.loads(
                state_path.read_text(encoding="utf-8"),
                object_pairs_hook=unique_object,
            )
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            state_errors.append(f"content-overrides.json is unreadable: {exc}")
            state = None
        if not isinstance(state, dict):
            state_errors.append("content-overrides.json must contain one object")
        else:
            expected_fields = {"version", "revision", "updated_at", "values"}
            if set(state) != expected_fields:
                state_errors.append(
                    "content-overrides.json fields differ from "
                    + ", ".join(sorted(expected_fields))
                )
            if type(state.get("version")) is not int or state.get("version") != 1:
                state_errors.append("content-overrides.json version must be integer 1")
            updated_at = state.get("updated_at")
            if updated_at is not None and not isinstance(updated_at, str):
                state_errors.append("content-overrides.json updated_at must be text or null")
            values = state.get("values")
            if not isinstance(values, dict):
                state_errors.append("content-overrides.json values must be an object")
            else:
                unknown = sorted(set(values) - actual_keys)
                non_text = sorted(key for key, value in values.items() if not isinstance(value, str))
                if unknown:
                    state_errors.append("override values contain locked keys: " + ", ".join(unknown))
                if non_text:
                    state_errors.append("override values are not text: " + ", ".join(non_text))
                if not unknown and not non_text:
                    override_values = values
                    canonical = json.dumps(
                        values,
                        ensure_ascii=True,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    expected_revision = hashlib.sha256(canonical).hexdigest()
                    if state.get("revision") != expected_revision:
                        state_errors.append("content-overrides.json revision does not match values")

    content_js_path = root / "website/content-overrides.js"
    if content_js_path.is_file():
        content_js = content_js_path.read_text(encoding="utf-8")
        assignment = re.fullmatch(
            r"\s*window\.WEBSITE_CONTENT_OVERRIDES\s*=\s*Object\.freeze\((\{.*\})\);\s*",
            content_js,
            flags=re.DOTALL,
        )
        if assignment is None:
            state_errors.append("content-overrides.js lacks its generated frozen assignment")
        else:
            try:
                js_values = json.loads(assignment.group(1), object_pairs_hook=unique_object)
            except (ValueError, json.JSONDecodeError) as exc:
                state_errors.append(f"content-overrides.js contains invalid JSON: {exc}")
            else:
                if override_values is not None and js_values != override_values:
                    state_errors.append("content-overrides.js does not match content-overrides.json")

    apply_path = root / "website/apply-content.js"
    if apply_path.is_file():
        apply_source = apply_path.read_text(encoding="utf-8")
        for marker in (
            "window.WEBSITE_CONTENT_OVERRIDES",
            'querySelectorAll("[data-edit-key]")',
            "textContent",
        ):
            if marker not in apply_source:
                state_errors.append(f"apply-content.js lacks {marker}")
        if "innerHTML" in apply_source or "insertAdjacentHTML" in apply_source:
            state_errors.append("apply-content.js uses an HTML-injection API")

    state_ok = not state_errors
    state_detail = (
        f"all {len(EDITOR_REQUIRED_ARTIFACTS)} editor artifacts present; revision and generated "
        f"JavaScript agree for {len(override_values or {})} saved overrides"
        if state_ok
        else "; ".join(state_errors[:10])
    )

    editor_errors: list[str] = []
    editor_path = root / "editor.html"
    if editor_path.is_file():
        editor_source = editor_path.read_text(encoding="utf-8")
        editor_parser = SiteParser()
        editor_parser.feed(editor_source)
        required_ids = {
            "connectionBanner",
            "discardButton",
            "exportButton",
            "importButton",
            "importFile",
            "openSiteLink",
            "resetButton",
            "saveButton",
            "saveStatus",
            "selectionLabel",
            "sitePreview",
            "undoButton",
        }
        missing_ids = sorted(required_ids - editor_parser.ids)
        if missing_ids:
            editor_errors.append("editor controls absent: " + ", ".join(missing_ids))
        editor_refs = {value for _tag, _attribute, value, _runtime in editor_parser.references}
        for asset in ("website/editor.css", "website/editor.js"):
            if asset not in editor_refs:
                editor_errors.append(f"editor.html lacks {asset}")
        if re.search(
            r"(?is)<iframe\b(?=[^>]*\bid\s*=\s*['\"]sitePreview['\"])"
            r"(?=[^>]*\bsrc\s*=\s*['\"]index\.html\?editor-preview=1['\"])[^>]*>",
            editor_source,
        ) is None:
            editor_errors.append("editor iframe does not target index.html?editor-preview=1")
        remote_editor_runtime = dynamic_external_runtime_references(editor_source)
        if remote_editor_runtime:
            editor_errors.append("editor.html contains external runtime loading")

    editor_js_path = root / "website/editor.js"
    if editor_js_path.is_file():
        editor_js = editor_js_path.read_text(encoding="utf-8")
        for marker in (
            "/api/content",
            "X-Editor-Token",
            "base_revision",
            "contentEditable",
            "textContent",
            "beforeunload",
            'action: "save"',
            'action: "undo"',
            'action: "reset"',
            "error.status === 409",
        ):
            if marker not in editor_js:
                editor_errors.append(f"editor.js lacks {marker}")
        if dynamic_external_runtime_references(editor_js):
            editor_errors.append("editor.js contains an external runtime dependency")

    editor_css_path = root / "website/editor.css"
    if editor_css_path.is_file():
        editor_css = editor_css_path.read_text(encoding="utf-8")
        if css_external_runtime_references(editor_css):
            editor_errors.append("editor.css contains an external runtime dependency")

    server_path = root / "scripts/python/edit_website.py"
    if server_path.is_file():
        server_source = server_path.read_text(encoding="utf-8")
        for marker in (
            "127.0.0.1",
            "ThreadingHTTPServer",
            "secrets.token_urlsafe",
            "X-Editor-Token",
            "base_revision",
            "revision_conflict",
            "409",
            "Cache-Control",
            "no-store",
            'self.headers.get("Host"',
            'self.headers.get("Origin"',
            "Content-Length",
            "application/json",
            "os.replace",
            "_reject_hidden_static_path",
            "STATE_FILE",
            "PREVIOUS_FILE",
            "JAVASCRIPT_FILE",
        ):
            if marker not in server_source:
                editor_errors.append(f"edit_website.py lacks security marker {marker}")
        if "0.0.0.0" in server_source:
            editor_errors.append("edit_website.py binds to all network interfaces")

    launcher_path = root / "EDIT_WEBSITE.command"
    if launcher_path.is_file():
        launcher_source = launcher_path.read_text(encoding="utf-8")
        if "scripts/python/edit_website.py" not in launcher_source:
            editor_errors.append("EDIT_WEBSITE.command does not start the local editor")

    editor_ok = not editor_errors and not missing_artifacts
    editor_detail = (
        "complete editor controls; loopback-only token API, optimistic revision conflicts, "
        "atomic writes, and offline assets"
        if editor_ok
        else "; ".join([*missing_artifacts, *editor_errors][:10])
    )

    return [
        Check("narrow allowlisted website-text contract", editable_ok, editable_detail),
        Check("versioned editor state and text-only application", state_ok, state_detail),
        Check("private localhost editor controls and write boundary", editor_ok, editor_detail),
    ]


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
    checks.extend(editor_contract_checks(root, text, parser))

    science_block = first_block(text, "ol", "science-path")
    science_labels: tuple[str, ...] = ()
    if science_block:
        labels: list[str] = []
        for _attrs, item in element_blocks(science_block[1], "li"):
            spans = element_blocks(item, "span")
            labels.append(visible_text(spans[0][1]).lower() if spans else "")
        science_labels = tuple(labels)
    checks.append(
        Check(
            "Phase-5B scientific path uses the locked order",
            science_labels == SCIENCE_PATH,
            " → ".join(science_labels) if science_labels else "science-path list missing",
        )
    )

    hero_block = first_block(text, "section", "hero")
    hero_source = hero_block[1] if hero_block else ""
    hero_copy = visible_text(hero_source).lower()
    old_counter_classes = (
        "status-panel__number",
        "status-panel__bar",
        "status-panel__facts",
    )
    old_counter_language = (
        "project readiness",
        "admissions-ready",
        "checks pass",
        "science gates",
        "website gate",
        "completion record",
    )
    counter_language = re.search(
        r"(?:validation|checks?|passes?|failures?).{0,55}\b\d+\s*/\s*\d+|"
        r"\b\d+\s*/\s*\d+.{0,55}(?:validation|checks?|passes?|failures?)",
        hero_copy,
    )
    no_hero_counter = bool(hero_block) and not any(
        class_name in hero_source for class_name in old_counter_classes
    ) and not any(phrase in hero_copy for phrase in old_counter_language) and counter_language is None
    checks.append(
        Check(
            "hero leads with science rather than a validation counter",
            no_hero_counter,
            "causal/scientific content occupies the hero aside"
            if no_hero_counter
            else "legacy validation-count markup or count language remains in the hero",
        )
    )

    causal_block = first_block(hero_source, "ol", "causal-chain")
    causal_copy = visible_text(causal_block[1]).lower() if causal_block else ""
    causal_terms = (
        "demographic history",
        "analysis choices",
        "measured proxies",
        "estimator decisions",
    )
    causal_positions = [causal_copy.find(term) for term in causal_terms]
    absent_fitness = (
        "not observed" in hero_copy
        and "fitness" in hero_copy
        and all(term in hero_copy for term in ("survival", "fertility", "reproductive success"))
    )
    causal_ok = (
        causal_block is not None
        and all(position >= 0 for position in causal_positions)
        and causal_positions == sorted(causal_positions)
        and absent_fitness
    )
    checks.append(
        Check(
            "causal boundary stops before absent fitness outcomes",
            causal_ok,
            "demographic history → choices → proxies → decisions; survival, fertility, reproduction, and fitness absent"
            if causal_ok
            else "ordered causal chain or explicit absent-fitness boundary missing",
        )
    )

    local_targets: set[str] = set()
    missing_targets: list[str] = []
    missing_anchors: list[str] = []
    external_runtime: list[str] = []
    for tag, _attribute, value, runtime in parser.references:
        stripped = value.strip()
        parsed = urlsplit(stripped)
        if stripped.startswith("//") or parsed.netloc or parsed.scheme in {"http", "https"}:
            if runtime:
                external_runtime.append(value)
            continue
        if parsed.scheme in {"mailto", "tel", "data", "blob"}:
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

    for relative in sorted(local_targets):
        target = root / relative
        if not target.is_file():
            continue
        suffix = target.suffix.lower()
        if suffix == ".css":
            external_runtime.extend(css_external_runtime_references(target.read_text(encoding="utf-8")))
        elif suffix in {".html", ".htm", ".svg", ".js", ".mjs"}:
            external_runtime.extend(
                dynamic_external_runtime_references(
                    target.read_text(encoding="utf-8", errors="replace")
                )
            )

    unique_missing_targets = list(dict.fromkeys(missing_targets))
    checks.append(
        Check(
            "all local links and media targets exist",
            not unique_missing_targets,
            f"{len(local_targets)} unique local targets"
            if not unique_missing_targets
            else "; ".join(unique_missing_targets[:8]),
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

    result_count_match = re.search(
        r"<[^>]*\bdata-result-count\b[^>]*>\s*(\d+)\s+deliverables?\s*</",
        text,
        re.IGNORECASE,
    )
    result_count_ok = (
        result_count_match is not None
        and int(result_count_match.group(1)) == parser.deliverable_count
    )
    checks.append(
        Check(
            "no-script deliverable count matches the library",
            result_count_ok,
            f"placeholder and parsed library both report {parser.deliverable_count} deliverables"
            if result_count_ok
            else (
                f"placeholder={result_count_match.group(1) if result_count_match else 'missing'}; "
                f"parsed cards={parser.deliverable_count}"
            ),
        )
    )

    labelled_controls = {
        selector: has_labelled_select(text, selector) for selector in PHASE5B_SELECT_OPTIONS
    }
    option_sets = {selector: select_options(text, selector) for selector in PHASE5B_SELECT_OPTIONS}
    controls_ok = all(labelled_controls.values()) and all(
        option_sets[selector] == expected
        for selector, expected in PHASE5B_SELECT_OPTIONS.items()
    )
    bad_controls = [
        selector
        for selector, expected in PHASE5B_SELECT_OPTIONS.items()
        if not labelled_controls[selector] or option_sets[selector] != expected
    ]
    checks.append(
        Check(
            "native labelled wolf, damage, N_e, and localization controls",
            controls_ok,
            "11 labelled native selects expose the exact predeclared grids"
            if controls_ok
            else f"missing, unlabelled, or wrong option grids: {', '.join(bad_controls)}",
        )
    )

    mind_cards = element_blocks(text, "article", "mind-card")
    conditional_pattern = re.compile(r"\b(?:would|resolution rule|change|reopen|upgrade|stop)\b", re.I)
    numeric_pattern = re.compile(r"(?:\b\d+(?:\.\d+)?\b|[<>\u2264\u2265]=?\s*\d)")
    numeric_mind_cards = [
        visible_text(inner)
        for _attrs, inner in mind_cards
        if conditional_pattern.search(visible_text(inner))
        and numeric_pattern.search(visible_text(inner))
    ]
    mind_ok = len(mind_cards) >= 4 and len(numeric_mind_cards) == len(mind_cards)
    checks.append(
        Check(
            "numeric what-would-change-my-mind cards",
            mind_ok,
            f"{len(numeric_mind_cards)}/{len(mind_cards)} cards contain a numeric decision condition",
        )
    )

    correction_block = first_block(text, "div", "correction-grid")
    correction_cards = element_blocks(correction_block[1], "article") if correction_block else []
    correction_texts = [visible_text(inner).lower() for _attrs, inner in correction_cards]
    correction_labels = ("i thought", "check:", "correction:", "consequence:")
    correction_shape_ok = len(correction_cards) >= 4 and all(
        all(label in card for label in correction_labels) for card in correction_texts
    )
    joined_corrections = " ".join(correction_texts)
    correction_topics_ok = all(
        topic in joined_corrections for topic in ("prun", "gone2", "museum", "homozygosity")
    )
    corrections_ok = correction_shape_ok and correction_topics_ok
    checks.append(
        Check(
            "research-correction cards retain thought, check, correction, and consequence",
            corrections_ok,
            f"{len(correction_cards)} cards cover pruning, GONE2, temporal contrast, and homozygosity control"
            if corrections_ok
            else "four-part correction structure or required Phase-5B topics missing",
        )
    )

    trace_container = re.search(
        r"(?is)<[^>]+\bdata-claim-trace-list\b[^>]*\baria-live\s*=\s*['\"][^'\"]+['\"][^>]*>",
        text,
    ) or re.search(
        r"(?is)<[^>]+\baria-live\s*=\s*['\"][^'\"]+['\"][^>]*\bdata-claim-trace-list\b[^>]*>",
        text,
    )
    noscript_blocks = element_blocks(text, "noscript")
    trace_fallback = any(
        "results/tables/phase5b_claim_trace.tsv" in inner for _attrs, inner in noscript_blocks
    )
    checks.append(
        Check(
            "claim trace has a live region and no-script local fallback",
            bool(trace_container) and trace_fallback,
            "dynamic trace is announced; the machine-readable TSV remains reachable without JavaScript"
            if trace_container and trace_fallback
            else "claim-trace live region or no-script TSV fallback missing",
        )
    )

    css_path = root / "website/site.css"
    css = css_path.read_text(encoding="utf-8") if css_path.is_file() else ""
    js_path = root / "website/site.js"
    js = js_path.read_text(encoding="utf-8") if js_path.is_file() else ""
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

    keyboard_navigation_ok = (
        ".search-box input:focus-visible" in css
        and re.search(r"(?s)\.js\s+\.nav-links\s*\{[^}]*visibility:\s*hidden", css) is not None
        and re.search(r"(?s)\.js\s+\.nav-links\.is-open\s*\{[^}]*visibility:\s*visible", css) is not None
        and "closeNavigation({ restoreFocus: true })" in js
        and "navToggle.focus()" in js
    )
    checks.append(
        Check(
            "keyboard focus remains visible and mobile menu focus is contained",
            keyboard_navigation_ok,
            "search has an explicit focus ring; closed mobile links are hidden; Escape restores toggle focus"
            if keyboard_navigation_ok
            else "search focus, hidden mobile links, or Escape focus restoration is incomplete",
        )
    )

    compact_css = css_media_block(css, "max-width: 620px")
    tablet_css = css_media_block(css, "max-width: 860px")
    responsive_phase5b_ok = (
        bool(compact_css)
        and all(selector in compact_css for selector in (".science-path", ".mind-grid", ".lab-controls", ".lab-readout"))
        and "grid-template-columns: 1fr" in compact_css
        and bool(tablet_css)
        and ".trace-panel" in tablet_css
        and ".reproduce-grid" in tablet_css
        and "grid-template-columns: minmax(0, 1fr)" in tablet_css
        and re.search(
            r"(?s)\.phase5b-lab\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)",
            css,
        )
        is not None
        and re.search(r"(?s)\.lab-panel\s*\{[^}]*min-width:\s*0", css) is not None
        and re.search(r"(?s)\.reproduce-grid\s*>\s*\*\s*\{[^}]*min-width:\s*0", css)
        is not None
    )
    checks.append(
        Check(
            "Phase-5B path, cards, trace, and controls reflow responsively",
            responsive_phase5b_ok,
            "tablet and compact layouts collapse Phase-5B components; lab and reproduction "
            "grid tracks are min-width contained"
            if responsive_phase5b_ok
            else "Phase-5B responsive layout rules are incomplete",
        )
    )

    reduced_css = css_media_block(css, "prefers-reduced-motion: reduce")
    phase5b_motion_ok = (
        bool(reduced_css)
        and "scroll-behavior: auto" in reduced_css
        and ".js [data-reveal]" in reduced_css
        and "opacity: 1" in reduced_css
        and "transform: none" in reduced_css
        and "animation-duration" in reduced_css
        and "transition-duration" in reduced_css
    )
    checks.append(
        Check(
            "reduced-motion mode exposes all scientific content",
            phase5b_motion_ok,
            "smooth scroll and reveal motion are removed without hiding content"
            if phase5b_motion_ok
            else "reduced-motion reveal fallback is incomplete",
        )
    )

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

    ne_boundary_ui_ok = (
        "data-ne-correct-label" in text
        and "data-ne-incorrect-label" in text
        and "selectedTruth === 500" in js
        and "boundary_confident_pass_rate" in js
        and "boundary_confident_fail_rate" in js
        and "Boundary confident pass" in js
        and "Boundary confident fail" in js
    )
    checks.append(
        Check(
            "true-Ne=500 control switches to boundary outcomes",
            ne_boundary_ui_ok,
            (
                "boundary pass/fail rates and labels replace correct/incorrect at true Ne=500"
                if ne_boundary_ui_ok
                else "boundary-specific Ne labels or data mapping are incomplete"
            ),
        )
    )

    network_loading = re.search(
        r"\b(?:fetch|import|XMLHttpRequest|WebSocket|EventSource)\s*(?:\(|\.)",
        js,
    )
    phase5b_fallback_ok = (
        "window.PHASE5B_DATA" in js
        and "!phase5bArraysReady" in js
        and "Array.isArray" in js
        and "disablePhase5b" in js
        and ".disabled = true" in js
        and "Interactive rows unavailable; static outcomes remain:" in js
        and re.search(r"addEventListener\s*\(\s*['\"]error['\"]", js) is not None
        and ("dataset.missingAsset" in js or "data-missing-asset" in js)
        and re.search(r"getAttribute\s*\(\s*['\"]alt['\"]\s*\)", js) is not None
        and re.search(
            r"\b([A-Za-z_$][\w$]*)\.complete\s*&&\s*\1\.naturalWidth\s*===\s*0",
            js,
        ) is not None
        and ".is-missing" in css
        and ".missing-asset" in css
        and network_loading is None
    )
    checks.append(
        Check(
            "Phase-5B data and image failures degrade to local readable fallbacks",
            phase5b_fallback_ok,
            "missing data disables controls with an explanation; failed images retain alt-derived text"
            if phase5b_fallback_ok
            else "missing-data/image fallback or network-free guard missing",
        )
    )

    buttons_typed = bool(parser.buttons) and all(
        str(button.get("type", "")).lower() == "button" for button in parser.buttons
    )
    nav_button_ok = bool(
        re.search(
            r"(?is)<button\b(?=[^>]*\bdata-nav-toggle\b)(?=[^>]*\baria-expanded\s*=)(?=[^>]*\baria-controls\s*=)[^>]*>",
            text,
        )
    )
    keyboard_ok = (
        controls_ok
        and buttons_typed
        and nav_button_ok
        and re.search(r"addEventListener\s*\(\s*['\"]keydown['\"]", js) is not None
        and re.search(r"event\.key\s*===?\s*['\"]Escape['\"]", js) is not None
        and re.search(r"addEventListener\s*\(\s*['\"]change['\"]", js) is not None
        and re.search(r"\brole\s*=\s*['\"]status['\"]", text, re.I) is not None
    )
    checks.append(
        Check(
            "keyboard and native interaction semantics",
            keyboard_ok,
            f"{len(parser.buttons)} typed buttons, labelled selects, Escape handling, change events, and live status"
            if keyboard_ok
            else "button type, select label, keyboard, or status semantics missing",
        )
    )

    trace_js_ok = all(f"claim.{field}" in js for field in CLAIM_TRACE_FIELDS)
    checks.append(
        Check(
            "claim trace exposes table, provenance, validation, report, and workflow links",
            trace_js_ok,
            "six local evidence-link classes are constructed from each generated claim"
            if trace_js_ok
            else "one or more required dynamic claim-trace links are absent",
        )
    )

    phase5b_data_path = root / PHASE5B_DATA_PATH
    phase5b_payload: dict[str, object] | None = None
    payload_error = ""
    if phase5b_data_path.is_file():
        try:
            phase5b_payload = parse_phase5b_payload(phase5b_data_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            payload_error = str(error)
    else:
        payload_error = f"missing {PHASE5B_DATA_PATH}"

    data_script_match = re.search(
        r"(?is)<script\b(?=[^>]*\bdefer\b)[^>]*\bsrc\s*=\s*['\"]website/phase5b-data\.js['\"][^>]*>",
        text,
    )
    site_script_match = re.search(
        r"(?is)<script\b(?=[^>]*\bdefer\b)[^>]*\bsrc\s*=\s*['\"]website/site\.js['\"][^>]*>",
        text,
    )
    script_order_ok = bool(
        data_script_match
        and site_script_match
        and data_script_match.start() < site_script_match.start()
    )
    grid_errors = phase5b_payload_grid_errors(phase5b_payload) if phase5b_payload else []
    payload_ok = (
        phase5b_payload is not None
        and phase5b_payload.get("schemaVersion") == "phase5b-browser-v1"
        and not grid_errors
        and script_order_ok
    )
    payload_detail = (
        "local generated JSON covers 60 wolf associations, 120 localization, 8 damage, and 60 scenario-design cells and loads before site.js"
        if payload_ok
        else "; ".join(filter(None, [payload_error, *grid_errors, "wrong script order" if not script_order_ok else ""]))
    )
    checks.append(Check("complete local Phase-5B browser data", payload_ok, payload_detail))

    claim_errors = phase5b_claim_errors(root, phase5b_payload.get("claims")) if phase5b_payload else [
        "Phase-5B payload unavailable"
    ]
    checks.append(
        Check(
            "generated claims have numeric gates and resolvable local trace targets",
            not claim_errors,
            "all generated claims include uncertainty, numeric change conditions, and six verified local traces"
            if not claim_errors
            else "; ".join(claim_errors[:8]),
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
            "dependency-free behavior, and the Phase-5B scientific path, causal boundary, exact precomputed grids,",
            "numeric falsifiers, correction cards, trace links, and failure fallbacks. It also validates the closed",
            "narrative-edit allowlist, versioned override state, text-only application, and loopback editor boundary.",
            "Browser-based visual and interaction checks complement this file-level gate.",
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
