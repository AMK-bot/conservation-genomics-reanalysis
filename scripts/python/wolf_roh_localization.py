#!/usr/bin/env python3
"""ROH-localized realized wolf burden for CGplan Phase 5B section 13.4.

The chromosome worker loads one indexed chromosome at a time, never the whole
wolf VCF. It counts GERP-weighted homozygous-derived burden and eligible
polarized GERP-threshold SNP genotype calls inside versus outside each
individual's ROH union. The
null circularly translates that individual's observed ROH intervals within the
same chromosome, preserving chromosome and interval lengths while holding the
observed eligible-genotype and burden landscapes fixed.

The collator reconciles chromosome totals to the validated Phase-4 load and
F_ROH tables, creates cohort-stratified observed/null summaries, figures, and
provenance. These are genomic proxy localizations, not fitness effects or
causal inbreeding depression.

The denominator is deliberately an assayed-variant opportunity denominator:
one eligible call is a nonmissing diploid 0/1 genotype at a variant-only VCF
record with an exact GERP key, valid ancestral-allele polarization, and a score
strictly above the selected threshold. It is not a count of callable genomic
bases, and the circular-shift null cannot remove all SNP-ascertainment effects.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
import platform
import shutil
import sys
import tempfile
from typing import Iterable

import allel
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import yaml


MAX_ARRAY_BYTES = 4_000_000_000
EXPECTED_N = 211
FLOAT_TOL = 1e-6

INDIVIDUAL_COLUMNS = [
    "IND",
    "POP",
    "gerp_threshold",
    "roh_cutoff_mb",
    "n_roh",
    "roh_raw_span_bp",
    "roh_union_bp",
    "roh_overlap_bp",
    "froh_recomputed",
    "F_ROH_phase4",
    "froh_delta",
    "inside_eligible_genotype_calls",
    "outside_eligible_genotype_calls",
    "total_eligible_genotype_calls",
    "inside_hom_derived_copies",
    "outside_hom_derived_copies",
    "total_hom_derived_copies",
    "inside_hom_del_sum",
    "outside_hom_del_sum",
    "total_hom_del_sum",
    "all_polarized_gerp_genotype_calls",
    "inside_burden_rate",
    "outside_burden_rate",
    "rate_ratio",
    "log2_enrichment",
    "phase4_burden_delta",
    "phase4_copy_delta",
    "phase4_genotype_call_delta",
    "status",
    "failure_reason",
]

COHORT_COLUMNS = [
    "POP",
    "gerp_threshold",
    "roh_cutoff_mb",
    "n_ind",
    "inside_eligible_genotype_calls",
    "outside_eligible_genotype_calls",
    "inside_hom_derived_copies",
    "outside_hom_derived_copies",
    "inside_hom_del_sum",
    "outside_hom_del_sum",
    "inside_burden_rate",
    "outside_burden_rate",
    "rate_ratio",
    "log2_enrichment",
    "null_valid_reps",
    "null_failed_reps",
    "null_median_log2_enrichment",
    "null_ci_low",
    "null_ci_high",
    "observed_minus_null_median",
    "permutation_p_two_sided",
    "direction",
    "status",
    "failure_reason",
]

NULL_FINAL_COLUMNS = [
    "POP",
    "replicate",
    "base_seed",
    "gerp_threshold",
    "roh_cutoff_mb",
    "inside_eligible_genotype_calls",
    "outside_eligible_genotype_calls",
    "total_eligible_genotype_calls",
    "inside_hom_derived_copies",
    "outside_hom_derived_copies",
    "total_hom_derived_copies",
    "inside_hom_del_sum",
    "outside_hom_del_sum",
    "total_hom_del_sum",
    "inside_burden_rate",
    "outside_burden_rate",
    "rate_ratio",
    "log2_enrichment",
    "status",
    "failure_reason",
]

FINAL_OUTPUTS = {
    "individual": "results/tables/wolf_roh_localization_individual.tsv",
    "cohort": "results/tables/wolf_roh_localization_cohort.tsv",
    "null": "results/tables/wolf_roh_localization_null.tsv",
    "qc": "results/tables/wolf_roh_localization_qc.tsv",
    "figure_values": "results/tables/wolf_roh_localization_figure_values.tsv",
    "forest": "results/figures/wolf_roh_localization_forest.png",
    "ribbon": "results/figures/wolf_roh_localization_ribbon.png",
    "provenance": "results/provenance/wolf_roh_localization.json",
}

DEFAULT_DECISION_TABLE = "results/tables/phase5b_optional_decisions.tsv"
DEFAULT_DECISION_VALIDATION = "results/tables/validation_phase5b_decisions.tsv"


def stable_seed(base_seed: int, label: str) -> int:
    raw = sha256(f"{base_seed}|{label}".encode("utf-8")).digest()[:8]
    return int.from_bytes(raw, "little") % (2**63 - 1)


def tabix_executable() -> Path:
    sibling = Path(sys.executable).with_name("tabix")
    if sibling.is_file():
        return sibling
    discovered = shutil.which("tabix")
    if discovered:
        return Path(discovered)
    raise RuntimeError(
        "tabix is required for chromosome-indexed VCF access; refusing a whole-VCF fallback"
    )


def indexed_vcf_companion(vcf_path: Path) -> Path:
    candidates = [Path(f"{vcf_path}.csi"), Path(f"{vcf_path}.tbi")]
    found = [path for path in candidates if path.is_file()]
    if len(found) != 1:
        raise FileNotFoundError(f"expected exactly one CSI/TBI index for {vcf_path}, found {found}")
    return found[0]


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


def write_table(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, sep="\t", index=False, float_format="%.17g", na_rep="NA")


def verify_implementation_gate(
    decision_path: Path, validation_path: Path
) -> dict[str, object]:
    """Fail closed unless the validated offline §13.4 decision is IMPLEMENT."""
    if not decision_path.is_file() or not validation_path.is_file():
        raise FileNotFoundError(
            "§13.4 requires the decision and decision-validation tables from §13.6"
        )
    decisions = pd.read_csv(decision_path, sep="\t")
    required_columns = {
        "section", "decision", "observed_value", "required_operator",
        "required_value", "denominator",
    }
    if required_columns - set(decisions.columns):
        raise ValueError("Phase-5B decision table has an unexpected schema")
    row = decisions.loc[decisions["section"].astype(str).eq("13.4")]
    if len(row) != 1:
        raise ValueError(f"expected exactly one §13.4 decision row, found {len(row)}")
    row = row.iloc[0]
    if str(row["decision"]) != "IMPLEMENT":
        raise PermissionError(f"§13.4 gate is {row['decision']}, not IMPLEMENT")
    observed = float(row["observed_value"])
    required = float(row["required_value"])
    denominator = int(row["denominator"])
    if denominator != 15 or not (0 <= observed <= denominator) or not (0 <= required <= denominator):
        raise PermissionError(
            f"§13.4 gate must be expressed on the frozen 15-cell grid, found "
            f"observed={observed}, required={required}, denominator={denominator}"
        )
    if str(row["required_operator"]) != ">=" or not observed >= required:
        raise PermissionError(
            f"§13.4 numeric gate is not satisfied: {observed} {row['required_operator']} {required}"
        )
    validation = pd.read_csv(validation_path, sep="\t")
    gate_check = (
        validation.get("check", pd.Series(dtype=str))
        .astype(str)
        .eq("13.4 decision exactly follows the predeclared negative-control gate")
    )
    if (
        "status" not in validation
        or validation.empty
        or not validation["status"].eq("PASS").all()
        or int(gate_check.sum()) != 1
    ):
        raise PermissionError("Phase-5B optional-decision validation is absent or not all PASS")
    return {
        "decision": str(row["decision"]),
        "observed_value": observed,
        "required_operator": str(row["required_operator"]),
        "required_value": required,
        "denominator": denominator,
        "decision_table_sha256": file_sha256(decision_path),
        "decision_validation_sha256": file_sha256(validation_path),
    }


def read_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.open(encoding="utf-8") if line.strip()]


def read_popmap(path: Path) -> dict[str, str]:
    result = {}
    for line in read_lines(path):
        fields = line.split("\t")
        if len(fields) < 2:
            raise ValueError(f"invalid popmap row: {line}")
        if fields[0] in result:
            raise ValueError(f"duplicate popmap individual: {fields[0]}")
        result[fields[0]] = fields[1]
    return result


def read_lengths(path: Path) -> dict[str, int]:
    lengths = {}
    for line in read_lines(path):
        fields = line.split()
        if len(fields) < 2:
            continue
        lengths[str(fields[0])] = int(fields[1])
    if not lengths or any(length <= 0 for length in lengths.values()):
        raise ValueError("autosome-length table is empty or non-positive")
    return lengths


def read_gerp(
    path: Path, chromosome: str, chromosome_length: int
) -> tuple[np.ndarray, np.ndarray, dict]:
    positions = []
    scores = []
    wrong_chromosome = 0
    # Stream rather than materializing the BED as a Python string list.  The
    # deposited genome-wide file is ~148 MB; the workflow normally supplies
    # the Phase-4 per-chromosome slice, but this keeps direct CLI use bounded.
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 5:
                continue
            if str(fields[0]) != str(chromosome):
                wrong_chromosome += 1
                continue
            # Upstream BED is zero-based half-open; column 3 END equals 1-based VCF POS.
            positions.append(int(fields[2]))
            scores.append(float(fields[4]))
    pos = np.asarray(positions, dtype=np.int64)
    score = np.asarray(scores, dtype=np.float64)
    if pos.size == 0:
        raise ValueError(f"no GERP records for chromosome {chromosome}")
    if np.any(pos <= 0) or np.any(pos > chromosome_length) or not np.isfinite(score).all():
        raise ValueError("GERP BED contains out-of-bounds positions or non-finite scores")
    order = np.argsort(pos, kind="mergesort")
    pos, score = pos[order], score[order]
    duplicates = int(np.count_nonzero(np.diff(pos) == 0))
    if duplicates:
        raise ValueError(f"GERP BED has {duplicates} duplicate VCF-position keys")
    return pos, score, {
        "gerp_bed_records": int(pos.size),
        "gerp_wrong_chromosome_rows": wrong_chromosome,
        "gerp_duplicate_positions": duplicates,
        "gerp_bounds_failures": 0,
    }


def union_half_open(intervals: np.ndarray) -> tuple[np.ndarray, int]:
    """Union zero-based half-open intervals; return union and overlap base pairs."""
    if intervals.size == 0:
        return np.empty((0, 2), dtype=np.int64), 0
    ordered = np.asarray(intervals, dtype=np.int64)[np.argsort(intervals[:, 0], kind="mergesort")]
    merged = []
    overlap_bp = 0
    start, end = map(int, ordered[0])
    for next_start, next_end in ordered[1:]:
        next_start, next_end = int(next_start), int(next_end)
        if next_start <= end:
            if next_start < end:
                overlap_bp += min(end, next_end) - next_start
            end = max(end, next_end)
        else:
            merged.append((start, end))
            start, end = next_start, next_end
    merged.append((start, end))
    return np.asarray(merged, dtype=np.int64), int(overlap_bp)


def read_rg(
    path: Path,
    chromosome: str,
    chromosome_length: int,
    samples: list[str],
) -> tuple[dict[str, np.ndarray], dict]:
    sample_set = set(samples)
    raw: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    wrong_chromosome = unknown_samples = length_mismatch = bounds_failures = 0
    records = 0
    for line in read_lines(path):
        fields = line.split("\t")
        if len(fields) < 6 or fields[0] != "RG":
            continue
        records += 1
        sample, chrom = fields[1], str(fields[2])
        if chrom != str(chromosome):
            wrong_chromosome += 1
            continue
        if sample not in sample_set:
            unknown_samples += 1
            continue
        start, end, reported_length = int(fields[3]), int(fields[4]), int(fields[5])
        if reported_length != end - start + 1:
            length_mismatch += 1
        if not (1 <= start <= end <= chromosome_length):
            bounds_failures += 1
            continue
        raw[sample].append((start - 1, end, reported_length))

    interval_map: dict[str, np.ndarray] = {}
    overlap_pairs = adjacent_pairs = overlap_bp = 0
    for sample in samples:
        rows = sorted(raw.get(sample, []))
        for left, right in zip(rows, rows[1:]):
            if right[0] < left[1]:
                overlap_pairs += 1
            elif right[0] == left[1]:
                adjacent_pairs += 1
        arr = np.asarray(rows, dtype=np.int64).reshape(-1, 3)
        interval_map[sample] = arr
        if arr.size:
            _, sample_overlap = union_half_open(arr[:, :2])
            overlap_bp += sample_overlap
    audit = {
        "rg_records": records,
        "rg_wrong_chromosome_rows": wrong_chromosome,
        "rg_unknown_samples": unknown_samples,
        "rg_length_mismatches": length_mismatch,
        "rg_bounds_failures": bounds_failures,
        "rg_overlap_pairs": overlap_pairs,
        "rg_adjacent_pairs": adjacent_pairs,
        "rg_overlap_bp": overlap_bp,
    }
    if any(audit[key] for key in (
        "rg_wrong_chromosome_rows",
        "rg_unknown_samples",
        "rg_length_mismatches",
        "rg_bounds_failures",
        "rg_overlap_pairs",
    )):
        raise ValueError(f"RG coordinate/union audit failed: {audit}")
    return interval_map, audit


def prefix_ranges(
    position0: np.ndarray,
    starts0: np.ndarray,
    ends0: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    left = np.searchsorted(position0, starts0, side="left")
    right = np.searchsorted(position0, ends0, side="left")
    return left, right


def shifted_segments(
    intervals: np.ndarray,
    offset: int,
    chromosome_length: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Circularly translate intervals, returning segment starts/ends and source owners."""
    if intervals.size == 0:
        empty = np.asarray([], dtype=np.int64)
        return empty, empty, empty
    start = (intervals[:, 0] + int(offset)) % chromosome_length
    length = intervals[:, 2]
    end_unwrapped = start + length
    owner = np.arange(len(intervals), dtype=np.int64)
    nowrap = end_unwrapped <= chromosome_length
    starts = [start[nowrap], start[~nowrap], np.zeros(np.count_nonzero(~nowrap), dtype=np.int64)]
    ends = [
        end_unwrapped[nowrap],
        np.full(np.count_nonzero(~nowrap), chromosome_length, dtype=np.int64),
        end_unwrapped[~nowrap] - chromosome_length,
    ]
    owners = [owner[nowrap], owner[~nowrap], owner[~nowrap]]
    return np.concatenate(starts), np.concatenate(ends), np.concatenate(owners)


def contributions_by_interval(
    position0: np.ndarray,
    prefix: np.ndarray,
    starts0: np.ndarray,
    ends0: np.ndarray,
    owners: np.ndarray,
    n_intervals: int,
) -> np.ndarray:
    """Prefix-sum contribution per original interval, across all GERP thresholds."""
    if n_intervals == 0:
        return np.zeros((0, prefix.shape[1]), dtype=prefix.dtype)
    left, right = prefix_ranges(position0, starts0, ends0)
    segment = prefix[right] - prefix[left]
    result = np.zeros((n_intervals, prefix.shape[1]), dtype=prefix.dtype)
    np.add.at(result, owners, segment)
    return result


def aggregate_cutoffs(contribution: np.ndarray, lengths: np.ndarray, cutoff_bp: np.ndarray) -> np.ndarray:
    result = np.zeros((contribution.shape[1], len(cutoff_bp)), dtype=contribution.dtype)
    for cutoff_index, cutoff in enumerate(cutoff_bp):
        keep = lengths >= cutoff
        if np.any(keep):
            result[:, cutoff_index] = contribution[keep].sum(axis=0)
    return result


def extract_chromosome_arrays(
    vcf_path: Path,
    chromosome: str,
    expected_samples: list[str],
    gerp_position: np.ndarray,
    gerp_score: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict]:
    fields = [
        "samples",
        "variants/CHROM",
        "variants/POS",
        "variants/REF",
        "variants/ALT",
        "variants/numalt",
        "variants/AA",
        "calldata/GT",
    ]
    tabix = tabix_executable()
    indexed_vcf_companion(vcf_path)
    callset = allel.read_vcf(
        str(vcf_path), fields=fields, region=str(chromosome), alt_number=1,
        tabix=str(tabix),
    )
    if callset is None:
        raise ValueError(f"VCF has no variants on chromosome {chromosome}")
    vcf_samples = [str(value) for value in callset["samples"]]
    if vcf_samples != expected_samples:
        raise ValueError("VCF sample order does not match results/wolf/samples.txt")
    chrom_values = np.asarray(callset["variants/CHROM"]).astype(str)
    if set(chrom_values) != {str(chromosome)}:
        raise ValueError(f"VCF region returned chromosomes {sorted(set(chrom_values))}")
    position = np.asarray(callset["variants/POS"], dtype=np.int64)
    if np.any(position <= 0) or np.any(np.diff(position) < 0):
        raise ValueError("VCF chromosome positions are non-positive or unsorted")
    lookup = np.searchsorted(gerp_position, position)
    matched = (lookup < len(gerp_position)) & (gerp_position[np.minimum(lookup, len(gerp_position) - 1)] == position)
    score = np.full(position.shape, np.nan, dtype=np.float64)
    score[matched] = gerp_score[lookup[matched]]

    ref = np.char.upper(np.asarray(callset["variants/REF"]).astype(str))
    alt_raw = np.asarray(callset["variants/ALT"])
    alt = alt_raw[:, 0].astype(str) if alt_raw.ndim == 2 else alt_raw.astype(str)
    alt = np.char.upper(alt)
    numalt = np.asarray(callset["variants/numalt"], dtype=np.int64)
    ancestral = np.char.upper(np.asarray(callset["variants/AA"]).astype(str))
    # Match wolf_gerp_load.py exactly: AA==REF is accepted even on a rare
    # multiallelic record, while AA==ALT is accepted only when the raw ALT field
    # consists of that single allele. GT alleles other than 0/1 remain uncalled.
    valid_ancestral = matched & (
        (ancestral == ref) | ((numalt == 1) & (ancestral == alt))
    )
    invalid_ancestral = matched & ~valid_ancestral
    gt = np.asarray(callset["calldata/GT"])[valid_ancestral]
    selected_position = position[valid_ancestral]
    selected_score = score[valid_ancestral]
    selected_ref_derived = (ancestral[valid_ancestral] == alt[valid_ancestral])
    called = np.all((gt == 0) | (gt == 1), axis=2)
    # Diploid biallelic counts are only 0..2.  Keeping this int8 avoids a
    # chromosome-sized int64 temporary (~0.75 GB on chr1).
    n_alt = gt.sum(axis=2, dtype=np.int8)
    hom_derived = called & (
        (selected_ref_derived[:, None] & (n_alt == 0))
        | (~selected_ref_derived[:, None] & (n_alt == 2))
    )
    array_bytes = sum(
        value.nbytes for value in callset.values() if isinstance(value, np.ndarray)
    ) + sum(
        value.nbytes
        for value in (
            gt, n_alt, called, hom_derived, selected_score, selected_position,
            score, ref, alt, numalt, ancestral, valid_ancestral,
        )
    )
    if array_bytes >= MAX_ARRAY_BYTES:
        raise MemoryError(
            f"chromosome arrays estimate {array_bytes:,} bytes exceeds {MAX_ARRAY_BYTES:,}-byte cap"
        )
    audit = {
        "vcf_variants": int(len(position)),
        "gerp_positions_matched": int(matched.sum()),
        "valid_gerp_ancestral_sites": int(valid_ancestral.sum()),
        "invalid_ancestral_sites": int(invalid_ancestral.sum()),
        "estimated_array_bytes": int(array_bytes),
    }
    return selected_position - 1, selected_score, called, hom_derived, audit


def metric_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    with np.errstate(divide="ignore", invalid="ignore"):
        frame["inside_burden_rate"] = frame["inside_hom_del_sum"] / frame["inside_eligible_genotype_calls"]
        frame["outside_burden_rate"] = frame["outside_hom_del_sum"] / frame["outside_eligible_genotype_calls"]
        frame["rate_ratio"] = frame["inside_burden_rate"] / frame["outside_burden_rate"]
        frame["log2_enrichment"] = np.log2(frame["rate_ratio"])
    finite = np.isfinite(
        frame[["inside_burden_rate", "outside_burden_rate", "rate_ratio", "log2_enrichment"]]
        .to_numpy(dtype=float)
    ).all(axis=1)
    inherited_failure = frame.get("status", pd.Series("ok", index=frame.index)).astype(str).ne("ok")
    frame["status"] = np.where(~inherited_failure & finite, "ok", "nonconvergent")
    existing_reason = frame.get("failure_reason", pd.Series("", index=frame.index)).fillna("").astype(str)
    frame["failure_reason"] = np.where(
        inherited_failure,
        existing_reason,
        np.where(finite, "", "zero opportunity or non-finite enrichment"),
    )
    return frame


def chromosome_worker(args: argparse.Namespace) -> None:
    chromosome = str(args.chromosome)
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    settings = config["phase5b"]["roh_localization"]
    gate = verify_implementation_gate(
        Path(args.decision_table), Path(args.decision_validation)
    )
    thresholds = np.asarray(sorted(float(x) for x in config["wolf"]["load"]["gerp_sensitivity"]), dtype=float)
    cutoffs_mb = np.asarray(sorted(float(x) for x in config["wolf"]["roh"]["length_cutoffs_mb"]), dtype=float)
    cutoff_bp = np.rint(cutoffs_mb * 1_000_000).astype(np.int64)
    if len(thresholds) != 3 or len(cutoffs_mb) != 5:
        raise ValueError("ROH localization requires the frozen 3 x 5 grid")
    samples = read_lines(Path(args.samples))
    popmap = read_popmap(Path(args.popmap))
    if len(samples) != EXPECTED_N or set(samples) != set(popmap):
        raise ValueError("samples/popmap must contain the same 211 individuals")
    cohorts = sorted(set(popmap.values()))
    cohort_index = {cohort: index for index, cohort in enumerate(cohorts)}
    lengths = read_lengths(Path(args.lengths))
    chromosome_length = lengths[chromosome]
    gerp_position, gerp_score, gerp_audit = read_gerp(
        Path(args.gerp_bed), chromosome, chromosome_length
    )
    intervals, rg_audit = read_rg(
        Path(args.rg), chromosome, chromosome_length, samples
    )
    position0, score, called, hom_derived, vcf_audit = extract_chromosome_arrays(
        Path(args.vcf), chromosome, samples, gerp_position, gerp_score
    )
    qualifies = score[:, None] > thresholds[None, :]
    n_samples, n_thresholds, n_cutoffs = len(samples), len(thresholds), len(cutoffs_mb)
    permutation_reps = int(settings["permutation_reps"])
    base_seed = int(settings["seed"])
    chrom_seed = stable_seed(base_seed, f"chromosome|{chromosome}")
    rng = np.random.default_rng(chrom_seed)
    offsets = rng.integers(0, chromosome_length, size=(permutation_reps, n_samples), dtype=np.int64)

    inside_calls = np.zeros((n_samples, n_thresholds, n_cutoffs), dtype=np.int64)
    inside_copies = np.zeros_like(inside_calls)
    inside_burden = np.zeros((n_samples, n_thresholds, n_cutoffs), dtype=np.float64)
    total_calls = np.zeros((n_samples, n_thresholds), dtype=np.int64)
    total_copies = np.zeros_like(total_calls)
    total_burden = np.zeros((n_samples, n_thresholds), dtype=np.float64)
    all_polarized_calls = called.sum(axis=0, dtype=np.int64)
    null_inside_calls = np.zeros((len(cohorts), permutation_reps, n_thresholds, n_cutoffs), dtype=np.int64)
    null_inside_copies = np.zeros_like(null_inside_calls)
    null_inside_burden = np.zeros((len(cohorts), permutation_reps, n_thresholds, n_cutoffs), dtype=np.float64)

    for sample_index, sample in enumerate(samples):
        call_value = called[:, sample_index, None] & qualifies
        copy_value = (2 * hom_derived[:, sample_index, None] * qualifies).astype(np.int64)
        burden_value = (
            2.0 * score[:, None] * hom_derived[:, sample_index, None] * qualifies
        )
        prefix_call = np.vstack([np.zeros((1, n_thresholds), dtype=np.int64), np.cumsum(call_value, axis=0, dtype=np.int64)])
        prefix_copy = np.vstack([np.zeros((1, n_thresholds), dtype=np.int64), np.cumsum(copy_value, axis=0, dtype=np.int64)])
        prefix_burden = np.vstack([np.zeros((1, n_thresholds), dtype=np.float64), np.cumsum(burden_value, axis=0, dtype=np.float64)])
        total_calls[sample_index] = prefix_call[-1]
        total_copies[sample_index] = prefix_copy[-1]
        total_burden[sample_index] = prefix_burden[-1]

        sample_intervals = intervals[sample]
        n_interval = len(sample_intervals)
        interval_lengths = sample_intervals[:, 2] if n_interval else np.asarray([], dtype=np.int64)
        if n_interval:
            starts, ends = sample_intervals[:, 0], sample_intervals[:, 1]
            owners = np.arange(n_interval, dtype=np.int64)
            inside_calls[sample_index] = aggregate_cutoffs(
                contributions_by_interval(position0, prefix_call, starts, ends, owners, n_interval),
                interval_lengths,
                cutoff_bp,
            )
            inside_copies[sample_index] = aggregate_cutoffs(
                contributions_by_interval(position0, prefix_copy, starts, ends, owners, n_interval),
                interval_lengths,
                cutoff_bp,
            )
            inside_burden[sample_index] = aggregate_cutoffs(
                contributions_by_interval(position0, prefix_burden, starts, ends, owners, n_interval),
                interval_lengths,
                cutoff_bp,
            )
        cohort = cohort_index[popmap[sample]]
        for replicate in range(permutation_reps):
            starts, ends, owners = shifted_segments(
                sample_intervals, int(offsets[replicate, sample_index]), chromosome_length
            )
            null_inside_calls[cohort, replicate] += aggregate_cutoffs(
                contributions_by_interval(position0, prefix_call, starts, ends, owners, n_interval),
                interval_lengths,
                cutoff_bp,
            )
            null_inside_copies[cohort, replicate] += aggregate_cutoffs(
                contributions_by_interval(position0, prefix_copy, starts, ends, owners, n_interval),
                interval_lengths,
                cutoff_bp,
            )
            null_inside_burden[cohort, replicate] += aggregate_cutoffs(
                contributions_by_interval(position0, prefix_burden, starts, ends, owners, n_interval),
                interval_lengths,
                cutoff_bp,
            )

    observed_records = []
    for sample_index, sample in enumerate(samples):
        sample_intervals = intervals[sample]
        for threshold_index, threshold in enumerate(thresholds):
            for cutoff_index, cutoff in enumerate(cutoffs_mb):
                kept = sample_intervals[sample_intervals[:, 2] >= cutoff_bp[cutoff_index]] if len(sample_intervals) else sample_intervals
                raw_span = int(kept[:, 2].sum()) if len(kept) else 0
                union, overlap_bp = union_half_open(kept[:, :2] if len(kept) else np.empty((0, 2), dtype=np.int64))
                union_span = int((union[:, 1] - union[:, 0]).sum()) if len(union) else 0
                in_calls = int(inside_calls[sample_index, threshold_index, cutoff_index])
                in_copies = int(inside_copies[sample_index, threshold_index, cutoff_index])
                in_burden = float(inside_burden[sample_index, threshold_index, cutoff_index])
                observed_records.append(
                    {
                        "chrom": chromosome,
                        "IND": sample,
                        "POP": popmap[sample],
                        "gerp_threshold": threshold,
                        "roh_cutoff_mb": cutoff,
                        "n_roh": len(kept),
                        "roh_raw_span_bp": raw_span,
                        "roh_union_bp": union_span,
                        "roh_overlap_bp": overlap_bp,
                        "inside_eligible_genotype_calls": in_calls,
                        "outside_eligible_genotype_calls": int(total_calls[sample_index, threshold_index] - in_calls),
                        "total_eligible_genotype_calls": int(total_calls[sample_index, threshold_index]),
                        "inside_hom_derived_copies": in_copies,
                        "outside_hom_derived_copies": int(total_copies[sample_index, threshold_index] - in_copies),
                        "total_hom_derived_copies": int(total_copies[sample_index, threshold_index]),
                        "inside_hom_del_sum": in_burden,
                        "outside_hom_del_sum": float(total_burden[sample_index, threshold_index] - in_burden),
                        "total_hom_del_sum": float(total_burden[sample_index, threshold_index]),
                        "all_polarized_gerp_genotype_calls": int(all_polarized_calls[sample_index]),
                    }
                )
    observed = pd.DataFrame(observed_records)

    cohort_total_calls = np.zeros((len(cohorts), n_thresholds), dtype=np.int64)
    cohort_total_copies = np.zeros_like(cohort_total_calls)
    cohort_total_burden = np.zeros((len(cohorts), n_thresholds), dtype=float)
    for sample_index, sample in enumerate(samples):
        ci = cohort_index[popmap[sample]]
        cohort_total_calls[ci] += total_calls[sample_index]
        cohort_total_copies[ci] += total_copies[sample_index]
        cohort_total_burden[ci] += total_burden[sample_index]
    null_records = []
    for cohort_index_value, cohort in enumerate(cohorts):
        for replicate in range(permutation_reps):
            for threshold_index, threshold in enumerate(thresholds):
                for cutoff_index, cutoff in enumerate(cutoffs_mb):
                    in_calls = int(null_inside_calls[cohort_index_value, replicate, threshold_index, cutoff_index])
                    in_copies = int(null_inside_copies[cohort_index_value, replicate, threshold_index, cutoff_index])
                    in_burden = float(null_inside_burden[cohort_index_value, replicate, threshold_index, cutoff_index])
                    total_call = int(cohort_total_calls[cohort_index_value, threshold_index])
                    total_copy = int(cohort_total_copies[cohort_index_value, threshold_index])
                    total_b = float(cohort_total_burden[cohort_index_value, threshold_index])
                    null_records.append(
                        {
                            "chrom": chromosome,
                            "POP": cohort,
                            "replicate": replicate,
                            "base_seed": base_seed,
                            "chrom_seed": chrom_seed,
                            "gerp_threshold": threshold,
                            "roh_cutoff_mb": cutoff,
                            "inside_eligible_genotype_calls": in_calls,
                            "outside_eligible_genotype_calls": total_call - in_calls,
                            "total_eligible_genotype_calls": total_call,
                            "inside_hom_derived_copies": in_copies,
                            "outside_hom_derived_copies": total_copy - in_copies,
                            "total_hom_derived_copies": total_copy,
                            "inside_hom_del_sum": in_burden,
                            "outside_hom_del_sum": total_b - in_burden,
                            "total_hom_del_sum": total_b,
                            "status": "ok",
                            "failure_reason": "",
                        }
                    )
    null = pd.DataFrame(null_records)

    phase4 = pd.read_csv(args.phase4_chrom_load, sep="\t")
    source = observed.sort_values("roh_cutoff_mb").drop_duplicates(["IND", "gerp_threshold"])
    reconciliation = source.merge(
        phase4[["IND", "POP", "THRES", "hom_del_sum", "n_hom_del", "calls"]],
        left_on=["IND", "POP", "gerp_threshold"],
        right_on=["IND", "POP", "THRES"],
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    max_burden_delta = float((reconciliation["total_hom_del_sum"] - reconciliation["hom_del_sum"]).abs().max())
    max_copy_delta = int((reconciliation["total_hom_derived_copies"] - reconciliation["n_hom_del"]).abs().max())
    max_calls_delta = int(
        (reconciliation["all_polarized_gerp_genotype_calls"] - reconciliation["calls"])
        .abs()
        .max()
    )
    qc_status = "PASS" if (
        reconciliation["_merge"].eq("both").all()
        and max_burden_delta <= FLOAT_TOL
        and max_copy_delta == 0
        and max_calls_delta == 0
    ) else "FAIL"
    qc = pd.DataFrame(
        [
            {
                "chrom": chromosome,
                "coordinate_semantics": "RG=1-based-inclusive; internal=0-based-half-open; GERP_BED_END=VCF_POS",
                **gerp_audit,
                **rg_audit,
                **vcf_audit,
                "n_samples": n_samples,
                "n_cohorts": len(cohorts),
                "permutation_reps": permutation_reps,
                "base_seed": base_seed,
                "chrom_seed": chrom_seed,
                **{f"gate_{key}": value for key, value in gate.items()},
                "input_gerp_bed_sha256": file_sha256(Path(args.gerp_bed)),
                "input_rg_sha256": file_sha256(Path(args.rg)),
                "input_phase4_chrom_load_sha256": file_sha256(Path(args.phase4_chrom_load)),
                "input_samples_sha256": file_sha256(Path(args.samples)),
                "input_popmap_sha256": file_sha256(Path(args.popmap)),
                "input_lengths_sha256": file_sha256(Path(args.lengths)),
                "input_config_sha256": file_sha256(Path(args.config)),
                "phase4_join_rows": len(reconciliation),
                "phase4_unmatched_rows": int((reconciliation["_merge"] != "both").sum()),
                "phase4_max_abs_burden_delta": max_burden_delta,
                "phase4_max_abs_copy_delta": max_copy_delta,
                "phase4_max_abs_genotype_call_delta": max_calls_delta,
                "status": qc_status,
            }
        ]
    )
    write_table(observed, Path(args.out_observed))
    write_table(null, Path(args.out_null))
    write_table(qc, Path(args.out_qc))
    if qc_status != "PASS":
        raise SystemExit(f"chromosome {chromosome} failed Phase-4 reconciliation")
    print(
        f"wolf ROH localization chr{chromosome}: {len(observed)} observed rows, "
        f"{len(null)} null rows, array estimate={vcf_audit['estimated_array_bytes'] / 1e6:.1f} MB"
    )


def sum_columns() -> list[str]:
    return [
        "n_roh",
        "roh_raw_span_bp",
        "roh_union_bp",
        "roh_overlap_bp",
        "inside_eligible_genotype_calls",
        "outside_eligible_genotype_calls",
        "total_eligible_genotype_calls",
        "inside_hom_derived_copies",
        "outside_hom_derived_copies",
        "total_hom_derived_copies",
        "inside_hom_del_sum",
        "outside_hom_del_sum",
        "total_hom_del_sum",
        "all_polarized_gerp_genotype_calls",
    ]


def build_individual(
    observed: pd.DataFrame,
    wolf_load: pd.DataFrame,
    wolf_roh: pd.DataFrame,
    genome_length: int,
) -> pd.DataFrame:
    keys = ["IND", "POP", "gerp_threshold", "roh_cutoff_mb"]
    aggregate = observed.groupby(keys, as_index=False)[sum_columns()].sum()
    aggregate["froh_recomputed"] = aggregate["roh_union_bp"] / genome_length
    aggregate = aggregate.merge(
        wolf_load[["IND", "POP", "THRES", "hom_del_sum", "n_hom_del", "calls"]],
        left_on=["IND", "POP", "gerp_threshold"],
        right_on=["IND", "POP", "THRES"],
        how="left",
        validate="many_to_one",
    ).merge(
        wolf_roh[["IND", "POP", "min_length_mb", "F_ROH"]],
        left_on=["IND", "POP", "roh_cutoff_mb"],
        right_on=["IND", "POP", "min_length_mb"],
        how="left",
        validate="many_to_one",
    )
    aggregate["F_ROH_phase4"] = aggregate["F_ROH"]
    aggregate["froh_delta"] = aggregate["froh_recomputed"] - aggregate["F_ROH_phase4"]
    aggregate["phase4_burden_delta"] = aggregate["total_hom_del_sum"] - aggregate["hom_del_sum"]
    aggregate["phase4_copy_delta"] = aggregate["total_hom_derived_copies"] - aggregate["n_hom_del"]
    aggregate["phase4_genotype_call_delta"] = aggregate["all_polarized_gerp_genotype_calls"] - aggregate["calls"]
    aggregate["status"] = "ok"
    aggregate["failure_reason"] = ""
    aggregate = metric_columns(aggregate)
    return aggregate[INDIVIDUAL_COLUMNS].sort_values(
        ["gerp_threshold", "roh_cutoff_mb", "POP", "IND"]
    ).reset_index(drop=True)


def build_null(null_chrom: pd.DataFrame) -> pd.DataFrame:
    keys = ["POP", "replicate", "base_seed", "gerp_threshold", "roh_cutoff_mb"]
    columns = [
        "inside_eligible_genotype_calls",
        "outside_eligible_genotype_calls",
        "total_eligible_genotype_calls",
        "inside_hom_derived_copies",
        "outside_hom_derived_copies",
        "total_hom_derived_copies",
        "inside_hom_del_sum",
        "outside_hom_del_sum",
        "total_hom_del_sum",
    ]
    aggregate = null_chrom.groupby(keys, as_index=False)[columns].sum()
    failures = (
        null_chrom.assign(failed=null_chrom["status"].astype(str).ne("ok"))
        .groupby(keys, as_index=False)["failed"]
        .max()
    )
    aggregate = aggregate.merge(failures, on=keys, validate="one_to_one")
    aggregate["status"] = np.where(aggregate["failed"], "nonconvergent", "ok")
    aggregate["failure_reason"] = np.where(aggregate["failed"], "one or more chromosome rows failed", "")
    aggregate = metric_columns(aggregate)
    return aggregate[NULL_FINAL_COLUMNS].sort_values(
        ["gerp_threshold", "roh_cutoff_mb", "POP", "replicate"]
    ).reset_index(drop=True)


def build_cohort(individual: pd.DataFrame, null: pd.DataFrame, settings: dict) -> pd.DataFrame:
    keys = ["POP", "gerp_threshold", "roh_cutoff_mb"]
    raw_columns = [
        "inside_eligible_genotype_calls",
        "outside_eligible_genotype_calls",
        "inside_hom_derived_copies",
        "outside_hom_derived_copies",
        "inside_hom_del_sum",
        "outside_hom_del_sum",
    ]
    cohort = individual.groupby(keys, as_index=False).agg(
        n_ind=("IND", "nunique"),
        **{column: (column, "sum") for column in raw_columns},
    )
    cohort["status"] = "ok"
    cohort["failure_reason"] = ""
    cohort = metric_columns(cohort)
    ci_pct = float(settings["ci_pct"])
    alpha = (100.0 - ci_pct) / 2.0
    summaries = []
    for row in cohort.itertuples(index=False):
        sample = null.loc[
            null["POP"].eq(row.POP)
            & null["gerp_threshold"].eq(row.gerp_threshold)
            & null["roh_cutoff_mb"].eq(row.roh_cutoff_mb)
        ]
        valid = sample.loc[sample["status"].eq("ok") & np.isfinite(sample["log2_enrichment"])]
        failed = len(sample) - len(valid)
        if len(valid):
            values = valid["log2_enrichment"].to_numpy(dtype=float)
            median = float(np.median(values))
            ci_low, ci_high = np.percentile(values, [alpha, 100.0 - alpha])
            distance = abs(float(row.log2_enrichment) - median)
            extreme = int(np.count_nonzero(np.abs(values - median) >= distance))
            p_value = (extreme + 1.0) / (len(values) + 1.0)
        else:
            median = ci_low = ci_high = p_value = float("nan")
        summaries.append(
            {
                "POP": row.POP,
                "gerp_threshold": row.gerp_threshold,
                "roh_cutoff_mb": row.roh_cutoff_mb,
                "null_valid_reps": len(valid),
                "null_failed_reps": failed,
                "null_median_log2_enrichment": median,
                "null_ci_low": float(ci_low),
                "null_ci_high": float(ci_high),
                "observed_minus_null_median": float(row.log2_enrichment) - median,
                "permutation_p_two_sided": p_value,
            }
        )
    cohort = cohort.merge(pd.DataFrame(summaries), on=keys, validate="one_to_one")
    cohort["direction"] = np.select(
        [cohort["log2_enrichment"] > 0, cohort["log2_enrichment"] < 0],
        ["enriched_inside_roh", "depleted_inside_roh"],
        default="no_difference",
    )
    null_finite = np.isfinite(
        cohort[[
            "null_median_log2_enrichment",
            "null_ci_low",
            "null_ci_high",
            "permutation_p_two_sided",
        ]].to_numpy(dtype=float)
    ).all(axis=1)
    cohort.loc[~null_finite, "status"] = "nonconvergent"
    cohort.loc[~null_finite, "failure_reason"] = "no finite circular-shift null replicates"
    return cohort[COHORT_COLUMNS].sort_values(
        ["gerp_threshold", "roh_cutoff_mb", "POP"]
    ).reset_index(drop=True)


def build_figure_values(cohort: pd.DataFrame, default_cutoff: float) -> pd.DataFrame:
    records = []
    for row in cohort.itertuples(index=False):
        records.append(
            {
                "figure": "wolf_roh_localization_ribbon.png",
                "record_type": "ribbon_cell",
                "panel": f"GERP>{row.gerp_threshold:g}",
                "POP": row.POP,
                "gerp_threshold": row.gerp_threshold,
                "roh_cutoff_mb": row.roh_cutoff_mb,
                "estimate": row.log2_enrichment,
                "null_median": row.null_median_log2_enrichment,
                "ci_low": row.null_ci_low,
                "ci_high": row.null_ci_high,
                "permutation_p_two_sided": row.permutation_p_two_sided,
                "n_ind": row.n_ind,
            }
        )
        if math.isclose(float(row.roh_cutoff_mb), default_cutoff):
            records.append(
                {
                    "figure": "wolf_roh_localization_forest.png",
                    "record_type": "forest_cell",
                    "panel": f"GERP>{row.gerp_threshold:g}",
                    "POP": row.POP,
                    "gerp_threshold": row.gerp_threshold,
                    "roh_cutoff_mb": row.roh_cutoff_mb,
                    "estimate": row.log2_enrichment,
                    "null_median": row.null_median_log2_enrichment,
                    "ci_low": row.null_ci_low,
                    "ci_high": row.null_ci_high,
                    "permutation_p_two_sided": row.permutation_p_two_sided,
                    "n_ind": row.n_ind,
                }
            )
    return pd.DataFrame(records)


def render_forest(values: pd.DataFrame, path: Path) -> None:
    data = values.loc[values["record_type"].eq("forest_cell")]
    thresholds = sorted(data["gerp_threshold"].unique())
    fig, axes = plt.subplots(1, len(thresholds), figsize=(15, 6.5), sharey=True, constrained_layout=True)
    if len(thresholds) == 1:
        axes = [axes]
    populations = sorted(data["POP"].unique())
    for ax, threshold in zip(axes, thresholds):
        panel = data.loc[data["gerp_threshold"].eq(threshold)].set_index("POP").loc[populations]
        y = np.arange(len(populations))[::-1]
        estimate = panel["estimate"].to_numpy(dtype=float)
        lower = panel["ci_low"].to_numpy(dtype=float)
        upper = panel["ci_high"].to_numpy(dtype=float)
        ax.hlines(y, lower, upper, color="#888888", linewidth=2, label="circular-shift 95% interval")
        ax.scatter(estimate, y, color="#8c2d36", s=35, label="observed")
        ax.scatter(panel["null_median"], y, color="#245b78", marker="|", s=90, label="null median")
        ax.axvline(0, color="black", linestyle="--", linewidth=0.8)
        ax.set_yticks(y, populations)
        ax.set_xlabel("log2 inside/outside burden per eligible SNP-genotype call")
        ax.set_title(f"GERP>{threshold:g}")
    axes[-1].legend(frameon=False, fontsize=8)
    fig.suptitle("ROH-localized realized burden at the predeclared 1.5 Mb cutoff — genomic proxy")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, metadata={"Software": "congen-phase5b"})
    plt.close(fig)


def render_ribbon(values: pd.DataFrame, path: Path) -> None:
    data = values.loc[values["record_type"].eq("ribbon_cell")]
    thresholds = sorted(data["gerp_threshold"].unique())
    populations = sorted(data["POP"].unique())
    colors = dict(zip(populations, plt.get_cmap("tab10").colors, strict=False))
    fig, axes = plt.subplots(1, len(thresholds), figsize=(16, 5.7), sharey=True, constrained_layout=True)
    if len(thresholds) == 1:
        axes = [axes]
    for ax, threshold in zip(axes, thresholds):
        panel = data.loc[data["gerp_threshold"].eq(threshold)]
        for population in populations:
            line = panel.loc[panel["POP"].eq(population)].sort_values("roh_cutoff_mb")
            x = line["roh_cutoff_mb"].to_numpy(dtype=float)
            ax.fill_between(
                x,
                line["ci_low"].to_numpy(dtype=float),
                line["ci_high"].to_numpy(dtype=float),
                color=colors[population],
                alpha=0.07,
            )
            ax.plot(x, line["estimate"], marker="o", markersize=3, color=colors[population], label=population)
        ax.axhline(0, color="black", linestyle="--", linewidth=0.8)
        ax.set_title(f"GERP>{threshold:g}")
        ax.set_xlabel("Minimum ROH length (Mb)")
    axes[0].set_ylabel("Observed log2 inside/outside burden ratio; shading = null interval")
    axes[-1].legend(frameon=False, fontsize=7, ncol=2)
    fig.suptitle("Wolf ROH-localized realized burden across the frozen 3 × 5 grid")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, metadata={"Software": "congen-phase5b"})
    plt.close(fig)


def collate(args: argparse.Namespace) -> None:
    config_path = Path(args.config)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    settings = config["phase5b"]["roh_localization"]
    gate = verify_implementation_gate(
        Path(args.decision_table), Path(args.decision_validation)
    )
    vcf_index = indexed_vcf_companion(Path(args.vcf))
    tabix = tabix_executable()
    observed_paths = [Path(path) for path in args.observed]
    null_paths = [Path(path) for path in args.null]
    qc_paths = [Path(path) for path in args.qc]
    expected_chromosomes = int(config["wolf"]["n_autosomes"])
    if not (len(observed_paths) == len(null_paths) == len(qc_paths) == expected_chromosomes):
        raise ValueError(f"collation requires {expected_chromosomes} observed/null/QC chromosome files")
    observed_chrom = pd.concat([pd.read_csv(path, sep="\t") for path in observed_paths], ignore_index=True)
    null_chrom = pd.concat([pd.read_csv(path, sep="\t") for path in null_paths], ignore_index=True)
    qc = pd.concat([pd.read_csv(path, sep="\t") for path in qc_paths], ignore_index=True).sort_values("chrom")
    if qc["chrom"].astype(str).nunique() != expected_chromosomes or not qc["status"].eq("PASS").all():
        raise ValueError("chromosome QC is incomplete or failed")
    wolf_load = pd.read_csv(args.wolf_load, sep="\t")
    wolf_roh = pd.read_csv(args.wolf_roh, sep="\t")
    genome_length = sum(read_lengths(Path(args.lengths)).values())
    individual = build_individual(observed_chrom, wolf_load, wolf_roh, genome_length)
    null = build_null(null_chrom)
    cohort = build_cohort(individual, null, settings)
    expected_individual_rows = EXPECTED_N * len(config["wolf"]["load"]["gerp_sensitivity"]) * len(
        config["wolf"]["roh"]["length_cutoffs_mb"]
    )
    expected_null_rows = (
        wolf_load["POP"].nunique()
        * int(settings["permutation_reps"])
        * len(config["wolf"]["load"]["gerp_sensitivity"])
        * len(config["wolf"]["roh"]["length_cutoffs_mb"])
    )
    if len(individual) != expected_individual_rows or len(null) != expected_null_rows:
        raise ValueError(
            f"incomplete final grid: individual={len(individual)}/{expected_individual_rows}, "
            f"null={len(null)}/{expected_null_rows}"
        )
    reconciliation_columns = [
        "phase4_burden_delta", "phase4_copy_delta", "phase4_genotype_call_delta",
        "froh_delta", "roh_overlap_bp",
    ]
    if (
        individual[reconciliation_columns].isna().any().any()
        or
        individual["phase4_burden_delta"].abs().max() > FLOAT_TOL
        or individual["phase4_copy_delta"].abs().max() != 0
        or individual["phase4_genotype_call_delta"].abs().max() != 0
        or individual["froh_delta"].abs().max() > 5e-12
        or individual["roh_overlap_bp"].max() != 0
    ):
        raise ValueError("final Phase-4 load/F_ROH reconciliation failed")
    figure_values = build_figure_values(
        cohort, float(config["wolf"]["roh"]["long_roh_threshold_mb"])
    )

    output_paths = {
        "individual": Path(args.out_individual),
        "cohort": Path(args.out_cohort),
        "null": Path(args.out_null),
        "qc": Path(args.out_qc),
        "figure_values": Path(args.out_figure_values),
        "forest": Path(args.out_forest),
        "ribbon": Path(args.out_ribbon),
        "provenance": Path(args.out_provenance),
    }
    write_table(individual, output_paths["individual"])
    write_table(cohort, output_paths["cohort"])
    write_table(null, output_paths["null"])
    write_table(qc, output_paths["qc"])
    write_table(figure_values, output_paths["figure_values"])
    render_forest(figure_values, output_paths["forest"])
    render_ribbon(figure_values, output_paths["ribbon"])

    scientific_names = ["individual", "cohort", "null", "qc", "figure_values"]
    scientific_files = [(FINAL_OUTPUTS[name], output_paths[name]) for name in scientific_names]
    chrom_seeds = {
        str(row.chrom): int(row.chrom_seed) for row in qc[["chrom", "chrom_seed"]].itertuples(index=False)
    }
    chromosome_source_sha256 = {
        str(row.chrom): {
            "gerp_bed": str(row.input_gerp_bed_sha256),
            "rg": str(row.input_rg_sha256),
            "phase4_chrom_load": str(row.input_phase4_chrom_load_sha256),
        }
        for row in qc[[
            "chrom", "input_gerp_bed_sha256", "input_rg_sha256",
            "input_phase4_chrom_load_sha256",
        ]].itertuples(index=False)
    }
    provenance = {
        "schema_version": "1.0",
        "analysis": "wolf_roh_localized_realized_burden",
        "claim_boundary": "ROH localization of genomic burden proxies; not fitness, harm, or causation.",
        "coordinate_semantics": {
            "RG": "bcftools roh START/END are 1-based inclusive; reported length is END-START+1",
            "internal": "zero-based half-open interval unions",
            "GERP": "BED column 3 END is used as the 1-based VCF POS key",
        },
        "opportunity_denominator": {
            "canonical_name": "eligible_polarized_gerp_threshold_snp_genotype_calls",
            "unit": "individual-by-SNP genotype calls",
            "eligibility": (
                "variant-only allSNPs VCF record with exact GERP key, valid AA polarization, "
                "diploid 0/1 genotype, and GERP score strictly above threshold"
            ),
            "not_callable_genome_bases": True,
            "ascertainment_caveat": (
                "The denominator is restricted to assayed SNP records; circular shifts preserve "
                "the observed SNP/GERP landscape but do not eliminate every ascertainment effect."
            ),
        },
        "settings": {
            "seed": int(settings["seed"]),
            "permutation_reps": int(settings["permutation_reps"]),
            "ci_pct": float(settings["ci_pct"]),
            "null_model": str(settings["null_model"]),
            "denominator": str(settings["denominator"]),
            "gerp_thresholds": sorted(float(x) for x in config["wolf"]["load"]["gerp_sensitivity"]),
            "roh_cutoffs_mb": sorted(float(x) for x in config["wolf"]["roh"]["length_cutoffs_mb"]),
            "max_array_bytes": MAX_ARRAY_BYTES,
        },
        "implementation_gate": gate,
        "chromosome_source_sha256": chromosome_source_sha256,
        "seeds": {
            "base_seed": int(settings["seed"]),
            "derivation": "sha256(base_seed|chromosome|CHROM) first 8 bytes modulo 2^63-1",
            "chromosome_seeds": chrom_seeds,
        },
        "inputs": {
            **{str(path): file_sha256(path) for path in [*observed_paths, *null_paths, *qc_paths]},
            str(args.wolf_load): file_sha256(Path(args.wolf_load)),
            str(args.wolf_roh): file_sha256(Path(args.wolf_roh)),
            str(args.lengths): file_sha256(Path(args.lengths)),
            str(args.decision_table): file_sha256(Path(args.decision_table)),
            str(args.vcf): file_sha256(Path(args.vcf)),
            str(vcf_index): file_sha256(vcf_index),
            str(args.gerp_source): file_sha256(Path(args.gerp_source)),
            str(args.samples): file_sha256(Path(args.samples)),
            str(args.popmap): file_sha256(Path(args.popmap)),
            str(config_path): file_sha256(config_path),
            str(args.decision_validation): file_sha256(Path(args.decision_validation)),
            "scripts/python/wolf_roh_localization.py": file_sha256(Path(__file__)),
        },
        "counts": {
            "individual_rows": len(individual),
            "cohort_rows": len(cohort),
            "null_rows": len(null),
            "chromosomes": len(qc),
            "null_failed_rows": int(null["status"].ne("ok").sum()),
            "cohort_failed_rows": int(cohort["status"].ne("ok").sum()),
        },
        "reconciliation": {
            "max_abs_phase4_burden_delta": float(individual["phase4_burden_delta"].abs().max()),
            "max_abs_phase4_copy_delta": int(individual["phase4_copy_delta"].abs().max()),
            "max_abs_phase4_genotype_call_delta": int(individual["phase4_genotype_call_delta"].abs().max()),
            "max_abs_froh_delta": float(individual["froh_delta"].abs().max()),
            "max_roh_overlap_bp": int(individual["roh_overlap_bp"].max()),
        },
        "scientific_hash_algorithm": "sha256 over labelled deterministic TSV bytes",
        "scientific_hash_files": [label for label, _ in scientific_files],
        "scientific_hash": scientific_hash(scientific_files),
        "output_sha256": {
            FINAL_OUTPUTS[name]: file_sha256(output_paths[name])
            for name in [*scientific_names, "forest", "ribbon"]
        },
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
            "scikit_allel": allel.__version__,
            "matplotlib": matplotlib.__version__,
            # Keep the sendable provenance host-independent while retaining
            # exact binary identity through the checksum below.  The
            # acceptance validator resolves this command token through PATH.
            "tabix_executable": tabix.name,
            "tabix_executable_sha256": file_sha256(tabix),
        },
    }
    output_paths["provenance"].parent.mkdir(parents=True, exist_ok=True)
    output_paths["provenance"].write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"wolf ROH localization: {len(individual)} individual cells, {len(cohort)} cohort cells, "
        f"{len(null)} null rows; scientific hash={provenance['scientific_hash']}"
    )


def self_check() -> None:
    intervals = np.asarray([[4, 10, 6]], dtype=np.int64)
    union, overlap = union_half_open(intervals[:, :2])
    assert overlap == 0 and union.tolist() == [[4, 10]]
    position0 = np.asarray([0, 4, 9, 12], dtype=np.int64)
    values = np.asarray([[1], [2], [4], [8]], dtype=np.int64)
    prefix = np.vstack([np.zeros((1, 1), dtype=np.int64), np.cumsum(values, axis=0)])
    owners = np.asarray([0], dtype=np.int64)
    observed = contributions_by_interval(position0, prefix, intervals[:, 0], intervals[:, 1], owners, 1)
    assert observed[0, 0] == 6  # positions 4 and 9; half-open end 10
    starts, ends, owners = shifted_segments(intervals, 4, 14)  # [8,14), no wrap
    shifted = contributions_by_interval(position0, prefix, starts, ends, owners, 1)
    assert shifted[0, 0] == 12  # positions 9 and 12
    wrap_interval = np.asarray([[8, 12, 4]], dtype=np.int64)
    starts, ends, owners = shifted_segments(wrap_interval, 4, 14)  # [12,14) U [0,2)
    wrapped = contributions_by_interval(position0, prefix, starts, ends, owners, 1)
    assert wrapped[0, 0] == 9  # positions 12 and 0
    nested = aggregate_cutoffs(
        np.asarray([[3, 6, 9], [5, 10, 15]], dtype=np.int64),
        np.asarray([100, 500]),
        np.asarray([100, 500]),
    )
    assert nested.tolist() == [[8, 5], [16, 10], [24, 15]]
    with tempfile.TemporaryDirectory(prefix="wolf-roh-localization-self-check-") as temporary:
        decision = Path(temporary) / "decision.tsv"
        validation = Path(temporary) / "validation.tsv"
        decision.write_text(
            "section\tdecision\tobserved_value\trequired_operator\trequired_value\tdenominator\n"
            "13.4\tIMPLEMENT\t15\t>=\t12\t15\n",
            encoding="utf-8",
        )
        validation.write_text(
            "check\tstatus\n"
            "13.4 decision exactly follows the predeclared negative-control gate\tPASS\n",
            encoding="utf-8",
        )
        gate = verify_implementation_gate(decision, validation)
        assert gate["decision"] == "IMPLEMENT" and gate["observed_value"] == 15
    print("wolf_roh_localization self-check: OK")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    worker = subparsers.add_parser("chromosome", help="compute one chromosome")
    worker.add_argument("--chromosome", required=True)
    worker.add_argument("--vcf", required=True)
    worker.add_argument("--gerp-bed", required=True)
    worker.add_argument("--rg", required=True)
    worker.add_argument("--phase4-chrom-load", required=True)
    worker.add_argument("--samples", default="results/wolf/samples.txt")
    worker.add_argument("--popmap", default="results/wolf/popmap.tsv")
    worker.add_argument("--lengths", default="results/wolf/autosome_lengths.tsv")
    worker.add_argument("--config", default="config/config.yaml")
    worker.add_argument("--decision-table", default=DEFAULT_DECISION_TABLE)
    worker.add_argument("--decision-validation", default=DEFAULT_DECISION_VALIDATION)
    worker.add_argument("--out-observed", required=True)
    worker.add_argument("--out-null", required=True)
    worker.add_argument("--out-qc", required=True)

    combine = subparsers.add_parser("collate", help="collate all chromosome outputs")
    combine.add_argument("--observed", nargs="+", required=True)
    combine.add_argument("--null", nargs="+", required=True)
    combine.add_argument("--qc", nargs="+", required=True)
    combine.add_argument("--wolf-load", default="results/tables/wolf_load.tsv")
    combine.add_argument("--wolf-roh", default="results/tables/wolf_roh.tsv")
    combine.add_argument("--lengths", default="results/wolf/autosome_lengths.tsv")
    combine.add_argument("--config", default="config/config.yaml")
    combine.add_argument(
        "--vcf",
        default="data/wolf/vcf/Pol.2out.mac2/100S95F14R.chr1-38.allSNPs.wfm.vcf.gz",
    )
    combine.add_argument(
        "--gerp-source",
        default="data/wolf/gerp/100S95F14R.chr1-38.allSNPs.rates.unique.bed",
    )
    combine.add_argument("--samples", default="results/wolf/samples.txt")
    combine.add_argument("--popmap", default="results/wolf/popmap.tsv")
    combine.add_argument("--decision-table", default=DEFAULT_DECISION_TABLE)
    combine.add_argument("--decision-validation", default=DEFAULT_DECISION_VALIDATION)
    combine.add_argument("--out-individual", default=FINAL_OUTPUTS["individual"])
    combine.add_argument("--out-cohort", default=FINAL_OUTPUTS["cohort"])
    combine.add_argument("--out-null", default=FINAL_OUTPUTS["null"])
    combine.add_argument("--out-qc", default=FINAL_OUTPUTS["qc"])
    combine.add_argument("--out-figure-values", default=FINAL_OUTPUTS["figure_values"])
    combine.add_argument("--out-forest", default=FINAL_OUTPUTS["forest"])
    combine.add_argument("--out-ribbon", default=FINAL_OUTPUTS["ribbon"])
    combine.add_argument("--out-provenance", default=FINAL_OUTPUTS["provenance"])

    subparsers.add_parser("self-check", help="run synthetic coordinate/interval tests only")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "chromosome":
        chromosome_worker(args)
    elif args.command == "collate":
        collate(args)
    else:
        self_check()


if __name__ == "__main__":
    main()
