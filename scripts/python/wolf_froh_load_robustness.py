#!/usr/bin/env python3
"""Phase-5B wolf individual F_ROH-load robustness surface.

The analysis joins the validated Phase-4 wolf load and ROH summaries, evaluates
the frozen 3 x 5 threshold grid, and keeps inference at the level supported by
the data: associations among genomic risk proxies. It does not estimate fitness,
inbreeding depression, or causation.

Outputs are deterministic for the seeds in config/config.yaml. Heavy wolf VCFs
are not reopened; the generic-homozygosity negative control is derived from the
threshold-independent polarized counts already present in wolf_load.tsv.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import platform
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy import stats
import yaml


EXPECTED_N = 211
ASSOCIATION_COLUMNS = [
    "analysis_id",
    "cell_id",
    "gerp_threshold",
    "roh_cutoff_mb",
    "outcome",
    "model",
    "n_ind",
    "n_pop",
    "coefficient",
    "ci_low",
    "ci_high",
    "ci_pct",
    "permutation_p_two_sided",
    "expected_direction",
    "direction_matches_expected",
    "bootstrap_reps",
    "bootstrap_valid",
    "bootstrap_failed",
    "permutation_reps",
    "permutation_valid",
    "permutation_failed",
    "bootstrap_seed",
    "permutation_seed",
    "negative_control",
]

STABILITY_COLUMNS = [
    "pair_id",
    "cell_a_id",
    "cell_b_id",
    "gerp_a",
    "roh_a_mb",
    "gerp_b",
    "roh_b_mb",
    "n_ind",
    "spearman_rho",
    "spearman_p",
    "kendall_tau",
    "kendall_p",
    "top_percentile",
    "top_n",
    "top_overlap_n",
    "top_overlap_fraction",
    "top_jaccard",
]

INDIVIDUAL_COLUMNS = [
    "cell_id",
    "gerp_threshold",
    "roh_cutoff_mb",
    "IND",
    "POP",
    "F_ROH",
    "REALIZED_LOAD",
    "MASKED_LOAD",
    "generic_homozygosity",
    "froh_within_pop_rank",
    "realized_within_pop_rank",
    "masked_within_pop_rank",
    "inverse_masked_within_pop_rank",
    "generic_homozygosity_within_pop_rank",
    "composite_risk_proxy_score",
    "composite_global_rank",
    "composite_risk_percentile",
]

FIGURE_VALUE_COLUMNS = [
    "figure",
    "panel",
    "record_type",
    "cell_id",
    "gerp_threshold",
    "roh_cutoff_mb",
    "outcome",
    "model",
    "IND",
    "POP",
    "x_value",
    "y_value",
    "estimate",
    "ci_low",
    "ci_high",
    "n",
]

RELATIVE_OUTPUTS = {
    "associations": "results/tables/wolf_froh_load_associations.tsv",
    "rank_stability": "results/tables/wolf_froh_load_rank_stability.tsv",
    "individual_scores": "results/tables/wolf_froh_load_individual_scores.tsv",
    "figure_values": "results/tables/wolf_froh_load_figure_values.tsv",
    "surface_figure": "results/figures/wolf_froh_load_surface.png",
    "forest_figure": "results/figures/wolf_froh_load_forest.png",
    "provenance": "results/provenance/wolf_froh_load.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--load", default="results/tables/wolf_load.tsv")
    parser.add_argument("--roh", default="results/tables/wolf_roh.tsv")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument(
        "--output-root",
        default=".",
        help="Root below which the standard results/ paths are created",
    )
    parser.add_argument(
        "--skip-figures",
        action="store_true",
        help="Write scientific tables/provenance but skip PNG rendering (validator reruns)",
    )
    return parser.parse_args()


def require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{label} missing required columns: {sorted(missing)}")


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def scientific_hash(paths: Iterable[tuple[str, Path]]) -> str:
    digest = sha256()
    for label, path in sorted(paths):
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def stable_seed(base_seed: int, label: str) -> int:
    raw = sha256(f"{base_seed}|{label}".encode("utf-8")).digest()[:8]
    return int.from_bytes(raw, "little") % (2**63 - 1)


def number_label(value: float) -> str:
    return f"{float(value):g}".replace("-", "m").replace(".", "p")


def make_cell_id(gerp_threshold: float, roh_cutoff_mb: float) -> str:
    return f"gerp{number_label(gerp_threshold)}_roh{number_label(roh_cutoff_mb)}"


def within_population_rank(values: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Average-tie rank scaled to [0, 1] separately within each population."""
    values = np.asarray(values, dtype=float)
    groups = np.asarray(groups, dtype=str)
    if not np.isfinite(values).all():
        raise ValueError("within-population ranking received non-finite values")
    ranked = np.empty(values.size, dtype=float)
    for group in sorted(np.unique(groups)):
        idx = np.flatnonzero(groups == group)
        if idx.size == 1:
            ranked[idx] = 0.5
        else:
            ranked[idx] = (stats.rankdata(values[idx], method="average") - 1.0) / (idx.size - 1.0)
    return ranked


def pearson_coefficient(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    finite = np.isfinite(x) & np.isfinite(y)
    if finite.sum() < 3:
        return float("nan")
    x = x[finite] - np.mean(x[finite])
    y = y[finite] - np.mean(y[finite])
    denom = math.sqrt(float(np.dot(x, x) * np.dot(y, y)))
    if not np.isfinite(denom) or denom <= np.finfo(float).eps:
        return float("nan")
    return float(np.clip(np.dot(x, y) / denom, -1.0, 1.0))


def partial_coefficient(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> float:
    """Pearson partial correlation of x and y controlling z."""
    r_xy = pearson_coefficient(x, y)
    r_xz = pearson_coefficient(x, z)
    r_yz = pearson_coefficient(y, z)
    if not np.isfinite([r_xy, r_xz, r_yz]).all():
        return float("nan")
    denominator = math.sqrt(max(0.0, (1.0 - r_xz**2) * (1.0 - r_yz**2)))
    if denominator <= np.finfo(float).eps:
        return float("nan")
    return float(np.clip((r_xy - r_xz * r_yz) / denominator, -1.0, 1.0))


def stratified_indices(groups: np.ndarray) -> list[np.ndarray]:
    groups = np.asarray(groups, dtype=str)
    return [np.flatnonzero(groups == group) for group in sorted(np.unique(groups))]


def infer_associations(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    groups: np.ndarray,
    bootstrap_reps: int,
    permutation_reps: int,
    ci_pct: float,
    bootstrap_seed: int,
    permutation_seed: int,
) -> dict[str, dict[str, float | int]]:
    """Observed, stratified-bootstrap, and within-population permutation inference."""
    strata = stratified_indices(groups)
    observed = {
        "primary": pearson_coefficient(x, y),
        "partial_generic_homozygosity_control": partial_coefficient(x, y, z),
    }

    bootstrap_values = {model: np.full(bootstrap_reps, np.nan) for model in observed}
    bootstrap_rng = np.random.default_rng(bootstrap_seed)
    for replicate in range(bootstrap_reps):
        sampled = np.concatenate(
            [idx[bootstrap_rng.integers(0, idx.size, size=idx.size)] for idx in strata]
        )
        xb, yb, zb = x[sampled], y[sampled], z[sampled]
        bootstrap_values["primary"][replicate] = pearson_coefficient(xb, yb)
        bootstrap_values["partial_generic_homozygosity_control"][replicate] = partial_coefficient(
            xb, yb, zb
        )

    permutation_values = {model: np.full(permutation_reps, np.nan) for model in observed}
    permutation_rng = np.random.default_rng(permutation_seed)
    for replicate in range(permutation_reps):
        permuted_x = x.copy()
        for idx in strata:
            permuted_x[idx] = x[permutation_rng.permutation(idx)]
        permutation_values["primary"][replicate] = pearson_coefficient(permuted_x, y)
        permutation_values["partial_generic_homozygosity_control"][replicate] = partial_coefficient(
            permuted_x, y, z
        )

    alpha = (100.0 - ci_pct) / 2.0
    result: dict[str, dict[str, float | int]] = {}
    for model, coefficient in observed.items():
        boot = bootstrap_values[model]
        valid_boot = boot[np.isfinite(boot)]
        perm = permutation_values[model]
        valid_perm = perm[np.isfinite(perm)]
        if valid_boot.size:
            ci_low, ci_high = np.percentile(valid_boot, [alpha, 100.0 - alpha])
        else:
            ci_low = ci_high = float("nan")
        if valid_perm.size and np.isfinite(coefficient):
            extreme = int(np.count_nonzero(np.abs(valid_perm) >= abs(coefficient)))
            permutation_p = (extreme + 1.0) / (valid_perm.size + 1.0)
        else:
            permutation_p = float("nan")
        result[model] = {
            "coefficient": coefficient,
            "ci_low": float(ci_low),
            "ci_high": float(ci_high),
            "permutation_p_two_sided": float(permutation_p),
            "bootstrap_valid": int(valid_boot.size),
            "bootstrap_failed": int(bootstrap_reps - valid_boot.size),
            "permutation_valid": int(valid_perm.size),
            "permutation_failed": int(permutation_reps - valid_perm.size),
        }
    return result


def read_and_validate_inputs(
    load_path: Path,
    roh_path: Path,
    gerp_thresholds: list[float],
    roh_cutoffs: list[float],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    load = pd.read_csv(load_path, sep="\t")
    roh = pd.read_csv(roh_path, sep="\t")
    require_columns(
        load,
        {
            "IND",
            "POP",
            "THRES",
            "REALIZED_LOAD",
            "MASKED_LOAD",
            "tot_der",
            "hom_der",
            "calls",
        },
        "wolf load",
    )
    require_columns(roh, {"IND", "POP", "min_length_mb", "F_ROH"}, "wolf ROH")

    if load.duplicated(["IND", "THRES"]).any():
        raise ValueError("wolf load contains duplicate (IND, THRES) keys")
    if roh.duplicated(["IND", "min_length_mb"]).any():
        raise ValueError("wolf ROH contains duplicate (IND, min_length_mb) keys")
    if set(load["THRES"].astype(float).unique()) != set(gerp_thresholds):
        raise ValueError("wolf load thresholds do not equal the frozen GERP grid")
    if set(roh["min_length_mb"].astype(float).unique()) != set(roh_cutoffs):
        raise ValueError("wolf ROH cutoffs do not equal the frozen ROH grid")

    load_ids = set(load["IND"].astype(str))
    roh_ids = set(roh["IND"].astype(str))
    if len(load_ids) != EXPECTED_N or len(roh_ids) != EXPECTED_N or load_ids != roh_ids:
        raise ValueError(
            f"strict join failed: load={len(load_ids)}, ROH={len(roh_ids)}, "
            f"load_only={sorted(load_ids - roh_ids)}, roh_only={sorted(roh_ids - load_ids)}"
        )
    for threshold in gerp_thresholds:
        ids = set(load.loc[load["THRES"].astype(float).eq(threshold), "IND"].astype(str))
        if ids != load_ids:
            raise ValueError(f"GERP>{threshold:g} does not contain all {EXPECTED_N} individuals")
    for cutoff in roh_cutoffs:
        ids = set(roh.loc[roh["min_length_mb"].astype(float).eq(cutoff), "IND"].astype(str))
        if ids != roh_ids:
            raise ValueError(f"ROH cutoff {cutoff:g} Mb does not contain all {EXPECTED_N} individuals")

    load_pop = load[["IND", "POP"]].drop_duplicates()
    roh_pop = roh[["IND", "POP"]].drop_duplicates()
    if load_pop.duplicated("IND").any() or roh_pop.duplicated("IND").any():
        raise ValueError("an individual maps to more than one population/cohort")
    pop_join = load_pop.merge(roh_pop, on="IND", how="outer", suffixes=("_load", "_roh"), indicator=True)
    if not pop_join["_merge"].eq("both").all() or not pop_join["POP_load"].eq(pop_join["POP_roh"]).all():
        raise ValueError("load and ROH population/cohort mappings do not reconcile")

    numeric_load = ["REALIZED_LOAD", "MASKED_LOAD", "tot_der", "hom_der", "calls"]
    if not np.isfinite(load[numeric_load].to_numpy(dtype=float)).all():
        raise ValueError("wolf load contains non-finite analysis values")
    if not np.isfinite(roh[["F_ROH"]].to_numpy(dtype=float)).all():
        raise ValueError("wolf ROH contains non-finite F_ROH")
    if (load["calls"] <= 0).any():
        raise ValueError("generic homozygosity is undefined where calls <= 0")

    invariant_columns = ["tot_der", "hom_der", "calls"]
    if not load.groupby("IND")[invariant_columns].nunique().eq(1).all().all():
        raise ValueError("threshold-independent wolf counts vary across GERP rows")
    generic = load.sort_values("THRES").drop_duplicates("IND")[["IND", *invariant_columns]].copy()
    generic["generic_homozygosity"] = 1.0 - (
        (generic["tot_der"] - generic["hom_der"]) / generic["calls"]
    )
    if not generic["generic_homozygosity"].between(0.0, 1.0, inclusive="both").all():
        raise ValueError("derived generic homozygosity falls outside [0, 1]")
    return load, roh, generic[["IND", "generic_homozygosity"]]


def build_individual_scores(
    load: pd.DataFrame,
    roh: pd.DataFrame,
    generic: pd.DataFrame,
    gerp_thresholds: list[float],
    roh_cutoffs: list[float],
) -> pd.DataFrame:
    records: list[pd.DataFrame] = []
    for threshold in gerp_thresholds:
        load_cell = load.loc[
            load["THRES"].astype(float).eq(threshold),
            ["IND", "POP", "REALIZED_LOAD", "MASKED_LOAD"],
        ]
        for cutoff in roh_cutoffs:
            roh_cell = roh.loc[
                roh["min_length_mb"].astype(float).eq(cutoff), ["IND", "POP", "F_ROH"]
            ]
            cell = load_cell.merge(
                roh_cell, on=["IND", "POP"], how="inner", validate="one_to_one"
            ).merge(generic, on="IND", how="inner", validate="one_to_one")
            if len(cell) != EXPECTED_N:
                raise ValueError(f"cell GERP>{threshold:g}/ROH>={cutoff:g} joined {len(cell)} individuals")
            cell = cell.sort_values("IND").reset_index(drop=True)
            groups = cell["POP"].astype(str).to_numpy()
            cell["froh_within_pop_rank"] = within_population_rank(
                cell["F_ROH"].to_numpy(), groups
            )
            cell["realized_within_pop_rank"] = within_population_rank(
                cell["REALIZED_LOAD"].to_numpy(), groups
            )
            cell["masked_within_pop_rank"] = within_population_rank(
                cell["MASKED_LOAD"].to_numpy(), groups
            )
            cell["inverse_masked_within_pop_rank"] = 1.0 - cell["masked_within_pop_rank"]
            cell["generic_homozygosity_within_pop_rank"] = within_population_rank(
                cell["generic_homozygosity"].to_numpy(), groups
            )
            cell["composite_risk_proxy_score"] = cell[
                [
                    "froh_within_pop_rank",
                    "realized_within_pop_rank",
                    "inverse_masked_within_pop_rank",
                ]
            ].mean(axis=1)
            cell["composite_global_rank"] = stats.rankdata(
                -cell["composite_risk_proxy_score"].to_numpy(), method="average"
            )
            cell["composite_risk_percentile"] = 100.0 * (
                stats.rankdata(cell["composite_risk_proxy_score"].to_numpy(), method="average") - 1.0
            ) / (EXPECTED_N - 1.0)
            cell["cell_id"] = make_cell_id(threshold, cutoff)
            cell["gerp_threshold"] = threshold
            cell["roh_cutoff_mb"] = cutoff
            records.append(cell[INDIVIDUAL_COLUMNS])
    result = pd.concat(records, ignore_index=True)
    return result.sort_values(["gerp_threshold", "roh_cutoff_mb", "IND"]).reset_index(drop=True)


def build_associations(
    scores: pd.DataFrame,
    settings: dict,
    negative_control_name: str,
) -> pd.DataFrame:
    records: list[dict] = []
    base_seed = int(settings["seed"])
    bootstrap_reps = int(settings["bootstrap_reps"])
    permutation_reps = int(settings["permutation_reps"])
    ci_pct = float(settings["ci_pct"])
    outcome_columns = {
        "realized_load": ("realized_within_pop_rank", 1),
        "masked_load": ("masked_within_pop_rank", -1),
    }
    for cell_id, cell in scores.groupby("cell_id", sort=False):
        cell = cell.sort_values("IND")
        threshold = float(cell["gerp_threshold"].iloc[0])
        cutoff = float(cell["roh_cutoff_mb"].iloc[0])
        groups = cell["POP"].astype(str).to_numpy()
        x = cell["froh_within_pop_rank"].to_numpy(dtype=float)
        z = cell["generic_homozygosity_within_pop_rank"].to_numpy(dtype=float)
        for outcome, (column, expected_direction) in outcome_columns.items():
            y = cell[column].to_numpy(dtype=float)
            bootstrap_seed = stable_seed(base_seed, f"bootstrap|{cell_id}|{outcome}")
            permutation_seed = stable_seed(base_seed, f"permutation|{cell_id}|{outcome}")
            inference = infer_associations(
                x,
                y,
                z,
                groups,
                bootstrap_reps,
                permutation_reps,
                ci_pct,
                bootstrap_seed,
                permutation_seed,
            )
            for model in ("primary", "partial_generic_homozygosity_control"):
                values = inference[model]
                coefficient = float(values["coefficient"])
                records.append(
                    {
                        "analysis_id": f"{cell_id}|{outcome}|{model}",
                        "cell_id": cell_id,
                        "gerp_threshold": threshold,
                        "roh_cutoff_mb": cutoff,
                        "outcome": outcome,
                        "model": model,
                        "n_ind": len(cell),
                        "n_pop": cell["POP"].nunique(),
                        "coefficient": coefficient,
                        "ci_low": values["ci_low"],
                        "ci_high": values["ci_high"],
                        "ci_pct": ci_pct,
                        "permutation_p_two_sided": values["permutation_p_two_sided"],
                        "expected_direction": expected_direction,
                        "direction_matches_expected": bool(coefficient * expected_direction > 0),
                        "bootstrap_reps": bootstrap_reps,
                        "bootstrap_valid": values["bootstrap_valid"],
                        "bootstrap_failed": values["bootstrap_failed"],
                        "permutation_reps": permutation_reps,
                        "permutation_valid": values["permutation_valid"],
                        "permutation_failed": values["permutation_failed"],
                        "bootstrap_seed": bootstrap_seed,
                        "permutation_seed": permutation_seed,
                        "negative_control": (
                            "none" if model == "primary" else negative_control_name
                        ),
                    }
                )
    result = pd.DataFrame(records, columns=ASSOCIATION_COLUMNS)
    model_order = pd.Categorical(
        result["model"],
        categories=["primary", "partial_generic_homozygosity_control"],
        ordered=True,
    )
    outcome_order = pd.Categorical(
        result["outcome"], categories=["realized_load", "masked_load"], ordered=True
    )
    return (
        result.assign(_model_order=model_order, _outcome_order=outcome_order)
        .sort_values(["gerp_threshold", "roh_cutoff_mb", "_outcome_order", "_model_order"])
        .drop(columns=["_model_order", "_outcome_order"])
        .reset_index(drop=True)
    )


def top_individuals(cell: pd.DataFrame, top_n: int) -> set[str]:
    ordered = cell.sort_values(
        ["composite_risk_proxy_score", "IND"], ascending=[False, True], kind="mergesort"
    )
    return set(ordered.head(top_n)["IND"].astype(str))


def build_rank_stability(scores: pd.DataFrame, percentiles: list[float]) -> pd.DataFrame:
    cells = []
    for cell_id, cell in scores.groupby("cell_id", sort=False):
        cell = cell.sort_values("IND").reset_index(drop=True)
        cells.append((cell_id, cell))
    records: list[dict] = []
    for left in range(len(cells)):
        cell_a_id, cell_a = cells[left]
        for right in range(left + 1, len(cells)):
            cell_b_id, cell_b = cells[right]
            if not cell_a["IND"].equals(cell_b["IND"]):
                raise ValueError(f"individual ordering differs between {cell_a_id} and {cell_b_id}")
            a = cell_a["composite_risk_proxy_score"].to_numpy(dtype=float)
            b = cell_b["composite_risk_proxy_score"].to_numpy(dtype=float)
            spearman = stats.spearmanr(a, b)
            kendall = stats.kendalltau(a, b)
            pair_id = f"{cell_a_id}__{cell_b_id}"
            for percentile in percentiles:
                top_n = max(1, int(math.ceil(EXPECTED_N * float(percentile) / 100.0)))
                top_a = top_individuals(cell_a, top_n)
                top_b = top_individuals(cell_b, top_n)
                overlap = len(top_a.intersection(top_b))
                union = len(top_a.union(top_b))
                records.append(
                    {
                        "pair_id": pair_id,
                        "cell_a_id": cell_a_id,
                        "cell_b_id": cell_b_id,
                        "gerp_a": float(cell_a["gerp_threshold"].iloc[0]),
                        "roh_a_mb": float(cell_a["roh_cutoff_mb"].iloc[0]),
                        "gerp_b": float(cell_b["gerp_threshold"].iloc[0]),
                        "roh_b_mb": float(cell_b["roh_cutoff_mb"].iloc[0]),
                        "n_ind": EXPECTED_N,
                        "spearman_rho": float(spearman.statistic),
                        "spearman_p": float(spearman.pvalue),
                        "kendall_tau": float(kendall.statistic),
                        "kendall_p": float(kendall.pvalue),
                        "top_percentile": float(percentile),
                        "top_n": top_n,
                        "top_overlap_n": overlap,
                        "top_overlap_fraction": overlap / top_n,
                        "top_jaccard": overlap / union,
                    }
                )
    return pd.DataFrame(records, columns=STABILITY_COLUMNS)


def blank_figure_record() -> dict:
    return {column: "" for column in FIGURE_VALUE_COLUMNS}


def build_figure_values(
    associations: pd.DataFrame,
    scores: pd.DataFrame,
    default_gerp: float,
    default_roh: float,
) -> pd.DataFrame:
    records: list[dict] = []
    for row in associations.itertuples(index=False):
        surface = blank_figure_record()
        surface.update(
            {
                "figure": "wolf_froh_load_surface.png",
                "panel": f"{row.model}|{row.outcome}",
                "record_type": "heatmap_cell",
                "cell_id": row.cell_id,
                "gerp_threshold": row.gerp_threshold,
                "roh_cutoff_mb": row.roh_cutoff_mb,
                "outcome": row.outcome,
                "model": row.model,
                "estimate": row.coefficient,
                "ci_low": row.ci_low,
                "ci_high": row.ci_high,
                "n": row.n_ind,
            }
        )
        records.append(surface)
        if row.model == "primary":
            forest = surface.copy()
            forest.update(
                {
                    "figure": "wolf_froh_load_forest.png",
                    "panel": f"forest|{row.outcome}",
                    "record_type": "forest_cell",
                }
            )
            records.append(forest)

    default_scores = scores.loc[
        scores["gerp_threshold"].astype(float).eq(default_gerp)
        & scores["roh_cutoff_mb"].astype(float).eq(default_roh)
    ].copy()
    if len(default_scores) != EXPECTED_N:
        raise ValueError("default scatter cell does not contain all individuals")
    for outcome, value_column in (
        ("realized_load", "REALIZED_LOAD"),
        ("masked_load", "MASKED_LOAD"),
    ):
        for row in default_scores.itertuples(index=False):
            scatter = blank_figure_record()
            scatter.update(
                {
                    "figure": "wolf_froh_load_forest.png",
                    "panel": f"scatter|{outcome}",
                    "record_type": "scatter_individual",
                    "cell_id": row.cell_id,
                    "gerp_threshold": row.gerp_threshold,
                    "roh_cutoff_mb": row.roh_cutoff_mb,
                    "outcome": outcome,
                    "model": "primary",
                    "IND": row.IND,
                    "POP": row.POP,
                    "x_value": row.F_ROH,
                    "y_value": getattr(row, value_column),
                    "n": 1,
                }
            )
            records.append(scatter)
        cohort = (
            default_scores.groupby("POP", as_index=False)
            .agg(x_value=("F_ROH", "mean"), y_value=(value_column, "mean"), n=("IND", "size"))
            .sort_values("POP")
        )
        for row in cohort.itertuples(index=False):
            centroid = blank_figure_record()
            centroid.update(
                {
                    "figure": "wolf_froh_load_forest.png",
                    "panel": f"scatter|{outcome}",
                    "record_type": "cohort_centroid",
                    "cell_id": make_cell_id(default_gerp, default_roh),
                    "gerp_threshold": default_gerp,
                    "roh_cutoff_mb": default_roh,
                    "outcome": outcome,
                    "model": "primary",
                    "POP": row.POP,
                    "x_value": row.x_value,
                    "y_value": row.y_value,
                    "n": row.n,
                }
            )
            records.append(centroid)
    return pd.DataFrame(records, columns=FIGURE_VALUE_COLUMNS)


def render_surface(figure_values: pd.DataFrame, path: Path) -> None:
    data = figure_values.loc[figure_values["record_type"].eq("heatmap_cell")].copy()
    models = ["primary", "partial_generic_homozygosity_control"]
    outcomes = ["realized_load", "masked_load"]
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 8.5), constrained_layout=True)
    image = None
    for row_idx, outcome in enumerate(outcomes):
        for col_idx, model in enumerate(models):
            ax = axes[row_idx, col_idx]
            panel = data.loc[data["outcome"].eq(outcome) & data["model"].eq(model)].copy()
            thresholds = sorted(panel["gerp_threshold"].astype(float).unique())
            cutoffs = sorted(panel["roh_cutoff_mb"].astype(float).unique())
            matrix = (
                panel.pivot(index="gerp_threshold", columns="roh_cutoff_mb", values="estimate")
                .reindex(index=thresholds, columns=cutoffs)
                .to_numpy(dtype=float)
            )
            image = ax.imshow(matrix, cmap="RdBu_r", vmin=-1.0, vmax=1.0, aspect="auto")
            for i in range(matrix.shape[0]):
                for j in range(matrix.shape[1]):
                    color = "white" if abs(matrix[i, j]) >= 0.55 else "black"
                    ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center", fontsize=9, color=color)
            ax.set_xticks(range(len(cutoffs)), [f"{value:g}" for value in cutoffs])
            ax.set_yticks(range(len(thresholds)), [f"{value:g}" for value in thresholds])
            ax.set_xlabel("Minimum ROH length (Mb)")
            ax.set_ylabel("GERP threshold")
            outcome_title = "Realized load" if outcome == "realized_load" else "Masked load"
            model_title = "Primary" if model == "primary" else "Partial: generic homozygosity controlled"
            ax.set_title(f"{outcome_title} — {model_title}", fontsize=11)
    if image is not None:
        fig.colorbar(image, ax=axes, shrink=0.82, label="Within-cohort rank association")
    fig.suptitle(
        "Wolf F_ROH–load robustness surface: genomic risk-proxy associations",
        fontsize=15,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, metadata={"Software": "congen-phase5b"})
    plt.close(fig)


def render_scatter_forest(figure_values: pd.DataFrame, path: Path) -> None:
    outcomes = ["realized_load", "masked_load"]
    populations = sorted(
        figure_values.loc[figure_values["record_type"].eq("scatter_individual"), "POP"]
        .astype(str)
        .unique()
    )
    colors = dict(zip(populations, plt.get_cmap("tab10").colors, strict=False))
    fig, axes = plt.subplots(2, 2, figsize=(15, 12), constrained_layout=True)
    for column, outcome in enumerate(outcomes):
        scatter = figure_values.loc[
            figure_values["record_type"].eq("scatter_individual")
            & figure_values["outcome"].eq(outcome)
        ].copy()
        centroids = figure_values.loc[
            figure_values["record_type"].eq("cohort_centroid")
            & figure_values["outcome"].eq(outcome)
        ].copy()
        ax = axes[0, column]
        for population in populations:
            sub = scatter.loc[scatter["POP"].eq(population)]
            ax.scatter(
                pd.to_numeric(sub["x_value"]),
                pd.to_numeric(sub["y_value"]),
                s=18,
                alpha=0.48,
                color=colors[population],
                label=population,
                linewidths=0,
            )
            centroid = centroids.loc[centroids["POP"].eq(population)]
            ax.scatter(
                pd.to_numeric(centroid["x_value"]),
                pd.to_numeric(centroid["y_value"]),
                s=70,
                marker="X",
                edgecolor="black",
                linewidth=0.6,
                color=colors[population],
            )
        ax.set_xlabel("F_ROH")
        ax.set_ylabel("GERP-weighted load")
        title = "Realized load" if outcome == "realized_load" else "Masked load"
        ax.set_title(f"Cohort-aware individual scatter — {title}")
        if column == 1:
            ax.legend(loc="best", fontsize=7, frameon=False, ncol=2)

        forest = figure_values.loc[
            figure_values["record_type"].eq("forest_cell")
            & figure_values["outcome"].eq(outcome)
        ].copy()
        forest = forest.sort_values(["gerp_threshold", "roh_cutoff_mb"]).reset_index(drop=True)
        estimates = pd.to_numeric(forest["estimate"]).to_numpy()
        ci_low = pd.to_numeric(forest["ci_low"]).to_numpy()
        ci_high = pd.to_numeric(forest["ci_high"]).to_numpy()
        positions = np.arange(len(forest))[::-1]
        labels = [
            f"GERP>{float(g):g}; ROH≥{float(r):g} Mb"
            for g, r in zip(forest["gerp_threshold"], forest["roh_cutoff_mb"])
        ]
        axf = axes[1, column]
        axf.errorbar(
            estimates,
            positions,
            xerr=np.vstack([estimates - ci_low, ci_high - estimates]),
            fmt="o",
            color="#245b78" if outcome == "realized_load" else "#a05a2c",
            ecolor="#737373",
            capsize=2,
            markersize=4,
        )
        axf.axvline(0.0, color="black", linestyle="--", linewidth=0.8)
        axf.set_yticks(positions, labels, fontsize=7)
        axf.set_xlim(-1.0, 1.0)
        axf.set_xlabel("Primary within-cohort rank association (95% bootstrap CI)")
        axf.set_title(f"Frozen 3 × 5 forest — {title}")
    fig.suptitle(
        "Wolf F_ROH and load: cohort-aware association, not fitness or causation",
        fontsize=15,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, metadata={"Software": "congen-phase5b"})
    plt.close(fig)


def write_table(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, sep="\t", index=False, float_format="%.17g", na_rep="NA")


def run_analysis(args: argparse.Namespace) -> dict:
    config_path = Path(args.config)
    load_path = Path(args.load)
    roh_path = Path(args.roh)
    output_root = Path(args.output_root)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    settings = config["phase5b"]["wolf_robustness"]
    gerp_thresholds = sorted(float(value) for value in config["wolf"]["load"]["gerp_sensitivity"])
    roh_cutoffs = sorted(float(value) for value in config["wolf"]["roh"]["length_cutoffs_mb"])
    if len(gerp_thresholds) != 3 or len(roh_cutoffs) != 5:
        raise ValueError("Phase-5B wolf robustness requires the frozen 3 x 5 grid")
    percentiles = [float(value) for value in settings["top_risk_percentiles"]]
    if percentiles != sorted(set(percentiles)) or any(value <= 0 or value >= 100 for value in percentiles):
        raise ValueError("top-risk percentiles must be unique, increasing, and inside (0,100)")

    load, roh, generic = read_and_validate_inputs(
        load_path, roh_path, gerp_thresholds, roh_cutoffs
    )
    scores = build_individual_scores(load, roh, generic, gerp_thresholds, roh_cutoffs)
    associations = build_associations(scores, settings, str(settings["negative_control"]))
    stability = build_rank_stability(scores, percentiles)
    figure_values = build_figure_values(
        associations,
        scores,
        float(config["wolf"]["load"]["gerp_threshold"]),
        float(config["wolf"]["roh"]["long_roh_threshold_mb"]),
    )

    paths = {name: output_root / relative for name, relative in RELATIVE_OUTPUTS.items()}
    write_table(associations, paths["associations"])
    write_table(stability, paths["rank_stability"])
    write_table(scores, paths["individual_scores"])
    write_table(figure_values, paths["figure_values"])
    if not args.skip_figures:
        render_surface(figure_values, paths["surface_figure"])
        render_scatter_forest(figure_values, paths["forest_figure"])

    scientific_files = [
        (RELATIVE_OUTPUTS[name], paths[name])
        for name in ("associations", "rank_stability", "individual_scores", "figure_values")
    ]
    result_hash = scientific_hash(scientific_files)
    partial_realized = associations.loc[
        associations["outcome"].eq("realized_load")
        & associations["model"].eq("partial_generic_homozygosity_control")
    ]
    partial_masked = associations.loc[
        associations["outcome"].eq("masked_load")
        & associations["model"].eq("partial_generic_homozygosity_control")
    ]
    ci_positive_cells = int(partial_realized["ci_low"].gt(0).sum())
    ci_negative_masked_cells = int(partial_masked["ci_high"].lt(0).sum())
    reopen_threshold = int(settings["roh_localization_reopen_min_cells"])

    produced_names = ["associations", "rank_stability", "individual_scores", "figure_values"]
    if not args.skip_figures:
        produced_names.extend(["surface_figure", "forest_figure"])
    provenance = {
        "schema_version": "1.0",
        "analysis": "wolf_individual_froh_load_robustness_surface",
        "claim_boundary": (
            "Associations and rankings among genomic risk proxies; not fitness, causal "
            "inbreeding depression, or measured biological harm."
        ),
        "inputs": {
            str(load_path): file_sha256(load_path),
            str(roh_path): file_sha256(roh_path),
            str(config_path): file_sha256(config_path),
            "scripts/python/wolf_froh_load_robustness.py": file_sha256(Path(__file__)),
        },
        "settings": {
            "seed": int(settings["seed"]),
            "bootstrap_reps": int(settings["bootstrap_reps"]),
            "permutation_reps": int(settings["permutation_reps"]),
            "ci_pct": float(settings["ci_pct"]),
            "top_risk_percentiles": percentiles,
            "negative_control": str(settings["negative_control"]),
            "gerp_thresholds": gerp_thresholds,
            "roh_cutoffs_mb": roh_cutoffs,
        },
        "methods": {
            "primary": "Pearson association of within-POP fractional ranks.",
            "partial": (
                "Partial correlation of within-POP ranks controlling the within-POP rank of "
                "GERP-covered generic homozygosity."
            ),
            "bootstrap": "Cohort-stratified resampling with replacement at original cohort sizes.",
            "permutation": "F_ROH rank permuted independently within each cohort; two-sided Monte Carlo p-value.",
            "composite_risk_proxy": (
                "Mean of within-POP F_ROH rank, realized-load rank, and inverse masked-load rank."
            ),
            "top_overlap": "Exactly ceil(percentile * 211) individuals; deterministic IND tie-break.",
        },
        "counts": {
            "individuals": EXPECTED_N,
            "cohorts": int(scores["POP"].nunique()),
            "grid_cells": int(scores["cell_id"].nunique()),
            "association_rows": len(associations),
            "cell_pairs": int(stability["pair_id"].nunique()),
            "rank_stability_rows": len(stability),
            "individual_score_rows": len(scores),
        },
        "findings": {
            "partial_realized_ci_positive_cells": ci_positive_cells,
            "partial_masked_ci_negative_cells": ci_negative_masked_cells,
            "roh_localization_reopen_min_cells": reopen_threshold,
            "roh_localization_gate_pass": bool(ci_positive_cells >= reopen_threshold),
            "primary_expected_direction_cells": int(
                associations.loc[associations["model"].eq("primary"), "direction_matches_expected"].sum()
            ),
            "partial_expected_direction_cells": int(
                associations.loc[
                    associations["model"].eq("partial_generic_homozygosity_control"),
                    "direction_matches_expected",
                ].sum()
            ),
        },
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
            "matplotlib": matplotlib.__version__,
        },
        "scientific_hash_algorithm": "sha256 over labelled deterministic TSV bytes",
        "scientific_hash_files": [label for label, _ in scientific_files],
        "scientific_hash": result_hash,
        "output_sha256": {
            RELATIVE_OUTPUTS[name]: file_sha256(paths[name]) for name in produced_names
        },
    }
    paths["provenance"].parent.mkdir(parents=True, exist_ok=True)
    paths["provenance"].write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(
        f"wolf robustness: {EXPECTED_N}/211 individuals, {len(associations)} association rows, "
        f"{stability['pair_id'].nunique()} cell pairs x {len(percentiles)} percentiles"
    )
    print(
        "partial realized-load CI entirely positive in "
        f"{ci_positive_cells}/15 cells; ROH-localization reopen threshold={reopen_threshold} -> "
        f"{'PASS' if ci_positive_cells >= reopen_threshold else 'NO-GO'}"
    )
    print(f"scientific hash: {result_hash}")
    return provenance


def main() -> None:
    run_analysis(parse_args())


if __name__ == "__main__":
    main()
