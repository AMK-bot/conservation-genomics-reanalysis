#!/usr/bin/env python3
"""Bounded Phase-5B peafowl N_e sample-design calibration (CGplan §13.2).

This program deliberately keeps two evidence streams separate:

* ``scenario``: neutral diploid Wright--Fisher allele-frequency drift with free
  assortment, known true N_e, and nested samples/marker panels; and
* ``empirical``: seeded individual and marker downsampling of the standard real
  peafowl Set-A VCF, never beyond each population's observed sample size.

Every replicate is passed to the project's actual currentNe2 binary and parsed
with ``currentne2_parse``--the same parser and three-state GBF decision function
used by the real results cube.  Timeouts, non-zero exits, missing output, parser
errors, and estimator non-convergence remain explicit rows.  The pilot is run
twice from the same seeds; its scientific hash excludes wall-clock telemetry and
paths.  Expansion occurs only when the pilot-projected full runtime is within
the configured laptop budget.

The neutral scenarios are a transparent study-design calibration, not a model
of green-peafowl demographic history and not a guarantee that a particular real
sample size will resolve N_e > 500.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import platform
import shlex
import shutil
from statistics import NormalDist
import subprocess
import sys
import tempfile
import time
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import currentne2_parse as cn2  # noqa: E402  (shared authoritative parser/decision code)


# Monte-Carlo intervals quantify replicate-rate uncertainty.  This is separate
# from currentNe2's configured 90% estimator interval.
MC_CI_PCT = 95.0
MC_Z = NormalDist().inv_cdf(0.5 + MC_CI_PCT / 200.0)
SCHEMA_VERSION = "phase5b-ne-design-v2-pedigree-haldane"
CACHE_ROW_SCHEMA = "phase5b-ne-design-row-cache-v2"
CACHE_MANIFEST_SCHEMA = "phase5b-ne-design-cache-manifest-v2"
TRUTH_THRESHOLD = 500.0
PEDIGREE_GOLDEN_SHA256 = "6fb3c1b84e3a98bcce1768949108df6637cb0455429de0ac46db924b2921d60f"


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


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_seed(base_seed: int, *parts: object) -> int:
    payload = "\x1f".join([str(base_seed), *(str(part) for part in parts)])
    # Stay within signed 63-bit integer range for portable TSV/JSON handling.
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


def truth_class(true_ne: float) -> str:
    if true_ne < TRUTH_THRESHOLD:
        return "below"
    if true_ne > TRUTH_THRESHOLD:
        return "above"
    return "boundary"


def wilson_interval(successes: int, total: int, z: float = MC_Z) -> tuple[float, float]:
    if total <= 0:
        return math.nan, math.nan
    p = successes / total
    denom = 1.0 + z * z / total
    centre = (p + z * z / (2.0 * total)) / denom
    half = z * math.sqrt((p * (1.0 - p) / total) + z * z / (4.0 * total * total)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def _as_finite_or_nan(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def _canonical_value(value: object) -> object:
    if value is None or value is pd.NA:
        return None
    # Empty audit fields and missing numeric values both serialize as blank TSV
    # cells; canonicalize both to JSON null so hashes can be independently
    # reproduced from the delivered tables.
    if isinstance(value, str) and value == "":
        return None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if math.isnan(number):
            return None
        if math.isinf(number):
            return "inf" if number > 0 else "-inf"
        return format(number, ".15g")
    return str(value)


def scientific_hash(frame: pd.DataFrame, columns: Sequence[str]) -> str:
    ordered = frame.loc[:, list(columns)].sort_values(
        [column for column in ("scenario_id", "replicate", "sample_size", "marker_density") if column in columns],
        kind="mergesort",
    )
    rows = [[_canonical_value(value) for value in row] for row in ordered.itertuples(index=False, name=None)]
    payload = json.dumps({"columns": list(columns), "rows": rows}, sort_keys=True, separators=(",", ":"))
    return sha256_text(payload)


def load_settings(config_path: Path) -> Settings:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    try:
        raw = config["phase5b"]["ne_design"]
    except (KeyError, TypeError) as exc:
        raise ValueError("config lacks phase5b.ne_design") from exc
    settings = Settings(
        seed=int(raw["seed"]),
        true_ne=tuple(int(value) for value in raw["true_ne"]),
        sample_sizes=tuple(int(value) for value in raw["sample_sizes"]),
        marker_densities=tuple(int(value) for value in raw["marker_densities"]),
        pilot_reps=int(raw["pilot_reps"]),
        final_reps=int(raw["final_reps"]),
        empirical_reps=int(raw["empirical_reps"]),
        simulation_generations=int(raw["simulation_generations"]),
        initial_maf_low=float(raw["initial_maf_low"]),
        initial_maf_high=float(raw["initial_maf_high"]),
        currentne2_threads=int(raw["currentne2_threads"]),
        run_timeout_seconds=float(raw["run_timeout_seconds"]),
        pilot_expansion_max_seconds=float(raw["pilot_expansion_max_seconds"]),
        genome_size_morgans=float(raw["genome_size_morgans"]),
        ci_pct=float(raw["ci_pct"]),
        resolution_truths=tuple(int(value) for value in raw["resolution_truths"]),
        resolution_min_correct_confident_ci_low=float(
            raw["resolution_min_correct_confident_ci_low"]
        ),
        resolution_max_incorrect_confident_ci_high=float(
            raw["resolution_max_incorrect_confident_ci_high"]
        ),
    )
    if sorted(settings.true_ne) != list(settings.true_ne) or len(set(settings.true_ne)) != len(settings.true_ne):
        raise ValueError("true_ne must be sorted and unique")
    if (
        sorted(set(settings.sample_sizes)) != list(settings.sample_sizes)
        or min(settings.sample_sizes) < 2
    ):
        raise ValueError("sample_sizes must be sorted, unique, and >=2")
    if (
        sorted(set(settings.marker_densities)) != list(settings.marker_densities)
        or min(settings.marker_densities) < 2
    ):
        raise ValueError("marker_densities must be sorted, unique, and >=2")
    if settings.pilot_reps < 1 or settings.final_reps < settings.pilot_reps:
        raise ValueError("require 1 <= pilot_reps <= final_reps")
    if settings.empirical_reps < 1 or settings.simulation_generations < 1:
        raise ValueError("empirical_reps and simulation_generations must be positive")
    if not (0.0 < settings.initial_maf_low < settings.initial_maf_high <= 0.5):
        raise ValueError("initial MAF bounds must satisfy 0 < low < high <= 0.5")
    if settings.ci_pct != 90:
        raise ValueError("phase5b.ne_design.ci_pct must remain 90 to match the real cube parser")
    if set(settings.true_ne) != {100, 250, 500, 1000}:
        raise ValueError("the predeclared true_ne grid must be exactly 100/250/500/1000")
    if settings.sample_sizes != (5, 10, 15, 20, 30):
        raise ValueError("the predeclared sample-size grid must remain 5/10/15/20/30")
    if settings.marker_densities != (250, 500, 1000):
        raise ValueError("the predeclared marker-density grid must remain 250/500/1000")
    if settings.resolution_truths != (250, 1000):
        raise ValueError("resolution_truths must remain exactly the frozen pair 250/1000")
    if not (
        0 <= settings.resolution_min_correct_confident_ci_low <= 1
        and 0 <= settings.resolution_max_incorrect_confident_ci_high <= 1
    ):
        raise ValueError("resolution Wilson thresholds must lie in [0,1]")
    return settings


def locate_executable(requested: str | Path | None, name: str) -> Path:
    if requested:
        candidate = _resolve(requested)
    else:
        found = shutil.which(name)
        candidate = Path(found) if found else Path(sys.executable).resolve().parent / name
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise FileNotFoundError(f"executable not found: {candidate}")
    return candidate.resolve()


def parse_currentne2(raw_path: Path, threshold: float = TRUTH_THRESHOLD) -> dict[str, object]:
    lines = raw_path.read_text(encoding="utf-8", errors="replace").splitlines()
    block = cn2._block(lines, cn2.XCHROM_HDR)
    point, low, high = cn2._estimate(block)
    basis = "cross_chromosome"
    if math.isnan(point):
        block = cn2._block(lines, cn2.WHOLE_HDR)
        point, low, high = cn2._estimate(block)
        basis = "whole_genome"
    if math.isnan(point):
        basis = "none"

    n_snps_raw = cn2._value_after(
        lines,
        "# Number of SNPs included in the analysis (only polymorphic and with less than 20% missing data):",
    )
    try:
        n_snps = int(float(n_snps_raw))
    except (TypeError, ValueError):
        n_snps = -1
    try:
        n_ind = int(float(cn2._value_after(lines, cn2.N_IND_LABEL)))
    except (TypeError, ValueError):
        n_ind = -1
    try:
        k_value = float(cn2._value_startswith(block, cn2.K_PREFIX)) if basis != "none" else math.nan
    except (TypeError, ValueError):
        k_value = math.nan

    state = cn2.gbf_state(point, low, high, threshold)
    width = high - low if not (math.isnan(low) or math.isnan(high)) else math.nan
    return {
        "ne_point": point,
        "ci_low": low,
        "ci_high": high,
        "ci_width": width,
        "n_ind": n_ind,
        "n_snps": n_snps,
        "k": k_value,
        "ne_basis": basis,
        "converged": basis != "none" and not math.isnan(point),
        "gbf_state": state,
    }


def classify_scenario_outcome(truth: str, state: str, execution_failure: bool) -> str:
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


def exact_cache_path(raw_path: Path, raw_root: Path) -> Path:
    relative = raw_path.resolve().relative_to(raw_root.resolve())
    return raw_root / ".exact_cache" / relative


def assert_public_artifact_privacy(paths: Iterable[Path]) -> None:
    banned = (
        "/" + "Users/", "/" + "private/", "/var/" + "folders/",
        "cg-ne-" + "design-",
    )
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(token in text for token in banned):
            raise RuntimeError(f"public path leak in {path}")


def run_currentne2(
    *, binary: Path, vcf_path: Path, raw_path: Path, marker_density: int,
    settings: Settings, raw_root: Path | None = None,
) -> dict[str, object]:
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    log_path = raw_path.with_suffix(".log")
    canonical_root = raw_root if raw_root is not None else raw_path.parent
    exact_raw_path = exact_cache_path(raw_path, canonical_root)
    exact_raw_path.parent.mkdir(parents=True, exist_ok=True)
    exact_log_path = exact_raw_path.with_suffix(".log")
    # A failed rerun must never parse an output left by an earlier attempt.
    for stale in (raw_path, log_path, exact_raw_path, exact_log_path):
        stale.unlink(missing_ok=True)
    execution_command = [
        str(binary), "-t", str(settings.currentne2_threads), "-s", str(marker_density),
        "-o", str(exact_raw_path), str(vcf_path), f"{settings.genome_size_morgans:g}",
    ]
    # The VCF is a deterministic, short-lived file in a random temporary
    # directory. Record a portable command contract in the public audit table
    # while retaining the exact executed command in the ignored local log.
    recorded_command = [
        _display_path(binary), "-t", str(settings.currentne2_threads),
        "-s", str(marker_density), "-o", _display_path(raw_path),
        "<ephemeral-input-vcf>", f"{settings.genome_size_morgans:g}",
    ]
    started = time.perf_counter()
    timed_out = False
    stdout = ""
    stderr = ""
    exit_code = -1
    try:
        completed = subprocess.run(
            execution_command, cwd=ROOT, capture_output=True, text=True, check=False,
            timeout=settings.run_timeout_seconds,
        )
        exit_code = int(completed.returncode)
        stdout, stderr = completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = 124
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    runtime = time.perf_counter() - started
    exact_log_text = (
        f"executed_command: {shlex.join(execution_command)}\nexit_code: {exit_code}\n"
        f"timed_out: {str(timed_out).lower()}\nwall_seconds: {runtime:.9f}\n"
        f"--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}\n"
    )
    exact_log_path.write_text(exact_log_text, encoding="utf-8")

    replacements = [
        (str(vcf_path), "<ephemeral-input-vcf>"),
        (str(vcf_path.parent), "<ephemeral-run-dir>"),
        (str(exact_raw_path), _display_path(raw_path)),
        (str(exact_log_path), _display_path(log_path)),
        (str(binary), _display_path(binary)),
        (str(ROOT.resolve()) + os.sep, ""),
    ]

    def sanitize(value: str) -> str:
        clean = value
        for source, target in replacements:
            clean = clean.replace(source, target)
        return clean

    if exact_raw_path.is_file():
        raw_path.write_text(
            sanitize(exact_raw_path.read_text(encoding="utf-8", errors="replace")),
            encoding="utf-8",
        )
    log_text = (
        f"command: {shlex.join(recorded_command)}\nexit_code: {exit_code}\n"
        f"timed_out: {str(timed_out).lower()}\nwall_seconds: {runtime:.9f}\n"
        f"--- stdout ---\n{sanitize(stdout)}\n--- stderr ---\n{sanitize(stderr)}\n"
    )
    log_path.write_text(log_text, encoding="utf-8")
    assert_public_artifact_privacy(
        [log_path] + ([raw_path] if raw_path.is_file() else [])
    )

    parse_error = ""
    parsed: dict[str, object] = {
        "ne_point": math.nan, "ci_low": math.nan, "ci_high": math.nan,
        "ci_width": math.nan, "n_ind": -1, "n_snps": -1, "k": math.nan,
        "ne_basis": "none", "converged": False, "gbf_state": "indeterminate",
    }
    if raw_path.is_file() and raw_path.stat().st_size > 0:
        try:
            parsed = parse_currentne2(raw_path)
        except Exception as exc:  # preserve malformed estimator output as a row
            parse_error = f"{type(exc).__name__}: {exc}"
    else:
        parse_error = "missing or empty currentNe2 output"

    failure_reasons: list[str] = []
    if timed_out:
        failure_reasons.append("timeout")
    if exit_code != 0:
        failure_reasons.append(f"exit_code_{exit_code}")
    if parse_error:
        failure_reasons.append("parse_error")
    failure = ";".join(failure_reasons)
    return {
        "command": shlex.join(recorded_command),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "runtime_seconds": runtime,
        "raw_output_path": _display_path(raw_path),
        "raw_output_sha256": sha256_file(raw_path) if raw_path.is_file() else "",
        "log_path": _display_path(log_path),
        "log_sha256": sha256_file(log_path),
        "parse_error": parse_error,
        "execution_failure_reason": failure,
        **parsed,
    }


def _cache_value(value: object) -> object:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if math.isnan(number):
            return None
        if math.isinf(number):
            return "inf" if number > 0 else "-inf"
        return number
    return str(value)


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def settings_sha256(settings: Settings) -> str:
    return sha256_text(json.dumps(asdict(settings), sort_keys=True, separators=(",", ":")))


def _portable_command(
    binary: Path, raw_path: Path, marker_density: int, settings: Settings,
) -> str:
    return shlex.join([
        _display_path(binary), "-t", str(settings.currentne2_threads),
        "-s", str(marker_density), "-o", _display_path(raw_path),
        "<ephemeral-input-vcf>", f"{settings.genome_size_morgans:g}",
    ])


def _execution_log_header(path: Path, command_label: str) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    labels = (command_label, "exit_code", "timed_out", "wall_seconds")
    if len(lines) < len(labels):
        raise ValueError(f"short execution log: {path}")
    values: dict[str, str] = {}
    for line, label in zip(lines[:4], labels):
        prefix = f"{label}: "
        if not line.startswith(prefix):
            raise ValueError(f"execution log header mismatch: {path}")
        values[label] = line[len(prefix):]
    return {
        "command": values[command_label],
        "exit_code": int(values["exit_code"]),
        "timed_out": values["timed_out"] == "true",
        "wall_seconds": float(values["wall_seconds"]),
    }


def _numbers_match(left: object, right: object) -> bool:
    try:
        a = math.nan if left in (None, "") else float(left)
        b = math.nan if right in (None, "") else float(right)
    except (TypeError, ValueError):
        return left == right
    if math.isnan(a) and math.isnan(b):
        return True
    if math.isinf(a) or math.isinf(b):
        return a == b
    return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)


def _binding_values_match(key: str, cached: object, expected: object) -> bool:
    """Compare signed cache identity fields without lossy float coercion."""
    desired = _cache_value(expected)
    if key in {"initial_maf_low", "initial_maf_high"}:
        return _numbers_match(cached, desired)
    # In particular, signed-63-bit RNG seeds must not pass through IEEE-754;
    # adjacent seeds above 2**53 are scientifically different bindings.
    return type(cached) is type(desired) and cached == desired


def _checkpoint_namespace(checkpoint_path: Path, raw_root: Path) -> dict[str, str]:
    relative = checkpoint_path.resolve().relative_to(
        (raw_root / "checkpoints").resolve()
    )
    canonical_raw = raw_root.resolve() / relative.with_suffix(".txt")
    return {
        "checkpoint_relative": (
            Path("checkpoints") / relative
        ).as_posix(),
        "canonical_raw_path": _display_path(canonical_raw),
        "canonical_log_path": _display_path(canonical_raw.with_suffix(".log")),
    }


def _checkpoint_payload(
    *, row: dict[str, object], checkpoint_path: Path, raw_root: Path,
    binary: Path, settings: Settings,
) -> dict[str, object]:
    public_raw = Path(str(row["raw_output_path"])) if row.get("raw_output_path") else None
    if public_raw is not None and not public_raw.is_absolute():
        public_raw = ROOT / public_raw
    public_log = Path(str(row["log_path"])) if row.get("log_path") else None
    if public_log is not None and not public_log.is_absolute():
        public_log = ROOT / public_log
    exact_raw = exact_cache_path(public_raw, raw_root) if public_raw is not None else None
    exact_log = exact_raw.with_suffix(".log") if exact_raw is not None else None
    public_raw_present = bool(public_raw is not None and public_raw.is_file())
    public_log_present = bool(public_log is not None and public_log.is_file())
    exact_raw_present = bool(exact_raw is not None and exact_raw.is_file())
    exact_log_present = bool(exact_log is not None and exact_log.is_file())
    return {
        "cache_schema": CACHE_ROW_SCHEMA,
        "analysis_schema": SCHEMA_VERSION,
        "settings_sha256": settings_sha256(settings),
        "binary_sha256": sha256_file(binary),
        "pedigree_golden_sha256": PEDIGREE_GOLDEN_SHA256,
        "namespace": _checkpoint_namespace(checkpoint_path, raw_root),
        "row": {key: _cache_value(value) for key, value in row.items()},
        "exact_execution": {
            "raw_path": _display_path(exact_raw) if exact_raw is not None else "",
            "raw_present": exact_raw_present,
            "raw_sha256": sha256_file(exact_raw) if exact_raw_present else "",
            "log_path": _display_path(exact_log) if exact_log is not None else "",
            "log_present": exact_log_present,
            "log_sha256": sha256_file(exact_log) if exact_log_present else "",
        },
        "public_materialization": {
            "raw_present": public_raw_present,
            "raw_text": public_raw.read_text(encoding="utf-8", errors="replace")
            if public_raw_present else "",
            "log_present": public_log_present,
            "log_text": public_log.read_text(encoding="utf-8", errors="replace")
            if public_log_present else "",
        },
    }


def _validate_cached_row(
    *, checkpoint_path: Path, expected: dict[str, object], raw_root: Path,
    binary: Path, settings: Settings,
) -> dict[str, object]:
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    if payload.get("cache_schema") != CACHE_ROW_SCHEMA:
        raise RuntimeError(f"cache schema mismatch: {checkpoint_path}")
    if payload.get("analysis_schema") != SCHEMA_VERSION:
        raise RuntimeError(f"analysis schema mismatch: {checkpoint_path}")
    if payload.get("settings_sha256") != settings_sha256(settings):
        raise RuntimeError(f"settings mismatch: {checkpoint_path}")
    if payload.get("binary_sha256") != sha256_file(binary):
        raise RuntimeError(f"currentNe2 binary mismatch: {checkpoint_path}")
    if payload.get("pedigree_golden_sha256") != PEDIGREE_GOLDEN_SHA256:
        raise RuntimeError(f"pedigree golden mismatch: {checkpoint_path}")
    row = dict(payload.get("row", {}))
    for key, value in expected.items():
        if key not in row or not _binding_values_match(key, row[key], value):
            raise RuntimeError(f"cached {key} mismatch: {checkpoint_path}")

    namespace = _checkpoint_namespace(checkpoint_path, raw_root)
    if payload.get("namespace") != namespace:
        raise RuntimeError(f"checkpoint namespace mismatch: {checkpoint_path}")

    reason = str(row.get("execution_failure_reason") or "")
    if reason == "input_generation_error":
        for key in ("ne_point", "ci_low", "ci_high", "ci_width", "k"):
            if row.get(key) not in (None, ""):
                raise RuntimeError(f"input-generation cache has estimate {key}: {checkpoint_path}")
        if not (
            int(row.get("n_ind", -1)) == -1 and int(row.get("n_snps", -1)) == -1
            and row.get("ne_basis") == "none" and not bool(row.get("converged"))
            and row.get("gbf_state") == "indeterminate"
        ):
            raise RuntimeError(f"input-generation sentinel mismatch: {checkpoint_path}")
        return row

    if _resolve(str(row.get("raw_output_path", ""))).resolve() != _resolve(
        namespace["canonical_raw_path"]
    ).resolve():
        raise RuntimeError(f"canonical raw namespace mismatch: {checkpoint_path}")
    if _resolve(str(row.get("log_path", ""))).resolve() != _resolve(
        namespace["canonical_log_path"]
    ).resolve():
        raise RuntimeError(f"canonical log namespace mismatch: {checkpoint_path}")

    exact = payload.get("exact_execution", {})
    raw_path = _resolve(str(row.get("raw_output_path", "")))
    log_path = _resolve(str(row.get("log_path", "")))
    materialization = payload.get("public_materialization", {})
    expected_exact_raw = exact_cache_path(raw_path, raw_root)
    expected_exact_log = expected_exact_raw.with_suffix(".log")
    if _resolve(str(exact.get("raw_path", ""))).resolve() != expected_exact_raw.resolve():
        raise RuntimeError(f"exact raw namespace mismatch: {checkpoint_path}")
    if _resolve(str(exact.get("log_path", ""))).resolve() != expected_exact_log.resolve():
        raise RuntimeError(f"exact log namespace mismatch: {checkpoint_path}")

    # Every estimator invocation writes a durable exact/public log.  A timeout,
    # non-zero exit, or crash is nevertheless allowed to produce no raw output.
    # Presence booleans make that absence part of the signed row contract,
    # rather than turning a legitimate failed attempt into an endless rerun.
    exact_log = _resolve(str(exact.get("log_path", "")))
    if not bool(exact.get("log_present")) or not exact_log.is_file():
        raise RuntimeError(f"exact execution log absent: {checkpoint_path}")
    if sha256_file(exact_log) != exact.get("log_sha256"):
        raise RuntimeError(f"exact execution log mismatch: {checkpoint_path}")
    if not bool(materialization.get("log_present")):
        raise RuntimeError(f"public log presence contract mismatch: {checkpoint_path}")
    if not log_path.is_file():
        log_text = str(materialization.get("log_text", ""))
        if not log_text:
            raise RuntimeError(f"no public log rematerialization: {checkpoint_path}")
        _atomic_text(log_path, log_text)
    if sha256_file(log_path) != row.get("log_sha256"):
        raise RuntimeError(f"public log hash mismatch: {checkpoint_path}")
    public_log = _execution_log_header(log_path, "command")
    exact_log_values = _execution_log_header(exact_log, "executed_command")
    if public_log["command"] != row.get("command"):
        raise RuntimeError(f"public command/log mismatch: {checkpoint_path}")
    if int(row.get("exit_code", -1)) != public_log["exit_code"] or (
        bool(row.get("timed_out")) != public_log["timed_out"]
    ):
        raise RuntimeError(f"public execution telemetry mismatch: {checkpoint_path}")
    if (
        exact_log_values["exit_code"] != public_log["exit_code"]
        or exact_log_values["timed_out"] != public_log["timed_out"]
        or not math.isclose(
            float(exact_log_values["wall_seconds"]),
            float(public_log["wall_seconds"]), rel_tol=0, abs_tol=5.1e-10,
        )
        or not math.isclose(
            float(row.get("runtime_seconds", math.nan)),
            float(public_log["wall_seconds"]), rel_tol=0, abs_tol=5.1e-10,
        )
    ):
        raise RuntimeError(f"exact/public runtime telemetry mismatch: {checkpoint_path}")

    raw_present = bool(materialization.get("raw_present"))
    exact_raw_present = bool(exact.get("raw_present"))
    if raw_present != exact_raw_present or raw_present != bool(row.get("raw_output_sha256")):
        raise RuntimeError(f"raw presence contract mismatch: {checkpoint_path}")
    exact_raw = _resolve(str(exact.get("raw_path", "")))
    if raw_present:
        if not exact_raw.is_file() or sha256_file(exact_raw) != exact.get("raw_sha256"):
            raise RuntimeError(f"exact execution raw mismatch: {checkpoint_path}")
        if not raw_path.is_file():
            raw_text = str(materialization.get("raw_text", ""))
            # An empty raw file is legitimate and is represented by a present
            # flag plus the SHA-256 of empty content, not by a truthy-text test.
            _atomic_text(raw_path, raw_text)
        if sha256_file(raw_path) != row.get("raw_output_sha256"):
            raise RuntimeError(f"public raw hash mismatch: {checkpoint_path}")
    else:
        if exact.get("raw_sha256") or materialization.get("raw_text"):
            raise RuntimeError(f"absent raw has cached content/hash: {checkpoint_path}")
        if exact_raw.is_file() or raw_path.is_file():
            raise RuntimeError(f"absent raw unexpectedly materialized: {checkpoint_path}")
    public_paths = [log_path] + ([raw_path] if raw_present else [])
    assert_public_artifact_privacy(public_paths)
    if row.get("command") != _portable_command(
        binary, raw_path, int(row["marker_density"]), settings
    ):
        raise RuntimeError(f"portable command mismatch: {checkpoint_path}")
    exact_tokens = shlex.split(str(exact_log_values["command"]))
    if not (
        len(exact_tokens) == 9
        and Path(exact_tokens[0]).resolve() == binary.resolve()
        and exact_tokens[1:6] == [
            "-t", str(settings.currentne2_threads), "-s",
            str(int(row["marker_density"])), "-o",
        ]
        and Path(exact_tokens[6]).resolve() == expected_exact_raw.resolve()
        and exact_tokens[8] == f"{settings.genome_size_morgans:g}"
    ):
        raise RuntimeError(f"exact execution command mismatch: {checkpoint_path}")
    expected_reasons: list[str] = []
    if bool(row.get("timed_out")):
        expected_reasons.append("timeout")
    if int(row.get("exit_code", -1)) != 0:
        expected_reasons.append(f"exit_code_{int(row.get('exit_code', -1))}")
    if row.get("parse_error"):
        expected_reasons.append("parse_error")
    if reason != ";".join(expected_reasons):
        raise RuntimeError(f"execution failure reason mismatch: {checkpoint_path}")
    if not raw_present:
        for key in ("ne_point", "ci_low", "ci_high", "ci_width", "k"):
            if row.get(key) not in (None, ""):
                raise RuntimeError(f"missing-output cache has estimate {key}: {checkpoint_path}")
        if not (
            int(row.get("n_ind", -1)) == -1 and int(row.get("n_snps", -1)) == -1
            and row.get("ne_basis") == "none" and not bool(row.get("converged"))
            and row.get("gbf_state") == "indeterminate"
            and "parse_error" in reason
        ):
            raise RuntimeError(f"missing-output sentinel mismatch: {checkpoint_path}")
        return row

    parsed = parse_currentne2(raw_path)
    exact_parsed = parse_currentne2(exact_raw)
    for key in ("ne_point", "ci_low", "ci_high", "ci_width", "k"):
        if not (
            _numbers_match(row.get(key), parsed[key])
            and _numbers_match(parsed[key], exact_parsed[key])
        ):
            raise RuntimeError(f"cached parser field {key} mismatch: {checkpoint_path}")
    for key in ("n_ind", "n_snps", "ne_basis", "converged", "gbf_state"):
        if row.get(key) != parsed[key] or parsed[key] != exact_parsed[key]:
            raise RuntimeError(f"cached parser field {key} mismatch: {checkpoint_path}")
    return row


def _preserve_uncheckpointed(
    *, raw_path: Path, raw_root: Path,
) -> None:
    log_path = raw_path.with_suffix(".log")
    exact_raw = exact_cache_path(raw_path, raw_root)
    exact_log = exact_raw.with_suffix(".log")
    existing = [path for path in (raw_path, log_path, exact_raw, exact_log) if path.is_file()]
    if not existing:
        return
    partial_root = raw_root / ".partial_cache"
    for source in existing:
        try:
            relative = source.relative_to(raw_root)
        except ValueError:
            relative = Path(source.name)
        destination = partial_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination = destination.with_name(
            f"{destination.name}.{sha256_file(source)[:12]}.partial"
        )
        source.replace(destination)


def _quarantine_binding_mismatch(
    *, checkpoint_path: Path, raw_path: Path, raw_root: Path, error: Exception,
) -> None:
    sources = [
        checkpoint_path, raw_path, raw_path.with_suffix(".log"),
        exact_cache_path(raw_path, raw_root),
        exact_cache_path(raw_path, raw_root).with_suffix(".log"),
    ]
    quarantine = raw_root / ".binding_mismatch"
    moved: list[str] = []
    for source in sources:
        if not source.is_file():
            continue
        try:
            relative = source.relative_to(raw_root)
        except ValueError:
            relative = Path(source.name)
        destination = quarantine / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination = destination.with_name(
            f"{destination.name}.{sha256_file(source)[:12]}.mismatch"
        )
        source.replace(destination)
        moved.append(_display_path(destination))
    reason_path = quarantine / "events" / f"{checkpoint_path.stem}.{time.time_ns()}.json"
    _atomic_json(reason_path, {
        "error": f"{type(error).__name__}: {error}",
        "checkpoint": _display_path(checkpoint_path),
        "moved": moved,
    })
    print(f"WARNING: quarantined mismatched checkpoint {checkpoint_path}: {error}", file=sys.stderr)


def _preserved_panel_runtime(
    *, raw_root: Path, run_label: str, true_ne: int, replicate: int,
    measured_seconds: float, panel_sha256: str, panel_error: str,
    seed: int, simulation_attempt: int, candidate_loci: int, panel_seed: int,
    binary: Path, settings: Settings,
) -> float:
    """Return an atomic, scientifically bound panel timing across resumes."""
    timing_path = raw_root / ".timing_cache" / "panels" / run_label / (
        f"ne{true_ne:04d}.r{replicate:02d}.json"
    )
    binding = {
        "cache_schema": "phase5b-ne-design-panel-timing-v1",
        "analysis_schema": SCHEMA_VERSION,
        "settings_sha256": settings_sha256(settings),
        "binary_sha256": sha256_file(binary),
        "pedigree_golden_sha256": PEDIGREE_GOLDEN_SHA256,
        "run_label": run_label,
        "true_ne": int(true_ne),
        "replicate": int(replicate),
        "panel_sha256": panel_sha256,
        "panel_error": panel_error,
        "seed": int(seed),
        "simulation_attempt": int(simulation_attempt),
        "candidate_loci": int(candidate_loci),
        "panel_seed": int(panel_seed),
    }
    if timing_path.is_file():
        try:
            cached = json.loads(timing_path.read_text(encoding="utf-8"))
            cached_binding = {key: cached.get(key) for key in binding}
            runtime = float(cached.get("simulation_runtime_seconds", math.nan))
            if cached_binding != binding or not math.isfinite(runtime) or runtime < 0:
                raise ValueError("panel timing binding/runtime mismatch")
            return runtime
        except Exception as exc:
            destination = raw_root / ".binding_mismatch" / "panel_timings" / run_label / (
                f"{timing_path.stem}.{sha256_file(timing_path)[:12]}.mismatch.json"
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            timing_path.replace(destination)
            reason_path = destination.with_suffix(".reason.json")
            _atomic_json(reason_path, {
                "error": f"{type(exc).__name__}: {exc}",
                "source": _display_path(timing_path),
                "quarantined": _display_path(destination),
            })
    payload = {**binding, "simulation_runtime_seconds": float(measured_seconds)}
    _atomic_json(timing_path, payload)
    return float(measured_seconds)


def _quarantine_stale_file(path: Path, raw_root: Path, reason: str) -> None:
    relative = path.resolve().relative_to(raw_root.resolve())
    destination = raw_root / ".stale_cache" / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination = destination.with_name(
        f"{destination.name}.{sha256_file(path)[:12]}.stale"
    )
    path.replace(destination)
    _atomic_json(destination.with_suffix(destination.suffix + ".reason.json"), {
        "reason": reason,
        "source": relative.as_posix(),
        "quarantined": _display_path(destination),
    })


def reconcile_cache_namespace(
    *, raw_root: Path, settings: Settings, expansion_status: str,
    empirical: pd.DataFrame,
) -> None:
    """Recoverably remove artifacts outside the current configured namespace."""
    scenario_runs: list[tuple[str, range]] = [
        ("pilot_primary", range(1, settings.pilot_reps + 1)),
        ("pilot_repeat", range(1, settings.pilot_reps + 1)),
    ]
    if expansion_status == "expanded":
        scenario_runs.append((
            "expanded", range(settings.pilot_reps + 1, settings.final_reps + 1)
        ))
    expected_checkpoints: set[Path] = set()
    expected_timings: set[Path] = set()
    for run_label, replicates in scenario_runs:
        for true_ne in settings.true_ne:
            for replicate in replicates:
                expected_timings.add((
                    raw_root / ".timing_cache" / "panels" / run_label
                    / f"ne{true_ne:04d}.r{replicate:02d}.json"
                ).resolve())
                for sample_size in settings.sample_sizes:
                    for marker_density in settings.marker_densities:
                        raw_path = _scenario_raw_path(
                            raw_root, run_label, true_ne, sample_size,
                            marker_density, replicate,
                        )
                        expected_checkpoints.add((
                            raw_root / "checkpoints" / raw_path.relative_to(raw_root)
                        ).with_suffix(".json").resolve())
    for row in empirical.to_dict("records"):
        raw_path = raw_root / "empirical" / (
            f"{row['population']}.n{int(row['sample_size']):02d}."
            f"m{int(row['marker_density']):04d}.r{int(row['replicate']):02d}.currentne2.txt"
        )
        expected_checkpoints.add((
            raw_root / "checkpoints" / raw_path.relative_to(raw_root)
        ).with_suffix(".json").resolve())

    for checkpoint in list((raw_root / "checkpoints").rglob("*.json")):
        if checkpoint.resolve() in expected_checkpoints:
            continue
        relative = checkpoint.resolve().relative_to(
            (raw_root / "checkpoints").resolve()
        )
        raw_path = raw_root / relative.with_suffix(".txt")
        _quarantine_binding_mismatch(
            checkpoint_path=checkpoint, raw_path=raw_path, raw_root=raw_root,
            error=RuntimeError("checkpoint namespace is not in current configured grid"),
        )
    for timing in list((raw_root / ".timing_cache").rglob("*.json")):
        if timing.resolve() not in expected_timings:
            _quarantine_stale_file(
                timing, raw_root, "panel timing namespace is not in current configured grid"
            )

    referenced: set[Path] = set()
    for checkpoint in (raw_root / "checkpoints").rglob("*.json"):
        payload = json.loads(checkpoint.read_text(encoding="utf-8"))
        row = payload.get("row", {})
        exact = payload.get("exact_execution", {})
        materialization = payload.get("public_materialization", {})
        if bool(materialization.get("raw_present")):
            referenced.add(_resolve(str(row.get("raw_output_path", ""))).resolve())
        if bool(materialization.get("log_present")):
            referenced.add(_resolve(str(row.get("log_path", ""))).resolve())
        if bool(exact.get("raw_present")):
            referenced.add(_resolve(str(exact.get("raw_path", ""))).resolve())
        if bool(exact.get("log_present")):
            referenced.add(_resolve(str(exact.get("log_path", ""))).resolve())
    artifact_patterns = (
        "*.currentne2.txt", "*.currentne2.log",
    )
    for pattern in artifact_patterns:
        for artifact in list(raw_root.rglob(pattern)):
            relative_parts = artifact.resolve().relative_to(raw_root.resolve()).parts
            if any(part in {".binding_mismatch", ".partial_cache", ".stale_cache"}
                   for part in relative_parts):
                continue
            if artifact.resolve() not in referenced:
                _quarantine_stale_file(
                    artifact, raw_root, "artifact is not referenced by a current row checkpoint"
                )


def _wf_generation(
    population: np.ndarray, rng: np.random.Generator,
    chromosome_indices: Sequence[np.ndarray],
) -> np.ndarray:
    """One diploid Wright--Fisher generation with Mendelian gametes.

    Each of the two gametes forming an offspring chooses one parental
    individual, shared genome-wide.  On each 1-Morgan chromosome it chooses a
    starting homolog and toggles homolog between adjacent, evenly spaced loci
    with the Haldane recombination fraction.  Independent meioses across the
    32 chromosomes implement free assortment without erasing pedigree LD.
    """
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
                distance_morgans = 1.0 / n_loci
                recombination_fraction = (1.0 - math.exp(-2.0 * distance_morgans)) / 2.0
                toggles = (rng.random((population_size, n_loci - 1)) < recombination_fraction)
                parity = np.bitwise_xor.accumulate(toggles, axis=1).astype(np.uint8, copy=False)
                homologs = np.empty((population_size, n_loci), dtype=np.uint8)
                homologs[:, 0] = starts
                homologs[:, 1:] = starts[:, None] ^ parity
            offspring[:, gamete, loci] = population[
                parent[:, None], homologs, loci[None, :]
            ]
    return offspring


def simulate_nested_panel(
    *, settings: Settings, true_ne: int, replicate: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], int, int, int, int]:
    """Simulate a neutral pedigree-preserving nested individual/locus panel.

    The population is an explicit ``H[N,2,L]`` uint8 haplotype array.  Fifteen
    shared-parent Wright--Fisher generations with Mendelian gametes, Haldane
    recombination, and independent chromosome assortment generate the
    multilocus drift LD that currentNe2 estimates.  Selected loci retain their
    original simulated chromosome and map coordinate in every nested VCF.
    """
    seed = stable_seed(settings.seed, "scenario", true_ne, replicate)
    min_n, max_n = min(settings.sample_sizes), max(settings.sample_sizes)
    max_markers = max(settings.marker_densities)
    if max_n > true_ne:
        raise ValueError(f"sample n={max_n} exceeds simulated diploid population N_e={true_ne}")

    for attempt, factor in enumerate((4, 8, 16), start=1):
        panel_seed = stable_seed(seed, "attempt", attempt)
        rng = np.random.default_rng(panel_seed)
        candidate_count = max_markers * factor
        maf = rng.uniform(settings.initial_maf_low, settings.initial_maf_high, candidate_count)
        p = np.where(rng.random(candidate_count) < 0.5, maf, 1.0 - maf)
        population = (
            rng.random((true_ne, 2, candidate_count)) < p[None, None, :]
        ).astype(np.uint8)
        candidate_chromosomes = np.arange(candidate_count, dtype=np.int16) % 32 + 1
        candidate_ranks = np.arange(candidate_count, dtype=np.int32) // 32
        loci_by_chromosome = [
            np.flatnonzero(candidate_chromosomes == chromosome)
            for chromosome in range(1, 33)
        ]
        for _ in range(settings.simulation_generations):
            population = _wf_generation(population, rng, loci_by_chromosome)
        diploids = population.sum(axis=1)
        individual_order = rng.permutation(true_ne)
        nested = diploids[individual_order[:max_n], :]
        allele_count = nested[:min_n, :].sum(axis=0)
        polymorphic = np.flatnonzero((allele_count > 0) & (allele_count < 2 * min_n))
        quotas = np.full(32, max_markers // 32, dtype=int)
        quotas[:max_markers % 32] += 1
        by_chromosome: list[np.ndarray] = []
        enough = True
        for chromosome, quota in enumerate(quotas, start=1):
            eligible = polymorphic[candidate_chromosomes[polymorphic] == chromosome]
            if len(eligible) < quota:
                enough = False
                break
            by_chromosome.append(rng.permutation(eligible)[:quota])
        if enough:
            # Round-robin once across chromosomes: every nested marker prefix
            # is balanced, while each locus keeps its original map identity.
            locus_order = np.array([
                int(by_chromosome[chromosome][rank])
                for rank in range(int(quotas.max()))
                for chromosome in range(32)
                if rank < len(by_chromosome[chromosome])
            ], dtype=np.int32)
            selected = nested[:, locus_order].astype(np.uint8, copy=False)
            selected_chromosomes = candidate_chromosomes[locus_order]
            # Evenly centred positions on each simulated 1-M chromosome.  The
            # integer coordinate is metadata only; currentNe2 receives 32 M.
            chromosome_sizes = np.array([len(indices) for indices in loci_by_chromosome])
            selected_map_morgans = np.array([
                (candidate_ranks[index] + 0.5) / chromosome_sizes[candidate_chromosomes[index] - 1]
                for index in locus_order
            ], dtype=float)
            marker_ids = [f"sim_locus_{rank + 1:05d}" for rank in range(max_markers)]
            return (
                selected, selected_chromosomes, selected_map_morgans, marker_ids,
                seed, attempt, candidate_count, panel_seed,
            )
    raise RuntimeError(
        f"could not obtain {max_markers} loci polymorphic in nested n={min_n} "
        f"for true N_e={true_ne}, replicate={replicate}"
    )


def _dosage_gt(value: int) -> str:
    return ("0/0", "0/1", "1/1")[int(value)]


def write_simulation_vcf(
    path: Path, genotypes: np.ndarray, marker_chromosomes: np.ndarray,
    marker_map_morgans: np.ndarray, sample_size: int, marker_density: int,
) -> tuple[list[str], list[str]]:
    samples = [f"SIM{i + 1:03d}" for i in range(sample_size)]
    marker_ids = [f"sim_locus_{i + 1:05d}" for i in range(marker_density)]
    rows: list[tuple[int, int, int]] = []
    for index in range(marker_density):
        chrom = int(marker_chromosomes[index])
        # Preserve map order at an integer VCF coordinate.  currentNe2 ignores
        # physical distance in the configured 32-Morgan cross-chromosome mode.
        pos = max(1, int(round(float(marker_map_morgans[index]) * 100_000_000)))
        rows.append((chrom, pos, index))
    rows.sort()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("##fileformat=VCFv4.2\n##source=CG_phase5b_ne_design_neutral_Wright_Fisher_free_assortment\n")
        for chrom in range(1, 33):
            handle.write(f"##contig=<ID={chrom}>\n")
        handle.write('##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n')
        handle.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t" + "\t".join(samples) + "\n")
        for chrom, pos, index in rows:
            calls = [_dosage_gt(value) for value in genotypes[:sample_size, index]]
            handle.write(
                f"{chrom}\t{pos}\t{marker_ids[index]}\tA\tG\t.\tPASS\t.\tGT\t"
                + "\t".join(calls) + "\n"
            )
    return samples, marker_ids


def _scenario_raw_path(raw_dir: Path, run_label: str, true_ne: int, sample_size: int,
                       marker_density: int, replicate: int) -> Path:
    return raw_dir / "scenario" / run_label / (
        f"ne{true_ne:04d}.n{sample_size:02d}.m{marker_density:04d}.r{replicate:02d}.currentne2.txt"
    )


def run_scenario_batch(
    *, settings: Settings, binary: Path, raw_dir: Path, work_dir: Path,
    replicates: Iterable[int], run_label: str, pilot_member: bool,
    expansion_status: str,
) -> tuple[pd.DataFrame, float]:
    records: list[dict[str, object]] = []
    batch_started = time.perf_counter()
    for true_ne in settings.true_ne:
        for replicate in replicates:
            panel_error = ""
            simulation_started = time.perf_counter()
            try:
                (
                    genotypes, marker_chromosomes, marker_map_morgans,
                    all_markers, seed, simulation_attempt, candidate_loci,
                    panel_seed,
                ) = simulate_nested_panel(
                    settings=settings, true_ne=true_ne, replicate=replicate
                )
            except Exception as exc:
                genotypes = np.empty((max(settings.sample_sizes), 0), dtype=np.uint8)
                marker_chromosomes = np.empty(0, dtype=np.int16)
                marker_map_morgans = np.empty(0, dtype=float)
                seed = stable_seed(settings.seed, "scenario", true_ne, replicate)
                simulation_attempt = -1
                candidate_loci = 0
                panel_seed = -1
                all_markers = []
                panel_error = f"{type(exc).__name__}: {exc}"
            measured_simulation_seconds = time.perf_counter() - simulation_started
            panel_sha256 = (
                sha256_text(f"input_generation_error\x1f{panel_error}")
                if panel_error else panel_fingerprint(
                    genotypes, marker_chromosomes, marker_map_morgans,
                    all_markers, seed, simulation_attempt, candidate_loci, panel_seed,
                )
            )
            preserved_simulation_seconds = _preserved_panel_runtime(
                raw_root=raw_dir, run_label=run_label, true_ne=true_ne,
                replicate=replicate, measured_seconds=measured_simulation_seconds,
                panel_sha256=panel_sha256, panel_error=panel_error, seed=seed,
                simulation_attempt=simulation_attempt, candidate_loci=candidate_loci,
                panel_seed=panel_seed, binary=binary, settings=settings,
            )
            simulation_runtime_share = (
                preserved_simulation_seconds
                / (len(settings.sample_sizes) * len(settings.marker_densities))
            )
            for sample_size in settings.sample_sizes:
                for marker_density in settings.marker_densities:
                    scenario_id = f"ne{true_ne:04d}_n{sample_size:02d}_m{marker_density:04d}"
                    vcf_path = work_dir / run_label / (
                        f"{scenario_id}.r{replicate:02d}.vcf"
                    )
                    raw_path = _scenario_raw_path(
                        raw_dir, run_label, true_ne, sample_size, marker_density, replicate
                    )
                    checkpoint_path = (
                        raw_dir / "checkpoints" / raw_path.relative_to(raw_dir)
                    ).with_suffix(".json")
                    base: dict[str, object] = {
                        "analysis_type": "scenario", "scenario_id": scenario_id,
                        "replicate": replicate, "true_ne": true_ne,
                        "truth_class": truth_class(true_ne), "sample_size": sample_size,
                        "marker_density": marker_density, "seed": seed,
                        "simulation_attempt": simulation_attempt,
                        "candidate_loci": candidate_loci, "panel_seed": panel_seed,
                        "simulation_runtime_seconds": simulation_runtime_share,
                        "simulation_generations": settings.simulation_generations,
                        "initial_maf_low": settings.initial_maf_low,
                        "initial_maf_high": settings.initial_maf_high,
                        "pilot_member": pilot_member, "expansion_status": expansion_status,
                    }
                    if panel_error:
                        result = {
                            "command": "", "exit_code": -1, "timed_out": False,
                            "runtime_seconds": 0.0, "raw_output_path": "",
                            "raw_output_sha256": "", "log_path": "", "log_sha256": "",
                            "parse_error": panel_error,
                            "execution_failure_reason": "input_generation_error",
                            "ne_point": math.nan, "ci_low": math.nan, "ci_high": math.nan,
                            "ci_width": math.nan, "n_ind": -1, "n_snps": -1,
                            "k": math.nan, "ne_basis": "none", "converged": False,
                            "gbf_state": "indeterminate",
                        }
                        samples: list[str] = []
                        markers: list[str] = []
                        input_hash = ""
                    else:
                        samples, markers = write_simulation_vcf(
                            vcf_path, genotypes, marker_chromosomes,
                            marker_map_morgans, sample_size, marker_density
                        )
                        input_hash = sha256_file(vcf_path)
                    marker_hash = sha256_text("\n".join(markers)) if markers else ""
                    sample_hash = sha256_text("\n".join(samples)) if samples else ""
                    expected_cache = {
                        **base,
                        "input_vcf_sha256": input_hash,
                        "marker_ids_sha256": marker_hash,
                        "sample_ids_sha256": sample_hash,
                    }
                    if checkpoint_path.is_file():
                        try:
                            record = _validate_cached_row(
                                checkpoint_path=checkpoint_path, expected=expected_cache,
                                raw_root=raw_dir, binary=binary, settings=settings,
                            )
                        except Exception as exc:
                            _quarantine_binding_mismatch(
                                checkpoint_path=checkpoint_path, raw_path=raw_path,
                                raw_root=raw_dir, error=exc,
                            )
                        else:
                            records.append(record)
                            vcf_path.unlink(missing_ok=True)
                            continue
                    _preserve_uncheckpointed(raw_path=raw_path, raw_root=raw_dir)
                    if not panel_error:
                        result = run_currentne2(
                            binary=binary, vcf_path=vcf_path, raw_path=raw_path,
                            marker_density=marker_density, settings=settings,
                            raw_root=raw_dir,
                        )
                        vcf_path.unlink(missing_ok=True)
                    execution_failure = bool(result["execution_failure_reason"])
                    coverage: bool | str = ""
                    low = _as_finite_or_nan(result["ci_low"])
                    high = _as_finite_or_nan(result["ci_high"])
                    if not math.isnan(low) and not math.isnan(high) and not execution_failure:
                        coverage = bool(low <= true_ne <= high)
                    record = {
                        **base,
                        "input_vcf_sha256": input_hash,
                        "marker_ids_sha256": marker_hash,
                        "sample_ids_sha256": sample_hash,
                        **result,
                        "interval_covers_true": coverage,
                        "outcome_class": classify_scenario_outcome(
                            truth_class(true_ne), str(result["gbf_state"]), execution_failure
                        ),
                    }
                    records.append(record)
                    _atomic_json(
                        checkpoint_path,
                        _checkpoint_payload(
                            row=record, checkpoint_path=checkpoint_path,
                            raw_root=raw_dir, binary=binary, settings=settings
                        ),
                    )
    return pd.DataFrame(records, columns=SCENARIO_COLUMNS), time.perf_counter() - batch_started


def _parse_gt(gt: str) -> tuple[int, int] | None:
    gt = gt.split(":", 1)[0]
    if "." in gt:
        return None
    separator = "/" if "/" in gt else ("|" if "|" in gt else None)
    if separator is None:
        return None
    left, right = gt.split(separator, 1)
    try:
        return int(left), int(right)
    except ValueError:
        return None


def read_popmap(path: Path) -> dict[str, list[str]]:
    frame = pd.read_csv(path, sep="\t", dtype=str)
    if list(frame.columns)[:2] != ["sample", "population"]:
        raise ValueError("popmap must begin with sample and population columns")
    if frame["sample"].duplicated().any():
        raise ValueError("popmap contains duplicate sample IDs")
    return {
        str(pop): group["sample"].astype(str).tolist()
        for pop, group in frame.groupby("population", sort=True)
    }


def empirical_candidate_reservoir(
    *, bcftools: Path, vcf_path: Path, sample_order: Sequence[str],
    capacity: int, seed: int,
) -> tuple[list[EmpiricalVariant], int]:
    command = [
        str(bcftools), "query", "-f", r"%CHROM\t%POS\t%REF\t%ALT[\t%GT]\n", str(vcf_path),
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert process.stdout is not None
    rng = np.random.default_rng(seed)
    reservoir: list[EmpiricalVariant] = []
    seen = 0
    for line in process.stdout:
        parts = line.rstrip("\n").split("\t")
        if len(parts) != 4 + len(sample_order):
            continue
        chrom, pos, ref, alt, *genotypes = parts
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
            replace = int(rng.integers(0, seen))
            if replace < capacity:
                reservoir[replace] = variant
    stderr = process.stderr.read() if process.stderr is not None else ""
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"bcftools query failed ({return_code}): {stderr[-500:]}")
    if len(reservoir) < capacity:
        raise RuntimeError(f"only {len(reservoir)} eligible biallelic SNPs for reservoir {capacity}")
    return reservoir, seen


def _chrom_key(chrom: str) -> tuple[object, ...]:
    tail = chrom.rsplit("_", 1)[-1]
    return (0, int(tail)) if tail.isdigit() else (1, chrom)


def write_empirical_vcf(
    path: Path, variants: Sequence[EmpiricalVariant], sample_indices: Sequence[int],
    sample_names: Sequence[str],
) -> list[str]:
    ordered = sorted(variants, key=lambda row: (_chrom_key(row.chrom), row.pos, row.ref, row.alt))
    contigs = sorted({row.chrom for row in ordered}, key=_chrom_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("##fileformat=VCFv4.2\n##source=CG_phase5b_empirical_seeded_rarefaction\n")
        for contig in contigs:
            handle.write(f"##contig=<ID={contig}>\n")
        handle.write('##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n')
        handle.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t" + "\t".join(sample_names) + "\n")
        for row in ordered:
            calls = [row.genotypes[index].replace("|", "/") for index in sample_indices]
            handle.write(
                f"{row.chrom}\t{row.pos}\t{row.marker_id}\t{row.ref}\t{row.alt}\t.\tPASS\t.\tGT\t"
                + "\t".join(calls) + "\n"
            )
    return [row.marker_id for row in ordered]


def _eligible_empirical_variant(row: EmpiricalVariant, sample_indices: Sequence[int]) -> bool:
    called = [_parse_gt(row.genotypes[index]) for index in sample_indices]
    valid = [pair for pair in called if pair is not None]
    # currentNe2's contract is strictly *less than* 20% missing.  Integer
    # arithmetic makes the boundary auditable and rejects exactly 80% called
    # (notably 4/5 and 8/10), which a floating ``>=0.8`` test admitted.
    if len(valid) * 5 <= 4 * len(sample_indices):
        return False
    alleles = [allele for pair in valid for allele in pair]
    return bool(alleles) and min(alleles) != max(alleles)


def _subset_plan(samples: Sequence[str], n: int, reps: int, seed: int) -> list[tuple[list[str], bool]]:
    combinations = list(itertools.combinations(samples, n))
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(combinations))
    shuffled = [combinations[index] for index in order]
    return [
        (list(shuffled[rep % len(shuffled)]), rep >= len(shuffled))
        for rep in range(reps)
    ]


def run_empirical(
    *, settings: Settings, binary: Path, bcftools: Path, empirical_vcf: Path,
    popmap_path: Path, raw_dir: Path, work_dir: Path,
) -> tuple[pd.DataFrame, dict[str, object]]:
    listed = subprocess.run(
        [str(bcftools), "query", "-l", str(empirical_vcf)],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    sample_index = {sample: index for index, sample in enumerate(listed)}
    populations = read_popmap(popmap_path)
    missing = sorted({sample for samples in populations.values() for sample in samples} - set(listed))
    if missing:
        raise ValueError(f"empirical VCF lacks popmap samples: {missing}")

    reservoir_capacity = max(25_000, max(settings.marker_densities) * 25)
    reservoir_seed = stable_seed(settings.seed, "empirical", "candidate_reservoir")
    variants, n_source_variants = empirical_candidate_reservoir(
        bcftools=bcftools, vcf_path=empirical_vcf, sample_order=listed,
        capacity=reservoir_capacity, seed=reservoir_seed,
    )
    reservoir_hash = sha256_text("\n".join(sorted(row.marker_id for row in variants)))

    records: list[dict[str, object]] = []
    min_empirical_n = min(settings.sample_sizes)
    for population, population_samples in populations.items():
        observed_n = len(population_samples)
        if observed_n < min_empirical_n:
            continue
        for n in range(min_empirical_n, observed_n + 1):
            subset_seed = stable_seed(settings.seed, "empirical", population, n, "subsets")
            plans = _subset_plan(population_samples, n, settings.empirical_reps, subset_seed)
            for replicate_index, (subset, subset_reused) in enumerate(plans, start=1):
                indices = [sample_index[sample] for sample in subset]
                eligible = [row for row in variants if _eligible_empirical_variant(row, indices)]
                marker_seed = stable_seed(settings.seed, "empirical", population, n, replicate_index, "markers")
                rng = np.random.default_rng(marker_seed)
                if eligible:
                    eligible = [eligible[index] for index in rng.permutation(len(eligible))]
                for marker_density in settings.marker_densities:
                    empirical_id = f"{population}_n{n:02d}_m{marker_density:04d}"
                    vcf_path = work_dir / "empirical" / (
                        f"{population}.n{n:02d}.m{marker_density:04d}.r{replicate_index:02d}.vcf"
                    )
                    raw_path = raw_dir / "empirical" / (
                        f"{population}.n{n:02d}.m{marker_density:04d}.r{replicate_index:02d}.currentne2.txt"
                    )
                    checkpoint_path = (
                        raw_dir / "checkpoints" / raw_path.relative_to(raw_dir)
                    ).with_suffix(".json")
                    base = {
                        "analysis_type": "empirical", "empirical_id": empirical_id,
                        "population": population, "observed_n": observed_n, "sample_size": n,
                        "marker_density": marker_density, "replicate": replicate_index,
                        "seed": marker_seed, "subset_seed": subset_seed,
                        "subset_reused": subset_reused,
                        "sample_ids": ";".join(subset),
                        "sample_ids_sha256": sha256_text("\n".join(subset)),
                    }
                    if len(eligible) < marker_density:
                        result = {
                            "input_vcf_sha256": "", "marker_ids_sha256": "", "command": "",
                            "exit_code": -1, "timed_out": False, "runtime_seconds": 0.0,
                            "raw_output_path": "", "raw_output_sha256": "", "log_path": "",
                            "log_sha256": "", "parse_error": (
                                f"only {len(eligible)} polymorphic >80%-called (<20% missing) reservoir loci; "
                                f"need {marker_density}"
                            ), "execution_failure_reason": "input_generation_error",
                            "ne_point": math.nan, "ci_low": math.nan, "ci_high": math.nan,
                            "ci_width": math.nan, "n_ind": -1, "n_snps": -1, "k": math.nan,
                            "ne_basis": "none", "converged": False, "gbf_state": "indeterminate",
                        }
                        input_hash = ""
                        marker_hash = ""
                    else:
                        selected = eligible[:marker_density]
                        marker_ids = write_empirical_vcf(vcf_path, selected, indices, subset)
                        input_hash = sha256_file(vcf_path)
                        marker_hash = sha256_text("\n".join(marker_ids))
                    expected_cache = {
                        **base,
                        "input_vcf_sha256": input_hash,
                        "marker_ids_sha256": marker_hash,
                    }
                    if checkpoint_path.is_file():
                        try:
                            record = _validate_cached_row(
                                checkpoint_path=checkpoint_path, expected=expected_cache,
                                raw_root=raw_dir, binary=binary, settings=settings,
                            )
                        except Exception as exc:
                            _quarantine_binding_mismatch(
                                checkpoint_path=checkpoint_path, raw_path=raw_path,
                                raw_root=raw_dir, error=exc,
                            )
                        else:
                            records.append(record)
                            vcf_path.unlink(missing_ok=True)
                            continue
                    _preserve_uncheckpointed(raw_path=raw_path, raw_root=raw_dir)
                    if len(eligible) >= marker_density:
                        run = run_currentne2(
                            binary=binary, vcf_path=vcf_path, raw_path=raw_path,
                            marker_density=marker_density, settings=settings,
                            raw_root=raw_dir,
                        )
                        result = {
                            "input_vcf_sha256": input_hash,
                            "marker_ids_sha256": marker_hash,
                            **run,
                        }
                        vcf_path.unlink(missing_ok=True)
                    execution_failure = bool(result["execution_failure_reason"])
                    state = str(result["gbf_state"])
                    outcome = "execution_failure" if execution_failure else f"empirical_{state}"
                    record = {**base, **result, "outcome_class": outcome}
                    records.append(record)
                    _atomic_json(
                        checkpoint_path,
                        _checkpoint_payload(
                            row=record, checkpoint_path=checkpoint_path,
                            raw_root=raw_dir, binary=binary, settings=settings
                        ),
                    )
    metadata = {
        "source_variant_count": n_source_variants,
        "reservoir_capacity": reservoir_capacity,
        "reservoir_seed": reservoir_seed,
        "reservoir_marker_sha256": reservoir_hash,
        "vcf_samples": len(listed),
        "population_observed_n": {pop: len(samples) for pop, samples in populations.items()},
    }
    return pd.DataFrame(records, columns=EMPIRICAL_COLUMNS), metadata


def _rate_fields(name: str, count: int, total: int) -> dict[str, object]:
    low, high = wilson_interval(count, total)
    return {
        f"n_{name}": count,
        f"{name}_rate": count / total if total else math.nan,
        f"{name}_ci_low": low,
        f"{name}_ci_high": high,
    }


def _convergence_fields(count: int, total: int) -> dict[str, object]:
    fields = _rate_fields("convergence", count, total)
    fields["n_converged"] = fields.pop("n_convergence")
    return fields


def summarize_scenarios(frame: pd.DataFrame, settings: Settings, expansion_status: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for keys, group in frame.groupby(["true_ne", "truth_class", "sample_size", "marker_density"], sort=True):
        true_ne, truth, sample_size, marker_density = keys
        total = len(group)
        failures = group["outcome_class"].eq("execution_failure")
        executed = ~failures
        intervals = group.loc[executed & group["ci_low"].notna() & group["ci_high"].notna()]
        widths = pd.to_numeric(intervals["ci_width"], errors="coerce")
        finite_widths = widths[np.isfinite(widths)]
        combined_runtime = (
            pd.to_numeric(group["runtime_seconds"], errors="coerce").fillna(0)
            + pd.to_numeric(group["simulation_runtime_seconds"], errors="coerce").fillna(0)
        )
        # pandas 3 returns an empty string for ``object``-dtype ``sum()`` on
        # an empty Series, so count booleans explicitly.  All-failure cells
        # must remain valid summary rows rather than crashing the analysis.
        coverage_count = sum(
            str(value).lower() == "true" for value in intervals["interval_covers_true"]
        )
        record: dict[str, object] = {
            "analysis_type": "scenario", "population": "", "true_ne": true_ne,
            "truth_class": truth, "sample_size": sample_size, "marker_density": marker_density,
            "reps_planned": settings.final_reps if expansion_status == "expanded" else settings.pilot_reps,
            "n_attempted": total, "n_executed": int(executed.sum()),
            **_rate_fields("execution_failure", int(failures.sum()), total),
            **_convergence_fields(int(group.loc[executed, "converged"].astype(bool).sum()), total),
            **_rate_fields("correct_confident", int(group["outcome_class"].eq("correct_confident").sum()), total),
            **_rate_fields("incorrect_confident", int(group["outcome_class"].eq("incorrect_confident").sum()), total),
            **_rate_fields("indeterminate", int(group["outcome_class"].eq("indeterminate").sum()), total),
            **_rate_fields("boundary_confident_pass", int(group["outcome_class"].eq("boundary_confident_pass").sum()), total),
            **_rate_fields("boundary_confident_fail", int(group["outcome_class"].eq("boundary_confident_fail").sum()), total),
            **_rate_fields("pass", int(group.loc[executed, "gbf_state"].eq("pass").sum()), total),
            **_rate_fields("fail", int(group.loc[executed, "gbf_state"].eq("fail").sum()), total),
            "n_intervals": len(intervals), "n_interval_covers_true": coverage_count,
            "coverage_rate": coverage_count / len(intervals) if len(intervals) else math.nan,
            "coverage_ci_low": wilson_interval(coverage_count, len(intervals))[0],
            "coverage_ci_high": wilson_interval(coverage_count, len(intervals))[1],
            "n_unbounded_ci": int(np.isinf(widths).sum()),
            "mean_ci_width": float(finite_widths.mean()) if len(finite_widths) else math.nan,
            "median_ci_width": float(finite_widths.median()) if len(finite_widths) else math.nan,
            "median_ne_point": float(pd.to_numeric(group.loc[executed, "ne_point"], errors="coerce").median()),
            "mean_runtime_seconds": float(combined_runtime.mean()),
            "total_runtime_seconds": float(combined_runtime.sum()),
            "monte_carlo_ci_pct": MC_CI_PCT, "expansion_status": expansion_status,
        }
        rows.append(record)
    return rows


def summarize_empirical(frame: pd.DataFrame, settings: Settings, expansion_status: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for keys, group in frame.groupby(["population", "sample_size", "marker_density"], sort=True):
        population, sample_size, marker_density = keys
        total = len(group)
        failures = group["outcome_class"].eq("execution_failure")
        executed = ~failures
        widths = pd.to_numeric(group.loc[executed, "ci_width"], errors="coerce")
        finite_widths = widths[np.isfinite(widths)]
        record: dict[str, object] = {
            "analysis_type": "empirical", "population": population, "true_ne": math.nan,
            "truth_class": "not_known", "sample_size": sample_size,
            "marker_density": marker_density, "reps_planned": settings.empirical_reps,
            "n_attempted": total, "n_executed": int(executed.sum()),
            **_rate_fields("execution_failure", int(failures.sum()), total),
            **_convergence_fields(int(group.loc[executed, "converged"].astype(bool).sum()), total),
            **_rate_fields("correct_confident", 0, total),
            **_rate_fields("incorrect_confident", 0, total),
            **_rate_fields("indeterminate", int(group.loc[executed, "gbf_state"].eq("indeterminate").sum()), total),
            **_rate_fields("boundary_confident_pass", 0, total),
            **_rate_fields("boundary_confident_fail", 0, total),
            **_rate_fields("pass", int(group.loc[executed, "gbf_state"].eq("pass").sum()), total),
            **_rate_fields("fail", int(group.loc[executed, "gbf_state"].eq("fail").sum()), total),
            "n_intervals": 0, "n_interval_covers_true": 0,
            "coverage_rate": math.nan, "coverage_ci_low": math.nan,
            "coverage_ci_high": math.nan, "n_unbounded_ci": int(np.isinf(widths).sum()),
            "mean_ci_width": float(finite_widths.mean()) if len(finite_widths) else math.nan,
            "median_ci_width": float(finite_widths.median()) if len(finite_widths) else math.nan,
            "median_ne_point": float(pd.to_numeric(group.loc[executed, "ne_point"], errors="coerce").median()),
            "mean_runtime_seconds": float(pd.to_numeric(group["runtime_seconds"], errors="coerce").mean()),
            "total_runtime_seconds": float(pd.to_numeric(group["runtime_seconds"], errors="coerce").sum()),
            "monte_carlo_ci_pct": MC_CI_PCT, "expansion_status": expansion_status,
        }
        rows.append(record)
    return rows


def build_summary(scenarios: pd.DataFrame, empirical: pd.DataFrame, settings: Settings,
                  expansion_status: str) -> pd.DataFrame:
    records = summarize_scenarios(scenarios, settings, expansion_status)
    records.extend(summarize_empirical(empirical, settings, expansion_status))
    return pd.DataFrame(records, columns=SUMMARY_COLUMNS)


def build_figure_values(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    scenario = summary.loc[summary["analysis_type"].eq("scenario")]
    for record in scenario.to_dict("records"):
        truth = str(record["truth_class"])
        if truth == "boundary":
            metric = "indeterminate_rate"
            target = "boundary_indeterminate"
        else:
            metric = "correct_confident_rate"
            target = "correct_confident"
        rows.append({
            "panel": "scenario_design_target", "analysis_type": "scenario",
            "population": "", "true_ne": record["true_ne"], "truth_class": truth,
            "sample_size": record["sample_size"], "marker_density": record["marker_density"],
            "metric": metric, "value": record[metric],
            "ci_low": record[f"{metric.removesuffix('_rate')}_ci_low"],
            "ci_high": record[f"{metric.removesuffix('_rate')}_ci_high"],
            "n_attempted": record["n_attempted"], "target_outcome": target,
        })
        # Preserve a mutually exclusive, exhaustive bridge to every scenario
        # outcome. Boundary truth has no correct/incorrect category: its two
        # confident directions remain explicitly visible instead.
        audit_metrics = (
            ("boundary_confident_pass_rate", "boundary_confident_fail_rate", "execution_failure_rate")
            if truth == "boundary" else
            ("incorrect_confident_rate", "indeterminate_rate", "execution_failure_rate")
        )
        for extra in audit_metrics:
            rows.append({
                "panel": "scenario_outcome_audit", "analysis_type": "scenario",
                "population": "", "true_ne": record["true_ne"], "truth_class": truth,
                "sample_size": record["sample_size"], "marker_density": record["marker_density"],
                "metric": extra, "value": record[extra],
                "ci_low": record[f"{extra.removesuffix('_rate')}_ci_low"],
                "ci_high": record[f"{extra.removesuffix('_rate')}_ci_high"],
                "n_attempted": record["n_attempted"], "target_outcome": "audit_only",
            })
    empirical = summary.loc[summary["analysis_type"].eq("empirical")]
    for record in empirical.to_dict("records"):
        for metric in ("convergence_rate", "pass_rate", "fail_rate", "indeterminate_rate", "execution_failure_rate"):
            rows.append({
                "panel": "empirical_sensitivity", "analysis_type": "empirical",
                "population": record["population"], "true_ne": math.nan,
                "truth_class": "not_known", "sample_size": record["sample_size"],
                "marker_density": record["marker_density"], "metric": metric,
                "value": record[metric],
                "ci_low": record[f"{metric.removesuffix('_rate')}_ci_low"],
                "ci_high": record[f"{metric.removesuffix('_rate')}_ci_high"],
                "n_attempted": record["n_attempted"], "target_outcome": "empirical_no_known_truth",
            })
    return pd.DataFrame(rows, columns=FIGURE_VALUE_COLUMNS)


def render_figure(values: pd.DataFrame, output: Path, marker_densities: Sequence[int],
                  sample_sizes: Sequence[int], true_ne_values: Sequence[int]) -> None:
    # Keep Matplotlib cache out of the repository/home directory in restricted runs.
    mpl_cache = Path(tempfile.gettempdir()) / "cg-matplotlib"
    mpl_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))
    import matplotlib  # noqa: WPS433
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: WPS433

    figure, axes = plt.subplots(2, len(marker_densities), figsize=(15, 8.5), constrained_layout=True)
    scenario_values = values.loc[values["panel"].eq("scenario_design_target")]
    empirical_values = values.loc[
        values["panel"].eq("empirical_sensitivity") & values["metric"].eq("convergence_rate")
    ]
    populations = sorted(empirical_values["population"].dropna().astype(str).unique())
    empirical_sample_sizes = sorted(
        pd.to_numeric(empirical_values["sample_size"], errors="coerce").dropna().astype(int).unique()
    )
    image = None
    for column, density in enumerate(marker_densities):
        top = axes[0, column]
        matrix = np.full((len(true_ne_values), len(sample_sizes)), np.nan)
        subset = scenario_values.loc[scenario_values["marker_density"].eq(density)]
        for y, ne_value in enumerate(true_ne_values):
            for x, n_value in enumerate(sample_sizes):
                match = subset.loc[
                    subset["true_ne"].eq(ne_value) & subset["sample_size"].eq(n_value), "value"
                ]
                if len(match) == 1:
                    matrix[y, x] = float(match.iloc[0])
        image = top.imshow(matrix, vmin=0, vmax=1, cmap="viridis", aspect="auto")
        top.set_title(f"Scenario · {density:,} markers")
        top.set_xticks(range(len(sample_sizes)), sample_sizes)
        top.set_yticks(range(len(true_ne_values)), true_ne_values if column == 0 else [""] * len(true_ne_values))
        top.set_xlabel("sampled individuals")
        if column == 0:
            top.set_ylabel("known true Nₑ")
        for y in range(matrix.shape[0]):
            for x in range(matrix.shape[1]):
                if np.isfinite(matrix[y, x]):
                    top.text(x, y, f"{matrix[y, x]:.2f}", ha="center", va="center",
                             color="white" if matrix[y, x] < 0.55 else "black", fontsize=8)

        bottom = axes[1, column]
        empirical_matrix = np.full((len(populations), len(empirical_sample_sizes)), np.nan)
        esub = empirical_values.loc[empirical_values["marker_density"].eq(density)]
        for y, population in enumerate(populations):
            for x, n_value in enumerate(empirical_sample_sizes):
                match = esub.loc[
                    esub["population"].eq(population) & esub["sample_size"].eq(n_value), "value"
                ]
                if len(match) == 1:
                    empirical_matrix[y, x] = float(match.iloc[0])
        bottom.imshow(empirical_matrix, vmin=0, vmax=1, cmap="magma", aspect="auto")
        bottom.set_title(f"Empirical convergence · {density:,} markers")
        bottom.set_xticks(range(len(empirical_sample_sizes)), empirical_sample_sizes)
        bottom.set_yticks(range(len(populations)), populations if column == 0 else [""] * len(populations))
        bottom.set_xlabel("downsampled individuals")
        if column == 0:
            bottom.set_ylabel("real population")
        for y in range(empirical_matrix.shape[0]):
            for x in range(empirical_matrix.shape[1]):
                if np.isfinite(empirical_matrix[y, x]):
                    bottom.text(x, y, f"{empirical_matrix[y, x]:.2f}", ha="center", va="center",
                                color="white" if empirical_matrix[y, x] < 0.65 else "black", fontsize=8)
    if image is not None:
        figure.colorbar(image, ax=axes, shrink=0.72, label="rate (Wilson intervals in table)")
    figure.suptitle(
        "Peafowl Nₑ study-design calibration\n"
        "Scenario: correct-confident rate (Nₑ≠500); Nₑ=500 row: indeterminate rate. "
        "Empirical panel has no known truth.",
        fontsize=13,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180, metadata={"Software": "CG Phase-5B deterministic plot"})
    plt.close(figure)


def write_tsv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Fifteen significant digits preserve scientific-hash round trips while
    # still avoiding binary floating-point noise in the audit tables.
    frame.to_csv(path, sep="\t", index=False, na_rep="", float_format="%.15g", lineterminator="\n")


def _inventory(paths: Iterable[Path]) -> list[dict[str, object]]:
    return [
        {"path": _display_path(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
        for path in sorted(paths, key=lambda item: item.as_posix())
        if path.is_file()
    ]


def write_cache_manifest(
    *, path: Path, raw_dir: Path, settings: Settings, binary: Path,
    config_path: Path, empirical_vcf: Path, popmap_path: Path,
    output_paths: dict[str, Path], expansion_status: str,
    scenario_rows: int, pilot_rows: int, empirical_rows: int,
) -> None:
    if path.parent.resolve() != raw_dir.resolve():
        raise ValueError("CACHE_MANIFEST.json must live directly inside the canonical raw directory")
    checkpoint_files = list((raw_dir / "checkpoints").rglob("*.json"))
    canonical_raw = [
        item for item in raw_dir.rglob("*.currentne2.txt")
        if not any(part.startswith(".") for part in item.relative_to(raw_dir).parts)
    ]
    canonical_logs = [
        item for item in raw_dir.rglob("*.currentne2.log")
        if not any(part.startswith(".") for part in item.relative_to(raw_dir).parts)
    ]
    exact_raw = list((raw_dir / ".exact_cache").rglob("*.currentne2.txt"))
    exact_logs = list((raw_dir / ".exact_cache").rglob("*.currentne2.log"))
    timing_files = list((raw_dir / ".timing_cache" / "panels").rglob("*.json"))
    grid_per_replicate = (
        len(settings.true_ne) * len(settings.sample_sizes)
        * len(settings.marker_densities)
    )
    expected_scenario_attempts = grid_per_replicate * (
        settings.final_reps + settings.pilot_reps
        if expansion_status == "expanded" else 2 * settings.pilot_reps
    )
    expected_final_scenario_rows = grid_per_replicate * (
        settings.final_reps if expansion_status == "expanded" else settings.pilot_reps
    )
    expected_pilot_rows = grid_per_replicate * 2 * settings.pilot_reps
    expected_attempts = expected_scenario_attempts + empirical_rows
    expected_panel_timings = len(settings.true_ne) * (
        settings.final_reps + settings.pilot_reps
        if expansion_status == "expanded" else 2 * settings.pilot_reps
    )
    if scenario_rows != expected_final_scenario_rows or pilot_rows != expected_pilot_rows:
        raise RuntimeError("public scenario/pilot row counts disagree with configured cache grid")
    if len(checkpoint_files) != expected_attempts:
        raise RuntimeError(
            f"checkpoint count {len(checkpoint_files)} != attempted row count {expected_attempts}"
        )
    if len(timing_files) != expected_panel_timings:
        raise RuntimeError(
            f"panel timing count {len(timing_files)} != expected {expected_panel_timings}"
        )
    timing_by_panel: dict[tuple[str, int, int], float] = {}
    for timing in timing_files:
        payload = json.loads(timing.read_text(encoding="utf-8"))
        if not (
            payload.get("cache_schema") == "phase5b-ne-design-panel-timing-v1"
            and payload.get("analysis_schema") == SCHEMA_VERSION
            and payload.get("settings_sha256") == settings_sha256(settings)
            and payload.get("binary_sha256") == sha256_file(binary)
            and payload.get("pedigree_golden_sha256") == PEDIGREE_GOLDEN_SHA256
            and math.isfinite(float(payload.get("simulation_runtime_seconds", math.nan)))
            and float(payload.get("simulation_runtime_seconds")) >= 0
        ):
            raise RuntimeError(f"invalid panel timing cache: {timing}")
        key = (
            str(payload.get("run_label")), int(payload.get("true_ne", -1)),
            int(payload.get("replicate", -1)),
        )
        expected_timing_path = (
            raw_dir / ".timing_cache" / "panels" / key[0]
            / f"ne{key[1]:04d}.r{key[2]:02d}.json"
        )
        if timing.resolve() != expected_timing_path.resolve() or key in timing_by_panel:
            raise RuntimeError(f"panel timing namespace mismatch: {timing}")
        panel_hash = str(payload.get("panel_sha256", ""))
        if len(panel_hash) != 64 or any(char not in "0123456789abcdef" for char in panel_hash):
            raise RuntimeError(f"panel timing scientific hash mismatch: {timing}")
        timing_by_panel[key] = float(payload["simulation_runtime_seconds"])

    expected_public_raw: set[Path] = set()
    expected_public_logs: set[Path] = set()
    expected_exact_raw: set[Path] = set()
    expected_exact_logs: set[Path] = set()
    input_generation_failures = 0
    missing_estimator_raw = 0
    for checkpoint in checkpoint_files:
        payload = json.loads(checkpoint.read_text(encoding="utf-8"))
        if payload.get("cache_schema") != CACHE_ROW_SCHEMA:
            raise RuntimeError(f"row-cache schema mismatch in {checkpoint}")
        if payload.get("namespace") != _checkpoint_namespace(checkpoint, raw_dir):
            raise RuntimeError(f"row-cache namespace mismatch in {checkpoint}")
        row = payload.get("row", {})
        materialization = payload.get("public_materialization", {})
        exact = payload.get("exact_execution", {})
        reason = str(row.get("execution_failure_reason") or "")
        if row.get("analysis_type") == "scenario":
            relative = checkpoint.resolve().relative_to(
                (raw_dir / "checkpoints").resolve()
            )
            if len(relative.parts) < 3 or relative.parts[0] != "scenario":
                raise RuntimeError(f"scenario checkpoint namespace malformed: {checkpoint}")
            panel_key = (
                relative.parts[1], int(row.get("true_ne", -1)),
                int(row.get("replicate", -1)),
            )
            if panel_key not in timing_by_panel:
                raise RuntimeError(f"scenario row lacks panel timing: {checkpoint}")
            expected_share = timing_by_panel[panel_key] / (
                len(settings.sample_sizes) * len(settings.marker_densities)
            )
            if not math.isclose(
                float(row.get("simulation_runtime_seconds", math.nan)),
                expected_share, rel_tol=0, abs_tol=1e-15,
            ):
                raise RuntimeError(f"scenario row/panel timing mismatch: {checkpoint}")
        if reason == "input_generation_error":
            input_generation_failures += 1
            if any(bool(materialization.get(f"{kind}_present")) for kind in ("raw", "log")):
                raise RuntimeError(f"input-generation failure has public estimator artifact: {checkpoint}")
            if any(bool(exact.get(f"{kind}_present")) for kind in ("raw", "log")):
                raise RuntimeError(f"input-generation failure has exact estimator artifact: {checkpoint}")
            continue
        if not bool(materialization.get("log_present")) or not bool(exact.get("log_present")):
            raise RuntimeError(f"estimator attempt lacks durable log contract: {checkpoint}")
        public_log = _resolve(str(row.get("log_path", ""))).resolve()
        exact_log = _resolve(str(exact.get("log_path", ""))).resolve()
        expected_public_logs.add(public_log)
        expected_exact_logs.add(exact_log)
        public_raw_present = bool(materialization.get("raw_present"))
        exact_raw_present = bool(exact.get("raw_present"))
        if public_raw_present != exact_raw_present:
            raise RuntimeError(f"public/exact raw presence differs: {checkpoint}")
        if public_raw_present:
            expected_public_raw.add(_resolve(str(row.get("raw_output_path", ""))).resolve())
            expected_exact_raw.add(_resolve(str(exact.get("raw_path", ""))).resolve())
        else:
            missing_estimator_raw += 1

    actual_sets = {
        "canonical raw": {item.resolve() for item in canonical_raw},
        "canonical log": {item.resolve() for item in canonical_logs},
        "exact raw": {item.resolve() for item in exact_raw},
        "exact log": {item.resolve() for item in exact_logs},
    }
    expected_sets = {
        "canonical raw": expected_public_raw,
        "canonical log": expected_public_logs,
        "exact raw": expected_exact_raw,
        "exact log": expected_exact_logs,
    }
    for label, actual in actual_sets.items():
        expected_set = expected_sets[label]
        if actual != expected_set:
            missing = sorted(str(item) for item in expected_set - actual)[:3]
            extra = sorted(str(item) for item in actual - expected_set)[:3]
            raise RuntimeError(
                f"{label} inventory differs from row contracts; missing={missing}, extra={extra}"
            )
    manifest = {
        "cache_schema": CACHE_MANIFEST_SCHEMA,
        "analysis_schema": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "written_atomically_last": True,
        "settings_sha256": settings_sha256(settings),
        "binary": {"path": _display_path(binary), "sha256": sha256_file(binary)},
        "pedigree_golden_sha256": PEDIGREE_GOLDEN_SHA256,
        "inputs": {
            "config_sha256": sha256_file(config_path),
            "empirical_vcf_sha256": sha256_file(empirical_vcf),
            "popmap_sha256": sha256_file(popmap_path),
        },
        "expansion_status": expansion_status,
        "row_counts": {
            "scenario": scenario_rows, "pilot_audit": pilot_rows,
            "empirical": empirical_rows, "checkpoints": len(checkpoint_files),
            "panel_timings": len(timing_files),
            "expected_panel_timings": expected_panel_timings,
            "expected_attempts": expected_attempts,
            "expected_scenario_attempts": expected_scenario_attempts,
            "input_generation_failures": input_generation_failures,
            "estimator_attempts": expected_attempts - input_generation_failures,
            "estimator_attempts_without_raw": missing_estimator_raw,
            "canonical_raw": len(canonical_raw), "canonical_logs": len(canonical_logs),
            "exact_raw": len(exact_raw), "exact_logs": len(exact_logs),
            "expected_materialized_raw": len(expected_public_raw),
            "expected_materialized_logs": len(expected_public_logs),
        },
        "outputs": {
            label: {"path": _display_path(output), "sha256": sha256_file(output)}
            for label, output in output_paths.items() if output.is_file()
        },
        "checkpoints": _inventory(checkpoint_files),
        "panel_timings": _inventory(timing_files),
        "canonical_raw": _inventory(canonical_raw),
        "canonical_logs": _inventory(canonical_logs),
        "exact_raw": _inventory(exact_raw),
        "exact_logs": _inventory(exact_logs),
    }
    _atomic_json(path, manifest)


def _versions() -> dict[str, str]:
    versions = {
        "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
    }
    try:
        import matplotlib
        versions["matplotlib"] = matplotlib.__version__
    except Exception:
        versions["matplotlib"] = "unavailable"
    return versions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--empirical-vcf", default="results/qc/setA.standard.vcf.gz")
    parser.add_argument("--popmap", default="config/peafowl_popmap.tsv")
    parser.add_argument("--currentne2", default="tools/currentNe2/currentne2")
    parser.add_argument("--bcftools", default=None)
    parser.add_argument("--out-replicates", default="results/tables/peafowl_ne_design_replicates.tsv")
    parser.add_argument("--out-pilot", default="results/tables/peafowl_ne_design_pilot.tsv")
    parser.add_argument("--out-summary", default="results/tables/peafowl_ne_design_summary.tsv")
    parser.add_argument("--out-empirical", default="results/tables/peafowl_ne_design_empirical.tsv")
    parser.add_argument("--out-figure-values", default="results/tables/peafowl_ne_design_figure_values.tsv")
    parser.add_argument("--out-figure", default="results/figures/peafowl_ne_design.png")
    parser.add_argument("--out-provenance", default="results/provenance/peafowl_ne_design.json")
    parser.add_argument("--raw-dir", default="results/ne/design")
    parser.add_argument("--cache-manifest", default="results/ne/design/CACHE_MANIFEST.json")
    parser.add_argument("--pilot-only", action="store_true", help="retain pilot by request; never used by the final gate")
    parser.add_argument("--skip-empirical", action="store_true", help="diagnostic-only; final validator rejects this")
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument(
        "--cache-self-check", action="store_true",
        help="exercise restart/rematerialization/corruption contracts on a tiny local fixture",
    )
    return parser.parse_args()


def self_check() -> None:
    assert truth_class(100) == "below" and truth_class(500) == "boundary" and truth_class(1000) == "above"
    assert classify_scenario_outcome("below", "fail", False) == "correct_confident"
    assert classify_scenario_outcome("above", "fail", False) == "incorrect_confident"
    assert classify_scenario_outcome("boundary", "pass", False) == "boundary_confident_pass"
    low, high = wilson_interval(0, 2)
    assert 0 <= low <= high <= 1
    convergence = _convergence_fields(3, 12)
    assert convergence["n_converged"] == 3
    assert "n_convergence" not in convergence
    assert not _binding_values_match("seed", 2**60, 2**60 + 1)
    sample = pd.DataFrame([
        {column: (1 if column in {"replicate", "true_ne", "sample_size", "marker_density", "seed"} else "")
         for column in SCENARIO_COLUMNS}
    ])
    assert scientific_hash(sample, PILOT_HASH_COLUMNS) == scientific_hash(sample.copy(), PILOT_HASH_COLUMNS)
    golden_settings = Settings(
        seed=1302, true_ne=(20,), sample_sizes=(5, 10), marker_densities=(64,),
        pilot_reps=1, final_reps=2, empirical_reps=1, simulation_generations=4,
        initial_maf_low=0.1, initial_maf_high=0.5, currentne2_threads=1,
        run_timeout_seconds=30, pilot_expansion_max_seconds=300,
        genome_size_morgans=32, ci_pct=90, resolution_truths=(250, 1000),
        resolution_min_correct_confident_ci_low=0.7,
        resolution_max_incorrect_confident_ci_high=0.25,
    )
    panel = simulate_nested_panel(settings=golden_settings, true_ne=20, replicate=3)
    genotypes, chromosomes, map_morgans, marker_ids, seed, attempt, loci, panel_seed = panel
    assert len(set(chromosomes.tolist())) == 32
    assert panel_fingerprint(
        genotypes, chromosomes, map_morgans, marker_ids, seed, attempt, loci, panel_seed
    ) == PEDIGREE_GOLDEN_SHA256
    # Exactly 80% called must be excluded; >80% remains eligible.
    exact_boundary = EmpiricalVariant("1", 1, "A", "G", ("0/0", "0/1", "1/1", "0/0", "./."))
    assert not _eligible_empirical_variant(exact_boundary, range(5))
    print("peafowl_ne_design self-check: OK")


def cache_self_check(binary: Path) -> None:
    settings = Settings(
        seed=1302, true_ne=(20,), sample_sizes=(5, 10), marker_densities=(64,),
        pilot_reps=1, final_reps=2, empirical_reps=1, simulation_generations=4,
        initial_maf_low=0.1, initial_maf_high=0.5, currentne2_threads=1,
        run_timeout_seconds=30, pilot_expansion_max_seconds=300,
        genome_size_morgans=32, ci_pct=90, resolution_truths=(250, 1000),
        resolution_min_correct_confident_ci_low=0.7,
        resolution_max_incorrect_confident_ci_high=0.25,
    )
    with tempfile.TemporaryDirectory(prefix=".ne-cache-selfcheck-", dir=ROOT) as temporary:
        fixture = Path(temporary)
        raw_dir, work_dir = fixture / "raw", fixture / "work"
        arguments = dict(
            settings=settings, binary=binary, raw_dir=raw_dir, work_dir=work_dir,
            replicates=range(1, 2), run_label="pilot_primary",
            pilot_member=True, expansion_status="pilot_pending",
        )
        first, _ = run_scenario_batch(**arguments)
        resumed, _ = run_scenario_batch(**arguments)
        assert first["runtime_seconds"].tolist() == resumed["runtime_seconds"].tolist()
        assert first["simulation_runtime_seconds"].tolist() == resumed[
            "simulation_runtime_seconds"
        ].tolist()

        public_raw = next((raw_dir / "scenario" / "pilot_primary").glob("*.currentne2.txt"))
        public_log = public_raw.with_suffix(".log")
        raw_hash, log_hash = sha256_file(public_raw), sha256_file(public_log)
        public_raw.unlink()
        public_log.unlink()
        rematerialized, _ = run_scenario_batch(**arguments)
        assert sha256_file(public_raw) == raw_hash and sha256_file(public_log) == log_hash
        assert rematerialized["runtime_seconds"].tolist() == first["runtime_seconds"].tolist()

        checkpoint_dir = raw_dir / "checkpoints" / "scenario" / "pilot_primary"
        checkpoint = sorted(checkpoint_dir.glob("*.json"))[0]
        payload = json.loads(checkpoint.read_text(encoding="utf-8"))
        payload["row"]["seed"] += 1
        _atomic_json(checkpoint, payload)
        before = len(list((raw_dir / ".binding_mismatch").rglob("*.mismatch")))
        repaired, _ = run_scenario_batch(**arguments)
        after = len(list((raw_dir / ".binding_mismatch").rglob("*.mismatch")))
        assert after > before and set(repaired["seed"]) == set(first["seed"])

        stable_simulation = repaired["simulation_runtime_seconds"].tolist()
        sorted(checkpoint_dir.glob("*.json"))[0].unlink()
        partial, _ = run_scenario_batch(**arguments)
        assert partial["simulation_runtime_seconds"].tolist() == stable_simulation

        repeat_arguments = {**arguments, "run_label": "pilot_repeat"}
        run_scenario_batch(**repeat_arguments)
        primary_checkpoint = sorted(checkpoint_dir.glob("*.json"))[0]
        repeat_checkpoint = sorted(
            (raw_dir / "checkpoints" / "scenario" / "pilot_repeat").glob("*.json")
        )[0]
        shutil.copy2(primary_checkpoint, repeat_checkpoint)
        before = len(list((raw_dir / ".binding_mismatch").rglob("*.mismatch")))
        run_scenario_batch(**repeat_arguments)
        assert len(list((raw_dir / ".binding_mismatch").rglob("*.mismatch"))) > before

        failure_arguments = {
            **arguments, "binary": Path("/usr/bin/false"),
            "raw_dir": fixture / "failure_raw", "work_dir": fixture / "failure_work",
        }
        failure_first, _ = run_scenario_batch(**failure_arguments)
        failure_resumed, _ = run_scenario_batch(**failure_arguments)
        assert failure_first["runtime_seconds"].tolist() == failure_resumed[
            "runtime_seconds"
        ].tolist()
        assert failure_first["raw_output_sha256"].eq("").all()
        assert failure_first["log_sha256"].ne("").all()
        assert failure_first["n_ind"].eq(-1).all()
    print("peafowl_ne_design cache self-check: OK")


def main() -> None:
    args = parse_args()
    if args.self_check:
        self_check()
        return
    if args.cache_self_check:
        cache_self_check(locate_executable(args.currentne2, "currentne2"))
        return

    config_path = _resolve(args.config)
    empirical_vcf = _resolve(args.empirical_vcf)
    popmap_path = _resolve(args.popmap)
    binary = locate_executable(args.currentne2, "currentne2")
    bcftools = locate_executable(args.bcftools, "bcftools")
    settings = load_settings(config_path)
    raw_dir = _resolve(args.raw_dir)
    cache_manifest = _resolve(args.cache_manifest)
    output_paths = {
        "replicates": _resolve(args.out_replicates), "pilot": _resolve(args.out_pilot),
        "summary": _resolve(args.out_summary), "empirical": _resolve(args.out_empirical),
        "figure_values": _resolve(args.out_figure_values), "figure": _resolve(args.out_figure),
        "provenance": _resolve(args.out_provenance),
    }

    run_started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="cg-ne-" + "design-") as temporary:
        work_dir = Path(temporary)
        primary, pilot_wall = run_scenario_batch(
            settings=settings, binary=binary, raw_dir=raw_dir, work_dir=work_dir,
            replicates=range(1, settings.pilot_reps + 1), run_label="pilot_primary",
            pilot_member=True, expansion_status="pilot_pending",
        )
        repeat, repeat_wall = run_scenario_batch(
            settings=settings, binary=binary, raw_dir=raw_dir, work_dir=work_dir,
            replicates=range(1, settings.pilot_reps + 1), run_label="pilot_repeat",
            pilot_member=True, expansion_status="pilot_repeat",
        )
        primary_hash = scientific_hash(primary, PILOT_HASH_COLUMNS)
        repeat_hash = scientific_hash(repeat, PILOT_HASH_COLUMNS)
        repeatability_match = primary_hash == repeat_hash
        # Use preserved per-attempt estimator runtimes, not this invocation's
        # cache-hit wall clock, so a resumed pilot makes the identical gate
        # decision. Preserved pedigree-simulation timing is included once per
        # true-Ne x replicate panel; transient cache-validation replay time and
        # VCF serialization overhead are not projected.
        primary_currentne2_seconds = float(
            pd.to_numeric(primary["runtime_seconds"], errors="coerce").fillna(0).sum()
        )
        primary_simulation_seconds = float(
            pd.to_numeric(
                primary["simulation_runtime_seconds"], errors="coerce"
            ).fillna(0).sum()
        )
        primary_projectable_seconds = (
            primary_simulation_seconds + primary_currentne2_seconds
        )
        projected_full_seconds = (
            primary_projectable_seconds * settings.final_reps / settings.pilot_reps
        )
        runtime_pass = projected_full_seconds <= settings.pilot_expansion_max_seconds
        pilot_integrity_pass = all(
            bool(
                frame["execution_failure_reason"].eq("").all()
                and pd.to_numeric(frame["n_ind"], errors="coerce").eq(
                    pd.to_numeric(frame["sample_size"], errors="coerce")
                ).all()
                and pd.to_numeric(frame["n_snps"], errors="coerce").eq(
                    pd.to_numeric(frame["marker_density"], errors="coerce")
                ).all()
            )
            for frame in (primary, repeat)
        )
        attainable_correct_low = wilson_interval(settings.final_reps, settings.final_reps)[0]
        attainable_incorrect_high = wilson_interval(0, settings.final_reps)[1]
        uncertainty_attainable = bool(
            attainable_correct_low >= settings.resolution_min_correct_confident_ci_low
            and attainable_incorrect_high <= settings.resolution_max_incorrect_confident_ci_high
        )
        expand = bool(
            runtime_pass and repeatability_match and pilot_integrity_pass
            and uncertainty_attainable and not args.pilot_only
        )
        expansion_status = "expanded" if expand else "pilot_only"
        expansion_reason = (
            "outcome-blind pilot gates passed: repeat hash, integrity, runtime, Wilson attainability"
            if expand else (
                "explicit --pilot-only diagnostic request" if args.pilot_only else
                "pilot repeated scientific hashes differ" if not repeatability_match else
                "pilot execution/parser/analyzed-dimension integrity failed" if not pilot_integrity_pass else
                "final replicate count cannot attain predeclared Wilson bounds" if not uncertainty_attainable else
                "pilot-projected full runtime exceeds configured limit"
            )
        )
        primary["expansion_status"] = expansion_status
        pilot = pd.concat([
            primary.assign(pilot_run="primary", pilot_batch_hash=primary_hash,
                           repeatability_match=repeatability_match),
            repeat.assign(pilot_run="repeat", pilot_batch_hash=repeat_hash,
                          repeatability_match=repeatability_match),
        ], ignore_index=True)
        if expand and settings.final_reps > settings.pilot_reps:
            expanded, expansion_wall = run_scenario_batch(
                settings=settings, binary=binary, raw_dir=raw_dir, work_dir=work_dir,
                replicates=range(settings.pilot_reps + 1, settings.final_reps + 1),
                run_label="expanded", pilot_member=False, expansion_status=expansion_status,
            )
            scenarios = pd.concat([primary, expanded], ignore_index=True)
        else:
            expansion_wall = 0.0
            scenarios = primary

        if args.skip_empirical:
            empirical = pd.DataFrame(columns=EMPIRICAL_COLUMNS)
            empirical_meta: dict[str, object] = {"skipped": True}
            empirical_wall = 0.0
        else:
            empirical_started = time.perf_counter()
            empirical, empirical_meta = run_empirical(
                settings=settings, binary=binary, bcftools=bcftools,
                empirical_vcf=empirical_vcf, popmap_path=popmap_path,
                raw_dir=raw_dir, work_dir=work_dir,
            )
            empirical_wall = time.perf_counter() - empirical_started

    reconcile_cache_namespace(
        raw_root=raw_dir, settings=settings, expansion_status=expansion_status,
        empirical=empirical,
    )
    summary = build_summary(scenarios, empirical, settings, expansion_status)
    figure_values = build_figure_values(summary)
    render_figure(
        figure_values, output_paths["figure"], settings.marker_densities,
        settings.sample_sizes, settings.true_ne,
    )
    # Pilot includes audit-only columns after the fixed scenario schema.
    write_tsv(scenarios[SCENARIO_COLUMNS], output_paths["replicates"])
    write_tsv(pilot[SCENARIO_COLUMNS + ["pilot_run", "pilot_batch_hash", "repeatability_match"]], output_paths["pilot"])
    write_tsv(empirical[EMPIRICAL_COLUMNS], output_paths["empirical"])
    write_tsv(summary[SUMMARY_COLUMNS], output_paths["summary"])
    write_tsv(figure_values[FIGURE_VALUE_COLUMNS], output_paths["figure_values"])

    pilot_max_halfwidth = max(
        wilson_interval(successes, settings.pilot_reps)[1] - successes / settings.pilot_reps
        for successes in range(settings.pilot_reps + 1)
    )
    final_max_halfwidth = max(
        wilson_interval(successes, settings.final_reps)[1] - successes / settings.final_reps
        for successes in range(settings.final_reps + 1)
    )
    provenance = {
        "schema_version": SCHEMA_VERSION,
        "analysis_id": "peafowl_ne_sample_design_calibration",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "interpretation": (
            "Scenario-based study-design calibration plus bounded empirical sensitivity; "
            "not a guarantee that an exact real peafowl sample size resolves N_e>500."
        ),
        "settings": asdict(settings),
        "threshold": {"value": TRUTH_THRESHOLD, "operator": ">", "boundary_handling": (
            "true_Ne=500 is boundary; confident pass/fail are reported separately and never scored correct/incorrect"
        )},
        "simulation": {
            "model": (
                "explicit neutral diploid Wright-Fisher H[N,2,L] pedigree; each gamete chooses "
                "one parental individual genome-wide, with Mendelian Haldane recombination on "
                "32 one-Morgan chromosomes and independent chromosome assortment"
            ),
            "generations": settings.simulation_generations,
            "initial_maf": [settings.initial_maf_low, settings.initial_maf_high],
            "map": (
                "candidate loci evenly centred on each 1-M chromosome; adjacent recombination "
                "fraction r=(1-exp(-2d))/2; selected loci retain original chromosome/map coordinate"
            ),
            "cross_chromosome_initial_ld_residual": f"2^-{settings.simulation_generations}",
            "nested_design": "individual samples and marker panels are nested within true-Ne x replicate",
            "ascertainment": (
                "candidate neutral loci retained when polymorphic in the smallest nested sample, "
                "so configured marker density equals currentNe2 analyzed density"
            ),
            "limitations": [
                "no mutation, selection, migration, population structure, or demographic change",
                "one-Morgan evenly spaced chromosome maps are transparent calibration assumptions, not a peafowl map",
                "whole-genome fallback depends on the simplified within-chromosome map; ne_basis is retained per row",
                "pedigree scenarios calibrate this estimator/decision pipeline, not peafowl history",
            ],
        },
        "empirical": {
            **empirical_meta,
            "scope": "standard Set-A populations, n=5 through observed n only",
            "replicates": settings.empirical_reps,
            "truth": "unknown; empirical rows are never scored correct/incorrect",
            "uncertainty_caveat": (
                "At observed n the only individual subset repeats across six marker panels; other "
                "subsets overlap. Empirical Wilson intervals describe seeded subset/marker-panel "
                "sensitivity, not independent biological-sampling uncertainty."
            ),
        },
        "currentne2": {
            "binary": _display_path(binary), "sha256": sha256_file(binary),
            "threads": settings.currentne2_threads, "timeout_seconds": settings.run_timeout_seconds,
            "genome_size_morgans": settings.genome_size_morgans,
            "parser": "scripts/python/currentne2_parse.py cross-chromosome headline + whole-genome fallback",
            "decision_function": "currentne2_parse.gbf_state with 90% CI and N_e>500",
        },
        "inputs": {
            "config": _display_path(config_path), "config_sha256": sha256_file(config_path),
            "empirical_vcf": _display_path(empirical_vcf),
            "empirical_vcf_sha256": sha256_file(empirical_vcf) if empirical_vcf.is_file() else "",
            "popmap": _display_path(popmap_path), "popmap_sha256": sha256_file(popmap_path),
        },
        "pilot": {
            "primary_scientific_sha256": primary_hash,
            "repeat_scientific_sha256": repeat_hash,
            "repeatability_match": repeatability_match,
            "scientific_hash_excludes": [
                "runtime_seconds", "simulation_runtime_seconds", "command/path fields",
                "raw/log hashes containing runtime telemetry",
            ],
            "primary_wall_seconds": pilot_wall, "repeat_wall_seconds": repeat_wall,
            "primary_currentne2_seconds": primary_currentne2_seconds,
            "primary_simulation_seconds": primary_simulation_seconds,
            "primary_projectable_seconds": primary_projectable_seconds,
            "projected_full_seconds": projected_full_seconds,
            "runtime_projection_metric": (
                "(sum of preserved primary currentNe2 row runtimes + sum of preserved "
                "per-row amortized pedigree-simulation runtimes) * final_reps/pilot_reps; "
                "simulation wall time is divided by the configured sample-size x marker-density "
                "cells so each true-Ne x replicate panel is counted exactly once; cache-invariant"
            ),
            "configured_expansion_max_seconds": settings.pilot_expansion_max_seconds,
            "runtime_gate_pass": runtime_pass, "expansion_status": expansion_status,
            "integrity_gate_pass": pilot_integrity_pass,
            "wilson_attainability_gate_pass": uncertainty_attainable,
            "attainable_correct_confident_ci_low": attainable_correct_low,
            "attainable_incorrect_confident_ci_high": attainable_incorrect_high,
            "gate_is_outcome_blind": True,
            "expansion_reason": expansion_reason,
            "pilot_max_wilson_halfwidth": pilot_max_halfwidth,
            "final_max_wilson_halfwidth": final_max_halfwidth,
            "monte_carlo_ci_pct": MC_CI_PCT,
        },
        "runtime": {
            "expanded_batch_wall_seconds": expansion_wall,
            "empirical_wall_seconds": empirical_wall,
            "total_wall_seconds": time.perf_counter() - run_started,
        },
        "scientific_hashes": {
            "scenario_runtime_excluded_sha256": scientific_hash(scenarios, PILOT_HASH_COLUMNS),
            "empirical_runtime_excluded_sha256": scientific_hash(
                empirical.assign(
                    scenario_id=empirical.get("empirical_id", pd.Series(dtype=str)),
                    true_ne="", truth_class="", simulation_generations="",
                    simulation_attempt="", candidate_loci="", panel_seed="",
                    initial_maf_low="", initial_maf_high="", interval_covers_true="",
                    pilot_member="", expansion_status="",
                ),
                PILOT_HASH_COLUMNS,
            ) if len(empirical) else "",
        },
        "outcomes": {
            "scenario_rows": len(scenarios), "empirical_rows": len(empirical),
            "scenario_outcome_counts": scenarios["outcome_class"].value_counts().sort_index().to_dict(),
            "empirical_outcome_counts": empirical["outcome_class"].value_counts().sort_index().to_dict(),
        },
        "software": _versions(),
        "outputs": {
            label: {"path": _display_path(path), "sha256": sha256_file(path)}
            for label, path in output_paths.items() if label != "provenance" and path.is_file()
        },
        "raw_outputs": {
            "directory": _display_path(raw_dir),
            "canonical_currentne2_files": len([
                path for path in raw_dir.rglob("*.currentne2.txt")
                if ".exact_cache" not in path.parts
            ]) if raw_dir.exists() else 0,
            "exact_cache_currentne2_files": len([
                path for path in raw_dir.rglob("*.currentne2.txt")
                if ".exact_cache" in path.parts
            ]) if raw_dir.exists() else 0,
            "exact_cache_scope": "ignored local execution audit; public raw/log copies are path-sanitized",
        },
        "cache": {
            "manifest": _display_path(cache_manifest),
            "schema": CACHE_MANIFEST_SCHEMA,
            "written_atomically_last": True,
            "checkpoint_directory": _display_path(raw_dir / "checkpoints"),
            "exact_execution_directory": _display_path(raw_dir / ".exact_cache"),
        },
    }
    output_paths["provenance"].parent.mkdir(parents=True, exist_ok=True)
    output_paths["provenance"].write_text(
        json.dumps(provenance, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    write_cache_manifest(
        path=cache_manifest, raw_dir=raw_dir, settings=settings, binary=binary,
        config_path=config_path, empirical_vcf=empirical_vcf, popmap_path=popmap_path,
        output_paths=output_paths, expansion_status=expansion_status,
        scenario_rows=len(scenarios), pilot_rows=len(pilot), empirical_rows=len(empirical),
    )
    print(
        f"Peafowl N_e design: {len(scenarios)} scenario rows, {len(empirical)} empirical rows; "
        f"pilot repeatability={repeatability_match}; expansion={expansion_status}; "
        f"projected={projected_full_seconds:.2f}s <= {settings.pilot_expansion_max_seconds:.2f}s"
    )


if __name__ == "__main__":
    main()
