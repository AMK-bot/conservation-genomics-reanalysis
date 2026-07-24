#!/usr/bin/env python3
"""Freeze the Section-13.6 core claim contracts after Sections 13.1/13.3/13.2.

This is the ordered hand-off from validated analyses to communication. Optional
wolf studies are deliberately absent: their gates run only after this contract
has been independently validated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bool_values(series: pd.Series) -> pd.Series:
    return series.map(lambda value: value if isinstance(value, bool) else str(value).lower() == "true")


def validator_clear(path: Path) -> bool:
    frame = pd.read_csv(path, sep="\t")
    return bool(len(frame) and frame["status"].astype(str).str.upper().isin(["PASS", "WARN"]).all())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wolf", default="results/tables/wolf_froh_load_associations.tsv")
    parser.add_argument("--damage", default="results/tables/peafowl_damage_effects.tsv")
    parser.add_argument("--ne", default="results/tables/peafowl_ne_design_summary.tsv")
    parser.add_argument("--wolf-validation", default="results/tables/validation_wolf_robustness.tsv")
    parser.add_argument("--damage-validation", default="results/tables/validation_peafowl_damage.tsv")
    parser.add_argument("--ne-validation", default="results/tables/validation_peafowl_ne_design.tsv")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--report", default="report/report.qmd")
    parser.add_argument("--app", default="app/streamlit_app.py")
    parser.add_argument("--html", default="index.html")
    parser.add_argument("--js", default="website/site.js")
    parser.add_argument("--css", default="website/site.css")
    parser.add_argument("--out-contract", default="results/tables/phase5b_core_claim_contract.tsv")
    parser.add_argument("--out-provenance", default="results/provenance/phase5b_core_integration.json")
    args = parser.parse_args()

    paths = {name: Path(value) for name, value in vars(args).items() if name not in {"out_contract", "out_provenance"}}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)
    for key in ("wolf_validation", "damage_validation", "ne_validation"):
        if not validator_clear(paths[key]):
            raise ValueError(f"upstream validator is not clear: {paths[key]}")

    config = yaml.safe_load(paths["config"].read_text(encoding="utf-8"))
    wolf = pd.read_csv(paths["wolf"], sep="\t")
    damage = pd.read_csv(paths["damage"], sep="\t")
    ne = pd.read_csv(paths["ne"], sep="\t")

    partial_realized = wolf.loc[
        wolf["outcome"].astype(str).eq("realized_load")
        & wolf["model"].astype(str).str.contains("partial")
    ]
    if len(partial_realized) != 15:
        raise ValueError("wolf partial realized-load result does not cover 15 cells")
    wolf_observed = int(partial_realized["ci_low"].gt(0).sum())
    wolf_threshold = int(config["phase5b"]["wolf_robustness"]["roh_localization_reopen_min_cells"])

    damage_observed = 0
    for _metric, group in damage.groupby("metric"):
        damage_observed += int(
            group["direction"].astype(str).eq("museum_higher").all()
            and bool_values(group["same_direction_all_snp_vs_transversion"]).all()
            and (group["equal_n_same_direction_n"] == group["equal_n_cases_n"]).all()
            and (group["leave_one_same_direction_n"] == group["leave_one_cases_n"]).all()
        )
    damage_threshold = int(config["phase5b"]["damage_falsification"]["upgrade_min_concordant_metrics"])

    scenario = ne.loc[ne["analysis_type"].astype(str).eq("scenario")].copy()
    boundary_required = {
        "n_attempted", "n_execution_failure", "execution_failure_rate",
        "n_correct_confident", "correct_confident_rate", "n_incorrect_confident",
        "incorrect_confident_rate", "n_indeterminate", "indeterminate_rate",
        "n_boundary_confident_pass", "boundary_confident_pass_rate",
        "n_boundary_confident_fail", "boundary_confident_fail_rate",
    }
    if boundary_required - set(scenario.columns):
        raise ValueError(f"Ne summary lacks boundary fields: {sorted(boundary_required - set(scenario.columns))}")
    boundary = scenario.loc[pd.to_numeric(scenario["true_ne"]).eq(500)].copy()
    expected_boundary_rows = (
        len(config["phase5b"]["ne_design"]["sample_sizes"])
        * len(config["phase5b"]["ne_design"]["marker_densities"])
    )
    boundary_count_total = (
        pd.to_numeric(boundary["n_execution_failure"])
        + pd.to_numeric(boundary["n_boundary_confident_pass"])
        + pd.to_numeric(boundary["n_boundary_confident_fail"])
        + pd.to_numeric(boundary["n_indeterminate"])
    )
    boundary_rate_total = (
        pd.to_numeric(boundary["execution_failure_rate"])
        + pd.to_numeric(boundary["boundary_confident_pass_rate"])
        + pd.to_numeric(boundary["boundary_confident_fail_rate"])
        + pd.to_numeric(boundary["indeterminate_rate"])
    )
    if (
        len(boundary) != expected_boundary_rows
        or not boundary["truth_class"].astype(str).eq("boundary").all()
        or not boundary_count_total.eq(pd.to_numeric(boundary["n_attempted"])).all()
        or not boundary_rate_total.sub(1.0).abs().le(1e-12).all()
        or not pd.to_numeric(boundary["n_correct_confident"]).eq(0).all()
        or not pd.to_numeric(boundary["n_incorrect_confident"]).eq(0).all()
        or not pd.to_numeric(boundary["correct_confident_rate"]).eq(0).all()
        or not pd.to_numeric(boundary["incorrect_confident_rate"]).eq(0).all()
    ):
        raise ValueError(
            "true Ne=500 must be a complete boundary pass/fail/indeterminate/failure partition "
            "and must never be scored correct or incorrect"
        )
    truths = {float(value) for value in config["phase5b"]["ne_design"]["resolution_truths"]}
    correct_floor = float(config["phase5b"]["ne_design"]["resolution_min_correct_confident_ci_low"])
    incorrect_ceiling = float(config["phase5b"]["ne_design"]["resolution_max_incorrect_confident_ci_high"])
    target = scenario.loc[scenario["true_ne"].astype(float).isin(truths)].copy()
    target["meets"] = (
        target["correct_confident_ci_low"].ge(correct_floor)
        & target["incorrect_confident_ci_high"].le(incorrect_ceiling)
    )
    designs = []
    for (sample_size, marker_density), group in target.groupby(["sample_size", "marker_density"]):
        designs.append(
            set(group["true_ne"].astype(float)) == truths and bool(group["meets"].all())
        )
    ne_observed = int(sum(designs))
    if ne_observed:
        ne_consequence = (
            "Sampling plans can prioritize designs that resolved both predeclared resolution "
            "truths (N_e=250 and 1,000) in the simplified known-truth scenarios while preserving "
            "empirical uncertainty."
        )
    else:
        ne_consequence = (
            "No tested design resolved both predeclared resolution truths (N_e=250 and 1,000) in "
            "the simplified known-truth scenarios, so this calibration does not support an "
            "empirical sampling prescription."
        )

    rows = [
        {
            "claim_id": "wolf_froh_load_association",
            "section": "13.1",
            "question": "Does individual F_ROH associate with realized load beyond generic homozygosity?",
            "prediction": "Positive partial association across most of the frozen 15-cell grid.",
            "stress_test": "Generic-homozygosity partial model, 999 cohort bootstraps, 1,999 within-cohort permutations.",
            "result": f"{wolf_observed}/15 partial realized-load CIs entirely above zero.",
            "correction": "Describe proxy association, not fitness or causal inbreeding depression.",
            "falsifier_operator": ">=",
            "falsifier_threshold": wolf_threshold,
            "observed_value": wolf_observed,
            "unit": "of 15 cells",
            "conservation_consequence": "The declared gate reopens ROH localization while retaining the fitness boundary.",
            "table": args.wolf,
            "provenance": "results/provenance/wolf_froh_load.json",
            "validator": args.wolf_validation,
            "report_anchor": "#wolf-individual-association",
            "explorer_anchor": "#wolf-robustness",
        },
        {
            "claim_id": "peafowl_damage_falsification",
            "section": "13.3",
            "question": "Does the weak museum-higher direction survive damage and individual checks?",
            "prediction": "All four metrics remain museum-higher through every declared check.",
            "stress_test": "Transversions, all 462 labels, six equal-n omissions, 11 leave-one cases, 999 block bootstraps.",
            "result": f"{damage_observed}/4 metrics fully museum-higher; geography remains confounded with period.",
            "correction": "Retain a mixed sample contrast, not temporal erosion.",
            "falsifier_operator": "==",
            "falsifier_threshold": damage_threshold,
            "observed_value": damage_observed,
            "unit": "of 4 metrics",
            "conservation_consequence": "Future temporal inference must separate geography from period, not merely add loci.",
            "table": args.damage,
            "provenance": "results/provenance/peafowl_damage.json",
            "validator": args.damage_validation,
            "report_anchor": "#damage-aware-falsification",
            "explorer_anchor": "#damage-falsification",
        },
        {
            "claim_id": "peafowl_ne_study_design",
            "section": "13.2",
            "question": "How do individuals and marker density change decision resolution?",
            "prediction": "Known-truth scenario rates improve as independent genomes and informative markers increase.",
            "stress_test": "60 scenarios, repeated seeded pilot, bounded expansion, empirical downsampling, retained failures.",
            "result": (
                f"{ne_observed}/{len(designs)} designs resolve both predeclared resolution truths "
                "(N_e=250 and 1,000) under the uncertainty rule."
            ),
            "correction": "Call this scenario calibration; empirical downsampling has no known truth.",
            "falsifier_operator": "bounds",
            "falsifier_threshold": f"correct CI low >= {correct_floor}; incorrect CI high <= {incorrect_ceiling}",
            "observed_value": ne_observed,
            "unit": f"of {len(designs)} sample-size/marker designs",
            "conservation_consequence": ne_consequence,
            "table": args.ne,
            "provenance": "results/provenance/peafowl_ne_design.json",
            "validator": args.ne_validation,
            "report_anchor": "#ne-sample-design-calibration",
            "explorer_anchor": "#ne-design",
        },
    ]
    contract = pd.DataFrame(rows)
    out_contract = Path(args.out_contract)
    out_provenance = Path(args.out_provenance)
    out_contract.parent.mkdir(parents=True, exist_ok=True)
    out_provenance.parent.mkdir(parents=True, exist_ok=True)
    contract.to_csv(out_contract, sep="\t", index=False, lineterminator="\n")
    provenance = {
        "analysis": "Phase 5B core communication contract",
        "order": ["13.1", "13.3", "13.2", "13.6"],
        "inputs": {key: {"path": str(path), "sha256": sha256_file(path)} for key, path in paths.items()},
        "output": {"path": str(out_contract), "sha256": sha256_file(out_contract)},
        "boundary": "Communication integration only; optional Sections 13.4/13.5 are not evaluated here.",
    }
    out_provenance.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(contract[["section", "claim_id", "observed_value", "falsifier_threshold"]].to_string(index=False))


if __name__ == "__main__":
    main()
