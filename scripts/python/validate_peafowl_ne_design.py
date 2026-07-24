#!/usr/bin/env python3
"""Independent acceptance-gate validator for the peafowl N_e design study.

The validator reconciles the configured scenario/empirical grids, every
currentNe2 attempt and raw-output hash, the repeated seeded pilot, summary
denominators and Wilson intervals, the figure-value bridge, the rendered PNG,
and provenance.  It intentionally treats true N_e=500 as a boundary case and
never scores it correct or incorrect.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import struct
from statistics import NormalDist
import subprocess
import sys
import tempfile
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[2]
VALIDATION_COLUMNS = ["check_id", "status", "details"]
MC_Z = NormalDist().inv_cdf(0.975)
SCHEMA_VERSION = "phase5b-ne-design-v2-pedigree-haldane"
CACHE_ROW_SCHEMA = "phase5b-ne-design-row-cache-v2"
CACHE_MANIFEST_SCHEMA = "phase5b-ne-design-cache-manifest-v2"
PEDIGREE_GOLDEN_SHA256 = "6fb3c1b84e3a98bcce1768949108df6637cb0455429de0ac46db924b2921d60f"
INF_THRESHOLD = 1e7
XCHROM_HDR = "Ne estimation based only on LD between chromosomes"
WHOLE_HDR = "Ne estimation by integration over the whole genome"
K_PREFIX = "# Estimated Number of full siblings that a random individuals has in the population"
N_IND_LABEL = "# Total number of individuals in the input file:"

SCENARIO_COLUMNS = [
    "analysis_type", "scenario_id", "replicate", "true_ne", "truth_class",
    "sample_size", "marker_density", "seed", "simulation_attempt",
    "candidate_loci", "panel_seed", "simulation_runtime_seconds", "simulation_generations",
    "initial_maf_low", "initial_maf_high", "input_vcf_sha256",
    "marker_ids_sha256", "sample_ids_sha256", "command", "exit_code",
    "timed_out", "runtime_seconds", "raw_output_path", "raw_output_sha256",
    "log_path", "log_sha256", "parse_error", "execution_failure_reason",
    "ne_point", "ci_low", "ci_high", "ci_width", "interval_covers_true",
    "n_ind", "n_snps", "k", "ne_basis", "converged", "gbf_state",
    "outcome_class", "pilot_member", "expansion_status",
]
EMPIRICAL_COLUMNS = [
    "analysis_type", "empirical_id", "population", "observed_n", "sample_size",
    "marker_density", "replicate", "seed", "subset_seed", "subset_reused", "sample_ids",
    "sample_ids_sha256", "input_vcf_sha256", "marker_ids_sha256", "command",
    "exit_code", "timed_out", "runtime_seconds", "raw_output_path",
    "raw_output_sha256", "log_path", "log_sha256", "parse_error",
    "execution_failure_reason", "ne_point", "ci_low", "ci_high", "ci_width",
    "n_ind", "n_snps", "k", "ne_basis", "converged", "gbf_state",
    "outcome_class",
]
SUMMARY_COLUMNS = [
    "analysis_type", "population", "true_ne", "truth_class", "sample_size",
    "marker_density", "reps_planned", "n_attempted", "n_executed",
    "n_execution_failure", "execution_failure_rate", "execution_failure_ci_low",
    "execution_failure_ci_high", "n_converged", "convergence_rate",
    "convergence_ci_low", "convergence_ci_high", "n_correct_confident",
    "correct_confident_rate", "correct_confident_ci_low",
    "correct_confident_ci_high", "n_incorrect_confident",
    "incorrect_confident_rate", "incorrect_confident_ci_low",
    "incorrect_confident_ci_high", "n_indeterminate", "indeterminate_rate",
    "indeterminate_ci_low", "indeterminate_ci_high",
    "n_boundary_confident_pass", "boundary_confident_pass_rate",
    "boundary_confident_pass_ci_low", "boundary_confident_pass_ci_high",
    "n_boundary_confident_fail", "boundary_confident_fail_rate",
    "boundary_confident_fail_ci_low", "boundary_confident_fail_ci_high",
    "n_pass", "pass_rate", "pass_ci_low", "pass_ci_high", "n_fail",
    "fail_rate", "fail_ci_low", "fail_ci_high", "n_intervals",
    "n_interval_covers_true", "coverage_rate", "coverage_ci_low",
    "coverage_ci_high", "n_unbounded_ci", "mean_ci_width", "median_ci_width",
    "median_ne_point", "mean_runtime_seconds", "total_runtime_seconds",
    "monte_carlo_ci_pct", "expansion_status",
]
FIGURE_VALUE_COLUMNS = [
    "panel", "analysis_type", "population", "true_ne", "truth_class",
    "sample_size", "marker_density", "metric", "value", "ci_low", "ci_high",
    "n_attempted", "target_outcome",
]
PILOT_HASH_COLUMNS = [
    "scenario_id", "replicate", "true_ne", "truth_class", "sample_size",
    "marker_density", "seed", "simulation_attempt", "candidate_loci",
    "panel_seed", "simulation_generations", "initial_maf_low",
    "initial_maf_high", "input_vcf_sha256", "marker_ids_sha256",
    "sample_ids_sha256", "exit_code", "timed_out", "parse_error",
    "execution_failure_reason", "ne_point", "ci_low", "ci_high", "ci_width",
    "interval_covers_true", "n_ind", "n_snps", "k", "ne_basis", "converged",
    "gbf_state", "outcome_class",
]
PILOT_HASH_FLOAT_COLUMNS = {
    "initial_maf_low", "initial_maf_high", "ne_point", "ci_low", "ci_high",
    "ci_width", "k",
}


@dataclass(frozen=True)
class Settings:
    seed: int
    true_ne: tuple[int, ...]
    sample_sizes: tuple[int, ...]
    marker_densities: tuple[int, ...]
    pilot_reps: int
    final_reps: int
    empirical_reps: int
    simulation_generations: int
    initial_maf_low: float
    initial_maf_high: float
    currentne2_threads: int
    run_timeout_seconds: float
    pilot_expansion_max_seconds: float
    genome_size_morgans: float
    ci_pct: float
    resolution_truths: tuple[int, ...]
    resolution_min_correct_confident_ci_low: float
    resolution_max_incorrect_confident_ci_high: float


@dataclass(frozen=True)
class EmpiricalVariant:
    chrom: str
    pos: int
    ref: str
    alt: str
    genotypes: tuple[str, ...]

    @property
    def marker_id(self) -> str:
        return f"{self.chrom}:{self.pos}:{self.ref}:{self.alt}"


def resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_settings(config_path: Path) -> Settings:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))["phase5b"]["ne_design"]
    settings = Settings(
        seed=int(raw["seed"]), true_ne=tuple(map(int, raw["true_ne"])),
        sample_sizes=tuple(map(int, raw["sample_sizes"])),
        marker_densities=tuple(map(int, raw["marker_densities"])),
        pilot_reps=int(raw["pilot_reps"]), final_reps=int(raw["final_reps"]),
        empirical_reps=int(raw["empirical_reps"]),
        simulation_generations=int(raw["simulation_generations"]),
        initial_maf_low=float(raw["initial_maf_low"]),
        initial_maf_high=float(raw["initial_maf_high"]),
        currentne2_threads=int(raw["currentne2_threads"]),
        run_timeout_seconds=float(raw["run_timeout_seconds"]),
        pilot_expansion_max_seconds=float(raw["pilot_expansion_max_seconds"]),
        genome_size_morgans=float(raw["genome_size_morgans"]),
        ci_pct=float(raw["ci_pct"]),
        resolution_truths=tuple(map(int, raw["resolution_truths"])),
        resolution_min_correct_confident_ci_low=float(
            raw["resolution_min_correct_confident_ci_low"]
        ),
        resolution_max_incorrect_confident_ci_high=float(
            raw["resolution_max_incorrect_confident_ci_high"]
        ),
    )
    errors: list[str] = []
    if settings.true_ne != (100, 250, 500, 1000):
        errors.append("true_ne must be 100/250/500/1000")
    if settings.sample_sizes != (5, 10, 15, 20, 30):
        errors.append("sample_sizes must be 5/10/15/20/30")
    if settings.marker_densities != (250, 500, 1000):
        errors.append("marker_densities must be 250/500/1000")
    if settings.resolution_truths != (250, 1000):
        errors.append("resolution_truths must be 250/1000")
    if settings.pilot_reps != 2 or settings.final_reps != 12:
        errors.append("pilot/final reps must be frozen at 2/12")
    if settings.empirical_reps != 6 or settings.simulation_generations != 15:
        errors.append("empirical reps/generations must be frozen at 6/15")
    if settings.ci_pct != 90 or settings.genome_size_morgans != 32:
        errors.append("currentNe2 CI/map contract must be 90%/32M")
    if errors:
        raise ValueError("; ".join(errors))
    return settings


def settings_sha256(settings: Settings) -> str:
    return sha256_text(json.dumps(asdict(settings), sort_keys=True, separators=(",", ":")))


def read_tsv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)


def text_value(value: object) -> str:
    if value is None or value is pd.NA:
        return ""
    return str(value)


def numeric(value: object) -> float:
    text = text_value(value).strip().lower()
    if text == "":
        return math.nan
    if text in {"inf", "+inf", "infinity", "+infinity"}:
        return math.inf
    if text in {"-inf", "-infinity"}:
        return -math.inf
    try:
        return float(text)
    except ValueError:
        return math.nan


def integer(value: object, default: int = -1) -> int:
    text = text_value(value).strip()
    try:
        # Seeds use signed 63-bit integers and cannot safely pass through a
        # binary float before conversion.
        return int(text)
    except ValueError:
        number = numeric(text)
        return int(number) if math.isfinite(number) and number.is_integer() else default


def bool_value(value: object) -> bool | None:
    text = text_value(value).strip().lower()
    if text in {"true", "1"}:
        return True
    if text in {"false", "0"}:
        return False
    return None


def numbers_equal(left: object, right: object, *, atol: float = 2e-8, rtol: float = 2e-8) -> bool:
    a, b = numeric(left), numeric(right)
    if math.isnan(a) and math.isnan(b):
        return True
    if math.isinf(a) or math.isinf(b):
        return a == b
    return math.isclose(a, b, rel_tol=rtol, abs_tol=atol)


def finite_probability(value: object) -> bool:
    number = numeric(value)
    return math.isfinite(number) and 0.0 <= number <= 1.0


def repository_path(value: object) -> Path | None:
    text = text_value(value).strip()
    if not text:
        return None
    path = Path(text)
    return path if path.is_absolute() else ROOT / path


def within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def exact_cache_path(public_raw: Path, raw_dir: Path) -> Path:
    relative = public_raw.resolve().relative_to(raw_dir.resolve())
    return raw_dir / ".exact_cache" / relative


def checkpoint_namespace(checkpoint: Path, raw_dir: Path) -> dict[str, str]:
    relative = checkpoint.resolve().relative_to((raw_dir / "checkpoints").resolve())
    canonical_raw = raw_dir.resolve() / relative.with_suffix(".txt")
    return {
        "checkpoint_relative": (Path("checkpoints") / relative).as_posix(),
        "canonical_raw_path": display_path(canonical_raw),
        "canonical_log_path": display_path(canonical_raw.with_suffix(".log")),
    }


def execution_log_header(path: Path, command_label: str) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    labels = (command_label, "exit_code", "timed_out", "wall_seconds")
    if len(lines) < 4:
        raise ValueError("short execution log")
    values: dict[str, str] = {}
    for line, label in zip(lines[:4], labels):
        prefix = f"{label}: "
        if not line.startswith(prefix):
            raise ValueError("execution log header mismatch")
        values[label] = line[len(prefix):]
    return {
        "command": values[command_label], "exit_code": int(values["exit_code"]),
        "timed_out": values["timed_out"] == "true",
        "wall_seconds": float(values["wall_seconds"]),
    }


def privacy_tokens() -> tuple[str, ...]:
    return (
        "/" + "Users/", "/" + "private/", "/var/" + "folders/",
        "cg-ne-" + "design-",
    )


class Audit:
    def __init__(self) -> None:
        self.rows: list[dict[str, str]] = []

    def add(self, check_id: str, passed: bool, details: str) -> None:
        self.rows.append({
            "check_id": check_id,
            "status": "PASS" if passed else "FAIL",
            "details": details,
        })

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=VALIDATION_COLUMNS)


def mismatch_detail(values: Sequence[str], limit: int = 5) -> str:
    if not values:
        return "none"
    shown = list(values[:limit])
    suffix = f" (+{len(values) - limit} more)" if len(values) > limit else ""
    return "; ".join(shown) + suffix


def schema_check(audit: Audit, name: str, frame: pd.DataFrame, expected: Sequence[str]) -> None:
    actual = list(frame.columns)
    audit.add(
        f"schema_{name}", actual == list(expected),
        f"expected={len(expected)} columns; actual={len(actual)}; "
        f"missing={sorted(set(expected) - set(actual))}; extra={sorted(set(actual) - set(expected))}",
    )


def local_truth_class(true_ne: int) -> str:
    return "below" if true_ne < 500 else ("above" if true_ne > 500 else "boundary")


def local_stable_seed(base_seed: int, *parts: object) -> int:
    payload = "\x1f".join([str(base_seed), *(str(part) for part in parts)])
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "big") & ((1 << 63) - 1)


def panel_fingerprint(
    genotypes: np.ndarray, chromosomes: np.ndarray, map_morgans: np.ndarray,
    marker_ids: Sequence[str], seed: int, attempt: int, candidate_loci: int,
    panel_seed: int,
) -> str:
    digest = hashlib.sha256()
    digest.update(np.ascontiguousarray(genotypes).tobytes())
    digest.update(np.asarray(chromosomes, dtype="<i2").tobytes())
    digest.update("\n".join(format(value, ".17g") for value in map_morgans).encode())
    digest.update("\n".join(marker_ids).encode())
    digest.update(f"{seed}|{attempt}|{candidate_loci}|{panel_seed}".encode())
    return digest.hexdigest()


def local_wf_generation(
    population: np.ndarray, rng: np.random.Generator,
    chromosome_indices: Sequence[np.ndarray],
) -> np.ndarray:
    if population.dtype != np.uint8 or population.ndim != 3 or population.shape[1] != 2:
        raise ValueError("population must be explicit uint8 H[N,2,L]")
    population_size = population.shape[0]
    parents = rng.integers(0, population_size, size=(population_size, 2))
    offspring = np.empty_like(population)
    for gamete in range(2):
        parent = parents[:, gamete]
        for loci in chromosome_indices:
            n_loci = len(loci)
            starts = rng.integers(0, 2, size=population_size, dtype=np.uint8)
            if n_loci == 1:
                homologs = starts[:, None]
            else:
                distance = 1.0 / n_loci
                haldane_r = (1.0 - math.exp(-2.0 * distance)) / 2.0
                toggles = rng.random((population_size, n_loci - 1)) < haldane_r
                parity = np.bitwise_xor.accumulate(toggles, axis=1).astype(np.uint8, copy=False)
                homologs = np.empty((population_size, n_loci), dtype=np.uint8)
                homologs[:, 0] = starts
                homologs[:, 1:] = starts[:, None] ^ parity
            offspring[:, gamete, loci] = population[
                parent[:, None], homologs, loci[None, :]
            ]
    return offspring


def local_simulate_panel(
    settings: Settings, true_ne: int, replicate: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], int, int, int, int]:
    seed = local_stable_seed(settings.seed, "scenario", true_ne, replicate)
    min_n, max_n = min(settings.sample_sizes), max(settings.sample_sizes)
    max_markers = max(settings.marker_densities)
    if max_n > true_ne:
        raise ValueError("nested sample exceeds simulated population")
    for attempt, factor in enumerate((4, 8, 16), start=1):
        panel_seed = local_stable_seed(seed, "attempt", attempt)
        rng = np.random.default_rng(panel_seed)
        candidate_count = max_markers * factor
        maf = rng.uniform(settings.initial_maf_low, settings.initial_maf_high, candidate_count)
        frequencies = np.where(rng.random(candidate_count) < 0.5, maf, 1.0 - maf)
        population = (
            rng.random((true_ne, 2, candidate_count)) < frequencies[None, None, :]
        ).astype(np.uint8)
        chromosomes = np.arange(candidate_count, dtype=np.int16) % 32 + 1
        ranks = np.arange(candidate_count, dtype=np.int32) // 32
        loci_by_chromosome = [
            np.flatnonzero(chromosomes == chromosome) for chromosome in range(1, 33)
        ]
        for _ in range(settings.simulation_generations):
            population = local_wf_generation(population, rng, loci_by_chromosome)
        diploids = population.sum(axis=1)
        individual_order = rng.permutation(true_ne)
        nested = diploids[individual_order[:max_n], :]
        allele_count = nested[:min_n, :].sum(axis=0)
        polymorphic = np.flatnonzero((allele_count > 0) & (allele_count < 2 * min_n))
        quotas = np.full(32, max_markers // 32, dtype=int)
        quotas[:max_markers % 32] += 1
        selected_by_chromosome: list[np.ndarray] = []
        for chromosome, quota in enumerate(quotas, start=1):
            eligible = polymorphic[chromosomes[polymorphic] == chromosome]
            if len(eligible) < quota:
                break
            selected_by_chromosome.append(rng.permutation(eligible)[:quota])
        if len(selected_by_chromosome) != 32:
            continue
        locus_order = np.array([
            int(selected_by_chromosome[chromosome][rank])
            for rank in range(int(quotas.max()))
            for chromosome in range(32)
            if rank < len(selected_by_chromosome[chromosome])
        ], dtype=np.int32)
        selected = nested[:, locus_order].astype(np.uint8, copy=False)
        selected_chromosomes = chromosomes[locus_order]
        chromosome_sizes = np.array([len(indices) for indices in loci_by_chromosome])
        selected_map = np.array([
            (ranks[index] + 0.5) / chromosome_sizes[chromosomes[index] - 1]
            for index in locus_order
        ], dtype=float)
        marker_ids = [f"sim_locus_{index + 1:05d}" for index in range(max_markers)]
        return (
            selected, selected_chromosomes, selected_map, marker_ids,
            seed, attempt, candidate_count, panel_seed,
        )
    raise RuntimeError("independent simulator could not obtain nested marker panel")


def local_simulation_vcf_bytes(
    genotypes: np.ndarray, chromosomes: np.ndarray, map_morgans: np.ndarray,
    sample_size: int, marker_density: int,
) -> tuple[bytes, list[str], list[str]]:
    samples = [f"SIM{index + 1:03d}" for index in range(sample_size)]
    marker_ids = [f"sim_locus_{index + 1:05d}" for index in range(marker_density)]
    ordered: list[tuple[int, int, int]] = []
    for index in range(marker_density):
        position = max(1, int(round(float(map_morgans[index]) * 100_000_000)))
        ordered.append((int(chromosomes[index]), position, index))
    ordered.sort()
    lines = [
        "##fileformat=VCFv4.2",
        "##source=CG_phase5b_ne_design_neutral_Wright_Fisher_free_assortment",
        *[f"##contig=<ID={chromosome}>" for chromosome in range(1, 33)],
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t" + "\t".join(samples),
    ]
    dosage = ("0/0", "0/1", "1/1")
    for chromosome, position, index in ordered:
        calls = [dosage[int(value)] for value in genotypes[:sample_size, index]]
        lines.append(
            f"{chromosome}\t{position}\t{marker_ids[index]}\tA\tG\t.\tPASS\t.\tGT\t"
            + "\t".join(calls)
        )
    return ("\n".join(lines) + "\n").encode(), samples, marker_ids


def local_wilson(successes: int, total: int) -> tuple[float, float]:
    if total <= 0:
        return math.nan, math.nan
    p = successes / total
    denominator = 1.0 + MC_Z * MC_Z / total
    centre = (p + MC_Z * MC_Z / (2.0 * total)) / denominator
    half = MC_Z * math.sqrt(
        p * (1.0 - p) / total + MC_Z * MC_Z / (4.0 * total * total)
    ) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def local_outcome(truth: str, state: str, execution_failure: bool) -> str:
    if execution_failure:
        return "execution_failure"
    if truth == "boundary":
        if state == "pass":
            return "boundary_confident_pass"
        if state == "fail":
            return "boundary_confident_fail"
        return "indeterminate"
    correct_state = "fail" if truth == "below" else "pass"
    incorrect_state = "pass" if truth == "below" else "fail"
    if state == correct_state:
        return "correct_confident"
    if state == incorrect_state:
        return "incorrect_confident"
    return "indeterminate"


def local_gbf_state(point: float, low: float, high: float) -> str:
    if math.isnan(point):
        return "indeterminate"
    effective_low = -math.inf if math.isnan(low) else low
    effective_high = math.inf if math.isnan(high) else high
    if effective_low <= 500 <= effective_high:
        return "indeterminate"
    return "pass" if point > 500 else "fail"


def _to_currentne_float(value: str | None) -> float:
    if value is None:
        return math.nan
    try:
        number = float(value.strip())
    except ValueError:
        return math.nan
    if not math.isfinite(number) or abs(number) >= INF_THRESHOLD:
        return math.inf
    return number


def _estimate_block(lines: Sequence[str], header: str) -> list[str] | None:
    start = next((index for index, line in enumerate(lines) if header in line), None)
    if start is None:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("# Ne estimation") or "(end of output)" in lines[index]:
            end = index
            break
    return list(lines[start:end])


def _value_after(lines: Sequence[str] | None, label: str) -> str | None:
    if lines is None:
        return None
    for index, line in enumerate(lines):
        if line.strip() == label and index + 1 < len(lines):
            return lines[index + 1]
    return None


def _value_startswith(lines: Sequence[str] | None, prefix: str) -> str | None:
    if lines is None:
        return None
    for index, line in enumerate(lines):
        if line.strip().startswith(prefix) and index + 1 < len(lines):
            return lines[index + 1]
    return None


def _estimate(lines: Sequence[str] | None) -> tuple[float, float, float]:
    return (
        _to_currentne_float(_value_after(lines, "# Ne point estimate:")),
        _to_currentne_float(_value_after(lines, "# Lower limit of 90% CI:")),
        _to_currentne_float(_value_after(lines, "# Upper limit of 90% CI:")),
    )


def independent_parse_currentne2(raw_path: Path) -> dict[str, object]:
    """Re-extract the authoritative headline and 90% interval from raw text."""
    lines = raw_path.read_text(encoding="utf-8", errors="replace").splitlines()
    block = _estimate_block(lines, XCHROM_HDR)
    point, low, high = _estimate(block)
    basis = "cross_chromosome"
    if math.isnan(point):
        block = _estimate_block(lines, WHOLE_HDR)
        point, low, high = _estimate(block)
        basis = "whole_genome"
    if math.isnan(point):
        basis = "none"

    raw_n_snps = _value_after(
        lines,
        "# Number of SNPs included in the analysis (only polymorphic and with less than 20% missing data):",
    )
    try:
        n_snps = int(float(raw_n_snps))
    except (TypeError, ValueError):
        n_snps = -1
    try:
        n_ind = int(float(_value_after(lines, N_IND_LABEL)))
    except (TypeError, ValueError):
        n_ind = -1
    try:
        k_value = float(_value_startswith(block, K_PREFIX)) if basis != "none" else math.nan
    except (TypeError, ValueError):
        k_value = math.nan
    return {
        "ne_point": point,
        "ci_low": low,
        "ci_high": high,
        "ci_width": high - low if not (math.isnan(low) or math.isnan(high)) else math.nan,
        "n_ind": n_ind,
        "n_snps": n_snps,
        "k": k_value,
        "ne_basis": basis,
        "converged": basis != "none" and not math.isnan(point),
        "gbf_state": local_gbf_state(point, low, high),
    }


def _canonical(value: object) -> object:
    text = text_value(value)
    if text == "":
        return None
    boolean = bool_value(text)
    if text.strip().lower() in {"true", "false"}:
        return boolean
    if not any(character in text.lower() for character in (".", "e")):
        try:
            return int(text)
        except ValueError:
            pass
    number = numeric(text)
    if not math.isnan(number):
        if math.isinf(number):
            return "inf" if number > 0 else "-inf"
        return format(number, ".15g")
    return text


def independent_scientific_hash(frame: pd.DataFrame, columns: Sequence[str]) -> str:
    order_columns = [
        column for column in ("scenario_id", "replicate", "sample_size", "marker_density")
        if column in columns
    ]
    ordered = frame.loc[:, list(columns)].copy()
    sort_keys: list[str] = []
    for column in order_columns:
        key = f"__sort_{column}"
        sort_keys.append(key)
        ordered[key] = (
            pd.to_numeric(ordered[column], errors="coerce")
            if column in {"replicate", "sample_size", "marker_density"}
            else ordered[column]
        )
    ordered = ordered.sort_values(sort_keys, kind="mergesort").loc[:, list(columns)]
    rows = []
    for row in ordered.itertuples(index=False, name=None):
        canonical_row = []
        for column, value in zip(columns, row):
            if column in PILOT_HASH_FLOAT_COLUMNS:
                number = numeric(value)
                if math.isnan(number):
                    canonical_row.append(None)
                elif math.isinf(number):
                    canonical_row.append("inf" if number > 0 else "-inf")
                else:
                    canonical_row.append(format(number, ".15g"))
            else:
                canonical_row.append(_canonical(value))
        rows.append(canonical_row)
    payload = json.dumps({"columns": list(columns), "rows": rows}, sort_keys=True, separators=(",", ":"))
    return sha256_text(payload)


def validate_artifact_paths(
    frame: pd.DataFrame, kind: str, raw_dir: Path,
) -> tuple[list[str], int, int]:
    errors: list[str] = []
    parsed_count = 0
    success_count = 0
    numeric_fields = ["ne_point", "ci_low", "ci_high", "ci_width", "k"]
    for position, row in frame.iterrows():
        label = (
            text_value(row.get("scenario_id")) or text_value(row.get("empirical_id"))
        ) + f"/r{text_value(row.get('replicate'))}/{kind}"
        reason = text_value(row.get("execution_failure_reason"))
        parse_error = text_value(row.get("parse_error"))
        command = text_value(row.get("command"))
        timed_out = bool_value(row.get("timed_out")) is True
        exit_code = integer(row.get("exit_code"))
        raw_path = repository_path(row.get("raw_output_path"))
        log_path = repository_path(row.get("log_path"))

        if timed_out and "timeout" not in reason:
            errors.append(f"{label}: timeout not named in failure reason")
        if exit_code != 0 and command and f"exit_code_{exit_code}" not in reason:
            errors.append(f"{label}: non-zero exit not named in failure reason")
        if parse_error and command and "parse_error" not in reason:
            errors.append(f"{label}: parser error not named in failure reason")
        if not command and reason != "input_generation_error":
            errors.append(f"{label}: no command without input_generation_error")
        if not reason:
            success_count += 1
            if exit_code != 0 or timed_out or parse_error:
                errors.append(f"{label}: success row has exit/timeout/parser failure")
            if integer(row.get("n_ind")) != integer(row.get("sample_size")):
                errors.append(f"{label}: n_ind != requested sample_size")
            if integer(row.get("n_snps")) != integer(row.get("marker_density")):
                errors.append(f"{label}: analyzed n_snps != configured marker_density")
            for hash_name in ("input_vcf_sha256", "marker_ids_sha256", "sample_ids_sha256"):
                if len(text_value(row.get(hash_name))) != 64:
                    errors.append(f"{label}: missing {hash_name}")

        if command:
            marker_density = integer(row.get("marker_density"))
            if f"-s {marker_density}" not in command:
                errors.append(f"{label}: command lacks configured -s marker cap")
            if raw_path is None or not within(raw_path, raw_dir):
                errors.append(f"{label}: raw path absent/outside raw directory")
            if log_path is None or not within(log_path, raw_dir):
                errors.append(f"{label}: log path absent/outside raw directory")
            if log_path is None or not log_path.is_file():
                errors.append(f"{label}: log file missing")
            elif sha256_file(log_path) != text_value(row.get("log_sha256")):
                errors.append(f"{label}: log SHA-256 mismatch")

        if raw_path is not None and raw_path.is_file():
            if sha256_file(raw_path) != text_value(row.get("raw_output_sha256")):
                errors.append(f"{label}: raw SHA-256 mismatch")
            try:
                parsed = independent_parse_currentne2(raw_path)
                parsed_count += 1
                for field in numeric_fields:
                    if not numbers_equal(row.get(field), parsed[field]):
                        errors.append(f"{label}: raw parser mismatch in {field}")
                for field in ("n_ind", "n_snps"):
                    if integer(row.get(field)) != int(parsed[field]):
                        errors.append(f"{label}: raw parser mismatch in {field}")
                if text_value(row.get("ne_basis")) != str(parsed["ne_basis"]):
                    errors.append(f"{label}: raw parser mismatch in ne_basis")
                if bool_value(row.get("converged")) is not bool(parsed["converged"]):
                    errors.append(f"{label}: raw parser mismatch in converged")
                if text_value(row.get("gbf_state")) != str(parsed["gbf_state"]):
                    errors.append(f"{label}: raw parser mismatch in gbf_state")
            except Exception as exc:  # malformed raw output must already be an explicit failed row
                if not parse_error:
                    errors.append(f"{label}: independent raw parse raised {type(exc).__name__}")
        elif command and not reason:
            errors.append(f"{label}: successful command has no raw output")
    return errors, parsed_count, success_count


def expected_scenario_keys(settings: Settings, reps: int) -> set[tuple[int, int, int, int]]:
    return {
        (true_ne, sample_size, markers, replicate)
        for true_ne, sample_size, markers, replicate in itertools.product(
            settings.true_ne, settings.sample_sizes, settings.marker_densities, range(1, reps + 1)
        )
    }


def actual_scenario_keys(frame: pd.DataFrame) -> list[tuple[int, int, int, int]]:
    return [
        (integer(row.true_ne), integer(row.sample_size), integer(row.marker_density), integer(row.replicate))
        for row in frame.itertuples(index=False)
    ]


def validate_scenario_rows(frame: pd.DataFrame, settings: Settings) -> list[str]:
    errors: list[str] = []
    allowed = {
        "execution_failure", "correct_confident", "incorrect_confident", "indeterminate",
        "boundary_confident_pass", "boundary_confident_fail",
    }
    for row in frame.to_dict("records"):
        true_ne = integer(row["true_ne"])
        sample_size = integer(row["sample_size"])
        markers = integer(row["marker_density"])
        replicate = integer(row["replicate"])
        label = f"Ne{true_ne}/n{sample_size}/m{markers}/r{replicate}"
        truth = local_truth_class(true_ne)
        expected_id = f"ne{true_ne:04d}_n{sample_size:02d}_m{markers:04d}"
        if row["analysis_type"] != "scenario" or row["scenario_id"] != expected_id:
            errors.append(f"{label}: analysis/scenario ID mismatch")
        if row["truth_class"] != truth:
            errors.append(f"{label}: truth_class mismatch")
        expected_seed = local_stable_seed(settings.seed, "scenario", true_ne, replicate)
        if integer(row["seed"]) != expected_seed:
            errors.append(f"{label}: seed mismatch")
        if integer(row["simulation_generations"]) != settings.simulation_generations:
            errors.append(f"{label}: simulation generation mismatch")
        if not numbers_equal(row["initial_maf_low"], settings.initial_maf_low):
            errors.append(f"{label}: initial MAF low mismatch")
        if not numbers_equal(row["initial_maf_high"], settings.initial_maf_high):
            errors.append(f"{label}: initial MAF high mismatch")
        if row["outcome_class"] not in allowed:
            errors.append(f"{label}: unknown outcome {row['outcome_class']}")
        expected_outcome = local_outcome(
            truth, row["gbf_state"], bool(row["execution_failure_reason"])
        )
        if row["outcome_class"] != expected_outcome:
            errors.append(f"{label}: outcome mismatch ({row['outcome_class']} != {expected_outcome})")
        if truth == "boundary" and row["outcome_class"] in {"correct_confident", "incorrect_confident"}:
            errors.append(f"{label}: boundary scored correct/incorrect")
        if truth != "boundary" and row["outcome_class"].startswith("boundary_"):
            errors.append(f"{label}: non-boundary has boundary outcome")
        expected_samples = [f"SIM{i + 1:03d}" for i in range(sample_size)]
        expected_markers = [f"sim_locus_{i + 1:05d}" for i in range(markers)]
        if not row["execution_failure_reason"]:
            if row["sample_ids_sha256"] != sha256_text("\n".join(expected_samples)):
                errors.append(f"{label}: deterministic sample-ID hash mismatch")
            if row["marker_ids_sha256"] != sha256_text("\n".join(expected_markers)):
                errors.append(f"{label}: deterministic marker-ID hash mismatch")
        low, high = numeric(row["ci_low"]), numeric(row["ci_high"])
        expected_coverage: bool | None = None
        if not math.isnan(low) and not math.isnan(high) and not row["execution_failure_reason"]:
            expected_coverage = low <= true_ne <= high
        observed_coverage = bool_value(row["interval_covers_true"])
        if observed_coverage is not expected_coverage:
            errors.append(f"{label}: interval coverage flag mismatch")
    return errors


def replay_scenario_inputs(
    frame: pd.DataFrame, settings: Settings,
    panel_cache: dict[tuple[int, int], tuple[np.ndarray, np.ndarray, np.ndarray, list[str], int, int, int, int]],
) -> list[str]:
    errors: list[str] = []
    for row in frame.to_dict("records"):
        true_ne, replicate = integer(row["true_ne"]), integer(row["replicate"])
        sample_size, markers = integer(row["sample_size"]), integer(row["marker_density"])
        label = f"Ne{true_ne}/n{sample_size}/m{markers}/r{replicate}"
        key = (true_ne, replicate)
        if key not in panel_cache:
            panel_cache[key] = local_simulate_panel(settings, true_ne, replicate)
        panel = panel_cache[key]
        genotypes, chromosomes, map_morgans, marker_ids, seed, attempt, candidates, panel_seed = panel
        if len(set(chromosomes.tolist())) != 32:
            errors.append(f"{label}: replayed panel does not span 32 chromosomes")
        expected_trace = {
            "seed": seed, "simulation_attempt": attempt,
            "candidate_loci": candidates, "panel_seed": panel_seed,
        }
        for field, expected in expected_trace.items():
            if integer(row[field]) != expected:
                errors.append(f"{label}: {field} mismatch")
        payload, samples, selected_markers = local_simulation_vcf_bytes(
            genotypes, chromosomes, map_morgans, sample_size, markers
        )
        if text_value(row["input_vcf_sha256"]) != hashlib.sha256(payload).hexdigest():
            errors.append(f"{label}: independently regenerated VCF hash mismatch")
        if text_value(row["sample_ids_sha256"]) != sha256_text("\n".join(samples)):
            errors.append(f"{label}: replayed sample hash mismatch")
        if text_value(row["marker_ids_sha256"]) != sha256_text("\n".join(selected_markers)):
            errors.append(f"{label}: replayed marker-prefix hash mismatch")
        if text_value(row["execution_failure_reason"]) == "input_generation_error":
            errors.append(f"{label}: analysis reported input failure but independent panel succeeded")
        if marker_ids[:markers] != selected_markers:
            errors.append(f"{label}: marker prefix is not nested")
    return errors


def local_subset_plan(samples: Sequence[str], n: int, reps: int, seed: int) -> list[tuple[list[str], bool]]:
    combinations = list(itertools.combinations(samples, n))
    order = np.random.default_rng(seed).permutation(len(combinations))
    shuffled = [combinations[index] for index in order]
    return [(list(shuffled[rep % len(shuffled)]), rep >= len(shuffled)) for rep in range(reps)]


def read_populations(path: Path) -> dict[str, list[str]]:
    frame = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    return {
        str(population): group["sample"].tolist()
        for population, group in frame.groupby("population", sort=True)
    }


def locate_executable(requested: str | None, name: str) -> Path:
    if requested:
        candidate = resolve(requested)
    else:
        found = shutil.which(name)
        candidate = Path(found) if found else Path("")
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise FileNotFoundError(f"executable not found: {candidate}")
    return candidate.resolve()


def query_empirical_reservoir(
    bcftools: Path, vcf_path: Path, sample_count: int, capacity: int, seed: int,
) -> tuple[list[EmpiricalVariant], int]:
    process = subprocess.Popen(
        [str(bcftools), "query", "-f", r"%CHROM\t%POS\t%REF\t%ALT[\t%GT]\n", str(vcf_path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    assert process.stdout is not None
    rng = np.random.default_rng(seed)
    reservoir: list[EmpiricalVariant] = []
    seen = 0
    for line in process.stdout:
        fields = line.rstrip("\n").split("\t")
        if len(fields) != 4 + sample_count:
            continue
        chrom, pos, ref, alt, *genotypes = fields
        if "," in alt or len(ref) != 1 or len(alt) != 1:
            continue
        try:
            variant = EmpiricalVariant(chrom, int(pos), ref, alt, tuple(genotypes))
        except ValueError:
            continue
        seen += 1
        if len(reservoir) < capacity:
            reservoir.append(variant)
        else:
            replacement = int(rng.integers(0, seen))
            if replacement < capacity:
                reservoir[replacement] = variant
    stderr = process.stderr.read() if process.stderr is not None else ""
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"bcftools empirical replay failed ({return_code}): {stderr[-300:]}")
    if len(reservoir) < capacity:
        raise RuntimeError(f"empirical replay reservoir short: {len(reservoir)} < {capacity}")
    return reservoir, seen


def _parse_gt(value: str) -> tuple[int, int] | None:
    genotype = value.split(":", 1)[0]
    if "." in genotype:
        return None
    separator = "/" if "/" in genotype else ("|" if "|" in genotype else None)
    if separator is None:
        return None
    try:
        left, right = genotype.split(separator, 1)
        return int(left), int(right)
    except ValueError:
        return None


def strict_empirical_eligible(
    variant: EmpiricalVariant, sample_indices: Sequence[int],
) -> bool:
    calls = [_parse_gt(variant.genotypes[index]) for index in sample_indices]
    valid = [call for call in calls if call is not None]
    if len(valid) * 5 <= 4 * len(sample_indices):
        return False
    alleles = [allele for call in valid for allele in call]
    return bool(alleles) and min(alleles) != max(alleles)


def _chromosome_key(chromosome: str) -> tuple[object, ...]:
    tail = chromosome.rsplit("_", 1)[-1]
    return (0, int(tail)) if tail.isdigit() else (1, chromosome)


def local_empirical_vcf_bytes(
    variants: Sequence[EmpiricalVariant], sample_indices: Sequence[int],
    sample_names: Sequence[str],
) -> tuple[bytes, list[str]]:
    ordered = sorted(
        variants, key=lambda row: (_chromosome_key(row.chrom), row.pos, row.ref, row.alt)
    )
    contigs = sorted({row.chrom for row in ordered}, key=_chromosome_key)
    lines = [
        "##fileformat=VCFv4.2", "##source=CG_phase5b_empirical_seeded_rarefaction",
        *[f"##contig=<ID={contig}>" for contig in contigs],
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t" + "\t".join(sample_names),
    ]
    for row in ordered:
        calls = [row.genotypes[index].replace("|", "/") for index in sample_indices]
        lines.append(
            f"{row.chrom}\t{row.pos}\t{row.marker_id}\t{row.ref}\t{row.alt}\t.\tPASS\t.\tGT\t"
            + "\t".join(calls)
        )
    return ("\n".join(lines) + "\n").encode(), [row.marker_id for row in ordered]


def replay_empirical_inputs(
    frame: pd.DataFrame, settings: Settings, bcftools: Path, empirical_vcf: Path,
    provenance: dict[str, object],
) -> list[str]:
    errors: list[str] = []
    listed = subprocess.run(
        [str(bcftools), "query", "-l", str(empirical_vcf)],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    sample_index = {sample: index for index, sample in enumerate(listed)}
    capacity = max(25_000, max(settings.marker_densities) * 25)
    reservoir_seed = local_stable_seed(settings.seed, "empirical", "candidate_reservoir")
    variants, source_count = query_empirical_reservoir(
        bcftools, empirical_vcf, len(listed), capacity, reservoir_seed
    )
    reservoir_hash = sha256_text("\n".join(sorted(row.marker_id for row in variants)))
    empirical_provenance = provenance.get("empirical", {})
    if not isinstance(empirical_provenance, dict):
        errors.append("empirical provenance is not an object")
        empirical_provenance = {}
    expected_meta = {
        "source_variant_count": source_count, "reservoir_capacity": capacity,
        "reservoir_seed": reservoir_seed, "reservoir_marker_sha256": reservoir_hash,
        "vcf_samples": len(listed),
    }
    for key, expected in expected_meta.items():
        observed = empirical_provenance.get(key)
        if observed != expected:
            errors.append(f"empirical provenance {key} mismatch")

    subset_cache: dict[tuple[str, int, int], tuple[list[EmpiricalVariant], list[int], list[str]]] = {}
    for row in frame.to_dict("records"):
        population, n, replicate = row["population"], integer(row["sample_size"]), integer(row["replicate"])
        markers = integer(row["marker_density"])
        label = f"{population}/n{n}/m{markers}/r{replicate}"
        subset = text_value(row["sample_ids"]).split(";") if row["sample_ids"] else []
        try:
            indices = [sample_index[sample] for sample in subset]
        except KeyError as exc:
            errors.append(f"{label}: subset sample absent from empirical VCF ({exc})")
            continue
        key = (population, n, replicate)
        if key not in subset_cache:
            eligible = [variant for variant in variants if strict_empirical_eligible(variant, indices)]
            marker_seed = local_stable_seed(
                settings.seed, "empirical", population, n, replicate, "markers"
            )
            rng = np.random.default_rng(marker_seed)
            if eligible:
                eligible = [eligible[index] for index in rng.permutation(len(eligible))]
            subset_cache[key] = eligible, indices, subset
        eligible, indices, subset = subset_cache[key]
        if len(eligible) < markers:
            if row["execution_failure_reason"] != "input_generation_error":
                errors.append(f"{label}: insufficient strict-called markers not recorded as input failure")
            if row["input_vcf_sha256"] or row["marker_ids_sha256"]:
                errors.append(f"{label}: input-generation failure has input hashes")
            continue
        payload, marker_ids = local_empirical_vcf_bytes(eligible[:markers], indices, subset)
        if row["input_vcf_sha256"] != hashlib.sha256(payload).hexdigest():
            errors.append(f"{label}: independently replayed empirical VCF hash mismatch")
        if row["marker_ids_sha256"] != sha256_text("\n".join(marker_ids)):
            errors.append(f"{label}: independently replayed empirical marker hash mismatch")
        if integer(row["n_snps"]) not in {-1, markers}:
            errors.append(f"{label}: currentNe2 analyzed density violates strict-called input contract")
    return errors


def expected_empirical_keys(
    settings: Settings, populations: dict[str, list[str]],
) -> set[tuple[str, int, int, int]]:
    keys: set[tuple[str, int, int, int]] = set()
    minimum = min(settings.sample_sizes)
    for population, samples in populations.items():
        for n in range(minimum, len(samples) + 1):
            for markers in settings.marker_densities:
                for replicate in range(1, settings.empirical_reps + 1):
                    keys.add((population, n, markers, replicate))
    return keys


def validate_empirical_rows(
    frame: pd.DataFrame, settings: Settings, populations: dict[str, list[str]],
) -> list[str]:
    errors: list[str] = []
    expected_plans: dict[tuple[str, int], list[tuple[list[str], bool]]] = {}
    for population, samples in populations.items():
        for n in range(min(settings.sample_sizes), len(samples) + 1):
            subset_seed = local_stable_seed(settings.seed, "empirical", population, n, "subsets")
            expected_plans[(population, n)] = local_subset_plan(
                samples, n, settings.empirical_reps, subset_seed
            )

    for row in frame.to_dict("records"):
        population = row["population"]
        n = integer(row["sample_size"])
        markers = integer(row["marker_density"])
        replicate = integer(row["replicate"])
        label = f"{population}/n{n}/m{markers}/r{replicate}"
        observed = len(populations.get(population, []))
        if row["analysis_type"] != "empirical":
            errors.append(f"{label}: analysis_type is not empirical")
        if integer(row["observed_n"]) != observed or n > observed:
            errors.append(f"{label}: empirical n exceeds/mismatches observed n")
        if row["empirical_id"] != f"{population}_n{n:02d}_m{markers:04d}":
            errors.append(f"{label}: empirical ID mismatch")
        expected_seed = local_stable_seed(settings.seed, "empirical", population, n, replicate, "markers")
        if integer(row["seed"]) != expected_seed:
            errors.append(f"{label}: marker seed mismatch")
        expected_subset_seed = local_stable_seed(
            settings.seed, "empirical", population, n, "subsets"
        )
        if integer(row["subset_seed"]) != expected_subset_seed:
            errors.append(f"{label}: subset seed mismatch")
        plans = expected_plans.get((population, n), [])
        if not (1 <= replicate <= len(plans)):
            errors.append(f"{label}: replicate outside plan")
        else:
            expected_subset, expected_reused = plans[replicate - 1]
            observed_subset = row["sample_ids"].split(";") if row["sample_ids"] else []
            if observed_subset != expected_subset:
                errors.append(f"{label}: seeded subset mismatch")
            if bool_value(row["subset_reused"]) is not expected_reused:
                errors.append(f"{label}: subset_reused mismatch")
            if row["sample_ids_sha256"] != sha256_text("\n".join(observed_subset)):
                errors.append(f"{label}: sample-ID SHA-256 mismatch")
            if len(observed_subset) != n or not set(observed_subset).issubset(populations[population]):
                errors.append(f"{label}: subset size/membership mismatch")
        reason = bool(row["execution_failure_reason"])
        expected_outcome = "execution_failure" if reason else f"empirical_{row['gbf_state']}"
        if row["outcome_class"] != expected_outcome:
            errors.append(f"{label}: empirical outcome mismatch")
        if row["outcome_class"] in {"correct_confident", "incorrect_confident"}:
            errors.append(f"{label}: empirical unknown truth scored correct/incorrect")
    return errors


INTEGER_ROW_FIELDS = {
    "replicate", "true_ne", "observed_n", "sample_size", "marker_density",
    "seed", "subset_seed", "simulation_attempt", "candidate_loci", "panel_seed",
    "simulation_generations", "exit_code", "n_ind", "n_snps",
}
FLOAT_ROW_FIELDS = {
    "simulation_runtime_seconds", "initial_maf_low", "initial_maf_high",
    "runtime_seconds", "ne_point", "ci_low", "ci_high", "ci_width", "k",
}
BOOL_ROW_FIELDS = {
    "timed_out", "converged", "pilot_member", "subset_reused",
    "interval_covers_true",
}


def sidecar_row_matches_table(
    cached: dict[str, object], table: dict[str, object], columns: Sequence[str],
    *, primary_checkpoint: bool,
) -> list[str]:
    errors: list[str] = []
    for field in columns:
        left, right = cached.get(field), table.get(field)
        if primary_checkpoint and field == "expansion_status":
            if left != "pilot_pending":
                errors.append("primary checkpoint expansion_status is not pilot_pending")
            continue
        if field in INTEGER_ROW_FIELDS:
            if integer(left) != integer(right):
                errors.append(f"{field} differs")
        elif field in FLOAT_ROW_FIELDS:
            if not numbers_equal(left, right, atol=2e-12, rtol=2e-12):
                errors.append(f"{field} differs")
        elif field in BOOL_ROW_FIELDS:
            if bool_value(left) is not bool_value(right):
                errors.append(f"{field} differs")
        elif text_value(left) != text_value(right):
            errors.append(f"{field} differs")
    return errors


def expected_checkpoint_rows(
    scenario: pd.DataFrame, pilot: pd.DataFrame, empirical: pd.DataFrame,
    raw_dir: Path, settings: Settings,
) -> dict[Path, tuple[dict[str, object], Sequence[str], bool]]:
    expected: dict[Path, tuple[dict[str, object], Sequence[str], bool]] = {}
    for row in pilot.to_dict("records"):
        run_name = text_value(row["pilot_run"])
        run_label = "pilot_primary" if run_name == "primary" else "pilot_repeat"
        raw = raw_dir / "scenario" / run_label / (
            f"ne{integer(row['true_ne']):04d}.n{integer(row['sample_size']):02d}."
            f"m{integer(row['marker_density']):04d}.r{integer(row['replicate']):02d}.currentne2.txt"
        )
        checkpoint = (raw_dir / "checkpoints" / raw.relative_to(raw_dir)).with_suffix(".json")
        expected[checkpoint.resolve()] = (row, SCENARIO_COLUMNS, run_name == "primary")
    expanded = scenario.loc[
        pd.to_numeric(scenario["replicate"], errors="coerce") > settings.pilot_reps
    ]
    for row in expanded.to_dict("records"):
        raw = raw_dir / "scenario" / "expanded" / (
            f"ne{integer(row['true_ne']):04d}.n{integer(row['sample_size']):02d}."
            f"m{integer(row['marker_density']):04d}.r{integer(row['replicate']):02d}.currentne2.txt"
        )
        checkpoint = (raw_dir / "checkpoints" / raw.relative_to(raw_dir)).with_suffix(".json")
        expected[checkpoint.resolve()] = (row, SCENARIO_COLUMNS, False)
    for row in empirical.to_dict("records"):
        raw = raw_dir / "empirical" / (
            f"{row['population']}.n{integer(row['sample_size']):02d}."
            f"m{integer(row['marker_density']):04d}.r{integer(row['replicate']):02d}.currentne2.txt"
        )
        checkpoint = (raw_dir / "checkpoints" / raw.relative_to(raw_dir)).with_suffix(".json")
        expected[checkpoint.resolve()] = (row, EMPIRICAL_COLUMNS, False)
    return expected


def validate_inventory(
    entries: object, actual_paths: set[Path], label: str,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(entries, list):
        return [f"manifest {label} inventory is not a list"]
    mapped: dict[Path, dict[str, object]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append(f"manifest {label} inventory has non-object entry")
            continue
        path = repository_path(entry.get("path"))
        if path is None:
            errors.append(f"manifest {label} entry has blank path")
            continue
        mapped[path.resolve()] = entry
    if len(mapped) != len(entries):
        errors.append(f"manifest {label} inventory contains duplicate paths")
    if set(mapped) != actual_paths:
        errors.append(
            f"manifest {label} path set differs (manifest={len(mapped)} actual={len(actual_paths)})"
        )
    for path in sorted(set(mapped) & actual_paths, key=lambda item: item.as_posix()):
        entry = mapped[path]
        if not path.is_file():
            errors.append(f"manifest {label} file absent: {path}")
        elif entry.get("sha256") != sha256_file(path) or integer(entry.get("bytes")) != path.stat().st_size:
            errors.append(f"manifest {label} hash/size mismatch: {path}")
    return errors


def validate_cache_manifest(
    manifest_path: Path, raw_dir: Path, settings: Settings, binary: Path,
    config_path: Path, empirical_vcf: Path, popmap: Path,
    output_paths: dict[str, Path], scenario: pd.DataFrame, pilot: pd.DataFrame,
    empirical: pd.DataFrame, expansion_status: str,
    panel_cache: dict[tuple[int, int], tuple[np.ndarray, np.ndarray, np.ndarray, list[str], int, int, int, int]],
) -> list[str]:
    errors: list[str] = []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("cache_schema") != CACHE_MANIFEST_SCHEMA:
        errors.append("cache manifest schema mismatch")
    if manifest.get("analysis_schema") != SCHEMA_VERSION:
        errors.append("cache manifest analysis schema mismatch")
    if manifest.get("settings_sha256") != settings_sha256(settings):
        errors.append("cache manifest settings hash mismatch")
    if manifest.get("pedigree_golden_sha256") != PEDIGREE_GOLDEN_SHA256:
        errors.append("cache manifest pedigree golden mismatch")
    if manifest.get("binary", {}).get("sha256") != sha256_file(binary):
        errors.append("cache manifest binary hash mismatch")
    expected_input_hashes = {
        "config_sha256": sha256_file(config_path),
        "empirical_vcf_sha256": sha256_file(empirical_vcf),
        "popmap_sha256": sha256_file(popmap),
    }
    for key, expected_hash in expected_input_hashes.items():
        if manifest.get("inputs", {}).get(key) != expected_hash:
            errors.append(f"cache manifest input {key} mismatch")
    if manifest.get("expansion_status") != expansion_status or not manifest.get("written_atomically_last"):
        errors.append("cache manifest expansion/atomic-last contract mismatch")
    for label, output in output_paths.items():
        entry = manifest.get("outputs", {}).get(label, {})
        if entry.get("path") != display_path(output) or entry.get("sha256") != sha256_file(output):
            errors.append(f"cache manifest output {label} mismatch")

    expected_rows = expected_checkpoint_rows(scenario, pilot, empirical, raw_dir, settings)
    checkpoints = {path.resolve() for path in (raw_dir / "checkpoints").rglob("*.json")}
    if checkpoints != set(expected_rows):
        errors.append(
            f"checkpoint namespace differs: actual={len(checkpoints)} expected={len(expected_rows)}"
        )
    referenced_public_raw: set[Path] = set()
    referenced_public_logs: set[Path] = set()
    referenced_exact_raw: set[Path] = set()
    referenced_exact_logs: set[Path] = set()
    scenario_shares: dict[tuple[str, int, int], list[float]] = {}
    input_generation_failures = 0
    missing_raw = 0
    for checkpoint in sorted(checkpoints):
        if checkpoint not in expected_rows:
            continue
        table_row, columns, primary_checkpoint = expected_rows[checkpoint]
        try:
            payload = json.loads(checkpoint.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"checkpoint unreadable {checkpoint}: {exc}")
            continue
        if payload.get("cache_schema") != CACHE_ROW_SCHEMA:
            errors.append(f"checkpoint cache schema mismatch: {checkpoint}")
        if payload.get("analysis_schema") != SCHEMA_VERSION:
            errors.append(f"checkpoint analysis schema mismatch: {checkpoint}")
        if payload.get("settings_sha256") != settings_sha256(settings):
            errors.append(f"checkpoint settings mismatch: {checkpoint}")
        if payload.get("binary_sha256") != sha256_file(binary):
            errors.append(f"checkpoint binary mismatch: {checkpoint}")
        if payload.get("pedigree_golden_sha256") != PEDIGREE_GOLDEN_SHA256:
            errors.append(f"checkpoint golden mismatch: {checkpoint}")
        if payload.get("namespace") != checkpoint_namespace(checkpoint, raw_dir):
            errors.append(f"checkpoint namespace payload mismatch: {checkpoint}")
        cached_row = payload.get("row", {})
        if not isinstance(cached_row, dict):
            errors.append(f"checkpoint row is not an object: {checkpoint}")
            continue
        row_errors = sidecar_row_matches_table(
            cached_row, table_row, columns, primary_checkpoint=primary_checkpoint
        )
        errors.extend(f"{checkpoint.name}: {error}" for error in row_errors[:5])
        relative = checkpoint.resolve().relative_to((raw_dir / "checkpoints").resolve())
        if relative.parts[0] == "scenario":
            panel_key = (
                relative.parts[1], integer(cached_row.get("true_ne")),
                integer(cached_row.get("replicate")),
            )
            scenario_shares.setdefault(panel_key, []).append(
                numeric(cached_row.get("simulation_runtime_seconds"))
            )
        reason = text_value(cached_row.get("execution_failure_reason"))
        materialization = payload.get("public_materialization", {})
        exact = payload.get("exact_execution", {})
        if reason == "input_generation_error":
            input_generation_failures += 1
            if any(bool(materialization.get(f"{kind}_present")) for kind in ("raw", "log")):
                errors.append(f"input-generation checkpoint has public artifacts: {checkpoint}")
            if any(bool(exact.get(f"{kind}_present")) for kind in ("raw", "log")):
                errors.append(f"input-generation checkpoint has exact artifacts: {checkpoint}")
            continue
        public_raw = repository_path(cached_row.get("raw_output_path"))
        public_log = repository_path(cached_row.get("log_path"))
        if public_raw is None or public_log is None:
            errors.append(f"executed checkpoint has blank public paths: {checkpoint}")
            continue
        expected_public_command = shlex.join([
            display_path(binary), "-t", str(settings.currentne2_threads), "-s",
            str(integer(cached_row.get("marker_density"))), "-o",
            display_path(public_raw), "<ephemeral-input-vcf>",
            f"{settings.genome_size_morgans:g}",
        ])
        if text_value(cached_row.get("command")) != expected_public_command:
            errors.append(f"portable public command mismatch: {checkpoint}")
        expected_reasons: list[str] = []
        if bool_value(cached_row.get("timed_out")) is True:
            expected_reasons.append("timeout")
        if integer(cached_row.get("exit_code")) != 0:
            expected_reasons.append(f"exit_code_{integer(cached_row.get('exit_code'))}")
        if text_value(cached_row.get("parse_error")):
            expected_reasons.append("parse_error")
        if reason != ";".join(expected_reasons):
            errors.append(f"execution failure reason mismatch: {checkpoint}")
        expected_exact_raw = exact_cache_path(public_raw, raw_dir)
        expected_exact_log = expected_exact_raw.with_suffix(".log")
        exact_raw = repository_path(exact.get("raw_path"))
        exact_log = repository_path(exact.get("log_path"))
        if exact_raw is None or exact_raw.resolve() != expected_exact_raw.resolve():
            errors.append(f"exact raw namespace mismatch: {checkpoint}")
        if exact_log is None or exact_log.resolve() != expected_exact_log.resolve():
            errors.append(f"exact log namespace mismatch: {checkpoint}")
            continue
        if not bool(materialization.get("log_present")) or not bool(exact.get("log_present")):
            errors.append(f"executed checkpoint lacks log presence: {checkpoint}")
            continue
        referenced_public_logs.add(public_log.resolve())
        referenced_exact_logs.add(exact_log.resolve())
        if not public_log.is_file() or not exact_log.is_file():
            errors.append(f"checkpoint log file absent: {checkpoint}")
            continue
        if sha256_file(public_log) != text_value(cached_row.get("log_sha256")):
            errors.append(f"public log hash mismatch: {checkpoint}")
        if sha256_file(exact_log) != text_value(exact.get("log_sha256")):
            errors.append(f"exact log hash mismatch: {checkpoint}")
        if public_log.read_text(encoding="utf-8", errors="replace") != text_value(
            materialization.get("log_text")
        ):
            errors.append(f"public log rematerialization bytes mismatch: {checkpoint}")
        try:
            public_header = execution_log_header(public_log, "command")
            exact_header = execution_log_header(exact_log, "executed_command")
            if public_header["command"] != text_value(cached_row.get("command")):
                errors.append(f"public log command mismatch: {checkpoint}")
            if integer(cached_row.get("exit_code")) != public_header["exit_code"]:
                errors.append(f"public log exit mismatch: {checkpoint}")
            if bool_value(cached_row.get("timed_out")) is not public_header["timed_out"]:
                errors.append(f"public log timeout mismatch: {checkpoint}")
            for observed in (public_header["wall_seconds"], exact_header["wall_seconds"]):
                if not math.isclose(
                    numeric(cached_row.get("runtime_seconds")), float(observed),
                    rel_tol=0, abs_tol=5.1e-10,
                ):
                    errors.append(f"checkpoint/log runtime mismatch: {checkpoint}")
            if public_header["exit_code"] != exact_header["exit_code"] or (
                public_header["timed_out"] is not exact_header["timed_out"]
            ):
                errors.append(f"public/exact log telemetry differs: {checkpoint}")
            tokens = shlex.split(text_value(exact_header["command"]))
            if not (
                len(tokens) == 9 and Path(tokens[0]).resolve() == binary.resolve()
                and tokens[1:6] == [
                    "-t", str(settings.currentne2_threads), "-s",
                    str(integer(cached_row.get("marker_density"))), "-o",
                ]
                and Path(tokens[6]).resolve() == expected_exact_raw.resolve()
                and tokens[8] == f"{settings.genome_size_morgans:g}"
            ):
                errors.append(f"exact executed command mismatch: {checkpoint}")
        except Exception as exc:
            errors.append(f"execution log parse failed {checkpoint}: {exc}")
        if any(token in public_log.read_text(errors="replace") for token in privacy_tokens()):
            errors.append(f"privacy leak in public log: {checkpoint}")

        raw_present = bool(materialization.get("raw_present"))
        if raw_present != bool(exact.get("raw_present")) or raw_present != bool(
            text_value(cached_row.get("raw_output_sha256"))
        ):
            errors.append(f"raw presence contract differs: {checkpoint}")
        if raw_present:
            referenced_public_raw.add(public_raw.resolve())
            referenced_exact_raw.add(expected_exact_raw.resolve())
            if not public_raw.is_file() or not expected_exact_raw.is_file():
                errors.append(f"present raw file absent: {checkpoint}")
                continue
            if sha256_file(public_raw) != text_value(cached_row.get("raw_output_sha256")):
                errors.append(f"public raw hash mismatch: {checkpoint}")
            if sha256_file(expected_exact_raw) != text_value(exact.get("raw_sha256")):
                errors.append(f"exact raw hash mismatch: {checkpoint}")
            if public_raw.read_text(encoding="utf-8", errors="replace") != text_value(
                materialization.get("raw_text")
            ):
                errors.append(f"public raw rematerialization bytes mismatch: {checkpoint}")
            if any(token in public_raw.read_text(errors="replace") for token in privacy_tokens()):
                errors.append(f"privacy leak in public raw: {checkpoint}")
            public_parsed = independent_parse_currentne2(public_raw)
            exact_parsed = independent_parse_currentne2(expected_exact_raw)
            for field in ("ne_point", "ci_low", "ci_high", "ci_width", "k"):
                if not numbers_equal(cached_row.get(field), public_parsed[field]):
                    errors.append(f"cached/public parser mismatch {field}: {checkpoint}")
                if not numbers_equal(public_parsed[field], exact_parsed[field]):
                    errors.append(f"public/exact parser mismatch {field}: {checkpoint}")
            for field in ("n_ind", "n_snps", "ne_basis", "converged", "gbf_state"):
                observed = cached_row.get(field)
                if field == "converged":
                    cached_public_matches = bool_value(observed) is public_parsed[field]
                    public_exact_matches = public_parsed[field] is exact_parsed[field]
                elif field in {"n_ind", "n_snps"}:
                    cached_public_matches = integer(observed) == public_parsed[field]
                    public_exact_matches = public_parsed[field] == exact_parsed[field]
                else:
                    cached_public_matches = text_value(observed) == str(public_parsed[field])
                    public_exact_matches = str(public_parsed[field]) == str(exact_parsed[field])
                if not cached_public_matches:
                    errors.append(f"cached/public parser mismatch {field}: {checkpoint}")
                if not public_exact_matches:
                    errors.append(f"public/exact parser mismatch {field}: {checkpoint}")
        else:
            missing_raw += 1
            if public_raw.is_file() or expected_exact_raw.is_file() or exact.get("raw_sha256"):
                errors.append(f"absent raw unexpectedly materialized: {checkpoint}")
            for field in ("ne_point", "ci_low", "ci_high", "ci_width", "k"):
                if text_value(cached_row.get(field)):
                    errors.append(f"absent raw has estimate {field}: {checkpoint}")
            if not (
                integer(cached_row.get("n_ind")) == -1
                and integer(cached_row.get("n_snps")) == -1
                and cached_row.get("ne_basis") == "none"
                and bool_value(cached_row.get("converged")) is False
                and cached_row.get("gbf_state") == "indeterminate"
                and "parse_error" in reason
            ):
                errors.append(f"absent raw sentinel contract mismatch: {checkpoint}")

    timing_files = {
        path.resolve() for path in (raw_dir / ".timing_cache" / "panels").rglob("*.json")
    }
    expected_timing_paths: set[Path] = set()
    timing_runtimes: dict[tuple[str, int, int], float] = {}
    for panel_key, shares in scenario_shares.items():
        run_label, true_ne, replicate = panel_key
        timing_path = raw_dir / ".timing_cache" / "panels" / run_label / (
            f"ne{true_ne:04d}.r{replicate:02d}.json"
        )
        expected_timing_paths.add(timing_path.resolve())
        if not timing_path.is_file():
            errors.append(f"panel timing absent: {timing_path}")
            continue
        payload = json.loads(timing_path.read_text(encoding="utf-8"))
        replay = panel_cache[(true_ne, replicate)]
        fingerprint = panel_fingerprint(*replay[:4], *replay[4:])
        expected_binding = {
            "cache_schema": "phase5b-ne-design-panel-timing-v1",
            "analysis_schema": SCHEMA_VERSION,
            "settings_sha256": settings_sha256(settings),
            "binary_sha256": sha256_file(binary),
            "pedigree_golden_sha256": PEDIGREE_GOLDEN_SHA256,
            "run_label": run_label, "true_ne": true_ne, "replicate": replicate,
            "panel_sha256": fingerprint, "panel_error": "",
            "seed": replay[4], "simulation_attempt": replay[5],
            "candidate_loci": replay[6], "panel_seed": replay[7],
        }
        if any(payload.get(key) != value for key, value in expected_binding.items()):
            errors.append(f"panel timing scientific binding mismatch: {timing_path}")
        runtime = numeric(payload.get("simulation_runtime_seconds"))
        timing_runtimes[panel_key] = runtime
        expected_share = runtime / (len(settings.sample_sizes) * len(settings.marker_densities))
        if len(shares) != len(settings.sample_sizes) * len(settings.marker_densities):
            errors.append(f"panel timing has {len(shares)} row shares: {timing_path}")
        if not math.isfinite(runtime) or runtime < 0 or any(
            not math.isclose(share, expected_share, rel_tol=0, abs_tol=2e-12)
            for share in shares
        ):
            errors.append(f"panel timing/row shares mismatch: {timing_path}")
    if timing_files != expected_timing_paths:
        errors.append(
            f"timing namespace differs: actual={len(timing_files)} expected={len(expected_timing_paths)}"
        )

    canonical_raw = {
        path.resolve() for path in raw_dir.rglob("*.currentne2.txt")
        if not any(part.startswith(".") for part in path.relative_to(raw_dir).parts)
    }
    canonical_logs = {
        path.resolve() for path in raw_dir.rglob("*.currentne2.log")
        if not any(part.startswith(".") for part in path.relative_to(raw_dir).parts)
    }
    exact_raw = {path.resolve() for path in (raw_dir / ".exact_cache").rglob("*.currentne2.txt")}
    exact_logs = {path.resolve() for path in (raw_dir / ".exact_cache").rglob("*.currentne2.log")}
    actual_sets = {
        "checkpoints": checkpoints, "panel_timings": timing_files,
        "canonical_raw": canonical_raw, "canonical_logs": canonical_logs,
        "exact_raw": exact_raw, "exact_logs": exact_logs,
    }
    expected_sets = {
        "checkpoints": set(expected_rows), "panel_timings": expected_timing_paths,
        "canonical_raw": referenced_public_raw, "canonical_logs": referenced_public_logs,
        "exact_raw": referenced_exact_raw, "exact_logs": referenced_exact_logs,
    }
    for label, actual in actual_sets.items():
        if actual != expected_sets[label]:
            errors.append(f"cache {label} contains missing/stale extras")
        errors.extend(validate_inventory(manifest.get(label), actual, label))

    expected_counts = {
        "scenario": len(scenario), "pilot_audit": len(pilot), "empirical": len(empirical),
        "checkpoints": len(checkpoints), "panel_timings": len(timing_files),
        "expected_attempts": len(expected_rows),
        "expected_scenario_attempts": len(expected_rows) - len(empirical),
        "expected_panel_timings": len(expected_timing_paths),
        "input_generation_failures": input_generation_failures,
        "estimator_attempts": len(expected_rows) - input_generation_failures,
        "estimator_attempts_without_raw": missing_raw,
        "canonical_raw": len(canonical_raw), "canonical_logs": len(canonical_logs),
        "exact_raw": len(exact_raw), "exact_logs": len(exact_logs),
        "expected_materialized_raw": len(referenced_public_raw),
        "expected_materialized_logs": len(referenced_public_logs),
    }
    manifest_counts = manifest.get("row_counts", {})
    for key, expected in expected_counts.items():
        if integer(manifest_counts.get(key)) != expected:
            errors.append(f"cache manifest row count {key} mismatch")
    if expansion_status != "expanded" or len(expected_rows) != 1020 or input_generation_failures:
        errors.append(
            f"official cache must be expanded/1020 attempts/no input failures; "
            f"status={expansion_status} attempts={len(expected_rows)} input_failures={input_generation_failures}"
        )
    return errors


def rate_fields(name: str, count: int, total: int) -> dict[str, object]:
    low, high = local_wilson(count, total)
    return {
        f"n_{name}": count,
        f"{name}_rate": count / total if total else math.nan,
        f"{name}_ci_low": low,
        f"{name}_ci_high": high,
    }


def convergence_fields(count: int, total: int) -> dict[str, object]:
    fields = rate_fields("convergence", count, total)
    fields["n_converged"] = fields.pop("n_convergence")
    return fields


def expected_summary_rows(
    scenario: pd.DataFrame, empirical: pd.DataFrame, settings: Settings,
    expansion_status: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    scenario_groups = scenario.groupby(
        ["true_ne", "truth_class", "sample_size", "marker_density"], sort=True
    )
    for keys, group in scenario_groups:
        true_ne_text, truth, sample_text, marker_text = keys
        total = len(group)
        failures = group["outcome_class"].eq("execution_failure")
        executed = ~failures
        ci_low = pd.to_numeric(group["ci_low"], errors="coerce")
        ci_high = pd.to_numeric(group["ci_high"], errors="coerce")
        interval_mask = executed & ci_low.notna() & ci_high.notna()
        widths = pd.to_numeric(group.loc[interval_mask, "ci_width"], errors="coerce")
        finite_widths = widths[np.isfinite(widths)]
        combined_runtime = (
            pd.to_numeric(group["runtime_seconds"], errors="coerce").fillna(0)
            + pd.to_numeric(group["simulation_runtime_seconds"], errors="coerce").fillna(0)
        )
        coverage = sum(
            text_value(value).lower() == "true"
            for value in group.loc[interval_mask, "interval_covers_true"]
        )
        converged = int(group.loc[executed, "converged"].map(bool_value).eq(True).sum())  # noqa: E712
        row: dict[str, object] = {
            "analysis_type": "scenario", "population": "", "true_ne": integer(true_ne_text),
            "truth_class": truth, "sample_size": integer(sample_text),
            "marker_density": integer(marker_text),
            "reps_planned": settings.final_reps if expansion_status == "expanded" else settings.pilot_reps,
            "n_attempted": total, "n_executed": int(executed.sum()),
            **rate_fields("execution_failure", int(failures.sum()), total),
            **convergence_fields(converged, total),
            **rate_fields("correct_confident", int(group["outcome_class"].eq("correct_confident").sum()), total),
            **rate_fields("incorrect_confident", int(group["outcome_class"].eq("incorrect_confident").sum()), total),
            **rate_fields("indeterminate", int(group["outcome_class"].eq("indeterminate").sum()), total),
            **rate_fields("boundary_confident_pass", int(group["outcome_class"].eq("boundary_confident_pass").sum()), total),
            **rate_fields("boundary_confident_fail", int(group["outcome_class"].eq("boundary_confident_fail").sum()), total),
            **rate_fields("pass", int(group.loc[executed, "gbf_state"].eq("pass").sum()), total),
            **rate_fields("fail", int(group.loc[executed, "gbf_state"].eq("fail").sum()), total),
            "n_intervals": int(interval_mask.sum()), "n_interval_covers_true": coverage,
            "coverage_rate": coverage / int(interval_mask.sum()) if interval_mask.any() else math.nan,
            "coverage_ci_low": local_wilson(coverage, int(interval_mask.sum()))[0],
            "coverage_ci_high": local_wilson(coverage, int(interval_mask.sum()))[1],
            "n_unbounded_ci": int(np.isinf(widths).sum()),
            "mean_ci_width": float(finite_widths.mean()) if len(finite_widths) else math.nan,
            "median_ci_width": float(finite_widths.median()) if len(finite_widths) else math.nan,
            "median_ne_point": float(pd.to_numeric(group.loc[executed, "ne_point"], errors="coerce").median()),
            "mean_runtime_seconds": float(combined_runtime.mean()),
            "total_runtime_seconds": float(combined_runtime.sum()),
            "monte_carlo_ci_pct": 95.0, "expansion_status": expansion_status,
        }
        rows.append(row)

    empirical_groups = empirical.groupby(["population", "sample_size", "marker_density"], sort=True)
    for keys, group in empirical_groups:
        population, sample_text, marker_text = keys
        total = len(group)
        failures = group["outcome_class"].eq("execution_failure")
        executed = ~failures
        widths = pd.to_numeric(group.loc[executed, "ci_width"], errors="coerce")
        finite_widths = widths[np.isfinite(widths)]
        converged = int(group.loc[executed, "converged"].map(bool_value).eq(True).sum())  # noqa: E712
        row = {
            "analysis_type": "empirical", "population": population, "true_ne": math.nan,
            "truth_class": "not_known", "sample_size": integer(sample_text),
            "marker_density": integer(marker_text), "reps_planned": settings.empirical_reps,
            "n_attempted": total, "n_executed": int(executed.sum()),
            **rate_fields("execution_failure", int(failures.sum()), total),
            **convergence_fields(converged, total),
            **rate_fields("correct_confident", 0, total),
            **rate_fields("incorrect_confident", 0, total),
            **rate_fields("indeterminate", int(group.loc[executed, "gbf_state"].eq("indeterminate").sum()), total),
            **rate_fields("boundary_confident_pass", 0, total),
            **rate_fields("boundary_confident_fail", 0, total),
            **rate_fields("pass", int(group.loc[executed, "gbf_state"].eq("pass").sum()), total),
            **rate_fields("fail", int(group.loc[executed, "gbf_state"].eq("fail").sum()), total),
            "n_intervals": 0, "n_interval_covers_true": 0,
            "coverage_rate": math.nan, "coverage_ci_low": math.nan, "coverage_ci_high": math.nan,
            "n_unbounded_ci": int(np.isinf(widths).sum()),
            "mean_ci_width": float(finite_widths.mean()) if len(finite_widths) else math.nan,
            "median_ci_width": float(finite_widths.median()) if len(finite_widths) else math.nan,
            "median_ne_point": float(pd.to_numeric(group.loc[executed, "ne_point"], errors="coerce").median()),
            "mean_runtime_seconds": float(pd.to_numeric(group["runtime_seconds"], errors="coerce").mean()),
            "total_runtime_seconds": float(pd.to_numeric(group["runtime_seconds"], errors="coerce").sum()),
            "monte_carlo_ci_pct": 95.0, "expansion_status": expansion_status,
        }
        rows.append(row)
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def compare_frames(
    actual: pd.DataFrame, expected: pd.DataFrame, keys: Sequence[str],
    numeric_columns: Iterable[str],
) -> list[str]:
    errors: list[str] = []
    numeric_set = set(numeric_columns)

    def normalized_key(row: dict[str, object]) -> tuple[str, ...]:
        values: list[str] = []
        for key in keys:
            if key in numeric_set:
                number = numeric(row[key])
                values.append("" if math.isnan(number) else format(number, ".15g"))
            else:
                values.append(text_value(row[key]))
        return tuple(values)

    actual_map = {normalized_key(row): row for row in actual.to_dict("records")}
    expected_map = {normalized_key(row): row for row in expected.to_dict("records")}
    if len(actual_map) != len(actual):
        errors.append("actual bridge contains duplicate keys")
    if set(actual_map) != set(expected_map):
        missing = sorted(set(expected_map) - set(actual_map))[:3]
        extra = sorted(set(actual_map) - set(expected_map))[:3]
        errors.append(f"key mismatch missing={missing} extra={extra}")
    for key in sorted(set(actual_map) & set(expected_map)):
        left, right = actual_map[key], expected_map[key]
        for column in actual.columns:
            if column in keys:
                continue
            if column in numeric_set:
                if not numbers_equal(left[column], right[column]):
                    errors.append(f"{key}: {column} mismatch {left[column]} != {right[column]}")
            elif text_value(left[column]) != text_value(right[column]):
                errors.append(f"{key}: {column} mismatch {left[column]} != {right[column]}")
    return errors


def expected_figure_rows(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for record in summary.loc[summary["analysis_type"].eq("scenario")].to_dict("records"):
        if record["truth_class"] == "boundary":
            metric, target = "indeterminate_rate", "boundary_indeterminate"
        else:
            metric, target = "correct_confident_rate", "correct_confident"
        stem = metric.removesuffix("_rate")
        rows.append({
            "panel": "scenario_design_target", "analysis_type": "scenario", "population": "",
            "true_ne": record["true_ne"], "truth_class": record["truth_class"],
            "sample_size": record["sample_size"], "marker_density": record["marker_density"],
            "metric": metric, "value": record[metric], "ci_low": record[f"{stem}_ci_low"],
            "ci_high": record[f"{stem}_ci_high"], "n_attempted": record["n_attempted"],
            "target_outcome": target,
        })
        audit_metrics = (
            ("boundary_confident_pass_rate", "boundary_confident_fail_rate", "execution_failure_rate")
            if record["truth_class"] == "boundary" else
            ("incorrect_confident_rate", "indeterminate_rate", "execution_failure_rate")
        )
        for extra in audit_metrics:
            stem = extra.removesuffix("_rate")
            rows.append({
                "panel": "scenario_outcome_audit", "analysis_type": "scenario", "population": "",
                "true_ne": record["true_ne"], "truth_class": record["truth_class"],
                "sample_size": record["sample_size"], "marker_density": record["marker_density"],
                "metric": extra, "value": record[extra], "ci_low": record[f"{stem}_ci_low"],
                "ci_high": record[f"{stem}_ci_high"], "n_attempted": record["n_attempted"],
                "target_outcome": "audit_only",
            })
    for record in summary.loc[summary["analysis_type"].eq("empirical")].to_dict("records"):
        for metric in ("convergence_rate", "pass_rate", "fail_rate", "indeterminate_rate", "execution_failure_rate"):
            stem = metric.removesuffix("_rate")
            rows.append({
                "panel": "empirical_sensitivity", "analysis_type": "empirical",
                "population": record["population"], "true_ne": "", "truth_class": "not_known",
                "sample_size": record["sample_size"], "marker_density": record["marker_density"],
                "metric": metric, "value": record[metric], "ci_low": record[f"{stem}_ci_low"],
                "ci_high": record[f"{stem}_ci_high"], "n_attempted": record["n_attempted"],
                "target_outcome": "empirical_no_known_truth",
            })
    return pd.DataFrame(rows, columns=FIGURE_VALUE_COLUMNS)


def validate_png(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "PNG absent"
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return False, "invalid PNG signature/IHDR"
    width, height = struct.unpack(">II", data[16:24])
    return width >= 1000 and height >= 600, f"bytes={len(data)} dimensions={width}x{height}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--popmap", default="config/peafowl_popmap.tsv")
    parser.add_argument("--empirical-vcf", default="results/qc/setA.standard.vcf.gz")
    parser.add_argument("--currentne2", default="tools/currentNe2/currentne2")
    parser.add_argument("--bcftools", default=None)
    parser.add_argument("--replicates", default="results/tables/peafowl_ne_design_replicates.tsv")
    parser.add_argument("--pilot", default="results/tables/peafowl_ne_design_pilot.tsv")
    parser.add_argument("--summary", default="results/tables/peafowl_ne_design_summary.tsv")
    parser.add_argument("--empirical", default="results/tables/peafowl_ne_design_empirical.tsv")
    parser.add_argument("--figure-values", default="results/tables/peafowl_ne_design_figure_values.tsv")
    parser.add_argument("--figure", default="results/figures/peafowl_ne_design.png")
    parser.add_argument("--provenance", default="results/provenance/peafowl_ne_design.json")
    parser.add_argument("--raw-dir", default="results/ne/design")
    parser.add_argument("--cache-manifest", default="results/ne/design/CACHE_MANIFEST.json")
    parser.add_argument("--out-tsv", default="results/tables/validation_peafowl_ne_design.tsv")
    parser.add_argument("--out-md", default="results/PEAFOWL_NE_DESIGN_VALIDATION.md")
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def local_golden_fingerprint() -> str:
    golden_settings = Settings(
        seed=1302, true_ne=(20,), sample_sizes=(5, 10), marker_densities=(64,),
        pilot_reps=1, final_reps=2, empirical_reps=1, simulation_generations=4,
        initial_maf_low=0.1, initial_maf_high=0.5, currentne2_threads=1,
        run_timeout_seconds=30, pilot_expansion_max_seconds=300,
        genome_size_morgans=32, ci_pct=90, resolution_truths=(250, 1000),
        resolution_min_correct_confident_ci_low=0.7,
        resolution_max_incorrect_confident_ci_high=0.25,
    )
    panel = local_simulate_panel(golden_settings, 20, 3)
    return panel_fingerprint(*panel[:4], *panel[4:])


def self_check() -> None:
    assert local_truth_class(500) == "boundary"
    assert local_outcome("boundary", "pass", False) == "boundary_confident_pass"
    assert local_outcome("below", "pass", False) == "incorrect_confident"
    low, high = local_wilson(0, 12)
    assert 0 <= low <= high <= 1
    convergence = convergence_fields(3, 12)
    assert convergence["n_converged"] == 3
    assert "n_convergence" not in convergence
    assert local_stable_seed(1302, "scenario", 100, 1) == 5555898811081412103
    assert local_stable_seed(1302, "scenario", 100, 1) + 1 != 5555898811081412103
    assert local_golden_fingerprint() == PEDIGREE_GOLDEN_SHA256
    golden_settings = Settings(
        seed=1302, true_ne=(20,), sample_sizes=(5, 10), marker_densities=(64,),
        pilot_reps=1, final_reps=2, empirical_reps=1, simulation_generations=4,
        initial_maf_low=0.1, initial_maf_high=0.5, currentne2_threads=1,
        run_timeout_seconds=30, pilot_expansion_max_seconds=300,
        genome_size_morgans=32, ci_pct=90, resolution_truths=(250, 1000),
        resolution_min_correct_confident_ci_low=0.7,
        resolution_max_incorrect_confident_ci_high=0.25,
    )
    panel = local_simulate_panel(golden_settings, 20, 3)
    assert panel[0].dtype == np.uint8 and len(set(panel[1].tolist())) == 32
    boundary = EmpiricalVariant(
        "1", 1, "A", "G", ("0/0", "0/1", "1/1", "0/0", "./.")
    )
    assert not strict_empirical_eligible(boundary, range(5))
    above_boundary = EmpiricalVariant(
        "1", 2, "A", "G", ("0/0", "0/1", "1/1", "0/0", "0/1", "./.")
    )
    assert strict_empirical_eligible(above_boundary, range(6))
    assert math.isclose((1 - math.exp(-2 * 0.1)) / 2, 0.09063462346100909)
    with tempfile.TemporaryDirectory(prefix="ne-validator-parser-") as temporary:
        raw = Path(temporary) / "currentne.txt"
        common = (
            "# Total number of individuals in the input file:\n10\n"
            "# Number of SNPs included in the analysis (only polymorphic and with less than 20% missing data):\n"
            "1000\n"
        )
        raw.write_text(
            common
            + "# Ne estimation based only on LD between chromosomes\n"
            + K_PREFIX + " (c=0.5):\n2\n"
            + "# Ne point estimate:\n800\n# Lower limit of 90% CI:\n600\n"
            + "# Upper limit of 90% CI:\n1200\n(end of output)\n",
            encoding="utf-8",
        )
        parsed = independent_parse_currentne2(raw)
        assert parsed["ne_basis"] == "cross_chromosome"
        assert parsed["ne_point"] == 800 and parsed["gbf_state"] == "pass"
        raw.write_text(
            common
            + "# Ne estimation based only on LD between chromosomes\n"
            + "# Ne point estimate:\nnot_available\n# Lower limit of 90% CI:\nnot_available\n"
            + "# Upper limit of 90% CI:\nnot_available\n"
            + "# Ne estimation by integration over the whole genome\n"
            + K_PREFIX + ":\n1\n"
            + "# Ne point estimate:\n300\n# Lower limit of 90% CI:\n200\n"
            + "# Upper limit of 90% CI:\n400\n(end of output)\n",
            encoding="utf-8",
        )
        fallback = independent_parse_currentne2(raw)
        assert fallback["ne_basis"] == "whole_genome"
        assert fallback["ne_point"] == 300 and fallback["gbf_state"] == "fail"
        assert local_gbf_state(500, 400, 600) == "indeterminate"
        raw.write_text(
            common
            + "The solution based on LD between all loci pairs does not converge.\n"
            + "The solution based on LD between SNPs on different chromosomes does not converge.\n",
            encoding="utf-8",
        )
        nonconverged = independent_parse_currentne2(raw)
        assert math.isnan(nonconverged["ne_point"])
        assert math.isnan(nonconverged["ci_low"])
        assert math.isnan(nonconverged["ci_high"])
        assert nonconverged["ne_basis"] == "none"
        assert nonconverged["converged"] is False
        assert nonconverged["gbf_state"] == "indeterminate"

        hash_rows = []
        for replicate, seed, point, low, high, k_value, covered in (
            (2, 8_500_000_000_000_001, 60.0, 20.5, 119.0, 0.0, True),
            (10, 8_500_000_000_000_009, math.inf, math.nan, math.inf, math.nan, ""),
        ):
            row = {column: "" for column in PILOT_HASH_COLUMNS}
            row.update({
                "scenario_id": "ne0250_n05_m0250",
                "replicate": replicate,
                "true_ne": 250,
                "truth_class": "below",
                "sample_size": 5,
                "marker_density": 250,
                "seed": seed,
                "simulation_attempt": 1,
                "candidate_loci": 4000,
                "panel_seed": seed - 10,
                "simulation_generations": 15,
                "initial_maf_low": 0.1,
                "initial_maf_high": 0.5,
                "input_vcf_sha256": "a" * 64,
                "marker_ids_sha256": "b" * 64,
                "sample_ids_sha256": "c" * 64,
                "exit_code": 0,
                "timed_out": False,
                "ne_point": point,
                "ci_low": low,
                "ci_high": high,
                "ci_width": high - low,
                "interval_covers_true": covered,
                "n_ind": 5,
                "n_snps": 250,
                "k": k_value,
                "ne_basis": "cross_chromosome",
                "converged": True,
                "gbf_state": "fail",
                "outcome_class": "correct_confident",
            })
            hash_rows.append(row)
        typed_hash_frame = pd.DataFrame(hash_rows, columns=PILOT_HASH_COLUMNS)
        hash_tsv = Path(temporary) / "hash-roundtrip.tsv"
        typed_hash_frame.to_csv(
            hash_tsv, sep="\t", index=False, na_rep="", float_format="%.15g",
            lineterminator="\n",
        )
        roundtripped_hash_frame = read_tsv(hash_tsv)
        assert independent_scientific_hash(
            typed_hash_frame, PILOT_HASH_COLUMNS
        ) == independent_scientific_hash(roundtripped_hash_frame, PILOT_HASH_COLUMNS)

        mismatch_expected = pd.DataFrame({
            "id": [f"key-{index:02d}" for index in range(8)],
            "value": [0.0] * 8,
        })
        mismatch_actual = pd.DataFrame({
            "id": list(reversed(mismatch_expected["id"].tolist())),
            "value": [1.0] * 8,
        })
        mismatch_errors = compare_frames(
            mismatch_actual, mismatch_expected, ("id",), ("value",)
        )
        expected_mismatch_errors = [
            f"('key-{index:02d}',): value mismatch 1.0 != 0.0"
            for index in range(8)
        ]
        assert mismatch_errors == expected_mismatch_errors
        assert mismatch_detail(mismatch_errors) == (
            "; ".join(expected_mismatch_errors[:5]) + " (+3 more)"
        )

        inventory_paths = []
        for index in range(8):
            path = Path(temporary) / f"inventory-{index:02d}.dat"
            path.write_text(f"fixture-{index}\n", encoding="utf-8")
            inventory_paths.append(path.resolve())
        inventory_entries = [
            {
                "path": str(path),
                "sha256": "0" * 64,
                "bytes": path.stat().st_size,
            }
            for path in reversed(inventory_paths)
        ]
        inventory_errors = validate_inventory(
            inventory_entries, set(reversed(inventory_paths)), "fixture"
        )
        assert inventory_errors == [
            f"manifest fixture hash/size mismatch: {path}"
            for path in sorted(inventory_paths, key=lambda item: item.as_posix())
        ]
    print("validate_peafowl_ne_design self-check: OK")


def main() -> None:
    args = parse_args()
    if args.self_check:
        self_check()
        return

    paths = {
        "config": resolve(args.config), "popmap": resolve(args.popmap),
        "empirical_vcf": resolve(args.empirical_vcf), "currentne2": resolve(args.currentne2),
        "replicates": resolve(args.replicates), "pilot": resolve(args.pilot),
        "summary": resolve(args.summary), "empirical": resolve(args.empirical),
        "figure_values": resolve(args.figure_values), "figure": resolve(args.figure),
        "provenance": resolve(args.provenance), "raw_dir": resolve(args.raw_dir),
        "cache_manifest": resolve(args.cache_manifest),
        "out_tsv": resolve(args.out_tsv), "out_md": resolve(args.out_md),
    }
    audit = Audit()
    required = [
        "config", "popmap", "empirical_vcf", "currentne2", "replicates", "pilot",
        "summary", "empirical", "figure_values", "figure", "provenance",
        "cache_manifest",
    ]
    missing = [name for name in required if not paths[name].is_file()]
    audit.add("required_artifacts", not missing, f"missing={missing or 'none'}")
    if missing:
        write_validation(audit, paths["out_tsv"], paths["out_md"])
        raise SystemExit(1)

    settings = load_settings(paths["config"])
    bcftools = locate_executable(args.bcftools, "bcftools")
    raw_config = yaml.safe_load(paths["config"].read_text(encoding="utf-8"))["phase5b"]["ne_design"]
    synthesis_errors: list[str] = []
    resolution_truths = raw_config.get("resolution_truths")
    if not isinstance(resolution_truths, list) or not resolution_truths:
        synthesis_errors.append("resolution_truths absent/empty")
    elif any(int(value) not in settings.true_ne or int(value) == 500 for value in resolution_truths):
        synthesis_errors.append(
            "resolution_truths must be configured true_ne values and must exclude boundary value 500"
        )
    for key in (
        "resolution_min_correct_confident_ci_low",
        "resolution_max_incorrect_confident_ci_high",
    ):
        if key not in raw_config or not finite_probability(raw_config.get(key)):
            synthesis_errors.append(f"{key} absent/outside [0,1]")
    audit.add("predeclared_synthesis_thresholds", not synthesis_errors, mismatch_detail(synthesis_errors))
    audit.add(
        "currentne2_ci_configuration",
        settings.ci_pct == 90 and settings.genome_size_morgans == 32,
        f"ci_pct={settings.ci_pct}; genome_size_morgans={settings.genome_size_morgans}",
    )
    independent_golden = local_golden_fingerprint()
    audit.add(
        "independent_pedigree_haldane_golden",
        independent_golden == PEDIGREE_GOLDEN_SHA256,
        f"observed={independent_golden}; expected={PEDIGREE_GOLDEN_SHA256}",
    )

    scenario = read_tsv(paths["replicates"])
    pilot = read_tsv(paths["pilot"])
    empirical = read_tsv(paths["empirical"])
    summary = read_tsv(paths["summary"])
    figure_values = read_tsv(paths["figure_values"])
    provenance = json.loads(paths["provenance"].read_text(encoding="utf-8"))

    schema_check(audit, "scenario", scenario, SCENARIO_COLUMNS)
    schema_check(
        audit, "pilot", pilot,
        SCENARIO_COLUMNS + ["pilot_run", "pilot_batch_hash", "repeatability_match"],
    )
    schema_check(audit, "empirical", empirical, EMPIRICAL_COLUMNS)
    schema_check(audit, "summary", summary, SUMMARY_COLUMNS)
    schema_check(audit, "figure_values", figure_values, FIGURE_VALUE_COLUMNS)

    expansion_status = text_value(provenance.get("pilot", {}).get("expansion_status"))
    reps_expected = settings.final_reps
    expected_grid = expected_scenario_keys(settings, reps_expected)
    observed_grid = actual_scenario_keys(scenario)
    duplicates = [key for key, count in Counter(observed_grid).items() if count != 1]
    missing_grid = expected_grid - set(observed_grid)
    extra_grid = set(observed_grid) - expected_grid
    audit.add(
        "scenario_grid_60_cells_by_replicates",
        expansion_status == "expanded" and len(expected_grid) == 60 * reps_expected
        and not duplicates and not missing_grid and not extra_grid,
        f"rows={len(scenario)} expected={60 * reps_expected}; duplicate={len(duplicates)}; "
        f"missing={len(missing_grid)}; extra={len(extra_grid)}",
    )
    scenario_errors = validate_scenario_rows(scenario, settings)
    audit.add(
        "scenario_truth_seed_outcome_traceability", not scenario_errors,
        f"checked={len(scenario)}; errors={mismatch_detail(scenario_errors)}",
    )
    panel_cache: dict[
        tuple[int, int],
        tuple[np.ndarray, np.ndarray, np.ndarray, list[str], int, int, int, int],
    ] = {}
    scenario_replay_errors = replay_scenario_inputs(scenario, settings, panel_cache)
    audit.add(
        "scenario_independent_pedigree_haldane_vcf_replay",
        not scenario_replay_errors,
        f"unique_panels={len(panel_cache)}; errors={mismatch_detail(scenario_replay_errors)}",
    )
    boundary = scenario.loc[pd.to_numeric(scenario["true_ne"], errors="coerce").eq(500)]
    boundary_bad = boundary["outcome_class"].isin(["correct_confident", "incorrect_confident"]).sum()
    audit.add(
        "boundary_ne500_never_correct_or_incorrect", boundary_bad == 0 and len(boundary) == 15 * reps_expected,
        f"boundary_rows={len(boundary)} expected={15 * reps_expected}; bad={boundary_bad}",
    )

    raw_scenario_errors, parsed_scenario, successful_scenario = validate_artifact_paths(
        scenario, "scenario", paths["raw_dir"]
    )
    audit.add(
        "scenario_raw_hash_parser_and_analyzed_dimensions", not raw_scenario_errors,
        f"rows={len(scenario)} parsed_raw={parsed_scenario} successful={successful_scenario}; "
        f"errors={mismatch_detail(raw_scenario_errors)}",
    )

    pilot_expected_per_run = expected_scenario_keys(settings, settings.pilot_reps)
    pilot_grid_errors: list[str] = []
    for run_name in ("primary", "repeat"):
        run = pilot.loc[pilot["pilot_run"].eq(run_name)]
        keys = actual_scenario_keys(run)
        if len(keys) != len(pilot_expected_per_run) or set(keys) != pilot_expected_per_run or len(keys) != len(set(keys)):
            pilot_grid_errors.append(f"{run_name} pilot grid mismatch ({len(keys)} rows)")
    audit.add("pilot_two_complete_seeded_runs", not pilot_grid_errors, mismatch_detail(pilot_grid_errors))
    primary = pilot.loc[pilot["pilot_run"].eq("primary")]
    repeated = pilot.loc[pilot["pilot_run"].eq("repeat")]
    primary_hash = independent_scientific_hash(primary, PILOT_HASH_COLUMNS)
    repeat_hash = independent_scientific_hash(repeated, PILOT_HASH_COLUMNS)
    stored_primary = text_value(provenance.get("pilot", {}).get("primary_scientific_sha256"))
    stored_repeat = text_value(provenance.get("pilot", {}).get("repeat_scientific_sha256"))
    audit.add(
        "pilot_scientific_hash_repeatability",
        primary_hash == repeat_hash == stored_primary == stored_repeat
        and set(primary["pilot_batch_hash"]) == {primary_hash}
        and set(repeated["pilot_batch_hash"]) == {repeat_hash}
        and set(pilot["repeatability_match"].str.lower()) == {"true"},
        f"independent_primary={primary_hash}; independent_repeat={repeat_hash}; "
        f"stored_match={stored_primary == stored_repeat}",
    )
    repeatability = primary_hash == repeat_hash
    integrity_gate = all(
        bool(
            frame["execution_failure_reason"].eq("").all()
            and pd.to_numeric(frame["n_ind"], errors="coerce").eq(
                pd.to_numeric(frame["sample_size"], errors="coerce")
            ).all()
            and pd.to_numeric(frame["n_snps"], errors="coerce").eq(
                pd.to_numeric(frame["marker_density"], errors="coerce")
            ).all()
        )
        for frame in (primary, repeated)
    )
    primary_currentne2_seconds = float(
        pd.to_numeric(primary["runtime_seconds"], errors="coerce").fillna(0).sum()
    )
    primary_simulation_seconds = float(
        pd.to_numeric(primary["simulation_runtime_seconds"], errors="coerce").fillna(0).sum()
    )
    primary_projectable_seconds = primary_currentne2_seconds + primary_simulation_seconds
    projected_full_seconds = (
        primary_projectable_seconds * settings.final_reps / settings.pilot_reps
    )
    runtime_gate = projected_full_seconds <= settings.pilot_expansion_max_seconds
    attainable_correct_low = local_wilson(settings.final_reps, settings.final_reps)[0]
    attainable_incorrect_high = local_wilson(0, settings.final_reps)[1]
    uncertainty_gate = bool(
        attainable_correct_low >= settings.resolution_min_correct_confident_ci_low
        and attainable_incorrect_high <= settings.resolution_max_incorrect_confident_ci_high
    )
    all_gates = repeatability and integrity_gate and runtime_gate and uncertainty_gate
    pilot_provenance = provenance.get("pilot", {})
    stored_gate_values = {
        "repeatability_match": repeatability,
        "integrity_gate_pass": integrity_gate,
        "runtime_gate_pass": runtime_gate,
        "wilson_attainability_gate_pass": uncertainty_gate,
    }
    gate_mismatches = [
        key for key, expected in stored_gate_values.items()
        if bool(pilot_provenance.get(key)) is not expected
    ]
    expansion_expected = "expanded" if all_gates else "pilot_only"
    audit.add(
        "pilot_four_outcome_blind_expansion_gates",
        not gate_mismatches and all_gates and expansion_status == expansion_expected == "expanded",
        f"repeat={repeatability}; integrity={integrity_gate}; runtime={runtime_gate}; "
        f"wilson={uncertainty_gate}; status={expansion_status}; mismatches={gate_mismatches}",
    )
    runtime_reconciliation = all(
        numbers_equal(observed, expected, atol=2e-8, rtol=2e-8)
        for observed, expected in (
            (pilot_provenance.get("primary_currentne2_seconds"), primary_currentne2_seconds),
            (pilot_provenance.get("primary_simulation_seconds"), primary_simulation_seconds),
            (pilot_provenance.get("primary_projectable_seconds"), primary_projectable_seconds),
            (pilot_provenance.get("projected_full_seconds"), projected_full_seconds),
            (pilot_provenance.get("attainable_correct_confident_ci_low"), attainable_correct_low),
            (pilot_provenance.get("attainable_incorrect_confident_ci_high"), attainable_incorrect_high),
        )
    )
    audit.add(
        "pilot_cache_invariant_runtime_and_wilson_reconciliation",
        runtime_reconciliation,
        f"currentNe2={primary_currentne2_seconds:.6f}; simulation={primary_simulation_seconds:.6f}; "
        f"projected={projected_full_seconds:.6f}",
    )
    scenario_pilot = scenario.loc[pd.to_numeric(scenario["replicate"], errors="coerce") <= settings.pilot_reps]
    scenario_pilot_hash = independent_scientific_hash(scenario_pilot, PILOT_HASH_COLUMNS)
    audit.add(
        "pilot_primary_retained_in_scenario_table", scenario_pilot_hash == primary_hash,
        f"scenario_pilot={scenario_pilot_hash}; primary={primary_hash}",
    )
    pilot_replay_errors = replay_scenario_inputs(pilot, settings, panel_cache)
    audit.add(
        "pilot_independent_input_replay", not pilot_replay_errors,
        f"rows={len(pilot)}; errors={mismatch_detail(pilot_replay_errors)}",
    )
    raw_pilot_errors, parsed_pilot, _ = validate_artifact_paths(pilot, "pilot", paths["raw_dir"])
    audit.add(
        "pilot_raw_hash_parser_traceability", not raw_pilot_errors,
        f"pilot_rows={len(pilot)} parsed_raw={parsed_pilot}; errors={mismatch_detail(raw_pilot_errors)}",
    )

    populations = read_populations(paths["popmap"])
    expected_empirical = expected_empirical_keys(settings, populations)
    actual_empirical = [
        (row.population, integer(row.sample_size), integer(row.marker_density), integer(row.replicate))
        for row in empirical.itertuples(index=False)
    ]
    empirical_duplicates = len(actual_empirical) != len(set(actual_empirical))
    audit.add(
        "empirical_grid_n5_through_observed",
        not empirical_duplicates and set(actual_empirical) == expected_empirical,
        f"rows={len(empirical)} expected={len(expected_empirical)}; duplicate={empirical_duplicates}; "
        f"missing={len(expected_empirical - set(actual_empirical))}; "
        f"extra={len(set(actual_empirical) - expected_empirical)}",
    )
    empirical_errors = validate_empirical_rows(empirical, settings, populations)
    audit.add(
        "empirical_bounds_subsets_seeds_unknown_truth", not empirical_errors,
        f"populations={{{', '.join(f'{key}:{len(value)}' for key, value in populations.items())}}}; "
        f"errors={mismatch_detail(empirical_errors)}",
    )
    empirical_replay_errors = replay_empirical_inputs(
        empirical, settings, bcftools, paths["empirical_vcf"], provenance
    )
    audit.add(
        "empirical_independent_reservoir_strict80_vcf_replay",
        not empirical_replay_errors,
        f"rows={len(empirical)}; strict_rule=called*5>samples*4; "
        f"errors={mismatch_detail(empirical_replay_errors)}",
    )
    raw_empirical_errors, parsed_empirical, successful_empirical = validate_artifact_paths(
        empirical, "empirical", paths["raw_dir"]
    )
    audit.add(
        "empirical_raw_hash_parser_and_analyzed_dimensions", not raw_empirical_errors,
        f"rows={len(empirical)} parsed_raw={parsed_empirical} successful={successful_empirical}; "
        f"errors={mismatch_detail(raw_empirical_errors)}",
    )
    failures_retained = int(scenario["outcome_class"].eq("execution_failure").sum()) + int(
        empirical["outcome_class"].eq("execution_failure").sum()
    )
    nonconverged_retained = int(
        ((scenario["converged"].str.lower() == "false") &
         (scenario["execution_failure_reason"] == "")).sum()
    ) + int(
        ((empirical["converged"].str.lower() == "false") &
         (empirical["execution_failure_reason"] == "")).sum()
    )
    audit.add(
        "failures_and_nonconvergence_are_explicit_rows", True,
        f"execution_failures={failures_retained}; successful_nonconverged={nonconverged_retained}; "
        "both categories retained in denominators",
    )

    expected_summary = expected_summary_rows(scenario, empirical, settings, expansion_status)
    summary_numeric = set(SUMMARY_COLUMNS) - {
        "analysis_type", "population", "truth_class", "expansion_status",
    }
    summary_errors = compare_frames(
        summary, expected_summary,
        ["analysis_type", "population", "true_ne", "truth_class", "sample_size", "marker_density"],
        summary_numeric,
    )
    audit.add(
        "summary_exact_reconciliation", not summary_errors,
        f"rows={len(summary)} expected={len(expected_summary)}; errors={mismatch_detail(summary_errors)}",
    )
    partition_errors: list[str] = []
    for row in summary.to_dict("records"):
        total = integer(row["n_attempted"])
        failures = integer(row["n_execution_failure"])
        if row["analysis_type"] == "scenario" and row["truth_class"] == "boundary":
            accounted = failures + integer(row["n_boundary_confident_pass"]) + integer(
                row["n_boundary_confident_fail"]
            ) + integer(row["n_indeterminate"])
        elif row["analysis_type"] == "scenario":
            accounted = failures + integer(row["n_correct_confident"]) + integer(
                row["n_incorrect_confident"]
            ) + integer(row["n_indeterminate"])
        else:
            accounted = failures + integer(row["n_pass"]) + integer(row["n_fail"]) + integer(
                row["n_indeterminate"]
            )
            if row["truth_class"] != "not_known" or text_value(row["true_ne"]):
                partition_errors.append(f"empirical {row['population']}: truth fields not unknown")
        if accounted != total:
            partition_errors.append(
                f"{row['analysis_type']}/{row['population']}/{row['true_ne']}/n{row['sample_size']}/"
                f"m{row['marker_density']}: accounted={accounted} total={total}"
            )
    audit.add("summary_outcome_denominators_partition", not partition_errors, mismatch_detail(partition_errors))

    expected_figure = expected_figure_rows(summary)
    figure_numeric = {"true_ne", "sample_size", "marker_density", "value", "ci_low", "ci_high", "n_attempted"}
    figure_errors = compare_frames(
        figure_values, expected_figure,
        ["panel", "analysis_type", "population", "true_ne", "truth_class", "sample_size",
         "marker_density", "metric", "target_outcome"],
        figure_numeric,
    )
    audit.add(
        "figure_values_exact_summary_bridge", not figure_errors,
        f"rows={len(figure_values)} expected={len(expected_figure)}; errors={mismatch_detail(figure_errors)}",
    )
    observed_axis_pairs = {
        (row.population, integer(row.sample_size))
        for row in figure_values.loc[
            figure_values["panel"].eq("empirical_sensitivity")
        ].itertuples(index=False)
    }
    expected_axis_pairs = {
        (population, n)
        for population, samples in populations.items()
        for n in range(min(settings.sample_sizes), len(samples) + 1)
    }
    audit.add(
        "empirical_figure_axis_n5_through_each_observed_n",
        observed_axis_pairs == expected_axis_pairs,
        f"observed={sorted(observed_axis_pairs)}; expected={sorted(expected_axis_pairs)}",
    )
    panel_types = {
        panel: set(group["analysis_type"])
        for panel, group in figure_values.groupby("panel")
    }
    separated = (
        panel_types.get("scenario_design_target") == {"scenario"}
        and panel_types.get("scenario_outcome_audit") == {"scenario"}
        and panel_types.get("empirical_sensitivity") == {"empirical"}
    )
    audit.add("scenario_empirical_visual_separation", separated, f"panel_types={panel_types}")
    png_ok, png_detail = validate_png(paths["figure"])
    audit.add("figure_png_rendered", png_ok, png_detail)

    provenance_errors: list[str] = []
    if provenance.get("schema_version") != SCHEMA_VERSION:
        provenance_errors.append("schema_version mismatch")
    interpretation = text_value(provenance.get("interpretation")).lower()
    if "not a guarantee" not in interpretation or "scenario" not in interpretation:
        provenance_errors.append("interpretation lacks scenario/not-a-guarantee wording")
    currentne = provenance.get("currentne2", {})
    if numeric(currentne.get("threads")) != settings.currentne2_threads:
        provenance_errors.append("currentNe2 thread setting mismatch")
    if numeric(currentne.get("timeout_seconds")) != settings.run_timeout_seconds:
        provenance_errors.append("currentNe2 timeout setting mismatch")
    if numeric(currentne.get("genome_size_morgans")) != settings.genome_size_morgans:
        provenance_errors.append("currentNe2 genome size mismatch")
    if "90%" not in text_value(currentne.get("decision_function")):
        provenance_errors.append("90% CI decision provenance absent")
    if currentne.get("sha256") != sha256_file(paths["currentne2"]):
        provenance_errors.append("currentNe2 binary hash mismatch")
    inputs = provenance.get("inputs", {})
    for label, file_key in (("config", "config"), ("empirical_vcf", "empirical_vcf"), ("popmap", "popmap")):
        if inputs.get(f"{label}_sha256") != sha256_file(paths[file_key]):
            provenance_errors.append(f"{label} input hash mismatch")
    output_map = {
        "replicates": "replicates", "pilot": "pilot", "summary": "summary",
        "empirical": "empirical", "figure_values": "figure_values", "figure": "figure",
    }
    for label, file_key in output_map.items():
        entry = provenance.get("outputs", {}).get(label, {})
        if entry.get("sha256") != sha256_file(paths[file_key]):
            provenance_errors.append(f"{label} output hash mismatch")
    if provenance.get("threshold", {}).get("boundary_handling", "").find("never scored correct/incorrect") < 0:
        provenance_errors.append("boundary handling provenance absent")
    simulation_text = json.dumps(provenance.get("simulation", {})).lower()
    required_simulation_terms = (
        "wright-fisher", "one parental individual genome-wide", "haldane",
        "32 one-morgan chromosomes", "independent chromosome assortment",
    )
    if any(term not in simulation_text for term in required_simulation_terms):
        provenance_errors.append("simulation model provenance absent")
    if provenance.get("empirical", {}).get("truth") != (
        "unknown; empirical rows are never scored correct/incorrect"
    ):
        provenance_errors.append("empirical unknown-truth provenance mismatch")
    caveat = text_value(provenance.get("empirical", {}).get("uncertainty_caveat")).lower()
    for term in (
        "only individual subset repeats across six marker panels", "subsets overlap",
        "seeded subset/marker-panel sensitivity", "not independent biological-sampling uncertainty",
    ):
        if term not in caveat:
            provenance_errors.append(f"empirical Wilson caveat lacks: {term}")
    projection_metric = text_value(
        provenance.get("pilot", {}).get("runtime_projection_metric")
    ).lower()
    if "simulation" not in projection_metric or "cache-invariant" not in projection_metric:
        provenance_errors.append("runtime projection provenance omits simulation/cache invariance")
    scenario_scientific = independent_scientific_hash(scenario, PILOT_HASH_COLUMNS)
    if provenance.get("scientific_hashes", {}).get("scenario_runtime_excluded_sha256") != scenario_scientific:
        provenance_errors.append("scenario scientific hash mismatch")
    empirical_scientific = independent_scientific_hash(
        empirical.assign(
            scenario_id=empirical["empirical_id"], true_ne="", truth_class="",
            simulation_generations="", simulation_attempt="", candidate_loci="",
            panel_seed="", initial_maf_low="", initial_maf_high="",
            interval_covers_true="", pilot_member="", expansion_status="",
        ),
        PILOT_HASH_COLUMNS,
    )
    if provenance.get("scientific_hashes", {}).get("empirical_runtime_excluded_sha256") != empirical_scientific:
        provenance_errors.append("empirical scientific hash mismatch")
    audit.add(
        "provenance_inputs_binary_parser_model_outputs", not provenance_errors,
        mismatch_detail(provenance_errors),
    )
    projected = numeric(provenance.get("pilot", {}).get("projected_full_seconds"))
    configured = numeric(provenance.get("pilot", {}).get("configured_expansion_max_seconds"))
    audit.add(
        "bounded_laptop_runtime_projection",
        numbers_equal(configured, settings.pilot_expansion_max_seconds)
        and numbers_equal(projected, projected_full_seconds)
        and runtime_gate == (projected <= configured),
        f"projected_full_seconds={projected}; configured_max={configured}; gate={runtime_gate}",
    )

    manifest_output_paths = {
        "replicates": paths["replicates"], "pilot": paths["pilot"],
        "summary": paths["summary"], "empirical": paths["empirical"],
        "figure_values": paths["figure_values"], "figure": paths["figure"],
        "provenance": paths["provenance"],
    }
    cache_errors = validate_cache_manifest(
        paths["cache_manifest"], paths["raw_dir"], settings, paths["currentne2"],
        paths["config"], paths["empirical_vcf"], paths["popmap"],
        manifest_output_paths, scenario, pilot, empirical, expansion_status, panel_cache,
    )
    audit.add(
        "cache_manifest_sidecars_timing_telemetry_and_inventories",
        not cache_errors,
        f"expected_attempts=1020; errors={mismatch_detail(cache_errors)}",
    )
    public_text_paths = [
        paths["replicates"], paths["pilot"], paths["summary"], paths["empirical"],
        paths["figure_values"], paths["provenance"], paths["cache_manifest"],
    ]
    privacy_errors = [
        f"{path}: {token}"
        for path in public_text_paths
        for token in privacy_tokens()
        if token in path.read_text(encoding="utf-8", errors="replace")
    ]
    audit.add(
        "public_tables_provenance_manifest_path_privacy",
        not privacy_errors,
        mismatch_detail(privacy_errors),
    )

    write_validation(audit, paths["out_tsv"], paths["out_md"])
    failures = int(audit.frame()["status"].eq("FAIL").sum())
    print(f"Peafowl N_e design validation: {len(audit.rows) - failures} PASS, {failures} FAIL")
    raise SystemExit(1 if failures else 0)


def write_validation(audit: Audit, out_tsv: Path, out_md: Path) -> None:
    frame = audit.frame()
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out_tsv, sep="\t", index=False, lineterminator="\n")
    failures = int(frame["status"].eq("FAIL").sum()) if len(frame) else 1
    lines = [
        "# Peafowl N_e sample-design validation",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Overall: **{'PASS' if failures == 0 else 'FAIL'}** "
        f"({len(frame) - failures} PASS, {failures} FAIL)",
        "",
        "This gate independently reconciles the simulated scenario grid, bounded empirical "
        "sensitivity grid, raw currentNe2 90% CI parser state, repeated pilot, summaries, "
        "figure bridge, and provenance. Scenario calibration is not a guarantee that an "
        "exact real sample size will resolve N_e > 500.",
        "",
        "| Check | Status | Details |",
        "|---|---:|---|",
    ]
    for row in frame.to_dict("records"):
        details = row["details"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{row['check_id']}` | **{row['status']}** | {details} |")
    lines.append("")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
