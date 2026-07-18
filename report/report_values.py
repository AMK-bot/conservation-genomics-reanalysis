#!/usr/bin/env python3
"""Load and validate the workflow outputs used by ``report.qmd``.

This module is deliberately small and read-only.  It makes the report fail at render time when a
required result table or column is absent, instead of silently leaving stale numbers in prose.
Run ``python report/report_values.py`` for a fast source/provenance check without Quarto.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import re

import numpy as np
import pandas as pd


SOURCE_FILES = {
    "Filtering counts": "results/tables/qc_snp_counts.tsv",
    "Structure": "results/tables/pca_coords.tsv",
    "PCA variance": "results/tables/pca_variance.tsv",
    "ADMIXTURE CV": "results/tables/admixture_cv.tsv",
    "Modern diversity": "results/tables/diversity_perpop.tsv",
    "Allelic richness": "results/tables/allelic_richness_modern.tsv",
    "Temporal diversity": "results/tables/temporal_diversity.tsv",
    "Temporal pi": "results/tables/temporal_pi_summary.tsv",
    "Temporal allelic richness": "results/tables/temporal_allelic_richness.tsv",
    "Effective-size cube": "results/cube/results_cube.csv",
    "GBF Ne indicator": "results/tables/gbf_ne500.tsv",
    "GBF robustness": "results/tables/gbf_robustness.tsv",
    "Populations Maintained": "results/tables/gbf_populations_maintained.tsv",
    "GBF summary": "results/tables/gbf_summary.tsv",
    "GONE2 context": "results/tables/gone2_trajectory.tsv",
    "Wolf load": "results/tables/wolf_load.tsv",
    "Wolf ROH": "results/tables/wolf_roh.tsv",
    "Wolf validation": "results/tables/validation_phase4.tsv",
    "Fragility scorecard": "results/tables/fragility_scorecard.tsv",
}


def find_project_root(start: Path | None = None) -> Path:
    """Find the repository whether Quarto starts in the root or ``report/`` directory."""
    start = (start or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / "config/config.yaml").is_file() and (candidate / "results/tables").is_dir():
            return candidate
    raise FileNotFoundError("cannot find project root containing config/ and results/tables/")


def _read(root: Path, label: str, required: set[str]) -> pd.DataFrame:
    relative = SOURCE_FILES[label]
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(f"missing report input: {relative}; run the corresponding Snakemake phase")
    # results_cube.csv is historically named .csv but intentionally written as a TSV; inspect the
    # header instead of trusting the extension so the report follows the workflow's actual output.
    with path.open(encoding="utf-8") as handle:
        separator = "\t" if "\t" in handle.readline() else ","
    frame = pd.read_csv(path, sep=separator)
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{relative} lacks required column(s): {', '.join(sorted(missing))}")
    return frame


def _arrow(values: list[float], digits: int = 0) -> str:
    return " → ".join(f"{value:,.{digits}f}" for value in values)


def load_report_values(root: Path | None = None) -> SimpleNamespace:
    """Return all headline values, recomputed from workflow outputs at render time."""
    root = find_project_root(root)
    qc = _read(root, "Filtering counts", {"callset", "preset", "snps"})
    pca = _read(root, "Structure", {"population", "PC1", "PC2"})
    pca_variance = _read(root, "PCA variance", {"PC", "pct_variance"})
    admixture = _read(root, "ADMIXTURE CV", {"K", "cv_error"})
    diversity = _read(root, "Modern diversity", {"population", "n", "He", "Fis"}).set_index("population")
    richness = _read(root, "Allelic richness", {"population", "rarefied_allelic_richness"}).set_index("population")
    temporal = _read(root, "Temporal diversity", {"population", "n", "Ho", "He"}).set_index("population")
    temporal_pi = _read(root, "Temporal pi", {"group", "median_pi"}).set_index("group")
    temporal_ar = _read(root, "Temporal allelic richness", {"population", "rarefied_allelic_richness"}).set_index("population")
    cube = _read(
        root,
        "Effective-size cube",
        {"filter_preset", "structure_mode", "population", "ne_point", "ci_low", "ci_high", "gbf_state"},
    )
    ne500 = _read(root, "GBF Ne indicator", {"filter_preset", "n_pops", "n_pass"})
    robustness = _read(root, "GBF robustness", {"population", "stable"})
    pm = _read(root, "Populations Maintained", {"country", "maintained_flag", "note"})
    gbf_summary = _read(root, "GBF summary", {"indicator", "value", "detail"}).set_index("indicator")
    gone = _read(root, "GONE2 context", {"generation", "Ne"}).sort_values("generation")
    wolf_load = _read(root, "Wolf load", {"IND", "POP", "THRES", "REALIZED_LOAD", "MASKED_LOAD"})
    wolf_roh = _read(root, "Wolf ROH", {"IND", "min_length_mb", "F_ROH"})
    wolf_validation = _read(root, "Wolf validation", {"check", "status", "detail"})
    _read(
        root,
        "Fragility scorecard",
        {"conclusion_id", "classification", "settings_supporting", "settings_tested", "evidence_needed"},
    )

    postmac = (
        qc.loc[qc["callset"].eq("setA_postMAC"), ["preset", "snps"]]
        .set_index("preset")["snps"]
    )
    preset_order = ["lenient", "standard", "strict"]
    absent_presets = set(preset_order).difference(postmac.index)
    if absent_presets:
        raise ValueError(f"filtering table lacks preset(s): {', '.join(sorted(absent_presets))}")

    centroids = pca.groupby("population")[["PC1", "PC2"]].mean()
    within = pca.groupby("population").apply(
        lambda frame: np.sqrt(
            ((frame[["PC1", "PC2"]] - frame[["PC1", "PC2"]].mean()) ** 2).sum(axis=1)
        ).mean(),
        include_groups=False,
    )
    populations = centroids.index.tolist()
    gaps = [
        float(np.hypot(*(centroids.loc[left] - centroids.loc[right]).values))
        for i, left in enumerate(populations)
        for right in populations[i + 1 :]
    ]

    lenient = cube.loc[
        cube["filter_preset"].eq("lenient") & cube["structure_mode"].eq("per_population")
    ].set_index("population")
    pooled = cube.loc[cube["structure_mode"].eq("pooled")].set_index("filter_preset")

    def ne_interval(population: str) -> str:
        row = lenient.loc[population]
        return f"{row['ne_point']:,.0f} [{row['ci_low']:,.0f}–{row['ci_high']:,.0f}]"

    stable = robustness["stable"].astype(str).str.lower().eq("true")
    ne_ratios = ne500["n_pass"] / ne500["n_pops"]
    best_ne = ne500.loc[ne_ratios.idxmax()]
    pm_flags = pm["maintained_flag"].astype(str).str.strip().str.lower()
    pm_total = len(pm_flags)
    pm_yes = int(pm_flags.eq("yes").sum())
    pm_swing = int(pm_flags.eq("swing").sum())
    pm_value = pm_yes / pm_total
    pm_detail = (
        f"{pm_value:.2f} ({pm_yes}/{pm_total} range units maintained; "
        + (f"{pm_swing} unresolved swing case(s))" if pm_swing else "no unresolved swing cases)")
    )

    census_raw = str(gbf_summary.loc["census_n_mature", "value"])
    census_bounds = re.findall(r"\d+", census_raw)
    census_value = (
        "–".join(f"{int(bound):,}" for bound in census_bounds[:2])
        if len(census_bounds) >= 2
        else census_raw
    )
    nc_proxy = float(gbf_summary.loc["census_nc_proxy_threshold", "value"])
    cambodia_note = " ".join(pm.loc[pm["country"].eq("Cambodia"), "note"].astype(str))
    cambodia_count = re.search(r"~?([\d,]+)", cambodia_note)

    g4 = wolf_load.loc[wolf_load["THRES"].eq(4)]
    load_by_pop = g4.groupby("POP")[["REALIZED_LOAD", "MASKED_LOAD"]].mean()
    outbred_labels = [label for label in ("Finland", "Russia", "Immigrants") if label in load_by_pop.index]
    scandinavian = load_by_pop.drop(index=outbred_labels)
    outbred = load_by_pop.loc[outbred_labels]
    threshold_means = wolf_load.groupby("THRES")["REALIZED_LOAD"].mean().sort_index()
    roh_means = wolf_roh.groupby("min_length_mb")["F_ROH"].mean().sort_index()
    anchor_row = wolf_validation.loc[
        wolf_validation["check"].eq("GERP>4 reconciles with the deposit anchor")
    ]
    if len(anchor_row) != 1:
        raise ValueError("wolf validation lacks the unique deposit-anchor reconciliation row")
    anchor_detail = str(anchor_row.iloc[0]["detail"])
    anchor_error_match = re.search(r"= ([0-9.eE+-]+) over (\d+) inds", anchor_detail)
    anchor_delta_match = re.search(r"max = (\d+)/(\d+)/(\d+)", anchor_detail)
    if not anchor_error_match or not anchor_delta_match:
        raise ValueError(f"cannot parse wolf anchor validation detail: {anchor_detail}")

    provenance = pd.DataFrame(
        [{"Result block": label, "Workflow output": path} for label, path in SOURCE_FILES.items()]
    )

    return SimpleNamespace(
        project_root=root,
        provenance=provenance,
        peafowl_n=int(diversity["n"].sum()),
        population_n=", ".join(f"{pop} (n = {int(diversity.loc[pop, 'n'])})" for pop in ("Yunnan", "Vietnam", "Thailand")),
        population_n_compact="/".join(str(int(diversity.loc[pop, "n"])) for pop in ("Yunnan", "Vietnam", "Thailand")),
        museum_n=int(temporal.loc["museum", "n"]),
        modern_temporal_n=int(temporal.loc["modern", "n"]),
        wolf_n=int(wolf_load["IND"].nunique()),
        postmac_counts=" / ".join(f"{int(postmac[preset]):,}" for preset in preset_order),
        filter_spread=int(round(postmac["lenient"] / postmac["strict"])),
        pca_gap=min(gaps),
        pca_within=max(within),
        pc1_variance=float(pca_variance.set_index("PC").loc["PC1", "pct_variance"]),
        admixture_best_k=int(admixture.groupby("K")["cv_error"].mean().idxmin()),
        thailand_he=float(diversity.loc["Thailand", "He"]),
        thailand_ar=float(richness.loc["Thailand", "rarefied_allelic_richness"]),
        yunnan_fis=float(diversity.loc["Yunnan", "Fis"]),
        museum_pi=float(temporal_pi.loc["museum", "median_pi"]),
        modern_pi=float(temporal_pi.loc["modern", "median_pi"]),
        museum_ho=float(temporal.loc["museum", "Ho"]),
        modern_ho=float(temporal.loc["modern", "Ho"]),
        museum_he=float(temporal.loc["museum", "He"]),
        modern_he=float(temporal.loc["modern", "He"]),
        museum_ar=float(temporal_ar.loc["museum", "rarefied_allelic_richness"]),
        modern_ar=float(temporal_ar.loc["modern", "rarefied_allelic_richness"]),
        ne_pass_by_preset=" / ".join(
            f"{int(ne500.set_index('filter_preset').loc[preset, 'n_pass'])}/{int(ne500.set_index('filter_preset').loc[preset, 'n_pops'])}"
            for preset in preset_order
        ),
        ne_headline=f"{int(best_ne['n_pass'])}/{int(best_ne['n_pops'])}",
        ne_yunnan=ne_interval("Yunnan"),
        ne_thailand=ne_interval("Thailand"),
        ne_vietnam=ne_interval("Vietnam"),
        pooled_ne=_arrow([float(pooled.loc[preset, "ne_point"]) for preset in preset_order]),
        unstable_population_count=int((~stable).sum()),
        population_count=len(stable),
        gone_old=float(gone.iloc[-1]["Ne"]),
        gone_recent=float(gone.iloc[0]["Ne"]),
        gone_generations=int(gone.iloc[-1]["generation"] - gone.iloc[0]["generation"]),
        pm_detail=pm_detail,
        census_value=census_value,
        nc_proxy=nc_proxy,
        cambodia_count=cambodia_count.group(1) if cambodia_count else "not reported",
        anchor_relative_error=float(anchor_error_match.group(1)),
        anchor_n=int(anchor_error_match.group(2)),
        anchor_deltas="/".join(anchor_delta_match.groups()),
        scandinavian_realized_low=float(scandinavian["REALIZED_LOAD"].min()),
        scandinavian_realized_high=float(scandinavian["REALIZED_LOAD"].max()),
        scandinavian_masked_low=float(scandinavian["MASKED_LOAD"].min()),
        scandinavian_masked_high=float(scandinavian["MASKED_LOAD"].max()),
        outbred_realized_low=float(outbred["REALIZED_LOAD"].min()),
        outbred_realized_high=float(outbred["REALIZED_LOAD"].max()),
        outbred_masked_low=float(outbred["MASKED_LOAD"].min()),
        outbred_masked_high=float(outbred["MASKED_LOAD"].max()),
        load_thresholds="/".join(f"{threshold:g}" for threshold in threshold_means.index),
        load_means=_arrow(threshold_means.tolist(), digits=3),
        roh_low_cutoff=float(roh_means.index.min()),
        roh_high_cutoff=float(roh_means.index.max()),
        roh_mean_low=float(roh_means.iloc[0]),
        roh_mean_high=float(roh_means.iloc[-1]),
    )


if __name__ == "__main__":
    values = load_report_values()
    print(f"report source check: OK ({len(values.provenance)} workflow outputs)")
    print(f"peafowl n={values.peafowl_n}; wolf n={values.wolf_n}; PM={values.pm_detail}")
