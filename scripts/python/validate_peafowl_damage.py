#!/usr/bin/env python3
"""Validate the Phase-5B peafowl damage-aware falsification artifacts.

The validator deliberately reimplements VCF record classification, block-point
estimation, seeded chromosome-block bootstrap intervals, exact allocation
enumeration, and decision logic instead of importing the analysis module.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import gzip
import hashlib
from itertools import combinations
import json
import math
from pathlib import Path
import re
from typing import Sequence

import numpy as np
import pandas as pd
import yaml


METRICS = ("pi", "Ho", "He", "allelic_richness")
VARIANT_SETS = ("all_snp", "transversion_only")
EXPECTED_CELL_ORDER = tuple(
    (variant_set, metric)
    for variant_set in VARIANT_SETS
    for metric in METRICS
)
METRIC_BASIS = {
    "pi": "raw_comparative",
    "Ho": "normalized_comparative",
    "He": "normalized_comparative",
    "allelic_richness": "normalized_comparative",
}
METRIC_SEED_CODE = {"pi": 11, "Ho": 12, "He": 13, "allelic_richness": 14}
VARIANT_SEED_CODE = {"all_snp": 0, "transversion_only": 1000}
LEAF_CLASSES = ("transition", "transversion", "mnv", "indel", "multiallelic", "other")
OTHER_CLASSES = ("mnv", "indel", "multiallelic", "other")

DEFAULTS = {
    "effects": "results/tables/peafowl_damage_effects.tsv",
    "permutations": "results/tables/peafowl_damage_permutations.tsv",
    "influence": "results/tables/peafowl_damage_influence.tsv",
    "blocks": "results/tables/peafowl_damage_blocks.tsv",
    "classification": "results/tables/peafowl_damage_classification.tsv",
    "figure_values": "results/tables/peafowl_damage_figure_values.tsv",
    "figure": "results/figures/peafowl_damage_falsification.png",
    "provenance": "results/provenance/peafowl_damage.json",
    "out_tsv": "results/tables/validation_peafowl_damage.tsv",
    "out_md": "results/PEAFOWL_DAMAGE_VALIDATION.md",
}

EFFECT_COLUMNS = {
    "analysis_id", "variant_set", "metric", "basis", "museum_n", "modern_n",
    "rarefy_n", "n_sites", "opportunity_bp", "museum_value", "modern_value",
    "effect_museum_minus_modern", "ci_pct", "ci_low", "ci_high",
    "bootstrap_reps", "bootstrap_seed", "direction",
    "exact_permutation_p_two_sided", "exact_permutation_percentile",
    "n_exact_allocations", "equal_n_same_direction_n", "equal_n_cases_n",
    "leave_one_same_direction_n", "leave_one_cases_n", "equal_n_effect_min",
    "equal_n_effect_max", "leave_one_effect_min", "leave_one_effect_max",
    "geographic_mismatch_caveat", "same_direction_all_snp_vs_transversion",
    "museum_higher_concordant_metrics_n", "supports_temporal_erosion_upgrade",
}
PERMUTATION_COLUMNS = {
    "allocation_id", "museum_samples", "modern_samples", "is_observed_allocation",
    "variant_set", "metric", "basis", "museum_n", "modern_n", "rarefy_n",
    "n_sites", "museum_value", "modern_value", "effect_museum_minus_modern",
    "direction",
}
INFLUENCE_COLUMNS = {
    "case_id", "case_type", "left_out_sample", "left_out_group", "museum_samples",
    "modern_samples", "museum_n", "modern_n", "rarefy_n", "variant_set",
    "metric", "basis", "n_sites", "museum_value", "modern_value",
    "effect_museum_minus_modern", "direction", "same_direction_as_baseline",
}
BLOCK_COLUMNS = {
    "basis", "variant_set", "metric", "chrom", "block_index", "block_start_bp",
    "block_end_bp", "opportunity_bp", "n_sites", "museum_sum", "modern_sum",
    "museum_n", "modern_n", "rarefy_n", "denominator",
}
CLASSIFICATION_COLUMNS = {
    "basis", "input_path", "variant_class", "n_records", "n_complete_11",
    "n_incomplete_11", "used_all_snp_records", "used_transversion_records",
    "n_samples", "n_contigs_in_header", "genomic_opportunity_bp",
}
FIGURE_VALUE_COLUMNS = {
    "panel", "series_id", "case_id", "case_type", "variant_set", "metric",
    "x_order", "label", "estimate", "ci_low", "ci_high",
    "display_effect_pct_of_modern", "display_ci_low_pct_of_modern",
    "display_ci_high_pct_of_modern",
}


@dataclass(frozen=True)
class VCFInspection:
    samples: tuple[str, ...]
    contig_lengths: dict[str, int]
    class_counts: dict[str, int]
    complete_counts: dict[str, int]
    records_outside_allowed_contigs: int


def open_text(path: str):
    return gzip.open(path, "rt") if str(path).endswith(".gz") else open(path, "rt")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_autosomes(path: str) -> list[str]:
    text = Path(path).read_text(encoding="utf-8")
    return [token.strip() for token in text.replace("\n", ",").split(",") if token.strip()]


def variant_class(ref: str, alt: str, transition_pairs: set[str]) -> str:
    ref = ref.upper()
    alt = alt.upper()
    if "," in alt:
        return "multiallelic"
    canonical = set("ACGT")
    if len(ref) == 1 and len(alt) == 1 and ref in canonical and alt in canonical:
        return "transition" if f"{ref}>{alt}" in transition_pairs else "transversion"
    if len(ref) == len(alt) and len(ref) > 1 and set(ref + alt) <= canonical:
        return "mnv"
    if ref and alt and not alt.startswith("<") and "*" not in alt and len(ref) != len(alt):
        return "indel"
    return "other"


def complete_diploid_call(fmt: str, sample_fields: Sequence[str], biallelic: bool) -> bool:
    keys = fmt.split(":")
    if "GT" not in keys:
        return False
    gt_index = keys.index("GT")
    for field in sample_fields:
        values = field.split(":")
        if gt_index >= len(values):
            return False
        alleles = values[gt_index].replace("|", "/").split("/")
        if len(alleles) != 2 or any(a == "." or not a.isdigit() for a in alleles):
            return False
        if biallelic and any(int(a) not in (0, 1) for a in alleles):
            return False
    return True


def inspect_vcf(
    path: str,
    expected_samples: Sequence[str],
    transition_pairs: set[str],
    allowed_contigs: set[str] | None = None,
) -> VCFInspection:
    contig_lengths: dict[str, int] = {}
    class_counts: Counter[str] = Counter()
    complete_counts: Counter[str] = Counter()
    vcf_samples: list[str] = []
    sample_indices: list[int] | None = None
    outside = 0
    with open_text(path) as handle:
        for line in handle:
            if line.startswith("##contig="):
                name_match = re.search(r"(?:<|,)ID=([^,>]+)", line)
                length_match = re.search(r"(?:<|,)length=([0-9]+)", line)
                if name_match and length_match:
                    name = name_match.group(1)
                    if name in contig_lengths:
                        raise ValueError(f"duplicate contig in {path}: {name}")
                    contig_lengths[name] = int(length_match.group(1))
                continue
            if line.startswith("##"):
                continue
            if line.startswith("#CHROM"):
                vcf_samples = line.rstrip("\n").split("\t")[9:]
                if len(vcf_samples) != len(expected_samples) or set(vcf_samples) != set(expected_samples):
                    raise ValueError(
                        f"VCF sample mismatch for {path}: found={vcf_samples}, expected={list(expected_samples)}"
                    )
                sample_indices = [vcf_samples.index(sample) for sample in expected_samples]
                continue
            if line.startswith("#") or not line.strip():
                continue
            if sample_indices is None:
                raise ValueError(f"missing #CHROM header before records in {path}")
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 9 + len(vcf_samples):
                raise ValueError(f"malformed record in {path}")
            chrom, ref, alt = fields[0], fields[3], fields[4]
            if chrom not in contig_lengths:
                raise ValueError(f"record contig lacks length in {path}: {chrom}")
            if allowed_contigs is not None and chrom not in allowed_contigs:
                outside += 1
            cls = variant_class(ref, alt, transition_pairs)
            class_counts[cls] += 1
            ordered = [fields[9 + index] for index in sample_indices]
            if complete_diploid_call(
                fields[8], ordered, biallelic=cls in {"transition", "transversion"}
            ):
                complete_counts[cls] += 1
    if sample_indices is None or not contig_lengths:
        raise ValueError(f"incomplete VCF metadata in {path}")
    return VCFInspection(
        samples=tuple(vcf_samples),
        contig_lengths=contig_lengths,
        class_counts=dict(class_counts),
        complete_counts=dict(complete_counts),
        records_outside_allowed_contigs=outside,
    )


def as_bool(value: object) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise ValueError(f"not a boolean: {value!r}")


def direction(value: float, tolerance: float = 1e-15) -> str:
    if value > tolerance:
        return "museum_higher"
    if value < -tolerance:
        return "modern_higher"
    return "equal"


def close(left: float, right: float) -> bool:
    return bool(np.isclose(float(left), float(right), rtol=1e-10, atol=1e-15))


def block_point(frame: pd.DataFrame, metric: str) -> tuple[float, float, float]:
    denominator = (
        float(frame["opportunity_bp"].sum())
        if metric == "pi"
        else float(frame["n_sites"].sum())
    )
    museum = float(frame["museum_sum"].sum()) / denominator
    modern = float(frame["modern_sum"].sum()) / denominator
    return museum, modern, museum - modern


def bootstrap_effects(frame: pd.DataFrame, metric: str, reps: int, seed: int) -> np.ndarray:
    groups = []
    ordered = frame.sort_values(["chrom", "block_index"])
    for _chrom, group in ordered.groupby("chrom", sort=True):
        groups.append(
            (
                group["museum_sum"].to_numpy(float),
                group["modern_sum"].to_numpy(float),
                group["n_sites"].to_numpy(float),
                group["opportunity_bp"].to_numpy(float),
            )
        )
    rng = np.random.default_rng(seed)
    output = np.empty(reps, dtype=float)
    for rep in range(reps):
        museum_sum = modern_sum = n_sites = opportunity = 0.0
        for museum, modern, sites, bp in groups:
            draw = rng.integers(0, len(museum), size=len(museum))
            museum_sum += float(museum[draw].sum())
            modern_sum += float(modern[draw].sum())
            n_sites += float(sites[draw].sum())
            opportunity += float(bp[draw].sum())
        denominator = opportunity if metric == "pi" else n_sites
        output[rep] = (museum_sum - modern_sum) / denominator
    return output


def expected_block_tuples(
    contigs: Sequence[str], contig_lengths: dict[str, int], block_size: int
) -> set[tuple[str, int, int, int, int]]:
    expected: set[tuple[str, int, int, int, int]] = set()
    for chrom in contigs:
        length = int(contig_lengths[chrom])
        for index in range(math.ceil(length / block_size)):
            start = index * block_size + 1
            end = min((index + 1) * block_size, length)
            expected.add((chrom, index, start, end, end - start + 1))
    return expected


def table_block_tuples(frame: pd.DataFrame) -> set[tuple[str, int, int, int, int]]:
    return {
        (
            str(row.chrom), int(row.block_index), int(row.block_start_bp),
            int(row.block_end_bp), int(row.opportunity_bp),
        )
        for row in frame.itertuples(index=False)
    }


def png_ok(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "missing"
    data = path.read_bytes()
    ok = len(data) > 10_000 and data.startswith(b"\x89PNG\r\n\x1a\n") and b"IHDR" in data[:40]
    return ok, f"{len(data):,} bytes" if ok else f"invalid PNG; {len(data):,} bytes"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--raw-vcf", default="data/peafowl/raw/Comparative_genomic_dataset_F.vcf.gz")
    parser.add_argument("--normalized-vcf", default="results/qc/comparative.norm.vcf.gz")
    parser.add_argument("--popmap", default="results/qc/temporal_popmap.tsv")
    parser.add_argument("--autosomes", default="config/peafowl_autosomes.txt")
    parser.add_argument("--effects", default=DEFAULTS["effects"])
    parser.add_argument("--permutations", default=DEFAULTS["permutations"])
    parser.add_argument("--influence", default=DEFAULTS["influence"])
    parser.add_argument("--blocks", default=DEFAULTS["blocks"])
    parser.add_argument("--classification", default=DEFAULTS["classification"])
    parser.add_argument("--figure-values", default=DEFAULTS["figure_values"])
    parser.add_argument("--figure", default=DEFAULTS["figure"])
    parser.add_argument("--provenance", default=DEFAULTS["provenance"])
    parser.add_argument("--out-tsv", default=DEFAULTS["out_tsv"])
    parser.add_argument("--out-md", default=DEFAULTS["out_md"])
    return parser.parse_args()


def self_test() -> None:
    transitions = {"C>T", "T>C", "G>A", "A>G"}
    assert variant_class("C", "T", transitions) == "transition"
    assert variant_class("C", "A", transitions) == "transversion"
    assert variant_class("AA", "CC", transitions) == "mnv"
    assert variant_class("A", "AT", transitions) == "indel"
    assert variant_class("A", "C,G", transitions) == "multiallelic"
    assert len(list(combinations(range(11), 5))) == 462
    frame = pd.DataFrame(
        {
            "chrom": ["a", "a", "b"], "block_index": [0, 1, 0],
            "museum_sum": [1.0, 2.0, 3.0], "modern_sum": [0.5, 1.5, 2.5],
            "n_sites": [2, 2, 2], "opportunity_bp": [5, 5, 5],
        }
    )
    first = bootstrap_effects(frame, "He", 20, 7)
    second = bootstrap_effects(frame, "He", 20, 7)
    assert np.array_equal(first, second) and np.isfinite(first).all()
    assert EXPECTED_CELL_ORDER == (
        ("all_snp", "pi"),
        ("all_snp", "Ho"),
        ("all_snp", "He"),
        ("all_snp", "allelic_richness"),
        ("transversion_only", "pi"),
        ("transversion_only", "Ho"),
        ("transversion_only", "He"),
        ("transversion_only", "allelic_richness"),
    )
    print("validate_peafowl_damage self-test: OK")


def run_validation(args: argparse.Namespace) -> None:
    checks: list[tuple[str, str, str]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append((name, "PASS" if ok else "FAIL", detail))

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    settings = cfg["phase5b"]["damage_falsification"]
    seed = int(settings["seed"])
    reps = int(settings["bootstrap_reps"])
    ci_pct = float(settings["ci_pct"])
    block_size = int(settings["block_size_bp"])
    rarefy_n = int(settings["rarefy_n"])
    upgrade_min = int(settings["upgrade_min_concordant_metrics"])
    transition_pairs = {str(value).upper() for value in settings["transition_pairs"]}

    popmap = pd.read_csv(args.popmap, sep="\t")
    if list(popmap.columns[:2]) != ["sample", "population"]:
        popmap = popmap.iloc[:, :2].copy()
        popmap.columns = ["sample", "population"]
    samples = popmap["sample"].astype(str).tolist()
    museum_samples = popmap.loc[popmap["population"].eq("museum"), "sample"].astype(str).tolist()
    modern_samples = popmap.loc[popmap["population"].eq("modern"), "sample"].astype(str).tolist()
    autosomes = read_autosomes(args.autosomes)
    add(
        "frozen popmap is 5 museum versus 6 modern unique birds",
        len(samples) == len(set(samples)) == 11 and len(museum_samples) == 5 and len(modern_samples) == 6,
        f"museum={len(museum_samples)}, modern={len(modern_samples)}, total={len(samples)}",
    )
    add(
        "damage-aware transition definition is the predeclared four ordered changes",
        transition_pairs == {"C>T", "T>C", "G>A", "A>G"},
        ", ".join(sorted(transition_pairs)),
    )

    effects = pd.read_csv(args.effects, sep="\t")
    permutations = pd.read_csv(args.permutations, sep="\t")
    influence = pd.read_csv(args.influence, sep="\t")
    blocks = pd.read_csv(args.blocks, sep="\t")
    classification = pd.read_csv(args.classification, sep="\t")
    figure_values = pd.read_csv(args.figure_values, sep="\t")
    provenance = json.loads(Path(args.provenance).read_text(encoding="utf-8"))

    schemas = [
        ("effects", effects, EFFECT_COLUMNS),
        ("permutations", permutations, PERMUTATION_COLUMNS),
        ("influence", influence, INFLUENCE_COLUMNS),
        ("blocks", blocks, BLOCK_COLUMNS),
        ("classification", classification, CLASSIFICATION_COLUMNS),
        ("figure values", figure_values, FIGURE_VALUE_COLUMNS),
    ]
    for label, table, required in schemas:
        missing = sorted(required - set(table.columns))
        add(f"{label} table has its complete audit schema", not missing, "complete" if not missing else f"missing={missing}")

    # Independent streaming classification also verifies the exact sample set.
    raw = inspect_vcf(args.raw_vcf, samples, transition_pairs)
    normalized = inspect_vcf(args.normalized_vcf, samples, transition_pairs, set(autosomes))
    add(
        "both VCF headers contain the exact 11 frozen samples",
        set(raw.samples) == set(samples) == set(normalized.samples),
        "raw and normalized headers independently inspected",
    )
    add(
        "normalized comparative records stay on the frozen autosomes",
        normalized.records_outside_allowed_contigs == 0,
        f"outside-autosome records={normalized.records_outside_allowed_contigs}",
    )

    inspections = {"raw_comparative": raw, "normalized_comparative": normalized}
    class_ok = len(classification) == 2 * (len(LEAF_CLASSES) + 2)
    class_details = []
    for basis, inspection in inspections.items():
        frame = classification[classification["basis"].eq(basis)]
        class_ok &= set(frame["variant_class"].astype(str)) == set(LEAF_CLASSES) | {"other_all", "total"}
        indexed = frame.set_index("variant_class")
        for cls in LEAF_CLASSES:
            if cls not in indexed.index:
                class_ok = False
                continue
            row = indexed.loc[cls]
            n = int(inspection.class_counts.get(cls, 0))
            complete = int(inspection.complete_counts.get(cls, 0))
            class_ok &= int(row["n_records"]) == n
            class_ok &= int(row["n_complete_11"]) == complete
            class_ok &= int(row["n_incomplete_11"]) == n - complete
            expected_all = complete if cls in {"transition", "transversion"} else 0
            expected_tv = complete if cls == "transversion" else 0
            class_ok &= int(row["used_all_snp_records"]) == expected_all
            class_ok &= int(row["used_transversion_records"]) == expected_tv
        leaf_total = sum(int(inspection.class_counts.get(cls, 0)) for cls in LEAF_CLASSES)
        complete_total = sum(int(inspection.complete_counts.get(cls, 0)) for cls in LEAF_CLASSES)
        other_total = sum(int(inspection.class_counts.get(cls, 0)) for cls in OTHER_CLASSES)
        other_complete = sum(int(inspection.complete_counts.get(cls, 0)) for cls in OTHER_CLASSES)
        if {"total", "other_all"} <= set(indexed.index):
            total_row = indexed.loc["total"]
            other_row = indexed.loc["other_all"]
            class_ok &= int(total_row["n_records"]) == leaf_total
            class_ok &= int(total_row["n_complete_11"]) == complete_total
            class_ok &= int(other_row["n_records"]) == other_total
            class_ok &= int(other_row["n_complete_11"]) == other_complete
            class_ok &= int(total_row["n_contigs_in_header"]) == len(inspection.contig_lengths)
            class_ok &= int(total_row["genomic_opportunity_bp"]) == sum(inspection.contig_lengths.values())
        class_details.append(
            f"{basis}: total={leaf_total:,}, complete SNP="
            f"{inspection.complete_counts.get('transition', 0) + inspection.complete_counts.get('transversion', 0):,}"
        )
    add(
        "transition, transversion, MNV, indel, multiallelic, and other counts independently reconcile",
        bool(class_ok),
        "; ".join(class_details),
    )

    expected_cells = set(EXPECTED_CELL_ORDER)
    observed_effect_cells = set(zip(effects["variant_set"], effects["metric"]))
    add(
        "effects preserve exactly the eight variant-set by metric outcomes",
        len(effects) == 8 and observed_effect_cells == expected_cells and not effects.duplicated(["variant_set", "metric"]).any(),
        f"rows={len(effects)}, unique cells={len(observed_effect_cells)}",
    )
    effect_index = effects.set_index(["variant_set", "metric"])
    effect_algebra_ok = True
    for (variant_set, metric), row in effect_index.iterrows():
        effect = float(row["museum_value"]) - float(row["modern_value"])
        expected_seed = seed + VARIANT_SEED_CODE[variant_set] + METRIC_SEED_CODE[metric]
        effect_algebra_ok &= close(effect, row["effect_museum_minus_modern"])
        effect_algebra_ok &= str(row["analysis_id"]) == f"{variant_set}__{metric}"
        effect_algebra_ok &= str(row["basis"]) == METRIC_BASIS[metric]
        effect_algebra_ok &= str(row["direction"]) == direction(effect)
        effect_algebra_ok &= int(row["museum_n"]) == 5 and int(row["modern_n"]) == 6
        effect_algebra_ok &= int(row["rarefy_n"]) == (rarefy_n if metric == "allelic_richness" else 0)
        effect_algebra_ok &= int(row["bootstrap_reps"]) == reps
        effect_algebra_ok &= int(row["bootstrap_seed"]) == expected_seed
        effect_algebra_ok &= close(row["ci_pct"], ci_pct)
        effect_algebra_ok &= np.isfinite([row["museum_value"], row["modern_value"], row["ci_low"], row["ci_high"]]).all()
        effect_algebra_ok &= float(row["ci_low"]) <= float(row["ci_high"])
    add(
        "effect values, metric bases, directions, sample sizes, and derived bootstrap seeds reconcile",
        bool(effect_algebra_ok),
        f"base seed={seed}; reps={reps}; CI={ci_pct:g}%",
    )

    # Every declared genomic block, including zero-variant and terminal blocks,
    # must be present for each applicable metric/variant-set combination.
    raw_expected_blocks = expected_block_tuples(list(raw.contig_lengths), raw.contig_lengths, block_size)
    norm_expected_blocks = expected_block_tuples(autosomes, normalized.contig_lengths, block_size)
    blocks_ok = not blocks.duplicated(["basis", "variant_set", "metric", "chrom", "block_index"]).any()
    block_count_details = []
    for variant_set, metric in EXPECTED_CELL_ORDER:
        frame = blocks[(blocks["variant_set"].eq(variant_set)) & (blocks["metric"].eq(metric))]
        expected = raw_expected_blocks if metric == "pi" else norm_expected_blocks
        blocks_ok &= table_block_tuples(frame) == expected
        blocks_ok &= set(frame["basis"].astype(str)) == {METRIC_BASIS[metric]}
        blocks_ok &= set(frame["denominator"].astype(str)) == ({"genomic_bp"} if metric == "pi" else {"complete_variant_sites"})
        blocks_ok &= (pd.to_numeric(frame["n_sites"]) >= 0).all()
        blocks_ok &= np.isfinite(frame[["museum_sum", "modern_sum"]].to_numpy(float)).all()
        blocks_ok &= set(pd.to_numeric(frame["museum_n"]).astype(int)) == {5}
        blocks_ok &= set(pd.to_numeric(frame["modern_n"]).astype(int)) == {6}
        expected_rarefy = rarefy_n if metric == "allelic_richness" else 0
        blocks_ok &= set(pd.to_numeric(frame["rarefy_n"]).astype(int)) == {expected_rarefy}
        block_count_details.append(f"{variant_set}/{metric}={len(frame):,}")
    add(
        "5-Mb block table includes the complete raw and autosomal opportunity grids",
        bool(blocks_ok),
        "; ".join(block_count_details),
    )

    # Site totals are frozen independently for raw pi and normalized Ho/He/AR.
    expected_sites = {
        ("all_snp", "pi"): raw.complete_counts.get("transition", 0) + raw.complete_counts.get("transversion", 0),
        ("transversion_only", "pi"): raw.complete_counts.get("transversion", 0),
    }
    for variant_set in VARIANT_SETS:
        n_all = normalized.complete_counts.get("transition", 0) + normalized.complete_counts.get("transversion", 0)
        n_tv = normalized.complete_counts.get("transversion", 0)
        for metric in ("Ho", "He", "allelic_richness"):
            expected_sites[(variant_set, metric)] = n_all if variant_set == "all_snp" else n_tv
    site_basis_ok = True
    for cell, expected_n in expected_sites.items():
        frame = blocks[(blocks["variant_set"].eq(cell[0])) & (blocks["metric"].eq(cell[1]))]
        effect_row = effect_index.loc[cell]
        site_basis_ok &= int(frame["n_sites"].sum()) == int(expected_n)
        site_basis_ok &= int(effect_row["n_sites"]) == int(expected_n)
        if cell[1] == "pi":
            expected_bp = sum(raw.contig_lengths.values())
            site_basis_ok &= int(frame["opportunity_bp"].sum()) == expected_bp
            site_basis_ok &= int(effect_row["opportunity_bp"]) == expected_bp
        else:
            site_basis_ok &= int(effect_row["opportunity_bp"]) == 0
    add(
        "raw pi and normalized Ho/He/AR use independent complete-call frozen site bases",
        bool(site_basis_ok),
        "pi uses raw all-contig bp; Ho/He/AR use normalized autosomal complete SNP sites",
    )

    bootstrap_ok = True
    bootstrap_details = []
    alpha = (100.0 - ci_pct) / 2.0
    for variant_set, metric in sorted(expected_cells):
        frame = blocks[(blocks["variant_set"].eq(variant_set)) & (blocks["metric"].eq(metric))]
        row = effect_index.loc[(variant_set, metric)]
        museum, modern, effect = block_point(frame, metric)
        derived_seed = seed + VARIANT_SEED_CODE[variant_set] + METRIC_SEED_CODE[metric]
        first = bootstrap_effects(frame, metric, reps, derived_seed)
        second = bootstrap_effects(frame, metric, reps, derived_seed)
        low, high = np.percentile(first, [alpha, 100.0 - alpha])
        cell_ok = (
            np.array_equal(first, second)
            and np.isfinite(first).all()
            and close(museum, row["museum_value"])
            and close(modern, row["modern_value"])
            and close(effect, row["effect_museum_minus_modern"])
            and close(low, row["ci_low"])
            and close(high, row["ci_high"])
        )
        bootstrap_ok &= cell_ok
        bootstrap_details.append(f"{variant_set}/{metric} seed={derived_seed}")
    add(
        "independent repeated chromosome-stratified block bootstraps reproduce every point and interval",
        bool(bootstrap_ok),
        "; ".join(bootstrap_details),
    )

    # Enumerate C(11,5) independently and require every outcome for every allocation.
    expected_allocations: dict[str, tuple[str, str, bool]] = {}
    observed_museum = set(museum_samples)
    for index, indices in enumerate(combinations(range(11), 5)):
        museum = [samples[i] for i in indices]
        modern = [sample for i, sample in enumerate(samples) if i not in indices]
        expected_allocations[f"P{index:03d}"] = (
            "|".join(museum), "|".join(modern), set(museum) == observed_museum
        )
    permutation_keys = set(zip(permutations["allocation_id"], permutations["variant_set"], permutations["metric"]))
    expected_keys = {
        (allocation_id, variant_set, metric)
        for allocation_id in expected_allocations
        for variant_set, metric in expected_cells
    }
    allocation_ok = (
        len(permutations) == 462 * 8
        and permutation_keys == expected_keys
        and not permutations.duplicated(["allocation_id", "variant_set", "metric"]).any()
    )
    for allocation_id, (museum_label, modern_label, observed) in expected_allocations.items():
        frame = permutations[permutations["allocation_id"].eq(allocation_id)]
        allocation_ok &= set(frame["museum_samples"].astype(str)) == {museum_label}
        allocation_ok &= set(frame["modern_samples"].astype(str)) == {modern_label}
        allocation_ok &= {as_bool(value) for value in frame["is_observed_allocation"]} == {observed}
    observed_ids = permutations.loc[
        permutations["is_observed_allocation"].map(as_bool), "allocation_id"
    ].drop_duplicates()
    allocation_ok &= len(observed_ids) == 1
    add(
        "all 462 exact 5-versus-6 allocations retain all eight labeled outcomes",
        bool(allocation_ok),
        f"allocations={permutations['allocation_id'].nunique()}, outcomes={len(permutations)}, observed={observed_ids.tolist()}",
    )

    permutation_values_ok = True
    for row in permutations.itertuples(index=False):
        effect = float(row.museum_value) - float(row.modern_value)
        permutation_values_ok &= close(effect, row.effect_museum_minus_modern)
        permutation_values_ok &= str(row.direction) == direction(effect)
        permutation_values_ok &= str(row.basis) == METRIC_BASIS[str(row.metric)]
        permutation_values_ok &= int(row.museum_n) == 5 and int(row.modern_n) == 6
        permutation_values_ok &= int(row.rarefy_n) == (rarefy_n if row.metric == "allelic_richness" else 0)
        permutation_values_ok &= int(row.n_sites) == expected_sites[(str(row.variant_set), str(row.metric))]
    add(
        "every exact-allocation effect, direction, metric basis, and frozen denominator reconciles",
        bool(permutation_values_ok),
        "museum minus modern recomputed for 3,696 outcomes",
    )

    exact_reference_ok = True
    exact_details = []
    for cell in sorted(expected_cells):
        frame = permutations[(permutations["variant_set"].eq(cell[0])) & (permutations["metric"].eq(cell[1]))]
        observed = frame[frame["is_observed_allocation"].map(as_bool)]
        effect = float(observed.iloc[0]["effect_museum_minus_modern"])
        values = frame["effect_museum_minus_modern"].to_numpy(float)
        p_value = float(np.mean(np.abs(values) >= abs(effect) - 1e-15))
        percentile = float((np.sum(values < effect) + 0.5 * np.sum(np.isclose(values, effect))) / len(values))
        row = effect_index.loc[cell]
        exact_reference_ok &= len(observed) == 1
        exact_reference_ok &= close(effect, row["effect_museum_minus_modern"])
        exact_reference_ok &= close(p_value, row["exact_permutation_p_two_sided"])
        exact_reference_ok &= close(percentile, row["exact_permutation_percentile"])
        exact_reference_ok &= int(row["n_exact_allocations"]) == 462
        exact_details.append(f"{cell[0]}/{cell[1]} p={p_value:.4f}")
    add(
        "independent exact-reference p-values and percentiles reproduce the effects table",
        bool(exact_reference_ok),
        "; ".join(exact_details),
    )

    # Predeclared six equal-n omissions and all 11 leave-one cases.
    expected_cases: dict[str, tuple[str, str, str, list[str], list[str]]] = {}
    for index, left_out in enumerate(modern_samples, start=1):
        expected_cases[f"E{index:02d}"] = (
            "equal_n_modern_leave_one", left_out, "modern", museum_samples,
            [sample for sample in modern_samples if sample != left_out],
        )
    for index, left_out in enumerate(samples, start=1):
        group = "museum" if left_out in museum_samples else "modern"
        expected_cases[f"L{index:02d}"] = (
            "leave_one_individual", left_out, group,
            [sample for sample in museum_samples if sample != left_out],
            [sample for sample in modern_samples if sample != left_out],
        )
    influence_keys = set(zip(influence["case_id"], influence["variant_set"], influence["metric"]))
    expected_influence_keys = {
        (case_id, variant_set, metric)
        for case_id in expected_cases
        for variant_set, metric in expected_cells
    }
    influence_ok = (
        len(influence) == 17 * 8
        and influence_keys == expected_influence_keys
        and not influence.duplicated(["case_id", "variant_set", "metric"]).any()
    )
    for case_id, (case_type, left_out, group, museum, modern) in expected_cases.items():
        frame = influence[influence["case_id"].eq(case_id)]
        influence_ok &= set(frame["case_type"].astype(str)) == {case_type}
        influence_ok &= set(frame["left_out_sample"].astype(str)) == {left_out}
        influence_ok &= set(frame["left_out_group"].astype(str)) == {group}
        influence_ok &= set(frame["museum_samples"].astype(str)) == {"|".join(museum)}
        influence_ok &= set(frame["modern_samples"].astype(str)) == {"|".join(modern)}
        influence_ok &= set(pd.to_numeric(frame["museum_n"]).astype(int)) == {len(museum)}
        influence_ok &= set(pd.to_numeric(frame["modern_n"]).astype(int)) == {len(modern)}
        expected_rarefaction = min(rarefy_n, len(museum), len(modern))
        ar = frame[frame["metric"].eq("allelic_richness")]
        non_ar = frame[~frame["metric"].eq("allelic_richness")]
        influence_ok &= set(pd.to_numeric(ar["rarefy_n"]).astype(int)) == {expected_rarefaction}
        influence_ok &= set(pd.to_numeric(non_ar["rarefy_n"]).astype(int)) == {0}
    add(
        "six equal-n omissions and all 11 leave-one cases preserve samples, groups, and rarefaction n",
        bool(influence_ok),
        f"cases={influence['case_id'].nunique()}, outcomes={len(influence)}; museum-LOO AR rarefies to n=4",
    )

    influence_values_ok = True
    for row in influence.itertuples(index=False):
        effect = float(row.museum_value) - float(row.modern_value)
        baseline_direction = str(effect_index.loc[(row.variant_set, row.metric), "direction"])
        influence_values_ok &= close(effect, row.effect_museum_minus_modern)
        influence_values_ok &= str(row.direction) == direction(effect)
        influence_values_ok &= as_bool(row.same_direction_as_baseline) == (direction(effect) == baseline_direction)
        influence_values_ok &= str(row.basis) == METRIC_BASIS[str(row.metric)]
        influence_values_ok &= int(row.n_sites) == expected_sites[(str(row.variant_set), str(row.metric))]
    add(
        "all influence effects and direction-stability labels independently reconcile",
        bool(influence_values_ok),
        "museum minus modern and baseline direction recomputed for 136 outcomes",
    )

    scorecard_ok = True
    for cell, row in effect_index.iterrows():
        frame = influence[(influence["variant_set"].eq(cell[0])) & (influence["metric"].eq(cell[1]))]
        equal = frame[frame["case_type"].eq("equal_n_modern_leave_one")]
        leave = frame[frame["case_type"].eq("leave_one_individual")]
        baseline = str(row["direction"])
        scorecard_ok &= int(row["equal_n_cases_n"]) == 6
        scorecard_ok &= int(row["leave_one_cases_n"]) == 11
        scorecard_ok &= int(row["equal_n_same_direction_n"]) == int((equal["direction"] == baseline).sum())
        scorecard_ok &= int(row["leave_one_same_direction_n"]) == int((leave["direction"] == baseline).sum())
        scorecard_ok &= close(row["equal_n_effect_min"], equal["effect_museum_minus_modern"].min())
        scorecard_ok &= close(row["equal_n_effect_max"], equal["effect_museum_minus_modern"].max())
        scorecard_ok &= close(row["leave_one_effect_min"], leave["effect_museum_minus_modern"].min())
        scorecard_ok &= close(row["leave_one_effect_max"], leave["effect_museum_minus_modern"].max())
    for metric in METRICS:
        all_dir = str(effect_index.loc[("all_snp", metric), "direction"])
        tv_dir = str(effect_index.loc[("transversion_only", metric), "direction"])
        for variant_set in VARIANT_SETS:
            scorecard_ok &= as_bool(effect_index.loc[(variant_set, metric), "same_direction_all_snp_vs_transversion"]) == (all_dir == tv_dir)
    for variant_set in VARIANT_SETS:
        frame = effects[effects["variant_set"].eq(variant_set)]
        positive = int((frame["direction"] == "museum_higher").sum())
        scorecard_ok &= set(pd.to_numeric(frame["museum_higher_concordant_metrics_n"]).astype(int)) == {positive}
    add(
        "effect scorecard independently reproduces equal-n, leave-one, and transversion stability",
        bool(scorecard_ok),
        "all case counts, extrema, and concordance flags recomputed",
    )

    directional_condition = bool(
        all(
            int(effect_index.loc[(variant_set, metric), "museum_higher_concordant_metrics_n"]) >= upgrade_min
            for variant_set in VARIANT_SETS
            for metric in (METRICS[0],)
        )
        and all(
            as_bool(effect_index.loc[(variant_set, metric), "same_direction_all_snp_vs_transversion"])
            for variant_set, metric in expected_cells
        )
        and all(
            int(row.equal_n_same_direction_n) == int(row.equal_n_cases_n)
            and int(row.leave_one_same_direction_n) == int(row.leave_one_cases_n)
            for row in effects.itertuples(index=False)
        )
    )
    geographic_flags = effects["geographic_mismatch_caveat"].map(as_bool)
    expected_upgrade = directional_condition and not bool(geographic_flags.any())
    decision_ok = geographic_flags.all() and all(
        as_bool(value) == expected_upgrade for value in effects["supports_temporal_erosion_upgrade"]
    )
    add(
        "numeric falsifier is distinct from the unresolved geographic-design veto",
        bool(decision_ok and not expected_upgrade),
        f"directional condition={directional_condition}; geographic mismatch=True; temporal upgrade=False",
    )

    # Plotting values must be a transparent, lossless projection of source tables.
    forest = figure_values[figure_values["panel"].eq("forest")]
    plotted_influence = figure_values[figure_values["panel"].eq("influence")]
    figure_values_ok = len(forest) == 8 and len(plotted_influence) == 136
    for row in forest.itertuples(index=False):
        source = effect_index.loc[(row.variant_set, row.metric)]
        scale = 100.0 / float(source["modern_value"])
        figure_values_ok &= str(row.series_id) == f"{row.variant_set}__{row.metric}"
        figure_values_ok &= str(row.case_id) == "baseline" and str(row.case_type) == "baseline"
        figure_values_ok &= close(row.estimate, source["effect_museum_minus_modern"])
        figure_values_ok &= close(row.ci_low, source["ci_low"]) and close(row.ci_high, source["ci_high"])
        figure_values_ok &= close(row.display_effect_pct_of_modern, float(source["effect_museum_minus_modern"]) * scale)
        figure_values_ok &= close(row.display_ci_low_pct_of_modern, float(source["ci_low"]) * scale)
        figure_values_ok &= close(row.display_ci_high_pct_of_modern, float(source["ci_high"]) * scale)
    influence_index = influence.set_index(["case_id", "variant_set", "metric"])
    for row in plotted_influence.itertuples(index=False):
        source = influence_index.loc[(row.case_id, row.variant_set, row.metric)]
        expected_display = 100.0 * float(source["effect_museum_minus_modern"]) / float(source["modern_value"])
        figure_values_ok &= str(row.series_id) == f"{row.variant_set}__{row.metric}"
        figure_values_ok &= str(row.case_type) == str(source["case_type"])
        figure_values_ok &= str(row.label) == str(source["left_out_sample"])
        figure_values_ok &= close(row.estimate, source["effect_museum_minus_modern"])
        figure_values_ok &= pd.isna(row.ci_low) and pd.isna(row.ci_high)
        figure_values_ok &= close(row.display_effect_pct_of_modern, expected_display)
    add(
        "figure-values table exactly projects all effects, intervals, and influence cases",
        bool(figure_values_ok),
        f"forest={len(forest)}, influence={len(plotted_influence)}",
    )
    ok, png_detail = png_ok(Path(args.figure))
    add("compact forest/influence figure is a non-empty PNG", ok, png_detail)

    # Provenance must preserve settings, bases, limitations, exact methods, and
    # checksums for every non-provenance artifact.
    prov_settings = provenance.get("settings", {})
    settings_ok = (
        int(prov_settings.get("seed", -1)) == seed
        and int(prov_settings.get("bootstrap_reps", -1)) == reps
        and close(prov_settings.get("ci_pct", math.nan), ci_pct)
        and int(prov_settings.get("block_size_bp", -1)) == block_size
        and int(prov_settings.get("rarefy_n", -1)) == rarefy_n
        and int(prov_settings.get("exact_allocations", -1)) == 462
        and set(prov_settings.get("transition_pairs", [])) == transition_pairs
        and int(prov_settings.get("upgrade_min_concordant_metrics", -1)) == upgrade_min
    )
    prov_samples = provenance.get("samples", {})
    settings_ok &= prov_samples.get("order") == samples
    settings_ok &= prov_samples.get("museum") == museum_samples and prov_samples.get("modern") == modern_samples
    add(
        "provenance freezes configuration and exact sample identities",
        bool(settings_ok),
        f"seed={seed}, reps={reps}, blocks={block_size:,} bp, rarefy n={rarefy_n}",
    )

    basis = provenance.get("basis", {})
    relabel_text = str(basis.get("exact_relabeling", "")).lower()
    basis_ok = (
        basis.get("pi", {}).get("input") == args.raw_vcf
        and int(basis.get("pi", {}).get("genomic_opportunity_bp", -1)) == sum(raw.contig_lengths.values())
        and basis.get("Ho_He_allelic_richness", {}).get("input") == args.normalized_vcf
        and "all 11" in relabel_text and "before" in relabel_text and "site" in relabel_text
        and "analytical hypergeometric" in str(basis.get("allelic_richness", "")).lower()
    )
    method_text = " ".join(
        [str(provenance.get("bootstrap", "")), str(provenance.get("exact_permutation", "")),
         json.dumps(provenance.get("variant_handling", {}), sort_keys=True)]
    ).lower()
    basis_ok &= "within chromosome" in method_text and "462" in method_text
    basis_ok &= all(term in method_text for term in ("mnv", "indel", "multiallelic"))
    add(
        "provenance records raw/normalized bases, complete-call relabeling, analytical rarefaction, and reconciled other variants",
        bool(basis_ok),
        "method boundaries and exclusions are explicit",
    )

    caveat_text = " ".join(map(str, provenance.get("caveats", []))).lower()
    falsifier = provenance.get("numeric_falsifier", {})
    prov_decision_ok = (
        "geograph" in caveat_text and "mismatch" in caveat_text
        and as_bool(falsifier.get("directional_condition_met_before_design_limitations", False)) == directional_condition
        and all(as_bool(value) == expected_upgrade for value in falsifier.get("upgrade_supported", {}).values())
        and "geographic" in str(falsifier.get("claim_upgrade_condition", "")).lower()
    )
    add(
        "provenance keeps the geographic mismatch prominent under the recorded numerical outcome",
        bool(prov_decision_ok),
        "geography cannot be isolated from time; the claim-upgrade veto is machine readable",
    )

    input_map = {
        "raw_vcf": args.raw_vcf, "normalized_vcf": args.normalized_vcf,
        "popmap": args.popmap, "autosomes": args.autosomes, "config": args.config,
    }
    input_hash_ok = True
    for key, path in input_map.items():
        recorded = provenance.get("inputs", {}).get(key, {})
        input_hash_ok &= recorded.get("path") == path and recorded.get("sha256") == sha256_file(path)
    add("provenance input paths and SHA-256 hashes reconcile", bool(input_hash_ok), f"inputs={len(input_map)}")

    output_map = {
        "effects": args.effects, "permutations": args.permutations,
        "influence": args.influence, "blocks": args.blocks,
        "classification": args.classification, "figure_values": args.figure_values,
        "figure": args.figure,
    }
    output_hash_ok = True
    for key, path in output_map.items():
        recorded = provenance.get("outputs", {}).get(key, {})
        output_hash_ok &= recorded.get("path") == path and recorded.get("sha256") == sha256_file(path)
    add("provenance output paths and SHA-256 hashes reconcile", bool(output_hash_ok), f"outputs={len(output_map)}")

    report = pd.DataFrame(checks, columns=["check", "status", "detail"])
    out_tsv = Path(args.out_tsv)
    out_md = Path(args.out_md)
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(out_tsv, sep="\t", index=False)
    n_pass = int(report["status"].eq("PASS").sum())
    n_fail = int(report["status"].eq("FAIL").sum())
    lines = [
        "# Peafowl damage-aware falsification — validation",
        "",
        f"**Summary: {n_pass} PASS, 0 WARN, {n_fail} FAIL**",
        "",
        "| check | status | evidence |",
        "|---|---|---|",
    ]
    for row in report.itertuples(index=False):
        detail = str(row.detail).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {row.check} | **{row.status}** | {detail} |")
    lines.extend(
        [
            "",
            "The exact allocation reference, block intervals, and influence checks quantify fragility; they do not make the museum and modern samples geographically exchangeable.",
            "",
            "The temporal-erosion claim remains withheld while geography and time are confounded, even if the predeclared directional condition happens to pass.",
            "",
        ]
    )
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(report.to_string(index=False))
    print(f"peafowl damage validation: {n_pass} PASS, 0 WARN, {n_fail} FAIL")
    raise SystemExit(1 if n_fail else 0)


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    run_validation(args)


if __name__ == "__main__":
    main()
