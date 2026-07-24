#!/usr/bin/env python3
"""Build the compact Phase-5B decision, traceability, and offline-data layer.

The core analyses retain their full row-level tables.  This script derives only
the cross-analysis claims and browser payload after all independent scientific
validators have passed.  It therefore cannot turn an exploratory pattern into
a claim by silently selecting a threshold or dropping an inconvenient row.
"""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[2]

DEFAULTS = {
    "wolf_associations": "results/tables/wolf_froh_load_associations.tsv",
    "wolf_rank": "results/tables/wolf_froh_load_rank_stability.tsv",
    "wolf_scores": "results/tables/wolf_froh_load_individual_scores.tsv",
    "wolf_figure_values": "results/tables/wolf_froh_load_figure_values.tsv",
    "wolf_validation": "results/tables/validation_wolf_robustness.tsv",
    "wolf_provenance": "results/provenance/wolf_froh_load.json",
    "localization_individual": "results/tables/wolf_roh_localization_individual.tsv",
    "localization_cohort": "results/tables/wolf_roh_localization_cohort.tsv",
    "localization_null": "results/tables/wolf_roh_localization_null.tsv",
    "localization_qc": "results/tables/wolf_roh_localization_qc.tsv",
    "localization_figure_values": "results/tables/wolf_roh_localization_figure_values.tsv",
    "localization_validation": "results/tables/validation_wolf_roh_localization.tsv",
    "localization_provenance": "results/provenance/wolf_roh_localization.json",
    "damage_effects": "results/tables/peafowl_damage_effects.tsv",
    "damage_permutations": "results/tables/peafowl_damage_permutations.tsv",
    "damage_influence": "results/tables/peafowl_damage_influence.tsv",
    "damage_blocks": "results/tables/peafowl_damage_blocks.tsv",
    "damage_classification": "results/tables/peafowl_damage_classification.tsv",
    "damage_figure_values": "results/tables/peafowl_damage_figure_values.tsv",
    "damage_validation": "results/tables/validation_peafowl_damage.tsv",
    "damage_provenance": "results/provenance/peafowl_damage.json",
    "ne_replicates": "results/tables/peafowl_ne_design_replicates.tsv",
    "ne_pilot": "results/tables/peafowl_ne_design_pilot.tsv",
    "ne_summary": "results/tables/peafowl_ne_design_summary.tsv",
    "ne_empirical": "results/tables/peafowl_ne_design_empirical.tsv",
    "ne_figure_values": "results/tables/peafowl_ne_design_figure_values.tsv",
    "ne_validation": "results/tables/validation_peafowl_ne_design.tsv",
    "ne_provenance": "results/provenance/peafowl_ne_design.json",
    "decisions": "results/tables/phase5b_optional_decisions.tsv",
    "inventory": "results/tables/phase5b_annotation_inventory.tsv",
    "decisions_validation": "results/tables/validation_phase5b_decisions.tsv",
    "decisions_provenance": "results/provenance/phase5b_optional_decisions.json",
    "config": "config/config.yaml",
}

TABLE_LABELS = {
    "wolf_associations": "Wolf association surface",
    "wolf_rank": "Wolf rank stability",
    "wolf_scores": "Wolf individual risk-proxy scores",
    "wolf_figure_values": "Wolf figure bridge",
    "wolf_validation": "Wolf robustness validation",
    "localization_individual": "Wolf ROH-localization individual results",
    "localization_cohort": "Wolf ROH-localization cohort results",
    "localization_null": "Wolf ROH-localization circular-shift null",
    "localization_qc": "Wolf ROH-localization chromosome QC",
    "localization_figure_values": "Wolf ROH-localization figure bridge",
    "localization_validation": "Wolf ROH-localization validation",
    "damage_effects": "Peafowl damage-aware effects",
    "damage_permutations": "Peafowl exact label permutations",
    "damage_influence": "Peafowl individual influence",
    "damage_blocks": "Peafowl chromosome blocks",
    "damage_classification": "Peafowl variant classification",
    "damage_figure_values": "Peafowl damage figure bridge",
    "damage_validation": "Peafowl damage validation",
    "ne_replicates": "Peafowl Ne scenario replicates",
    "ne_pilot": "Peafowl Ne repeated pilot",
    "ne_summary": "Peafowl Ne design summary",
    "ne_empirical": "Peafowl Ne empirical sensitivity",
    "ne_figure_values": "Peafowl Ne figure bridge",
    "ne_validation": "Peafowl Ne design validation",
    "decisions": "Optional-study decisions",
    "inventory": "Wolf annotation inventory",
    "decisions_validation": "Optional-study validation",
}

# TSV readers can coerce dotted section identifiers to floats and mixed
# threshold fields to strings.  Those columns are identifiers/expressions, not
# quantities, so the delivered dictionary records their semantic storage type.
DECLARED_STORAGE_DTYPES = {
    "claims": {"section": "str", "change_threshold": "object"},
    "scorecard": {"section": "str"},
}

COLUMN_DESCRIPTIONS = {
    "analysis_id": "Stable identifier for one analysis result.",
    "cell_id": "Stable identifier for a frozen parameter-grid cell.",
    "gerp_threshold": "GERP RS cutoff defining the wolf load subset.",
    "roh_cutoff_mb": "Minimum ROH length in megabases.",
    "outcome": "Outcome or decision category evaluated in the row.",
    "model": "Predeclared association model.",
    "coefficient": "Within-cohort rank association coefficient.",
    "ci_low": "Lower bound of the stated confidence interval.",
    "ci_high": "Upper bound of the stated confidence interval.",
    "ci_pct": "Confidence level in percent.",
    "bootstrap_reps": "Number of requested bootstrap replicates.",
    "permutation_reps": "Number of requested permutation replicates.",
    "permutation_p_two_sided": "Two-sided permutation p-value with plus-one correction.",
    "inside_eligible_genotype_calls": "Eligible polarized GERP-threshold SNP genotype calls inside the selected ROH intervals.",
    "outside_eligible_genotype_calls": "Eligible polarized GERP-threshold SNP genotype calls outside the selected ROH intervals.",
    "total_eligible_genotype_calls": "Inside plus outside eligible polarized GERP-threshold SNP genotype calls; an assayed-variant opportunity count, not callable genomic bases.",
    "all_polarized_gerp_genotype_calls": "Nonmissing diploid genotype calls at exact GERP-matched, validly polarized allSNPs records before applying a GERP threshold.",
    "phase4_genotype_call_delta": "Difference between the threshold-independent polarized GERP genotype-call count and the validated Phase-4 call total.",
    "inside_hom_del_sum": "GERP-weighted homozygous-derived burden inside the selected ROH intervals.",
    "outside_hom_del_sum": "GERP-weighted homozygous-derived burden outside the selected ROH intervals.",
    "inside_burden_rate": "Inside-ROH homozygous-derived burden per eligible polarized GERP-threshold SNP genotype call.",
    "outside_burden_rate": "Outside-ROH homozygous-derived burden per eligible polarized GERP-threshold SNP genotype call.",
    "rate_ratio": "Inside-ROH burden rate divided by the outside-ROH burden rate.",
    "log2_enrichment": "Base-2 logarithm of the inside/outside burden-per-eligible-genotype-call ratio.",
    "null_median_log2_enrichment": "Median log2 enrichment under within-chromosome circular ROH shifts.",
    "null_ci_low": "Lower percentile bound of the circular-shift null distribution.",
    "null_ci_high": "Upper percentile bound of the circular-shift null distribution.",
    "observed_minus_null_median": "Observed log2 enrichment minus the circular-shift null median.",
    "null_valid_reps": "Number of finite circular-shift null replicates in the cell.",
    "null_failed_reps": "Number of requested circular-shift null replicates that failed in the cell.",
    "variant_set": "All-SNP or damage-reduced transversion-only variant set.",
    "metric": "Diversity, estimator, or decision metric.",
    "effect_museum_minus_modern": "Museum value minus modern value on the metric scale.",
    "exact_permutation_p_two_sided": "Two-sided p-value from all 462 label allocations.",
    "direction": "Sign classification of the reported effect.",
    "geographic_mismatch_caveat": "Whether geography remains confounded with collection period.",
    "supports_temporal_erosion_upgrade": "Global design-aware claim-upgrade decision.",
    "true_ne": "Known simulated effective population size; absent for empirical rows.",
    "truth_class": "Known side of the Ne=500 boundary; unknown for empirical rows.",
    "sample_size": "Number of sampled diploid individuals.",
    "marker_density": "Number of input SNP markers requested from currentNe2.",
    "correct_confident_rate": "Fraction of attempts confidently on the correct side of Ne=500.",
    "incorrect_confident_rate": "Fraction of attempts confidently on the wrong side of Ne=500.",
    "boundary_confident_pass_rate": "For true Ne=500 only, fraction of attempts with a confident GBF pass; never scored correct or incorrect.",
    "boundary_confident_fail_rate": "For true Ne=500 only, fraction of attempts with a confident GBF fail; never scored correct or incorrect.",
    "indeterminate_rate": "Fraction of attempts whose interval cannot resolve the Ne=500 decision.",
    "execution_failure_rate": "Fraction of attempts with an execution or parsing failure.",
    "convergence_rate": "Fraction of all attempts yielding a converged estimator result.",
    "coverage_rate": (
        "Fraction of reported estimator intervals covering the known simulated truth, including "
        "unbounded intervals; n_unbounded_ci reports those intervals separately."
    ),
    "k": (
        "Estimated number of full-sibling counterparts for a randomly selected individual, "
        "as reported by currentNe2 for the chosen estimation basis."
    ),
    "n": (
        "Number of observations represented by the figure-value row: one for an individual "
        "point and the relevant sample size for an aggregate."
    ),
    "section": "CGplan section governed by the row.",
    "decision": "Gate outcome; negative and deferred outcomes are valid scientific results.",
    "observed_value": "Observed numeric gate value.",
    "required_operator": "Comparison operator in the predeclared gate.",
    "required_value": "Predeclared numeric threshold.",
    "reopen_condition": "Exact evidence condition that would reopen or change the decision.",
    "status": "PASS, WARN, or FAIL validator status.",
    "check": "Human-readable validation assertion.",
    "detail": "Machine-derived validation evidence.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for key, default in DEFAULTS.items():
        parser.add_argument("--" + key.replace("_", "-"), default=default)
    parser.add_argument("--out-claims", default="results/tables/phase5b_claim_trace.tsv")
    parser.add_argument("--out-scorecard", default="results/tables/phase5b_fragility_scorecard.tsv")
    parser.add_argument("--out-dictionary", default="results/tables/phase5b_data_dictionary.tsv")
    parser.add_argument("--out-dictionary-md", default="results/PHASE5B_DATA_DICTIONARY.md")
    parser.add_argument("--out-js", default="website/phase5b-data.js")
    parser.add_argument("--out-provenance", default="results/provenance/phase5b_synthesis.json")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def resolve(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validated_release_date(config: dict) -> str:
    """Return the frozen, canonical ISO date used by deterministic release assets."""
    phase5b = config.get("phase5b")
    if not isinstance(phase5b, dict):
        raise ValueError("config phase5b section must be a mapping")
    value = phase5b.get("release_date")
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("config phase5b.release_date must be a YYYY-MM-DD string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(
            "config phase5b.release_date must be a valid calendar date"
        ) from error
    if parsed.isoformat() != value:
        raise ValueError("config phase5b.release_date must be canonical YYYY-MM-DD")
    return value


def read_tsv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_csv(path, sep="\t")


def assert_validator_passes(frame: pd.DataFrame, label: str) -> None:
    if not {"status"}.issubset(frame.columns) or frame.empty:
        raise ValueError(f"{label} validator lacks non-empty status rows")
    statuses = frame["status"].astype(str).str.upper()
    unknown = sorted(set(statuses) - {"PASS", "WARN"})
    if unknown:
        raise ValueError(f"{label} validator is not clear: {unknown}")


def bool_series(series: pd.Series) -> pd.Series:
    return series.map(lambda value: value if isinstance(value, bool) else str(value).lower() == "true")


def fmt_number(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "not estimable"
    return f"{value:.{digits}f}"


def beyond_localization_null(frame: pd.DataFrame) -> pd.Series:
    """Apply the frozen, cellwise Section-13.4 evidence rule without row selection."""
    observed = pd.to_numeric(frame["log2_enrichment"], errors="coerce")
    null_high = pd.to_numeric(frame["null_ci_high"], errors="coerce")
    p_value = pd.to_numeric(frame["permutation_p_two_sided"], errors="coerce")
    return observed.gt(null_high) & p_value.le(0.05)


def build_claims(tables: dict[str, pd.DataFrame], config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    wolf = tables["wolf_associations"].copy()
    required_wolf = {"model", "outcome", "coefficient", "ci_low", "ci_high"}
    if required_wolf - set(wolf.columns) or len(wolf) != 60:
        raise ValueError("wolf association table is not the complete 60-row frozen grid")
    partial = wolf["model"].astype(str).str.contains("partial", case=False)
    realized = wolf["outcome"].astype(str).str.contains("realized", case=False)
    primary_realized = wolf.loc[~partial & realized]
    partial_realized = wolf.loc[partial & realized]
    if len(primary_realized) != 15 or len(partial_realized) != 15:
        raise ValueError("wolf primary/partial realized rows do not each cover 15 cells")
    primary_positive = int(pd.to_numeric(primary_realized["ci_low"]).gt(0).sum())
    partial_positive = int(pd.to_numeric(partial_realized["ci_low"]).gt(0).sum())
    wolf_gate = int(config["phase5b"]["wolf_robustness"]["roh_localization_reopen_min_cells"])

    damage = tables["damage_effects"].copy()
    if set(damage["metric"].astype(str)) != {"pi", "Ho", "He", "allelic_richness"} or len(damage) != 8:
        raise ValueError("damage effects must contain four metrics across two variant sets")
    robust_metrics = 0
    for _metric, group in damage.groupby("metric"):
        same_direction = bool_series(group["same_direction_all_snp_vs_transversion"]).all()
        museum_higher = group["direction"].astype(str).eq("museum_higher").all()
        equal_ok = (group["equal_n_same_direction_n"] == group["equal_n_cases_n"]).all()
        loo_ok = (group["leave_one_same_direction_n"] == group["leave_one_cases_n"]).all()
        robust_metrics += int(same_direction and museum_higher and equal_ok and loo_ok)
    damage_gate = int(config["phase5b"]["damage_falsification"]["upgrade_min_concordant_metrics"])
    damage_upgrade = bool_series(damage["supports_temporal_erosion_upgrade"]).all()
    damage_p_min = float(pd.to_numeric(damage["exact_permutation_p_two_sided"]).min())
    damage_p_max = float(pd.to_numeric(damage["exact_permutation_p_two_sided"]).max())

    ne = tables["ne_summary"].copy()
    scenario = ne.loc[ne["analysis_type"].astype(str).eq("scenario")].copy()
    empirical = ne.loc[ne["analysis_type"].astype(str).eq("empirical")].copy()
    expected_cells = (
        len(config["phase5b"]["ne_design"]["true_ne"])
        * len(config["phase5b"]["ne_design"]["sample_sizes"])
        * len(config["phase5b"]["ne_design"]["marker_densities"])
    )
    if len(scenario) != expected_cells or empirical.empty:
        raise ValueError(f"Ne summary does not contain {expected_cells} scenario cells plus empirical rows")
    resolution_truths = [float(value) for value in config["phase5b"]["ne_design"]["resolution_truths"]]
    correct_floor = float(config["phase5b"]["ne_design"]["resolution_min_correct_confident_ci_low"])
    incorrect_ceiling = float(config["phase5b"]["ne_design"]["resolution_max_incorrect_confident_ci_high"])
    resolution = scenario.loc[scenario["true_ne"].astype(float).isin(resolution_truths)].copy()
    resolution["meets_rate_bounds"] = (
        pd.to_numeric(resolution["correct_confident_ci_low"]).ge(correct_floor)
        & pd.to_numeric(resolution["incorrect_confident_ci_high"]).le(incorrect_ceiling)
    )
    design_rows = []
    for (sample_size, marker_density), group in resolution.groupby(["sample_size", "marker_density"]):
        covers_truths = set(group["true_ne"].astype(float)) == set(resolution_truths)
        design_rows.append(
            {
                "sample_size": int(sample_size),
                "marker_density": int(marker_density),
                "decision_resolving": bool(covers_truths and group["meets_rate_bounds"].all()),
            }
        )
    design = pd.DataFrame(design_rows)
    n_resolving = int(design["decision_resolving"].sum())
    min_resolving_n = (
        int(design.loc[design["decision_resolving"], "sample_size"].min()) if n_resolving else math.nan
    )

    localization = tables["localization_cohort"].copy()
    localization_required = {
        "POP", "gerp_threshold", "roh_cutoff_mb", "log2_enrichment",
        "null_ci_high", "permutation_p_two_sided", "status",
    }
    if localization_required - set(localization.columns):
        raise ValueError("ROH-localization cohort table lacks required observed/null columns")
    default_cutoff = float(config["wolf"]["roh"]["long_roh_threshold_mb"])
    if not math.isclose(default_cutoff, 1.5, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"predeclared long-ROH cutoff changed from 1.5 Mb to {default_cutoff:g} Mb")
    target_localization = localization.loc[
        np.isclose(pd.to_numeric(localization["roh_cutoff_mb"]), default_cutoff)
    ].copy()
    expected_thresholds = sorted(float(value) for value in config["wolf"]["load"]["gerp_sensitivity"])
    populations = sorted(target_localization["POP"].astype(str).unique())
    expected_localization_keys = {
        (population, threshold) for population in populations for threshold in expected_thresholds
    }
    actual_localization_keys = set(
        zip(
            target_localization["POP"].astype(str),
            pd.to_numeric(target_localization["gerp_threshold"]).astype(float),
            strict=False,
        )
    )
    if (
        len(populations) != 8
        or len(expected_thresholds) != 3
        or len(target_localization) != 24
        or actual_localization_keys != expected_localization_keys
    ):
        raise ValueError(
            "the predeclared 1.5-Mb ROH-localization slice is not the complete 8-population x 3-GERP grid"
        )
    localization_numeric = target_localization[
        ["log2_enrichment", "null_ci_high", "permutation_p_two_sided"]
    ].apply(pd.to_numeric, errors="coerce")
    if (
        not np.isfinite(localization_numeric.to_numpy(dtype=float)).all()
        or not target_localization["status"].astype(str).str.lower().eq("ok").all()
    ):
        raise ValueError("the predeclared 24-cell ROH-localization slice contains a failed or non-finite cell")
    target_localization["beyond_null"] = beyond_localization_null(target_localization)
    localization_support = int(target_localization["beyond_null"].sum())
    support_by_threshold = (
        target_localization.groupby("gerp_threshold", sort=True)["beyond_null"].sum().astype(int).to_dict()
    )
    support_detail = "; ".join(
        f"GERP>{float(threshold):g}: {support_by_threshold.get(threshold, 0)}/8"
        for threshold in expected_thresholds
    )
    localization_settings = config["phase5b"]["roh_localization"]

    decisions = tables["decisions"].copy()
    row_134 = decisions.loc[decisions["section"].astype(str).eq("13.4")].iloc[0]
    row_135 = decisions.loc[decisions["section"].astype(str).eq("13.5")].iloc[0]

    claims = [
        {
            "claim_id": "wolf_froh_load_association",
            "section": "13.1",
            "headline": (
                f"Within-cohort F_ROH–realized-load association has a CI above zero in "
                f"{primary_positive}/15 primary cells and {partial_positive}/15 cells after the "
                "generic-homozygosity control."
            ),
            "claim_status": "gerp_proxy_specific_support" if partial_positive >= wolf_gate else "proxy_coupling_not_excluded",
            "estimate": f"{partial_positive}/15 partial realized-load cells",
            "uncertainty": "95% cohort-stratified bootstrap intervals; 1,999 within-cohort permutations per outcome/cell",
            "result_table": DEFAULTS["wolf_associations"],
            "result_filter": "outcome=realized_load; compare model=primary vs partial_generic_homozygosity_control",
            "provenance": DEFAULTS["wolf_provenance"],
            "validator": DEFAULTS["wolf_validation"],
            "report_anchor": "report/report.html#wolf-individual-association",
            "explorer_anchor": "index.html#wolf-robustness",
            "workflow_rule": "workflow/rules/phase5b.smk#wolf_froh_load_robustness",
            "source_trace": "results/tables/wolf_load.tsv; results/tables/wolf_roh.tsv",
            "change_operator": ">=",
            "change_threshold": wolf_gate,
            "observed_value": partial_positive,
            "unit": "of 15 partial realized-load cells with CI low > 0",
            "what_changes_mind": f"At least {wolf_gate}/15 partial realized-load CIs entirely above zero.",
            "scientific_boundary": "Association among genomic proxies; no fitness, depression, or causal effect is measured.",
        },
        {
            "claim_id": "peafowl_damage_falsification",
            "section": "13.3",
            "headline": (
                f"{robust_metrics}/4 diversity metrics retain a museum-higher direction through every "
                "damage and individual-influence check; geographic mismatch still blocks a temporal-erosion claim."
            ),
            "claim_status": "temporal_erosion_upgrade" if damage_upgrade else "contrast_only",
            "estimate": f"{robust_metrics}/4 fully direction-concordant metrics",
            "uncertainty": f"95% 5-Mb chromosome-block bootstrap; exact label p-value range {damage_p_min:.4f}–{damage_p_max:.4f}",
            "result_table": DEFAULTS["damage_effects"],
            "result_filter": "all 4 metrics x all_snp/transversion_only",
            "provenance": DEFAULTS["damage_provenance"],
            "validator": DEFAULTS["damage_validation"],
            "report_anchor": "report/report.html#damage-aware-falsification",
            "explorer_anchor": "index.html#damage-falsification",
            "workflow_rule": "workflow/rules/phase5b.smk#peafowl_damage_falsification",
            "source_trace": "data/peafowl/raw/Comparative_genomic_dataset_F.vcf.gz",
            "change_operator": "==",
            "change_threshold": damage_gate,
            "observed_value": robust_metrics,
            "unit": "of 4 metrics concordant through every numerical stress test",
            "what_changes_mind": "4/4 metrics must pass every numerical stress test and time must be separated from geography by design.",
            "scientific_boundary": "Deposited groups differ in geography as well as period; diversity is not fitness.",
        },
        {
            "claim_id": "peafowl_ne_study_design",
            "section": "13.2",
            "headline": (
                f"{n_resolving}/{len(design)} simulated sample-size/marker designs meet the predeclared "
                "two-sided decision-resolution rule; empirical downsampling is reported separately."
            ),
            "claim_status": "scenario_landscape_not_guarantee",
            "estimate": (
                f"minimum qualifying simulated n={min_resolving_n}" if n_resolving else "no qualifying simulated design"
            ),
            "uncertainty": "95% Wilson intervals on replicate rates; currentNe2 90% estimator intervals retained per attempt",
            "result_table": DEFAULTS["ne_summary"],
            "result_filter": "scenario true_ne in {250,1000}; empirical rows remain truth=unknown",
            "provenance": DEFAULTS["ne_provenance"],
            "validator": DEFAULTS["ne_validation"],
            "report_anchor": "report/report.html#ne-sample-design-calibration",
            "explorer_anchor": "index.html#ne-design",
            "workflow_rule": "workflow/rules/phase5b.smk#peafowl_ne_design",
            "source_trace": "transparent Wright–Fisher scenarios; results/qc/setA.standard.vcf.gz",
            "change_operator": "bounds",
            "change_threshold": f"correct CI low >= {correct_floor:.2f}; incorrect CI high <= {incorrect_ceiling:.2f}",
            "observed_value": n_resolving,
            "unit": f"of {len(design)} design combinations resolving both true Ne=250 and 1,000",
            "what_changes_mind": (
                f"For both predeclared resolution truths (Ne=250 and 1,000), "
                f"correct-confident Wilson lower >= {correct_floor:.2f} and "
                f"incorrect-confident Wilson upper <= {incorrect_ceiling:.2f}."
            ),
            "scientific_boundary": "Neutral scenarios calibrate this pipeline; they cannot guarantee an exact real sampling outcome.",
        },
        {
            "claim_id": "wolf_roh_localization_gate",
            "section": "13.4",
            "headline": f"ROH-localized burden decision: {row_134['decision']}.",
            "claim_status": str(row_134["decision"]),
            "estimate": str(row_134["evidence"]),
            "uncertainty": "Gate inherits the 15 cohort-bootstrap intervals from Section 13.1.",
            "result_table": DEFAULTS["decisions"],
            "result_filter": "section=13.4",
            "provenance": DEFAULTS["decisions_provenance"],
            "validator": DEFAULTS["decisions_validation"],
            "report_anchor": "report/report.html#optional-study-decisions",
            "explorer_anchor": "index.html#decision-boundaries",
            "workflow_rule": "workflow/rules/phase5b.smk#phase5b_optional_decisions",
            "source_trace": str(row_134["source_trace"]),
            "change_operator": str(row_134["required_operator"]),
            "change_threshold": row_134["required_value"],
            "observed_value": row_134["observed_value"],
            "unit": str(row_134["unit"]),
            "what_changes_mind": str(row_134["reopen_condition"]),
            "scientific_boundary": str(row_134["scientific_boundary"]),
        },
        {
            "claim_id": "wolf_roh_localized_realized_burden",
            "section": "13.4",
            "headline": (
                f"At the predeclared 1.5 Mb cutoff, observed realized-burden enrichment exceeds "
                f"the circular-shift null upper bound with two-sided permutation p <= 0.05 in "
                f"{localization_support}/24 population-by-GERP cells."
            ),
            "claim_status": "cellwise_beyond_null_summary",
            "estimate": f"{localization_support}/24 cells ({support_detail})",
            "uncertainty": (
                f"{float(localization_settings['ci_pct']):g}% interval from "
                f"{int(localization_settings['permutation_reps'])} within-chromosome circular-shift "
                "replicates per cell; two-sided plus-one permutation p-values."
            ),
            "result_table": DEFAULTS["localization_cohort"],
            "result_filter": (
                "roh_cutoff_mb=1.5; each of 8 populations x GERP>{2,3,4} counted only when "
                "log2_enrichment>null_ci_high and permutation_p_two_sided<=0.05"
            ),
            "provenance": DEFAULTS["localization_provenance"],
            "validator": DEFAULTS["localization_validation"],
            "report_anchor": "report/report.html#wolf-roh-localization",
            "explorer_anchor": "index.html#wolf-roh-localization",
            "workflow_rule": "workflow/rules/phase5b.smk#wolf_roh_localization_collate",
            "source_trace": (
                "results/tables/wolf_roh_localization_individual.tsv; "
                "results/wolf/localization/chr*.observed.tsv; results/wolf/localization/chr*.null.tsv"
            ),
            "change_operator": "cell_rule",
            "change_threshold": "log2 enrichment > null 95% upper bound and two-sided p <= 0.05",
            "observed_value": localization_support,
            "unit": "of 24 predeclared population-by-GERP cells beyond the circular-shift null",
            "what_changes_mind": (
                "A cell changes classification only if its observed log2 enrichment crosses the "
                "circular-shift upper bound or its two-sided permutation p-value crosses 0.05."
            ),
            "scientific_boundary": (
                "This spatial co-localization of genomic proxies provides mechanistic support, not "
                "a demonstrated biological mechanism. The denominator is eligible calls at assayed "
                "SNP records rather than callable genomic bases, so ascertainment remains. It is "
                "not fitness evidence, not evidence of phenotypic consequences, and not causal evidence."
            ),
        },
        {
            "claim_id": "wolf_annotation_triangulation_gate",
            "section": "13.5",
            "headline": f"Independent annotation triangulation decision: {row_135['decision']}.",
            "claim_status": str(row_135["decision"]),
            "estimate": str(row_135["evidence"]),
            "uncertainty": "Exact deposited class inventory and common-sample coverage, not an estimated effect.",
            "result_table": DEFAULTS["decisions"],
            "result_filter": "section=13.5",
            "provenance": DEFAULTS["decisions_provenance"],
            "validator": DEFAULTS["decisions_validation"],
            "report_anchor": "report/report.html#optional-study-decisions",
            "explorer_anchor": "index.html#decision-boundaries",
            "workflow_rule": "workflow/rules/phase5b.smk#phase5b_optional_decisions",
            "source_trace": str(row_135["source_trace"]),
            "change_operator": str(row_135["required_operator"]),
            "change_threshold": row_135["required_value"],
            "observed_value": row_135["observed_value"],
            "unit": str(row_135["unit"]),
            "what_changes_mind": str(row_135["reopen_condition"]),
            "scientific_boundary": str(row_135["scientific_boundary"]),
        },
    ]
    localization_claim = next(
        claim for claim in claims if claim["claim_id"] == "wolf_roh_localized_realized_burden"
    )
    claim_frame = pd.DataFrame(claims)

    scorecard = pd.DataFrame(
        [
            {
                "conclusion_id": "wolf_individual_association",
                "section": "13.1",
                "classification": "negative-control-sensitive" if partial_positive < wolf_gate else "robust_association",
                "conclusion": claims[0]["headline"],
                "settings_supporting": partial_positive,
                "settings_tested": 15,
                "dominant_uncertainty": "generic mathematical coupling with homozygosity",
                "evidence_needed": claims[0]["what_changes_mind"],
                "machine_result": DEFAULTS["wolf_associations"],
            },
            {
                "conclusion_id": "peafowl_damage_aware_temporal",
                "section": "13.3",
                "classification": "design-limited" if not damage_upgrade else "robust_direction",
                "conclusion": claims[1]["headline"],
                "settings_supporting": robust_metrics,
                "settings_tested": 4,
                "dominant_uncertainty": "collection period is confounded with geography",
                "evidence_needed": claims[1]["what_changes_mind"],
                "machine_result": DEFAULTS["damage_effects"],
            },
            {
                "conclusion_id": "peafowl_ne_design_resolution",
                "section": "13.2",
                "classification": "scenario-calibrated",
                "conclusion": claims[2]["headline"],
                "settings_supporting": n_resolving,
                "settings_tested": len(design),
                "dominant_uncertainty": "simplified neutral scenarios and small Monte-Carlo replicate count",
                "evidence_needed": claims[2]["what_changes_mind"],
                "machine_result": DEFAULTS["ne_summary"],
            },
            {
                "conclusion_id": "wolf_roh_localized_realized_burden",
                "section": "13.4",
                "classification": (
                    "grid_wide_beyond_null" if localization_support == 24
                    else "null_compatible" if localization_support == 0
                    else "population_threshold_heterogeneous"
                ),
                "conclusion": localization_claim["headline"],
                "settings_supporting": localization_support,
                "settings_tested": 24,
                "dominant_uncertainty": (
                    f"within-chromosome circular-shift placement null with "
                    f"{int(localization_settings['permutation_reps'])} replicates per cell"
                ),
                "evidence_needed": localization_claim["what_changes_mind"],
                "machine_result": DEFAULTS["localization_cohort"],
            },
        ]
    )
    return claim_frame, scorecard


def plain_description(column: str) -> str:
    if column in COLUMN_DESCRIPTIONS:
        return COLUMN_DESCRIPTIONS[column]
    text = re.sub(r"_+", " ", column).strip()
    return text[:1].upper() + text[1:] + "."


def dictionary_storage_dtype(key: str, column: str, values: pd.Series) -> str:
    return DECLARED_STORAGE_DTYPES.get(key, {}).get(column, str(values.dtype))


def build_dictionary(paths: dict[str, Path]) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for key in TABLE_LABELS:
        frame = read_tsv(paths[key])
        for position, column in enumerate(frame.columns, start=1):
            records.append(
                {
                    "table": relative(paths[key]),
                    "table_label": TABLE_LABELS[key],
                    "column_position": position,
                    "column": column,
                    "storage_dtype": dictionary_storage_dtype(key, column, frame[column]),
                    "non_missing_rows": int(frame[column].notna().sum()),
                    "total_rows": len(frame),
                    "description": plain_description(column),
                }
            )
    return pd.DataFrame(records)


def json_records(frame: pd.DataFrame) -> list[dict[str, object]]:
    clean = frame.astype(object).where(pd.notna(frame), None)
    records = clean.to_dict(orient="records")
    for record in records:
        for key, value in list(record.items()):
            if isinstance(value, np.generic):
                record[key] = value.item()
            elif isinstance(value, float) and not math.isfinite(value):
                record[key] = None
    return records


def write_dictionary_md(frame: pd.DataFrame, path: Path) -> None:
    lines = [
        "# Phase 5B data dictionary",
        "",
        "Generated from the final workflow tables. Row counts and storage types therefore describe the delivered artifacts, not a hand-maintained schema draft.",
        "",
    ]
    for table, group in frame.groupby("table", sort=False):
        lines.extend([f"## `{table}`", "", f"{int(group['total_rows'].iloc[0]):,} rows.", "", "| column | type | complete | definition |", "|---|---|---:|---|"])
        for row in group.itertuples(index=False):
            description = str(row.description).replace("|", "\\|")
            lines.append(f"| `{row.column}` | `{row.storage_dtype}` | {row.non_missing_rows}/{row.total_rows} | {description} |")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def self_test() -> None:
    assert validated_release_date(
        {"phase5b": {"release_date": "2026-07-19"}}
    ) == "2026-07-19"
    for invalid in (
        "2026-7-19",
        "2026-02-30",
        "19-07-2026",
        "",
        None,
        date(2026, 7, 19),
    ):
        try:
            validated_release_date({"phase5b": {"release_date": invalid}})
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid release date was accepted: {invalid!r}")
    for invalid_config in ({}, {"phase5b": None}, {"phase5b": {}}):
        try:
            validated_release_date(invalid_config)
        except ValueError:
            pass
        else:
            raise AssertionError(
                f"missing release date was accepted: {invalid_config!r}"
            )
    assert fmt_number(math.nan) == "not estimable"
    assert plain_description("ci_low").startswith("Lower")
    assert "full-sibling" in plain_description("k").lower()
    assert "observations represented" in plain_description("n").lower()
    assert dictionary_storage_dtype("claims", "section", pd.Series([13.1])) == "str"
    assert dictionary_storage_dtype(
        "claims", "change_threshold", pd.Series(["12", "cell rule"])
    ) == "object"
    assert dictionary_storage_dtype("scorecard", "section", pd.Series([13.1])) == "str"
    with TemporaryDirectory() as temp_dir:
        delivered_path = Path(temp_dir) / "claim_like.tsv"
        in_memory = pd.DataFrame(
            {
                "section": ["13.1", "13.4"],
                "change_threshold": [12, "cell rule"],
            }
        )
        in_memory.to_csv(delivered_path, sep="\t", index=False, lineterminator="\n")
        dictionary = build_dictionary({key: delivered_path for key in TABLE_LABELS})
        dictionary_slice = dictionary.loc[
            dictionary["table_label"].eq(TABLE_LABELS["wolf_associations"])
        ].set_index("column")
        delivered = read_tsv(delivered_path)
        expected_dtypes = delivered.dtypes.astype(str).to_dict()
        actual_dtypes = dictionary_slice["storage_dtype"].astype(str).to_dict()
        assert actual_dtypes == expected_dtypes, (actual_dtypes, expected_dtypes)
    small = pd.DataFrame({"a": [1.0, math.nan], "b": [True, False]})
    encoded = json.dumps(json_records(small), allow_nan=False)
    assert "NaN" not in encoded and "null" in encoded
    localization = pd.DataFrame(
        {
            "log2_enrichment": [1.1, 1.0, 1.1],
            "null_ci_high": [1.0, 1.0, 1.0],
            "permutation_p_two_sided": [0.05, 0.01, 0.051],
        }
    )
    assert beyond_localization_null(localization).tolist() == [True, False, False]
    print("phase5b_synthesis self-test: OK")


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return

    paths = {key: resolve(getattr(args, key)) for key in DEFAULTS}
    table_keys = list(TABLE_LABELS)
    tables = {key: read_tsv(paths[key]) for key in table_keys}
    for key in (
        "wolf_validation", "damage_validation", "ne_validation",
        "decisions_validation", "localization_validation",
    ):
        assert_validator_passes(tables[key], TABLE_LABELS[key])
    config = yaml.safe_load(paths["config"].read_text(encoding="utf-8"))
    frozen_release_date = validated_release_date(config)

    claims, scorecard = build_claims(tables, config)
    out_claims = resolve(args.out_claims)
    out_scorecard = resolve(args.out_scorecard)
    out_dictionary = resolve(args.out_dictionary)
    out_dictionary_md = resolve(args.out_dictionary_md)
    out_js = resolve(args.out_js)
    out_provenance = resolve(args.out_provenance)
    for path in (out_claims, out_scorecard, out_dictionary, out_dictionary_md, out_js, out_provenance):
        path.parent.mkdir(parents=True, exist_ok=True)
    claims.to_csv(out_claims, sep="\t", index=False, lineterminator="\n")
    scorecard.to_csv(out_scorecard, sep="\t", index=False, lineterminator="\n")

    paths_with_synthesis = dict(paths)
    paths_with_synthesis["claims"] = out_claims
    paths_with_synthesis["scorecard"] = out_scorecard
    labels_backup = dict(TABLE_LABELS)
    TABLE_LABELS["claims"] = "Phase 5B claim trace"
    TABLE_LABELS["scorecard"] = "Phase 5B fragility scorecard"
    dictionary = build_dictionary(paths_with_synthesis)
    TABLE_LABELS.clear()
    TABLE_LABELS.update(labels_backup)
    dictionary.to_csv(out_dictionary, sep="\t", index=False, lineterminator="\n")
    write_dictionary_md(dictionary, out_dictionary_md)

    wolf_payload = tables["wolf_associations"].loc[:, [
        "cell_id", "gerp_threshold", "roh_cutoff_mb", "outcome", "model",
        "coefficient", "ci_low", "ci_high", "permutation_p_two_sided",
    ]]
    damage_payload = tables["damage_effects"]
    localization_payload_columns = [
        "POP", "gerp_threshold", "roh_cutoff_mb", "n_ind", "inside_eligible_genotype_calls",
        "outside_eligible_genotype_calls", "log2_enrichment",
        "null_median_log2_enrichment", "null_ci_low", "null_ci_high",
        "observed_minus_null_median", "permutation_p_two_sided", "direction", "status",
    ]
    localization_payload = tables["localization_cohort"][localization_payload_columns].copy()
    localization_payload["beyond_null"] = beyond_localization_null(localization_payload)
    ne_columns = [
        "analysis_type", "population", "true_ne", "truth_class", "sample_size",
        "marker_density", "n_attempted", "convergence_rate", "correct_confident_rate",
        "correct_confident_ci_low", "correct_confident_ci_high", "incorrect_confident_rate",
        "incorrect_confident_ci_low", "incorrect_confident_ci_high", "indeterminate_rate",
        "boundary_confident_pass_rate", "boundary_confident_fail_rate",
        "pass_rate", "fail_rate", "execution_failure_rate", "median_ci_width",
    ]
    payload = {
        "schemaVersion": "phase5b-browser-v1",
        "generatedDate": frozen_release_date,
        "wolfAssociations": json_records(wolf_payload),
        "wolfLocalization": json_records(localization_payload),
        "damageEffects": json_records(damage_payload),
        "neDesign": json_records(tables["ne_summary"][ne_columns]),
        "claims": json_records(claims),
        "optionalDecisions": json_records(tables["decisions"]),
    }
    out_js.write_text(
        "/* Generated by scripts/python/phase5b_synthesis.py; do not edit by hand. */\n"
        "window.PHASE5B_DATA = " + json.dumps(payload, separators=(",", ":"), allow_nan=False) + ";\n",
        encoding="utf-8",
    )

    provenance_inputs = {key: {"path": relative(path), "sha256": sha256_file(path)} for key, path in paths.items()}
    outputs = [out_claims, out_scorecard, out_dictionary, out_dictionary_md, out_js]
    provenance = {
        "schema_version": "phase5b-synthesis-v1",
        "analysis": "Phase 5B decision and offline traceability synthesis",
        "claim_count": len(claims),
        "scorecard_rows": len(scorecard),
        "data_dictionary_rows": len(dictionary),
        "browser_payload_counts": {key: len(value) for key, value in payload.items() if isinstance(value, list)},
        "inputs": provenance_inputs,
        "outputs": {relative(path): sha256_file(path) for path in outputs},
        "boundary": "Synthesis only; it does not recompute, select, or upgrade core scientific results.",
    }
    out_provenance.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Phase 5B synthesis: {len(claims)} claims, {len(scorecard)} scorecard rows, {len(dictionary)} dictionary rows")


if __name__ == "__main__":
    main()
