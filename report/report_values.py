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
    "Wolf individual association": "results/tables/wolf_froh_load_associations.tsv",
    "Wolf rank stability": "results/tables/wolf_froh_load_rank_stability.tsv",
    "Damage-aware effects": "results/tables/peafowl_damage_effects.tsv",
    "Ne design summary": "results/tables/peafowl_ne_design_summary.tsv",
    "Wolf ROH localization": "results/tables/wolf_roh_localization_cohort.tsv",
    "Wolf ROH localization validation": "results/tables/validation_wolf_roh_localization.tsv",
    "Phase 5B decisions": "results/tables/phase5b_optional_decisions.tsv",
    "Phase 5B claim trace": "results/tables/phase5b_claim_trace.tsv",
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
    wolf_associations = _read(
        root,
        "Wolf individual association",
        {"gerp_threshold", "roh_cutoff_mb", "outcome", "model", "coefficient", "ci_low", "ci_high"},
    )
    wolf_rank_stability = _read(
        root,
        "Wolf rank stability",
        {"spearman_rho", "kendall_tau", "top_percentile", "top_overlap_fraction"},
    )
    damage_effects = _read(
        root,
        "Damage-aware effects",
        {
            "variant_set", "metric", "effect_museum_minus_modern", "ci_low", "ci_high",
            "exact_permutation_p_two_sided", "direction", "equal_n_same_direction_n",
            "equal_n_cases_n", "leave_one_same_direction_n", "leave_one_cases_n",
            "same_direction_all_snp_vs_transversion", "supports_temporal_erosion_upgrade",
        },
    )
    ne_design = _read(
        root,
        "Ne design summary",
        {
            "analysis_type", "true_ne", "sample_size", "marker_density", "n_attempted",
            "correct_confident_rate", "correct_confident_ci_low",
            "incorrect_confident_rate", "incorrect_confident_ci_high", "indeterminate_rate",
            "boundary_confident_pass_rate", "boundary_confident_fail_rate",
        },
    )
    roh_localization = _read(
        root,
        "Wolf ROH localization",
        {
            "POP", "gerp_threshold", "roh_cutoff_mb", "n_ind",
            "inside_eligible_genotype_calls", "outside_eligible_genotype_calls", "inside_burden_rate",
            "outside_burden_rate", "log2_enrichment", "null_ci_low", "null_ci_high",
            "permutation_p_two_sided", "status",
        },
    )
    roh_localization_validation = _read(
        root, "Wolf ROH localization validation", {"check", "status", "detail"}
    )
    if not roh_localization_validation["status"].astype(str).eq("PASS").all():
        raise ValueError("wolf ROH-localization validator is not all PASS")
    phase5b_decisions = _read(
        root,
        "Phase 5B decisions",
        {"section", "decision", "observed_value", "required_value", "evidence", "reopen_condition"},
    )
    phase5b_claims = _read(
        root,
        "Phase 5B claim trace",
        {"claim_id", "headline", "claim_status", "estimate", "uncertainty", "what_changes_mind"},
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

    wolf_partial_realized = wolf_associations.loc[
        wolf_associations["outcome"].astype(str).eq("realized_load")
        & wolf_associations["model"].astype(str).str.contains("partial")
    ]
    wolf_primary_realized = wolf_associations.loc[
        wolf_associations["outcome"].astype(str).eq("realized_load")
        & wolf_associations["model"].astype(str).eq("primary")
    ]
    wolf_partial_masked = wolf_associations.loc[
        wolf_associations["outcome"].astype(str).eq("masked_load")
        & wolf_associations["model"].astype(str).str.contains("partial")
    ]
    if not all(len(frame) == 15 for frame in (wolf_partial_realized, wolf_primary_realized, wolf_partial_masked)):
        raise ValueError("wolf Phase-5B association subsets do not each cover the frozen 15-cell grid")

    damage_concordant = 0
    for _metric, group in damage_effects.groupby("metric"):
        values = group["same_direction_all_snp_vs_transversion"].astype(str).str.lower().eq("true")
        museum_higher = group["direction"].astype(str).eq("museum_higher").all()
        equal_ok = (group["equal_n_same_direction_n"] == group["equal_n_cases_n"]).all()
        leave_ok = (group["leave_one_same_direction_n"] == group["leave_one_cases_n"]).all()
        damage_concordant += int(values.all() and museum_higher and equal_ok and leave_ok)

    localization_primary = roh_localization.loc[
        np.isclose(pd.to_numeric(roh_localization["roh_cutoff_mb"]), 1.5)
    ].copy()
    localization_primary["beyond_null"] = (
        pd.to_numeric(localization_primary["log2_enrichment"])
        > pd.to_numeric(localization_primary["null_ci_high"])
    ) & pd.to_numeric(localization_primary["permutation_p_two_sided"]).le(0.05)
    if (
        len(roh_localization) != 120
        or len(localization_primary) != 24
        or roh_localization.groupby(["POP", "gerp_threshold", "roh_cutoff_mb"]).size().ne(1).any()
        or not localization_primary["status"].astype(str).eq("ok").all()
    ):
        raise ValueError("wolf ROH-localization table lacks the complete 8 x 3 x 5 grid or primary slice")
    localization_support = int(localization_primary["beyond_null"].sum())
    localization_by_threshold = ", ".join(
        f"GERP>{threshold:g}: {int(group['beyond_null'].sum())}/8"
        for threshold, group in localization_primary.groupby("gerp_threshold", sort=True)
    )

    claims_by_id = phase5b_claims.set_index("claim_id")
    required_claim_ids = {
        "wolf_froh_load_association", "peafowl_damage_falsification", "peafowl_ne_study_design",
        "wolf_roh_localization_gate", "wolf_roh_localized_realized_burden",
        "wolf_annotation_triangulation_gate",
    }
    if required_claim_ids - set(claims_by_id.index):
        raise ValueError("Phase-5B claim trace lacks one or more required headline claims")
    decisions_by_section = phase5b_decisions.assign(
        section=phase5b_decisions["section"].astype(str)
    ).set_index("section")

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
        wolf_primary_realized_low=float(wolf_primary_realized["coefficient"].min()),
        wolf_primary_realized_high=float(wolf_primary_realized["coefficient"].max()),
        wolf_partial_realized_low=float(wolf_partial_realized["coefficient"].min()),
        wolf_partial_realized_high=float(wolf_partial_realized["coefficient"].max()),
        wolf_partial_realized_ci_positive=int(wolf_partial_realized["ci_low"].gt(0).sum()),
        wolf_partial_masked_ci_excluding_zero=int(
            (wolf_partial_masked["ci_low"].gt(0) | wolf_partial_masked["ci_high"].lt(0)).sum()
        ),
        wolf_rank_spearman_low=float(wolf_rank_stability["spearman_rho"].min()),
        wolf_rank_spearman_high=float(wolf_rank_stability["spearman_rho"].max()),
        wolf_rank_overlap_low=float(wolf_rank_stability["top_overlap_fraction"].min()),
        damage_concordant_metrics=damage_concordant,
        damage_exact_p_low=float(damage_effects["exact_permutation_p_two_sided"].min()),
        damage_exact_p_high=float(damage_effects["exact_permutation_p_two_sided"].max()),
        damage_effects=damage_effects.sort_values(["metric", "variant_set"]),
        roh_localization_primary=localization_primary.sort_values(["gerp_threshold", "POP"]),
        roh_localization_support_cells=localization_support,
        roh_localization_support_by_threshold=localization_by_threshold,
        roh_localization_log2_low=float(localization_primary["log2_enrichment"].min()),
        roh_localization_log2_high=float(localization_primary["log2_enrichment"].max()),
        roh_localization_p_low=float(localization_primary["permutation_p_two_sided"].min()),
        roh_localization_p_high=float(localization_primary["permutation_p_two_sided"].max()),
        roh_localization_claim=str(claims_by_id.loc["wolf_roh_localized_realized_burden", "headline"]),
        ne_design_summary=ne_design,
        ne_design_claim=str(claims_by_id.loc["peafowl_ne_study_design", "headline"]),
        ne_design_estimate=str(claims_by_id.loc["peafowl_ne_study_design", "estimate"]),
        wolf_claim=str(claims_by_id.loc["wolf_froh_load_association", "headline"]),
        damage_claim=str(claims_by_id.loc["peafowl_damage_falsification", "headline"]),
        section134_decision=str(decisions_by_section.loc["13.4", "decision"]),
        section134_evidence=str(decisions_by_section.loc["13.4", "evidence"]),
        section135_decision=str(decisions_by_section.loc["13.5", "decision"]),
        section135_evidence=str(decisions_by_section.loc["13.5", "evidence"]),
        phase5b_claims=phase5b_claims,
    )


if __name__ == "__main__":
    values = load_report_values()
    print(f"report source check: OK ({len(values.provenance)} workflow outputs)")
    print(f"peafowl n={values.peafowl_n}; wolf n={values.wolf_n}; PM={values.pm_detail}")
