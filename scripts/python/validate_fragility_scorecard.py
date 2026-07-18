#!/usr/bin/env python3
"""Validate the Phase-5A fragility scorecard against its Phase-2/3/4 sources.

The primary reconciliation check independently rebuilds the expected scorecard
from the existing summary tables and requires an exact cell-for-cell match with
the materialized TSV.  The remaining checks guard the fixed four-row scope and
the offline PNG artifact.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

from fragility_scorecard import CLASS_ORDER, SCORECARD_COLUMNS, _read_table, build_scorecard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cube", required=True)
    parser.add_argument("--ne500", required=True)
    parser.add_argument("--robustness", required=True)
    parser.add_argument("--wolf-load", required=True)
    parser.add_argument("--wolf-roh", required=True)
    parser.add_argument("--validation-phase2", required=True)
    parser.add_argument("--validation-phase3", required=True)
    parser.add_argument("--validation-phase4", required=True)
    parser.add_argument("--scorecard", required=True)
    parser.add_argument("--figure", required=True)
    parser.add_argument("--out-tsv", required=True)
    parser.add_argument("--out-md", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = [
        args.cube,
        args.ne500,
        args.robustness,
        args.wolf_load,
        args.wolf_roh,
        args.validation_phase2,
        args.validation_phase3,
        args.validation_phase4,
        args.scorecard,
        args.figure,
    ]
    missing = [path for path in paths if not Path(path).is_file()]
    if missing:
        raise SystemExit(f"missing input artifact(s): {', '.join(missing)}")

    source_paths = paths[:8]
    sources = [_read_table(path) for path in source_paths]
    cube, ne500, robustness, wolf_load, wolf_roh, _, _, _ = sources
    expected = build_scorecard(*sources).astype(str)
    observed = pd.read_csv(args.scorecard, sep="\t", dtype=str, keep_default_na=False)

    checks: list[tuple[str, str, str]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append((name, "PASS" if ok else "FAIL", detail))

    add(
        "scorecard schema is exact",
        list(observed.columns) == SCORECARD_COLUMNS,
        f"got {list(observed.columns)}",
    )
    required_ids = {
        "peafowl_ne500_confidence",
        "peafowl_filter_dependence",
        "wolf_load_direction",
        "wolf_threshold_magnitude",
    }
    has_id_column = "conclusion_id" in observed.columns
    add(
        "four pre-specified conclusions present once",
        len(observed) == 4
        and has_id_column
        and observed["conclusion_id"].is_unique
        and set(observed["conclusion_id"]) == required_ids,
        f"rows={len(observed)}, ids={sorted(observed['conclusion_id'].tolist()) if has_id_column else 'missing column'}",
    )
    has_class_column = "classification" in observed.columns
    add(
        "all four interpretation classes represented",
        has_class_column and set(observed["classification"]) == set(CLASS_ORDER),
        f"classes={sorted(observed['classification'].unique()) if has_class_column else 'missing column'}",
    )

    # Exact source reconciliation: same row order, schema, and text/numeric evidence.
    mismatch = "none"
    exact = False
    if list(observed.columns) == SCORECARD_COLUMNS:
        try:
            pd.testing.assert_frame_equal(
                observed.reset_index(drop=True),
                expected.reset_index(drop=True),
                check_dtype=False,
                check_like=False,
            )
            exact = True
        except AssertionError as exc:
            mismatch = str(exc).splitlines()[0]
    add(
        "scorecard exactly reconciles with source tables",
        exact,
        "cell-for-cell rebuild matches cube, GBF, wolf, and validation tables" if exact else mismatch,
    )

    # Independent metric checks make the scientific reconciliation explicit,
    # rather than relying only on the shared table-building function above.
    rows = observed.set_index("conclusion_id") if has_id_column and observed["conclusion_id"].is_unique else None

    n_presets = ne500["filter_preset"].nunique()
    zero_pass = int((ne500["n_pass"] == 0).sum())
    peafowl_headline_ok = (
        rows is not None
        and "peafowl_ne500_confidence" in rows.index
        and zero_pass == n_presets
        and rows.loc["peafowl_ne500_confidence", "support_fraction"] == f"{zero_pass}/{n_presets}"
    )
    add(
        "peafowl confidence headline reconciles with GBF counts",
        peafowl_headline_ok,
        f"{zero_pass}/{n_presets} presets have zero confident population passes",
    )

    stable = robustness["stable"].map(
        lambda value: value if isinstance(value, bool) else str(value).strip().lower() == "true"
    )
    n_changed = int((~stable).sum())
    pp = cube.loc[cube["structure_mode"] == "per_population"]
    non_converged = pp["ne_point"].isna() | pp["ne_basis"].astype(str).str.lower().eq("none")
    n_non_converged = int(non_converged.sum())
    peafowl_filter_ok = (
        rows is not None
        and "peafowl_filter_dependence" in rows.index
        and rows.loc["peafowl_filter_dependence", "settings_supporting"]
        == f"{n_changed}/{len(robustness)} populations change verdict; {n_non_converged}/{len(pp)} cells do not converge"
    )
    add(
        "peafowl filter dependence reconciles with cube and robustness table",
        peafowl_filter_ok,
        f"{n_changed}/{len(robustness)} verdicts change; {n_non_converged}/{len(pp)} cells non-converged",
    )

    load_means = wolf_load.groupby(["POP", "THRES"])[["REALIZED_LOAD", "MASKED_LOAD"]].mean()
    directions = (load_means["REALIZED_LOAD"] > load_means["MASKED_LOAD"]).groupby(level="POP").nunique()
    stable_groups = int((directions == 1).sum())
    n_groups = int(len(directions))
    n_thresholds = int(wolf_load["THRES"].nunique())
    wolf_direction_ok = (
        rows is not None
        and "wolf_load_direction" in rows.index
        and stable_groups == n_groups
        and rows.loc["wolf_load_direction", "support_fraction"] == f"{stable_groups}/{n_groups}"
    )
    add(
        "wolf load direction reconciles across every GERP threshold",
        wolf_direction_ok,
        f"{stable_groups}/{n_groups} groups retain direction across {n_thresholds} thresholds",
    )

    realized_means = wolf_load.groupby("THRES")["REALIZED_LOAD"].mean()
    froh_means = wolf_roh.groupby("min_length_mb")["F_ROH"].mean()

    def fmt(value: float) -> str:
        return f"{value:.3f}".rstrip("0").rstrip(".")

    magnitude_text = (
        f"mean realized load {fmt(realized_means.min())}-{fmt(realized_means.max())}; "
        f"mean F_ROH {fmt(froh_means.min())}-{fmt(froh_means.max())}"
    )
    wolf_magnitude_ok = (
        rows is not None
        and "wolf_threshold_magnitude" in rows.index
        and realized_means.round(12).nunique() == len(realized_means)
        and froh_means.round(12).nunique() == len(froh_means)
        and rows.loc["wolf_threshold_magnitude", "observed_result"] == magnitude_text
    )
    add(
        "wolf magnitude ranges reconcile with load and ROH tables",
        wolf_magnitude_ok,
        magnitude_text,
    )

    evidence_columns = (
        "settings_supporting",
        "settings_tested",
        "dominant_uncertainty",
        "evidence_needed",
        "source_tables",
        "validation_evidence",
    )
    evidence_complete = set(evidence_columns) <= set(observed.columns) and all(
        observed[column].str.strip().ne("").all() for column in evidence_columns
    )
    add(
        "every conclusion records settings, uncertainty, and next evidence",
        evidence_complete,
        "required explanatory fields are non-empty for all rows",
    )

    figure = Path(args.figure)
    with figure.open("rb") as handle:
        signature = handle.read(8)
    is_png = signature == b"\x89PNG\r\n\x1a\n"
    figure_ok = is_png and figure.stat().st_size >= 10_000
    add(
        "offline figure is a non-empty PNG",
        figure_ok,
        f"signature={'PNG' if is_png else 'invalid'}, bytes={figure.stat().st_size}",
    )

    report = pd.DataFrame(checks, columns=["check", "status", "detail"])
    out_tsv = Path(args.out_tsv)
    out_md = Path(args.out_md)
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(out_tsv, sep="\t", index=False)

    n_fail = int((report["status"] == "FAIL").sum())
    with out_md.open("w") as handle:
        handle.write("# Phase 5A.1 — fragility scorecard validation\n\n")
        handle.write(
            "This gate rebuilds the four-row scorecard directly from the validated Phase-2/3/4 "
            "summary tables and requires an exact cell-for-cell match. It also checks the fixed "
            "scope, four interpretation classes, explanatory evidence, and offline PNG artifact.\n\n"
        )
        handle.write("| check | status | detail |\n|---|---|---|\n")
        for row in report.itertuples(index=False):
            detail = str(row.detail).replace("|", "\\|")
            handle.write(f"| {row.check} | **{row.status}** | {detail} |\n")
        handle.write(
            f"\n**{n_fail} FAIL**, {(report['status'] == 'PASS').sum()} PASS. "
            "No raw variants or heavy bioinformatics were read by this validation.\n"
        )

    print(report.to_string(index=False))
    print(f"\n{n_fail} FAIL")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
