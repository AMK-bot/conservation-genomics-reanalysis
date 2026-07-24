#!/usr/bin/env python3
"""Independently validate the ordered Section-13.6 core communication hand-off."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pandas as pd
import yaml


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def truthy(value: object) -> bool:
    return value if isinstance(value, bool) else str(value).strip().lower() == "true"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", default="results/tables/phase5b_core_claim_contract.tsv")
    parser.add_argument("--provenance", default="results/provenance/phase5b_core_integration.json")
    parser.add_argument("--wolf", default="results/tables/wolf_froh_load_associations.tsv")
    parser.add_argument("--damage", default="results/tables/peafowl_damage_effects.tsv")
    parser.add_argument("--ne", default="results/tables/peafowl_ne_design_summary.tsv")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--report", default="report/report.qmd")
    parser.add_argument("--app", default="app/streamlit_app.py")
    parser.add_argument("--html", default="index.html")
    parser.add_argument("--js", default="website/site.js")
    parser.add_argument("--css", default="website/site.css")
    parser.add_argument("--out-tsv", default="results/tables/validation_phase5b_core_integration.tsv")
    parser.add_argument("--out-md", default="results/PHASE5B_CORE_INTEGRATION_VALIDATION.md")
    args = parser.parse_args()

    checks: list[tuple[str, str, str]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append((name, "PASS" if ok else "FAIL", detail))

    input_paths = {
        key: Path(getattr(args, key))
        for key in ("contract", "provenance", "wolf", "damage", "ne", "config", "report", "app", "html", "js", "css")
    }
    missing = [str(path) for path in input_paths.values() if not path.is_file()]
    add("all core integration artifacts and sources exist", not missing, "complete" if not missing else str(missing))
    if missing:
        # Write a useful failure report without cascading unreadable-file errors.
        report = pd.DataFrame(checks, columns=["check", "status", "detail"])
        Path(args.out_tsv).parent.mkdir(parents=True, exist_ok=True)
        report.to_csv(args.out_tsv, sep="\t", index=False)
        Path(args.out_md).write_text("# Phase 5B core integration validation\n\n**0 PASS, 1 FAIL**\n", encoding="utf-8")
        raise SystemExit(1)

    contract = pd.read_csv(args.contract, sep="\t")
    provenance = json.loads(Path(args.provenance).read_text(encoding="utf-8"))
    wolf = pd.read_csv(args.wolf, sep="\t")
    damage = pd.read_csv(args.damage, sep="\t")
    ne = pd.read_csv(args.ne, sep="\t")
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    required = {
        "claim_id", "section", "question", "prediction", "stress_test", "result", "correction",
        "falsifier_operator", "falsifier_threshold", "observed_value", "unit",
        "conservation_consequence", "table", "provenance", "validator", "report_anchor",
        "explorer_anchor",
    }
    add(
        "contract has three ordered core claims and complete trace schema",
        len(contract) == 3
        and contract["section"].astype(str).tolist() == ["13.1", "13.3", "13.2"]
        and not (required - set(contract.columns))
        and contract[list(required)].notna().all().all(),
        f"rows={len(contract)}, sections={contract['section'].astype(str).tolist()}",
    )

    partial = wolf.loc[
        wolf["outcome"].astype(str).eq("realized_load")
        & wolf["model"].astype(str).str.contains("partial")
    ]
    expected_wolf = int(partial["ci_low"].gt(0).sum())
    row_wolf = contract.loc[contract["claim_id"].eq("wolf_froh_load_association")].iloc[0]
    wolf_threshold = int(config["phase5b"]["wolf_robustness"]["roh_localization_reopen_min_cells"])
    add(
        "wolf result and numeric gate independently reconcile",
        len(partial) == 15
        and int(row_wolf["observed_value"]) == expected_wolf
        and int(float(row_wolf["falsifier_threshold"])) == wolf_threshold,
        f"observed={expected_wolf}/15; threshold={wolf_threshold}",
    )

    expected_damage = 0
    for _metric, group in damage.groupby("metric"):
        expected_damage += int(
            group["direction"].astype(str).eq("museum_higher").all()
            and group["same_direction_all_snp_vs_transversion"].map(truthy).all()
            and (group["equal_n_same_direction_n"] == group["equal_n_cases_n"]).all()
            and (group["leave_one_same_direction_n"] == group["leave_one_cases_n"]).all()
        )
    row_damage = contract.loc[contract["claim_id"].eq("peafowl_damage_falsification")].iloc[0]
    damage_threshold = int(config["phase5b"]["damage_falsification"]["upgrade_min_concordant_metrics"])
    add(
        "damage-aware result and numeric falsifier independently reconcile",
        int(row_damage["observed_value"]) == expected_damage
        and int(float(row_damage["falsifier_threshold"])) == damage_threshold
        and "geograph" in str(row_damage["result"]).lower(),
        f"observed={expected_damage}/4; threshold={damage_threshold}; geography retained",
    )

    scenario = ne.loc[ne["analysis_type"].astype(str).eq("scenario")].copy()
    boundary = scenario.loc[pd.to_numeric(scenario["true_ne"]).eq(500)].copy()
    boundary_required = {
        "n_attempted", "n_execution_failure", "execution_failure_rate",
        "n_correct_confident", "correct_confident_rate", "n_incorrect_confident",
        "incorrect_confident_rate", "n_indeterminate", "indeterminate_rate",
        "n_boundary_confident_pass", "boundary_confident_pass_rate",
        "n_boundary_confident_fail", "boundary_confident_fail_rate",
    }
    boundary_schema_ok = not (boundary_required - set(boundary.columns))
    if boundary_schema_ok:
        boundary_count_total = (
            pd.to_numeric(boundary["n_execution_failure"])
            + pd.to_numeric(boundary["n_boundary_confident_pass"])
            + pd.to_numeric(boundary["n_boundary_confident_fail"])
            + pd.to_numeric(boundary["n_indeterminate"])
        )
        boundary_rate_total = (
            pd.to_numeric(boundary["execution_failure_rate"])
            + pd.to_numeric(boundary["boundary_confident_pass_rate"])
            + pd.to_numeric(boundary["boundary_confident_fail_rate"])
            + pd.to_numeric(boundary["indeterminate_rate"])
        )
        boundary_ok = (
            len(boundary) == 15
            and boundary["truth_class"].astype(str).eq("boundary").all()
            and boundary_count_total.eq(pd.to_numeric(boundary["n_attempted"])).all()
            and boundary_rate_total.sub(1.0).abs().le(1e-12).all()
            and pd.to_numeric(boundary["n_correct_confident"]).eq(0).all()
            and pd.to_numeric(boundary["n_incorrect_confident"]).eq(0).all()
            and pd.to_numeric(boundary["correct_confident_rate"]).eq(0).all()
            and pd.to_numeric(boundary["incorrect_confident_rate"]).eq(0).all()
        )
    else:
        boundary_ok = False
    add(
        "Ne=500 is a boundary partition and is never scored correct/incorrect",
        boundary_ok,
        f"boundary rows={len(boundary)}/15; schema_ok={boundary_schema_ok}",
    )
    truths = {float(value) for value in config["phase5b"]["ne_design"]["resolution_truths"]}
    correct_floor = float(config["phase5b"]["ne_design"]["resolution_min_correct_confident_ci_low"])
    incorrect_ceiling = float(config["phase5b"]["ne_design"]["resolution_max_incorrect_confident_ci_high"])
    target = scenario.loc[scenario["true_ne"].astype(float).isin(truths)].copy()
    target["meets"] = target["correct_confident_ci_low"].ge(correct_floor) & target["incorrect_confident_ci_high"].le(incorrect_ceiling)
    designs = [
        set(group["true_ne"].astype(float)) == truths and bool(group["meets"].all())
        for _key, group in target.groupby(["sample_size", "marker_density"])
    ]
    row_ne = contract.loc[contract["claim_id"].eq("peafowl_ne_study_design")].iloc[0]
    ne_consequence = str(row_ne["conservation_consequence"]).lower()
    consequence_ok = "simplified known-truth scenarios" in ne_consequence
    if int(sum(designs)) == 0:
        consequence_ok = (
            consequence_ok
            and "no tested design" in ne_consequence
            and "does not support an empirical sampling prescription" in ne_consequence
        )
    add(
        "Ne design result and uncertainty-bounded resolution rule reconcile",
        len(designs) == 15
        and int(row_ne["observed_value"]) == int(sum(designs))
        and str(correct_floor) in str(row_ne["falsifier_threshold"])
        and str(incorrect_ceiling) in str(row_ne["falsifier_threshold"])
        and consequence_ok,
        (
            f"resolving={sum(designs)}/15; bounds={correct_floor}/{incorrect_ceiling}; "
            "consequence is conditional and scenario-qualified"
        ),
    )
    add(
        "each claim separates result, correction, falsifier, and consequence",
        contract[["result", "correction", "conservation_consequence"]].apply(
            lambda column: column.astype(str).str.len().ge(20).all()
        ).all(),
        "all three contracts retain the seven-step reasoning path",
    )

    report_text = Path(args.report).read_text(encoding="utf-8")
    app_text = Path(args.app).read_text(encoding="utf-8")
    html_text = Path(args.html).read_text(encoding="utf-8")
    js_text = Path(args.js).read_text(encoding="utf-8")
    css_text = Path(args.css).read_text(encoding="utf-8")
    report_normalized = " ".join(report_text.lower().split())
    # Join prose split across adjacent Python string literals before matching the
    # rendered scientific boundary. Whitespace normalization alone leaves `" "`
    # source delimiters between words that are contiguous at runtime.
    app_normalized = " ".join(re.sub(r'"\s*"', "", app_text.lower()).split())
    add(
        "technical report has all three core result anchors and scientific boundaries",
        all(anchor in report_text for anchor in ("#damage-aware-falsification", "#ne-sample-design-calibration", "#wolf-individual-association"))
        and "not a guarantee" in report_normalized
        and "not temporal genetic erosion" in report_normalized
        and "shared-parent pedigree" in report_normalized
        and "32 one-morgan chromosomes" in report_normalized
        and "not independent biological-sampling uncertainty" in report_normalized,
        "anchors, finalized Ne model, empirical uncertainty, and causal boundaries present",
    )
    add(
        "Streamlit explorer reads all three core machine tables without recomputation",
        all(name in app_text for name in (
            "wolf_froh_load_associations.tsv", "peafowl_damage_effects.tsv", "peafowl_ne_design_summary.tsv"
        ))
        and "associations among genomic proxies" in app_normalized
        and "sampling guarantee" in app_normalized
        and "int(design_truth) == 500" in app_text
        and "boundary_confident_pass_rate" in app_text
        and "boundary_confident_fail_rate" in app_text
        and "never scored as correct or incorrect" in app_normalized
        and "not independent biological-sampling uncertainty" in app_normalized
        and "snakemake --snakefile workflow/Snakefile phase5b --cores 4 --resources mem_mb=7000" in app_text,
        "three read-only panels, boundary-specific outcomes, and boundaries present",
    )
    path_terms = ["Question", "Prediction", "Stress test", "Result", "Correction", "Falsifier", "Conservation consequence"]
    positions = [html_text.find(f"<span>{term}</span>") for term in path_terms]
    add(
        "static portal presents the exact seven-step scientific path in order",
        all(position >= 0 for position in positions) and positions == sorted(positions),
        " -> ".join(path_terms),
    )
    add(
        "static portal has native core controls, causal boundary, and numeric mind-change cards",
        all(token in html_text for token in (
            "data-wolf-gerp", "data-damage-variant", "data-ne-truth", "causal-chain", "mind-grid",
            "data-claim-trace-list", "data-ne-correct-label", "data-ne-incorrect-label"
        ))
        and "Not observed:" in html_text
        and "15 / 15" in html_text
        and "1 / 4" in html_text,
        "native selects, absent-fitness stop, trace, boundary labels, and numeric cards present",
    )
    add(
        "offline JavaScript uses generated local data and handles missing assets",
        "window.PHASE5B_DATA" in js_text
        and "disablePhase5b" in js_text
        and "data-missing-asset" in js_text
        and "selectedTruth === 500" in js_text
        and "boundary_confident_pass_rate" in js_text
        and "boundary_confident_fail_rate" in js_text
        and "not independent biological-sampling uncertainty" in html_text.lower()
        and "snakemake --snakefile workflow/Snakefile phase5b --cores 4 --resources mem_mb=7000" in html_text
        and "fetch(" not in js_text,
        "local global payload; boundary labels switch at true Ne=500; no fetch; fallbacks present",
    )
    add(
        "responsive and reduced-motion behavior covers the decision layer",
        "@media (max-width: 620px)" in css_text
        and ".phase5b-lab" in css_text
        and "@media (prefers-reduced-motion: reduce)" in css_text,
        "responsive lab/card grids and reduced-motion override present",
    )

    provenance_inputs = provenance.get("inputs", {})
    input_hashes_ok = all(
        Path(record.get("path", "")).is_file()
        and sha256_file(Path(record["path"])) == record.get("sha256")
        for record in provenance_inputs.values()
    )
    add(
        "core integration provenance hashes every analysis and validator input",
        provenance.get("order") == ["13.1", "13.3", "13.2", "13.6"]
        and input_hashes_ok
        and provenance.get("output", {}).get("sha256") == sha256_file(Path(args.contract)),
        f"inputs={len(provenance_inputs)}; ordered hand-off recorded",
    )

    report = pd.DataFrame(checks, columns=["check", "status", "detail"])
    out_tsv = Path(args.out_tsv)
    out_md = Path(args.out_md)
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(out_tsv, sep="\t", index=False, lineterminator="\n")
    n_pass = int(report["status"].eq("PASS").sum())
    n_fail = int(report["status"].eq("FAIL").sum())
    lines = [
        "# Phase 5B core communication integration validation",
        "",
        "This gate freezes Section 13.6 after the three core analyses and before optional-study decisions.",
        "",
        f"**Summary: {n_pass} PASS, {n_fail} FAIL**",
        "",
        "| check | status | evidence |",
        "|---|---|---|",
    ]
    for row in report.itertuples(index=False):
        clean_detail = str(row.detail).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {row.check} | **{row.status}** | {clean_detail} |")
    lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(report.to_string(index=False))
    print(f"\n{n_pass} PASS, {n_fail} FAIL")
    raise SystemExit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
