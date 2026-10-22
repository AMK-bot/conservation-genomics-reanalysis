#!/usr/bin/env python3
"""Final Phase-5A readiness gate.

This validator checks the completed Phase-1--4 and Phase-5A.1 gates, the
communication artifact set, the evidence map, environment portability, the
Streamlit runtime smoke result, and the recorded clean-clone/local-data run. It
does not perform rendering, launch the app, or run the scientific workflow.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET


VALIDATION_TABLES = [
    ("Phase 1", "results/tables/validation_report.tsv"),
    ("Phase 2", "results/tables/validation_phase2.tsv"),
    ("Phase 3", "results/tables/validation_phase3.tsv"),
    ("Phase 4", "results/tables/validation_phase4.tsv"),
    ("Phase 5A.1", "results/tables/validation_fragility_scorecard.tsv"),
]

TEXT_ARTIFACTS = [
    ("research journey", "RESEARCH_JOURNEY.md"),
    ("questions and answers", "FAQ.md"),
    ("narrated walkthrough", "brief/walkthrough.md"),
    ("research brief Markdown", "brief/research_brief.md"),
]

SCREENSHOTS = [
    "brief/screenshots/01-ne-gbf-verdict.jpg",
    "brief/screenshots/02-structure-diversity.jpg",
    "brief/screenshots/03-wolf-load-roh.jpg",
    "brief/screenshots/04-about-limitations.jpg",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--out-tsv", default="results/tables/validation_phase5a.tsv")
    parser.add_argument("--out-md", default="results/PHASE5A_VALIDATION.md")
    return parser.parse_args()


def _plain_markdown(text: str) -> str:
    text = re.sub(r"[*_`{}#]", "", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _read_text(path: Path) -> tuple[str | None, str | None]:
    if not path.is_file():
        return None, "missing"
    try:
        return path.read_text(encoding="utf-8"), None
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"unreadable UTF-8: {exc}"


def _evidence_map(path: Path) -> tuple[bool, str]:
    text, error = _read_text(path)
    if error:
        return False, error
    assert text is not None
    plain = _plain_markdown(text)
    concepts = {
        "heading": "what evidence would change the conclusion" in plain,
        "more individuals per population": (
            "more" in plain and "individual" in plain and "per population" in plain
        ),
        "species-specific recombination map": "recombination map" in plain,
        "fitness/reproductive evidence": "fitness" in plain and "reproductive" in plain,
        "finer sub-country occurrence": (
            "sub-country" in plain and ("occurrence" in plain or "occupancy" in plain)
        ),
        "individuals before marker density": (
            any(term in plain for term in ("snps", "loci", "marker count"))
            and any(term in plain for term in ("individuals", "independent genomes"))
            and any(term in plain for term in ("cannot replace", "alone", "before additional snp"))
        ),
    }
    missing = [name for name, present in concepts.items() if not present]
    return not missing, "all 6 concepts present" if not missing else f"missing: {', '.join(missing)}"


def _html_signature(path: Path) -> tuple[bool, str]:
    text, error = _read_text(path)
    if error:
        return False, error
    assert text is not None
    lower = text.lower()
    size = path.stat().st_size
    ok = size > 1_000 and "<!doctype html" in lower[:512] and "<html" in lower and "</html>" in lower
    return ok, f"HTML signature; {size:,} bytes" if ok else f"invalid/incomplete HTML; {size:,} bytes"


def _svg_signature(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "missing"
    data = path.read_bytes()
    try:
        root = ET.fromstring(data)
        is_svg = root.tag.rsplit("}", 1)[-1].lower() == "svg"
    except ET.ParseError:
        is_svg = False
    ok = len(data) > 1_000 and is_svg
    return ok, f"SVG signature; {len(data):,} bytes" if ok else f"invalid/incomplete SVG; {len(data):,} bytes"


def _jpeg_signature(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "missing"
    data = path.read_bytes()
    ok = len(data) > 10_000 and data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9")
    return ok, f"JPEG signature; {len(data):,} bytes" if ok else f"invalid/incomplete JPEG; {len(data):,} bytes"


def _validation_status(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "missing"
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        return False, f"unreadable TSV: {exc}"
    if "status" not in (reader.fieldnames or []):
        return False, "missing status column"
    if not rows:
        return False, "no validation rows"
    statuses = [str(row.get("status", "")).strip().upper() for row in rows]
    n_fail = statuses.count("FAIL")
    n_pass = statuses.count("PASS")
    n_warn = statuses.count("WARN")
    known = all(status in {"PASS", "WARN", "FAIL"} for status in statuses)
    ok = known and n_fail == 0
    return ok, f"{n_pass} PASS, {n_warn} WARN, {n_fail} FAIL"


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    out_tsv = Path(args.out_tsv)
    out_md = Path(args.out_md)
    if not out_tsv.is_absolute():
        out_tsv = root / out_tsv
    if not out_md.is_absolute():
        out_md = root / out_md

    checks: list[tuple[str, str, str]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append((name, "PASS" if ok else "FAIL", detail))

    # Existing scientific and scorecard gates.
    for label, relative in VALIDATION_TABLES:
        ok, detail = _validation_status(root / relative)
        add(f"{label} validation has zero FAIL", ok, detail)

    # The complete five-part evidence map must exist in both public explanations.
    for label, relative in (
        ("explorer", "app/streamlit_app.py"),
        ("technical report", "report/report.qmd"),
    ):
        ok, detail = _evidence_map(root / relative)
        add(f"evidence map is complete in {label}", ok, detail)

    # Written communication artifacts.
    for label, relative in TEXT_ARTIFACTS:
        path = root / relative
        text, error = _read_text(path)
        size = path.stat().st_size if path.is_file() else 0
        ok = error is None and text is not None and bool(text.strip()) and size > 100
        add(f"{label} exists and is non-empty", ok, f"{size:,} bytes" if ok else (error or "empty"))

    ok, detail = _svg_signature(root / "brief/graphical_abstract.svg")
    add("graphical abstract is a valid SVG", ok, detail)

    for relative in SCREENSHOTS:
        ok, detail = _jpeg_signature(root / relative)
        add(f"screenshot {Path(relative).name} is a valid JPEG", ok, detail)

    ok, detail = _html_signature(root / "brief/research_brief.html")
    add("research brief HTML is complete", ok, detail)
    ok, detail = _html_signature(root / "report/report.html")
    add("technical report HTML is complete", ok, detail)

    # Portable environment: no exported machine prefix, and R must not silently
    # activate the retained historical renv scaffold.
    lock_text, lock_error = _read_text(root / "environment.lock.yml")
    prefix_lines = [] if lock_text is None else [
        line.strip() for line in lock_text.splitlines() if re.match(r"^\s*prefix\s*:", line, re.IGNORECASE)
    ]
    add(
        "environment lock has no machine-specific prefix",
        lock_error is None and not prefix_lines,
        "no prefix key" if lock_error is None and not prefix_lines else (lock_error or f"found {prefix_lines}"),
    )

    rprofile_text, rprofile_error = _read_text(root / ".Rprofile")
    active_r = ""
    if rprofile_text is not None:
        active_r = "\n".join(line.split("#", 1)[0] for line in rprofile_text.splitlines())
    renv_activation = bool(
        re.search(r"renv\s*::\s*activate|renv[/\\]activate\.r|source\s*\([^)]*renv", active_r, re.IGNORECASE)
    )
    add(
        "R profile does not activate renv",
        rprofile_error is None and not renv_activation,
        "no active renv loader" if rprofile_error is None and not renv_activation else (rprofile_error or "activation found"),
    )

    # README fast path.
    readme, readme_error = _read_text(root / "README.md")
    section = None if readme is None else re.search(
        r"(?ms)^## Understand the project in 60 seconds\s*$\n(.*?)(?=^##\s|\Z)", readme
    )
    section_text = section.group(1) if section else ""
    readme_markers = ("**Question:**", "**Green peafowl:**", "**Scandinavian wolf:**", "**Contribution:**", "**Boundary:**")
    readme_ok = (
        readme_error is None
        and section is not None
        and len(section_text.strip()) > 200
        and all(marker in section_text for marker in readme_markers)
    )
    add(
        "README has the complete 60-second overview",
        readme_ok,
        "heading plus five required bullets" if readme_ok else (readme_error or "section/required bullets missing"),
    )

    # Runtime app proof and its full captured log.
    smoke, smoke_error = _read_text(root / "results/APP_SMOKE.md")
    smoke_plain = _plain_markdown(smoke or "")
    smoke_count = re.search(r"tests run:\s*(\d+)", smoke_plain)
    smoke_ok = (
        smoke_error is None
        and bool(re.search(r"status:\s*pass", smoke_plain))
        and smoke_count is not None
        and int(smoke_count.group(1)) > 0
        and bool(re.search(r"return code:\s*0", smoke_plain))
    )
    add(
        "Streamlit app smoke result is PASS",
        smoke_ok,
        f"{smoke_count.group(1)} tests" if smoke_ok and smoke_count else (smoke_error or "PASS/test count/return code missing"),
    )
    smoke_log = root / "results/logs/app_smoke.log"
    log_ok = smoke_log.is_file() and smoke_log.stat().st_size > 0
    add("Streamlit app smoke log is non-empty", log_ok, f"{smoke_log.stat().st_size:,} bytes" if log_ok else "missing/empty")

    # The clean-clone proof is deliberately external to this validator. The gate
    # requires an explicit, human-readable record rather than inferring success
    # from the current worktree being up to date.
    reproduction, reproduction_error = _read_text(root / "results/PHASE5A_REPRODUCIBILITY.md")
    reproduction_plain = _plain_markdown(reproduction or "")
    reproduction_markers = {
        "Status: PASS": bool(re.search(r"status:\s*pass", reproduction_plain)),
        "full run": "full" in reproduction_plain and "run" in reproduction_plain,
        "clean clone": "clean-clone" in reproduction_plain or "clean clone" in reproduction_plain,
        "local data": "local-data" in reproduction_plain or "local data" in reproduction_plain,
        "Snakemake": "snakemake" in reproduction_plain,
        "successful result": "success" in reproduction_plain,
        "zero failures": bool(re.search(r"\b0\s+fail", reproduction_plain)),
    }
    missing_reproduction = [name for name, present in reproduction_markers.items() if not present]
    reproduction_ok = reproduction_error is None and not missing_reproduction
    add(
        "full clean-clone/local-data reproduction is recorded",
        reproduction_ok,
        "PASS record with full-run command and 0 FAIL" if reproduction_ok else (
            reproduction_error or f"missing markers: {', '.join(missing_reproduction)}"
        ),
    )

    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    with out_tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["check", "status", "detail"])
        writer.writerows(checks)

    n_fail = sum(status == "FAIL" for _, status, _ in checks)
    n_pass = sum(status == "PASS" for _, status, _ in checks)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    with out_md.open("w", encoding="utf-8") as handle:
        handle.write("# Phase 5A — completion validation\n\n")
        handle.write(
            "This is the strict readiness gate before optional Phase 6. It combines the scientific "
            "validators with the communication artifacts, environment portability, runtime app smoke "
            "test, and the separately recorded clean-clone/local-data reproduction.\n\n"
        )
        handle.write("| check | status | detail |\n|---|---|---|\n")
        for name, status, detail in checks:
            clean_detail = str(detail).replace("|", "\\|").replace("\n", " ")
            handle.write(f"| {name} | **{status}** | {clean_detail} |\n")
        handle.write(f"\n**{n_fail} FAIL**, {n_pass} PASS.\n")
        if n_fail == 0:
            handle.write("\n**Phase 5A is complete; Phase 6 is ready to begin.**\n")
        else:
            handle.write("\n**Phase 5A remains incomplete; Phase 6 is not ready.**\n")

    report_rows = [f"{name}: {status} — {detail}" for name, status, detail in checks]
    print("\n".join(report_rows))
    print(f"\n{n_fail} FAIL, {n_pass} PASS")
    raise SystemExit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
