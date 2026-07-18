#!/usr/bin/env python3
"""Build the Phase-5A fragility scorecard from existing summary tables.

This is deliberately a lightweight synthesis step: it reads the tracked peafowl
cube/GBF summaries, wolf load/ROH summaries, and their Phase-2/3/4 validation
reports.  It does not touch VCFs or re-run any bioinformatics.

Outputs
-------
results/tables/fragility_scorecard.tsv
    One row per pre-specified biological conclusion, including the tested and
    supporting settings, robustness class, uncertainty, and evidence needed.
results/figures/fragility_scorecard.png
    A compact, offline-readable rendering of the same four rows.
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

import pandas as pd


CLASS_ORDER = [
    "robust conclusion",
    "fragile magnitude",
    "insufficient evidence",
    "method-dependent result",
]

CLASS_COLORS = {
    "robust conclusion": "#1B7F5A",
    "fragile magnitude": "#D38B22",
    "insufficient evidence": "#6D6F75",
    "method-dependent result": "#8B5FBF",
}

SCORECARD_COLUMNS = [
    "conclusion_id",
    "taxon",
    "conclusion",
    "classification",
    "settings_supporting",
    "settings_tested",
    "support_fraction",
    "conclusion_robust",
    "only_magnitude_sensitive",
    "observed_result",
    "dominant_uncertainty",
    "evidence_needed",
    "source_tables",
    "validation_evidence",
]

REQUIRED_VALIDATION = {
    "phase2": {
        "cube has 12 rows",
        "schema columns present",
        "every preset has 3 per_population + 1 pooled(ALL)",
    },
    "phase3": {
        "ne500 counts reconcile with the cube",
        "robustness `stable` flag correct",
    },
    "phase4": {
        "load has all GERP thresholds",
        "GERP>4 reconciles with the deposit anchor",
        "F_ROH in [0,1]",
        "F_ROH non-increasing as ROH-length cutoff rises",
    },
}


def _read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    sep = "\t" if path.suffix == ".tsv" else ","
    return pd.read_csv(path, sep=sep)


def _require_columns(df: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = columns - set(df.columns)
    if missing:
        raise ValueError(f"{label} is missing columns: {sorted(missing)}")


def _checked_validation(report: pd.DataFrame, phase: str) -> str:
    """Require the existing structural validation anchors and return a citation."""
    _require_columns(report, {"check", "status", "detail"}, f"{phase} validation")
    by_check = report.set_index("check")["status"].astype(str)
    required = REQUIRED_VALIDATION[phase]
    missing = required - set(by_check.index)
    if missing:
        raise ValueError(f"{phase} validation is missing checks: {sorted(missing)}")
    not_pass = {check: by_check.loc[check] for check in required if by_check.loc[check] != "PASS"}
    if not_pass:
        raise ValueError(f"{phase} validation anchors are not PASS: {not_pass}")
    return f"{phase.upper()}: " + "; ".join(f"{check} [PASS]" for check in sorted(required))


def _format_number(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def build_scorecard(
    cube: pd.DataFrame,
    ne500: pd.DataFrame,
    robustness: pd.DataFrame,
    wolf_load: pd.DataFrame,
    wolf_roh: pd.DataFrame,
    validation_phase2: pd.DataFrame,
    validation_phase3: pd.DataFrame,
    validation_phase4: pd.DataFrame,
) -> pd.DataFrame:
    """Derive the four pre-specified scorecard conclusions from summary tables."""
    _require_columns(
        cube,
        {"filter_preset", "structure_mode", "population", "ne_point", "ne_basis", "gbf_state", "n_ind"},
        "results cube",
    )
    _require_columns(
        ne500,
        {"filter_preset", "n_pops", "n_pass", "n_fail", "n_indeterminate", "ne_threshold"},
        "GBF N_e table",
    )
    _require_columns(robustness, {"population", "stable"}, "GBF robustness table")
    _require_columns(wolf_load, {"POP", "THRES", "REALIZED_LOAD", "MASKED_LOAD"}, "wolf load table")
    _require_columns(wolf_roh, {"min_length_mb", "F_ROH"}, "wolf ROH table")

    v2 = _checked_validation(validation_phase2, "phase2")
    v3 = _checked_validation(validation_phase3, "phase3")
    v4 = _checked_validation(validation_phase4, "phase4")

    pp = cube.loc[cube["structure_mode"] == "per_population"].copy()
    presets = sorted(ne500["filter_preset"].astype(str).unique())
    populations = sorted(pp["population"].astype(str).unique())

    if len(ne500) != len(presets):
        raise ValueError("GBF N_e table must contain exactly one row per filter preset")
    if ne500["ne_threshold"].nunique() != 1:
        raise ValueError("GBF N_e table contains more than one N_e threshold")
    threshold = float(ne500["ne_threshold"].iloc[0])

    # Row 1 — the headline remains 0 confident passes under every filter preset.
    zero_pass = int((ne500["n_pass"] == 0).sum())
    n_pops_values = sorted(ne500["n_pops"].astype(int).unique())
    if len(n_pops_values) != 1:
        raise ValueError("GBF N_e table contains inconsistent population counts")
    n_pops = n_pops_values[0]
    state_counts = "; ".join(
        f"{r.filter_preset}: {int(r.n_pass)} pass/{int(r.n_fail)} fail/"
        f"{int(r.n_indeterminate)} indeterminate"
        for r in ne500.itertuples()
    )

    # Row 2 — verdict changes and non-convergence make the population-level result
    # filter-dependent.  Treat a missing point estimate or ne_basis=none as non-converged.
    stable = robustness["stable"].map(
        lambda value: value if isinstance(value, bool) else str(value).strip().lower() == "true"
    )
    n_changed = int((~stable).sum())
    non_converged = pp["ne_point"].isna() | pp["ne_basis"].astype(str).str.lower().eq("none")
    n_non_converged = int(non_converged.sum())
    sample_sizes = sorted(pp.groupby("population")["n_ind"].first().astype(int).unique())
    convergence_by_preset = []
    for preset in presets:
        subset = pp.loc[pp["filter_preset"].astype(str) == preset]
        converged = int((subset["ne_point"].notna() & ~subset["ne_basis"].astype(str).str.lower().eq("none")).sum())
        convergence_by_preset.append(f"{preset}: {converged}/{len(subset)} converged")

    # Row 3 — compare each population/time group's realized-vs-masked direction at
    # every tracked GERP threshold.  A group supports the claim only if its direction
    # is identical across the complete threshold sweep.
    load_means = (
        wolf_load.groupby(["POP", "THRES"], as_index=False)[["REALIZED_LOAD", "MASKED_LOAD"]]
        .mean()
        .sort_values(["POP", "THRES"])
    )
    load_means["direction"] = load_means.apply(
        lambda row: "realized>masked" if row["REALIZED_LOAD"] > row["MASKED_LOAD"] else "realized<=masked",
        axis=1,
    )
    thresholds = sorted(load_means["THRES"].unique())
    directions_per_group = load_means.groupby("POP")["direction"].nunique()
    stable_groups = int((directions_per_group == 1).sum())
    n_groups = int(directions_per_group.size)
    group_direction = load_means.groupby("POP")["direction"].first()
    n_realized = int((group_direction == "realized>masked").sum())
    n_masked = int((group_direction == "realized<=masked").sum())

    # Row 4 — numerical means over each sensitivity axis.  The ranges are shown,
    # rather than converted into a new threshold or biological verdict.
    realized_by_threshold = wolf_load.groupby("THRES")["REALIZED_LOAD"].mean().sort_index()
    froh_by_cutoff = wolf_roh.groupby("min_length_mb")["F_ROH"].mean().sort_index()
    n_load_distinct = int(realized_by_threshold.round(12).nunique())
    n_roh_distinct = int(froh_by_cutoff.round(12).nunique())

    # These statements are the pre-specified Phase-5A.1 conclusions. If future
    # source tables no longer support one, stop for scientific review instead of
    # emitting a stale declarative sentence.
    if zero_pass != len(presets):
        raise ValueError("not every filter preset supports the 0-confident-pass peafowl headline")
    if n_changed == 0 and n_non_converged == 0:
        raise ValueError("source tables no longer support filter-fragile peafowl results")
    if stable_groups != n_groups:
        raise ValueError("wolf realized-versus-masked direction is not stable for every group")
    if n_load_distinct <= 1 or n_roh_distinct <= 1:
        raise ValueError("source tables no longer support threshold-sensitive wolf magnitudes")

    records = [
        {
            "conclusion_id": "peafowl_ne500_confidence",
            "taxon": "Green peafowl",
            "conclusion": f"No sampled peafowl population confidently clears N_e>{threshold:g} across filter presets.",
            "classification": "insufficient evidence",
            "settings_supporting": f"{zero_pass}/{len(presets)} filter presets have 0/{n_pops} confident passes",
            "settings_tested": f"{len(presets)} filter presets; {len(pp)} population x preset cells",
            "support_fraction": f"{zero_pass}/{len(presets)}",
            "conclusion_robust": "yes" if zero_pass == len(presets) else "no",
            "only_magnitude_sensitive": "no",
            "observed_result": state_counts,
            "dominant_uncertainty": (
                f"Small per-population samples (n={'/'.join(str(n) for n in sample_sizes)}) produce wide or "
                "unresolved contemporary-N_e estimates."
            ),
            "evidence_needed": "More individuals per population; adding SNPs alone cannot resolve uncertainty caused by small n.",
            "source_tables": "results/cube/results_cube.parquet; results/tables/gbf_ne500.tsv",
            "validation_evidence": f"{v2}; {v3}",
        },
        {
            "conclusion_id": "peafowl_filter_dependence",
            "taxon": "Green peafowl",
            "conclusion": "Population-level peafowl estimates, convergence, and verdicts are filter-fragile.",
            "classification": "method-dependent result",
            "settings_supporting": f"{n_changed}/{len(robustness)} populations change verdict; {n_non_converged}/{len(pp)} cells do not converge",
            "settings_tested": f"{len(pp)} population x preset cells across {len(presets)} filter presets",
            "support_fraction": f"{n_changed}/{len(robustness)} populations",
            "conclusion_robust": "no",
            "only_magnitude_sensitive": "no",
            "observed_result": "; ".join(convergence_by_preset),
            "dominant_uncertainty": "Filter choice interacts with very small population samples and estimator convergence.",
            "evidence_needed": "More individuals per population plus a pre-specified filter sensitivity analysis; extra SNPs alone are insufficient.",
            "source_tables": "results/cube/results_cube.parquet; results/tables/gbf_robustness.tsv",
            "validation_evidence": f"{v2}; {v3}",
        },
        {
            "conclusion_id": "wolf_load_direction",
            "taxon": "Scandinavian wolf",
            "conclusion": "The group-level realized-versus-masked load direction is stable across GERP thresholds.",
            "classification": "robust conclusion",
            "settings_supporting": f"{stable_groups}/{n_groups} groups preserve direction across all {len(thresholds)} GERP thresholds",
            "settings_tested": f"{len(load_means)} group x GERP cells ({n_groups} groups x {len(thresholds)} thresholds)",
            "support_fraction": f"{stable_groups}/{n_groups}",
            "conclusion_robust": "yes" if stable_groups == n_groups else "no",
            "only_magnitude_sensitive": "yes" if stable_groups == n_groups else "no",
            "observed_result": f"{n_realized} groups remain realized>masked; {n_masked} remain realized<=masked",
            "dominant_uncertainty": "GERP threshold changes load magnitude; genetic load is a risk proxy rather than measured fitness.",
            "evidence_needed": "Measured fitness or reproductive data before interpreting the stable load pattern as inbreeding depression.",
            "source_tables": "results/tables/wolf_load.tsv",
            "validation_evidence": v4,
        },
        {
            "conclusion_id": "wolf_threshold_magnitude",
            "taxon": "Scandinavian wolf",
            "conclusion": "Wolf load and F_ROH magnitudes depend on the GERP and ROH-length thresholds.",
            "classification": "fragile magnitude",
            "settings_supporting": f"{n_load_distinct}/{len(realized_by_threshold)} GERP means and {n_roh_distinct}/{len(froh_by_cutoff)} ROH means are distinct",
            "settings_tested": f"{len(realized_by_threshold)} GERP thresholds; {len(froh_by_cutoff)} ROH-length cutoffs",
            "support_fraction": f"{n_load_distinct + n_roh_distinct}/{len(realized_by_threshold) + len(froh_by_cutoff)} settings",
            "conclusion_robust": "yes" if n_load_distinct > 1 and n_roh_distinct > 1 else "no",
            "only_magnitude_sensitive": "yes",
            "observed_result": (
                f"mean realized load {_format_number(realized_by_threshold.min())}-"
                f"{_format_number(realized_by_threshold.max())}; mean F_ROH "
                f"{_format_number(froh_by_cutoff.min())}-{_format_number(froh_by_cutoff.max())}"
            ),
            "dominant_uncertainty": "Analyst-defined GERP and ROH-length cutoffs, plus the constant recombination-rate approximation.",
            "evidence_needed": "Biologically justified pre-specified thresholds and measured fitness data for any depression claim.",
            "source_tables": "results/tables/wolf_load.tsv; results/tables/wolf_roh.tsv",
            "validation_evidence": v4,
        },
    ]
    return pd.DataFrame(records, columns=SCORECARD_COLUMNS)


def plot_scorecard(scorecard: pd.DataFrame, output: str | Path) -> None:
    """Render a compact four-card view that remains legible outside the app."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    fig, ax = plt.subplots(figsize=(14, 12), facecolor="#F5F3EE")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.04, 0.955, "Fragility scorecard", fontsize=25, fontweight="bold", color="#1D2A32", va="top")
    ax.text(
        0.04,
        0.91,
        "Existing summary tables only  |  conclusion stability is separated from numerical sensitivity",
        fontsize=11,
        color="#4E5961",
        va="top",
    )

    top = 0.87
    card_height = 0.20
    gap = 0.012
    for index, row in scorecard.iterrows():
        y = top - index * (card_height + gap) - card_height
        color = CLASS_COLORS[row["classification"]]
        card = FancyBboxPatch(
            (0.04, y),
            0.92,
            card_height,
            boxstyle="round,pad=0.008,rounding_size=0.012",
            facecolor="white",
            edgecolor="#D9D5CC",
            linewidth=1.0,
        )
        ax.add_patch(card)
        ax.add_patch(
            FancyBboxPatch(
                (0.04, y),
                0.012,
                card_height,
                boxstyle="round,pad=0.002,rounding_size=0.006",
                facecolor=color,
                edgecolor=color,
            )
        )
        ax.text(
            0.075,
            y + card_height - 0.026,
            row["classification"].upper(),
            fontsize=9,
            fontweight="bold",
            color=color,
            va="top",
        )
        ax.text(
            0.075,
            y + card_height - 0.052,
            textwrap.fill(row["conclusion"], width=76),
            fontsize=12.2,
            fontweight="bold",
            color="#1D2A32",
            va="top",
            linespacing=1.15,
        )
        ax.text(
            0.075,
            y + 0.103,
            textwrap.fill(
                f"Support: {row['settings_supporting']} (tested: {row['settings_tested']}).",
                width=116,
            ),
            fontsize=9.2,
            color="#3F4A51",
            va="top",
            linespacing=1.15,
        )
        ax.text(
            0.075,
            y + 0.062,
            textwrap.fill(f"Main uncertainty: {row['dominant_uncertainty']}", width=120),
            fontsize=8.7,
            color="#657079",
            va="top",
            linespacing=1.12,
        )
        ax.text(
            0.075,
            y + 0.033,
            textwrap.fill(f"Evidence needed: {row['evidence_needed']}", width=120),
            fontsize=8.7,
            color="#657079",
            va="top",
            linespacing=1.12,
        )

    ax.text(
        0.96,
        0.018,
        "Derived from validated Phase 2/3/4 outputs",
        fontsize=8.5,
        color="#777B7E",
        ha="right",
        va="bottom",
    )
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


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
    parser.add_argument("--out-table", required=True)
    parser.add_argument("--out-figure", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs = [
        args.cube,
        args.ne500,
        args.robustness,
        args.wolf_load,
        args.wolf_roh,
        args.validation_phase2,
        args.validation_phase3,
        args.validation_phase4,
    ]
    missing = [path for path in inputs if not Path(path).is_file()]
    if missing:
        raise SystemExit(f"missing input table(s): {', '.join(missing)}")

    scorecard = build_scorecard(*(_read_table(path) for path in inputs))
    out_table = Path(args.out_table)
    out_table.parent.mkdir(parents=True, exist_ok=True)
    scorecard.to_csv(out_table, sep="\t", index=False)
    plot_scorecard(scorecard, args.out_figure)
    print(f"wrote {len(scorecard)} conclusions to {out_table}")
    print(f"wrote figure to {args.out_figure}")


if __name__ == "__main__":
    main()
