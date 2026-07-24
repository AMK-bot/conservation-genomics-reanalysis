#!/usr/bin/env python3
"""Damage-aware museum--modern peafowl falsification (CGplan section 13.3).

The analysis deliberately keeps two deposited/derived data bases separate:

* nucleotide diversity (pi) uses the *raw deposited comparative VCF* and the
  genomic opportunity recorded by that VCF's contig lengths;
* Ho, unbiased He, and analytically rarefied allelic richness use the existing
  normalized, biallelic-SNP, autosomal comparative VCF.

For exact label permutations, and for every related stress test, each basis is
restricted to biallelic single-base SNPs called in all 11 retained birds.  Thus
the site set cannot change when labels are reassigned.  Other records (MNV,
indel, multiallelic, symbolic/other) are counted and reconciled but never
silently coerced into the transition/transversion analysis.

The 462 exact 5-vs-6 allocations are evaluated with base-3 genotype-pattern
aggregation (at most 3**11 patterns) and small matrix batches.  This preserves
every allocation and outcome without constructing a 462 x sites array.
"""

from __future__ import annotations

import argparse
from array import array
from collections import Counter
from dataclasses import dataclass
import gzip
import hashlib
from itertools import combinations
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Sequence

import numpy as np
import pandas as pd
import yaml


METRICS = ("pi", "Ho", "He", "allelic_richness")
VARIANT_SETS = ("all_snp", "transversion_only")
METRIC_BASIS = {
    "pi": "raw_comparative",
    "Ho": "normalized_comparative",
    "He": "normalized_comparative",
    "allelic_richness": "normalized_comparative",
}
METRIC_SEED_CODE = {"pi": 11, "Ho": 12, "He": 13, "allelic_richness": 14}
VARIANT_SEED_CODE = {"all_snp": 0, "transversion_only": 1000}
CONTIG_RE = re.compile(r"^##contig=<ID=([^,>]+),.*?length=([0-9]+)(?:,|>)")


DEFAULT_OUTPUTS = {
    "effects": "results/tables/peafowl_damage_effects.tsv",
    "permutations": "results/tables/peafowl_damage_permutations.tsv",
    "influence": "results/tables/peafowl_damage_influence.tsv",
    "blocks": "results/tables/peafowl_damage_blocks.tsv",
    "classification": "results/tables/peafowl_damage_classification.tsv",
    "figure_values": "results/tables/peafowl_damage_figure_values.tsv",
    "figure": "results/figures/peafowl_damage_falsification.png",
    "provenance": "results/provenance/peafowl_damage.json",
}


@dataclass(frozen=True)
class VCFDataset:
    basis: str
    path: str
    samples: tuple[str, ...]
    contig_names: tuple[str, ...]
    contig_lengths: dict[str, int]
    chrom_id: np.ndarray
    position: np.ndarray
    genotypes: np.ndarray
    is_transition: np.ndarray
    class_counts: dict[str, int]
    complete_counts: dict[str, int]

    @property
    def n_sites(self) -> int:
        return int(self.genotypes.shape[0])


@dataclass(frozen=True)
class PatternSummary:
    patterns: np.ndarray
    counts: np.ndarray
    n_sites: int


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
    values = [value.strip() for value in text.replace("\n", ",").split(",") if value.strip()]
    if not values or len(values) != len(set(values)):
        raise ValueError(f"invalid or duplicated autosome list: {path}")
    return values


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


def parse_sample_genotypes(
    fmt: str, sample_fields: Sequence[str], *, biallelic: bool
) -> tuple[bool, list[int] | None]:
    keys = fmt.split(":")
    if "GT" not in keys:
        return False, None
    gt_index = keys.index("GT")
    alt_counts: list[int] = []
    for sample in sample_fields:
        values = sample.split(":")
        if gt_index >= len(values):
            return False, None
        gt = values[gt_index].replace("|", "/")
        alleles = gt.split("/")
        if len(alleles) != 2 or any(a == "." or not a.isdigit() for a in alleles):
            return False, None
        numeric = [int(a) for a in alleles]
        if biallelic and any(a not in (0, 1) for a in numeric):
            return False, None
        alt_counts.append(sum(numeric))
    return True, alt_counts if biallelic else None


def load_vcf(
    path: str,
    basis: str,
    sample_order: Sequence[str],
    transition_pairs: set[str],
    *,
    allowed_contigs: set[str] | None = None,
) -> VCFDataset:
    """Stream a VCF and retain only complete-call biallelic SNVs in bounded arrays."""

    contig_lengths: dict[str, int] = {}
    contig_names: list[str] = []
    contig_to_id: dict[str, int] = {}
    sample_indices: list[int] | None = None
    vcf_samples: list[str] = []
    class_counts: Counter[str] = Counter()
    complete_counts: Counter[str] = Counter()
    chrom_buffer = array("H")
    pos_buffer = array("I")
    gt_buffer = bytearray()
    transition_buffer = bytearray()

    with open_text(path) as handle:
        for line in handle:
            if line.startswith("##contig="):
                match = CONTIG_RE.match(line.rstrip("\n"))
                if match:
                    name, length = match.group(1), int(match.group(2))
                    if name in contig_lengths:
                        raise ValueError(f"duplicate contig header in {path}: {name}")
                    contig_to_id[name] = len(contig_names)
                    contig_names.append(name)
                    contig_lengths[name] = length
                continue
            if line.startswith("##"):
                continue
            if line.startswith("#CHROM"):
                fields = line.rstrip("\n").split("\t")
                vcf_samples = fields[9:]
                missing = [sample for sample in sample_order if sample not in vcf_samples]
                extra = [sample for sample in vcf_samples if sample not in sample_order]
                if missing or extra or len(vcf_samples) != len(sample_order):
                    raise ValueError(
                        f"{basis} sample mismatch: missing={missing}, extra={extra}, "
                        f"VCF n={len(vcf_samples)}, expected n={len(sample_order)}"
                    )
                sample_indices = [vcf_samples.index(sample) for sample in sample_order]
                continue
            if line.startswith("#") or not line.strip():
                continue
            if sample_indices is None:
                raise ValueError(f"VCF header was not found before records in {path}")
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 9 + len(vcf_samples):
                raise ValueError(f"malformed VCF record in {path}: {line[:100]!r}")
            chrom, pos, ref, alt = fields[0], int(fields[1]), fields[3], fields[4]
            if chrom not in contig_to_id:
                raise ValueError(f"record contig lacks a length-bearing VCF header: {chrom}")
            if allowed_contigs is not None and chrom not in allowed_contigs:
                raise ValueError(f"normalized comparative record is outside frozen autosomes: {chrom}:{pos}")
            cls = variant_class(ref, alt, transition_pairs)
            class_counts[cls] += 1
            ordered_fields = [fields[9 + index] for index in sample_indices]
            is_biallelic_snv = cls in {"transition", "transversion"}
            complete, alt_counts = parse_sample_genotypes(
                fields[8], ordered_fields, biallelic=is_biallelic_snv
            )
            if complete:
                complete_counts[cls] += 1
            if not (is_biallelic_snv and complete and alt_counts is not None):
                continue
            chrom_buffer.append(contig_to_id[chrom])
            pos_buffer.append(pos)
            gt_buffer.extend(alt_counts)
            transition_buffer.append(1 if cls == "transition" else 0)

    if sample_indices is None:
        raise ValueError(f"VCF contains no #CHROM header: {path}")
    if not contig_lengths:
        raise ValueError(f"VCF has no contig lengths: {path}")
    n_sites = len(pos_buffer)
    genotypes = np.frombuffer(gt_buffer, dtype=np.uint8).reshape(n_sites, len(sample_order))
    return VCFDataset(
        basis=basis,
        path=path,
        samples=tuple(sample_order),
        contig_names=tuple(contig_names),
        contig_lengths=contig_lengths,
        chrom_id=np.asarray(chrom_buffer, dtype=np.uint16),
        position=np.asarray(pos_buffer, dtype=np.uint32),
        genotypes=genotypes,
        is_transition=np.frombuffer(transition_buffer, dtype=np.uint8).astype(bool),
        class_counts=dict(class_counts),
        complete_counts=dict(complete_counts),
    )


def analytical_ar_lookup(n_individuals: int, rarefy_n: int) -> np.ndarray:
    if rarefy_n < 1 or rarefy_n > n_individuals:
        raise ValueError(f"cannot rarefy n={n_individuals} individuals to {rarefy_n}")
    total = 2 * n_individuals
    draw = 2 * rarefy_n
    denominator = math.comb(total, draw)
    values = []
    for alt_count in range(total + 1):
        ref_count = total - alt_count
        p_ref_absent = math.comb(alt_count, draw) / denominator if alt_count >= draw else 0.0
        p_alt_absent = math.comb(ref_count, draw) / denominator if ref_count >= draw else 0.0
        values.append(2.0 - p_ref_absent - p_alt_absent)
    return np.asarray(values, dtype=float)


def he_lookup(n_individuals: int) -> np.ndarray:
    total = 2 * n_individuals
    alt = np.arange(total + 1, dtype=float)
    return 2.0 * alt * (total - alt) / (total * (total - 1.0))


def site_values(genotypes: np.ndarray, indices: Sequence[int], metric: str, rarefy_n: int) -> np.ndarray:
    group = genotypes[:, np.asarray(indices, dtype=int)]
    n = group.shape[1]
    alt = group.sum(axis=1, dtype=np.int16)
    if metric in {"pi", "He"}:
        return he_lookup(n)[alt]
    if metric == "Ho":
        return (group == 1).sum(axis=1) / float(n)
    if metric == "allelic_richness":
        return analytical_ar_lookup(n, rarefy_n)[alt]
    raise KeyError(metric)


def aggregate_patterns(genotypes: np.ndarray) -> PatternSummary:
    powers = (3 ** np.arange(genotypes.shape[1], dtype=np.int32)).astype(np.int32)
    codes = genotypes.astype(np.int32) @ powers
    counts_full = np.bincount(codes, minlength=int(3 ** genotypes.shape[1]))
    used = np.flatnonzero(counts_full)
    patterns = ((used[:, None] // powers[None, :]) % 3).astype(np.uint8)
    counts = counts_full[used].astype(np.int64)
    return PatternSummary(patterns, counts, int(genotypes.shape[0]))


def group_values_from_patterns(
    summary: PatternSummary,
    museum_indices: Sequence[int],
    modern_indices: Sequence[int],
    metric: str,
    rarefy_n: int,
    opportunity_bp: int,
) -> tuple[float, float]:
    patterns, counts = summary.patterns, summary.counts

    def one(indices: Sequence[int]) -> float:
        idx = np.asarray(indices, dtype=int)
        n = len(idx)
        alt = patterns[:, idx].sum(axis=1, dtype=np.int16)
        if metric in {"pi", "He"}:
            values = he_lookup(n)[alt]
        elif metric == "Ho":
            values = (patterns[:, idx] == 1).sum(axis=1) / float(n)
        elif metric == "allelic_richness":
            values = analytical_ar_lookup(n, rarefy_n)[alt]
        else:
            raise KeyError(metric)
        total = float(values @ counts)
        return total / opportunity_bp if metric == "pi" else total / summary.n_sites

    return one(museum_indices), one(modern_indices)


def allocation_values_from_patterns(
    summary: PatternSummary,
    allocation_matrix: np.ndarray,
    metrics: Sequence[str],
    rarefy_n: int,
    opportunity_bp: int,
    batch_size: int = 4096,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Evaluate all fixed-size allocations using bounded pattern batches."""

    n_alloc, n_samples = allocation_matrix.shape
    museum_n = int(allocation_matrix[0].sum())
    modern_n = n_samples - museum_n
    sums = {
        metric: (np.zeros(n_alloc, dtype=float), np.zeros(n_alloc, dtype=float))
        for metric in metrics
    }
    for start in range(0, len(summary.patterns), batch_size):
        stop = min(start + batch_size, len(summary.patterns))
        patterns = summary.patterns[start:stop].astype(np.int16, copy=False)
        counts = summary.counts[start:stop].astype(float, copy=False)
        museum_alt = allocation_matrix @ patterns.T
        total_alt = patterns.sum(axis=1, dtype=np.int16)
        modern_alt = total_alt[None, :] - museum_alt
        museum_het = allocation_matrix @ (patterns == 1).astype(np.int16).T
        total_het = (patterns == 1).sum(axis=1, dtype=np.int16)
        modern_het = total_het[None, :] - museum_het
        for metric in metrics:
            if metric in {"pi", "He"}:
                museum_site = he_lookup(museum_n)[museum_alt]
                modern_site = he_lookup(modern_n)[modern_alt]
            elif metric == "Ho":
                museum_site = museum_het / float(museum_n)
                modern_site = modern_het / float(modern_n)
            elif metric == "allelic_richness":
                museum_site = analytical_ar_lookup(museum_n, rarefy_n)[museum_alt]
                modern_site = analytical_ar_lookup(modern_n, rarefy_n)[modern_alt]
            else:
                raise KeyError(metric)
            sums[metric][0][:] += museum_site @ counts
            sums[metric][1][:] += modern_site @ counts
    output: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for metric, (museum_sum, modern_sum) in sums.items():
        denom = opportunity_bp if metric == "pi" else summary.n_sites
        output[metric] = (museum_sum / denom, modern_sum / denom)
    return output


def make_block_rows(
    dataset: VCFDataset,
    contigs: Sequence[str],
    mask: np.ndarray,
    variant_set: str,
    metrics: Sequence[str],
    museum_indices: Sequence[int],
    modern_indices: Sequence[int],
    rarefy_n: int,
    block_size: int,
) -> list[dict[str, object]]:
    name_to_dataset_id = {name: idx for idx, name in enumerate(dataset.contig_names)}
    block_meta: list[tuple[str, int, int, int, int]] = []
    offsets: dict[int, int] = {}
    for contig in contigs:
        if contig not in dataset.contig_lengths or contig not in name_to_dataset_id:
            raise ValueError(f"missing contig length for block bootstrap: {dataset.basis}/{contig}")
        length = int(dataset.contig_lengths[contig])
        dataset_id = name_to_dataset_id[contig]
        offsets[dataset_id] = len(block_meta)
        n_blocks = math.ceil(length / block_size)
        for block_index in range(n_blocks):
            start = block_index * block_size + 1
            end = min((block_index + 1) * block_size, length)
            block_meta.append((contig, block_index, start, end, end - start + 1))
    selected_ids = dataset.chrom_id[mask].astype(int)
    selected_pos = dataset.position[mask].astype(np.int64)
    try:
        global_block = np.fromiter(
            (offsets[int(cid)] + int((pos - 1) // block_size) for cid, pos in zip(selected_ids, selected_pos)),
            dtype=np.int64,
            count=len(selected_pos),
        )
    except KeyError as exc:
        raise ValueError(f"site fell outside declared block-contig universe: {exc}") from exc
    n_blocks = len(block_meta)
    site_counts = np.bincount(global_block, minlength=n_blocks)
    gt = dataset.genotypes[mask]
    rows: list[dict[str, object]] = []
    for metric in metrics:
        museum_site = site_values(gt, museum_indices, metric, rarefy_n)
        modern_site = site_values(gt, modern_indices, metric, rarefy_n)
        museum_sums = np.bincount(global_block, weights=museum_site, minlength=n_blocks)
        modern_sums = np.bincount(global_block, weights=modern_site, minlength=n_blocks)
        for block_id, (contig, block_index, start, end, opportunity) in enumerate(block_meta):
            rows.append(
                {
                    "basis": dataset.basis,
                    "variant_set": variant_set,
                    "metric": metric,
                    "chrom": contig,
                    "block_index": block_index,
                    "block_start_bp": start,
                    "block_end_bp": end,
                    "opportunity_bp": opportunity,
                    "n_sites": int(site_counts[block_id]),
                    "museum_sum": float(museum_sums[block_id]),
                    "modern_sum": float(modern_sums[block_id]),
                    "museum_n": len(museum_indices),
                    "modern_n": len(modern_indices),
                    "rarefy_n": rarefy_n if metric == "allelic_richness" else 0,
                    "denominator": "genomic_bp" if metric == "pi" else "complete_variant_sites",
                }
            )
    return rows


def block_point(blocks: pd.DataFrame, metric: str) -> tuple[float, float, float]:
    denominator = (
        float(blocks["opportunity_bp"].sum())
        if metric == "pi"
        else float(blocks["n_sites"].sum())
    )
    if denominator <= 0:
        raise ValueError(f"zero denominator for {metric}")
    museum = float(blocks["museum_sum"].sum()) / denominator
    modern = float(blocks["modern_sum"].sum()) / denominator
    return museum, modern, museum - modern


def block_bootstrap_effects(
    blocks: pd.DataFrame, metric: str, reps: int, seed: int, ci_pct: float
) -> np.ndarray:
    """Stratified 5-Mb block bootstrap, resampling blocks within chromosome."""

    groups = []
    for _chrom, frame in blocks.sort_values(["chrom", "block_index"]).groupby("chrom", sort=True):
        groups.append(
            (
                frame["museum_sum"].to_numpy(float),
                frame["modern_sum"].to_numpy(float),
                frame["n_sites"].to_numpy(float),
                frame["opportunity_bp"].to_numpy(float),
            )
        )
    rng = np.random.default_rng(seed)
    effects = np.empty(reps, dtype=float)
    for rep in range(reps):
        museum_sum = modern_sum = n_sites = opportunity = 0.0
        for museum, modern, sites, bp in groups:
            draw = rng.integers(0, len(museum), size=len(museum))
            museum_sum += float(museum[draw].sum())
            modern_sum += float(modern[draw].sum())
            n_sites += float(sites[draw].sum())
            opportunity += float(bp[draw].sum())
        denominator = opportunity if metric == "pi" else n_sites
        effects[rep] = (museum_sum - modern_sum) / denominator
    if not np.isfinite(effects).all():
        raise ValueError(f"non-finite bootstrap replicate for {metric}")
    return effects


def direction(value: float, tolerance: float = 1e-15) -> str:
    if value > tolerance:
        return "museum_higher"
    if value < -tolerance:
        return "modern_higher"
    return "equal"


def classification_table(dataset: VCFDataset, input_path: str) -> pd.DataFrame:
    leaves = ("transition", "transversion", "mnv", "indel", "multiallelic", "other")
    rows = []
    total = sum(dataset.class_counts.get(cls, 0) for cls in leaves)
    complete_total = sum(dataset.complete_counts.get(cls, 0) for cls in leaves)
    other_classes = ("mnv", "indel", "multiallelic", "other")
    for cls in leaves:
        n = int(dataset.class_counts.get(cls, 0))
        complete = int(dataset.complete_counts.get(cls, 0))
        rows.append(
            {
                "basis": dataset.basis,
                "input_path": input_path,
                "variant_class": cls,
                "n_records": n,
                "n_complete_11": complete,
                "n_incomplete_11": n - complete,
                "used_all_snp_records": complete if cls in {"transition", "transversion"} else 0,
                "used_transversion_records": complete if cls == "transversion" else 0,
                "n_samples": len(dataset.samples),
                "n_contigs_in_header": len(dataset.contig_lengths),
                "genomic_opportunity_bp": sum(dataset.contig_lengths.values()),
            }
        )
    rows.extend(
        [
            {
                "basis": dataset.basis,
                "input_path": input_path,
                "variant_class": "other_all",
                "n_records": sum(dataset.class_counts.get(cls, 0) for cls in other_classes),
                "n_complete_11": sum(dataset.complete_counts.get(cls, 0) for cls in other_classes),
                "n_incomplete_11": sum(
                    dataset.class_counts.get(cls, 0) - dataset.complete_counts.get(cls, 0)
                    for cls in other_classes
                ),
                "used_all_snp_records": 0,
                "used_transversion_records": 0,
                "n_samples": len(dataset.samples),
                "n_contigs_in_header": len(dataset.contig_lengths),
                "genomic_opportunity_bp": sum(dataset.contig_lengths.values()),
            },
            {
                "basis": dataset.basis,
                "input_path": input_path,
                "variant_class": "total",
                "n_records": total,
                "n_complete_11": complete_total,
                "n_incomplete_11": total - complete_total,
                "used_all_snp_records": dataset.n_sites,
                "used_transversion_records": int((~dataset.is_transition).sum()),
                "n_samples": len(dataset.samples),
                "n_contigs_in_header": len(dataset.contig_lengths),
                "genomic_opportunity_bp": sum(dataset.contig_lengths.values()),
            },
        ]
    )
    return pd.DataFrame(rows)


def build_permutations(
    raw: VCFDataset,
    normalized: VCFDataset,
    samples: Sequence[str],
    observed_museum: set[str],
    rarefy_n: int,
    raw_opportunity: int,
) -> pd.DataFrame:
    allocations = list(combinations(range(len(samples)), len(observed_museum)))
    if len(allocations) != 462:
        raise ValueError(f"expected C(11,5)=462 allocations, got {len(allocations)}")
    matrix = np.zeros((len(allocations), len(samples)), dtype=np.int16)
    for row, indices in enumerate(allocations):
        matrix[row, list(indices)] = 1
    labels = []
    for allocation_id, indices in enumerate(allocations):
        museum = [samples[index] for index in indices]
        modern = [sample for index, sample in enumerate(samples) if index not in indices]
        labels.append(
            (
                f"P{allocation_id:03d}",
                "|".join(museum),
                "|".join(modern),
                set(museum) == observed_museum,
            )
        )

    rows: list[dict[str, object]] = []
    for variant_set in VARIANT_SETS:
        raw_mask = np.ones(raw.n_sites, dtype=bool) if variant_set == "all_snp" else ~raw.is_transition
        norm_mask = (
            np.ones(normalized.n_sites, dtype=bool)
            if variant_set == "all_snp"
            else ~normalized.is_transition
        )
        datasets = [
            (aggregate_patterns(raw.genotypes[raw_mask]), ("pi",), raw_opportunity),
            (
                aggregate_patterns(normalized.genotypes[norm_mask]),
                ("Ho", "He", "allelic_richness"),
                0,
            ),
        ]
        for summary, metrics, opportunity in datasets:
            values = allocation_values_from_patterns(
                summary, matrix, metrics, rarefy_n, opportunity
            )
            for metric in metrics:
                museum_values, modern_values = values[metric]
                for allocation_index, label in enumerate(labels):
                    effect = float(museum_values[allocation_index] - modern_values[allocation_index])
                    rows.append(
                        {
                            "allocation_id": label[0],
                            "museum_samples": label[1],
                            "modern_samples": label[2],
                            "is_observed_allocation": bool(label[3]),
                            "variant_set": variant_set,
                            "metric": metric,
                            "basis": METRIC_BASIS[metric],
                            "museum_n": len(observed_museum),
                            "modern_n": len(samples) - len(observed_museum),
                            "rarefy_n": rarefy_n if metric == "allelic_richness" else 0,
                            "n_sites": summary.n_sites,
                            "museum_value": float(museum_values[allocation_index]),
                            "modern_value": float(modern_values[allocation_index]),
                            "effect_museum_minus_modern": effect,
                            "direction": direction(effect),
                        }
                    )
    return pd.DataFrame(rows).sort_values(
        ["allocation_id", "variant_set", "metric"]
    ).reset_index(drop=True)


def build_influence(
    raw: VCFDataset,
    normalized: VCFDataset,
    samples: Sequence[str],
    museum_samples: Sequence[str],
    modern_samples: Sequence[str],
    rarefy_n: int,
    raw_opportunity: int,
    baseline_direction: dict[tuple[str, str], str],
) -> pd.DataFrame:
    sample_to_index = {sample: index for index, sample in enumerate(samples)}
    summaries: dict[tuple[str, str], PatternSummary] = {}
    for variant_set in VARIANT_SETS:
        summaries[("raw", variant_set)] = aggregate_patterns(
            raw.genotypes if variant_set == "all_snp" else raw.genotypes[~raw.is_transition]
        )
        summaries[("normalized", variant_set)] = aggregate_patterns(
            normalized.genotypes
            if variant_set == "all_snp"
            else normalized.genotypes[~normalized.is_transition]
        )

    scenarios: list[tuple[str, str, str, str, list[str], list[str]]] = []
    for index, left_out in enumerate(modern_samples, start=1):
        scenarios.append(
            (
                f"E{index:02d}",
                "equal_n_modern_leave_one",
                left_out,
                "modern",
                list(museum_samples),
                [sample for sample in modern_samples if sample != left_out],
            )
        )
    for index, left_out in enumerate(samples, start=1):
        group = "museum" if left_out in museum_samples else "modern"
        scenarios.append(
            (
                f"L{index:02d}",
                "leave_one_individual",
                left_out,
                group,
                [sample for sample in museum_samples if sample != left_out],
                [sample for sample in modern_samples if sample != left_out],
            )
        )

    rows = []
    for case_id, case_type, left_out, left_out_group, museum, modern in scenarios:
        museum_indices = [sample_to_index[sample] for sample in museum]
        modern_indices = [sample_to_index[sample] for sample in modern]
        scenario_rarefy = min(rarefy_n, len(museum), len(modern))
        for variant_set in VARIANT_SETS:
            for metric in METRICS:
                summary = summaries[("raw" if metric == "pi" else "normalized", variant_set)]
                museum_value, modern_value = group_values_from_patterns(
                    summary,
                    museum_indices,
                    modern_indices,
                    metric,
                    scenario_rarefy,
                    raw_opportunity,
                )
                effect = museum_value - modern_value
                observed_direction = direction(effect)
                rows.append(
                    {
                        "case_id": case_id,
                        "case_type": case_type,
                        "left_out_sample": left_out,
                        "left_out_group": left_out_group,
                        "museum_samples": "|".join(museum),
                        "modern_samples": "|".join(modern),
                        "museum_n": len(museum),
                        "modern_n": len(modern),
                        "rarefy_n": scenario_rarefy if metric == "allelic_richness" else 0,
                        "variant_set": variant_set,
                        "metric": metric,
                        "basis": METRIC_BASIS[metric],
                        "n_sites": summary.n_sites,
                        "museum_value": museum_value,
                        "modern_value": modern_value,
                        "effect_museum_minus_modern": effect,
                        "direction": observed_direction,
                        "same_direction_as_baseline": observed_direction
                        == baseline_direction[(variant_set, metric)],
                    }
                )
    return pd.DataFrame(rows).sort_values(
        ["case_type", "case_id", "variant_set", "metric"]
    ).reset_index(drop=True)


def build_effects(
    blocks: pd.DataFrame,
    permutations: pd.DataFrame,
    influence: pd.DataFrame,
    seed: int,
    reps: int,
    ci_pct: float,
    upgrade_min_metrics: int,
) -> pd.DataFrame:
    rows = []
    alpha = (100.0 - ci_pct) / 2.0
    for variant_set in VARIANT_SETS:
        for metric in METRICS:
            frame = blocks[
                (blocks["variant_set"] == variant_set) & (blocks["metric"] == metric)
            ].copy()
            museum, modern, effect = block_point(frame, metric)
            bootstrap_seed = seed + VARIANT_SEED_CODE[variant_set] + METRIC_SEED_CODE[metric]
            replicates = block_bootstrap_effects(frame, metric, reps, bootstrap_seed, ci_pct)
            ci_low, ci_high = np.percentile(replicates, [alpha, 100.0 - alpha])
            perm = permutations[
                (permutations["variant_set"] == variant_set)
                & (permutations["metric"] == metric)
            ]
            observed = perm[perm["is_observed_allocation"]]
            if len(observed) != 1 or not np.isclose(
                float(observed.iloc[0]["effect_museum_minus_modern"]), effect, rtol=1e-10, atol=1e-15
            ):
                raise ValueError(f"observed allocation/block point mismatch: {variant_set}/{metric}")
            # The exact reference is defined on the 462 allocation values.
            # Use its observed allocation as the comparison threshold, rather
            # than the algebraically identical block-summed point whose final
            # floating addition can differ by a few ulps at tied allocations.
            observed_permutation_effect = float(
                observed.iloc[0]["effect_museum_minus_modern"]
            )
            perm_effects = perm["effect_museum_minus_modern"].to_numpy(float)
            exact_p = float(
                np.mean(
                    np.abs(perm_effects)
                    >= abs(observed_permutation_effect) - 1e-15
                )
            )
            percentile = float(
                (
                    np.sum(perm_effects < observed_permutation_effect)
                    + 0.5
                    * np.sum(
                        np.isclose(perm_effects, observed_permutation_effect)
                    )
                )
                / len(perm_effects)
            )
            inf = influence[
                (influence["variant_set"] == variant_set) & (influence["metric"] == metric)
            ]
            equal_n = inf[inf["case_type"] == "equal_n_modern_leave_one"]
            leave_one = inf[inf["case_type"] == "leave_one_individual"]
            baseline_dir = direction(effect)
            rows.append(
                {
                    "analysis_id": f"{variant_set}__{metric}",
                    "variant_set": variant_set,
                    "metric": metric,
                    "basis": METRIC_BASIS[metric],
                    "museum_n": int(frame["museum_n"].iloc[0]),
                    "modern_n": int(frame["modern_n"].iloc[0]),
                    "rarefy_n": int(frame["rarefy_n"].max()),
                    "n_sites": int(frame["n_sites"].sum()),
                    "opportunity_bp": int(frame["opportunity_bp"].sum()) if metric == "pi" else 0,
                    "museum_value": museum,
                    "modern_value": modern,
                    "effect_museum_minus_modern": effect,
                    "ci_pct": ci_pct,
                    "ci_low": float(ci_low),
                    "ci_high": float(ci_high),
                    "bootstrap_reps": reps,
                    "bootstrap_seed": bootstrap_seed,
                    "direction": baseline_dir,
                    "exact_permutation_p_two_sided": exact_p,
                    "exact_permutation_percentile": percentile,
                    "n_exact_allocations": int(perm["allocation_id"].nunique()),
                    "equal_n_same_direction_n": int((equal_n["direction"] == baseline_dir).sum()),
                    "equal_n_cases_n": int(len(equal_n)),
                    "leave_one_same_direction_n": int((leave_one["direction"] == baseline_dir).sum()),
                    "leave_one_cases_n": int(len(leave_one)),
                    "equal_n_effect_min": float(equal_n["effect_museum_minus_modern"].min()),
                    "equal_n_effect_max": float(equal_n["effect_museum_minus_modern"].max()),
                    "leave_one_effect_min": float(leave_one["effect_museum_minus_modern"].min()),
                    "leave_one_effect_max": float(leave_one["effect_museum_minus_modern"].max()),
                    "geographic_mismatch_caveat": True,
                }
            )
    effects = pd.DataFrame(rows)
    direction_map = effects.set_index(["variant_set", "metric"])["direction"].to_dict()
    effects["same_direction_all_snp_vs_transversion"] = [
        direction_map[("all_snp", metric)] == direction_map[("transversion_only", metric)]
        for metric in effects["metric"]
    ]
    concordant_by_set = {}
    stability_by_set = {}
    for variant_set in VARIANT_SETS:
        sub = effects[effects["variant_set"] == variant_set]
        positive_metrics = int((sub["direction"] == "museum_higher").sum())
        concordant_by_set[variant_set] = positive_metrics
        stability_by_set[variant_set] = bool(
            positive_metrics >= upgrade_min_metrics
            and (sub["equal_n_same_direction_n"] == sub["equal_n_cases_n"]).all()
            and (sub["leave_one_same_direction_n"] == sub["leave_one_cases_n"]).all()
        )
    effects["museum_higher_concordant_metrics_n"] = effects["variant_set"].map(concordant_by_set)
    # The claim is global, not variant-set specific: an all-SNP result cannot
    # upgrade the temporal interpretation if its transversion stress test
    # fails (or vice versa).  Every row therefore carries the same deliberately
    # conservative global decision for easy downstream integration.
    directional_condition_met = bool(
        all(stability_by_set.values())
        and effects["same_direction_all_snp_vs_transversion"].all()
    )
    # Even perfect directional robustness cannot resolve the pre-existing
    # geographic confounding of these deposited museum and modern samples.
    # Keep the numerical falsifier visible in the preceding columns, while
    # vetoing a causal temporal-erosion upgrade unless that limitation is ever
    # genuinely removed by a different design.
    effects["supports_temporal_erosion_upgrade"] = bool(
        directional_condition_met and not effects["geographic_mismatch_caveat"].any()
    )
    return effects.sort_values(["variant_set", "metric"]).reset_index(drop=True)


def build_figure_values(effects: pd.DataFrame, influence: pd.DataFrame) -> pd.DataFrame:
    rows = []
    metric_order = {metric: index for index, metric in enumerate(METRICS)}
    variant_offset = {"all_snp": -0.12, "transversion_only": 0.12}
    for _, row in effects.iterrows():
        modern = float(row["modern_value"])
        scale = 100.0 / modern if modern != 0 else np.nan
        rows.append(
            {
                "panel": "forest",
                "series_id": f"{row['variant_set']}__{row['metric']}",
                "case_id": "baseline",
                "case_type": "baseline",
                "variant_set": row["variant_set"],
                "metric": row["metric"],
                "x_order": metric_order[row["metric"]] + variant_offset[row["variant_set"]],
                "label": row["metric"],
                "estimate": row["effect_museum_minus_modern"],
                "ci_low": row["ci_low"],
                "ci_high": row["ci_high"],
                "display_effect_pct_of_modern": float(row["effect_museum_minus_modern"]) * scale,
                "display_ci_low_pct_of_modern": float(row["ci_low"]) * scale,
                "display_ci_high_pct_of_modern": float(row["ci_high"]) * scale,
            }
        )
    case_order = {
        case_id: index
        for index, case_id in enumerate(
            list(influence[influence["case_type"] == "equal_n_modern_leave_one"]["case_id"].drop_duplicates())
            + list(influence[influence["case_type"] == "leave_one_individual"]["case_id"].drop_duplicates()),
            start=1,
        )
    }
    for _, row in influence.iterrows():
        modern = float(row["modern_value"])
        rows.append(
            {
                "panel": "influence",
                "series_id": f"{row['variant_set']}__{row['metric']}",
                "case_id": row["case_id"],
                "case_type": row["case_type"],
                "variant_set": row["variant_set"],
                "metric": row["metric"],
                "x_order": case_order[row["case_id"]],
                "label": row["left_out_sample"],
                "estimate": row["effect_museum_minus_modern"],
                "ci_low": np.nan,
                "ci_high": np.nan,
                "display_effect_pct_of_modern": (
                    100.0 * float(row["effect_museum_minus_modern"]) / modern
                    if modern != 0
                    else np.nan
                ),
                "display_ci_low_pct_of_modern": np.nan,
                "display_ci_high_pct_of_modern": np.nan,
            }
        )
    return pd.DataFrame(rows)


def plot_figure(values: pd.DataFrame, output: str) -> str:
    # Keep Matplotlib cache out of the repository/home directory in restricted
    # workflow runs, and avoid importing the plotting stack for self-tests.
    mpl_cache = Path(tempfile.gettempdir()) / "cg-matplotlib"
    mpl_cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))
    import matplotlib  # noqa: WPS433

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: WPS433

    colors = {
        "pi": "#31688e",
        "Ho": "#35b779",
        "He": "#fde725",
        "allelic_richness": "#7b3294",
    }
    markers = {"all_snp": "o", "transversion_only": "s"}
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.8), gridspec_kw={"width_ratios": [0.9, 1.7]})
    forest = values[values["panel"] == "forest"]
    for _, row in forest.iterrows():
        y = float(row["x_order"])
        estimate = float(row["display_effect_pct_of_modern"])
        low = float(row["display_ci_low_pct_of_modern"])
        high = float(row["display_ci_high_pct_of_modern"])
        # Percentile intervals need not contain the point estimate.  Draw the
        # interval explicitly so that such a scientifically valid outcome is
        # not rejected by Matplotlib's non-negative ``xerr`` requirement.
        axes[0].plot([low, high], [y, y], color=colors[row["metric"]], linewidth=1.2)
        axes[0].plot(
            estimate,
            y,
            marker=markers[row["variant_set"]],
            linestyle="none",
            color=colors[row["metric"]],
            markeredgecolor="black",
            markersize=6,
        )
    axes[0].axvline(0, color="#555555", linestyle=":", linewidth=1)
    axes[0].set_yticks(range(len(METRICS)))
    axes[0].set_yticklabels(METRICS)
    axes[0].set_xlabel("Museum − modern (% of modern point value)\n95% chromosome-block bootstrap CI")
    axes[0].set_title("Baseline effect forest")

    influence = values[values["panel"] == "influence"]
    for (variant_set, metric), frame in influence.groupby(["variant_set", "metric"], sort=False):
        axes[1].scatter(
            frame["x_order"],
            frame["display_effect_pct_of_modern"],
            s=18,
            marker=markers[variant_set],
            facecolors=colors[metric] if variant_set == "all_snp" else "none",
            edgecolors=colors[metric],
            linewidths=0.9,
            alpha=0.85,
        )
    axes[1].axhline(0, color="#555555", linestyle=":", linewidth=1)
    boundary = influence[influence["case_type"] == "equal_n_modern_leave_one"]["x_order"].max()
    axes[1].axvline(float(boundary) + 0.5, color="#aaaaaa", linewidth=1)
    case_labels = (
        influence[["x_order", "case_id", "label"]]
        .drop_duplicates("x_order")
        .sort_values("x_order")
    )
    axes[1].set_xticks(case_labels["x_order"])
    axes[1].set_xticklabels(case_labels["case_id"], rotation=90, fontsize=7)
    axes[1].set_ylabel("Museum − modern (% of scenario modern value)")
    axes[1].set_xlabel("E = equal-n modern omission; L = leave one individual")
    axes[1].set_title("Single-individual influence")
    legend_handles = [
        plt.Line2D([], [], marker="o", linestyle="none", color=colors[m], label=m, markersize=6)
        for m in METRICS
    ] + [
        plt.Line2D([], [], marker="o", linestyle="none", color="black", label="all SNP", markersize=6),
        plt.Line2D(
            [], [], marker="s", markerfacecolor="none", linestyle="none", color="black",
            label="transversions", markersize=6
        ),
    ]
    axes[1].legend(handles=legend_handles, frameon=False, fontsize=7, ncol=2, loc="best")
    fig.suptitle(
        "Damage-aware peafowl museum–modern falsification\n"
        "Complete-call shared SNPs; geographic mismatch still limits temporal interpretation",
        fontsize=11,
    )
    fig.tight_layout()
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output,
        dpi=170,
        bbox_inches="tight",
        metadata={"Software": "Conservation Genomics Phase 5B"},
    )
    plt.close(fig)
    return str(matplotlib.__version__)


def write_table(frame: pd.DataFrame, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, sep="\t", index=False, float_format="%.17g", na_rep="NA")


def run_analysis(args: argparse.Namespace) -> None:
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    settings = cfg["phase5b"]["damage_falsification"]
    transition_pairs = {str(value).upper() for value in settings["transition_pairs"]}
    expected_pairs = {"C>T", "T>C", "G>A", "A>G"}
    if transition_pairs != expected_pairs:
        raise ValueError(
            "transition-pair setting must be the damage-aware four: "
            f"{sorted(transition_pairs)}"
        )
    seed = int(settings["seed"])
    reps = int(settings["bootstrap_reps"])
    ci_pct = float(settings["ci_pct"])
    block_size = int(settings["block_size_bp"])
    rarefy_n = int(settings["rarefy_n"])
    upgrade_min = int(settings["upgrade_min_concordant_metrics"])

    popmap = pd.read_csv(args.popmap, sep="\t")
    if list(popmap.columns[:2]) != ["sample", "population"]:
        popmap = popmap.iloc[:, :2].copy()
        popmap.columns = ["sample", "population"]
    if popmap["sample"].duplicated().any() or len(popmap) != 11:
        raise ValueError("temporal popmap must contain 11 unique samples")
    museum_samples = popmap.loc[popmap["population"] == "museum", "sample"].tolist()
    modern_samples = popmap.loc[popmap["population"] == "modern", "sample"].tolist()
    if (len(museum_samples), len(modern_samples)) != (5, 6):
        raise ValueError(f"expected museum/modern n=5/6, got {len(museum_samples)}/{len(modern_samples)}")
    samples = popmap["sample"].tolist()
    autosomes = read_autosomes(args.autosomes)

    raw = load_vcf(args.raw_vcf, "raw_comparative", samples, transition_pairs)
    normalized = load_vcf(
        args.normalized_vcf,
        "normalized_comparative",
        samples,
        transition_pairs,
        allowed_contigs=set(autosomes),
    )
    sample_to_index = {sample: index for index, sample in enumerate(samples)}
    museum_indices = [sample_to_index[sample] for sample in museum_samples]
    modern_indices = [sample_to_index[sample] for sample in modern_samples]
    raw_contigs = list(raw.contig_names)
    raw_opportunity = sum(raw.contig_lengths[contig] for contig in raw_contigs)

    classification = pd.concat(
        [classification_table(raw, args.raw_vcf), classification_table(normalized, args.normalized_vcf)],
        ignore_index=True,
    )
    block_rows: list[dict[str, object]] = []
    baseline_direction: dict[tuple[str, str], str] = {}
    for variant_set in VARIANT_SETS:
        raw_mask = np.ones(raw.n_sites, dtype=bool) if variant_set == "all_snp" else ~raw.is_transition
        norm_mask = (
            np.ones(normalized.n_sites, dtype=bool)
            if variant_set == "all_snp"
            else ~normalized.is_transition
        )
        block_rows.extend(
            make_block_rows(
                raw,
                raw_contigs,
                raw_mask,
                variant_set,
                ("pi",),
                museum_indices,
                modern_indices,
                rarefy_n,
                block_size,
            )
        )
        block_rows.extend(
            make_block_rows(
                normalized,
                autosomes,
                norm_mask,
                variant_set,
                ("Ho", "He", "allelic_richness"),
                museum_indices,
                modern_indices,
                rarefy_n,
                block_size,
            )
        )
    blocks = pd.DataFrame(block_rows).sort_values(
        ["basis", "variant_set", "metric", "chrom", "block_index"]
    ).reset_index(drop=True)
    for variant_set in VARIANT_SETS:
        for metric in METRICS:
            frame = blocks[(blocks["variant_set"] == variant_set) & (blocks["metric"] == metric)]
            baseline_direction[(variant_set, metric)] = direction(block_point(frame, metric)[2])

    permutations = build_permutations(
        raw, normalized, samples, set(museum_samples), rarefy_n, raw_opportunity
    )
    influence = build_influence(
        raw,
        normalized,
        samples,
        museum_samples,
        modern_samples,
        rarefy_n,
        raw_opportunity,
        baseline_direction,
    )
    effects = build_effects(blocks, permutations, influence, seed, reps, ci_pct, upgrade_min)
    figure_values = build_figure_values(effects, influence)

    outputs = {
        "effects": args.out_effects,
        "permutations": args.out_permutations,
        "influence": args.out_influence,
        "blocks": args.out_blocks,
        "classification": args.out_classification,
        "figure_values": args.out_figure_values,
        "figure": args.out_figure,
        "provenance": args.out_provenance,
    }
    for frame, key in [
        (effects, "effects"),
        (permutations, "permutations"),
        (influence, "influence"),
        (blocks, "blocks"),
        (classification, "classification"),
        (figure_values, "figure_values"),
    ]:
        write_table(frame, outputs[key])
    matplotlib_version = plot_figure(figure_values, outputs["figure"])

    provenance = {
        "schema_version": "1.0",
        "analysis": "phase5b_peafowl_damage_falsification",
        "question": "Does the weak museum-higher diversity direction survive damage-aware and individual-influence stress tests?",
        "settings": {
            "seed": seed,
            "bootstrap_reps": reps,
            "ci_pct": ci_pct,
            "block_size_bp": block_size,
            "rarefy_n": rarefy_n,
            "transition_pairs": sorted(transition_pairs),
            "exact_allocations": 462,
            "upgrade_min_concordant_metrics": upgrade_min,
        },
        "samples": {
            "order": samples,
            "museum": museum_samples,
            "modern": modern_samples,
            "museum_n": len(museum_samples),
            "modern_n": len(modern_samples),
        },
        "basis": {
            "pi": {
                "input": args.raw_vcf,
                "definition": "sum of unbiased pairwise-difference contributions at complete-call biallelic SNPs divided by all raw-VCF contig-length base pairs",
                "genomic_opportunity_bp": raw_opportunity,
            },
            "Ho_He_allelic_richness": {
                "input": args.normalized_vcf,
                "definition": "complete-call biallelic autosomal SNPs from the existing normalized comparative basis",
            },
            "exact_relabeling": "Each basis is frozen to sites called in all 11 birds before any of the 462 label allocations; labels never alter site inclusion.",
            "allelic_richness": "Analytical hypergeometric rarefaction without Monte Carlo sampling; baseline n=5, leave-one-museum cases n=4.",
        },
        "variant_handling": {
            "all_snp": "transition plus transversion biallelic single-base SNPs",
            "transversion_only": "biallelic single-base SNPs excluding C<->T and G<->A transitions",
            "other_records": "MNV, indel, multiallelic, and symbolic/other records are reconciled in the classification table and excluded from SNP metrics.",
        },
        "bootstrap": "999 seeded 5-Mb blocks, resampled with replacement within chromosome; terminal blocks retain their recorded opportunity length.",
        "exact_permutation": "All C(11,5)=462 label allocations; genotype patterns are base-3 aggregated and evaluated in bounded matrix batches.",
        "caveats": [
            "Museum and modern birds are geographically mismatched; no outcome can isolate time from geography.",
            "Ancient-DNA damage reduction by transversion filtering does not remove all museum-specific technical bias.",
            "Genomic diversity differences are associations in deposited samples, not fitness effects or causal temporal erosion.",
        ],
        "numeric_falsifier": {
            "claim": "museum-higher temporal-erosion direction",
            "directional_condition": f"All {upgrade_min} metrics must remain museum-higher after every predeclared all-SNP/transversion, six equal-n, and 11 leave-one stress test.",
            "claim_upgrade_condition": "The directional condition must pass and the museum-modern geographic mismatch must be resolved by the study design.",
            "observed_concordant_metrics": {
                variant_set: int(
                    effects.loc[
                        effects["variant_set"] == variant_set,
                        "museum_higher_concordant_metrics_n",
                    ].iloc[0]
                )
                for variant_set in VARIANT_SETS
            },
            "directional_condition_met_before_design_limitations": bool(
                all(
                    int(
                        effects.loc[
                            effects["variant_set"] == variant_set,
                            "museum_higher_concordant_metrics_n",
                        ].iloc[0]
                    )
                    >= upgrade_min
                    for variant_set in VARIANT_SETS
                )
                and effects["same_direction_all_snp_vs_transversion"].all()
                and (effects["equal_n_same_direction_n"] == effects["equal_n_cases_n"]).all()
                and (effects["leave_one_same_direction_n"] == effects["leave_one_cases_n"]).all()
            ),
            "upgrade_supported": {
                variant_set: bool(
                    effects.loc[
                        effects["variant_set"] == variant_set,
                        "supports_temporal_erosion_upgrade",
                    ].iloc[0]
                )
                for variant_set in VARIANT_SETS
            },
        },
        "inputs": {
            "raw_vcf": {"path": args.raw_vcf, "sha256": sha256_file(args.raw_vcf)},
            "normalized_vcf": {
                "path": args.normalized_vcf,
                "sha256": sha256_file(args.normalized_vcf),
            },
            "popmap": {"path": args.popmap, "sha256": sha256_file(args.popmap)},
            "autosomes": {"path": args.autosomes, "sha256": sha256_file(args.autosomes)},
            "config": {"path": args.config, "sha256": sha256_file(args.config)},
        },
        "outputs": {
            key: {"path": path, "sha256": sha256_file(path)}
            for key, path in outputs.items()
            if key != "provenance"
        },
        "software": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "matplotlib": matplotlib_version,
        },
    }
    Path(args.out_provenance).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_provenance).write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"peafowl damage falsification: {len(effects)} effects, "
        f"{permutations['allocation_id'].nunique()} allocations/{len(permutations)} outcomes, "
        f"{len(influence)} influence outcomes, {len(blocks)} block rows"
    )
    for _, row in effects.iterrows():
        print(
            f"  {row['variant_set']} {row['metric']}: museum-modern="
            f"{row['effect_museum_minus_modern']:.6g} "
            f"({row['ci_pct']:.0f}% CI {row['ci_low']:.6g}, {row['ci_high']:.6g}); "
            f"exact p={row['exact_permutation_p_two_sided']:.4f}"
        )


def self_test() -> None:
    transition_pairs = {"C>T", "T>C", "G>A", "A>G"}
    assert sorted(transition_pairs) == ["A>G", "C>T", "G>A", "T>C"]
    assert variant_class("C", "T", transition_pairs) == "transition"
    assert variant_class("A", "C", transition_pairs) == "transversion"
    assert variant_class("AC", "GT", transition_pairs) == "mnv"
    assert variant_class("A", "AT", transition_pairs) == "indel"
    assert variant_class("A", "C,G", transition_pairs) == "multiallelic"
    gt = np.asarray(
        [
            [0, 0, 1, 2],
            [0, 1, 1, 2],
            [2, 2, 1, 0],
            [0, 2, 0, 2],
        ],
        dtype=np.uint8,
    )
    summary = aggregate_patterns(gt)
    for metric in METRICS:
        rarefy = 2
        direct_m = site_values(gt, [0, 1], metric, rarefy).mean()
        direct_o = site_values(gt, [2, 3], metric, rarefy).mean()
        opportunity = gt.shape[0]
        pattern_m, pattern_o = group_values_from_patterns(
            summary, [0, 1], [2, 3], metric, rarefy, opportunity
        )
        assert np.isclose(direct_m, pattern_m)
        assert np.isclose(direct_o, pattern_o)
    ar = analytical_ar_lookup(5, 5)
    assert ar[0] == 1.0 and ar[-1] == 1.0 and ar[5] == 2.0
    blocks = pd.DataFrame(
        {
            "chrom": ["a", "a", "b"],
            "block_index": [0, 1, 0],
            "museum_sum": [1.0, 2.0, 3.0],
            "modern_sum": [0.5, 1.5, 2.5],
            "n_sites": [2, 2, 2],
            "opportunity_bp": [5, 5, 5],
        }
    )
    first = block_bootstrap_effects(blocks, "He", 20, 7, 95)
    second = block_bootstrap_effects(blocks, "He", 20, 7, 95)
    assert np.array_equal(first, second)

    # Exercise the complete table-building path on a tiny in-memory 11-bird
    # dataset.  This catches schema/cartesian-product regressions without
    # reading source data or writing any analysis artifact.
    samples = tuple([f"m{i}" for i in range(5)] + [f"n{i}" for i in range(6)])
    positions = np.asarray([1, 2, 11, 12, 1, 2, 11, 12], dtype=np.uint32)
    chrom_id = np.asarray([0, 0, 0, 0, 1, 1, 1, 1], dtype=np.uint16)
    tiny_gt = np.asarray(
        [[(site + sample) % 3 for sample in range(11)] for site in range(8)],
        dtype=np.uint8,
    )
    tiny_transition = np.asarray([True, False] * 4)
    tiny = VCFDataset(
        basis="raw_comparative",
        path="in-memory",
        samples=samples,
        contig_names=("a", "b"),
        contig_lengths={"a": 20, "b": 20},
        chrom_id=chrom_id,
        position=positions,
        genotypes=tiny_gt,
        is_transition=tiny_transition,
        class_counts={"transition": 4, "transversion": 4},
        complete_counts={"transition": 4, "transversion": 4},
    )
    tiny_norm = VCFDataset(**{**tiny.__dict__, "basis": "normalized_comparative"})
    museum_indices = list(range(5))
    modern_indices = list(range(5, 11))
    block_rows: list[dict[str, object]] = []
    for variant_set, mask in (
        ("all_snp", np.ones(8, dtype=bool)),
        ("transversion_only", ~tiny_transition),
    ):
        block_rows.extend(
            make_block_rows(
                tiny, ("a", "b"), mask, variant_set, ("pi",),
                museum_indices, modern_indices, 5, 10,
            )
        )
        block_rows.extend(
            make_block_rows(
                tiny_norm, ("a", "b"), mask, variant_set,
                ("Ho", "He", "allelic_richness"), museum_indices,
                modern_indices, 5, 10,
            )
        )
    tiny_blocks = pd.DataFrame(block_rows)
    baseline = {
        (variant_set, metric): direction(
            block_point(
                tiny_blocks[
                    tiny_blocks["variant_set"].eq(variant_set)
                    & tiny_blocks["metric"].eq(metric)
                ],
                metric,
            )[2]
        )
        for variant_set in VARIANT_SETS
        for metric in METRICS
    }
    tiny_permutations = build_permutations(tiny, tiny_norm, samples, set(samples[:5]), 5, 40)
    tiny_influence = build_influence(
        tiny, tiny_norm, samples, samples[:5], samples[5:], 5, 40, baseline
    )
    tiny_effects = build_effects(
        tiny_blocks, tiny_permutations, tiny_influence, 1303, 20, 95, 4
    )
    tiny_figure_values = build_figure_values(tiny_effects, tiny_influence)
    assert len(tiny_permutations) == 462 * 8
    assert len(tiny_influence) == 17 * 8
    assert len(tiny_effects) == 8
    assert len(tiny_figure_values) == 8 + 17 * 8
    assert not tiny_effects["supports_temporal_erosion_upgrade"].any()
    print("peafowl_damage_falsification self-test: OK")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--raw-vcf", default="data/peafowl/raw/Comparative_genomic_dataset_F.vcf.gz")
    parser.add_argument("--normalized-vcf", default="results/qc/comparative.norm.vcf.gz")
    parser.add_argument("--popmap", default="results/qc/temporal_popmap.tsv")
    parser.add_argument("--autosomes", default="config/peafowl_autosomes.txt")
    parser.add_argument("--out-effects", default=DEFAULT_OUTPUTS["effects"])
    parser.add_argument("--out-permutations", default=DEFAULT_OUTPUTS["permutations"])
    parser.add_argument("--out-influence", default=DEFAULT_OUTPUTS["influence"])
    parser.add_argument("--out-blocks", default=DEFAULT_OUTPUTS["blocks"])
    parser.add_argument("--out-classification", default=DEFAULT_OUTPUTS["classification"])
    parser.add_argument("--out-figure-values", default=DEFAULT_OUTPUTS["figure_values"])
    parser.add_argument("--out-figure", default=DEFAULT_OUTPUTS["figure"])
    parser.add_argument("--out-provenance", default=DEFAULT_OUTPUTS["provenance"])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    run_analysis(args)


if __name__ == "__main__":
    main()
