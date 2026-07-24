#!/usr/bin/env python3
"""Validate the Section-13.4 go/no-go and Section-13.5 deferral review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml

from phase5b_optional_decisions import partial_realized_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--associations", required=True)
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--provenance", required=True)
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--out-tsv", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()

    checks: list[tuple[str, str, str]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append((name, "PASS" if ok else "FAIL", detail))

    decisions = pd.read_csv(args.decisions, sep="\t")
    inventory = pd.read_csv(args.inventory, sep="\t")
    assoc = pd.read_csv(args.associations, sep="\t")
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    provenance = json.loads(Path(args.provenance).read_text(encoding="utf-8"))

    add(
        "both optional studies have one explicit decision",
        set(decisions["section"].astype(str)) == {"13.4", "13.5"} and len(decisions) == 2,
        f"sections={sorted(decisions['section'].astype(str).tolist())}",
    )
    required = {
        "decision",
        "gate_metric",
        "observed_value",
        "required_operator",
        "required_value",
        "reopen_condition",
        "source_trace",
        "scientific_boundary",
    }
    add(
        "decision schema includes numeric gates and scientific boundaries",
        not (required - set(decisions.columns)) and decisions[list(required)].notna().all().all(),
        "numeric observed/required values, source trace, reopening rule, and boundary present",
    )

    partial, estimate_col, ci_low_col, _ = partial_realized_rows(assoc)
    min_cells = int(cfg["phase5b"]["wolf_robustness"]["roh_localization_reopen_min_cells"])
    n_positive = int((pd.to_numeric(partial[estimate_col]) > 0).sum())
    n_ci_positive = int((pd.to_numeric(partial[ci_low_col]) > 0).sum())
    expected_134 = "IMPLEMENT" if n_ci_positive >= min_cells else "NO_GO_NEGATIVE_CONTROL"
    row134 = decisions.loc[decisions["section"].astype(str).eq("13.4")].iloc[0]
    add(
        "13.4 decision exactly follows the predeclared negative-control gate",
        row134["decision"] == expected_134
        and int(row134["observed_value"]) == n_ci_positive
        and int(row134["secondary_observed_value"]) == n_positive
        and int(row134["required_value"]) == min_cells,
        f"{n_ci_positive}/15 CI-positive and {n_positive}/15 point-positive; decision={expected_134}",
    )

    auto = inventory.loc[inventory["scope"].eq("autosomes_1_38")]
    counts = auto.set_index(["definition", "annotation_class"])["n_unique_sites"].to_dict()
    expected_counts = {
        ("VEP", "synonymous"): 33895,
        ("VEP", "missense"): 24405,
        ("VEP", "nonsense"): 1023,
        ("SIFT", "deleterious"): 4809,
        ("SIFT", "tolerated"): 12981,
    }
    add(
        "deposited autosomal VEP and SIFT classes match the source inventory",
        counts == expected_counts and int(auto["duplicate_site_keys"].sum()) == 0,
        "; ".join(f"{key[0]} {key[1]}={value}" for key, value in sorted(counts.items())),
    )
    row135 = decisions.loc[decisions["section"].astype(str).eq("13.5")].iloc[0]
    overlap = provenance.get("source_overlap_review", {})
    overlap_ok = overlap and all(bool(value) for value in overlap.values())
    add(
        "13.5 deferral is supported by exact source-study overlap",
        row135["decision"] == "DEFER_DUPLICATES_SOURCE_STUDY"
        and float(row135["observed_value"]) == 0
        and overlap_ok
        and float(provenance.get("common_sample_fraction", 0)) == 1.0,
        "0 independent definitions; 211/211 common samples; source already compared VEP/SIFT, GERP, and intersection",
    )
    add(
        "deferral has a numeric independence and coverage reopening rule",
        ">=0.95" in str(row135["reopen_condition"])
        and ">=0.90" in str(row135["reopen_condition"])
        and float(row135["required_value"]) == 1,
        str(row135["reopen_condition"]),
    )
    source_text = str(row135["source_trace"])
    add(
        "primary paper and Dryad deposit are source-traced",
        "10.1111/mec.16802" in source_text and "10.5061/dryad.7m0cfxpzj" in source_text,
        source_text,
    )

    report = pd.DataFrame(checks, columns=["check", "status", "detail"])
    out_tsv = Path(args.out_tsv)
    out_md = Path(args.out_md)
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(out_tsv, sep="\t", index=False)
    n_pass = int(report["status"].eq("PASS").sum())
    n_fail = int(report["status"].eq("FAIL").sum())
    lines = [
        "# Phase 5B optional wolf studies — decision validation",
        "",
        "Sections 13.4 and 13.5 are resolved by their scientific gates. A negative or deferred decision is a valid outcome when its evidence and numeric reopening rule reconcile.",
        "",
        f"**Summary: {n_pass} PASS, {n_fail} FAIL**",
        "",
        "| check | status | evidence |",
        "|---|---|---|",
    ]
    for row in report.itertuples(index=False):
        detail = str(row.detail).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {row.check} | **{row.status}** | {detail} |")
    lines.extend(
        [
            "",
            "A Section-13.4 no-go means the generic-homozygosity control did not support a GERP-weighted proxy-localization study. It is not evidence that ROH or load lack biological relevance.",
            "",
            "The Section-13.5 deferral avoids presenting a same-data, same-annotation reproduction as independent triangulation.",
            "",
        ]
    )
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(report.to_string(index=False))
    raise SystemExit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
