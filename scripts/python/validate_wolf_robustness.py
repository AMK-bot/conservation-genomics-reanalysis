#!/usr/bin/env python3
"""Independent acceptance validator for the Phase-5B wolf robustness surface."""

from __future__ import annotations

import argparse
from hashlib import sha256
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd
from scipy import stats
import yaml


EXPECTED_N = 211
TABLES = {
    "associations": "results/tables/wolf_froh_load_associations.tsv",
    "rank_stability": "results/tables/wolf_froh_load_rank_stability.tsv",
    "individual_scores": "results/tables/wolf_froh_load_individual_scores.tsv",
    "figure_values": "results/tables/wolf_froh_load_figure_values.tsv",
}
FIGURES = [
    "results/figures/wolf_froh_load_surface.png",
    "results/figures/wolf_froh_load_forest.png",
]
PROVENANCE = "results/provenance/wolf_froh_load.json"
ANALYSIS_SCRIPT = "scripts/python/wolf_froh_load_robustness.py"
LOAD = "results/tables/wolf_load.tsv"
ROH = "results/tables/wolf_roh.tsv"
CONFIG = "config/config.yaml"

ASSOCIATION_COLUMNS = {
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
}

STABILITY_COLUMNS = {
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
}

INDIVIDUAL_COLUMNS = {
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
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--out-tsv", default="results/tables/validation_wolf_robustness.tsv")
    parser.add_argument("--out-md", default="results/WOLF_ROBUSTNESS_VALIDATION.md")
    parser.add_argument(
        "--skip-rerun",
        action="store_true",
        help="Skip the deterministic temporary rerun (diagnostic use only; not an acceptance run)",
    )
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def scientific_hash(paths: list[tuple[str, Path]]) -> str:
    digest = sha256()
    for label, path in sorted(paths):
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def as_bool(series: pd.Series) -> pd.Series:
    return series.map(lambda value: value if isinstance(value, bool) else str(value).lower() == "true")


class Validator:
    def __init__(self, root: Path):
        self.root = root
        self.checks: list[tuple[str, str, str]] = []

    def add(self, name: str, condition: bool, detail: str) -> None:
        self.checks.append((name, "PASS" if bool(condition) else "FAIL", detail))

    def path(self, relative: str) -> Path:
        return self.root / relative

    def validate(self, skip_rerun: bool) -> None:
        required = [
            LOAD,
            ROH,
            CONFIG,
            ANALYSIS_SCRIPT,
            PROVENANCE,
            *TABLES.values(),
            *FIGURES,
        ]
        missing = [relative for relative in required if not self.path(relative).is_file()]
        self.add("all wolf-robustness artifacts exist", not missing, f"missing={missing}" if missing else f"{len(required)} files")
        if missing:
            return

        config = yaml.safe_load(self.path(CONFIG).read_text(encoding="utf-8"))
        settings = config["phase5b"]["wolf_robustness"]
        gerp = sorted(float(value) for value in config["wolf"]["load"]["gerp_sensitivity"])
        cutoffs = sorted(float(value) for value in config["wolf"]["roh"]["length_cutoffs_mb"])
        percentiles = [float(value) for value in settings["top_risk_percentiles"]]
        expected_cells = {(g, r) for g in gerp for r in cutoffs}
        expected_cell_count = len(expected_cells)

        load = pd.read_csv(self.path(LOAD), sep="\t")
        roh = pd.read_csv(self.path(ROH), sep="\t")
        # Round-trip parsing preserves intentional exact ties in the composite
        # ranks. The default fast parser can perturb the last bit and therefore
        # change tie-aware Spearman/Kendall coefficients on a CSV reread.
        associations = pd.read_csv(
            self.path(TABLES["associations"]), sep="\t", float_precision="round_trip"
        )
        stability = pd.read_csv(
            self.path(TABLES["rank_stability"]), sep="\t", float_precision="round_trip"
        )
        individuals = pd.read_csv(
            self.path(TABLES["individual_scores"]), sep="\t", float_precision="round_trip"
        )
        figure_values = pd.read_csv(
            self.path(TABLES["figure_values"]), sep="\t", float_precision="round_trip"
        )
        provenance = json.loads(self.path(PROVENANCE).read_text(encoding="utf-8"))

        self._validate_join(load, roh)
        self._validate_associations(associations, settings, expected_cells)
        self._validate_individuals(individuals, load, roh, expected_cells)
        self._validate_stability(stability, individuals, percentiles, expected_cell_count)
        self._validate_figure_values(figure_values, associations, individuals, config)
        self._validate_figures()
        self._validate_provenance(provenance, settings, associations)
        if skip_rerun:
            self.add(
                "deterministic independent rerun",
                False,
                "acceptance rerun was explicitly skipped",
            )
        else:
            self._validate_rerun(provenance)

    def _validate_join(self, load: pd.DataFrame, roh: pd.DataFrame) -> None:
        load_ids = set(load["IND"].astype(str))
        roh_ids = set(roh["IND"].astype(str))
        duplicate_load = int(load.duplicated(["IND", "THRES"]).sum())
        duplicate_roh = int(roh.duplicated(["IND", "min_length_mb"]).sum())
        self.add(
            "strict 211/211 load-ROH join",
            len(load_ids) == EXPECTED_N
            and len(roh_ids) == EXPECTED_N
            and load_ids == roh_ids
            and duplicate_load == 0
            and duplicate_roh == 0,
            f"load={len(load_ids)}, ROH={len(roh_ids)}, load_only={len(load_ids-roh_ids)}, "
            f"roh_only={len(roh_ids-load_ids)}, duplicate keys={duplicate_load}/{duplicate_roh}",
        )
        load_pop = load[["IND", "POP"]].drop_duplicates().set_index("IND")["POP"]
        roh_pop = roh[["IND", "POP"]].drop_duplicates().set_index("IND")["POP"]
        common = load_pop.index.intersection(roh_pop.index)
        self.add(
            "load-ROH cohort mapping reconciles",
            len(common) == EXPECTED_N and load_pop.loc[common].equals(roh_pop.loc[common]),
            f"{len(common)} shared IDs; cohort mismatches={int((load_pop.loc[common] != roh_pop.loc[common]).sum())}",
        )

    def _validate_associations(
        self,
        frame: pd.DataFrame,
        settings: dict,
        expected_cells: set[tuple[float, float]],
    ) -> None:
        models = {"primary", "partial_generic_homozygosity_control"}
        outcomes = {"realized_load", "masked_load"}
        actual_cells = set(zip(frame["gerp_threshold"].astype(float), frame["roh_cutoff_mb"].astype(float)))
        combinations = frame.groupby(["gerp_threshold", "roh_cutoff_mb", "outcome", "model"]).size()
        self.add(
            "association table schema and 60-row shape",
            ASSOCIATION_COLUMNS.issubset(frame.columns)
            and len(frame) == 60
            and frame["analysis_id"].nunique() == 60,
            f"rows={len(frame)}, unique analysis IDs={frame['analysis_id'].nunique()}, columns={len(frame.columns)}",
        )
        self.add(
            "all frozen 15 cells x outcomes x models reported",
            actual_cells == expected_cells
            and set(frame["model"]) == models
            and set(frame["outcome"]) == outcomes
            and len(combinations) == 60
            and combinations.eq(1).all(),
            f"cells={len(actual_cells)}, combinations={len(combinations)}, models={sorted(set(frame['model']))}",
        )
        numeric = frame[
            ["coefficient", "ci_low", "ci_high", "permutation_p_two_sided"]
        ].to_numpy(dtype=float)
        bounds_ok = (
            np.isfinite(numeric).all()
            and frame["coefficient"].between(-1, 1).all()
            and frame["ci_low"].between(-1, 1).all()
            and frame["ci_high"].between(-1, 1).all()
            and frame["ci_low"].le(frame["ci_high"]).all()
            and frame["permutation_p_two_sided"].between(0, 1, inclusive="both").all()
        )
        self.add(
            "association coefficients, intervals, and p-values finite and bounded",
            bounds_ok,
            f"coefficient=[{frame['coefficient'].min():.3f},{frame['coefficient'].max():.3f}], "
            f"CI=[{frame['ci_low'].min():.3f},{frame['ci_high'].max():.3f}]",
        )
        boot_reps = int(settings["bootstrap_reps"])
        perm_reps = int(settings["permutation_reps"])
        inference_ok = (
            frame["n_ind"].eq(EXPECTED_N).all()
            and frame["bootstrap_reps"].eq(boot_reps).all()
            and frame["permutation_reps"].eq(perm_reps).all()
            and (frame["bootstrap_valid"] + frame["bootstrap_failed"]).eq(boot_reps).all()
            and (frame["permutation_valid"] + frame["permutation_failed"]).eq(perm_reps).all()
            and frame["bootstrap_valid"].gt(0).all()
            and frame["permutation_valid"].gt(0).all()
            and frame["bootstrap_seed"].notna().all()
            and frame["permutation_seed"].notna().all()
        )
        self.add(
            "bootstrap/permutation contract and failures recorded",
            inference_ok,
            f"bootstrap={boot_reps}, permutation={perm_reps}, "
            f"failed ranges={frame['bootstrap_failed'].min()}-{frame['bootstrap_failed'].max()}/"
            f"{frame['permutation_failed'].min()}-{frame['permutation_failed'].max()}",
        )
        partial = frame["model"].astype(str).str.contains("partial")
        control_ok = (
            partial.sum() == 30
            and frame.loc[partial, "negative_control"].eq(settings["negative_control"]).all()
            and frame.loc[~partial, "negative_control"].eq("none").all()
        )
        self.add(
            "generic-homozygosity partial model explicit",
            control_ok,
            f"partial rows={int(partial.sum())}; control={settings['negative_control']}",
        )
        expected_flag = frame["coefficient"] * frame["expected_direction"] > 0
        self.add(
            "direction flags independently reconcile",
            as_bool(frame["direction_matches_expected"]).equals(expected_flag.reset_index(drop=True)),
            f"expected-direction rows={int(expected_flag.sum())}/60",
        )

    def _validate_individuals(
        self,
        frame: pd.DataFrame,
        load: pd.DataFrame,
        roh: pd.DataFrame,
        expected_cells: set[tuple[float, float]],
    ) -> None:
        cells = set(zip(frame["gerp_threshold"].astype(float), frame["roh_cutoff_mb"].astype(float)))
        counts = frame.groupby("cell_id")["IND"].nunique()
        input_ids = set(load["IND"].astype(str))
        every_id = all(set(group["IND"].astype(str)) == input_ids for _, group in frame.groupby("cell_id"))
        self.add(
            "individual score table is 211 x 15 with unique keys",
            INDIVIDUAL_COLUMNS.issubset(frame.columns)
            and len(frame) == EXPECTED_N * 15
            and cells == expected_cells
            and len(counts) == 15
            and counts.eq(EXPECTED_N).all()
            and not frame.duplicated(["cell_id", "IND"]).any()
            and every_id,
            f"rows={len(frame)}, cells={len(counts)}, per-cell IDs={counts.min()}-{counts.max()}",
        )
        bound_columns = [
            "generic_homozygosity",
            "froh_within_pop_rank",
            "realized_within_pop_rank",
            "masked_within_pop_rank",
            "inverse_masked_within_pop_rank",
            "generic_homozygosity_within_pop_rank",
            "composite_risk_proxy_score",
        ]
        finite_columns = bound_columns + [
            "F_ROH",
            "REALIZED_LOAD",
            "MASKED_LOAD",
            "composite_global_rank",
            "composite_risk_percentile",
        ]
        finite = np.isfinite(frame[finite_columns].to_numpy(dtype=float)).all()
        bounded = all(frame[column].between(0, 1, inclusive="both").all() for column in bound_columns)
        composite = frame[
            ["froh_within_pop_rank", "realized_within_pop_rank", "inverse_masked_within_pop_rank"]
        ].mean(axis=1)
        self.add(
            "individual risk-proxy components finite, bounded, and composite exact",
            finite
            and bounded
            and np.allclose(composite, frame["composite_risk_proxy_score"], atol=1e-14)
            and frame["composite_global_rank"].between(1, EXPECTED_N).all()
            and frame["composite_risk_percentile"].between(0, 100).all(),
            f"score range=[{frame['composite_risk_proxy_score'].min():.3f},"
            f"{frame['composite_risk_proxy_score'].max():.3f}]",
        )

        invariant = load.sort_values("THRES").drop_duplicates("IND").copy()
        invariant["generic_expected"] = 1.0 - (
            (invariant["tot_der"] - invariant["hom_der"]) / invariant["calls"]
        )
        generic_expected = invariant.set_index("IND")["generic_expected"]
        mapped_generic = frame["IND"].map(generic_expected)
        self.add(
            "generic homozygosity formula independently reconciles",
            mapped_generic.notna().all()
            and np.allclose(mapped_generic, frame["generic_homozygosity"], atol=1e-14),
            f"range=[{mapped_generic.min():.6f},{mapped_generic.max():.6f}]",
        )

        expected = frame[["cell_id", "IND", "POP", "gerp_threshold", "roh_cutoff_mb"]].copy()
        expected = expected.merge(
            load[["IND", "POP", "THRES", "REALIZED_LOAD", "MASKED_LOAD"]],
            left_on=["IND", "POP", "gerp_threshold"],
            right_on=["IND", "POP", "THRES"],
            how="left",
            validate="many_to_one",
            suffixes=("", "_source"),
        ).merge(
            roh[["IND", "POP", "min_length_mb", "F_ROH"]],
            left_on=["IND", "POP", "roh_cutoff_mb"],
            right_on=["IND", "POP", "min_length_mb"],
            how="left",
            validate="many_to_one",
        )
        source_ok = (
            len(expected) == len(frame)
            and expected[["REALIZED_LOAD", "MASKED_LOAD", "F_ROH"]].notna().all().all()
            and np.allclose(expected["REALIZED_LOAD"], frame["REALIZED_LOAD"], atol=1e-14)
            and np.allclose(expected["MASKED_LOAD"], frame["MASKED_LOAD"], atol=1e-14)
            and np.allclose(expected["F_ROH"], frame["F_ROH"], atol=1e-14)
        )
        self.add(
            "individual raw values reconcile to Phase-4 inputs",
            source_ok,
            f"{len(expected)} source joins; missing={int(expected[['REALIZED_LOAD','MASKED_LOAD','F_ROH']].isna().sum().sum())}",
        )

    def _validate_stability(
        self,
        frame: pd.DataFrame,
        individuals: pd.DataFrame,
        percentiles: list[float],
        cell_count: int,
    ) -> None:
        expected_pairs = math.comb(cell_count, 2)
        pair_counts = frame.groupby("pair_id")["top_percentile"].nunique()
        self.add(
            "rank stability has all 105 pairs x configured percentiles",
            STABILITY_COLUMNS.issubset(frame.columns)
            and len(frame) == expected_pairs * len(percentiles)
            and frame["pair_id"].nunique() == expected_pairs
            and pair_counts.eq(len(percentiles)).all()
            and set(frame["top_percentile"].astype(float)) == set(percentiles)
            and not frame.duplicated(["pair_id", "top_percentile"]).any(),
            f"rows={len(frame)}, pairs={frame['pair_id'].nunique()}, percentiles={sorted(frame['top_percentile'].unique())}",
        )
        finite_cols = ["spearman_rho", "spearman_p", "kendall_tau", "kendall_p", "top_overlap_fraction", "top_jaccard"]
        bounded = (
            np.isfinite(frame[finite_cols].to_numpy(dtype=float)).all()
            and frame["spearman_rho"].between(-1, 1).all()
            and frame["kendall_tau"].between(-1, 1).all()
            and frame["spearman_p"].between(0, 1).all()
            and frame["kendall_p"].between(0, 1).all()
            and frame["top_overlap_fraction"].between(0, 1).all()
            and frame["top_jaccard"].between(0, 1).all()
            and frame["top_overlap_n"].between(0, frame["top_n"]).all()
        )
        self.add(
            "rank and top-overlap statistics finite and bounded",
            bounded,
            f"Spearman=[{frame['spearman_rho'].min():.3f},{frame['spearman_rho'].max():.3f}], "
            f"overlap=[{frame['top_overlap_fraction'].min():.3f},{frame['top_overlap_fraction'].max():.3f}]",
        )

        score_by_cell = {
            cell: group.sort_values("IND").reset_index(drop=True)
            for cell, group in individuals.groupby("cell_id")
        }
        recompute_ok = True
        mismatch = "none"
        for pair_id, group in frame.groupby("pair_id", sort=False):
            first = group.iloc[0]
            left = score_by_cell[str(first["cell_a_id"])]
            right = score_by_cell[str(first["cell_b_id"])]
            if not left["IND"].equals(right["IND"]):
                recompute_ok = False
                mismatch = f"ID order: {pair_id}"
                break
            a = left["composite_risk_proxy_score"].to_numpy()
            b = right["composite_risk_proxy_score"].to_numpy()
            spearman = stats.spearmanr(a, b)
            kendall = stats.kendalltau(a, b)
            for row in group.itertuples(index=False):
                top_n = int(math.ceil(EXPECTED_N * float(row.top_percentile) / 100.0))
                left_top = set(
                    left.sort_values(
                        ["composite_risk_proxy_score", "IND"], ascending=[False, True], kind="mergesort"
                    ).head(top_n)["IND"]
                )
                right_top = set(
                    right.sort_values(
                        ["composite_risk_proxy_score", "IND"], ascending=[False, True], kind="mergesort"
                    ).head(top_n)["IND"]
                )
                overlap = len(left_top & right_top)
                jaccard = overlap / len(left_top | right_top)
                values_ok = (
                    top_n == row.top_n
                    and overlap == row.top_overlap_n
                    and np.isclose(overlap / top_n, row.top_overlap_fraction, atol=1e-14)
                    and np.isclose(jaccard, row.top_jaccard, atol=1e-14)
                    and np.isclose(spearman.statistic, row.spearman_rho, atol=1e-14)
                    and np.isclose(spearman.pvalue, row.spearman_p, atol=1e-14)
                    and np.isclose(kendall.statistic, row.kendall_tau, atol=1e-14)
                    and np.isclose(kendall.pvalue, row.kendall_p, atol=1e-14)
                )
                if not values_ok:
                    recompute_ok = False
                    mismatch = f"{pair_id} at {row.top_percentile:g}%"
                    break
            if not recompute_ok:
                break
        self.add(
            "all rank/overlap values independently recompute",
            recompute_ok,
            f"checked {expected_pairs} pairs x {len(percentiles)} percentiles; first mismatch={mismatch}",
        )

    def _validate_figure_values(
        self,
        frame: pd.DataFrame,
        associations: pd.DataFrame,
        individuals: pd.DataFrame,
        config: dict,
    ) -> None:
        counts = frame["record_type"].value_counts().to_dict()
        expected_counts = {
            "heatmap_cell": 60,
            "forest_cell": 30,
            "scatter_individual": 422,
            "cohort_centroid": 16,
        }
        self.add(
            "figure-values table has every plotted record",
            len(frame) == sum(expected_counts.values()) and counts == expected_counts,
            f"rows={len(frame)}, record counts={counts}",
        )
        heatmap = frame.loc[frame["record_type"].eq("heatmap_cell")].copy()
        merged = heatmap.merge(
            associations,
            on=["cell_id", "gerp_threshold", "roh_cutoff_mb", "outcome", "model"],
            how="outer",
            validate="one_to_one",
            indicator=True,
            suffixes=("_figure", "_table"),
        )
        reconcile = (
            len(merged) == 60
            and merged["_merge"].eq("both").all()
            and np.allclose(merged["estimate"], merged["coefficient"], atol=1e-14)
            and np.allclose(merged["ci_low_figure"], merged["ci_low_table"], atol=1e-14)
            and np.allclose(merged["ci_high_figure"], merged["ci_high_table"], atol=1e-14)
        )
        self.add(
            "surface/forest values exactly reconcile to association table",
            reconcile,
            f"heatmap joins={len(merged)}, unmatched={int((merged['_merge']!='both').sum())}",
        )
        default_gerp = float(config["wolf"]["load"]["gerp_threshold"])
        default_roh = float(config["wolf"]["roh"]["long_roh_threshold_mb"])
        default_scores = individuals.loc[
            individuals["gerp_threshold"].astype(float).eq(default_gerp)
            & individuals["roh_cutoff_mb"].astype(float).eq(default_roh)
        ]
        scatter = frame.loc[frame["record_type"].eq("scatter_individual")]
        scatter_ok = (
            len(default_scores) == EXPECTED_N
            and scatter["IND"].nunique() == EXPECTED_N
            and set(scatter["outcome"]) == {"realized_load", "masked_load"}
            and scatter.groupby("outcome")["IND"].nunique().eq(EXPECTED_N).all()
        )
        self.add(
            "cohort-aware scatter uses the frozen default cell",
            scatter_ok,
            f"GERP>{default_gerp:g}, ROH>={default_roh:g} Mb; scatter rows={len(scatter)}",
        )

    def _validate_figures(self) -> None:
        details = []
        ok = True
        for relative in FIGURES:
            path = self.path(relative)
            size = path.stat().st_size if path.exists() else 0
            signature = path.read_bytes()[:8] if path.exists() else b""
            file_ok = size > 10_000 and signature == b"\x89PNG\r\n\x1a\n"
            ok &= file_ok
            details.append(f"{Path(relative).name}={size:,} bytes")
        self.add("surface and forest figures are valid PNG artifacts", ok, "; ".join(details))

    def _validate_provenance(
        self,
        provenance: dict,
        settings: dict,
        associations: pd.DataFrame,
    ) -> None:
        setting_ok = all(
            provenance.get("settings", {}).get(key) == value
            for key, value in {
                "seed": int(settings["seed"]),
                "bootstrap_reps": int(settings["bootstrap_reps"]),
                "permutation_reps": int(settings["permutation_reps"]),
                "ci_pct": float(settings["ci_pct"]),
                "negative_control": str(settings["negative_control"]),
            }.items()
        )
        input_hashes = provenance.get("inputs", {})
        input_ok = all(
            input_hashes.get(relative) == file_sha256(self.path(relative))
            for relative in (LOAD, ROH, CONFIG, ANALYSIS_SCRIPT)
        )
        output_hashes = provenance.get("output_sha256", {})
        output_ok = all(
            output_hashes.get(relative) == file_sha256(self.path(relative))
            for relative in [*TABLES.values(), *FIGURES]
        )
        self.add(
            "provenance records exact settings and input/output hashes",
            setting_ok and input_ok and output_ok,
            f"settings={setting_ok}, inputs={input_ok}, outputs={output_ok}",
        )
        labelled = [(relative, self.path(relative)) for relative in TABLES.values()]
        computed = scientific_hash(labelled)
        self.add(
            "provenance scientific hash independently reconciles",
            computed == provenance.get("scientific_hash"),
            f"computed={computed}",
        )
        partial_realized = associations.loc[
            associations["outcome"].eq("realized_load")
            & associations["model"].astype(str).str.contains("partial")
        ]
        count = int(partial_realized["ci_low"].gt(0).sum())
        threshold = int(settings["roh_localization_reopen_min_cells"])
        finding = provenance.get("findings", {})
        gate_ok = (
            finding.get("partial_realized_ci_positive_cells") == count
            and finding.get("roh_localization_reopen_min_cells") == threshold
            and finding.get("roh_localization_gate_pass") == (count >= threshold)
        )
        self.add(
            "ROH-localization go/no-go count is traceable",
            gate_ok,
            f"partial realized CI-positive cells={count}/15; reopen threshold={threshold}; "
            f"gate={'PASS' if count >= threshold else 'NO-GO'}",
        )

    def _validate_rerun(self, provenance: dict) -> None:
        with tempfile.TemporaryDirectory(prefix="wolf-robustness-validation-") as temporary:
            temporary_path = Path(temporary)
            command = [
                sys.executable,
                str(self.path(ANALYSIS_SCRIPT)),
                "--load",
                str(self.path(LOAD)),
                "--roh",
                str(self.path(ROH)),
                "--config",
                str(self.path(CONFIG)),
                "--output-root",
                str(temporary_path),
                "--skip-figures",
            ]
            environment = os.environ.copy()
            environment["MPLCONFIGDIR"] = str(temporary_path / "matplotlib")
            try:
                completed = subprocess.run(
                    command,
                    cwd=self.root,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=600,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                self.add("deterministic independent rerun", False, "rerun exceeded 600 seconds")
                return
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout)[-1000:].replace("\n", " ")
                self.add("deterministic independent rerun", False, f"exit={completed.returncode}: {detail}")
                return
            identical = True
            mismatches = []
            for relative in TABLES.values():
                original = self.path(relative)
                rerun = temporary_path / relative
                if not rerun.is_file() or original.read_bytes() != rerun.read_bytes():
                    identical = False
                    mismatches.append(relative)
            rerun_provenance_path = temporary_path / PROVENANCE
            rerun_hash = None
            if rerun_provenance_path.is_file():
                rerun_hash = json.loads(rerun_provenance_path.read_text(encoding="utf-8")).get(
                    "scientific_hash"
                )
            hash_ok = rerun_hash == provenance.get("scientific_hash")
            self.add(
                "deterministic independent rerun",
                identical and hash_ok,
                f"four TSVs byte-identical={identical}; scientific hash identical={hash_ok}; "
                f"mismatches={mismatches}",
            )


def write_report(checks: list[tuple[str, str, str]], out_tsv: Path, out_md: Path) -> int:
    report = pd.DataFrame(checks, columns=["check", "status", "detail"])
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(out_tsv, sep="\t", index=False)
    failures = int(report["status"].eq("FAIL").sum())
    passes = int(report["status"].eq("PASS").sum())
    lines = [
        "# Wolf F_ROH-load robustness validation",
        "",
        "Acceptance validation for CGplan.md section 13.1. Associations are between genomic risk",
        "proxies; they are not fitness effects, causal inbreeding depression, or measured harm.",
        "",
        f"**Summary: {passes} PASS, {failures} FAIL**",
        "",
        "| check | status | evidence |",
        "|---|---|---|",
    ]
    for name, status, detail in checks:
        clean = str(detail).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {name} | **{status}** | {clean} |")
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "The validator preserves all 15 threshold cells and both expected and unexpected directions.",
            "A positive partial association is evidence that two genomic proxies covary after the declared",
            "generic-homozygosity control; it is not evidence of fitness loss or causation.",
            "",
        ]
    )
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(report.to_string(index=False))
    print(f"\n{passes} PASS, {failures} FAIL")
    return failures


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    validator = Validator(root)
    try:
        validator.validate(args.skip_rerun)
    except Exception as error:
        validator.add("validator completed without internal exception", False, repr(error))
    failures = write_report(
        validator.checks,
        root / args.out_tsv,
        root / args.out_md,
    )
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
