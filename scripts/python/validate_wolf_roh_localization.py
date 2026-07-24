#!/usr/bin/env python3
"""Independent acceptance validator for Phase-5B wolf ROH localization.

This validator deliberately does not import the analysis implementation.  It
rebuilds ROH unions from the raw bcftools ``RG`` records, reconciles burden and
eligible SNP-genotype opportunity to the Phase-4 tables, independently audits
raw VCF/GERP/ROH interval assignment on a deterministic broad panel, reconstructs
a bounded raw circular-shift null sample, recomputes the cohort summaries,
validates figure values/provenance, and (by
default) re-runs only the deterministic collation stage in a temporary
directory.  It never re-runs the expensive chromosome VCF workers.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Iterable

import numpy as np
import pandas as pd
import yaml


EXPECTED_N = 211
FLOAT_TOL = 1e-6

DEFAULTS = {
    "config": "config/config.yaml",
    "wolf_load": "results/tables/wolf_load.tsv",
    "wolf_roh": "results/tables/wolf_roh.tsv",
    "lengths": "results/wolf/autosome_lengths.tsv",
    "samples": "results/wolf/samples.txt",
    "popmap": "results/wolf/popmap.tsv",
    "vcf": "data/wolf/vcf/Pol.2out.mac2/100S95F14R.chr1-38.allSNPs.wfm.vcf.gz",
    "roh_dir": "results/wolf/roh",
    "intermediate_dir": "results/wolf/localization",
    "analysis_script": "scripts/python/wolf_roh_localization.py",
    "decision_table": "results/tables/phase5b_optional_decisions.tsv",
    "decision_validation": "results/tables/validation_phase5b_decisions.tsv",
    "individual": "results/tables/wolf_roh_localization_individual.tsv",
    "cohort": "results/tables/wolf_roh_localization_cohort.tsv",
    "null": "results/tables/wolf_roh_localization_null.tsv",
    "qc": "results/tables/wolf_roh_localization_qc.tsv",
    "figure_values": "results/tables/wolf_roh_localization_figure_values.tsv",
    "forest": "results/figures/wolf_roh_localization_forest.png",
    "ribbon": "results/figures/wolf_roh_localization_ribbon.png",
    "provenance": "results/provenance/wolf_roh_localization.json",
    "out_tsv": "results/tables/validation_wolf_roh_localization.tsv",
    "out_md": "results/WOLF_ROH_LOCALIZATION_VALIDATION.md",
}

SCIENTIFIC_TABLES = ["individual", "cohort", "null", "qc", "figure_values"]
FIGURES = ["forest", "ribbon"]

INDIVIDUAL_COLUMNS = {
    "IND", "POP", "gerp_threshold", "roh_cutoff_mb", "n_roh",
    "roh_raw_span_bp", "roh_union_bp", "roh_overlap_bp", "froh_recomputed",
    "F_ROH_phase4", "froh_delta", "inside_eligible_genotype_calls",
    "outside_eligible_genotype_calls", "total_eligible_genotype_calls",
    "inside_hom_derived_copies", "outside_hom_derived_copies",
    "total_hom_derived_copies", "inside_hom_del_sum",
    "outside_hom_del_sum", "total_hom_del_sum", "all_polarized_gerp_genotype_calls",
    "inside_burden_rate", "outside_burden_rate", "rate_ratio",
    "log2_enrichment", "phase4_burden_delta", "phase4_copy_delta",
    "phase4_genotype_call_delta", "status", "failure_reason",
}

COHORT_COLUMNS = {
    "POP", "gerp_threshold", "roh_cutoff_mb", "n_ind",
    "inside_eligible_genotype_calls", "outside_eligible_genotype_calls",
    "inside_hom_derived_copies", "outside_hom_derived_copies",
    "inside_hom_del_sum", "outside_hom_del_sum", "inside_burden_rate",
    "outside_burden_rate", "rate_ratio", "log2_enrichment",
    "null_valid_reps", "null_failed_reps", "null_median_log2_enrichment",
    "null_ci_low", "null_ci_high", "observed_minus_null_median",
    "permutation_p_two_sided", "direction", "status", "failure_reason",
}

NULL_COLUMNS = {
    "POP", "replicate", "base_seed", "gerp_threshold", "roh_cutoff_mb",
    "inside_eligible_genotype_calls", "outside_eligible_genotype_calls",
    "total_eligible_genotype_calls", "inside_hom_derived_copies",
    "outside_hom_derived_copies", "total_hom_derived_copies",
    "inside_hom_del_sum", "outside_hom_del_sum", "total_hom_del_sum",
    "inside_burden_rate", "outside_burden_rate", "rate_ratio",
    "log2_enrichment", "status", "failure_reason",
}

OBSERVED_INTERMEDIATE_COLUMNS = {
    "chrom", "IND", "POP", "gerp_threshold", "roh_cutoff_mb", "n_roh",
    "roh_raw_span_bp", "roh_union_bp", "roh_overlap_bp",
    "inside_eligible_genotype_calls", "outside_eligible_genotype_calls",
    "total_eligible_genotype_calls", "inside_hom_derived_copies",
    "outside_hom_derived_copies", "total_hom_derived_copies",
    "inside_hom_del_sum", "outside_hom_del_sum", "total_hom_del_sum",
    "all_polarized_gerp_genotype_calls",
}

NULL_INTERMEDIATE_COLUMNS = {
    "chrom", "POP", "replicate", "base_seed", "chrom_seed",
    "gerp_threshold", "roh_cutoff_mb", "inside_eligible_genotype_calls",
    "outside_eligible_genotype_calls", "total_eligible_genotype_calls",
    "inside_hom_derived_copies", "outside_hom_derived_copies",
    "total_hom_derived_copies", "inside_hom_del_sum",
    "outside_hom_del_sum", "total_hom_del_sum", "status", "failure_reason",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run synthetic independent-null acceptance and perturbation regressions",
    )
    parser.add_argument("--root", default=".")
    for key in (
        "config", "wolf_load", "wolf_roh", "lengths", "samples", "popmap", "vcf", "roh_dir",
        "intermediate_dir", "analysis_script", "decision_table",
        "decision_validation", "individual", "cohort", "null", "qc",
        "figure_values", "forest", "ribbon", "provenance", "out_tsv", "out_md",
    ):
        parser.add_argument(f"--{key.replace('_', '-')}", default=DEFAULTS[key])
    parser.add_argument(
        "--skip-rerun",
        action="store_true",
        help="Skip temporary deterministic re-collation (not valid for acceptance)",
    )
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_portable_executable(
    token: str, python_executable: Path | None = None
) -> Path | None:
    """Resolve a separator-free command exactly as the analysis does."""
    token = token.strip()
    if not token or token != Path(token).name:
        return None
    sibling = Path(python_executable or sys.executable).with_name(token)
    if sibling.is_file():
        return sibling
    discovered = shutil.which(token)
    return Path(discovered) if discovered else None


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


def maximum_absolute(values: pd.Series | np.ndarray) -> float:
    array = np.asarray(values, dtype=float)
    if array.size == 0:
        return 0.0
    if not np.isfinite(array).all():
        return float("inf")
    return float(np.max(np.abs(array)))


def read_lengths(path: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            fields = line.split()
            if len(fields) >= 2:
                result[str(fields[0])] = int(fields[1])
    return result


def bcftools_executable() -> Path:
    """Resolve bcftools without importing or invoking the analysis implementation."""
    sibling = Path(sys.executable).with_name("bcftools")
    if sibling.is_file():
        return sibling
    discovered = shutil.which("bcftools")
    if discovered:
        return Path(discovered)
    raise RuntimeError("bcftools is required for the independent raw interval audit")


def chromosome_number(path: Path) -> int:
    name = path.name
    return int(name.split(".", 1)[0].removeprefix("chr"))


def png_dimensions(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", header[16:24])


def merged_span(intervals: list[tuple[int, int]]) -> tuple[int, int]:
    """Return independent union length and overlap amount for half-open rows."""
    if not intervals:
        return 0, 0
    ordered = sorted(intervals)
    union = 0
    overlap = 0
    start, end = ordered[0]
    for next_start, next_end in ordered[1:]:
        if next_start <= end:
            if next_start < end:
                overlap += min(end, next_end) - next_start
            end = max(end, next_end)
        else:
            union += end - start
            start, end = next_start, next_end
    union += end - start
    return int(union), int(overlap)


def reconstruct_circular_null(
    records: Iterable[tuple[int, str, str, str, list[str]]],
    gerp: dict[int, float],
    sample_order: list[str],
    pop_lookup: dict[str, str],
    populations: list[str],
    intervals: dict[str, list[tuple[int, int, int]]],
    offsets: dict[str, int],
    chromosome_length: int,
    thresholds: list[float],
    cutoff_bp: np.ndarray,
) -> dict[str, object]:
    """Independently reconstruct one chromosome/replicate null allocation.

    This is intentionally implemented in the validator rather than imported
    from the analysis. Raw ROH coordinates are zero-based half-open here;
    records use one-based VCF positions.
    """
    if len(sample_order) != len(set(sample_order)):
        raise ValueError("independent null audit sample order contains duplicates")
    if set(sample_order) != set(pop_lookup) or set(sample_order) != set(intervals):
        raise ValueError("independent null audit samples/populations/intervals disagree")
    if set(sample_order) != set(offsets):
        raise ValueError("independent null audit has incomplete offsets")
    if chromosome_length <= 0:
        raise ValueError("independent null audit chromosome length is non-positive")

    population_index = {population: index for index, population in enumerate(populations)}
    n_pop = len(populations)
    n_threshold = len(thresholds)
    n_cutoff = len(cutoff_bp)
    total_calls = np.zeros((n_pop, n_threshold), dtype=np.int64)
    total_copies = np.zeros_like(total_calls)
    total_burden = np.zeros((n_pop, n_threshold), dtype=np.float64)
    inside_calls = np.zeros((n_pop, n_threshold, n_cutoff), dtype=np.int64)
    inside_copies = np.zeros_like(inside_calls)
    inside_burden = np.zeros((n_pop, n_threshold, n_cutoff), dtype=np.float64)

    shifted: dict[str, list[list[tuple[int, int]]]] = {}
    wrapped_interval_cutoff_assignments = 0
    for sample in sample_order:
        sample_cutoffs: list[list[tuple[int, int]]] = []
        offset = int(offsets[sample])
        if not 0 <= offset < chromosome_length:
            raise ValueError(f"invalid independent null offset for {sample}: {offset}")
        for minimum in cutoff_bp:
            segments: list[tuple[int, int]] = []
            for start, end, reported_length in intervals[sample]:
                if reported_length != end - start:
                    raise ValueError(f"raw ROH length mismatch for {sample}")
                if not (0 <= start < end <= chromosome_length):
                    raise ValueError(f"raw ROH bounds failure for {sample}")
                if reported_length < int(minimum):
                    continue
                shifted_start = (start + offset) % chromosome_length
                shifted_end = shifted_start + reported_length
                if shifted_end <= chromosome_length:
                    segments.append((shifted_start, shifted_end))
                else:
                    segments.extend(
                        [(shifted_start, chromosome_length), (0, shifted_end - chromosome_length)]
                    )
                    wrapped_interval_cutoff_assignments += 1
            segments.sort()
            if any(right[0] < left[1] for left, right in zip(segments, segments[1:])):
                raise ValueError(f"circular shift created overlapping ROH segments for {sample}")
            sample_cutoffs.append(segments)
        shifted[sample] = sample_cutoffs

    pointers = np.zeros((len(sample_order), n_cutoff), dtype=np.int64)
    audit = defaultdict(int)
    previous_position = 0
    for position, ref, alt, ancestral, genotypes in records:
        if not (1 <= int(position) <= chromosome_length) or int(position) < previous_position:
            raise ValueError(f"invalid or unsorted raw VCF position: {position}")
        previous_position = int(position)
        audit["vcf_records"] += 1
        score = gerp.get(int(position))
        if score is None:
            continue
        if not math.isfinite(float(score)):
            raise ValueError(f"non-finite GERP score at {position}")
        audit["gerp_matched_records"] += 1
        ref = str(ref).upper()
        alt = str(alt).upper()
        ancestral = str(ancestral).upper()
        if ancestral == ref:
            derived_is_alt = True
            audit["aa_ref_records"] += 1
        elif "," not in alt and ancestral == alt:
            derived_is_alt = False
            audit["aa_alt_records"] += 1
        else:
            audit["invalid_aa_records"] += 1
            continue
        qualifying = [
            index for index, threshold in enumerate(thresholds)
            if float(score) > float(threshold)
        ]
        if not qualifying:
            continue
        if len(genotypes) != len(sample_order):
            raise ValueError(
                f"independent null VCF width {len(genotypes)} != {len(sample_order)} samples"
            )
        position0 = int(position) - 1
        for sample_index, genotype in enumerate(genotypes):
            alleles = str(genotype).replace("|", "/").split("/")
            if len(alleles) != 2 or any(allele not in {"0", "1"} for allele in alleles):
                continue
            sample = sample_order[sample_index]
            population = pop_lookup[sample]
            if population not in population_index:
                raise ValueError(f"population {population} absent from independent null audit")
            pop_index = population_index[population]
            n_alt = int(alleles[0] == "1") + int(alleles[1] == "1")
            homozygous_derived = (
                (derived_is_alt and n_alt == 2)
                or (not derived_is_alt and n_alt == 0)
            )
            inside = np.zeros(n_cutoff, dtype=bool)
            for cutoff_index, segments in enumerate(shifted[sample]):
                pointer = int(pointers[sample_index, cutoff_index])
                while pointer < len(segments) and segments[pointer][1] <= position0:
                    pointer += 1
                pointers[sample_index, cutoff_index] = pointer
                inside[cutoff_index] = (
                    pointer < len(segments)
                    and segments[pointer][0] <= position0 < segments[pointer][1]
                )
            audit["eligible_polarized_genotype_calls"] += 1
            for threshold_index in qualifying:
                total_calls[pop_index, threshold_index] += 1
                inside_calls[pop_index, threshold_index, inside] += 1
                if homozygous_derived:
                    total_copies[pop_index, threshold_index] += 2
                    total_burden[pop_index, threshold_index] += 2.0 * float(score)
                    inside_copies[pop_index, threshold_index, inside] += 2
                    inside_burden[pop_index, threshold_index, inside] += 2.0 * float(score)
                    audit["homozygous_derived_calls"] += 1

    audit["wrapped_interval_cutoff_assignments"] = wrapped_interval_cutoff_assignments
    return {
        "inside_calls": inside_calls,
        "total_calls": total_calls,
        "inside_copies": inside_copies,
        "total_copies": total_copies,
        "inside_burden": inside_burden,
        "total_burden": total_burden,
        "audit": dict(audit),
    }


def compare_circular_null(
    frame: pd.DataFrame,
    reconstructed: dict[str, object],
    chromosome: str,
    replicate: int,
    base_seed: int,
    chromosome_seed: int,
    populations: list[str],
    thresholds: list[float],
    cutoffs: list[float],
) -> dict[str, object]:
    """Compare a raw independent reconstruction with production null rows."""
    required = NULL_INTERMEDIATE_COLUMNS
    if required - set(frame.columns):
        return {
            "ok": False, "comparisons": 0, "max_integer_delta": math.inf,
            "max_burden_delta": math.inf, "metadata_ok": False,
        }
    subset = frame.loc[
        frame["chrom"].astype(str).eq(str(chromosome))
        & frame["replicate"].astype(int).eq(int(replicate))
        & frame["POP"].astype(str).isin(populations)
    ].copy()
    expected_keys = {
        (population, float(threshold), float(cutoff))
        for population in populations for threshold in thresholds for cutoff in cutoffs
    }
    actual_keys = set(
        zip(
            subset["POP"].astype(str),
            subset["gerp_threshold"].astype(float),
            subset["roh_cutoff_mb"].astype(float),
        )
    )
    grouped = subset.groupby(["POP", "gerp_threshold", "roh_cutoff_mb"]).size()
    cardinality_ok = (
        len(subset) == len(expected_keys)
        and actual_keys == expected_keys
        and grouped.eq(1).all()
    )
    if not cardinality_ok:
        return {
            "ok": False, "comparisons": len(subset), "max_integer_delta": math.inf,
            "max_burden_delta": math.inf, "metadata_ok": False,
        }

    indexed = subset.set_index(["POP", "gerp_threshold", "roh_cutoff_mb"])
    pop_index = {population: index for index, population in enumerate(populations)}
    integer_delta = 0
    burden_delta = 0.0
    metadata_ok = True
    reasons = subset["failure_reason"].fillna("").astype(str)
    metadata_ok &= subset["base_seed"].astype(int).eq(int(base_seed)).all()
    metadata_ok &= subset["chrom_seed"].astype(int).eq(int(chromosome_seed)).all()
    metadata_ok &= subset["status"].astype(str).eq("ok").all() and reasons.eq("").all()

    inside_calls = np.asarray(reconstructed["inside_calls"])
    total_calls = np.asarray(reconstructed["total_calls"])
    inside_copies = np.asarray(reconstructed["inside_copies"])
    total_copies = np.asarray(reconstructed["total_copies"])
    inside_burden = np.asarray(reconstructed["inside_burden"])
    total_burden = np.asarray(reconstructed["total_burden"])
    for population in populations:
        pi = pop_index[population]
        for threshold_index, threshold in enumerate(thresholds):
            for cutoff_index, cutoff in enumerate(cutoffs):
                row = indexed.loc[(population, threshold, cutoff)]
                expected_integer = {
                    "inside_eligible_genotype_calls": int(
                        inside_calls[pi, threshold_index, cutoff_index]
                    ),
                    "outside_eligible_genotype_calls": int(
                        total_calls[pi, threshold_index]
                        - inside_calls[pi, threshold_index, cutoff_index]
                    ),
                    "total_eligible_genotype_calls": int(total_calls[pi, threshold_index]),
                    "inside_hom_derived_copies": int(
                        inside_copies[pi, threshold_index, cutoff_index]
                    ),
                    "outside_hom_derived_copies": int(
                        total_copies[pi, threshold_index]
                        - inside_copies[pi, threshold_index, cutoff_index]
                    ),
                    "total_hom_derived_copies": int(total_copies[pi, threshold_index]),
                }
                for field, expected in expected_integer.items():
                    integer_delta = max(integer_delta, abs(int(row[field]) - expected))
                expected_burden = {
                    "inside_hom_del_sum": float(
                        inside_burden[pi, threshold_index, cutoff_index]
                    ),
                    "outside_hom_del_sum": float(
                        total_burden[pi, threshold_index]
                        - inside_burden[pi, threshold_index, cutoff_index]
                    ),
                    "total_hom_del_sum": float(total_burden[pi, threshold_index]),
                }
                for field, expected in expected_burden.items():
                    burden_delta = max(burden_delta, abs(float(row[field]) - expected))
    return {
        "ok": metadata_ok and integer_delta == 0 and burden_delta <= FLOAT_TOL,
        "comparisons": len(subset),
        "max_integer_delta": integer_delta,
        "max_burden_delta": burden_delta,
        "metadata_ok": bool(metadata_ok),
    }


def run_self_test() -> None:
    """Public regression: correct null passes; seed/allocation perturbations fail."""
    with tempfile.TemporaryDirectory(prefix="wolf-localization-executable-") as raw_tmp:
        tmp = Path(raw_tmp)
        fake_python = tmp / "python"
        sibling_tabix = tmp / "tabix"
        fake_python.write_bytes(b"python")
        sibling_tabix.write_bytes(b"tabix")
        assert resolve_portable_executable(
            "tabix", python_executable=fake_python
        ) == sibling_tabix
        assert resolve_portable_executable(
            str(sibling_tabix), python_executable=fake_python
        ) is None

    thresholds = [2.0, 4.0]
    cutoffs = [1.0, 4.0, 5.0]
    cutoff_bp = np.asarray([1, 4, 5], dtype=np.int64)
    samples = ["A", "B"]
    populations = ["X", "Y"]
    pop_lookup = {"A": "X", "B": "Y"}
    intervals = {"A": [(1, 5, 4)], "B": [(10, 14, 4)]}
    records = [
        (1, "A", "G", "A", ["1/1", "0/0"]),
        (17, "C", "T", "C", ["0/0", "1/1"]),
    ]
    gerp = {1: 5.0, 17: 5.0}
    base_seed = 1304
    replicate = 1
    chromosome = "fixture"
    chromosome_seed = stable_seed(base_seed, f"chromosome|{chromosome}")
    correct_draws = np.random.default_rng(chromosome_seed).integers(
        0, 20, size=(3, len(samples)), dtype=np.int64
    )
    assert correct_draws.tolist() == [[19, 18], [18, 6], [14, 18]]
    correct = reconstruct_circular_null(
        records, gerp, samples, pop_lookup, populations, intervals,
        dict(zip(samples, correct_draws[replicate], strict=True)),
        20, thresholds, cutoff_bp,
    )

    rows = []
    for population in populations:
        for threshold in thresholds:
            for cutoff in cutoffs:
                inside_call = 1 if cutoff <= 4 else 0
                inside_copy = 2 if cutoff <= 4 else 0
                inside_weight = 10.0 if cutoff <= 4 else 0.0
                rows.append(
                    {
                        "chrom": chromosome, "POP": population, "replicate": replicate,
                        "base_seed": base_seed, "chrom_seed": chromosome_seed,
                        "gerp_threshold": threshold, "roh_cutoff_mb": cutoff,
                        "inside_eligible_genotype_calls": inside_call,
                        "outside_eligible_genotype_calls": 2 - inside_call,
                        "total_eligible_genotype_calls": 2,
                        "inside_hom_derived_copies": inside_copy,
                        "outside_hom_derived_copies": 2 - inside_copy,
                        "total_hom_derived_copies": 2,
                        "inside_hom_del_sum": inside_weight,
                        "outside_hom_del_sum": 10.0 - inside_weight,
                        "total_hom_del_sum": 10.0,
                        "status": "ok", "failure_reason": "",
                    }
                )
    expected = pd.DataFrame(rows)
    accepted = compare_circular_null(
        expected, correct, chromosome, replicate, base_seed, chromosome_seed,
        populations, thresholds, cutoffs,
    )
    assert accepted["ok"] and accepted["comparisons"] == 12

    wrong_base_seed = base_seed + 1
    wrong_chromosome_seed = stable_seed(wrong_base_seed, f"chromosome|{chromosome}")
    wrong_draws = np.random.default_rng(wrong_chromosome_seed).integers(
        0, 20, size=(3, len(samples)), dtype=np.int64
    )
    wrong_seed = reconstruct_circular_null(
        records, gerp, samples, pop_lookup, populations, intervals,
        dict(zip(samples, wrong_draws[replicate], strict=True)),
        20, thresholds, cutoff_bp,
    )
    rejected_seed = compare_circular_null(
        expected, wrong_seed, chromosome, replicate, wrong_base_seed,
        wrong_chromosome_seed, populations, thresholds, cutoffs,
    )
    assert not rejected_seed["ok"]
    assert (
        not rejected_seed["metadata_ok"]
        and (
            rejected_seed["max_integer_delta"] > 0
            or rejected_seed["max_burden_delta"] > 0
        )
    )

    perturbed = expected.copy()
    perturbed.loc[0, "inside_hom_derived_copies"] -= 2
    perturbed.loc[0, "outside_hom_derived_copies"] += 2
    perturbed.loc[0, "inside_hom_del_sum"] -= 10.0
    perturbed.loc[0, "outside_hom_del_sum"] += 10.0
    rejected_allocation = compare_circular_null(
        perturbed, correct, chromosome, replicate, base_seed, chromosome_seed,
        populations, thresholds, cutoffs,
    )
    assert not rejected_allocation["ok"]
    assert rejected_allocation["max_integer_delta"] == 2
    assert rejected_allocation["max_burden_delta"] == 10.0
    print("validate_wolf_roh_localization independent-null self-test: OK")


class Validator:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.root = Path(args.root).resolve()
        self.checks: list[tuple[str, str, str]] = []
        self.paths = {
            key: self._resolve(getattr(args, key))
            for key in DEFAULTS
            if key not in {"out_tsv", "out_md"}
        }
        self.observed_paths: list[Path] = []
        self.null_paths: list[Path] = []
        self.chrom_qc_paths: list[Path] = []

    def _resolve(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    def add(self, name: str, condition: bool, detail: str) -> None:
        self.checks.append((name, "PASS" if bool(condition) else "FAIL", detail))

    def validate(self) -> None:
        required = [
            "config", "wolf_load", "wolf_roh", "lengths", "samples", "popmap", "vcf",
            "analysis_script", "decision_table", "decision_validation",
            "individual", "cohort", "null", "qc", "figure_values", "forest",
            "ribbon", "provenance",
        ]
        missing = [key for key in required if not self.paths[key].is_file()]
        if not self.paths["roh_dir"].is_dir():
            missing.append("roh_dir")
        if not self.paths["intermediate_dir"].is_dir():
            missing.append("intermediate_dir")
        self.add(
            "all ROH-localization inputs and final artifacts exist",
            not missing,
            f"missing={missing}" if missing else f"{len(required) + 2} required paths",
        )
        if missing:
            return

        config = yaml.safe_load(self.paths["config"].read_text(encoding="utf-8"))
        settings = config["phase5b"]["roh_localization"]
        chromosomes = [str(value) for value in range(1, int(config["wolf"]["n_autosomes"]) + 1)]
        thresholds = sorted(float(value) for value in config["wolf"]["load"]["gerp_sensitivity"])
        cutoffs = sorted(float(value) for value in config["wolf"]["roh"]["length_cutoffs_mb"])
        reps = int(settings["permutation_reps"])
        popmap = pd.read_csv(
            self.paths["popmap"], sep="\t", header=None, names=["IND", "POP"], dtype=str
        )
        populations = sorted(popmap["POP"].unique())
        expected_cells = {(threshold, cutoff) for threshold in thresholds for cutoff in cutoffs}

        self._discover_intermediates(chromosomes)
        load = pd.read_csv(self.paths["wolf_load"], sep="\t", float_precision="round_trip")
        roh = pd.read_csv(self.paths["wolf_roh"], sep="\t", float_precision="round_trip")
        individual = pd.read_csv(self.paths["individual"], sep="\t", float_precision="round_trip")
        cohort = pd.read_csv(self.paths["cohort"], sep="\t", float_precision="round_trip")
        null = pd.read_csv(self.paths["null"], sep="\t", float_precision="round_trip")
        qc = pd.read_csv(self.paths["qc"], sep="\t", float_precision="round_trip")
        figure_values = pd.read_csv(
            self.paths["figure_values"], sep="\t", float_precision="round_trip"
        )
        provenance = json.loads(self.paths["provenance"].read_text(encoding="utf-8"))

        self._validate_gate(provenance)
        self._validate_frozen_design(
            settings, thresholds, cutoffs, chromosomes, popmap, load, roh
        )
        self._validate_intermediates(
            chromosomes, thresholds, cutoffs, populations, reps, settings, popmap
        )
        self._validate_individual(
            individual, load, roh, expected_cells, thresholds, cutoffs, popmap
        )
        self._validate_raw_rg(individual, roh, chromosomes, cutoffs, popmap)
        self._validate_raw_interval_assignment(
            thresholds, cutoffs, chromosomes, popmap
        )
        self._validate_raw_null_assignment(
            settings, thresholds, cutoffs, chromosomes, popmap
        )
        self._validate_null(null, cohort, populations, thresholds, cutoffs, reps, settings)
        self._validate_cohort(cohort, individual, null, populations, thresholds, cutoffs, settings)
        self._validate_qc(qc, chromosomes, settings)
        self._validate_figure_values(
            figure_values, cohort, populations, thresholds, cutoffs, config
        )
        self._validate_figures()
        self._validate_provenance(provenance, settings, thresholds, cutoffs, individual, cohort, null, qc)
        self._validate_independent_null_self_test()
        self._validate_analysis_self_check()
        if self.args.skip_rerun:
            self.add(
                "deterministic temporary re-collation",
                False,
                "acceptance re-collation explicitly skipped",
            )
        else:
            self._validate_rerun(provenance)

    def _validate_analysis_self_check(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wolf-roh-localization-self-check-") as temporary:
            environment = os.environ.copy()
            environment["MPLCONFIGDIR"] = str(Path(temporary) / "mpl")
            result = subprocess.run(
                [sys.executable, str(self.paths["analysis_script"]), "self-check"],
                cwd=self.root, env=environment, capture_output=True, text=True,
                timeout=120, check=False,
            )
        self.add(
            "synthetic coordinate, circular-shift, nested-cutoff, and gate tests pass",
            result.returncode == 0 and "self-check: OK" in result.stdout,
            f"returncode={result.returncode}",
        )

    def _validate_independent_null_self_test(self) -> None:
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--self-test"],
            cwd=self.root, env=environment, capture_output=True, text=True,
            timeout=120, check=False,
        )
        self.add(
            "independent-null seed and allocation perturbation regressions pass",
            result.returncode == 0
            and "independent-null self-test: OK" in result.stdout,
            f"returncode={result.returncode}",
        )

    def _validate_gate(self, provenance: dict) -> None:
        decisions = pd.read_csv(self.paths["decision_table"], sep="\t")
        validation = pd.read_csv(self.paths["decision_validation"], sep="\t")
        row = decisions.loc[decisions["section"].astype(str).eq("13.4")]
        gate_ok = False
        detail = f"13.4 rows={len(row)}"
        if len(row) == 1:
            decision = row.iloc[0]
            gate_ok = (
                str(decision["decision"]) == "IMPLEMENT"
                and str(decision["required_operator"]) == ">="
                and float(decision["observed_value"]) >= float(decision["required_value"])
                and int(decision["denominator"]) == 15
                and 0 <= float(decision["observed_value"]) <= 15
                and 0 <= float(decision["required_value"]) <= 15
                and "status" in validation
                and not validation.empty
                and validation["status"].eq("PASS").all()
                and int(
                    validation.get("check", pd.Series(dtype=str))
                    .astype(str)
                    .eq("13.4 decision exactly follows the predeclared negative-control gate")
                    .sum()
                )
                == 1
            )
            detail = (
                f"decision={decision['decision']}; observed={decision['observed_value']} "
                f">= {decision['required_value']}; decision validation "
                f"PASS={int(validation['status'].eq('PASS').sum()) if 'status' in validation else 0}/{len(validation)}"
            )
        self.add("validated §13.4 offline decision explicitly authorizes IMPLEMENT", gate_ok, detail)
        declared = provenance.get("implementation_gate", {})
        provenance_ok = (
            gate_ok
            and declared.get("decision") == "IMPLEMENT"
            and float(declared.get("observed_value", float("nan"))) == float(row.iloc[0]["observed_value"])
            and float(declared.get("required_value", float("nan"))) == float(row.iloc[0]["required_value"])
            and declared.get("decision_table_sha256") == file_sha256(self.paths["decision_table"])
            and declared.get("decision_validation_sha256") == file_sha256(self.paths["decision_validation"])
        )
        self.add(
            "final provenance directly hashes the validated implementation gate",
            provenance_ok,
            f"gate provenance present={bool(declared)}",
        )

    def _discover_intermediates(self, chromosomes: list[str]) -> None:
        directory = self.paths["intermediate_dir"]
        expected_observed = [directory / f"chr{chrom}.observed.tsv" for chrom in chromosomes]
        expected_null = [directory / f"chr{chrom}.null.tsv" for chrom in chromosomes]
        expected_qc = [directory / f"chr{chrom}.qc.tsv" for chrom in chromosomes]
        missing = [str(path.relative_to(self.root)) for path in [*expected_observed, *expected_null, *expected_qc] if not path.is_file()]
        self.add(
            "all 38 chromosome observed/null/QC intermediates exist",
            not missing,
            f"missing={missing[:8]}{'...' if len(missing) > 8 else ''}" if missing else "114 files",
        )
        self.observed_paths = expected_observed
        self.null_paths = expected_null
        self.chrom_qc_paths = expected_qc

    def _validate_frozen_design(
        self,
        settings: dict,
        thresholds: list[float],
        cutoffs: list[float],
        chromosomes: list[str],
        popmap: pd.DataFrame,
        load: pd.DataFrame,
        roh: pd.DataFrame,
    ) -> None:
        self.add(
            "frozen localization design is the declared 38 x 211 x 3 x 5 grid",
            len(chromosomes) == 38
            and len(popmap) == EXPECTED_N
            and popmap["IND"].nunique() == EXPECTED_N
            and thresholds == [2.0, 3.0, 4.0]
            and cutoffs == [0.1, 0.5, 1.0, 1.5, 2.0]
            and int(settings["permutation_reps"]) == 199,
            f"chromosomes={len(chromosomes)}, individuals={popmap['IND'].nunique()}, "
            f"thresholds={thresholds}, cutoffs={cutoffs}, reps={settings['permutation_reps']}",
        )
        self.add(
            "predeclared callable-opportunity circular-shift null is retained",
            str(settings["null_model"]) == "within_chromosome_circular_roh_shift"
            and str(settings["denominator"])
            == "eligible_polarized_gerp_threshold_snp_genotype_calls"
            and int(settings["seed"]) == 1304
            and float(settings["ci_pct"]) == 95.0,
            f"seed={settings['seed']}, null={settings['null_model']}, denominator={settings['denominator']}",
        )
        load_keys = load.groupby(["IND", "POP", "THRES"]).size()
        roh_keys = roh.groupby(["IND", "POP", "min_length_mb"]).size()
        self.add(
            "Phase-4 load and F_ROH source cubes are complete and unique",
            len(load) == EXPECTED_N * len(thresholds)
            and len(roh) == EXPECTED_N * len(cutoffs)
            and load_keys.eq(1).all()
            and roh_keys.eq(1).all()
            and set(load["IND"].astype(str)) == set(popmap["IND"])
            and set(roh["IND"].astype(str)) == set(popmap["IND"]),
            f"load rows={len(load)}, ROH rows={len(roh)}, duplicate keys="
            f"{int((load_keys > 1).sum())}/{int((roh_keys > 1).sum())}",
        )

    def _validate_intermediates(
        self,
        chromosomes: list[str],
        thresholds: list[float],
        cutoffs: list[float],
        populations: list[str],
        reps: int,
        settings: dict,
        popmap: pd.DataFrame,
    ) -> None:
        if any(not path.is_file() for path in [*self.observed_paths, *self.null_paths, *self.chrom_qc_paths]):
            self.add("chromosome intermediate schemas and cardinalities", False, "one or more files absent")
            return
        expected_cells = {(threshold, cutoff) for threshold in thresholds for cutoff in cutoffs}
        expected_obs_rows = EXPECTED_N * len(expected_cells)
        expected_null_rows = len(populations) * reps * len(expected_cells)
        phase4_ok = True
        schema_ok = True
        cardinality_ok = True
        arithmetic_ok = True
        seed_ok = True
        status_ok = True
        max_burden_delta = 0.0
        max_copy_delta = 0.0
        max_call_delta = 0.0
        decision_hash = file_sha256(self.paths["decision_table"])
        decision_validation_hash = file_sha256(self.paths["decision_validation"])
        phase4_dir = self.root / "results/wolf/load"
        pop_lookup = popmap.set_index("IND")["POP"].to_dict()
        for chrom, observed_path, null_path, qc_path in zip(
            chromosomes, self.observed_paths, self.null_paths, self.chrom_qc_paths, strict=True
        ):
            observed = pd.read_csv(observed_path, sep="\t", float_precision="round_trip")
            null = pd.read_csv(null_path, sep="\t", float_precision="round_trip")
            chrom_qc = pd.read_csv(qc_path, sep="\t", float_precision="round_trip")
            schema_ok &= OBSERVED_INTERMEDIATE_COLUMNS.issubset(observed.columns)
            schema_ok &= NULL_INTERMEDIATE_COLUMNS.issubset(null.columns)
            cardinality_ok &= len(observed) == expected_obs_rows and len(null) == expected_null_rows and len(chrom_qc) == 1
            cardinality_ok &= observed.groupby(["IND", "gerp_threshold", "roh_cutoff_mb"]).size().eq(1).all()
            cardinality_ok &= null.groupby(["POP", "replicate", "gerp_threshold", "roh_cutoff_mb"]).size().eq(1).all()
            cardinality_ok &= set(zip(observed["gerp_threshold"], observed["roh_cutoff_mb"])) == expected_cells
            cardinality_ok &= set(observed["IND"].astype(str)) == set(pop_lookup)
            cardinality_ok &= set(observed["POP"].astype(str)) == set(populations)
            cardinality_ok &= observed["chrom"].astype(str).eq(chrom).all() and null["chrom"].astype(str).eq(chrom).all()
            arithmetic_ok &= self._partition_arithmetic(observed)
            arithmetic_ok &= self._partition_arithmetic(null)
            expected_seed = stable_seed(int(settings["seed"]), f"chromosome|{chrom}")
            seed_ok &= null["base_seed"].eq(int(settings["seed"])).all()
            seed_ok &= null["chrom_seed"].eq(expected_seed).all()
            seed_ok &= len(chrom_qc) == 1 and int(chrom_qc.iloc[0]["chrom_seed"]) == expected_seed
            seed_ok &= (
                len(chrom_qc) == 1
                and str(chrom_qc.iloc[0].get("gate_decision", "")) == "IMPLEMENT"
                and str(chrom_qc.iloc[0].get("gate_decision_table_sha256", "")) == decision_hash
                and str(chrom_qc.iloc[0].get("gate_decision_validation_sha256", "")) == decision_validation_hash
            )
            status_ok &= set(null["status"].astype(str)).issubset({"ok", "nonconvergent"})
            reason = null["failure_reason"].fillna("").astype(str)
            status_ok &= ((null["status"].eq("ok") & reason.eq("")) | (null["status"].ne("ok") & reason.ne(""))).all()

            phase4_path = phase4_dir / f"chr{chrom}.tsv"
            if not phase4_path.is_file():
                phase4_ok = False
                continue
            phase4 = pd.read_csv(phase4_path, sep="\t", float_precision="round_trip")
            source = observed.sort_values("roh_cutoff_mb").drop_duplicates(["IND", "POP", "gerp_threshold"])
            joined = source.merge(
                phase4[["IND", "POP", "THRES", "hom_del_sum", "n_hom_del", "calls"]],
                left_on=["IND", "POP", "gerp_threshold"],
                right_on=["IND", "POP", "THRES"],
                how="outer", validate="one_to_one", indicator=True,
            )
            phase4_ok &= joined["_merge"].eq("both").all()
            burden_delta = maximum_absolute(joined["total_hom_del_sum"] - joined["hom_del_sum"])
            copy_delta = maximum_absolute(joined["total_hom_derived_copies"] - joined["n_hom_del"])
            call_delta = maximum_absolute(
                joined["all_polarized_gerp_genotype_calls"] - joined["calls"]
            )
            max_burden_delta = max(max_burden_delta, burden_delta)
            max_copy_delta = max(max_copy_delta, copy_delta)
            max_call_delta = max(max_call_delta, call_delta)
            phase4_ok &= burden_delta <= FLOAT_TOL and copy_delta == 0 and call_delta == 0

        self.add(
            "chromosome intermediate schemas and cardinalities",
            schema_ok and cardinality_ok,
            f"expected rows/file observed={expected_obs_rows}, null={expected_null_rows}; "
            f"schema_ok={schema_ok}, cardinality_ok={cardinality_ok}",
        )
        self.add(
            "chromosome burden/copy/call partitions are nonnegative and exact",
            arithmetic_ok,
            f"38 observed and null chromosome partitions checked",
        )
        self.add(
            "chromosome worker seeds and implementation-gate hashes independently reproduce",
            seed_ok,
            f"base_seed={settings['seed']}; derivation=sha256(base_seed|chromosome|CHROM); gate=IMPLEMENT",
        )
        self.add(
            "chromosome null failures are explicitly represented",
            status_ok,
            "allowed statuses=ok/nonconvergent; every failure requires a reason",
        )
        self.add(
            "each chromosome reconciles to Phase-4 raw load totals",
            phase4_ok,
            f"max absolute deltas burden/copies/calls={max_burden_delta:.3g}/{max_copy_delta:.3g}/{max_call_delta:.3g}",
        )

    def _partition_arithmetic(self, frame: pd.DataFrame) -> bool:
        pairs = [
            (
                "inside_eligible_genotype_calls",
                "outside_eligible_genotype_calls",
                "total_eligible_genotype_calls",
            ),
            ("inside_hom_derived_copies", "outside_hom_derived_copies", "total_hom_derived_copies"),
            ("inside_hom_del_sum", "outside_hom_del_sum", "total_hom_del_sum"),
        ]
        for inside, outside, total in pairs:
            if not {inside, outside, total}.issubset(frame.columns):
                return False
            values = frame[[inside, outside, total]].to_numpy(dtype=float)
            if not np.isfinite(values).all() or np.any(values < -FLOAT_TOL):
                return False
            if maximum_absolute(frame[inside] + frame[outside] - frame[total]) > FLOAT_TOL:
                return False
        if "all_polarized_gerp_genotype_calls" in frame:
            if np.any(
                frame["total_eligible_genotype_calls"]
                > frame["all_polarized_gerp_genotype_calls"]
            ):
                return False
        return True

    def _validate_individual(
        self,
        individual: pd.DataFrame,
        load: pd.DataFrame,
        roh: pd.DataFrame,
        expected_cells: set[tuple[float, float]],
        thresholds: list[float],
        cutoffs: list[float],
        popmap: pd.DataFrame,
    ) -> None:
        combinations = individual.groupby(["IND", "gerp_threshold", "roh_cutoff_mb"]).size()
        self.add(
            "individual table has the complete 211 x 3 x 5 cube",
            INDIVIDUAL_COLUMNS.issubset(individual.columns)
            and len(individual) == EXPECTED_N * len(expected_cells)
            and combinations.eq(1).all()
            and set(zip(individual["gerp_threshold"], individual["roh_cutoff_mb"])) == expected_cells
            and set(individual["IND"].astype(str)) == set(popmap["IND"]),
            f"rows={len(individual)}, unique keys={len(combinations)}, expected={EXPECTED_N * len(expected_cells)}",
        )
        arithmetic_ok = self._partition_arithmetic(individual)
        rate = individual.copy()
        with np.errstate(divide="ignore", invalid="ignore"):
            expected_inside = (
                rate["inside_hom_del_sum"] / rate["inside_eligible_genotype_calls"]
            )
            expected_outside = (
                rate["outside_hom_del_sum"] / rate["outside_eligible_genotype_calls"]
            )
            expected_ratio = expected_inside / expected_outside
            expected_log = np.log2(expected_ratio)
        metric_delta = max(
            maximum_absolute(rate["inside_burden_rate"] - expected_inside),
            maximum_absolute(rate["outside_burden_rate"] - expected_outside),
            maximum_absolute(rate["rate_ratio"] - expected_ratio),
            maximum_absolute(rate["log2_enrichment"] - expected_log),
        )
        status = individual["status"].astype(str)
        reason = individual["failure_reason"].fillna("").astype(str)
        status_ok = set(status).issubset({"ok", "nonconvergent"}) and (
            (status.eq("ok") & reason.eq("")) | (status.ne("ok") & reason.ne(""))
        ).all()
        self.add(
            "individual eligible-genotype denominators and enrichment arithmetic are exact",
            arithmetic_ok and metric_delta <= FLOAT_TOL and status_ok,
            f"max derived-metric delta={metric_delta:.3g}; failures={int(status.ne('ok').sum())}",
        )

        joined = individual.merge(
            load[["IND", "POP", "THRES", "hom_del_sum", "n_hom_del", "calls"]],
            left_on=["IND", "POP", "gerp_threshold"],
            right_on=["IND", "POP", "THRES"],
            how="outer", validate="many_to_one", indicator=True,
        )
        burden_delta = maximum_absolute(joined["total_hom_del_sum"] - joined["hom_del_sum"])
        copy_delta = maximum_absolute(joined["total_hom_derived_copies"] - joined["n_hom_del"])
        call_delta = maximum_absolute(
            joined["all_polarized_gerp_genotype_calls"] - joined["calls"]
        )
        self.add(
            "inside plus outside reconciles exactly to genome-wide Phase-4 load",
            joined["_merge"].eq("both").all()
            and burden_delta <= FLOAT_TOL and copy_delta == 0 and call_delta == 0
            and maximum_absolute(individual["phase4_burden_delta"]) <= FLOAT_TOL
            and maximum_absolute(individual["phase4_copy_delta"]) == 0
            and maximum_absolute(individual["phase4_genotype_call_delta"]) == 0,
            f"max absolute deltas burden/copies/calls={burden_delta:.3g}/{copy_delta:.3g}/{call_delta:.3g}",
        )
        invariant = individual.groupby(["IND", "gerp_threshold"])[
            [
                "total_eligible_genotype_calls",
                "total_hom_derived_copies",
                "total_hom_del_sum",
                "all_polarized_gerp_genotype_calls",
            ]
        ].nunique(dropna=False)
        self.add(
            "genome-wide totals are invariant across the five ROH cutoffs",
            invariant.le(1).all().all(),
            f"non-invariant groups={int(invariant.gt(1).any(axis=1).sum())}",
        )

    def _validate_raw_rg(
        self,
        individual: pd.DataFrame,
        roh: pd.DataFrame,
        chromosomes: list[str],
        cutoffs: list[float],
        popmap: pd.DataFrame,
    ) -> None:
        lengths = read_lengths(self.paths["lengths"])
        samples = popmap["IND"].astype(str).tolist()
        sample_set = set(samples)
        aggregate = {
            (sample, cutoff): [0, 0, 0, 0]
            for sample in samples for cutoff in cutoffs
        }  # n, raw, union, overlap
        audit = defaultdict(int)
        for chrom in chromosomes:
            rg_path = self.paths["roh_dir"] / f"chr{chrom}.rg.txt"
            if not rg_path.is_file():
                audit["missing_files"] += 1
                continue
            by_sample: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
            with rg_path.open(encoding="utf-8") as handle:
                for line in handle:
                    fields = line.rstrip("\n").split("\t")
                    if len(fields) < 6 or fields[0] != "RG":
                        continue
                    audit["records"] += 1
                    sample, row_chrom = fields[1], str(fields[2])
                    if sample not in sample_set:
                        audit["unknown_samples"] += 1
                        continue
                    if row_chrom != chrom:
                        audit["wrong_chromosome"] += 1
                        continue
                    start, end, reported = int(fields[3]), int(fields[4]), int(fields[5])
                    if reported != end - start + 1:
                        audit["length_mismatch"] += 1
                    if not (1 <= start <= end <= lengths[chrom]):
                        audit["bounds_failure"] += 1
                        continue
                    by_sample[sample].append((start - 1, end, reported))
            for sample in samples:
                rows = by_sample.get(sample, [])
                for cutoff in cutoffs:
                    cutoff_bp = int(round(cutoff * 1_000_000))
                    kept = [row for row in rows if row[2] >= cutoff_bp]
                    union, overlap = merged_span([(start, end) for start, end, _ in kept])
                    key = (sample, cutoff)
                    aggregate[key][0] += len(kept)
                    aggregate[key][1] += sum(length for _, _, length in kept)
                    aggregate[key][2] += union
                    aggregate[key][3] += overlap

        reference = pd.DataFrame(
            [
                {
                    "IND": sample,
                    "roh_cutoff_mb": cutoff,
                    "expected_n_roh": values[0],
                    "expected_raw_span_bp": values[1],
                    "expected_union_bp": values[2],
                    "expected_overlap_bp": values[3],
                }
                for (sample, cutoff), values in aggregate.items()
            ]
        )
        independent = individual.merge(
            reference, on=["IND", "roh_cutoff_mb"], how="left", validate="many_to_one"
        )
        deltas = {
            "n": maximum_absolute(independent["n_roh"] - independent["expected_n_roh"]),
            "raw": maximum_absolute(independent["roh_raw_span_bp"] - independent["expected_raw_span_bp"]),
            "union": maximum_absolute(independent["roh_union_bp"] - independent["expected_union_bp"]),
            "overlap": maximum_absolute(independent["roh_overlap_bp"] - independent["expected_overlap_bp"]),
        }
        audit_fail = sum(
            audit[key] for key in (
                "missing_files", "unknown_samples", "wrong_chromosome",
                "length_mismatch", "bounds_failure",
            )
        )
        self.add(
            "raw RG coordinates independently pass 1-based-inclusive audits",
            audit_fail == 0 and audit["records"] > 0,
            f"records={audit['records']}; audit failures={audit_fail}",
        )
        self.add(
            "raw RG unions independently reproduce every individual/cutoff result",
            max(deltas.values()) == 0,
            f"max deltas n/raw/union/overlap={deltas['n']:.3g}/{deltas['raw']:.3g}/"
            f"{deltas['union']:.3g}/{deltas['overlap']:.3g}",
        )

        genome_length = sum(lengths.values())
        phase4 = reference.assign(
            froh_independent=reference["expected_union_bp"] / genome_length
        ).merge(
            roh[["IND", "POP", "min_length_mb", "F_ROH", "n_roh", "total_roh_mb"]],
            left_on=["IND", "roh_cutoff_mb"], right_on=["IND", "min_length_mb"],
            how="outer", validate="one_to_one", indicator=True,
        )
        froh_delta = maximum_absolute(phase4["froh_independent"] - phase4["F_ROH"])
        phase4_n_delta = maximum_absolute(phase4["expected_n_roh"] - phase4["n_roh"])
        phase4_span_delta = maximum_absolute(phase4["expected_raw_span_bp"] / 1_000_000.0 - phase4["total_roh_mb"])
        self.add(
            "independent RG coverage reconciles exactly to Phase-4 F_ROH",
            phase4["_merge"].eq("both").all()
            and froh_delta <= 5e-12
            and phase4_n_delta == 0
            and phase4_span_delta <= 5e-9
            and maximum_absolute(individual["froh_delta"]) <= 5e-12,
            f"max deltas F_ROH/n_ROH/span_Mb={froh_delta:.3g}/{phase4_n_delta:.3g}/{phase4_span_delta:.3g}",
        )

    def _validate_raw_interval_assignment(
        self,
        thresholds: list[float],
        cutoffs: list[float],
        chromosomes: list[str],
        popmap: pd.DataFrame,
    ) -> None:
        """Independently recompute a broad, deterministic raw-data audit panel.

        A full second 38-chromosome analysis would duplicate the expensive
        production job.  Instead this validator streams six chromosomes spaced
        across the autosomes and three SHA-256-selected individuals from every
        cohort.  It uses bcftools text output and its own genotype/AA/interval
        parser, never scikit-allel or an analysis helper.  Every selected
        individual is checked at all three GERP thresholds and all five ROH
        cutoffs against the chromosome intermediate table.
        """
        check_name = (
            "independent raw VCF/GERP/RG audit reproduces interval-assigned "
            "opportunity and burden"
        )
        try:
            if len(chromosomes) < 6:
                raise ValueError("raw audit requires at least six chromosomes")
            chromosome_indices = sorted(
                set(int(round(value)) for value in np.linspace(0, len(chromosomes) - 1, 6))
            )
            audit_chromosomes = [chromosomes[index] for index in chromosome_indices]

            selected: list[str] = []
            selected_by_population: dict[str, list[str]] = {}
            for population, group in popmap.groupby("POP", sort=True):
                ranked = sorted(
                    group["IND"].astype(str),
                    key=lambda sample: sha256(
                        f"wolf-roh-raw-audit|{population}|{sample}".encode("utf-8")
                    ).hexdigest(),
                )
                chosen = ranked[: min(3, len(ranked))]
                selected_by_population[str(population)] = chosen
                selected.extend(chosen)

            bcftools = bcftools_executable()
            sample_result = subprocess.run(
                [str(bcftools), "query", "-l", str(self.paths["vcf"])],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if sample_result.returncode != 0:
                raise RuntimeError(f"bcftools query -l failed: {sample_result.stderr.strip()}")
            vcf_samples = [line.strip() for line in sample_result.stdout.splitlines() if line.strip()]
            selected_set = set(selected)
            audit_samples = [sample for sample in vcf_samples if sample in selected_set]
            if len(audit_samples) != len(selected_set):
                missing = selected_set - set(audit_samples)
                raise ValueError(f"raw-audit samples absent from VCF: {sorted(missing)}")

            cutoff_bp = np.rint(np.asarray(cutoffs, dtype=float) * 1_000_000).astype(np.int64)
            sample_index = {sample: index for index, sample in enumerate(audit_samples)}
            max_integer_delta = 0
            max_burden_delta = 0.0
            audited_cells = 0
            audit = defaultdict(int)

            for chromosome in audit_chromosomes:
                gerp_path = self.root / f"results/wolf/gerp/chr{chromosome}.bed"
                if not gerp_path.is_file():
                    raise FileNotFoundError(gerp_path)
                gerp: dict[int, float] = {}
                with gerp_path.open(encoding="utf-8") as handle:
                    for line in handle:
                        fields = line.rstrip("\n").split("\t")
                        if len(fields) < 5:
                            continue
                        if str(fields[0]) != str(chromosome):
                            raise ValueError(f"wrong chromosome in {gerp_path}: {fields[0]}")
                        position = int(fields[2])
                        if position in gerp:
                            raise ValueError(f"duplicate GERP position chr{chromosome}:{position}")
                        gerp[position] = float(fields[4])

                intervals: dict[str, list[tuple[int, int, int]]] = {
                    sample: [] for sample in audit_samples
                }
                rg_path = self.paths["roh_dir"] / f"chr{chromosome}.rg.txt"
                with rg_path.open(encoding="utf-8") as handle:
                    for line in handle:
                        fields = line.rstrip("\n").split("\t")
                        if len(fields) < 6 or fields[0] != "RG":
                            continue
                        sample = fields[1]
                        if sample not in sample_index:
                            continue
                        if str(fields[2]) != str(chromosome):
                            raise ValueError(f"wrong chromosome in {rg_path}: {fields[2]}")
                        start, end, reported = int(fields[3]), int(fields[4]), int(fields[5])
                        if reported != end - start + 1:
                            raise ValueError(f"RG length mismatch in {rg_path}")
                        intervals[sample].append((start - 1, end, reported))
                for sample in audit_samples:
                    intervals[sample].sort()
                    for left, right in zip(intervals[sample], intervals[sample][1:]):
                        if right[0] < left[1]:
                            raise ValueError(
                                f"overlapping raw ROH rows for {sample} on chr{chromosome}"
                            )

                n_samples = len(audit_samples)
                n_thresholds = len(thresholds)
                n_cutoffs = len(cutoffs)
                all_calls = np.zeros(n_samples, dtype=np.int64)
                total_calls = np.zeros((n_samples, n_thresholds), dtype=np.int64)
                total_copies = np.zeros_like(total_calls)
                total_burden = np.zeros((n_samples, n_thresholds), dtype=np.float64)
                inside_calls = np.zeros(
                    (n_samples, n_thresholds, n_cutoffs), dtype=np.int64
                )
                inside_copies = np.zeros_like(inside_calls)
                inside_burden = np.zeros(
                    (n_samples, n_thresholds, n_cutoffs), dtype=np.float64
                )
                pointers = np.zeros(n_samples, dtype=np.int64)
                previous_position = 0
                query_format = "%POS\t%REF\t%ALT\t%INFO/AA[\t%GT]\n"
                process = subprocess.Popen(
                    [
                        str(bcftools), "query", "-r", str(chromosome),
                        "-s", ",".join(audit_samples), "-f", query_format,
                        str(self.paths["vcf"]),
                    ],
                    cwd=self.root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1024 * 1024,
                )
                assert process.stdout is not None
                for line in process.stdout:
                    fields = line.rstrip("\n").split("\t")
                    if len(fields) != 4 + n_samples:
                        raise ValueError(
                            f"unexpected bcftools query width on chr{chromosome}: {len(fields)}"
                        )
                    position = int(fields[0])
                    if position < previous_position:
                        raise ValueError(f"unsorted VCF positions on chromosome {chromosome}")
                    previous_position = position
                    audit["vcf_records"] += 1
                    score = gerp.get(position)
                    if score is None:
                        continue
                    audit["gerp_matched_records"] += 1
                    ref, alt, ancestral = (
                        fields[1].upper(), fields[2].upper(), fields[3].upper()
                    )
                    if ancestral == ref:
                        derived_is_alt = True
                        audit["aa_ref_records"] += 1
                    elif "," not in alt and ancestral == alt:
                        derived_is_alt = False
                        audit["aa_alt_records"] += 1
                    else:
                        audit["invalid_aa_records"] += 1
                        continue
                    qualifying = [
                        index for index, threshold in enumerate(thresholds)
                        if score > threshold
                    ]
                    position0 = position - 1
                    for index, genotype in enumerate(fields[4:]):
                        alleles = genotype.replace("|", "/").split("/")
                        if len(alleles) != 2 or any(allele not in {"0", "1"} for allele in alleles):
                            continue
                        audit["eligible_polarized_genotype_calls"] += 1
                        all_calls[index] += 1
                        n_alt = (alleles[0] == "1") + (alleles[1] == "1")
                        homozygous_derived = (
                            (derived_is_alt and n_alt == 2)
                            or (not derived_is_alt and n_alt == 0)
                        )
                        if homozygous_derived:
                            audit["homozygous_derived_calls"] += 1
                        sample_intervals = intervals[audit_samples[index]]
                        pointer = int(pointers[index])
                        while (
                            pointer < len(sample_intervals)
                            and sample_intervals[pointer][1] <= position0
                        ):
                            pointer += 1
                        pointers[index] = pointer
                        interval_length = 0
                        if (
                            pointer < len(sample_intervals)
                            and sample_intervals[pointer][0] <= position0
                            < sample_intervals[pointer][1]
                        ):
                            interval_length = sample_intervals[pointer][2]
                        inside_cutoffs = [
                            cutoff_index
                            for cutoff_index, minimum in enumerate(cutoff_bp)
                            if interval_length >= minimum
                        ]
                        for threshold_index in qualifying:
                            total_calls[index, threshold_index] += 1
                            if homozygous_derived:
                                total_copies[index, threshold_index] += 2
                                total_burden[index, threshold_index] += 2.0 * score
                            for cutoff_index in inside_cutoffs:
                                inside_calls[index, threshold_index, cutoff_index] += 1
                                if homozygous_derived:
                                    inside_copies[index, threshold_index, cutoff_index] += 2
                                    inside_burden[index, threshold_index, cutoff_index] += 2.0 * score
                process.stdout.close()
                stderr = process.stderr.read() if process.stderr is not None else ""
                returncode = process.wait()
                if returncode != 0:
                    raise RuntimeError(
                        f"bcftools raw audit failed on chr{chromosome}: {stderr.strip()}"
                    )

                observed = pd.read_csv(
                    self.paths["intermediate_dir"] / f"chr{chromosome}.observed.tsv",
                    sep="\t",
                    float_precision="round_trip",
                ).set_index(["IND", "gerp_threshold", "roh_cutoff_mb"])
                for sample_index_value, sample in enumerate(audit_samples):
                    for threshold_index, threshold in enumerate(thresholds):
                        for cutoff_index, cutoff in enumerate(cutoffs):
                            row = observed.loc[(sample, threshold, cutoff)]
                            expected_integer = {
                                "inside_eligible_genotype_calls": int(
                                    inside_calls[
                                        sample_index_value, threshold_index, cutoff_index
                                    ]
                                ),
                                "outside_eligible_genotype_calls": int(
                                    total_calls[sample_index_value, threshold_index]
                                    - inside_calls[
                                        sample_index_value, threshold_index, cutoff_index
                                    ]
                                ),
                                "total_eligible_genotype_calls": int(
                                    total_calls[sample_index_value, threshold_index]
                                ),
                                "inside_hom_derived_copies": int(
                                    inside_copies[
                                        sample_index_value, threshold_index, cutoff_index
                                    ]
                                ),
                                "outside_hom_derived_copies": int(
                                    total_copies[sample_index_value, threshold_index]
                                    - inside_copies[
                                        sample_index_value, threshold_index, cutoff_index
                                    ]
                                ),
                                "total_hom_derived_copies": int(
                                    total_copies[sample_index_value, threshold_index]
                                ),
                                "all_polarized_gerp_genotype_calls": int(
                                    all_calls[sample_index_value]
                                ),
                            }
                            for field, expected in expected_integer.items():
                                max_integer_delta = max(
                                    max_integer_delta, abs(int(row[field]) - expected)
                                )
                            expected_burden = {
                                "inside_hom_del_sum": float(
                                    inside_burden[
                                        sample_index_value, threshold_index, cutoff_index
                                    ]
                                ),
                                "outside_hom_del_sum": float(
                                    total_burden[sample_index_value, threshold_index]
                                    - inside_burden[
                                        sample_index_value, threshold_index, cutoff_index
                                    ]
                                ),
                                "total_hom_del_sum": float(
                                    total_burden[sample_index_value, threshold_index]
                                ),
                            }
                            for field, expected in expected_burden.items():
                                max_burden_delta = max(
                                    max_burden_delta, abs(float(row[field]) - expected)
                                )
                            audited_cells += 1

            expected_samples = 3 * popmap["POP"].nunique()
            expected_cells = (
                len(audit_chromosomes)
                * len(audit_samples)
                * len(thresholds)
                * len(cutoffs)
            )
            coverage_ok = (
                len(audit_chromosomes) == 6
                and len(audit_samples) == expected_samples
                and len(selected_by_population) == 8
                and all(len(samples) == 3 for samples in selected_by_population.values())
                and audited_cells == expected_cells
                and audit["gerp_matched_records"] > 0
                and audit["aa_ref_records"] > 0
                and audit["aa_alt_records"] > 0
                and audit["eligible_polarized_genotype_calls"] > 0
                and audit["homozygous_derived_calls"] > 0
            )
            self.add(
                check_name,
                coverage_ok
                and max_integer_delta == 0
                and max_burden_delta <= FLOAT_TOL,
                f"chromosomes={audit_chromosomes} (6/38); individuals={len(audit_samples)}/211 "
                f"(3/cohort); cells={audited_cells}; VCF records={audit['vcf_records']}; "
                f"AA REF/ALT={audit['aa_ref_records']}/{audit['aa_alt_records']}; "
                f"max integer/burden delta={max_integer_delta}/{max_burden_delta:.3g}",
            )
        except Exception as error:
            self.add(check_name, False, f"{type(error).__name__}: {error}")

    def _validate_raw_null_assignment(
        self,
        settings: dict,
        thresholds: list[float],
        cutoffs: list[float],
        chromosomes: list[str],
        popmap: pd.DataFrame,
    ) -> None:
        """Rebuild a bounded exact sample of worker null rows from raw inputs.

        The audit deliberately uses a separate parser and interval-shift
        implementation. It selects the first and last autosomes, three evenly
        spaced cohort labels, and one deterministic replicate per chromosome.
        All individuals in the selected cohorts and the full 3 x 5 grid are
        reconstructed so the cohort-aggregate intermediate rows can be checked
        exactly without materializing a second genome-wide null analysis.
        """
        check_name = (
            "independent raw circular-shift audit reproduces sampled chromosome null rows"
        )
        try:
            if len(chromosomes) < 2:
                raise ValueError("independent null audit requires at least two chromosomes")
            audit_chromosomes = [chromosomes[0], chromosomes[-1]]
            all_populations = sorted(popmap["POP"].astype(str).unique())
            population_indices = sorted(
                set(int(round(value)) for value in np.linspace(0, len(all_populations) - 1, 3))
            )
            audit_populations = [all_populations[index] for index in population_indices]
            pop_lookup_all = popmap.set_index("IND")["POP"].astype(str).to_dict()
            all_samples = [
                line.strip()
                for line in self.paths["samples"].open(encoding="utf-8")
                if line.strip()
            ]
            if (
                len(all_samples) != EXPECTED_N
                or len(set(all_samples)) != EXPECTED_N
                or set(all_samples) != set(pop_lookup_all)
            ):
                raise ValueError("independent null audit sample/popmap mismatch")

            bcftools = bcftools_executable()
            sample_result = subprocess.run(
                [str(bcftools), "query", "-l", str(self.paths["vcf"])],
                cwd=self.root, capture_output=True, text=True, timeout=120, check=False,
            )
            if sample_result.returncode != 0:
                raise RuntimeError(
                    f"bcftools query -l failed: {sample_result.stderr.strip()}"
                )
            vcf_samples = [
                line.strip() for line in sample_result.stdout.splitlines() if line.strip()
            ]
            if vcf_samples != all_samples:
                raise ValueError("VCF sample order differs from frozen samples.txt order")
            audit_samples = [
                sample for sample in all_samples
                if pop_lookup_all[sample] in audit_populations
            ]
            pop_lookup = {sample: pop_lookup_all[sample] for sample in audit_samples}
            if len(audit_samples) != 49:
                raise ValueError(
                    f"expected 49 individuals in deterministic null-audit cohorts, found "
                    f"{len(audit_samples)}"
                )

            lengths = read_lengths(self.paths["lengths"])
            cutoff_bp = np.rint(
                np.asarray(cutoffs, dtype=float) * 1_000_000
            ).astype(np.int64)
            base_seed = int(settings["seed"])
            reps = int(settings["permutation_reps"])
            global_sample_index = {
                sample: index for index, sample in enumerate(all_samples)
            }
            comparisons = 0
            max_integer_delta = 0
            max_burden_delta = 0.0
            metadata_ok = True
            comparisons_ok = True
            audit_totals = defaultdict(int)
            selected_replicates: dict[str, int] = {}

            for chromosome in audit_chromosomes:
                chromosome_length = int(lengths[chromosome])
                gerp_path = self.root / f"results/wolf/gerp/chr{chromosome}.bed"
                gerp: dict[int, float] = {}
                with gerp_path.open(encoding="utf-8") as handle:
                    for line in handle:
                        fields = line.rstrip("\n").split("\t")
                        if len(fields) < 5:
                            continue
                        if str(fields[0]) != str(chromosome):
                            raise ValueError(f"wrong chromosome in {gerp_path}: {fields[0]}")
                        position = int(fields[2])
                        score = float(fields[4])
                        if (
                            position in gerp or not 1 <= position <= chromosome_length
                            or not math.isfinite(score)
                        ):
                            raise ValueError(
                                f"invalid/duplicate GERP key chr{chromosome}:{position}"
                            )
                        gerp[position] = score

                intervals: dict[str, list[tuple[int, int, int]]] = {
                    sample: [] for sample in audit_samples
                }
                rg_path = self.paths["roh_dir"] / f"chr{chromosome}.rg.txt"
                with rg_path.open(encoding="utf-8") as handle:
                    for line in handle:
                        fields = line.rstrip("\n").split("\t")
                        if len(fields) < 6 or fields[0] != "RG":
                            continue
                        if str(fields[2]) != str(chromosome):
                            raise ValueError(f"wrong chromosome in {rg_path}: {fields[2]}")
                        sample = fields[1]
                        if sample not in intervals:
                            continue
                        start, end, reported = int(fields[3]), int(fields[4]), int(fields[5])
                        if reported != end - start + 1:
                            raise ValueError(f"RG length mismatch in {rg_path}")
                        if not 1 <= start <= end <= chromosome_length:
                            raise ValueError(f"RG bounds failure in {rg_path}")
                        intervals[sample].append((start - 1, end, reported))
                for sample in audit_samples:
                    intervals[sample].sort()
                    if any(
                        right[0] < left[1]
                        for left, right in zip(intervals[sample], intervals[sample][1:])
                    ):
                        raise ValueError(
                            f"overlapping raw ROH rows for {sample} on chr{chromosome}"
                        )

                chromosome_seed = stable_seed(base_seed, f"chromosome|{chromosome}")
                offsets = np.random.default_rng(chromosome_seed).integers(
                    0, chromosome_length,
                    size=(reps, len(all_samples)), dtype=np.int64,
                )
                replicate = int(
                    stable_seed(
                        base_seed, f"validator-null-audit-replicate|{chromosome}"
                    ) % reps
                )
                selected_replicates[chromosome] = replicate
                sample_offsets = {
                    sample: int(offsets[replicate, global_sample_index[sample]])
                    for sample in audit_samples
                }

                query_format = "%POS\t%REF\t%ALT\t%INFO/AA[\t%GT]\n"
                process = subprocess.Popen(
                    [
                        str(bcftools), "query", "-r", str(chromosome),
                        "-s", ",".join(audit_samples), "-f", query_format,
                        str(self.paths["vcf"]),
                    ],
                    cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, bufsize=1024 * 1024,
                )
                assert process.stdout is not None

                def records() -> Iterable[tuple[int, str, str, str, list[str]]]:
                    for raw_line in process.stdout:
                        fields = raw_line.rstrip("\n").split("\t")
                        if len(fields) != 4 + len(audit_samples):
                            raise ValueError(
                                f"unexpected null-audit VCF width on chr{chromosome}: "
                                f"{len(fields)}"
                            )
                        yield (
                            int(fields[0]), fields[1], fields[2], fields[3], fields[4:]
                        )

                try:
                    reconstructed = reconstruct_circular_null(
                        records(), gerp, audit_samples, pop_lookup, audit_populations,
                        intervals, sample_offsets, chromosome_length, thresholds, cutoff_bp,
                    )
                except Exception:
                    process.kill()
                    process.wait()
                    raise
                process.stdout.close()
                stderr = process.stderr.read() if process.stderr is not None else ""
                returncode = process.wait()
                if returncode != 0:
                    raise RuntimeError(
                        f"bcftools null audit failed on chr{chromosome}: {stderr.strip()}"
                    )

                intermediate = pd.read_csv(
                    self.paths["intermediate_dir"] / f"chr{chromosome}.null.tsv",
                    sep="\t", float_precision="round_trip",
                )
                comparison = compare_circular_null(
                    intermediate, reconstructed, chromosome, replicate, base_seed,
                    chromosome_seed, audit_populations, thresholds, cutoffs,
                )
                comparisons += int(comparison["comparisons"])
                max_integer_delta = max(
                    max_integer_delta, int(comparison["max_integer_delta"])
                )
                max_burden_delta = max(
                    max_burden_delta, float(comparison["max_burden_delta"])
                )
                metadata_ok &= bool(comparison["metadata_ok"])
                comparisons_ok &= bool(comparison["ok"])
                for key, value in dict(reconstructed["audit"]).items():
                    audit_totals[key] += int(value)

            expected_comparisons = (
                len(audit_chromosomes) * len(audit_populations)
                * len(thresholds) * len(cutoffs)
            )
            coverage_ok = (
                audit_chromosomes == ["1", "38"]
                and len(audit_populations) == 3
                and len(audit_samples) == 49
                and comparisons == expected_comparisons == 90
                and audit_totals["vcf_records"] > 0
                and audit_totals["gerp_matched_records"] > 0
                and audit_totals["aa_ref_records"] > 0
                and audit_totals["aa_alt_records"] > 0
                and audit_totals["eligible_polarized_genotype_calls"] > 0
                and audit_totals["homozygous_derived_calls"] > 0
                and audit_totals["wrapped_interval_cutoff_assignments"] > 0
            )
            self.add(
                check_name,
                coverage_ok and metadata_ok and comparisons_ok
                and max_integer_delta == 0 and max_burden_delta <= FLOAT_TOL,
                f"chromosomes={audit_chromosomes}; cohorts={audit_populations}; "
                f"individuals={len(audit_samples)}; replicates={selected_replicates}; "
                f"cohort cells={comparisons}/{expected_comparisons}; "
                f"individual-grid assignments={len(audit_chromosomes) * len(audit_samples) * len(thresholds) * len(cutoffs)}; "
                f"wrapped interval-cutoff assignments="
                f"{audit_totals['wrapped_interval_cutoff_assignments']}; "
                f"max integer/burden delta={max_integer_delta}/{max_burden_delta:.3g}; "
                f"metadata_ok={metadata_ok}; comparisons_ok={comparisons_ok}",
            )
        except Exception as error:
            self.add(check_name, False, f"{type(error).__name__}: {error}")

    def _validate_null(
        self,
        null: pd.DataFrame,
        cohort: pd.DataFrame,
        populations: list[str],
        thresholds: list[float],
        cutoffs: list[float],
        reps: int,
        settings: dict,
    ) -> None:
        expected_rows = len(populations) * len(thresholds) * len(cutoffs) * reps
        group = null.groupby(["POP", "gerp_threshold", "roh_cutoff_mb"])
        exact_reps = group["replicate"].agg(
            lambda values: set(values.astype(int)) == set(range(reps))
        )
        self.add(
            "final null table contains all 199 replicates for all 8 x 3 x 5 cells",
            NULL_COLUMNS.issubset(null.columns)
            and len(null) == expected_rows
            and len(group) == len(populations) * len(thresholds) * len(cutoffs)
            and exact_reps.all()
            and null["base_seed"].eq(int(settings["seed"])).all(),
            f"rows={len(null)}/{expected_rows}; cells={len(group)}; incomplete={int((~exact_reps).sum())}",
        )
        arithmetic_ok = self._partition_arithmetic(null)
        status = null["status"].astype(str)
        reason = null["failure_reason"].fillna("").astype(str)
        status_ok = set(status).issubset({"ok", "nonconvergent"}) and (
            (status.eq("ok") & reason.eq("")) | (status.ne("ok") & reason.ne(""))
        ).all()
        self.add(
            "circular-shift null preserves totals and reports every failure",
            arithmetic_ok and status_ok,
            f"partition_ok={arithmetic_ok}; failed rows={int(status.ne('ok').sum())}",
        )
        cohort_total = cohort.assign(
            expected_calls=(
                cohort["inside_eligible_genotype_calls"]
                + cohort["outside_eligible_genotype_calls"]
            ),
            expected_copies=cohort["inside_hom_derived_copies"] + cohort["outside_hom_derived_copies"],
            expected_burden=cohort["inside_hom_del_sum"] + cohort["outside_hom_del_sum"],
        )[["POP", "gerp_threshold", "roh_cutoff_mb", "expected_calls", "expected_copies", "expected_burden"]]
        joined = null.merge(
            cohort_total, on=["POP", "gerp_threshold", "roh_cutoff_mb"],
            how="left", validate="many_to_one",
        )
        deltas = (
            maximum_absolute(
                joined["total_eligible_genotype_calls"] - joined["expected_calls"]
            ),
            maximum_absolute(joined["total_hom_derived_copies"] - joined["expected_copies"]),
            maximum_absolute(joined["total_hom_del_sum"] - joined["expected_burden"]),
        )
        self.add(
            "each null replicate preserves cohort opportunity, copies, and burden",
            deltas[0] == 0 and deltas[1] == 0 and deltas[2] <= FLOAT_TOL,
            f"max absolute deltas calls/copies/burden={deltas[0]:.3g}/{deltas[1]:.3g}/{deltas[2]:.3g}",
        )

    def _validate_cohort(
        self,
        cohort: pd.DataFrame,
        individual: pd.DataFrame,
        null: pd.DataFrame,
        populations: list[str],
        thresholds: list[float],
        cutoffs: list[float],
        settings: dict,
    ) -> None:
        expected_rows = len(populations) * len(thresholds) * len(cutoffs)
        keys = ["POP", "gerp_threshold", "roh_cutoff_mb"]
        groups = cohort.groupby(keys).size()
        self.add(
            "cohort table contains the complete 8 x 3 x 5 grid",
            COHORT_COLUMNS.issubset(cohort.columns)
            and len(cohort) == expected_rows and len(groups) == expected_rows
            and groups.eq(1).all(),
            f"rows={len(cohort)}/{expected_rows}; duplicate cells={int((groups > 1).sum())}",
        )
        raw = [
            "inside_eligible_genotype_calls", "outside_eligible_genotype_calls",
            "inside_hom_derived_copies", "outside_hom_derived_copies",
            "inside_hom_del_sum", "outside_hom_del_sum",
        ]
        expected = individual.groupby(keys, as_index=False).agg(
            expected_n_ind=("IND", "nunique"),
            **{f"expected_{column}": (column, "sum") for column in raw},
        )
        joined = cohort.merge(expected, on=keys, how="outer", validate="one_to_one", indicator=True)
        raw_delta = maximum_absolute(joined["n_ind"] - joined["expected_n_ind"])
        for column in raw:
            raw_delta = max(raw_delta, maximum_absolute(joined[column] - joined[f"expected_{column}"]))
        self.add(
            "cohort observed values independently aggregate from individuals",
            joined["_merge"].eq("both").all() and raw_delta <= FLOAT_TOL,
            f"maximum aggregate delta={raw_delta:.3g}",
        )

        alpha = (100.0 - float(settings["ci_pct"])) / 2.0
        summaries = []
        for key, cell in null.groupby(keys, sort=False):
            valid = cell.loc[cell["status"].eq("ok") & np.isfinite(cell["log2_enrichment"])]
            values = valid["log2_enrichment"].to_numpy(dtype=float)
            observed = cohort.loc[
                cohort["POP"].eq(key[0])
                & cohort["gerp_threshold"].eq(key[1])
                & cohort["roh_cutoff_mb"].eq(key[2]), "log2_enrichment"
            ]
            if len(values) and len(observed) == 1:
                median = float(np.median(values))
                low, high = np.percentile(values, [alpha, 100.0 - alpha])
                distance = abs(float(observed.iloc[0]) - median)
                extreme = int(np.count_nonzero(np.abs(values - median) >= distance))
                pvalue = (extreme + 1.0) / (len(values) + 1.0)
            else:
                median = low = high = pvalue = float("nan")
            summaries.append(
                {
                    "POP": key[0], "gerp_threshold": key[1], "roh_cutoff_mb": key[2],
                    "expected_valid": len(values), "expected_failed": len(cell) - len(values),
                    "expected_median": median, "expected_low": low, "expected_high": high,
                    "expected_pvalue": pvalue,
                }
            )
        recomputed = cohort.merge(pd.DataFrame(summaries), on=keys, validate="one_to_one")
        null_delta = max(
            maximum_absolute(recomputed["null_valid_reps"] - recomputed["expected_valid"]),
            maximum_absolute(recomputed["null_failed_reps"] - recomputed["expected_failed"]),
            maximum_absolute(recomputed["null_median_log2_enrichment"] - recomputed["expected_median"]),
            maximum_absolute(recomputed["null_ci_low"] - recomputed["expected_low"]),
            maximum_absolute(recomputed["null_ci_high"] - recomputed["expected_high"]),
            maximum_absolute(recomputed["permutation_p_two_sided"] - recomputed["expected_pvalue"]),
        )
        pvalid = cohort["permutation_p_two_sided"].between(1.0 / (int(settings["permutation_reps"]) + 1.0), 1.0)
        direction = np.select(
            [cohort["log2_enrichment"] > 0, cohort["log2_enrichment"] < 0],
            ["enriched_inside_roh", "depleted_inside_roh"], default="no_difference",
        )
        self.add(
            "cohort null medians, intervals, and two-sided permutation p-values independently reproduce",
            null_delta <= FLOAT_TOL and pvalid.all() and np.array_equal(direction, cohort["direction"].to_numpy()),
            f"maximum summary delta={null_delta:.3g}; invalid p-values={int((~pvalid).sum())}",
        )

    def _validate_qc(self, qc: pd.DataFrame, chromosomes: list[str], settings: dict) -> None:
        expected_seeds = {
            chrom: stable_seed(int(settings["seed"]), f"chromosome|{chrom}")
            for chrom in chromosomes
        }
        actual = {str(row.chrom): int(row.chrom_seed) for row in qc.itertuples(index=False)}
        numeric = [
            "gerp_wrong_chromosome_rows", "gerp_duplicate_positions",
            "gerp_bounds_failures", "rg_wrong_chromosome_rows",
            "rg_unknown_samples", "rg_length_mismatches", "rg_bounds_failures",
            "rg_overlap_pairs", "rg_overlap_bp", "phase4_unmatched_rows",
            "phase4_max_abs_copy_delta", "phase4_max_abs_genotype_call_delta",
        ]
        zero_ok = all(column in qc and maximum_absolute(qc[column]) == 0 for column in numeric)
        burden_ok = "phase4_max_abs_burden_delta" in qc and maximum_absolute(qc["phase4_max_abs_burden_delta"]) <= FLOAT_TOL
        memory_ok = "estimated_array_bytes" in qc and qc["estimated_array_bytes"].between(1, 4_000_000_000 - 1).all()
        self.add(
            "all 38 chromosome QC rows pass coordinates, reconciliation, seed, and memory checks",
            len(qc) == len(chromosomes)
            and qc["chrom"].astype(str).nunique() == len(chromosomes)
            and qc["status"].eq("PASS").all()
            and actual == expected_seeds and zero_ok and burden_ok and memory_ok,
            f"rows={len(qc)}, PASS={int(qc['status'].eq('PASS').sum())}; "
            f"max memory={int(qc['estimated_array_bytes'].max()) if 'estimated_array_bytes' in qc else -1:,} bytes",
        )
        source_columns = {
            "input_gerp_bed_sha256", "input_rg_sha256",
            "input_phase4_chrom_load_sha256", "input_samples_sha256",
            "input_popmap_sha256", "input_lengths_sha256", "input_config_sha256",
        }
        source_ok = source_columns.issubset(qc.columns)
        common_hashes = {
            "input_samples_sha256": file_sha256(self.paths["samples"]),
            "input_popmap_sha256": file_sha256(self.paths["popmap"]),
            "input_lengths_sha256": file_sha256(self.paths["lengths"]),
            "input_config_sha256": file_sha256(self.paths["config"]),
        }
        if source_ok:
            for row in qc.itertuples(index=False):
                chrom = str(int(row.chrom))
                expected = {
                    "input_gerp_bed_sha256": file_sha256(self.root / f"results/wolf/gerp/chr{chrom}.bed"),
                    "input_rg_sha256": file_sha256(self.paths["roh_dir"] / f"chr{chrom}.rg.txt"),
                    "input_phase4_chrom_load_sha256": file_sha256(self.root / f"results/wolf/load/chr{chrom}.tsv"),
                    **common_hashes,
                }
                source_ok &= all(str(getattr(row, key)) == value for key, value in expected.items())
        self.add(
            "chromosome QC hashes every raw GERP/ROH/Phase-4 worker input",
            source_ok,
            f"hash columns={len(source_columns)}; chromosomes={len(qc)}",
        )

    def _validate_figure_values(
        self,
        values: pd.DataFrame,
        cohort: pd.DataFrame,
        populations: list[str],
        thresholds: list[float],
        cutoffs: list[float],
        config: dict,
    ) -> None:
        ribbon = values.loc[values["record_type"].eq("ribbon_cell")]
        forest = values.loc[values["record_type"].eq("forest_cell")]
        default_cutoff = float(config["wolf"]["roh"]["long_roh_threshold_mb"])
        fields = [
            "estimate", "null_median", "ci_low", "ci_high",
            "permutation_p_two_sided", "n_ind",
        ]
        source = cohort.rename(
            columns={
                "log2_enrichment": "estimate",
                "null_median_log2_enrichment": "null_median",
                "null_ci_low": "ci_low",
                "null_ci_high": "ci_high",
            }
        )
        keys = ["POP", "gerp_threshold", "roh_cutoff_mb"]
        ribbon_join = ribbon.merge(source[keys + fields], on=keys, suffixes=("", "_expected"), how="outer", indicator=True)
        forest_source = source.loc[np.isclose(source["roh_cutoff_mb"], default_cutoff)]
        forest_join = forest.merge(forest_source[keys + fields], on=keys, suffixes=("", "_expected"), how="outer", indicator=True)
        delta = 0.0
        for joined in (ribbon_join, forest_join):
            for field in fields:
                delta = max(delta, maximum_absolute(joined[field] - joined[f"{field}_expected"]))
        expected_ribbon = len(populations) * len(thresholds) * len(cutoffs)
        expected_forest = len(populations) * len(thresholds)
        labels_ok = (
            set(values["record_type"].astype(str)) == {"ribbon_cell", "forest_cell"}
            and ribbon["figure"].eq("wolf_roh_localization_ribbon.png").all()
            and forest["figure"].eq("wolf_roh_localization_forest.png").all()
            and set(values["panel"].astype(str)) == {f"GERP>{value:g}" for value in thresholds}
        )
        self.add(
            "figure-values table exactly reproduces cohort cells for ribbon and forest",
            len(ribbon) == expected_ribbon and len(forest) == expected_forest
            and ribbon_join["_merge"].eq("both").all()
            and forest_join["_merge"].eq("both").all()
            and delta <= FLOAT_TOL and labels_ok,
            f"ribbon={len(ribbon)}/{expected_ribbon}, forest={len(forest)}/{expected_forest}, "
            f"max delta={delta:.3g}, labels_ok={labels_ok}",
        )

    def _validate_figures(self) -> None:
        details = []
        valid = True
        for key in FIGURES:
            path = self.paths[key]
            dimensions = png_dimensions(path)
            size = path.stat().st_size
            valid &= dimensions is not None and dimensions[0] >= 800 and dimensions[1] >= 500 and size >= 10_000
            details.append(f"{key}={dimensions},{size}B")
        self.add("forest and ribbon are valid nontrivial PNGs", valid, "; ".join(details))

    def _validate_provenance(
        self,
        provenance: dict,
        settings: dict,
        thresholds: list[float],
        cutoffs: list[float],
        individual: pd.DataFrame,
        cohort: pd.DataFrame,
        null: pd.DataFrame,
        qc: pd.DataFrame,
    ) -> None:
        declared = provenance.get("settings", {})
        settings_ok = (
            int(declared.get("seed", -1)) == int(settings["seed"])
            and int(declared.get("permutation_reps", -1)) == int(settings["permutation_reps"])
            and float(declared.get("ci_pct", -1)) == float(settings["ci_pct"])
            and declared.get("null_model") == settings["null_model"]
            and declared.get("denominator") == settings["denominator"]
            and declared.get("gerp_thresholds") == thresholds
            and declared.get("roh_cutoffs_mb") == cutoffs
        )
        count = provenance.get("counts", {})
        count_ok = (
            int(count.get("individual_rows", -1)) == len(individual)
            and int(count.get("cohort_rows", -1)) == len(cohort)
            and int(count.get("null_rows", -1)) == len(null)
            and int(count.get("chromosomes", -1)) == len(qc)
            and int(count.get("null_failed_rows", -1)) == int(null["status"].ne("ok").sum())
            and int(count.get("cohort_failed_rows", -1)) == int(cohort["status"].ne("ok").sum())
        )
        software = provenance.get("software", {})
        tabix_token = str(software.get("tabix_executable", "")).strip()
        tabix_path = resolve_portable_executable(tabix_token)
        tabix_ok = (
            tabix_token == "tabix"
            and tabix_path is not None
            and tabix_path.is_file()
            and software.get("tabix_executable_sha256") == file_sha256(tabix_path)
        )
        opportunity = provenance.get("opportunity_denominator", {})
        opportunity_ok = (
            opportunity.get("canonical_name")
            == "eligible_polarized_gerp_threshold_snp_genotype_calls"
            and opportunity.get("unit") == "individual-by-SNP genotype calls"
            and opportunity.get("not_callable_genome_bases") is True
            and "variant-only" in str(opportunity.get("eligibility", ""))
            and "ascertainment" in str(opportunity.get("ascertainment_caveat", "")).lower()
        )
        self.add(
            "provenance records settings, denominator semantics, claim boundary, and coordinates",
            settings_ok and count_ok
            and "not fitness" in provenance.get("claim_boundary", "")
            and set(provenance.get("coordinate_semantics", {})) == {"RG", "internal", "GERP"}
            and tabix_ok and opportunity_ok,
            f"settings_ok={settings_ok}, counts_ok={count_ok}, tabix_ok={tabix_ok}, "
            f"opportunity_ok={opportunity_ok}, "
            f"analysis={provenance.get('analysis')}",
        )
        source_columns = {
            "gerp_bed": "input_gerp_bed_sha256",
            "rg": "input_rg_sha256",
            "phase4_chrom_load": "input_phase4_chrom_load_sha256",
        }
        expected_chromosome_sources = {
            str(int(row.chrom)): {
                label: str(getattr(row, column)) for label, column in source_columns.items()
            }
            for row in qc.itertuples(index=False)
        }
        self.add(
            "provenance exposes all per-chromosome raw source hashes",
            provenance.get("chromosome_source_sha256") == expected_chromosome_sources,
            f"declared chromosomes={len(provenance.get('chromosome_source_sha256', {}))}/38",
        )

        labels = {
            key: DEFAULTS[key] for key in SCIENTIFIC_TABLES
        }
        calculated = scientific_hash(
            [(label, self.paths[key]) for key, label in labels.items()]
        )
        files_ok = provenance.get("scientific_hash_files") == sorted(labels.values()) or set(
            provenance.get("scientific_hash_files", [])
        ) == set(labels.values())
        self.add(
            "scientific hash independently reproduces from deterministic TSV bytes",
            calculated == provenance.get("scientific_hash") and files_ok,
            f"calculated={calculated}; declared={provenance.get('scientific_hash')}",
        )

        declared_outputs = provenance.get("output_sha256", {})
        output_ok = True
        mismatches = []
        for key in [*SCIENTIFIC_TABLES, *FIGURES]:
            label = DEFAULTS[key]
            actual = file_sha256(self.paths[key])
            if declared_outputs.get(label) != actual:
                output_ok = False
                mismatches.append(label)
        input_hashes = provenance.get("inputs", {})
        input_ok = bool(input_hashes)
        input_mismatches = []
        for label, declared_hash in input_hashes.items():
            candidate = Path(label)
            candidate = candidate if candidate.is_absolute() else self.root / candidate
            if not candidate.is_file() or file_sha256(candidate) != declared_hash:
                input_ok = False
                input_mismatches.append(label)
        essential_inputs = [
            "wolf_load", "wolf_roh", "lengths", "config", "analysis_script",
            "decision_table", "decision_validation",
        ]
        for key in essential_inputs:
            candidates = {str(self.paths[key]), DEFAULTS[key], str(Path(DEFAULTS[key]))}
            if not any(
                name in input_hashes and input_hashes[name] == file_sha256(self.paths[key])
                for name in candidates
            ):
                input_ok = False
                input_mismatches.append(DEFAULTS[key])
        self.add(
            "provenance input and output SHA-256 hashes reconcile",
            output_ok and input_ok,
            f"output mismatches={mismatches}; input mismatches={input_mismatches[:8]}",
        )

    def _validate_rerun(self, provenance: dict) -> None:
        if any(not path.is_file() for path in [*self.observed_paths, *self.null_paths, *self.chrom_qc_paths]):
            self.add("deterministic temporary re-collation", False, "intermediate files absent")
            return
        with tempfile.TemporaryDirectory(prefix="wolf-roh-localization-validate-") as temporary:
            temp = Path(temporary)
            outputs = {
                key: temp / Path(DEFAULTS[key]).name
                for key in [*SCIENTIFIC_TABLES, *FIGURES, "provenance"]
            }
            command = [
                sys.executable, str(self.paths["analysis_script"]), "collate",
                "--observed", *map(str, self.observed_paths),
                "--null", *map(str, self.null_paths),
                "--qc", *map(str, self.chrom_qc_paths),
                "--wolf-load", str(self.paths["wolf_load"]),
                "--wolf-roh", str(self.paths["wolf_roh"]),
                "--lengths", str(self.paths["lengths"]),
                "--config", str(self.paths["config"]),
                "--decision-table", str(self.paths["decision_table"]),
                "--decision-validation", str(self.paths["decision_validation"]),
                "--out-individual", str(outputs["individual"]),
                "--out-cohort", str(outputs["cohort"]),
                "--out-null", str(outputs["null"]),
                "--out-qc", str(outputs["qc"]),
                "--out-figure-values", str(outputs["figure_values"]),
                "--out-forest", str(outputs["forest"]),
                "--out-ribbon", str(outputs["ribbon"]),
                "--out-provenance", str(outputs["provenance"]),
            ]
            environment = os.environ.copy()
            environment["MPLCONFIGDIR"] = str(temp / "mpl")
            environment["PYTHONHASHSEED"] = "0"
            result = subprocess.run(
                command, cwd=self.root, env=environment, capture_output=True,
                text=True, timeout=600, check=False,
            )
            mismatches = []
            if result.returncode == 0:
                for key in SCIENTIFIC_TABLES:
                    if outputs[key].read_bytes() != self.paths[key].read_bytes():
                        mismatches.append(key)
                rerun_provenance = json.loads(outputs["provenance"].read_text(encoding="utf-8"))
                hash_ok = rerun_provenance.get("scientific_hash") == provenance.get("scientific_hash")
            else:
                hash_ok = False
            stderr_tail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else ""
            self.add(
                "deterministic temporary re-collation",
                result.returncode == 0 and not mismatches and hash_ok,
                f"returncode={result.returncode}; byte mismatches={mismatches}; hash_ok={hash_ok}; stderr_tail={stderr_tail}",
            )


def write_reports(
    checks: list[tuple[str, str, str]], out_tsv: Path, out_md: Path
) -> None:
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(checks, columns=["check", "status", "detail"])
    frame.to_csv(out_tsv, sep="\t", index=False)
    failures = int(frame["status"].eq("FAIL").sum()) if len(frame) else 1
    lines = [
        "# Wolf ROH-localization validation",
        "",
        f"Acceptance status: **{'PASS' if failures == 0 else 'FAIL'}** "
        f"({len(frame) - failures}/{len(frame)} checks passed).",
        "",
        "The validation independently rebuilds raw ROH unions, checks eligible SNP-genotype "
        "burden partitions and Phase-4 reconciliation, directly re-parses VCF/GERP/RG "
        "assignment for six chromosomes and three deterministic individuals per cohort, "
        "independently reconstructs sampled raw circular-shift null allocations, recomputes "
        "cohort summaries, and verifies deterministic collation.",
        "",
        "| Check | Status | Detail |",
        "|---|---:|---|",
    ]
    for check, status, detail in checks:
        clean = str(detail).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {check} | **{status}** | {clean} |")
    lines.extend(
        [
            "",
            "Claim boundary: localization is genomic mechanistic support only; it is "
            "not a measured fitness effect, individual harm estimate, or causal "
            "inbreeding-depression result. The opportunity denominator counts eligible "
            "calls at assayed SNP records, not callable genomic bases, so ascertainment remains.",
            "",
        ]
    )
    out_md.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return
    validator = Validator(args)
    try:
        validator.validate()
    except Exception as error:  # Preserve a report even for malformed artifacts.
        validator.add("validator completed without internal exception", False, f"{type(error).__name__}: {error}")
    out_tsv = validator._resolve(args.out_tsv)
    out_md = validator._resolve(args.out_md)
    write_reports(validator.checks, out_tsv, out_md)
    failures = sum(status == "FAIL" for _, status, _ in validator.checks)
    print(
        f"wolf ROH-localization validation: {len(validator.checks) - failures} PASS, "
        f"{failures} FAIL; {out_tsv}; {out_md}"
    )
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
