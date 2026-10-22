#!/usr/bin/env python3
"""Fail-closed Phase-5B release-content validation.

This gate validates claims made by the finished repository rather than
recomputing scientific analyses.  It deliberately has no third-party
dependencies and runs immediately before deterministic ZIP packaging.

The reproducibility record is a Markdown contract with an explicit state:
``SCIENCE_PASS`` is the transparent first-release bridge and emits one WARN;
the delivered ``PASS`` state additionally requires the canonical full-release
no-op and emits no WARN.  Both states must contain:

* a two-row table with ``run_id``, ``started_at``, ``ended_at``,
  ``elapsed_seconds``, ``jobs``, ``return_code``, and ``peak_rss_mb``;
* an exact seven-row table with repository-relative ``validator``, ``pass``,
  ``warn``, and ``fail`` values independently reconciled to each validator TSV;
* an exact six-component science-hash table with ``component``, ``artifact``,
  ``hash_method``, ``workspace_science_sha256``, ``run_1_science_sha256``, and
  ``run_2_science_sha256``. ``hash_method`` is either ``file_sha256`` for a
  deterministic artifact or ``json_pointer:<RFC6901 pointer>`` for a stored,
  runtime-excluded science hash;
* two persisted exact-path/file-SHA-256 TSVs whose listed current bytes,
  entry counts, and canonical aggregate hashes reconcile to an exact two-row
  Markdown table across the workspace and both runs;
* a unique science no-op dry-run PASS attestation, plus the exact science
  dry-run command and a nearby concrete no-op result.  ``PASS`` additionally
  requires the distinct canonical no-op attestation, command, and result.

Missing files, fields, rows, markers, or trace targets are failures.  Optional
TSV/Markdown output paths let the workflow persist the audit; without them the
validator only reports to stdout and sets its exit status.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
from html import unescape
import json
import math
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Callable
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]

CANONICAL_COMMAND = (
    "snakemake --snakefile workflow/Snakefile phase5b --cores 4 "
    "--resources mem_mb=7000"
)
SCIENCE_COMMAND = (
    "snakemake --snakefile workflow/Snakefile phase5b_science --cores 4 "
    "--resources mem_mb=7000"
)
CANONICAL_DEFERRAL = "DEFER_DUPLICATES_SOURCE_STUDY"

EXPECTED_CLAIMS = {
    "wolf_froh_load_association": "13.1",
    "peafowl_damage_falsification": "13.3",
    "peafowl_ne_study_design": "13.2",
    "wolf_roh_localization_gate": "13.4",
    "wolf_roh_localized_realized_burden": "13.4",
    "wolf_annotation_triangulation_gate": "13.5",
}
CORE_SECTIONS = ("13.1", "13.2", "13.3", "13.4", "13.6")

CLAIM_REQUIRED_COLUMNS = {
    "claim_id",
    "section",
    "headline",
    "claim_status",
    "estimate",
    "uncertainty",
    "observed_value",
    "result_table",
    "provenance",
    "validator",
    "report_anchor",
    "explorer_anchor",
    "workflow_rule",
    "change_operator",
    "change_threshold",
    "what_changes_mind",
    "scientific_boundary",
}

SURFACE_PATHS = (
    "README.md",
    "PROJECT_STATUS.md",
    "CGplan.md",
    "scripts/python/README.md",
    "website/README.md",
    "RESEARCH_JOURNEY.md",
    "FAQ.md",
    "brief/research_brief.md",
    "brief/research_brief.html",
    "brief/walkthrough.md",
    "app/streamlit_app.py",
    "index.html",
    "brief/graphical_abstract.svg",
    "report/report.qmd",
    "report/report.html",
)

COMMAND_SURFACES = (
    "README.md",
    "scripts/python/README.md",
    "website/README.md",
    "app/streamlit_app.py",
    "index.html",
    "report/report.qmd",
    "report/report.html",
)

STATUS_SURFACES = (
    "README.md",
    "PROJECT_STATUS.md",
    "CGplan.md",
    "RESEARCH_JOURNEY.md",
    "FAQ.md",
    "brief/research_brief.md",
    "brief/research_brief.html",
    "brief/walkthrough.md",
    "app/streamlit_app.py",
    "index.html",
    "brief/graphical_abstract.svg",
    "report/report.qmd",
    "report/report.html",
)

DEFERRAL_SURFACES = (
    "README.md",
    "PROJECT_STATUS.md",
    "CGplan.md",
    "scripts/python/README.md",
    "website/README.md",
    "RESEARCH_JOURNEY.md",
    "FAQ.md",
    "brief/research_brief.md",
    "brief/research_brief.html",
    "brief/walkthrough.md",
    "app/streamlit_app.py",
    "index.html",
    "brief/graphical_abstract.svg",
    "report/report.qmd",
    "report/report.html",
)

STALE_LITERALS = (
    "temporal erosion (museum vs modern)",
    "temporal-erosion angle",
    "build + validate all Phase 1-5A",
    "snakemake all --cores",
    "four validation gates",
    "32 validation passes · 0 failures",
    "Complete through Phase 5A",
    "83 local targets",
    "placeholder is not completion evidence",
    "release-validation total while clean rendering and packaging are being verified",
    "final release-validation total until the clean release record exists",
    "no aggregate release-validation count is asserted here",
    "unfinished aggregate release-validation total",
    "no final aggregate release-validation count is asserted here",
    "clean release in progress",
    "clean rendering and packaging are separate release work now in progress",
    "clean release refresh is in progress",
    "render, release-content verification, and deterministic package rebuild remain in progress",
    "synchronized rendering, and packaging remain in progress",
    "synchronized rendering/package rebuild remain in progress",
    "rendering and packaging are release tasks still in progress",
    "being rebuilt and must not be described as current",
    "while preparing a clean release",
    "unfinished release total",
    "claims are being synchronized",
    "clean release is still being assembled",
    "the remaining release work is",
    "once the clean package rebuild passes",
    "complete for scientific analyses and decision gates",
    "still-running clean release",
    "last cleanly verified release",
    "clean release rendering and packaging are tracked separately",
    "packaging are separate work",
    "must not be presented as the final Phase-5B release",
    "clean-release verification remains a separately linked audit record",
)

RUN_COLUMNS = {
    "run_id",
    "started_at",
    "ended_at",
    "elapsed_seconds",
    "jobs",
    "return_code",
    "peak_rss_mb",
}
VALIDATOR_COLUMNS = {"validator", "pass", "warn", "fail"}
HASH_COLUMNS = {
    "component",
    "artifact",
    "hash_method",
    "workspace_science_sha256",
    "run_1_science_sha256",
    "run_2_science_sha256",
}
MANIFEST_COLUMN_ORDER = (
    "manifest_class",
    "entries",
    "workspace_sha256",
    "run_1_sha256",
    "run_2_sha256",
    "status",
)
MANIFEST_COLUMNS = set(MANIFEST_COLUMN_ORDER)
EXPECTED_VALIDATOR_PATHS = (
    "results/tables/validation_wolf_robustness.tsv",
    "results/tables/validation_peafowl_damage.tsv",
    "results/tables/validation_peafowl_ne_design.tsv",
    "results/tables/validation_phase5b_core_integration.tsv",
    "results/tables/validation_phase5b_decisions.tsv",
    "results/tables/validation_wolf_roh_localization.tsv",
    "results/tables/validation_phase5b.tsv",
)
EXPECTED_SCIENCE_HASHES = {
    "wolf_froh_load_association": (
        "results/provenance/wolf_froh_load.json",
        "json_pointer:/scientific_hash",
    ),
    "peafowl_damage_falsification": (
        "results/tables/peafowl_damage_effects.tsv",
        "file_sha256",
    ),
    "peafowl_ne_scenario": (
        "results/provenance/peafowl_ne_design.json",
        "json_pointer:/scientific_hashes/scenario_runtime_excluded_sha256",
    ),
    "peafowl_ne_empirical": (
        "results/provenance/peafowl_ne_design.json",
        "json_pointer:/scientific_hashes/empirical_runtime_excluded_sha256",
    ),
    "wolf_roh_localization": (
        "results/provenance/wolf_roh_localization.json",
        "json_pointer:/scientific_hash",
    ),
    "phase5b_synthesis": (
        "results/tables/phase5b_claim_trace.tsv",
        "file_sha256",
    ),
}
EXPECTED_MANIFEST_CLASSES = (
    "frozen_upstream_inputs",
    "external_source_leaves",
)
EXPECTED_FROZEN_UPSTREAM_PATHS = tuple(sorted([
    "results/qc/comparative.norm.vcf.gz",
    "results/qc/setA.standard.vcf.gz",
    "results/qc/temporal_popmap.tsv",
    "results/tables/validation_phase4.tsv",
    "results/tables/wolf_load.tsv",
    "results/tables/wolf_roh.tsv",
    "results/wolf/autosome_lengths.tsv",
    "results/wolf/popmap.tsv",
    "results/wolf/samples.txt",
] + [
    path
    for chromosome in range(1, 39)
    for path in (
        f"results/wolf/gerp/chr{chromosome}.bed",
        f"results/wolf/load/chr{chromosome}.tsv",
        f"results/wolf/roh/chr{chromosome}.rg.txt",
    )
]))
EXPECTED_EXTERNAL_SOURCE_PATHS = tuple(sorted((
    "data/peafowl/raw/Comparative_genomic_dataset_F.vcf.gz",
    "data/wolf/gerp/100S95F14R.chr1-38.allSNPs.rates.unique.bed",
    "data/wolf/vcf/Pol.2out.mac2/100S95F14R.chr1-38.allSNPs.wfm.vcf.gz",
    "data/wolf/vcf/Pol.2out.mac2/100S95F14R.chr1-38.allSNPs.wfm.vcf.gz.csi",
    "data/wolf/vcf/Pol.2out.mac2/100S95F14R.chr1-38.vepfinal.wfm.vcf.gz",
    "data/wolf/vep/Pol.2out.mac2/sifttypes.chr1-X.txt",
    "data/wolf/vep/Pol.2out.mac2/veptypes.chr1-X.txt",
)))
EXPECTED_MANIFESTS = {
    "frozen_upstream_inputs": (
        "results/provenance/phase5b_frozen_upstream_inputs.tsv",
        EXPECTED_FROZEN_UPSTREAM_PATHS,
    ),
    "external_source_leaves": (
        "results/provenance/phase5b_external_source_leaves.tsv",
        EXPECTED_EXTERNAL_SOURCE_PATHS,
    ),
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PLAUSIBLE_HTML_TAG_RE = re.compile(
    r"""
    <!--.*?-->
    |
    <!DOCTYPE\b[^<>]*>
    |
    <\?[A-Za-z][^<>]*\?>
    |
    </?[A-Za-z][A-Za-z0-9:_-]*
    (?:
        \s+
        [A-Za-z_:][A-Za-z0-9:._-]*
        (?:
            \s*=\s*
            (?:"[^"]*"|'[^']*'|[^\s"'=<>`]+)
        )?
    )*
    \s*/?>
    """,
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)


class ReleaseContentError(RuntimeError):
    """One fail-closed release-content condition."""


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class AuditOutcome:
    status: str
    detail: str


@dataclass(frozen=True)
class MarkdownTable:
    headers: tuple[str, ...]
    rows: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class PersistedManifest:
    manifest_class: str
    artifact: str
    entries: int
    aggregate_sha256: str


class Audit:
    def __init__(self) -> None:
        self.checks: list[Check] = []

    def run(self, name: str, operation: Callable[[], str | AuditOutcome]) -> None:
        try:
            outcome = operation()
            if isinstance(outcome, AuditOutcome):
                if outcome.status not in {"PASS", "WARN"}:
                    raise ReleaseContentError(
                        f"audit operation returned unsupported status {outcome.status!r}"
                    )
                status = outcome.status
                detail = outcome.detail
            else:
                status = "PASS"
                detail = str(outcome)
        except Exception as error:  # malformed release inputs become useful FAIL rows
            message = " ".join(str(error).split())
            self.checks.append(
                Check(name, "FAIL", f"{type(error).__name__}: {message}"[:1800])
            )
        else:
            self.checks.append(Check(name, status, str(detail)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", default=str(ROOT), help="repository root")
    parser.add_argument(
        "--claims",
        default="results/tables/phase5b_claim_trace.tsv",
        help="six-row Phase-5B claim trace, relative to --root unless absolute",
    )
    parser.add_argument(
        "--decisions",
        default="results/tables/phase5b_optional_decisions.tsv",
        help="optional-study decision table, relative to --root unless absolute",
    )
    parser.add_argument(
        "--reproducibility",
        default="results/PHASE5B_REPRODUCIBILITY.md",
        help="final clean-verification record, relative to --root unless absolute",
    )
    parser.add_argument("--out-tsv", help="optional machine-readable audit output")
    parser.add_argument("--out-md", help="optional Markdown audit output")
    parser.add_argument(
        "--self-test", action="store_true", help="exercise positive and negative temp fixtures"
    )
    return parser.parse_args()


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def require_within_root(root: Path, path: Path) -> Path:
    resolved_root = root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as error:
        raise ReleaseContentError(f"path escapes repository root: {path}") from error
    return resolved


def read_text(root: Path, relative: str) -> str:
    path = require_within_root(root, root / relative)
    if not path.is_file():
        raise ReleaseContentError(f"missing release surface: {relative}")
    return path.read_text(encoding="utf-8")


def searchable_text(text: str) -> str:
    """Normalize markup, Markdown, and adjacent Python string literals for scans."""
    value = unescape(text).replace("\u00ad", "")
    value = re.sub(r"\\\s*\n", " ", value)
    previous = None
    while previous != value:
        previous = value
        value = re.sub(r"([\"'])\s*(?:\+\s*)?\1", "", value)
    # Strip syntactically plausible markup only.  A broad ``<[^>]*>`` pattern
    # can span ordinary Markdown inequalities (for example, from ``<5 minutes``
    # through a later ``N_e > 500``) and silently delete an entire section.
    value = PLAUSIBLE_HTML_TAG_RE.sub(" ", value)
    return " ".join(value.split())


def normalized_header(value: str) -> str:
    value = re.sub(r"<[^>]*>", " ", unescape(value))
    value = value.strip().strip("`*_ ").casefold()
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def parse_markdown_tables(text: str) -> list[MarkdownTable]:
    lines = text.splitlines()
    tables: list[MarkdownTable] = []
    index = 0
    while index + 1 < len(lines):
        header_line = lines[index].strip()
        divider_line = lines[index + 1].strip()
        if not (header_line.startswith("|") and divider_line.startswith("|")):
            index += 1
            continue
        divider_cells = [cell.strip() for cell in divider_line.strip("|").split("|")]
        if not divider_cells or not all(
            re.fullmatch(r":?-{3,}:?", cell) for cell in divider_cells
        ):
            index += 1
            continue
        raw_headers = [cell.strip() for cell in header_line.strip("|").split("|")]
        headers = tuple(normalized_header(cell) for cell in raw_headers)
        if (
            not headers
            or any(not header for header in headers)
            or len(set(headers)) != len(headers)
        ):
            raise ReleaseContentError(
                f"malformed or duplicate Markdown table headers: {raw_headers}"
            )
        if len(headers) != len(divider_cells):
            raise ReleaseContentError(f"Markdown table divider width mismatch: {raw_headers}")
        rows: list[dict[str, str]] = []
        index += 2
        while index < len(lines) and lines[index].strip().startswith("|"):
            cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
            if len(cells) != len(headers):
                raise ReleaseContentError(
                    f"Markdown table row width {len(cells)} != {len(headers)}: {lines[index]}"
                )
            rows.append(dict(zip(headers, cells)))
            index += 1
        tables.append(MarkdownTable(headers=headers, rows=tuple(rows)))
    return tables


def unique_table_with_columns(
    tables: list[MarkdownTable], required: set[str], label: str
) -> MarkdownTable:
    matches = [table for table in tables if required <= set(table.headers)]
    if len(matches) != 1:
        raise ReleaseContentError(
            f"expected one {label} table with columns {sorted(required)}; found {len(matches)}"
        )
    if not matches[0].rows:
        raise ReleaseContentError(f"{label} table contains zero rows")
    return matches[0]


def exact_decimal(value: object, label: str) -> Decimal:
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as error:
        raise ReleaseContentError(f"{label} is not numeric: {value!r}") from error
    if not result.is_finite():
        raise ReleaseContentError(f"{label} is not finite: {value!r}")
    return result


def exact_int(value: object, label: str, minimum: int = 0) -> int:
    number = exact_decimal(value, label)
    if number != number.to_integral_value() or number < minimum:
        raise ReleaseContentError(f"{label} must be an integer >= {minimum}: {value!r}")
    return int(number)


def safe_relative_target(value: str, label: str) -> tuple[str, str]:
    parsed = urlsplit(value.strip())
    relative = unquote(parsed.path)
    pure = PurePosixPath(relative)
    if (
        not relative
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or pure.is_absolute()
        or ".." in pure.parts
        or "\\" in relative
    ):
        raise ReleaseContentError(f"{label} is not a safe repository-relative target: {value!r}")
    return pure.as_posix(), unquote(parsed.fragment)


def read_tsv(path: Path, label: str) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file():
        raise ReleaseContentError(f"missing {label}: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        headers = list(reader.fieldnames or [])
        if not headers or len(headers) != len(set(headers)):
            raise ReleaseContentError(f"{label} has missing or duplicate headers: {headers}")
        rows = [
            {key: str(value or "").strip() for key, value in row.items()}
            for row in reader
        ]
    if not rows:
        raise ReleaseContentError(f"{label} contains zero rows")
    return headers, rows


def anchor_present(path: Path, fragment: str) -> bool:
    if not fragment:
        return False
    text = path.read_text(encoding="utf-8")
    escaped = re.escape(fragment)
    return bool(
        re.search(rf"\b(?:id|name)\s*=\s*['\"]{escaped}['\"]", text, re.IGNORECASE)
        or re.search(rf"^\s*#+\s+.*\{{#{escaped}\}}\s*$", text, re.MULTILINE)
    )


def validate_trace_target(root: Path, value: str, label: str, require_fragment: bool) -> None:
    relative, fragment = safe_relative_target(value, label)
    target = require_within_root(root, root / relative)
    if not target.is_file():
        raise ReleaseContentError(f"{label} target does not exist: {relative}")
    if require_fragment and not fragment:
        raise ReleaseContentError(f"{label} has no fragment: {value!r}")
    if require_fragment and label != "workflow_rule" and not anchor_present(target, fragment):
        raise ReleaseContentError(f"{label} fragment #{fragment} is absent from {relative}")
    if require_fragment and label == "workflow_rule":
        text = target.read_text(encoding="utf-8")
        if not re.search(rf"\brule\s+{re.escape(fragment)}\s*:", text):
            raise ReleaseContentError(f"workflow rule {fragment!r} is absent from {relative}")


def validate_claim_trace(root: Path, path: Path) -> str:
    headers, rows = read_tsv(path, "Phase-5B claim trace")
    missing = sorted(CLAIM_REQUIRED_COLUMNS - set(headers))
    if missing:
        raise ReleaseContentError(f"claim trace missing required columns: {missing}")
    if len(rows) != 6:
        raise ReleaseContentError(f"claim trace must contain exactly 6 rows; found {len(rows)}")

    ids = [row["claim_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ReleaseContentError(f"claim trace has duplicate IDs: {ids}")
    if set(ids) != set(EXPECTED_CLAIMS):
        raise ReleaseContentError(
            f"claim IDs differ: missing={sorted(set(EXPECTED_CLAIMS) - set(ids))}; "
            f"extra={sorted(set(ids) - set(EXPECTED_CLAIMS))}"
        )

    for row in rows:
        claim_id = row["claim_id"]
        empty = sorted(column for column in CLAIM_REQUIRED_COLUMNS if not row.get(column, ""))
        if empty:
            raise ReleaseContentError(f"claim {claim_id} has empty fields: {empty}")
        if row["section"] != EXPECTED_CLAIMS[claim_id]:
            raise ReleaseContentError(
                f"claim {claim_id} section {row['section']!r} != {EXPECTED_CLAIMS[claim_id]!r}"
            )
        for column in ("result_table", "provenance", "validator"):
            validate_trace_target(root, row[column], f"{claim_id}.{column}", False)
        validate_trace_target(root, row["report_anchor"], "report_anchor", True)
        validate_trace_target(root, row["explorer_anchor"], "explorer_anchor", True)
        validate_trace_target(root, row["workflow_rule"], "workflow_rule", True)

    by_id = {row["claim_id"]: row for row in rows}
    annotation = by_id["wolf_annotation_triangulation_gate"]
    if annotation["claim_status"] != CANONICAL_DEFERRAL:
        raise ReleaseContentError(
            "Section 13.5 claim_status must be "
            f"{CANONICAL_DEFERRAL!r}; found {annotation['claim_status']!r}"
        )
    if exact_decimal(annotation["observed_value"], "Section 13.5 observed_value") != 0:
        raise ReleaseContentError("Section 13.5 observed_value must equal 0")
    if exact_decimal(annotation["change_threshold"], "Section 13.5 change_threshold") != 1:
        raise ReleaseContentError("Section 13.5 change_threshold must equal 1")
    if annotation["change_operator"] != ">=":
        raise ReleaseContentError("Section 13.5 change_operator must be >=")

    localization = by_id["wolf_roh_localization_gate"]
    if localization["claim_status"] != "IMPLEMENT":
        raise ReleaseContentError(
            "Section 13.4 gate must be IMPLEMENT for the completed localization claim; "
            f"found {localization['claim_status']!r}"
        )
    return "exact six-claim set, sections, statuses, values, files, anchors, and rules reconcile"


def validate_decisions(path: Path) -> str:
    headers, rows = read_tsv(path, "Phase-5B optional-study decisions")
    required = {
        "section",
        "decision",
        "observed_value",
        "required_operator",
        "required_value",
        "evidence",
        "reopen_condition",
        "scientific_boundary",
    }
    missing = sorted(required - set(headers))
    if missing:
        raise ReleaseContentError(f"decision table missing required columns: {missing}")
    if len(rows) != 2:
        raise ReleaseContentError(f"decision table must contain exactly 2 rows; found {len(rows)}")
    sections = [row["section"] for row in rows]
    if sections.count("13.4") != 1 or sections.count("13.5") != 1:
        raise ReleaseContentError(
            f"decision table must have one row each for 13.4/13.5: {sections}"
        )
    row_134 = next(row for row in rows if row["section"] == "13.4")
    row_135 = next(row for row in rows if row["section"] == "13.5")
    if row_134["decision"] != "IMPLEMENT":
        raise ReleaseContentError(
            f"completed Section 13.4 decision is not IMPLEMENT: {row_134['decision']!r}"
        )
    if row_135["decision"] != CANONICAL_DEFERRAL:
        raise ReleaseContentError(
            f"Section 13.5 decision is not {CANONICAL_DEFERRAL}: {row_135['decision']!r}"
        )
    if exact_decimal(row_135["observed_value"], "Section 13.5 observed_value") != 0:
        raise ReleaseContentError("Section 13.5 decision observed_value must equal 0")
    if row_135["required_operator"] != ">=":
        raise ReleaseContentError("Section 13.5 decision required_operator must be >=")
    if exact_decimal(row_135["required_value"], "Section 13.5 required_value") != 1:
        raise ReleaseContentError("Section 13.5 decision required_value must equal 1")
    for section, row in (("13.4", row_134), ("13.5", row_135)):
        empty = sorted(column for column in required if not row.get(column, ""))
        if empty:
            raise ReleaseContentError(f"decision {section} has empty required fields: {empty}")
    return "13.4 IMPLEMENT and 13.5 duplicate-source deferral reconcile to numeric gates"


def validate_surface_inventory(root: Path) -> str:
    missing = [relative for relative in SURFACE_PATHS if not (root / relative).is_file()]
    if missing:
        raise ReleaseContentError(f"missing claim surfaces: {missing}")
    return f"all {len(SURFACE_PATHS)} release claim surfaces exist"


def phase5b_section(text: str) -> str:
    match = re.search(r"^#{1,3}\s+.*Phase[\s-]*5B\b", text, re.IGNORECASE | re.MULTILINE)
    if not match:
        return text
    return text[match.start():]


def validate_stale_literals(
    root: Path, claims_path: Path, decisions_path: Path, repro_path: Path
) -> str:
    paths = [root / relative for relative in SURFACE_PATHS]
    paths.extend((claims_path, decisions_path, repro_path))
    findings: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
        text = searchable_text(path.read_text(encoding="utf-8"))
        folded = text.casefold()
        for literal in STALE_LITERALS:
            if literal.casefold() in folded:
                findings.append(f"{path.relative_to(root)}:{literal}")
        if path.name == "CGplan.md":
            section = searchable_text(phase5b_section(path.read_text(encoding="utf-8")))
            if "status: planned / 0%" in section.casefold():
                findings.append("CGplan.md:Status: PLANNED / 0% within Phase 5B")
    if findings:
        raise ReleaseContentError(f"stale release literals remain ({len(findings)}): {findings}")
    return f"no stale literal appears in {len(paths)} release inputs"


def validate_canonical_command(text: str, relative: str) -> str:
    normalized = searchable_text(text)
    if CANONICAL_COMMAND not in normalized:
        raise ReleaseContentError(
            f"{relative} lacks exact canonical command: {CANONICAL_COMMAND}"
        )
    conflicting = re.findall(
        r"snakemake\s+(?:--snakefile|-s)(?:=|\s+)workflow/Snakefile\s+all\s+--cores(?:=|\s+)",
        normalized,
        flags=re.IGNORECASE,
    )
    if conflicting:
        raise ReleaseContentError(
            f"{relative} still presents the all target as the release reproduction command"
        )
    return (
        "exact phase5b/4-core/7000-MB command present; "
        "no conflicting all-target release command"
    )


def validate_phase5b_status(text: str, relative: str) -> str:
    normalized = searchable_text(text)
    patterns = (
        r"\bPhase[\s-]*5B\s*(?:status\s*)?(?:[:\-\u2013\u2014]|\bis\b)?\s*"
        r"(?:\*{0,2})?(?:COMPLETE|100\s*%|PASS)\b(?!\s+when\b)",
        r"\b(?:COMPLETE|completed)\s+through\s+Phase[\s-]*5B\b",
        r"\bPhases?\s+0\s*[\-\u2013\u2014]\s*5B\s+(?:are\s+)?complete\b",
    )
    if not any(re.search(pattern, normalized, re.IGNORECASE) for pattern in patterns):
        raise ReleaseContentError(
            f"{relative} lacks an unconditional Phase 5B COMPLETE/100%/PASS marker"
        )
    return "unconditional Phase 5B completion marker present"


def validate_core_sections(text: str, relative: str) -> str:
    normalized = searchable_text(text)
    missing: list[str] = []
    for section in CORE_SECTIONS:
        occurrences = [match.start() for match in re.finditer(re.escape(section), normalized)]
        found = False
        for start in occurrences:
            window = normalized[start:start + 220]
            if re.search(r"\b(?:COMPLETE|PASS)\b|\b100\s*%", window):
                if not re.search(r"\b(?:PLANNED|PENDING|INCOMPLETE)\b|\b0\s*%", window):
                    found = True
                    break
        if not found:
            missing.append(section)
    if missing:
        raise ReleaseContentError(
            f"{relative} lacks explicit complete markers for core sections {missing}"
        )
    return f"core sections {', '.join(CORE_SECTIONS)} are explicitly complete"


def validate_deferral_marker(text: str, relative: str) -> str:
    normalized = searchable_text(text)
    if CANONICAL_DEFERRAL in normalized:
        return f"exact {CANONICAL_DEFERRAL} marker present"
    patterns = (
        r"(?:13\.5|annotation\s+triangulation).{0,220}\bdefer\w*.{0,220}"
        r"(?:duplicate\w*|same[-\s]data|source\s+study)",
        r"\bdefer\w*.{0,220}(?:duplicate\w*|same[-\s]data|source\s+study).{0,220}"
        r"(?:13\.5|annotation\s+triangulation)",
    )
    if not any(re.search(pattern, normalized, re.IGNORECASE) for pattern in patterns):
        raise ReleaseContentError(
            f"{relative} lacks an explicit Section 13.5 duplicate-source deferral marker"
        )
    return "Section 13.5 is explicitly deferred because it duplicates the source study"


def parse_timestamp(value: str, label: str) -> datetime:
    candidate = value.strip().replace("Z", "+00:00")
    try:
        result = datetime.fromisoformat(candidate)
    except ValueError as error:
        raise ReleaseContentError(f"{label} is not ISO-8601: {value!r}") from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise ReleaseContentError(f"{label} must include a UTC offset: {value!r}")
    return result


def parse_contract_declaration(line: str) -> tuple[str, str] | None:
    plain = unescape(line).strip().lstrip("-* ").strip()
    if ":" not in plain:
        return None
    raw_label, raw_value = plain.split(":", 1)
    label = re.sub(r"[*_`]", "", raw_label).strip()
    value = raw_value.strip().strip("*_`").strip()
    if not label or not value:
        return None
    return label, value


def unique_pass_attestation(text: str, exact_label: str) -> int:
    matches: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        parsed = parse_contract_declaration(line)
        if parsed and parsed[0].casefold() == exact_label.casefold():
            matches.append((line_number, parsed[1].upper()))
    values = [status for _line_number, status in matches]
    if values != ["PASS"]:
        raise ReleaseContentError(
            f"{exact_label} attestation must be unique PASS; found {values}"
        )
    return matches[0][0]


def unique_record_status(text: str) -> str:
    values: list[str] = []
    for line in text.splitlines():
        parsed = parse_contract_declaration(line)
        if parsed and parsed[0].casefold() == "status":
            values.append(parsed[1].upper())
    if len(values) != 1:
        raise ReleaseContentError(
            f"reproducibility Status must occur exactly once; found {values}"
        )
    if values[0] not in {"SCIENCE_PASS", "PASS"}:
        raise ReleaseContentError(
            "reproducibility Status must equal SCIENCE_PASS or PASS; "
            f"found {values[0]!r}"
        )
    return values[0]


def require_nearby_noop_result(normalized: str, command: str, label: str) -> None:
    command_match = re.search(
        re.escape(command) + r"\s+(?:--dry-run|-n)\b", normalized, re.IGNORECASE
    )
    if not command_match:
        raise ReleaseContentError(f"reproducibility record lacks {label} dry-run command")
    nearby = normalized[command_match.end() : command_match.end() + 900]
    result_prefix = f"{label.capitalize()} dry-run result"
    if not re.search(
        re.escape(result_prefix)
        + r"\s*:\s*(?:Nothing to be done|all requested files are present and up to date|\b0\s+jobs?\b)",
        nearby,
        re.IGNORECASE,
    ):
        raise ReleaseContentError(
            f"reproducibility record lacks a concrete {result_prefix} near its command"
        )


def validate_run_table(table: MarkdownTable) -> str:
    if len(table.rows) != 2:
        raise ReleaseContentError(
            f"verification-runs table must contain exactly 2 rows; found {len(table.rows)}"
        )
    run_ids = [row["run_id"].strip() for row in table.rows]
    if any(not run_id for run_id in run_ids) or len(set(run_ids)) != 2:
        raise ReleaseContentError(f"run IDs must be two nonempty unique values: {run_ids}")
    for row in table.rows:
        run_id = row["run_id"]
        started = parse_timestamp(row["started_at"], f"{run_id}.started_at")
        ended = parse_timestamp(row["ended_at"], f"{run_id}.ended_at")
        if ended <= started:
            raise ReleaseContentError(f"{run_id} ended_at must be after started_at")
        elapsed = float(exact_decimal(row["elapsed_seconds"], f"{run_id}.elapsed_seconds"))
        if not math.isfinite(elapsed) or elapsed <= 0:
            raise ReleaseContentError(f"{run_id}.elapsed_seconds must be finite and > 0")
        wall_elapsed = (ended - started).total_seconds()
        tolerance = max(2.0, wall_elapsed * 0.01)
        if not math.isclose(elapsed, wall_elapsed, rel_tol=0, abs_tol=tolerance):
            raise ReleaseContentError(
                f"{run_id} elapsed_seconds {elapsed} != timestamp delta "
                f"{wall_elapsed} within {tolerance}s"
            )
        exact_int(row["jobs"], f"{run_id}.jobs", minimum=1)
        if exact_int(row["return_code"], f"{run_id}.return_code") != 0:
            raise ReleaseContentError(f"{run_id}.return_code must equal 0")
        peak = float(exact_decimal(row["peak_rss_mb"], f"{run_id}.peak_rss_mb"))
        if not math.isfinite(peak) or peak <= 0:
            raise ReleaseContentError(f"{run_id}.peak_rss_mb must be finite and > 0")
    return f"two unique successful runs ({', '.join(run_ids)}) have complete timing/job/RSS fields"


def validate_validator_table(table: MarkdownTable, root: Path) -> str:
    names: list[str] = []
    rows_by_name: dict[str, dict[str, str]] = {}
    expected = set(EXPECTED_VALIDATOR_PATHS)
    for row in table.rows:
        raw_name = row["validator"].strip().strip("`")
        if not raw_name:
            raise ReleaseContentError("validator table contains an empty validator path")
        name, fragment = safe_relative_target(raw_name, f"validator {raw_name!r}")
        if fragment:
            raise ReleaseContentError(f"validator path must not contain a fragment: {raw_name!r}")
        names.append(name)
        if name in rows_by_name:
            raise ReleaseContentError(f"validator table has duplicate path: {name}")
        rows_by_name[name] = row
    if set(names) != expected or len(names) != len(EXPECTED_VALIDATOR_PATHS):
        raise ReleaseContentError(
            "validator table must contain exactly the seven Phase-5B validator paths; "
            f"missing={sorted(expected - set(names))}; extra={sorted(set(names) - expected)}"
        )

    pass_total = 0
    warn_total = 0
    for name in EXPECTED_VALIDATOR_PATHS:
        row = rows_by_name[name]
        validator_path = require_within_root(root, root / name)
        headers, validator_rows = read_tsv(validator_path, f"validator {name}")
        if "status" not in headers:
            raise ReleaseContentError(f"validator {name} lacks a status column")
        statuses = [item["status"].strip().upper() for item in validator_rows]
        unknown = sorted(set(statuses) - {"PASS", "WARN", "FAIL"})
        if unknown:
            raise ReleaseContentError(f"validator {name} has unknown statuses: {unknown}")
        actual = {status: statuses.count(status) for status in ("PASS", "WARN", "FAIL")}
        passed = exact_int(row["pass"], f"{name}.pass")
        warned = exact_int(row["warn"], f"{name}.warn")
        failed = exact_int(row["fail"], f"{name}.fail")
        recorded = {"PASS": passed, "WARN": warned, "FAIL": failed}
        if recorded != actual:
            raise ReleaseContentError(
                f"validator {name} recorded counts {recorded} != workspace counts {actual}"
            )
        if failed != 0:
            raise ReleaseContentError(f"validator {name} reports {failed} FAIL")
        if passed + warned == 0:
            raise ReleaseContentError(f"validator {name} reports no PASS or WARN checks")
        pass_total += passed
        warn_total += warned
    return (
        f"all {len(names)} exact validator TSV paths reconcile independently to "
        f"{pass_total} PASS, {warn_total} WARN, 0 FAIL"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_aggregate_sha256(records: list[tuple[str, str]]) -> str:
    """Hash canonical sha256sum-style records; the TSV header is excluded."""
    payload = "".join(
        f"{file_sha256}  {relative}\n"
        for relative, file_sha256 in sorted(records)
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_persisted_manifest(root: Path, manifest_class: str) -> PersistedManifest:
    """Verify one exact manifest's serialization, path contract, and current bytes."""
    try:
        artifact, expected_paths = EXPECTED_MANIFESTS[manifest_class]
    except KeyError as error:
        raise ReleaseContentError(f"unknown manifest class: {manifest_class!r}") from error

    manifest_path = require_within_root(root, root / artifact)
    if not manifest_path.is_file():
        raise ReleaseContentError(f"missing persisted manifest: {artifact}")
    raw = manifest_path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ReleaseContentError(f"persisted manifest is not UTF-8: {artifact}") from error
    if "\r" in text or not text.endswith("\n"):
        raise ReleaseContentError(
            f"persisted manifest must use canonical LF lines with a final newline: {artifact}"
        )
    lines = text.splitlines()
    if not lines or lines[0] != "path\tfile_sha256":
        raise ReleaseContentError(
            f"persisted manifest must start with exact header path<TAB>file_sha256: {artifact}"
        )

    records: list[tuple[str, str]] = []
    for row_number, line in enumerate(lines[1:], start=2):
        fields = line.split("\t")
        if len(fields) != 2:
            raise ReleaseContentError(
                f"{artifact}:{row_number} must contain exactly two tab-separated fields"
            )
        relative, recorded_digest = fields
        records.append((relative, recorded_digest))

    observed_paths = tuple(relative for relative, _ in records)
    if observed_paths != expected_paths:
        missing = sorted(set(expected_paths) - set(observed_paths))
        extra = sorted(set(observed_paths) - set(expected_paths))
        raise ReleaseContentError(
            f"{manifest_class} persisted paths/order differ from the exact contract; "
            f"expected={len(expected_paths)} observed={len(observed_paths)}; "
            f"missing={missing}; extra={extra}"
        )

    for row_number, (relative, recorded_digest) in enumerate(records, start=2):
        safe_relative, fragment = safe_relative_target(
            relative, f"{artifact}:{row_number}.path"
        )
        if fragment or safe_relative != relative:
            raise ReleaseContentError(
                f"{artifact}:{row_number} path is not exact canonical text: {relative!r}"
            )
        if not SHA256_RE.fullmatch(recorded_digest):
            raise ReleaseContentError(
                f"{artifact}:{row_number} file_sha256 is not lowercase SHA-256"
            )
        # The exact lexical path set is the trust boundary.  Some approved
        # external leaves traverse repository-relative symlinks, so resolving
        # containment here would incorrectly reject those intended sources.
        current_path = root / relative
        if not current_path.is_file():
            raise ReleaseContentError(
                f"{manifest_class} listed current file is missing: {relative}"
            )
        current_digest = sha256_file(current_path)
        if recorded_digest != current_digest:
            raise ReleaseContentError(
                f"{manifest_class} recorded digest for {relative} "
                f"{recorded_digest} != current bytes {current_digest}"
            )

    return PersistedManifest(
        manifest_class=manifest_class,
        artifact=artifact,
        entries=len(records),
        aggregate_sha256=manifest_aggregate_sha256(records),
    )


def json_pointer_value(payload: object, pointer: str, label: str) -> object:
    """Resolve an RFC 6901 JSON Pointer without accepting ambiguous array indices."""
    if pointer == "":
        return payload
    if not pointer.startswith("/"):
        raise ReleaseContentError(
            f"{label} JSON pointer must be empty or start with '/': {pointer!r}"
        )
    current = payload
    for raw_token in pointer[1:].split("/"):
        if re.search(r"~(?:[^01]|$)", raw_token):
            raise ReleaseContentError(
                f"{label} JSON pointer has an invalid '~' escape: {pointer!r}"
            )
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if token not in current:
                raise ReleaseContentError(
                    f"{label} JSON pointer token {token!r} is absent: {pointer!r}"
                )
            current = current[token]
        elif isinstance(current, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", token):
                raise ReleaseContentError(
                    f"{label} JSON pointer array token is not canonical: {token!r}"
                )
            index = int(token)
            if index >= len(current):
                raise ReleaseContentError(
                    f"{label} JSON pointer array index {index} is out of range"
                )
            current = current[index]
        else:
            raise ReleaseContentError(
                f"{label} JSON pointer descends through {type(current).__name__} at {token!r}"
            )
    return current


def workspace_science_hash(path: Path, method: str, component: str, relative: str) -> str:
    if method == "file_sha256":
        ne_runtime_markers = (
            "peafowl_ne",
            "ne_design",
            "ne_scenario",
            "ne_empirical",
            "results_ne_design",
        )
        identity = re.sub(
            r"[^a-z0-9]+", "_", f"{component} {relative}".casefold()
        ).strip("_")
        if any(marker in identity for marker in ne_runtime_markers):
            raise ReleaseContentError(
                f"{component} is runtime-bearing Ne evidence and must use a runtime-excluded "
                "json_pointer science hash, not file_sha256"
            )
        return sha256_file(path)
    prefix = "json_pointer:"
    if not method.startswith(prefix):
        raise ReleaseContentError(
            f"{component}.hash_method must be file_sha256 or json_pointer:<RFC6901 pointer>; "
            f"found {method!r}"
        )
    pointer = method[len(prefix):]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReleaseContentError(
            f"{component} json_pointer artifact is not valid UTF-8 JSON: {relative}"
        ) from error
    value = json_pointer_value(payload, pointer, component)
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value.casefold()):
        raise ReleaseContentError(
            f"{component} JSON pointer {pointer!r} does not resolve to one SHA-256 string"
        )
    return value.casefold()


def validate_hash_table(table: MarkdownTable, root: Path) -> str:
    if len(table.rows) != len(EXPECTED_SCIENCE_HASHES):
        raise ReleaseContentError(
            "science-hash table must contain exactly "
            f"{len(EXPECTED_SCIENCE_HASHES)} components; found {len(table.rows)}"
        )
    rows_by_component: dict[str, dict[str, str]] = {}
    for row in table.rows:
        component = row["component"].strip().strip("`")
        if not component:
            raise ReleaseContentError("science-hash table contains an empty component")
        if component in rows_by_component:
            raise ReleaseContentError(f"science-hash table has duplicate component: {component}")
        rows_by_component[component] = row
    expected = set(EXPECTED_SCIENCE_HASHES)
    observed = set(rows_by_component)
    if observed != expected:
        raise ReleaseContentError(
            "science-hash components differ from the frozen six-component contract; "
            f"missing={sorted(expected - observed)}; extra={sorted(observed - expected)}"
        )

    methods: list[str] = []
    for component, expected_mapping in EXPECTED_SCIENCE_HASHES.items():
        row = rows_by_component[component]
        artifact = row["artifact"].strip().strip("`")
        method = row["hash_method"].strip().strip("`")
        if not artifact or not method:
            raise ReleaseContentError(
                f"science-hash component {component} has an empty artifact or hash_method"
            )
        expected_artifact, expected_method = expected_mapping
        if (artifact, method) != expected_mapping:
            raise ReleaseContentError(
                f"science-hash mapping for {component} is {(artifact, method)!r}; "
                f"expected {(expected_artifact, expected_method)!r}"
            )
        relative, fragment = safe_relative_target(artifact, f"science hash artifact {artifact!r}")
        if fragment:
            raise ReleaseContentError(
                f"science hash artifact must not contain a fragment: {artifact!r}"
            )
        artifact_path = require_within_root(root, root / relative)
        if not artifact_path.is_file():
            raise ReleaseContentError(f"science hash artifact does not exist: {artifact}")
        methods.append(method.split(":", 1)[0])
        hashes = []
        for column in (
            "workspace_science_sha256",
            "run_1_science_sha256",
            "run_2_science_sha256",
        ):
            digest = row[column].strip().strip("`").casefold()
            if not SHA256_RE.fullmatch(digest):
                raise ReleaseContentError(f"{component}.{column} is not a SHA-256 digest")
            hashes.append(digest)
        if len(set(hashes)) != 1:
            raise ReleaseContentError(f"{component} science hashes do not all match: {hashes}")
        workspace_digest = workspace_science_hash(
            artifact_path, method, component, relative
        )
        if hashes[0] != workspace_digest:
            raise ReleaseContentError(
                f"{component} recorded science hash {hashes[0]} != workspace {workspace_digest}"
            )
    method_counts = {method: methods.count(method) for method in sorted(set(methods))}
    return (
        f"all {len(rows_by_component)} frozen workspace/run-1/run-2 science hashes match exactly; "
        f"methods={method_counts}"
    )


def validate_manifest_table(table: MarkdownTable, root: Path) -> str:
    if table.headers != MANIFEST_COLUMN_ORDER:
        raise ReleaseContentError(
            "manifest table must use the exact ordered schema "
            f"{MANIFEST_COLUMN_ORDER}; found {table.headers}"
        )
    if len(table.rows) != len(EXPECTED_MANIFEST_CLASSES):
        raise ReleaseContentError(
            "manifest table must contain exactly two rows; "
            f"found {len(table.rows)}"
        )
    rows_by_class: dict[str, dict[str, str]] = {}
    for row in table.rows:
        manifest_class = row["manifest_class"].strip().strip("`")
        if not manifest_class:
            raise ReleaseContentError("manifest table contains an empty manifest_class")
        if manifest_class in rows_by_class:
            raise ReleaseContentError(
                f"manifest table has duplicate class: {manifest_class}"
            )
        rows_by_class[manifest_class] = row
    expected = set(EXPECTED_MANIFEST_CLASSES)
    observed = set(rows_by_class)
    if observed != expected:
        raise ReleaseContentError(
            "manifest classes differ from the exact two-class contract; "
            f"missing={sorted(expected - observed)}; extra={sorted(observed - expected)}"
        )

    details: list[str] = []
    for manifest_class in EXPECTED_MANIFEST_CLASSES:
        row = rows_by_class[manifest_class]
        persisted = validate_persisted_manifest(root, manifest_class)
        entries = exact_int(row["entries"], f"{manifest_class}.entries", minimum=1)
        if entries != persisted.entries:
            raise ReleaseContentError(
                f"{manifest_class}.entries {entries} != persisted {persisted.entries}"
            )
        hashes: list[str] = []
        for column in ("workspace_sha256", "run_1_sha256", "run_2_sha256"):
            digest = row[column].strip().strip("`").casefold()
            if not SHA256_RE.fullmatch(digest):
                raise ReleaseContentError(
                    f"{manifest_class}.{column} is not a SHA-256 digest"
                )
            hashes.append(digest)
        if len(set(hashes)) != 1:
            raise ReleaseContentError(
                f"{manifest_class} workspace/run manifest hashes do not match: {hashes}"
            )
        if hashes[0] != persisted.aggregate_sha256:
            raise ReleaseContentError(
                f"{manifest_class} recorded aggregate {hashes[0]} != persisted/current "
                f"{persisted.aggregate_sha256}"
            )
        if row["status"].strip().strip("`").upper() != "PASS":
            raise ReleaseContentError(f"{manifest_class}.status must equal PASS")
        details.append(
            f"{manifest_class}:{entries}:{persisted.aggregate_sha256}"
        )
    return (
        "exact two-class manifest hashes match across workspace/run-1/run-2 ("
        + ", ".join(details)
        + ")"
    )


def validate_reproducibility_record(path: Path, root: Path) -> AuditOutcome:
    if not path.is_file():
        raise ReleaseContentError(f"missing reproducibility record: {path}")
    text = path.read_text(encoding="utf-8")
    record_status = unique_record_status(text)

    normalized = searchable_text(text)
    if CANONICAL_COMMAND not in normalized:
        raise ReleaseContentError(
            f"reproducibility record lacks exact command: {CANONICAL_COMMAND}"
        )

    tables = parse_markdown_tables(text)
    run_table = unique_table_with_columns(tables, RUN_COLUMNS, "verification-runs")
    validator_table = unique_table_with_columns(tables, VALIDATOR_COLUMNS, "validator-totals")
    hash_table = unique_table_with_columns(tables, HASH_COLUMNS, "science-hash")
    manifest_table = unique_table_with_columns(tables, MANIFEST_COLUMNS, "manifest-hash")
    run_detail = validate_run_table(run_table)
    validator_detail = validate_validator_table(validator_table, root)
    hash_detail = validate_hash_table(hash_table, root)
    manifest_detail = validate_manifest_table(manifest_table, root)
    if SCIENCE_COMMAND not in normalized:
        raise ReleaseContentError(
            f"reproducibility record lacks exact science command: {SCIENCE_COMMAND}"
        )
    unique_pass_attestation(text, "Science no-op dry-run")
    require_nearby_noop_result(normalized, SCIENCE_COMMAND, "science")

    common_detail = (
        f"{run_detail}; {validator_detail}; {hash_detail}; {manifest_detail}; "
        "science no-op dry-run recorded"
    )
    if record_status == "SCIENCE_PASS":
        return AuditOutcome(
            "WARN",
            "SCIENCE_PASS bootstrap only; clean science evidence is valid, but the canonical "
            f"full-release no-op is not yet attested; {common_detail}",
        )

    unique_pass_attestation(text, "No-op dry-run")
    require_nearby_noop_result(normalized, CANONICAL_COMMAND, "canonical")
    return AuditOutcome("PASS", f"PASS; {common_detail}; canonical no-op dry-run recorded")


def validate_workspace(
    root: Path,
    claims_path: Path,
    decisions_path: Path,
    reproducibility_path: Path,
) -> list[Check]:
    root = root.resolve()
    audit = Audit()
    audit.run("release surface inventory is complete", lambda: validate_surface_inventory(root))
    audit.run(
        "stale claim literals are absent",
        lambda: validate_stale_literals(root, claims_path, decisions_path, reproducibility_path),
    )
    audit.run(
        "claim trace is the exact six-row release contract",
        lambda: validate_claim_trace(root, claims_path),
    )
    audit.run(
        "optional-study decisions match release claims",
        lambda: validate_decisions(decisions_path),
    )

    for relative in COMMAND_SURFACES:
        audit.run(
            f"canonical Phase-5B command — {relative}",
            lambda relative=relative: validate_canonical_command(
                read_text(root, relative), relative
            ),
        )
    for relative in STATUS_SURFACES:
        audit.run(
            f"Phase-5B completion marker — {relative}",
            lambda relative=relative: validate_phase5b_status(read_text(root, relative), relative),
        )
    for relative in ("PROJECT_STATUS.md", "CGplan.md"):
        audit.run(
            f"core Phase-5B sections complete — {relative}",
            lambda relative=relative: validate_core_sections(read_text(root, relative), relative),
        )
    for relative in DEFERRAL_SURFACES:
        audit.run(
            f"Section-13.5 duplicate-source deferral — {relative}",
            lambda relative=relative: validate_deferral_marker(
                read_text(root, relative), relative
            ),
        )
    audit.run(
        "final Phase-5B reproducibility schema and status",
        lambda: validate_reproducibility_record(reproducibility_path, root),
    )
    return audit.checks


def write_outputs(checks: list[Check], out_tsv: Path | None, out_md: Path | None) -> None:
    if out_tsv is not None:
        out_tsv.parent.mkdir(parents=True, exist_ok=True)
        with out_tsv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(["check", "status", "detail"])
            writer.writerows((row.name, row.status, row.detail) for row in checks)
    if out_md is not None:
        out_md.parent.mkdir(parents=True, exist_ok=True)
        passed = sum(row.status == "PASS" for row in checks)
        warned = sum(row.status == "WARN" for row in checks)
        failed = sum(row.status == "FAIL" for row in checks)
        lines = [
            "# Phase 5B release-content validation",
            "",
            f"**Summary: {passed} PASS, {warned} WARN, {failed} FAIL**",
            "",
            "| check | status | evidence |",
            "|---|---|---|",
        ]
        for row in checks:
            detail = row.detail.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {row.name} | **{row.status}** | {detail} |")
        lines.append("")
        out_md.write_text("\n".join(lines), encoding="utf-8")


def fixture_claim_rows() -> list[dict[str, str]]:
    report_anchors = {
        "wolf_froh_load_association": "wolf-individual-association",
        "peafowl_damage_falsification": "damage-aware-falsification",
        "peafowl_ne_study_design": "ne-sample-design-calibration",
        "wolf_roh_localization_gate": "optional-study-decisions",
        "wolf_roh_localized_realized_burden": "wolf-roh-localization",
        "wolf_annotation_triangulation_gate": "optional-study-decisions",
    }
    explorer_anchors = {
        "wolf_froh_load_association": "wolf-robustness",
        "peafowl_damage_falsification": "damage-falsification",
        "peafowl_ne_study_design": "ne-design",
        "wolf_roh_localization_gate": "decision-boundaries",
        "wolf_roh_localized_realized_burden": "wolf-roh-localization",
        "wolf_annotation_triangulation_gate": "decision-boundaries",
    }
    rule_names = {
        "wolf_froh_load_association": "wolf_froh_load_robustness",
        "peafowl_damage_falsification": "peafowl_damage_falsification",
        "peafowl_ne_study_design": "peafowl_ne_design",
        "wolf_roh_localization_gate": "phase5b_optional_decisions",
        "wolf_roh_localized_realized_burden": "wolf_roh_localization_collate",
        "wolf_annotation_triangulation_gate": "phase5b_optional_decisions",
    }
    rows: list[dict[str, str]] = []
    for claim_id, section in EXPECTED_CLAIMS.items():
        status = "claim_complete"
        observed = "2"
        threshold = "1"
        operator = ">="
        if claim_id == "wolf_roh_localization_gate":
            status = "IMPLEMENT"
        elif claim_id == "wolf_annotation_triangulation_gate":
            status = CANONICAL_DEFERRAL
            observed = "0"
        rows.append(
            {
                "claim_id": claim_id,
                "section": section,
                "headline": f"Synthetic completed claim {claim_id}",
                "claim_status": status,
                "estimate": "synthetic estimate",
                "uncertainty": "synthetic uncertainty",
                "observed_value": observed,
                "result_table": "results/tables/synthetic_result.tsv",
                "provenance": "results/provenance/synthetic.json",
                "validator": "results/tables/synthetic_validator.tsv",
                "report_anchor": f"report/report.html#{report_anchors[claim_id]}",
                "explorer_anchor": f"index.html#{explorer_anchors[claim_id]}",
                "workflow_rule": f"workflow/rules/phase5b.smk#{rule_names[claim_id]}",
                "change_operator": operator,
                "change_threshold": threshold,
                "what_changes_mind": "synthetic numeric reopening condition",
                "scientific_boundary": "synthetic scientific boundary",
            }
        )
    return rows


def write_fixture_input_manifests(root: Path) -> None:
    """Create all exact manifest targets and canonical TSVs for isolated self-tests."""
    for manifest_class in EXPECTED_MANIFEST_CLASSES:
        artifact, expected_paths = EXPECTED_MANIFESTS[manifest_class]
        records: list[tuple[str, str]] = []
        for relative in expected_paths:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"synthetic manifest fixture: {relative}\n".encode("utf-8"))
            records.append((relative, sha256_file(path)))
        manifest_path = root / artifact
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            "path\tfile_sha256\n"
            + "".join(
                f"{relative}\t{file_sha256}\n"
                for relative, file_sha256 in records
            ),
            encoding="utf-8",
        )


def fixture_reproducibility(root: Path) -> str:
    validator_rows = (
        ("results/tables/validation_wolf_robustness.tsv", 2, 1, 0),
        ("results/tables/validation_peafowl_damage.tsv", 1, 0, 0),
        ("results/tables/validation_peafowl_ne_design.tsv", 2, 0, 0),
        ("results/tables/validation_phase5b_core_integration.tsv", 1, 0, 0),
        ("results/tables/validation_phase5b_decisions.tsv", 1, 0, 0),
        ("results/tables/validation_wolf_roh_localization.tsv", 1, 1, 0),
        ("results/tables/validation_phase5b.tsv", 2, 0, 0),
    )
    science_rows = (
        (
            "wolf_froh_load_association",
            "results/provenance/wolf_froh_load.json",
            "json_pointer:/scientific_hash",
        ),
        (
            "peafowl_damage_falsification",
            "results/tables/peafowl_damage_effects.tsv",
            "file_sha256",
        ),
        (
            "peafowl_ne_scenario",
            "results/provenance/peafowl_ne_design.json",
            "json_pointer:/scientific_hashes/scenario_runtime_excluded_sha256",
        ),
        (
            "peafowl_ne_empirical",
            "results/provenance/peafowl_ne_design.json",
            "json_pointer:/scientific_hashes/empirical_runtime_excluded_sha256",
        ),
        (
            "wolf_roh_localization",
            "results/provenance/wolf_roh_localization.json",
            "json_pointer:/scientific_hash",
        ),
        (
            "phase5b_synthesis",
            "results/tables/phase5b_claim_trace.tsv",
            "file_sha256",
        ),
    )
    validator_lines = "\n".join(
        f"| {path} | {passed} | {warned} | {failed} |"
        for path, passed, warned, failed in validator_rows
    )
    science_lines = []
    for component, artifact, method in science_rows:
        digest = workspace_science_hash(root / artifact, method, component, artifact)
        science_lines.append(
            f"| {component} | {artifact} | {method} | {digest} | {digest} | {digest} |"
        )
    persisted_manifests = {
        manifest_class: validate_persisted_manifest(root, manifest_class)
        for manifest_class in EXPECTED_MANIFEST_CLASSES
    }
    upstream = persisted_manifests["frozen_upstream_inputs"]
    external = persisted_manifests["external_source_leaves"]
    return f"""# Phase 5B synthetic clean verification

- **Status: PASS**
- **Science no-op dry-run: PASS**
- **No-op dry-run: PASS**

```bash
{SCIENCE_COMMAND}
{SCIENCE_COMMAND} --dry-run
```

Science dry-run result: Nothing to be done (all requested files are present and up to date).

```bash
{CANONICAL_COMMAND}
{CANONICAL_COMMAND} --dry-run
```

Canonical dry-run result: Nothing to be done (all requested files are present and up to date).

| run_id | started_at | ended_at | elapsed_seconds | jobs | return_code | peak_rss_mb |
|---|---|---|---:|---:|---:|---:|
| isolated-1 | 2026-07-19T08:00:00+07:00 | 2026-07-19T08:10:00+07:00 | 600 | 201 | 0 | 6123 |
| isolated-2 | 2026-07-19T09:00:00+07:00 | 2026-07-19T09:09:30+07:00 | 570 | 201 | 0 | 6088 |

| validator | pass | warn | fail |
|---|---:|---:|---:|
{validator_lines}

| component | artifact | hash_method | workspace_science_sha256 | run_1_science_sha256 | run_2_science_sha256 |
|---|---|---|---|---|---|
{chr(10).join(science_lines)}

| manifest_class | entries | workspace_sha256 | run_1_sha256 | run_2_sha256 | status |
|---|---:|---|---|---|---|
| frozen_upstream_inputs | {upstream.entries} | {upstream.aggregate_sha256} | {upstream.aggregate_sha256} | {upstream.aggregate_sha256} | PASS |
| external_source_leaves | {external.entries} | {external.aggregate_sha256} | {external.aggregate_sha256} | {external.aggregate_sha256} | PASS |
"""


def build_fixture(root: Path) -> tuple[Path, Path, Path]:
    common = "\n".join(
        [
            "# Synthetic release surface",
            "Phase 5B: COMPLETE",
            CANONICAL_COMMAND,
            (
                f"Section 13.5 annotation triangulation is {CANONICAL_DEFERRAL} "
                "because it duplicates the source study."
            ),
            *(f"{section} COMPLETE" for section in CORE_SECTIONS),
        ]
    )
    report_ids = (
        "wolf-individual-association",
        "damage-aware-falsification",
        "ne-sample-design-calibration",
        "optional-study-decisions",
        "wolf-roh-localization",
    )
    explorer_ids = (
        "wolf-robustness",
        "damage-falsification",
        "ne-design",
        "decision-boundaries",
        "wolf-roh-localization",
    )
    for relative in SURFACE_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = common
        if relative == "report/report.html":
            payload = "<html><body>" + common + "".join(
                f'<section id="{anchor}">{anchor}</section>' for anchor in report_ids
            ) + "</body></html>"
        elif relative == "index.html":
            payload = "<html><body>" + common + "".join(
                f'<section id="{anchor}">{anchor}</section>' for anchor in explorer_ids
            ) + "</body></html>"
        path.write_text(payload + "\n", encoding="utf-8")

    workflow = root / "workflow/rules/phase5b.smk"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "\n".join(
            f"rule {name}:\n    output: 'synthetic/{name}.done'"
            for name in (
                "wolf_froh_load_robustness",
                "peafowl_damage_falsification",
                "peafowl_ne_design",
                "phase5b_optional_decisions",
                "wolf_roh_localization_collate",
            )
        ) + "\n",
        encoding="utf-8",
    )
    fixture_ne_hashes = json.dumps(
        {
            "scientific_hashes": {
                "scenario_runtime_excluded_sha256": hashlib.sha256(
                    b"science-c-runtime-excluded"
                ).hexdigest(),
                "empirical_runtime_excluded_sha256": hashlib.sha256(
                    b"science-d-runtime-excluded"
                ).hexdigest(),
            },
        },
        sort_keys=True,
    ) + "\n"
    for relative, payload in (
        ("results/tables/synthetic_result.tsv", "value\n1\n"),
        ("results/provenance/synthetic.json", "{}\n"),
        ("results/tables/synthetic_validator.tsv", "check\tstatus\na\tPASS\n"),
        (
            "results/provenance/wolf_froh_load.json",
            json.dumps(
                {"scientific_hash": hashlib.sha256(b"wolf-association").hexdigest()}
            ) + "\n",
        ),
        ("results/tables/peafowl_damage_effects.tsv", "effect\n0.125\n"),
        ("results/provenance/peafowl_ne_design.json", fixture_ne_hashes),
        (
            "results/provenance/wolf_roh_localization.json",
            json.dumps(
                {"scientific_hash": hashlib.sha256(b"wolf-localization").hexdigest()}
            ) + "\n",
        ),
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")

    claims_path = root / "results/tables/phase5b_claim_trace.tsv"
    claims_path.parent.mkdir(parents=True, exist_ok=True)
    rows = fixture_claim_rows()
    with claims_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)

    validator_payloads = {
        "results/tables/validation_wolf_robustness.tsv": "a\tPASS\nb\tPASS\nc\tWARN\n",
        "results/tables/validation_peafowl_damage.tsv": "a\tPASS\n",
        "results/tables/validation_peafowl_ne_design.tsv": "a\tPASS\nb\tPASS\n",
        "results/tables/validation_phase5b_core_integration.tsv": "a\tPASS\n",
        "results/tables/validation_phase5b_decisions.tsv": "a\tPASS\n",
        "results/tables/validation_wolf_roh_localization.tsv": "a\tPASS\nb\tWARN\n",
        "results/tables/validation_phase5b.tsv": "a\tPASS\nb\tPASS\n",
    }
    for relative, body in validator_payloads.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("check\tstatus\n" + body, encoding="utf-8")

    decisions_path = root / "results/tables/phase5b_optional_decisions.tsv"
    decision_rows = [
        {
            "section": "13.4",
            "decision": "IMPLEMENT",
            "observed_value": "15",
            "required_operator": ">=",
            "required_value": "12",
            "evidence": "synthetic gate passed",
            "reopen_condition": "synthetic threshold",
            "scientific_boundary": "synthetic boundary",
        },
        {
            "section": "13.5",
            "decision": CANONICAL_DEFERRAL,
            "observed_value": "0",
            "required_operator": ">=",
            "required_value": "1",
            "evidence": "duplicates source study",
            "reopen_condition": "one independent definition",
            "scientific_boundary": "predicted impacts are proxies",
        },
    ]
    with decisions_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(decision_rows[0]), delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(decision_rows)

    write_fixture_input_manifests(root)
    repro_path = root / "results/PHASE5B_REPRODUCIBILITY.md"
    repro_path.write_text(fixture_reproducibility(root), encoding="utf-8")
    return claims_path, decisions_path, repro_path


def check_status(checks: list[Check], name: str) -> str:
    matches = [row.status for row in checks if row.name == name]
    if len(matches) != 1:
        raise AssertionError(f"expected one self-test check {name!r}; found {matches}")
    return matches[0]


def expect_release_error(operation: Callable[[], object]) -> None:
    try:
        operation()
    except ReleaseContentError:
        return
    raise AssertionError("expected ReleaseContentError")


def self_test() -> None:
    inequality_fixture = """
13.1 COMPLETE. Expected compute <5 minutes.
### 13.2 Peafowl N_e calibration
Distinguish N_e < 500 from N_e > 500. Section status: COMPLETE.
13.3 COMPLETE. 13.4 COMPLETE. 13.6 COMPLETE.
"""
    assert validate_core_sections(
        inequality_fixture, "synthetic-inequality-markdown.md"
    ).startswith("core sections")

    with tempfile.TemporaryDirectory(prefix="cg-phase5b-release-content-") as temporary:
        root = Path(temporary)
        claims, decisions, repro = build_fixture(root)
        checks = validate_workspace(root, claims, decisions, repro)
        failures = [row for row in checks if row.status != "PASS"]
        assert not failures, failures

        pointer_payload = {"a/b": {"~science": ["0" * 64]}}
        assert json_pointer_value(
            pointer_payload, "/a~1b/~0science/0", "escaped-pointer-test"
        ) == "0" * 64
        expect_release_error(
            lambda: json_pointer_value(pointer_payload, "/a~2b", "bad-pointer-test")
        )
        expect_release_error(
            lambda: workspace_science_hash(
                root / "results/tables/peafowl_damage_effects.tsv",
                "file_sha256",
                "peafowl_ne_scenario",
                "results/tables/peafowl_damage_effects.tsv",
            )
        )

        readme = root / "README.md"
        original_readme = readme.read_text(encoding="utf-8")
        for literal in STALE_LITERALS:
            readme.write_text(original_readme + f"\n{literal}\n", encoding="utf-8")
            expect_release_error(
                lambda: validate_stale_literals(root, claims, decisions, repro)
            )
        readme.write_text(original_readme, encoding="utf-8")

        plan = root / "CGplan.md"
        original_plan = plan.read_text(encoding="utf-8")
        plan.write_text(original_plan + "\n## Phase 5B\nStatus: PLANNED / 0%\n", encoding="utf-8")
        expect_release_error(lambda: validate_stale_literals(root, claims, decisions, repro))
        plan.write_text(original_plan, encoding="utf-8")

        index = root / "index.html"
        original_index = index.read_text(encoding="utf-8")
        index.write_text(
            original_index.replace(CANONICAL_COMMAND, CANONICAL_COMMAND.replace("phase5b", "all")),
            encoding="utf-8",
        )
        expect_release_error(
            lambda: validate_canonical_command(index.read_text(encoding="utf-8"), "index.html")
        )
        index.write_text(original_index, encoding="utf-8")

        original_claims = claims.read_text(encoding="utf-8")
        claims.write_text(
            original_claims + original_claims.splitlines()[-1] + "\n",
            encoding="utf-8",
        )
        checks = validate_workspace(root, claims, decisions, repro)
        assert check_status(checks, "claim trace is the exact six-row release contract") == "FAIL"
        claims.write_text(original_claims, encoding="utf-8")

        claims.write_text(
            original_claims.replace(CANONICAL_DEFERRAL, "IMPLEMENT", 1), encoding="utf-8"
        )
        expect_release_error(lambda: validate_claim_trace(root, claims))
        claims.write_text(original_claims, encoding="utf-8")

        original_repro = repro.read_text(encoding="utf-8")
        science_result_line = (
            "Science dry-run result: Nothing to be done "
            "(all requested files are present and up to date).\n"
        )
        canonical_result_line = (
            "Canonical dry-run result: Nothing to be done "
            "(all requested files are present and up to date).\n"
        )
        repro.write_text(
            original_repro.replace(science_result_line, "", 1), encoding="utf-8"
        )
        expect_release_error(lambda: validate_reproducibility_record(repro, root))
        repro.write_text(
            original_repro.replace(canonical_result_line, "", 1), encoding="utf-8"
        )
        expect_release_error(lambda: validate_reproducibility_record(repro, root))
        repro.write_text(
            original_repro + "\n- _Status: SCIENCE_PASS_\n", encoding="utf-8"
        )
        expect_release_error(lambda: validate_reproducibility_record(repro, root))
        repro.write_text(
            original_repro + "\n- _Science no-op dry-run: FAIL_\n",
            encoding="utf-8",
        )
        expect_release_error(lambda: validate_reproducibility_record(repro, root))
        repro.write_text(
            original_repro + "\n- _Status_: SCIENCE_PASS\n", encoding="utf-8"
        )
        expect_release_error(lambda: validate_reproducibility_record(repro, root))
        repro.write_text(
            original_repro + "\n- _Science no-op dry-run_: FAIL\n",
            encoding="utf-8",
        )
        expect_release_error(lambda: validate_reproducibility_record(repro, root))

        bootstrap_repro = (
            original_repro.replace("Status: PASS", "Status: SCIENCE_PASS", 1)
            .replace("- **No-op dry-run: PASS**\n", "", 1)
            .replace(f"{CANONICAL_COMMAND} --dry-run\n", "", 1)
            .replace(canonical_result_line, "", 1)
        )
        assert bootstrap_repro != original_repro
        repro.write_text(bootstrap_repro, encoding="utf-8")
        bootstrap_outcome = validate_reproducibility_record(repro, root)
        assert bootstrap_outcome.status == "WARN", bootstrap_outcome
        checks = validate_workspace(root, claims, decisions, repro)
        bootstrap_statuses = [row.status for row in checks]
        assert bootstrap_statuses.count("WARN") == 1, bootstrap_statuses
        assert "FAIL" not in bootstrap_statuses, bootstrap_statuses
        bootstrap_md = root / "results/BOOTSTRAP_RELEASE_VALIDATION.md"
        write_outputs(checks, None, bootstrap_md)
        bootstrap_text = bootstrap_md.read_text(encoding="utf-8")
        assert "1 WARN, 0 FAIL" in bootstrap_text

        repro.write_text(
            bootstrap_repro.replace("Status: SCIENCE_PASS", "Status: PASS", 1),
            encoding="utf-8",
        )
        expect_release_error(lambda: validate_reproducibility_record(repro, root))

        repro.write_text(
            bootstrap_repro.replace("- **Science no-op dry-run: PASS**\n", "", 1),
            encoding="utf-8",
        )
        expect_release_error(lambda: validate_reproducibility_record(repro, root))

        repro.write_text(
            bootstrap_repro.replace("Status: SCIENCE_PASS", "Status: UNKNOWN", 1),
            encoding="utf-8",
        )
        expect_release_error(lambda: validate_reproducibility_record(repro, root))

        repro.write_text(
            bootstrap_repro + "\n- **Status: SCIENCE_PASS**\n", encoding="utf-8"
        )
        expect_release_error(lambda: validate_reproducibility_record(repro, root))

        bootstrap_count_mismatch = bootstrap_repro.replace(
            "| results/tables/validation_wolf_robustness.tsv | 2 | 1 | 0 |",
            "| results/tables/validation_wolf_robustness.tsv | 3 | 0 | 0 |",
            1,
        )
        repro.write_text(bootstrap_count_mismatch, encoding="utf-8")
        expect_release_error(lambda: validate_reproducibility_record(repro, root))

        repro.write_text(original_repro, encoding="utf-8")
        repro.write_text(
            original_repro.replace("Status: PASS", "Status: PENDING", 1),
            encoding="utf-8",
        )
        checks = validate_workspace(root, claims, decisions, repro)
        assert check_status(checks, "final Phase-5B reproducibility schema and status") == "FAIL"
        repro.write_text(original_repro, encoding="utf-8")

        validator_count_mismatch = original_repro.replace(
            "| results/tables/validation_wolf_robustness.tsv | 2 | 1 | 0 |",
            "| results/tables/validation_wolf_robustness.tsv | 3 | 0 | 0 |",
            1,
        )
        repro.write_text(validator_count_mismatch, encoding="utf-8")
        expect_release_error(lambda: validate_reproducibility_record(repro, root))
        repro.write_text(original_repro, encoding="utf-8")

        validator_path_mismatch = original_repro.replace(
            "| results/tables/validation_peafowl_damage.tsv | 1 | 0 | 0 |",
            "| results/tables/synthetic_validator.tsv | 1 | 0 | 0 |",
            1,
        )
        repro.write_text(validator_path_mismatch, encoding="utf-8")
        expect_release_error(lambda: validate_reproducibility_record(repro, root))
        repro.write_text(original_repro, encoding="utf-8")

        renamed_component = original_repro.replace(
            "| peafowl_damage_falsification |", "| arbitrary_damage |", 1
        )
        repro.write_text(renamed_component, encoding="utf-8")
        expect_release_error(lambda: validate_reproducibility_record(repro, root))
        repro.write_text(original_repro, encoding="utf-8")

        damage_digest = sha256_file(root / "results/tables/peafowl_damage_effects.tsv")
        synthesis_digest = sha256_file(root / "results/tables/phase5b_claim_trace.tsv")
        original_damage_row = (
            "| peafowl_damage_falsification | results/tables/peafowl_damage_effects.tsv "
            f"| file_sha256 | {damage_digest} | {damage_digest} | {damage_digest} |"
        )
        remapped_damage_row = (
            "| peafowl_damage_falsification | results/tables/phase5b_claim_trace.tsv "
            f"| file_sha256 | {synthesis_digest} | {synthesis_digest} | {synthesis_digest} |"
        )
        remapped_artifact = original_repro.replace(
            original_damage_row, remapped_damage_row, 1
        )
        assert remapped_artifact != original_repro
        repro.write_text(remapped_artifact, encoding="utf-8")
        expect_release_error(lambda: validate_reproducibility_record(repro, root))
        repro.write_text(original_repro, encoding="utf-8")

        tampered_source = root / EXPECTED_FROZEN_UPSTREAM_PATHS[0]
        original_source_bytes = tampered_source.read_bytes()
        tampered_source.write_bytes(original_source_bytes + b"tampered\n")
        expect_release_error(lambda: validate_reproducibility_record(repro, root))
        tampered_source.write_bytes(original_source_bytes)

        frozen_artifact = EXPECTED_MANIFESTS["frozen_upstream_inputs"][0]
        frozen_manifest = root / frozen_artifact
        original_frozen_manifest = frozen_manifest.read_text(encoding="utf-8")
        frozen_lines = original_frozen_manifest.splitlines()
        first_fields = frozen_lines[1].split("\t")
        first_fields[1] = "0" * 64
        frozen_lines[1] = "\t".join(first_fields)
        frozen_manifest.write_text("\n".join(frozen_lines) + "\n", encoding="utf-8")
        expect_release_error(lambda: validate_reproducibility_record(repro, root))
        frozen_manifest.write_text(original_frozen_manifest, encoding="utf-8")

        frozen_lines = original_frozen_manifest.splitlines()
        frozen_lines[1], frozen_lines[2] = frozen_lines[2], frozen_lines[1]
        frozen_manifest.write_text("\n".join(frozen_lines) + "\n", encoding="utf-8")
        expect_release_error(lambda: validate_reproducibility_record(repro, root))
        frozen_manifest.write_text(original_frozen_manifest, encoding="utf-8")

        manifest_schema_mismatch = original_repro.replace(
            "| manifest_class | entries | workspace_sha256 |",
            "| entries | manifest_class | workspace_sha256 |",
            1,
        )
        repro.write_text(manifest_schema_mismatch, encoding="utf-8")
        expect_release_error(lambda: validate_reproducibility_record(repro, root))
        repro.write_text(original_repro, encoding="utf-8")

        upstream = validate_persisted_manifest(root, "frozen_upstream_inputs")
        external = validate_persisted_manifest(root, "external_source_leaves")
        zero_entry_manifest = original_repro.replace(
            f"| frozen_upstream_inputs | {upstream.entries} |",
            "| frozen_upstream_inputs | 0 |",
            1,
        )
        repro.write_text(zero_entry_manifest, encoding="utf-8")
        expect_release_error(lambda: validate_reproducibility_record(repro, root))
        repro.write_text(original_repro, encoding="utf-8")

        upstream_status_row = (
            f"| frozen_upstream_inputs | {upstream.entries} | "
            f"{upstream.aggregate_sha256} | {upstream.aggregate_sha256} "
            f"| {upstream.aggregate_sha256} | PASS |"
        )
        failed_manifest_status = original_repro.replace(
            upstream_status_row, upstream_status_row.replace("| PASS |", "| FAIL |"), 1
        )
        assert failed_manifest_status != original_repro
        repro.write_text(failed_manifest_status, encoding="utf-8")
        expect_release_error(lambda: validate_reproducibility_record(repro, root))
        repro.write_text(original_repro, encoding="utf-8")

        manifest_hash_mismatch = original_repro.replace(
            f"| external_source_leaves | {external.entries} | "
            f"{external.aggregate_sha256} | {external.aggregate_sha256} |",
            f"| external_source_leaves | {external.entries} | "
            f"{external.aggregate_sha256} | {'0' * 64} |",
            1,
        )
        assert manifest_hash_mismatch != original_repro
        repro.write_text(manifest_hash_mismatch, encoding="utf-8")
        expect_release_error(lambda: validate_reproducibility_record(repro, root))

    print("validate_phase5b_release_content self-test: OK")


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return

    root = Path(args.root).resolve()
    claims = resolve(root, args.claims)
    decisions = resolve(root, args.decisions)
    reproducibility = resolve(root, args.reproducibility)
    for path in (claims, decisions, reproducibility):
        require_within_root(root, path)

    checks = validate_workspace(root, claims, decisions, reproducibility)
    out_tsv = resolve(root, args.out_tsv) if args.out_tsv else None
    out_md = resolve(root, args.out_md) if args.out_md else None
    if out_tsv is not None:
        require_within_root(root, out_tsv)
    if out_md is not None:
        require_within_root(root, out_md)
    write_outputs(checks, out_tsv, out_md)

    passed = sum(row.status == "PASS" for row in checks)
    warned = sum(row.status == "WARN" for row in checks)
    failed = sum(row.status == "FAIL" for row in checks)
    for row in checks:
        if row.status == "FAIL":
            print(f"FAIL — {row.name}: {row.detail}")
    print(
        f"Phase-5B release-content validation: "
        f"{passed} PASS, {warned} WARN, {failed} FAIL"
    )
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
