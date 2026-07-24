#!/usr/bin/env python3
"""Resolve the Phase-5B optional wolf studies with auditable numeric gates.

Section 13.4 is a conditional analysis, not an automatic extra computation.  Its
gate is evaluated from the formal Section-13.1 negative-control rows.  Section
13.5 is reviewed against the exact deposited annotation classes and the source
paper; recomputing the same definitions from the same samples is deferred when
the local inventory proves that it would duplicate the source analysis.

The review is intentionally offline at workflow run time.  The primary-source
claims recorded below were checked against Smeds & Ellegren (2023), Molecular
Ecology, DOI 10.1111/mec.16802, on 2026-07-19.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml


SOURCE_DOI = "https://doi.org/10.1111/mec.16802"
DRYAD_DOI = "https://doi.org/10.5061/dryad.7m0cfxpzj"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def vcf_samples(path: Path) -> list[str]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("#CHROM"):
                return line.rstrip("\n").split("\t")[9:]
    raise ValueError(f"VCF has no #CHROM header: {path}")


def choose_column(frame: pd.DataFrame, candidates: tuple[str, ...], label: str) -> str:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    raise ValueError(f"association table lacks {label}; tried {candidates}")


def partial_realized_rows(frame: pd.DataFrame) -> tuple[pd.DataFrame, str, str, str]:
    model_col = choose_column(frame, ("analysis", "model", "control_model"), "model column")
    metric_col = choose_column(frame, ("load_metric", "metric", "outcome"), "metric column")
    estimate_col = choose_column(
        frame, ("coefficient", "rho", "spearman_rho", "estimate"), "coefficient column"
    )
    ci_low_col = choose_column(frame, ("ci_low", "bootstrap_ci_low", "lower_ci"), "CI-low column")
    model = frame[model_col].astype(str).str.lower()
    metric = frame[metric_col].astype(str).str.lower()
    rows = frame.loc[
        model.str.contains("partial|negative") & metric.str.contains("realized")
    ].copy()
    if rows.empty:
        raise ValueError("no partial/negative-control realized-load rows in association table")
    return rows, estimate_col, ci_low_col, model_col


def annotation_inventory(vep_path: Path, sift_path: Path) -> pd.DataFrame:
    vep = pd.read_csv(vep_path, sep="\t", dtype={"CHROM": str})
    sift = pd.read_csv(sift_path, sep="\t", dtype={"CHROM": str})
    required_vep = {"CHROM", "POS", "VEP_TYPE"}
    required_sift = {"CHROM", "POS", "SIFT_TYPE"}
    if required_vep - set(vep.columns) or required_sift - set(sift.columns):
        raise ValueError("annotation inventory files have unexpected schemas")
    if vep.duplicated(["CHROM", "POS"]).any() or sift.duplicated(["CHROM", "POS"]).any():
        raise ValueError("annotation inventory contains duplicate CHROM/POS keys")

    records: list[dict[str, object]] = []
    for definition, frame, class_col in (
        ("VEP", vep, "VEP_TYPE"),
        ("SIFT", sift, "SIFT_TYPE"),
    ):
        for scope, subset in (
            ("autosomes_plus_X", frame),
            ("autosomes_1_38", frame.loc[frame["CHROM"].ne("X")]),
        ):
            for annotation_class, count in subset.groupby(class_col).size().sort_index().items():
                records.append(
                    {
                        "definition": definition,
                        "scope": scope,
                        "annotation_class": annotation_class,
                        "n_unique_sites": int(count),
                        "duplicate_site_keys": 0,
                        "source_file": str(vep_path if definition == "VEP" else sift_path),
                    }
                )
    return pd.DataFrame(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--associations", required=True)
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--wolf-load", default="results/tables/wolf_load.tsv")
    parser.add_argument(
        "--coding-vcf",
        default="data/wolf/vcf/Pol.2out.mac2/100S95F14R.chr1-38.vepfinal.wfm.vcf.gz",
    )
    parser.add_argument(
        "--vep", default="data/wolf/vep/Pol.2out.mac2/veptypes.chr1-X.txt"
    )
    parser.add_argument(
        "--sift", default="data/wolf/vep/Pol.2out.mac2/sifttypes.chr1-X.txt"
    )
    parser.add_argument("--out-decisions", required=True)
    parser.add_argument("--out-inventory", required=True)
    parser.add_argument("--out-provenance", required=True)
    args = parser.parse_args()

    paths = {
        "associations": Path(args.associations),
        "config": Path(args.config),
        "wolf_load": Path(args.wolf_load),
        "coding_vcf": Path(args.coding_vcf),
        "vep": Path(args.vep),
        "sift": Path(args.sift),
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing decision input(s): {missing}")

    cfg = yaml.safe_load(paths["config"].read_text(encoding="utf-8"))
    min_cells = int(cfg["phase5b"]["wolf_robustness"]["roh_localization_reopen_min_cells"])
    assoc = pd.read_csv(paths["associations"], sep="\t")
    partial, estimate_col, ci_low_col, _model_col = partial_realized_rows(assoc)
    cell_cols = [column for column in ("THRES", "gerp_threshold", "min_length_mb", "roh_cutoff_mb") if column in partial]
    n_cells = len(partial.drop_duplicates(cell_cols)) if cell_cols else len(partial)
    if n_cells != 15:
        raise ValueError(f"expected 15 negative-control realized cells, found {n_cells}")
    estimates = pd.to_numeric(partial[estimate_col], errors="raise")
    ci_lows = pd.to_numeric(partial[ci_low_col], errors="raise")
    n_positive = int((estimates > 0).sum())
    n_ci_positive = int((ci_lows > 0).sum())
    localization_pass = n_ci_positive >= min_cells

    inventory = annotation_inventory(paths["vep"], paths["sift"])
    auto_counts = (
        inventory.loc[inventory["scope"].eq("autosomes_1_38")]
        .set_index(["definition", "annotation_class"])["n_unique_sites"]
        .to_dict()
    )
    expected = {
        ("VEP", "synonymous"): 33895,
        ("VEP", "missense"): 24405,
        ("VEP", "nonsense"): 1023,
        ("SIFT", "deleterious"): 4809,
        ("SIFT", "tolerated"): 12981,
    }
    if auto_counts != expected:
        raise ValueError(f"local autosomal annotation inventory no longer matches source classes: {auto_counts}")

    load_ids = set(pd.read_csv(paths["wolf_load"], sep="\t", usecols=["IND"])["IND"])
    coding_samples = set(vcf_samples(paths["coding_vcf"]))
    common_samples = len(load_ids & coding_samples)
    common_fraction = common_samples / len(load_ids) if load_ids else 0.0
    if len(load_ids) != 211 or common_fraction != 1.0:
        raise ValueError(
            f"wolf annotation sample intersection changed: {common_samples}/{len(load_ids)}"
        )

    decisions = pd.DataFrame(
        [
            {
                "section": "13.4",
                "study": "ROH-localized GERP-weighted derived-allele burden",
                "decision": "IMPLEMENT" if localization_pass else "NO_GO_NEGATIVE_CONTROL",
                "gate_metric": "partial realized-load cells with bootstrap CI entirely above zero",
                "observed_value": n_ci_positive,
                "secondary_observed_value": n_positive,
                "required_operator": ">=",
                "required_value": min_cells,
                "denominator": 15,
                "unit": "frozen GERP-by-ROH cells",
                "evidence": (
                    f"{n_positive}/15 partial coefficients positive; {n_ci_positive}/15 have CI low > 0"
                ),
                "source_trace": args.associations,
                "reopen_condition": (
                    f"At least {min_cells}/15 prespecified partial realized-load associations must "
                    "be positive with cohort-bootstrap CI entirely above zero."
                ),
                "scientific_boundary": (
                    "Localization would be mechanistic support between genomic proxies, not fitness, "
                    "inbreeding depression, or causation."
                ),
            },
            {
                "section": "13.5",
                "study": "Wolf annotation triangulation",
                "decision": "DEFER_DUPLICATES_SOURCE_STUDY",
                "gate_metric": "independent annotation definitions available",
                "observed_value": 0,
                "secondary_observed_value": common_fraction,
                "required_operator": ">=",
                "required_value": 1,
                "denominator": 1,
                "unit": "independent definition",
                "evidence": (
                    "Local autosomal VEP/SIFT class counts exactly match the source analysis; "
                    f"common sample intersection is {common_samples}/211. The source already compares "
                    "VEP/SIFT, genome-wide GERP, and their source-labeled SIFT-'deleterious' intersection."
                ),
                "source_trace": f"{SOURCE_DOI}; {DRYAD_DOI}; {args.vep}; {args.sift}",
                "reopen_condition": (
                    "At least 1 annotation definition independent of the deposited source classes, "
                    "with >=0.95 common-sample coverage and >=0.90 auditable callable-denominator coverage."
                ),
                "scientific_boundary": (
                    "Predicted-impact classes remain separate risk proxies; they are not proven harmful variants."
                ),
            },
        ]
    )

    out_decisions = Path(args.out_decisions)
    out_inventory = Path(args.out_inventory)
    out_provenance = Path(args.out_provenance)
    for path in (out_decisions, out_inventory, out_provenance):
        path.parent.mkdir(parents=True, exist_ok=True)
    decisions.to_csv(out_decisions, sep="\t", index=False)
    inventory.to_csv(out_inventory, sep="\t", index=False)

    provenance = {
        "analysis": "Phase 5B optional-study gate review",
        "review_date": "2026-07-19",
        "source_study": SOURCE_DOI,
        "source_deposit": DRYAD_DOI,
        "source_overlap_review": {
            "vep_release_and_sift_used": True,
            "vep_sift_vs_gerp_directions_compared": True,
            "sift_deleterious_intersect_gerp_gt4_evaluated": True,
            "discordant_nonsense_and_weakly_conserved_sift_sites_reported": True,
        },
        "common_samples": common_samples,
        "common_sample_fraction": common_fraction,
        "scientific_outcome": {
            row["section"]: row["decision"] for row in decisions.to_dict(orient="records")
        },
        "inputs": {
            label: {"path": str(path), "sha256": sha256(path)} for label, path in paths.items()
        },
        "outputs": [str(out_decisions), str(out_inventory)],
    }
    out_provenance.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(decisions[["section", "decision", "observed_value", "required_value"]].to_string(index=False))


if __name__ == "__main__":
    main()
