#!/usr/bin/env python3
"""Independently validate the complete Phase-5B synthesis and communication layer.

This is deliberately not an analysis wrapper.  It reads the delivered machine
tables, recomputes the frozen decision rules, resolves every local trace target,
and checks the generated offline browser payload and synthesis hashes.  Missing
or malformed inputs become explicit FAIL rows so a partial delivery cannot pass
by omission.
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Callable, Iterable
import hashlib
import json
import math
import numbers
from pathlib import Path
import re
import sys
from typing import Any

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[2]

EXPECTED_CLAIM_IDS = [
    "wolf_froh_load_association",
    "peafowl_damage_falsification",
    "peafowl_ne_study_design",
    "wolf_roh_localization_gate",
    "wolf_roh_localized_realized_burden",
    "wolf_annotation_triangulation_gate",
]
EXPECTED_CLAIM_SECTIONS = ["13.1", "13.3", "13.2", "13.4", "13.4", "13.5"]
EXPECTED_SCORECARD_IDS = [
    "wolf_individual_association",
    "peafowl_damage_aware_temporal",
    "peafowl_ne_design_resolution",
    "wolf_roh_localized_realized_burden",
]

REQUIRED_SCIENTIFIC_BOUNDARY_TERMS = {
    "wolf_froh_load_association": ["association", "no fitness", "causal"],
    "peafowl_damage_falsification": ["geography", "period", "not fitness"],
    "peafowl_ne_study_design": ["cannot guarantee", "real sampling"],
    "wolf_roh_localization_gate": ["not fitness", "causation"],
    "wolf_roh_localized_realized_burden": [
        "genomic proxies", "phenotypic", "mechanistic support",
    ],
    "wolf_annotation_triangulation_gate": ["risk proxies", "not proven harmful"],
}

EXPECTED_TRACE = {
    "wolf_froh_load_association": {
        "result_table": "results/tables/wolf_froh_load_associations.tsv",
        "provenance": "results/provenance/wolf_froh_load.json",
        "validator": "results/tables/validation_wolf_robustness.tsv",
        "report_anchor": "report/report.html#wolf-individual-association",
        "explorer_anchor": "index.html#wolf-robustness",
        "workflow_rule": "workflow/rules/phase5b.smk#wolf_froh_load_robustness",
    },
    "peafowl_damage_falsification": {
        "result_table": "results/tables/peafowl_damage_effects.tsv",
        "provenance": "results/provenance/peafowl_damage.json",
        "validator": "results/tables/validation_peafowl_damage.tsv",
        "report_anchor": "report/report.html#damage-aware-falsification",
        "explorer_anchor": "index.html#damage-falsification",
        "workflow_rule": "workflow/rules/phase5b.smk#peafowl_damage_falsification",
    },
    "peafowl_ne_study_design": {
        "result_table": "results/tables/peafowl_ne_design_summary.tsv",
        "provenance": "results/provenance/peafowl_ne_design.json",
        "validator": "results/tables/validation_peafowl_ne_design.tsv",
        "report_anchor": "report/report.html#ne-sample-design-calibration",
        "explorer_anchor": "index.html#ne-design",
        "workflow_rule": "workflow/rules/phase5b.smk#peafowl_ne_design",
    },
    "wolf_roh_localization_gate": {
        "result_table": "results/tables/phase5b_optional_decisions.tsv",
        "provenance": "results/provenance/phase5b_optional_decisions.json",
        "validator": "results/tables/validation_phase5b_decisions.tsv",
        "report_anchor": "report/report.html#optional-study-decisions",
        "explorer_anchor": "index.html#decision-boundaries",
        "workflow_rule": "workflow/rules/phase5b.smk#phase5b_optional_decisions",
    },
    "wolf_roh_localized_realized_burden": {
        "result_table": "results/tables/wolf_roh_localization_cohort.tsv",
        "provenance": "results/provenance/wolf_roh_localization.json",
        "validator": "results/tables/validation_wolf_roh_localization.tsv",
        "report_anchor": "report/report.html#wolf-roh-localization",
        "explorer_anchor": "index.html#wolf-roh-localization",
        "workflow_rule": "workflow/rules/phase5b.smk#wolf_roh_localization_collate",
    },
    "wolf_annotation_triangulation_gate": {
        "result_table": "results/tables/phase5b_optional_decisions.tsv",
        "provenance": "results/provenance/phase5b_optional_decisions.json",
        "validator": "results/tables/validation_phase5b_decisions.tsv",
        "report_anchor": "report/report.html#optional-study-decisions",
        "explorer_anchor": "index.html#decision-boundaries",
        "workflow_rule": "workflow/rules/phase5b.smk#phase5b_optional_decisions",
    },
}

VALIDATORS = {
    "Section 13.1 wolf robustness": "results/tables/validation_wolf_robustness.tsv",
    "Section 13.3 peafowl damage": "results/tables/validation_peafowl_damage.tsv",
    "Section 13.2 peafowl Ne design": "results/tables/validation_peafowl_ne_design.tsv",
    "core Section 13.6 integration": "results/tables/validation_phase5b_core_integration.tsv",
    "Sections 13.4/13.5 optional decisions": "results/tables/validation_phase5b_decisions.tsv",
    "Section 13.4 wolf ROH localization": "results/tables/validation_wolf_roh_localization.tsv",
}

TABLE_PATHS = {
    "wolf_associations": "results/tables/wolf_froh_load_associations.tsv",
    "wolf_rank": "results/tables/wolf_froh_load_rank_stability.tsv",
    "wolf_scores": "results/tables/wolf_froh_load_individual_scores.tsv",
    "wolf_figure_values": "results/tables/wolf_froh_load_figure_values.tsv",
    "wolf_validation": "results/tables/validation_wolf_robustness.tsv",
    "localization_individual": "results/tables/wolf_roh_localization_individual.tsv",
    "localization_cohort": "results/tables/wolf_roh_localization_cohort.tsv",
    "localization_null": "results/tables/wolf_roh_localization_null.tsv",
    "localization_qc": "results/tables/wolf_roh_localization_qc.tsv",
    "localization_figure_values": "results/tables/wolf_roh_localization_figure_values.tsv",
    "localization_validation": "results/tables/validation_wolf_roh_localization.tsv",
    "damage_effects": "results/tables/peafowl_damage_effects.tsv",
    "damage_permutations": "results/tables/peafowl_damage_permutations.tsv",
    "damage_influence": "results/tables/peafowl_damage_influence.tsv",
    "damage_blocks": "results/tables/peafowl_damage_blocks.tsv",
    "damage_classification": "results/tables/peafowl_damage_classification.tsv",
    "damage_figure_values": "results/tables/peafowl_damage_figure_values.tsv",
    "damage_validation": "results/tables/validation_peafowl_damage.tsv",
    "ne_replicates": "results/tables/peafowl_ne_design_replicates.tsv",
    "ne_pilot": "results/tables/peafowl_ne_design_pilot.tsv",
    "ne_summary": "results/tables/peafowl_ne_design_summary.tsv",
    "ne_empirical": "results/tables/peafowl_ne_design_empirical.tsv",
    "ne_figure_values": "results/tables/peafowl_ne_design_figure_values.tsv",
    "ne_validation": "results/tables/validation_peafowl_ne_design.tsv",
    "decisions": "results/tables/phase5b_optional_decisions.tsv",
    "inventory": "results/tables/phase5b_annotation_inventory.tsv",
    "decisions_validation": "results/tables/validation_phase5b_decisions.tsv",
    "claims": "results/tables/phase5b_claim_trace.tsv",
    "scorecard": "results/tables/phase5b_fragility_scorecard.tsv",
}

DECLARED_STORAGE_DTYPES = {
    TABLE_PATHS["claims"]: {
        "section": "str",
        "change_threshold": "object",
    },
    TABLE_PATHS["scorecard"]: {"section": "str"},
}

SYNTHESIS_INPUTS = {
    **{key: value for key, value in TABLE_PATHS.items() if key not in {"claims", "scorecard"}},
    "wolf_provenance": "results/provenance/wolf_froh_load.json",
    "localization_provenance": "results/provenance/wolf_roh_localization.json",
    "damage_provenance": "results/provenance/peafowl_damage.json",
    "ne_provenance": "results/provenance/peafowl_ne_design.json",
    "decisions_provenance": "results/provenance/phase5b_optional_decisions.json",
    "config": "config/config.yaml",
}

SYNTHESIS_OUTPUTS = [
    "results/tables/phase5b_claim_trace.tsv",
    "results/tables/phase5b_fragility_scorecard.tsv",
    "results/tables/phase5b_data_dictionary.tsv",
    "results/PHASE5B_DATA_DICTIONARY.md",
    "website/phase5b-data.js",
]

PAYLOAD_COLUMNS = {
    "wolfAssociations": [
        "cell_id", "gerp_threshold", "roh_cutoff_mb", "outcome", "model",
        "coefficient", "ci_low", "ci_high", "permutation_p_two_sided",
    ],
    "wolfLocalization": [
        "POP", "gerp_threshold", "roh_cutoff_mb", "n_ind", "inside_eligible_genotype_calls",
        "outside_eligible_genotype_calls", "log2_enrichment", "null_median_log2_enrichment",
        "null_ci_low", "null_ci_high", "observed_minus_null_median",
        "permutation_p_two_sided", "direction", "status", "beyond_null",
    ],
    "neDesign": [
        "analysis_type", "population", "true_ne", "truth_class", "sample_size",
        "marker_density", "n_attempted", "convergence_rate", "correct_confident_rate",
        "correct_confident_ci_low", "correct_confident_ci_high", "incorrect_confident_rate",
        "incorrect_confident_ci_low", "incorrect_confident_ci_high", "indeterminate_rate",
        "boundary_confident_pass_rate", "boundary_confident_fail_rate",
        "pass_rate", "fail_rate", "execution_failure_rate", "median_ci_width",
    ],
}

PAYLOAD_SEMANTIC_STRING_COLUMNS = {
    "claims": {"section"},
    "optionalDecisions": {"section"},
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def truthy(value: object) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).strip().lower() == "true"


def numeric(value: object, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} is not finite: {value!r}")
    return result


def number_equal(left: object, right: object, tolerance: float = 1e-12) -> bool:
    try:
        a = float(left)
        b = float(right)
    except (TypeError, ValueError):
        return False
    return math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)


def beyond_localization_null(frame: pd.DataFrame) -> pd.Series:
    observed = pd.to_numeric(frame["log2_enrichment"], errors="coerce")
    null_high = pd.to_numeric(frame["null_ci_high"], errors="coerce")
    p_value = pd.to_numeric(frame["permutation_p_two_sided"], errors="coerce")
    return observed.gt(null_high) & p_value.le(0.05)


def compact_exception(error: BaseException) -> str:
    message = " ".join(str(error).split())
    return f"{type(error).__name__}: {message}"[:1800]


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def python_string_corpus(source: str) -> str:
    """Return syntax-resolved Python string literals with whitespace normalized."""
    tree = ast.parse(source)
    strings = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    return normalize_whitespace("\n".join(strings))


def python_literal_contract_gaps(
    source: str,
    *,
    required: Iterable[str],
    stale: Iterable[str] = (),
    case_sensitive: bool = True,
) -> tuple[list[str], list[str]]:
    """Find required and forbidden phrases in syntax-resolved string literals."""
    corpus = python_string_corpus(source)
    transform = (lambda value: value) if case_sensitive else str.casefold
    searchable = transform(corpus)
    required_tokens = list(required)
    stale_tokens = list(stale)
    missing = [
        token
        for token in required_tokens
        if transform(normalize_whitespace(token)) not in searchable
    ]
    present_stale = [
        token
        for token in stale_tokens
        if transform(normalize_whitespace(token)) in searchable
    ]
    return missing, present_stale


def report_dynamic_reference(source: str, value_name: str) -> bool:
    """Recognize a Quarto inline Python reference to a report value."""
    escaped = re.escape(value_name)
    return bool(re.search(rf"`\{{python\}}\s*R\.{escaped}\b[^`]*`", source))


def ast_dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = ast_dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def report_values_contract_gaps(
    source: str,
    *,
    required_paths: Iterable[str],
    required_values: Iterable[str],
) -> dict[str, list[str]]:
    """Inspect the report-value loader without executing or importing it."""
    tree = ast.parse(source)
    source_files: dict[object, object] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == "SOURCE_FILES" for target in targets):
            continue
        try:
            candidate = ast.literal_eval(node.value)
        except (TypeError, ValueError):
            candidate = {}
        if isinstance(candidate, dict):
            source_files = candidate
        break

    namespace_values: set[str] = set()
    read_csv_in_loader = False
    write_methods = {
        "to_csv", "to_excel", "to_feather", "to_hdf", "to_json", "to_parquet",
        "to_pickle", "to_sql", "write_bytes", "write_text",
    }
    writes: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        dotted = ast_dotted_name(node.func)
        if dotted == "SimpleNamespace":
            namespace_values.update(keyword.arg for keyword in node.keywords if keyword.arg)
        if isinstance(node.func, ast.Attribute) and node.func.attr in write_methods:
            writes.add(node.func.attr)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_read":
            read_csv_in_loader = any(
                isinstance(child, ast.Call) and ast_dotted_name(child.func) == "pd.read_csv"
                for child in ast.walk(node)
            )
            break

    paths = {str(value) for value in source_files.values()}
    return {
        "tables": [path for path in required_paths if path not in paths],
        "dynamic values": [name for name in required_values if name not in namespace_values],
        "loader": [] if read_csv_in_loader else ["_read must call pd.read_csv"],
        "writes": sorted(writes),
    }


def expected_storage_dtype(relative: str, column: str, values: pd.Series) -> str:
    """Use declared semantic storage types where TSV inference is lossy."""
    return DECLARED_STORAGE_DTYPES.get(relative, {}).get(column, str(values.dtype))


def definition_is_explicit(column: str, description: object) -> bool:
    """Accept genuine prose definitions plus exact conventional symbol expansions."""
    if description is None or bool(pd.isna(description)):
        return False
    text = str(description).strip()
    symbol = column.casefold()
    symbolic = {"k": "K.", "n": "N."}
    if symbol in symbolic:
        if text == symbolic[symbol]:
            return True
        lowered = text.casefold()
        required_terms = {
            "k": ("full-sibling", "individual"),
            "n": ("number", "observations"),
        }
        return len(text) >= 12 and all(term in lowered for term in required_terms[symbol])
    return len(text) >= 3 and text.casefold() not in {"nan", "n/a", "none", "null", "tbd"}


class Audit:
    def __init__(self) -> None:
        self.rows: list[dict[str, str]] = []

    def add(self, check: str, passed: bool, detail: str) -> None:
        self.rows.append(
            {"check": check, "status": "PASS" if bool(passed) else "FAIL", "detail": str(detail)}
        )

    def run(self, check: str, operation: Callable[[], str | tuple[bool, str]]) -> None:
        try:
            result = operation()
            if isinstance(result, tuple):
                passed, detail = result
            else:
                passed, detail = True, result
            self.add(check, bool(passed), str(detail))
        except Exception as error:  # every malformed input becomes a useful machine row
            self.add(check, False, compact_exception(error))

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=["check", "status", "detail"])


class Context:
    def __init__(self, root: Path) -> None:
        self.root = root.absolute()
        self._tables: dict[str, pd.DataFrame] = {}
        self._json: dict[str, Any] = {}
        self._text: dict[str, str] = {}

    def path(self, relative: str | Path) -> Path:
        candidate = Path(relative)
        if candidate.is_absolute():
            return candidate
        return self.root / candidate

    def local_path(self, value: object) -> Path:
        text = str(value).strip()
        candidate = Path(text)
        if not text or candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"trace path must be a project-relative local path: {text!r}")
        return self.root / candidate

    def table(self, relative: str) -> pd.DataFrame:
        if relative not in self._tables:
            path = self.path(relative)
            if not path.is_file():
                raise FileNotFoundError(path)
            frame = pd.read_csv(path, sep="\t")
            if frame.empty:
                raise ValueError(f"empty TSV: {relative}")
            self._tables[relative] = frame
        return self._tables[relative].copy()

    def json(self, relative: str) -> Any:
        if relative not in self._json:
            path = self.path(relative)
            if not path.is_file():
                raise FileNotFoundError(path)
            self._json[relative] = json.loads(path.read_text(encoding="utf-8"))
        return self._json[relative]

    def text(self, relative: str) -> str:
        if relative not in self._text:
            path = self.path(relative)
            if not path.is_file():
                raise FileNotFoundError(path)
            self._text[relative] = path.read_text(encoding="utf-8")
        return self._text[relative]


def require_columns(frame: pd.DataFrame, columns: Iterable[str], label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{label} lacks columns: {missing}")


def load_config(context: Context) -> dict[str, Any]:
    config = yaml.safe_load(context.text("config/config.yaml"))
    if not isinstance(config, dict):
        raise ValueError("config/config.yaml is not a mapping")
    return config


def claim_index(context: Context) -> pd.DataFrame:
    claims = context.table(TABLE_PATHS["claims"])
    require_columns(
        claims,
        [
            "claim_id", "section", "headline", "claim_status", "estimate", "uncertainty",
            "result_table", "result_filter", "provenance", "validator", "report_anchor",
            "explorer_anchor", "workflow_rule", "source_trace", "change_operator",
            "change_threshold", "observed_value", "unit", "what_changes_mind",
            "scientific_boundary",
        ],
        "claim trace",
    )
    if claims["claim_id"].duplicated().any():
        raise ValueError("claim trace contains duplicate claim_id values")
    return claims.set_index("claim_id", drop=False)


def recompute_wolf(context: Context) -> dict[str, Any]:
    frame = context.table(TABLE_PATHS["wolf_associations"])
    require_columns(frame, ["cell_id", "gerp_threshold", "roh_cutoff_mb", "outcome", "model", "ci_low"], "wolf associations")
    if len(frame) != 60:
        raise ValueError(f"expected 60 wolf association rows, found {len(frame)}")
    keys = frame[["gerp_threshold", "roh_cutoff_mb", "outcome", "model"]].drop_duplicates()
    if len(keys) != 60:
        raise ValueError("wolf association grid has duplicate parameter rows")
    partial = frame.loc[
        frame["outcome"].astype(str).eq("realized_load")
        & frame["model"].astype(str).str.contains("partial", case=False, na=False)
    ].copy()
    if len(partial) != 15 or partial["cell_id"].nunique() != 15:
        raise ValueError(f"expected 15 partial realized-load cells, found {len(partial)}")
    ci_low = pd.to_numeric(partial["ci_low"], errors="raise")
    if not np.isfinite(ci_low).all():
        raise ValueError("partial realized-load CI lows include non-finite values")
    threshold = int(load_config(context)["phase5b"]["wolf_robustness"]["roh_localization_reopen_min_cells"])
    return {"support": int(ci_low.gt(0).sum()), "threshold": threshold, "tested": 15}


def recompute_damage(context: Context) -> dict[str, Any]:
    frame = context.table(TABLE_PATHS["damage_effects"])
    required = [
        "variant_set", "metric", "direction", "same_direction_all_snp_vs_transversion",
        "equal_n_same_direction_n", "equal_n_cases_n", "leave_one_same_direction_n",
        "leave_one_cases_n", "supports_temporal_erosion_upgrade",
    ]
    require_columns(frame, required, "peafowl damage effects")
    expected_metrics = {"pi", "Ho", "He", "allelic_richness"}
    expected_variants = {"all_snp", "transversion_only"}
    if len(frame) != 8 or set(frame["metric"].astype(str)) != expected_metrics or set(frame["variant_set"].astype(str)) != expected_variants:
        raise ValueError("damage table is not the complete four-metric by two-variant grid")
    robust = 0
    for metric, group in frame.groupby("metric", sort=False):
        if len(group) != 2 or set(group["variant_set"].astype(str)) != expected_variants:
            raise ValueError(f"damage metric {metric!r} lacks its two frozen variant sets")
        robust += int(
            group["direction"].astype(str).eq("museum_higher").all()
            and group["same_direction_all_snp_vs_transversion"].map(truthy).all()
            and (pd.to_numeric(group["equal_n_same_direction_n"]) == pd.to_numeric(group["equal_n_cases_n"])).all()
            and (pd.to_numeric(group["leave_one_same_direction_n"]) == pd.to_numeric(group["leave_one_cases_n"])).all()
        )
    threshold = int(load_config(context)["phase5b"]["damage_falsification"]["upgrade_min_concordant_metrics"])
    upgrade = bool(frame["supports_temporal_erosion_upgrade"].map(truthy).all())
    return {"support": robust, "threshold": threshold, "tested": 4, "upgrade": upgrade}


def recompute_ne(context: Context) -> dict[str, Any]:
    frame = context.table(TABLE_PATHS["ne_summary"])
    required = [
        "analysis_type", "population", "true_ne", "truth_class", "sample_size", "marker_density",
        "n_attempted", "n_execution_failure", "execution_failure_rate",
        "n_correct_confident", "correct_confident_rate", "correct_confident_ci_low",
        "n_incorrect_confident", "incorrect_confident_rate", "incorrect_confident_ci_high",
        "n_indeterminate", "indeterminate_rate", "n_boundary_confident_pass",
        "boundary_confident_pass_rate", "n_boundary_confident_fail",
        "boundary_confident_fail_rate",
    ]
    require_columns(frame, required, "peafowl Ne summary")
    config = load_config(context)["phase5b"]["ne_design"]
    true_values = {float(value) for value in config["true_ne"]}
    sizes = {int(value) for value in config["sample_sizes"]}
    densities = {int(value) for value in config["marker_densities"]}
    scenario = frame.loc[frame["analysis_type"].astype(str).eq("scenario")].copy()
    actual_keys = set(
        zip(
            pd.to_numeric(scenario["true_ne"]).astype(float),
            pd.to_numeric(scenario["sample_size"]).astype(int),
            pd.to_numeric(scenario["marker_density"]).astype(int),
            strict=False,
        )
    )
    expected_keys = {(truth, size, density) for truth in true_values for size in sizes for density in densities}
    if len(scenario) != len(expected_keys) or actual_keys != expected_keys:
        raise ValueError(f"Ne scenario grid mismatch: rows={len(scenario)}, expected={len(expected_keys)}")
    boundary = scenario.loc[pd.to_numeric(scenario["true_ne"]).astype(float).eq(500.0)].copy()
    if len(boundary) != len(sizes) * len(densities) or not boundary["truth_class"].astype(str).eq("boundary").all():
        raise ValueError(f"Ne=500 boundary grid mismatch: rows={len(boundary)}")
    boundary_partition_counts = (
        pd.to_numeric(boundary["n_execution_failure"])
        + pd.to_numeric(boundary["n_boundary_confident_pass"])
        + pd.to_numeric(boundary["n_boundary_confident_fail"])
        + pd.to_numeric(boundary["n_indeterminate"])
    )
    boundary_partition_rates = (
        pd.to_numeric(boundary["execution_failure_rate"])
        + pd.to_numeric(boundary["boundary_confident_pass_rate"])
        + pd.to_numeric(boundary["boundary_confident_fail_rate"])
        + pd.to_numeric(boundary["indeterminate_rate"])
    )
    if (
        not boundary_partition_counts.eq(pd.to_numeric(boundary["n_attempted"])).all()
        or not np.isclose(boundary_partition_rates.to_numpy(dtype=float), 1.0, atol=1e-12).all()
        or not pd.to_numeric(boundary["n_correct_confident"]).eq(0).all()
        or not pd.to_numeric(boundary["n_incorrect_confident"]).eq(0).all()
        or not pd.to_numeric(boundary["correct_confident_rate"]).eq(0).all()
        or not pd.to_numeric(boundary["incorrect_confident_rate"]).eq(0).all()
    ):
        raise ValueError(
            "Ne=500 must partition into boundary confident pass/fail, indeterminate, and "
            "execution failure without correct/incorrect scoring"
        )
    nonboundary = scenario.loc[~pd.to_numeric(scenario["true_ne"]).astype(float).eq(500.0)]
    if (
        not pd.to_numeric(nonboundary["n_boundary_confident_pass"]).eq(0).all()
        or not pd.to_numeric(nonboundary["n_boundary_confident_fail"]).eq(0).all()
    ):
        raise ValueError("non-boundary Ne scenarios contain boundary-confident outcomes")
    truths = {float(value) for value in config["resolution_truths"]}
    correct_floor = float(config["resolution_min_correct_confident_ci_low"])
    incorrect_ceiling = float(config["resolution_max_incorrect_confident_ci_high"])
    target = scenario.loc[pd.to_numeric(scenario["true_ne"]).astype(float).isin(truths)].copy()
    target["meets"] = (
        pd.to_numeric(target["correct_confident_ci_low"], errors="coerce").ge(correct_floor)
        & pd.to_numeric(target["incorrect_confident_ci_high"], errors="coerce").le(incorrect_ceiling)
    )
    resolving: list[bool] = []
    for _key, group in target.groupby(["sample_size", "marker_density"], sort=True):
        resolving.append(set(pd.to_numeric(group["true_ne"]).astype(float)) == truths and bool(group["meets"].all()))
    if len(resolving) != len(sizes) * len(densities):
        raise ValueError(f"expected {len(sizes) * len(densities)} resolution designs, found {len(resolving)}")

    empirical = frame.loc[frame["analysis_type"].astype(str).eq("empirical")].copy()
    popmap = pd.read_csv(context.path("config/peafowl_popmap.tsv"), sep="\t")
    require_columns(popmap, ["sample", "population"], "peafowl popmap")
    observed_n = popmap.groupby("population")["sample"].nunique().to_dict()
    minimum_n = min(sizes)
    expected_empirical = {
        (str(population), n, density)
        for population, count in observed_n.items()
        if count >= minimum_n
        for n in range(minimum_n, int(count) + 1)
        for density in densities
    }
    actual_empirical = set(
        zip(
            empirical["population"].astype(str),
            pd.to_numeric(empirical["sample_size"]).astype(int),
            pd.to_numeric(empirical["marker_density"]).astype(int),
            strict=False,
        )
    )
    if len(empirical) != len(expected_empirical) or actual_empirical != expected_empirical:
        raise ValueError(f"Ne empirical grid mismatch: rows={len(empirical)}, expected={len(expected_empirical)}")
    if not empirical["truth_class"].astype(str).eq("not_known").all() or pd.to_numeric(empirical["true_ne"], errors="coerce").notna().any():
        raise ValueError("empirical Ne rows do not preserve unknown truth")
    return {
        "support": int(sum(resolving)),
        "tested": len(resolving),
        "correct_floor": correct_floor,
        "incorrect_ceiling": incorrect_ceiling,
        "summary_rows": len(frame),
        "scenario_rows": len(scenario),
        "empirical_rows": len(empirical),
        "boundary_rows": len(boundary),
    }


def recompute_localization(context: Context) -> dict[str, Any]:
    frame = context.table(TABLE_PATHS["localization_cohort"])
    required = [
        "POP", "gerp_threshold", "roh_cutoff_mb", "log2_enrichment", "null_ci_high",
        "permutation_p_two_sided", "status",
    ]
    require_columns(frame, required, "wolf ROH-localization cohort table")
    config = load_config(context)
    thresholds = {float(value) for value in config["wolf"]["load"]["gerp_sensitivity"]}
    cutoffs = {float(value) for value in config["wolf"]["roh"]["length_cutoffs_mb"]}
    long_cutoff = float(config["wolf"]["roh"]["long_roh_threshold_mb"])
    if not math.isclose(long_cutoff, 1.5, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"predeclared long-ROH cutoff is not 1.5 Mb: {long_cutoff}")
    popmap = pd.read_csv(context.path("results/wolf/popmap.tsv"), sep="\t", header=None, names=["IND", "POP"])
    populations = set(popmap["POP"].astype(str))
    expected_keys = {(pop, threshold, cutoff) for pop in populations for threshold in thresholds for cutoff in cutoffs}
    actual_keys = set(
        zip(
            frame["POP"].astype(str),
            pd.to_numeric(frame["gerp_threshold"]).astype(float),
            pd.to_numeric(frame["roh_cutoff_mb"]).astype(float),
            strict=False,
        )
    )
    if len(populations) != 8 or len(frame) != len(expected_keys) or actual_keys != expected_keys:
        raise ValueError(f"localization grid mismatch: populations={len(populations)}, rows={len(frame)}, expected={len(expected_keys)}")
    target = frame.loc[np.isclose(pd.to_numeric(frame["roh_cutoff_mb"]), long_cutoff)].copy()
    target_keys = set(
        zip(target["POP"].astype(str), pd.to_numeric(target["gerp_threshold"]).astype(float), strict=False)
    )
    expected_target = {(pop, threshold) for pop in populations for threshold in thresholds}
    numeric_columns = target[["log2_enrichment", "null_ci_high", "permutation_p_two_sided"]].apply(pd.to_numeric, errors="coerce")
    if len(target) != 24 or target_keys != expected_target:
        raise ValueError(f"1.5-Mb localization slice is not the exact 24-cell grid: {len(target)} rows")
    if not np.isfinite(numeric_columns.to_numpy(dtype=float)).all() or not target["status"].astype(str).str.lower().eq("ok").all():
        raise ValueError("1.5-Mb localization slice contains failed or non-finite cells")
    target["beyond_null"] = beyond_localization_null(target)
    by_threshold = (
        target.groupby("gerp_threshold", sort=True)["beyond_null"].sum().astype(int).to_dict()
    )
    return {"support": int(target["beyond_null"].sum()), "tested": 24, "by_threshold": by_threshold}


def inspect_validator(context: Context, label: str, relative: str) -> str:
    frame = context.table(relative)
    require_columns(frame, ["status"], f"{label} validator")
    statuses = frame["status"].astype(str).str.upper()
    allowed = {"PASS"} if "ROH localization" in label else {"PASS", "WARN"}
    unexpected = sorted(set(statuses) - allowed)
    if unexpected:
        raise ValueError(f"{label} statuses outside {sorted(allowed)}: {unexpected}")
    if "ROH localization" in label and not statuses.eq("PASS").all():
        raise ValueError("localization validator must contain PASS rows only")
    counts = statuses.value_counts().to_dict()
    return f"rows={len(frame)}; statuses={counts}"


def anchor_exists(text: str, anchor: str) -> bool:
    escaped = re.escape(anchor)
    html_id = re.search(
        rf"\bid\s*=\s*['\"]{escaped}['\"]", text, flags=re.IGNORECASE
    )
    quarto_id = re.search(
        rf"\{{[^}}\n]*#{escaped}(?=\s|\}})[^}}\n]*\}}", text
    )
    return bool(html_id or quarto_id)


def pre_render_anchor_path(field: str, declared_path: str) -> str:
    """Resolve downstream report links to their authoritative pre-render source."""
    if field == "report_anchor" and declared_path == "report/report.html":
        return "report/report.qmd"
    return declared_path


def trace_targets_check(context: Context) -> str:
    claims = claim_index(context).reset_index(drop=True)
    errors: list[str] = []
    checked = 0
    for row in claims.to_dict(orient="records"):
        claim_id = str(row["claim_id"])
        for field in ("result_table", "provenance", "validator"):
            try:
                path = context.local_path(row[field])
                if not path.is_file():
                    errors.append(f"{claim_id}.{field} missing: {row[field]}")
                checked += 1
            except Exception as error:
                errors.append(f"{claim_id}.{field}: {compact_exception(error)}")
        for field in ("report_anchor", "explorer_anchor"):
            value = str(row[field])
            if "#" not in value:
                errors.append(f"{claim_id}.{field} lacks #anchor")
                continue
            declared_path, anchor = value.rsplit("#", 1)
            path_text = pre_render_anchor_path(field, declared_path)
            try:
                path = context.local_path(path_text)
                if not path.is_file():
                    errors.append(f"{claim_id}.{field} target missing: {path_text}")
                elif not anchor_exists(path.read_text(encoding="utf-8"), anchor):
                    errors.append(f"{claim_id}.{field} anchor missing: #{anchor}")
                checked += 1
            except Exception as error:
                errors.append(f"{claim_id}.{field}: {compact_exception(error)}")
        workflow = str(row["workflow_rule"])
        if "#" not in workflow:
            errors.append(f"{claim_id}.workflow_rule lacks #rule")
        else:
            path_text, rule = workflow.rsplit("#", 1)
            try:
                path = context.local_path(path_text)
                source = path.read_text(encoding="utf-8")
                if not re.search(rf"(?m)^rule\s+{re.escape(rule)}\s*:", source):
                    errors.append(f"{claim_id}.workflow_rule missing rule {rule}")
                checked += 1
            except Exception as error:
                errors.append(f"{claim_id}.workflow_rule: {compact_exception(error)}")
        for token in (part.strip() for part in str(row["source_trace"]).split(";")):
            if not token.startswith(("results/", "data/", "config/", "report/", "app/", "website/", "workflow/")):
                continue
            try:
                if any(mark in token for mark in "*?["):
                    matches = list(context.root.glob(token))
                    if not matches:
                        errors.append(f"{claim_id}.source_trace glob has no matches: {token}")
                elif not context.local_path(token).is_file():
                    errors.append(f"{claim_id}.source_trace missing: {token}")
                checked += 1
            except Exception as error:
                errors.append(f"{claim_id}.source_trace: {compact_exception(error)}")
    if errors:
        raise ValueError("; ".join(errors[:12]) + (f"; plus {len(errors)-12} more" if len(errors) > 12 else ""))
    return f"resolved {checked} local files, source anchors, workflow rules, and source targets"


def claims_schema_check(context: Context) -> str:
    claims = claim_index(context).reset_index(drop=True)
    ids = claims["claim_id"].astype(str).tolist()
    sections = claims["section"].astype(str).tolist()
    if ids != EXPECTED_CLAIM_IDS or sections != EXPECTED_CLAIM_SECTIONS:
        raise ValueError(f"claim order/identity mismatch: ids={ids}, sections={sections}")
    required = [
        "headline", "claim_status", "estimate", "uncertainty", "result_filter", "unit",
        "what_changes_mind", "scientific_boundary",
    ]
    if not claims[required].apply(lambda column: column.astype(str).str.strip().str.len().ge(3).all()).all():
        raise ValueError("one or more claims has an empty narrative, uncertainty, filter, unit, or boundary")
    trace_failures: list[str] = []
    indexed = claims.set_index("claim_id")
    for claim_id, expected_fields in EXPECTED_TRACE.items():
        for field, expected in expected_fields.items():
            observed = str(indexed.loc[claim_id, field])
            if observed != expected:
                trace_failures.append(f"{claim_id}.{field}={observed!r}, expected={expected!r}")
    if trace_failures:
        raise ValueError("exact trace mapping changed: " + "; ".join(trace_failures))
    return "six exact claims in locked 13.1 -> 13.3 -> 13.2 -> 13.4 -> 13.5 order"


def claims_numeric_check(context: Context) -> str:
    claims = claim_index(context)
    wolf = recompute_wolf(context)
    damage = recompute_damage(context)
    ne = recompute_ne(context)
    localization = recompute_localization(context)
    decisions = context.table(TABLE_PATHS["decisions"])
    require_columns(decisions, ["section", "decision", "observed_value", "required_value"], "optional decisions")
    row134 = decisions.loc[decisions["section"].astype(str).eq("13.4")]
    row135 = decisions.loc[decisions["section"].astype(str).eq("13.5")]
    if len(row134) != 1 or len(row135) != 1:
        raise ValueError("optional decision table must contain exactly one row for each of 13.4 and 13.5")
    row134 = row134.iloc[0]
    row135 = row135.iloc[0]

    failures: list[str] = []
    expected_observed = {
        "wolf_froh_load_association": wolf["support"],
        "peafowl_damage_falsification": damage["support"],
        "peafowl_ne_study_design": ne["support"],
        "wolf_roh_localization_gate": wolf["support"],
        "wolf_roh_localized_realized_burden": localization["support"],
        "wolf_annotation_triangulation_gate": 0,
    }
    for claim_id, expected in expected_observed.items():
        if not number_equal(claims.loc[claim_id, "observed_value"], expected):
            failures.append(f"{claim_id} observed={claims.loc[claim_id, 'observed_value']!r}, expected={expected}")
    if not number_equal(claims.loc["wolf_froh_load_association", "change_threshold"], wolf["threshold"]):
        failures.append("wolf association falsifier threshold does not match config")
    if not number_equal(claims.loc["peafowl_damage_falsification", "change_threshold"], damage["threshold"]):
        failures.append("damage falsifier threshold does not match config")
    ne_threshold = str(claims.loc["peafowl_ne_study_design", "change_threshold"])
    if f"{ne['correct_floor']:.2f}" not in ne_threshold or f"{ne['incorrect_ceiling']:.2f}" not in ne_threshold:
        failures.append("Ne bound falsifier does not contain both frozen Wilson limits")
    localization_threshold = str(claims.loc["wolf_roh_localized_realized_burden", "change_threshold"])
    if "null 95% upper bound" not in localization_threshold or "p <= 0.05" not in localization_threshold:
        failures.append("localization claim does not retain the exact two-part cell rule")
    if (
        not number_equal(row134["observed_value"], wolf["support"])
        or not number_equal(row134["required_value"], wolf["threshold"])
        or str(row134["decision"]) != ("IMPLEMENT" if wolf["support"] >= wolf["threshold"] else "NO_GO_NEGATIVE_CONTROL")
    ):
        failures.append("13.4 decision does not reconcile to the wolf negative-control gate")
    if not number_equal(row135["observed_value"], 0) or not number_equal(row135["required_value"], 1) or str(row135["decision"]) != "DEFER_DUPLICATES_SOURCE_STUDY":
        failures.append("13.5 deferral is not the frozen 0-of-1 independence result")
    expected_status = {
        "wolf_froh_load_association": "gerp_proxy_specific_support" if wolf["support"] >= wolf["threshold"] else "proxy_coupling_not_excluded",
        "peafowl_damage_falsification": "temporal_erosion_upgrade" if damage["upgrade"] else "contrast_only",
        "peafowl_ne_study_design": "scenario_landscape_not_guarantee",
        "wolf_roh_localization_gate": str(row134["decision"]),
        "wolf_roh_localized_realized_burden": "cellwise_beyond_null_summary",
        "wolf_annotation_triangulation_gate": str(row135["decision"]),
    }
    for claim_id, expected in expected_status.items():
        if str(claims.loc[claim_id, "claim_status"]) != expected:
            failures.append(f"{claim_id} status does not reconcile: expected {expected!r}")
    if failures:
        raise ValueError("; ".join(failures))
    return (
        f"wolf={wolf['support']}/15 (gate {wolf['threshold']}); damage={damage['support']}/4 "
        f"(gate {damage['threshold']}); Ne={ne['support']}/{ne['tested']}; "
        f"localization={localization['support']}/24; annotation=0/1"
    )


def scientific_boundaries_check(context: Context) -> str:
    claims = claim_index(context)
    boundaries = claims["scientific_boundary"].astype(str).str.lower().to_dict()
    missing = {
        claim_id: [term for term in terms if term not in boundaries[claim_id]]
        for claim_id, terms in REQUIRED_SCIENTIFIC_BOUNDARY_TERMS.items()
        if any(term not in boundaries[claim_id] for term in terms)
    }
    if missing:
        raise ValueError(f"scientific-boundary language missing: {missing}")
    return "all claims distinguish genomic proxies, design limits, unknown truth, and absent fitness/causal evidence"


def localization_check(context: Context) -> str:
    result = recompute_localization(context)
    config = load_config(context)["phase5b"]["roh_localization"]
    if int(config["permutation_reps"]) != 199 or float(config["ci_pct"]) != 95:
        raise ValueError("localization null settings changed from 199 replicates and 95% interval")
    by_threshold = ", ".join(f"GERP>{float(key):g}: {value}/8" for key, value in sorted(result["by_threshold"].items()))
    return f"1.5-Mb beyond-null rule independently gives {result['support']}/24 ({by_threshold})"


def scorecard_check(context: Context) -> str:
    frame = context.table(TABLE_PATHS["scorecard"])
    require_columns(
        frame,
        [
            "conclusion_id", "section", "classification", "conclusion", "settings_supporting",
            "settings_tested", "dominant_uncertainty", "evidence_needed", "machine_result",
        ],
        "Phase-5B fragility scorecard",
    )
    ids = frame["conclusion_id"].astype(str).tolist()
    if len(frame) != 4 or ids != EXPECTED_SCORECARD_IDS or frame["conclusion_id"].duplicated().any():
        raise ValueError(f"scorecard must contain the exact four ordered rows, found {ids}")
    wolf = recompute_wolf(context)
    damage = recompute_damage(context)
    ne = recompute_ne(context)
    localization = recompute_localization(context)
    expected = {
        "wolf_individual_association": (wolf["support"], 15, "robust_association" if wolf["support"] >= wolf["threshold"] else "negative-control-sensitive", TABLE_PATHS["wolf_associations"]),
        "peafowl_damage_aware_temporal": (damage["support"], 4, "robust_direction" if damage["upgrade"] else "design-limited", TABLE_PATHS["damage_effects"]),
        "peafowl_ne_design_resolution": (ne["support"], ne["tested"], "scenario-calibrated", TABLE_PATHS["ne_summary"]),
        "wolf_roh_localized_realized_burden": (
            localization["support"], 24,
            "grid_wide_beyond_null" if localization["support"] == 24 else "null_compatible" if localization["support"] == 0 else "population_threshold_heterogeneous",
            TABLE_PATHS["localization_cohort"],
        ),
    }
    failures: list[str] = []
    indexed = frame.set_index("conclusion_id")
    for conclusion_id, (support, tested, classification, machine_result) in expected.items():
        row = indexed.loc[conclusion_id]
        if not number_equal(row["settings_supporting"], support) or not number_equal(row["settings_tested"], tested):
            failures.append(f"{conclusion_id} support/tested mismatch")
        if str(row["classification"]) != classification or str(row["machine_result"]) != machine_result:
            failures.append(f"{conclusion_id} classification/result mismatch")
        if len(str(row["dominant_uncertainty"]).strip()) < 12 or len(str(row["evidence_needed"]).strip()) < 12:
            failures.append(f"{conclusion_id} lacks useful uncertainty/falsifier text")
    if failures:
        raise ValueError("; ".join(failures))
    return "four scorecard rows exactly reconcile to wolf, damage, Ne, and localization results"


def dictionary_check(context: Context) -> str:
    dictionary = context.table("results/tables/phase5b_data_dictionary.tsv")
    require_columns(
        dictionary,
        [
            "table", "table_label", "column_position", "column", "storage_dtype",
            "non_missing_rows", "total_rows", "description",
        ],
        "Phase-5B data dictionary",
    )
    if dictionary.duplicated(["table", "column"]).any():
        raise ValueError("data dictionary contains duplicate table/column rows")
    expected_tables = set(TABLE_PATHS.values())
    actual_tables = set(dictionary["table"].astype(str))
    if actual_tables != expected_tables:
        raise ValueError(
            f"dictionary table coverage mismatch; missing={sorted(expected_tables-actual_tables)}, extra={sorted(actual_tables-expected_tables)}"
        )
    failures: list[str] = []
    total_columns = 0
    for relative in sorted(expected_tables):
        source = context.table(relative)
        rows = dictionary.loc[dictionary["table"].astype(str).eq(relative)].sort_values("column_position")
        total_columns += len(source.columns)
        if rows["column"].astype(str).tolist() != list(source.columns):
            failures.append(f"{relative}: column order/coverage mismatch")
            continue
        for row in rows.itertuples(index=False):
            column = str(row.column)
            if int(row.column_position) != list(source.columns).index(column) + 1:
                failures.append(f"{relative}.{column}: position mismatch")
            if int(row.total_rows) != len(source) or int(row.non_missing_rows) != int(source[column].notna().sum()):
                failures.append(f"{relative}.{column}: completeness counts mismatch")
            expected_dtype = expected_storage_dtype(relative, column, source[column])
            if str(row.storage_dtype) != expected_dtype:
                failures.append(f"{relative}.{column}: dtype {row.storage_dtype!r} != {expected_dtype!r}")
            if not definition_is_explicit(column, row.description):
                failures.append(f"{relative}.{column}: missing definition")
    markdown = context.text("results/PHASE5B_DATA_DICTIONARY.md")
    missing_md = [relative for relative in sorted(expected_tables) if f"`{relative}`" not in markdown]
    if missing_md:
        failures.append(f"markdown dictionary omits {missing_md}")
    if failures:
        raise ValueError("; ".join(failures[:16]) + (f"; plus {len(failures)-16} more" if len(failures) > 16 else ""))
    if len(dictionary) != total_columns:
        raise ValueError(f"dictionary row count {len(dictionary)} != source column count {total_columns}")
    return f"{len(expected_tables)} tables and {total_columns} columns have exact order, type, completeness, and definitions"


def parse_browser_payload(text: str) -> dict[str, Any]:
    match = re.fullmatch(
        r"\s*/\*.*?\*/\s*window\.PHASE5B_DATA\s*=\s*(\{.*\})\s*;\s*",
        text,
        flags=re.DOTALL,
    )
    if not match:
        raise ValueError("browser data is not one generated window.PHASE5B_DATA JSON assignment")
    payload = json.loads(match.group(1))
    if not isinstance(payload, dict):
        raise ValueError("browser payload is not an object")
    return payload


def value_matches(
    payload_value: object,
    source_value: object,
    *,
    semantic_string: bool = False,
) -> bool:
    source_missing = source_value is None or (not isinstance(source_value, (list, dict)) and bool(pd.isna(source_value)))
    if isinstance(source_value, numbers.Real) and not isinstance(source_value, (bool, np.bool_)):
        source_missing = source_missing or not math.isfinite(float(source_value))
    if source_missing:
        return payload_value is None
    if semantic_string:
        return payload_value is not None and str(payload_value) == str(source_value)
    if isinstance(source_value, (bool, np.bool_)):
        return isinstance(payload_value, bool) and payload_value is bool(source_value)
    if isinstance(source_value, numbers.Real) and not isinstance(source_value, (bool, np.bool_)):
        return isinstance(payload_value, numbers.Real) and not isinstance(payload_value, bool) and math.isclose(
            float(payload_value), float(source_value), rel_tol=1e-12, abs_tol=1e-12
        )
    return str(payload_value) == str(source_value)


def compare_payload_records(
    records: object,
    source: pd.DataFrame,
    label: str,
    semantic_string_columns: set[str] | None = None,
) -> None:
    if not isinstance(records, list):
        raise ValueError(f"{label} payload is not a list")
    if len(records) != len(source):
        raise ValueError(f"{label} count {len(records)} != source rows {len(source)}")
    expected_columns = list(source.columns)
    semantic_string_columns = semantic_string_columns or set()
    undeclared = semantic_string_columns - set(expected_columns)
    if undeclared:
        raise ValueError(f"{label} semantic string columns absent from source: {sorted(undeclared)}")
    mismatches: list[str] = []
    for index, (record, source_row) in enumerate(zip(records, source.to_dict(orient="records"), strict=True)):
        if not isinstance(record, dict) or list(record.keys()) != expected_columns:
            mismatches.append(f"row {index}: keys differ")
            continue
        for column in expected_columns:
            if not value_matches(
                record[column], source_row[column],
                semantic_string=column in semantic_string_columns,
            ):
                mismatches.append(f"row {index}.{column}: payload={record[column]!r}, source={source_row[column]!r}")
                if len(mismatches) >= 8:
                    break
        if len(mismatches) >= 8:
            break
    if mismatches:
        raise ValueError(f"{label} values differ: {'; '.join(mismatches)}")


def payload_check(context: Context) -> str:
    payload = parse_browser_payload(context.text("website/phase5b-data.js"))
    expected_keys = {
        "schemaVersion", "generatedDate", "wolfAssociations", "wolfLocalization",
        "damageEffects", "neDesign", "claims", "optionalDecisions",
    }
    if set(payload) != expected_keys or payload.get("schemaVersion") != "phase5b-browser-v1":
        raise ValueError(f"browser payload envelope mismatch: keys={sorted(payload)}, schema={payload.get('schemaVersion')!r}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(payload.get("generatedDate", ""))):
        raise ValueError("browser payload generatedDate is not ISO YYYY-MM-DD")

    wolf = context.table(TABLE_PATHS["wolf_associations"])[PAYLOAD_COLUMNS["wolfAssociations"]]
    localization_source = context.table(TABLE_PATHS["localization_cohort"])
    localization = localization_source[[column for column in PAYLOAD_COLUMNS["wolfLocalization"] if column != "beyond_null"]].copy()
    localization["beyond_null"] = beyond_localization_null(localization)
    damage = context.table(TABLE_PATHS["damage_effects"])
    ne = context.table(TABLE_PATHS["ne_summary"])[PAYLOAD_COLUMNS["neDesign"]]
    claims = context.table(TABLE_PATHS["claims"])
    decisions = context.table(TABLE_PATHS["decisions"])
    sources = {
        "wolfAssociations": wolf,
        "wolfLocalization": localization,
        "damageEffects": damage,
        "neDesign": ne,
        "claims": claims,
        "optionalDecisions": decisions,
    }
    for label, source in sources.items():
        compare_payload_records(
            payload[label], source, label,
            semantic_string_columns=PAYLOAD_SEMANTIC_STRING_COLUMNS.get(label, set()),
        )

    if len(wolf) != 60 or len(localization) != 120 or len(damage) != 8 or len(claims) != 6 or len(decisions) != 2:
        raise ValueError("one or more payload source grids has an unexpected row count")
    wolf_keys = {(row["cell_id"], row["outcome"], row["model"]) for row in payload["wolfAssociations"]}
    localization_keys = {(row["POP"], row["gerp_threshold"], row["roh_cutoff_mb"]) for row in payload["wolfLocalization"]}
    ne_keys = {
        (row["analysis_type"], row["population"], row["true_ne"], row["sample_size"], row["marker_density"])
        for row in payload["neDesign"]
    }
    if len(wolf_keys) != 60 or len(localization_keys) != 120 or len(ne_keys) != len(ne):
        raise ValueError("browser payload contains duplicate grid keys")
    return (
        f"exact source values: wolf={len(wolf)}, localization={len(localization)}, damage={len(damage)}, "
        f"Ne={len(ne)}, claims={len(claims)}, decisions={len(decisions)}"
    )


def provenance_check(context: Context) -> str:
    provenance = context.json("results/provenance/phase5b_synthesis.json")
    if provenance.get("schema_version") != "phase5b-synthesis-v1":
        raise ValueError(f"unexpected synthesis schema: {provenance.get('schema_version')!r}")
    inputs = provenance.get("inputs")
    outputs = provenance.get("outputs")
    if not isinstance(inputs, dict) or set(inputs) != set(SYNTHESIS_INPUTS):
        raise ValueError(
            f"synthesis input inventory mismatch; missing={sorted(set(SYNTHESIS_INPUTS)-set(inputs or {}))}, extra={sorted(set(inputs or {})-set(SYNTHESIS_INPUTS))}"
        )
    failures: list[str] = []
    for key, expected_relative in SYNTHESIS_INPUTS.items():
        record = inputs.get(key, {})
        if record.get("path") != expected_relative:
            failures.append(f"input {key} path={record.get('path')!r}, expected={expected_relative!r}")
            continue
        path = context.local_path(expected_relative)
        if not path.is_file() or record.get("sha256") != sha256_file(path):
            failures.append(f"input {key} SHA256 mismatch or file missing")
    if not isinstance(outputs, dict) or set(outputs) != set(SYNTHESIS_OUTPUTS):
        failures.append(f"output inventory differs from exact five synthesis outputs: {sorted((outputs or {}).keys())}")
    else:
        for relative in SYNTHESIS_OUTPUTS:
            path = context.local_path(relative)
            if not path.is_file() or outputs.get(relative) != sha256_file(path):
                failures.append(f"output SHA256 mismatch or file missing: {relative}")
    payload = parse_browser_payload(context.text("website/phase5b-data.js"))
    expected_counts = {key: len(value) for key, value in payload.items() if isinstance(value, list)}
    if provenance.get("browser_payload_counts") != expected_counts:
        failures.append("provenance browser payload counts do not match generated JS")
    if int(provenance.get("claim_count", -1)) != 6 or int(provenance.get("scorecard_rows", -1)) != 4:
        failures.append("provenance claim/scorecard counts are not 6/4")
    dictionary_rows = len(context.table("results/tables/phase5b_data_dictionary.tsv"))
    if int(provenance.get("data_dictionary_rows", -1)) != dictionary_rows:
        failures.append(
            f"provenance dictionary rows={provenance.get('data_dictionary_rows')!r}, actual={dictionary_rows}"
        )
    boundary = str(provenance.get("boundary", "")).lower()
    if "synthesis only" not in boundary or "does not recompute" not in boundary or "upgrade" not in boundary:
        failures.append("provenance does not retain the synthesis-only scientific boundary")
    if failures:
        raise ValueError("; ".join(failures[:14]) + (f"; plus {len(failures)-14} more" if len(failures) > 14 else ""))
    return f"all {len(inputs)} inputs and {len(outputs)} outputs have exact declared paths and SHA256 hashes"


def report_check(context: Context) -> str:
    source = context.text("report/report.qmd")
    values = context.text("report/report_values.py")
    anchors = [
        "damage-aware-falsification", "ne-sample-design-calibration", "wolf-individual-association",
        "wolf-roh-localization", "optional-study-decisions",
    ]
    missing_source = [anchor for anchor in anchors if not anchor_exists(source, anchor)]
    value_tokens = [
        "damage_concordant_metrics", "ne_design_claim", "wolf_partial_realized_ci_positive",
        "roh_localization_support_cells", "section134_decision", "section135_decision",
    ]
    missing_value_references = [
        token for token in value_tokens if not report_dynamic_reference(source, token)
    ]
    path_tokens = [
        TABLE_PATHS["damage_effects"], TABLE_PATHS["ne_summary"], TABLE_PATHS["wolf_associations"],
        TABLE_PATHS["localization_cohort"], TABLE_PATHS["claims"],
    ]
    values_gaps = report_values_contract_gaps(
        values,
        required_paths=path_tokens,
        required_values=value_tokens,
    )
    boundary_terms = [
        "not temporal genetic erosion", "not a guarantee", "not measured individual",
        "fitness", "causal inbreeding depression", "geograph", "shared-parent pedigree",
        "32 one-morgan chromosomes", "hardy–weinberg equilibrium",
        "not independent biological-sampling uncertainty",
    ]
    combined = normalize_whitespace(source).lower()
    missing_boundaries = [term for term in boundary_terms if term not in combined]
    if (
        missing_source
        or missing_value_references
        or any(values_gaps.values())
        or missing_boundaries
    ):
        raise ValueError(
            f"report integration gaps: qmd anchors={missing_source}; "
            f"qmd dynamic values={missing_value_references}; value loader={values_gaps}; "
            f"boundaries={missing_boundaries}"
        )
    return "technical source contains all Phase-5B tables, dynamic values, anchors, and causal limits"


def app_check(context: Context) -> str:
    text = context.text("app/streamlit_app.py")
    required_tables = [
        Path(TABLE_PATHS["wolf_associations"]).name,
        Path(TABLE_PATHS["damage_effects"]).name,
        Path(TABLE_PATHS["ne_summary"]).name,
        Path(TABLE_PATHS["localization_cohort"]).name,
        Path(TABLE_PATHS["claims"]).name,
        Path(TABLE_PATHS["decisions"]).name,
    ]
    required_controls = [
        "Study-design calibration", "Damage-aware museum", "Individual F_ROH",
        "ROH localization of homozygous GERP-weighted derived-allele burden", "Phase-5B claim trace",
        "boundary_confident_pass_rate", "boundary_confident_fail_rate",
        "snakemake --snakefile workflow/Snakefile phase5b --cores 4 --resources mem_mb=7000",
    ]
    required_boundaries = [
        "associations among genomic", "sampling guarantee", "geograph",
        "temporal-erosion claim", "no fitness phenotype", "cannot demonstrate inbreeding depression",
        "never scored as correct or incorrect", "not independent biological-sampling uncertainty",
    ]
    stale_phrases = [
        "snakemake --snakefile workflow/Snakefile all --cores 4 --resources mem_mb=7000",
        "never scored correct or incorrect",
    ]
    missing_tables, _ = python_literal_contract_gaps(text, required=required_tables)
    missing_panels, stale = python_literal_contract_gaps(
        text,
        required=required_controls,
        stale=stale_phrases,
    )
    missing_boundaries, _ = python_literal_contract_gaps(
        text,
        required=required_boundaries,
        case_sensitive=False,
    )
    missing = {
        "tables": missing_tables,
        "panels": missing_panels,
        "code": [] if re.search(r"\bint\s*\(\s*design_truth\s*\)\s*==\s*500\b", text) else ["int(design_truth) == 500"],
        "boundaries": missing_boundaries,
        "stale": stale,
    }
    missing = {key: value for key, value in missing.items() if value}
    if missing:
        raise ValueError(f"Streamlit Phase-5B integration gaps: {missing}")
    return "read-only explorer loads all six trace/result tables and exposes four panels plus scientific boundaries"


def static_site_check(context: Context) -> str:
    html = context.text("index.html")
    javascript = context.text("website/site.js")
    css = context.text("website/site.css")
    ordered_path = ["Question", "Prediction", "Stress test", "Result", "Correction", "Falsifier", "Conservation consequence"]
    positions = [html.find(f"<span>{label}</span>") for label in ordered_path]
    required_html = [
        'src="website/phase5b-data.js"', "data-phase5b-lab", "data-claim-trace-list",
        "data-wolf-gerp", "data-damage-variant", "data-ne-truth", "data-localization-pop",
        "data-ne-correct-label", "data-ne-incorrect-label",
        'id="wolf-robustness"', 'id="damage-falsification"', 'id="ne-design"',
        'id="wolf-roh-localization"', "Not observed:", "15 / 15", "1 / 4", "0 / 1",
        "snakemake --snakefile workflow/Snakefile phase5b --cores 4 --resources mem_mb=7000",
    ]
    required_js = [
        "window.PHASE5B_DATA", "disablePhase5b", "wolfAssociations", "damageEffects",
        "neDesign", "wolfLocalization", "data-missing-asset", "replaceChildren",
        "selectedTruth === 500", "boundary_confident_pass_rate",
        "boundary_confident_fail_rate",
    ]
    required_css = [
        ".phase5b-lab", ".mind-grid", ".science-path", "@media (max-width: 620px)",
        "@media (prefers-reduced-motion: reduce)",
    ]
    missing_html = [token for token in required_html if token not in html]
    missing_js = [token for token in required_js if token not in javascript]
    missing_css = [token for token in required_css if token not in css]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        missing_html.append("ordered seven-step scientific path")
    lower_html = html.lower()
    boundary_terms = [
        "not measured fitness", "geography is confounded with period", "not a guarantee",
        "not individual harm", "causal inbreeding depression",
        "not independent biological-sampling uncertainty",
    ]
    missing_boundaries = [term for term in boundary_terms if term not in lower_html]
    if "fetch(" in javascript:
        missing_js.append("no fetch() allowed in offline decision layer")
    if missing_html or missing_js or missing_css or missing_boundaries:
        raise ValueError(
            f"static portal gaps: html={missing_html}; js={missing_js}; css={missing_css}; boundaries={missing_boundaries}"
        )
    return "offline site has four native result controls, exact reasoning path, missing-data fallbacks, responsive CSS, and no fetch"


def inventory_check(context: Context) -> str:
    inventory = context.table(TABLE_PATHS["inventory"])
    require_columns(inventory, ["definition", "scope", "annotation_class", "n_unique_sites", "duplicate_site_keys"], "annotation inventory")
    observed = (
        inventory.loc[inventory["scope"].astype(str).eq("autosomes_1_38")]
        .set_index(["definition", "annotation_class"])["n_unique_sites"]
        .astype(int)
        .to_dict()
    )
    expected = {
        ("VEP", "synonymous"): 33895,
        ("VEP", "missense"): 24405,
        ("VEP", "nonsense"): 1023,
        ("SIFT", "deleterious"): 4809,
        ("SIFT", "tolerated"): 12981,
    }
    duplicates = int(pd.to_numeric(inventory["duplicate_site_keys"]).sum())
    if observed != expected or duplicates != 0:
        raise ValueError(f"annotation inventory mismatch: observed={observed}; duplicates={duplicates}")
    decisions = context.table(TABLE_PATHS["decisions"])
    row = decisions.loc[decisions["section"].astype(str).eq("13.5")]
    if len(row) != 1 or "10.1111/mec.16802" not in str(row.iloc[0]["source_trace"]) or "10.5061/dryad.7m0cfxpzj" not in str(row.iloc[0]["source_trace"]):
        raise ValueError("13.5 decision does not trace both primary paper and Dryad deposit")
    return "autosomal VEP/SIFT inventory exactly matches five deposited classes; source paper and deposit traced"


def required_files_check(context: Context) -> str:
    required = set(TABLE_PATHS.values()) | set(VALIDATORS.values()) | set(SYNTHESIS_OUTPUTS) | {
        "results/provenance/phase5b_synthesis.json",
        "results/tables/validation_phase5b_core_integration.tsv",
        "report/report.qmd", "report/report_values.py",
        "app/streamlit_app.py", "index.html", "website/site.js", "website/site.css",
        "workflow/rules/phase5b.smk", "results/wolf/popmap.tsv", "config/peafowl_popmap.tsv",
    }
    required.update(SYNTHESIS_INPUTS.values())
    missing = sorted(relative for relative in required if not context.path(relative).is_file())
    if missing:
        raise FileNotFoundError(f"missing {len(missing)} required artifacts: {missing}")
    return f"all {len(required)} required scientific, synthesis, provenance, and interface artifacts exist"


def write_reports(audit: Audit, out_tsv: Path, out_md: Path) -> int:
    frame = audit.frame()
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out_tsv, sep="\t", index=False, lineterminator="\n")
    passes = int(frame["status"].eq("PASS").sum())
    failures = int(frame["status"].eq("FAIL").sum())
    lines = [
        "# Phase 5B final synthesis validation",
        "",
        "This independent fail-closed gate recomputes every claim-level decision from delivered result tables, audits the 1.5-Mb localization rule, and verifies the offline traceability layer without importing an analysis or synthesis implementation.",
        "",
        f"**Summary: {passes} PASS, 0 WARN, {failures} FAIL**",
        "",
        "| check | status | evidence |",
        "|---|---|---|",
    ]
    for row in frame.itertuples(index=False):
        detail = str(row.detail).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {row.check} | **{row.status}** | {detail} |")
    lines.extend(
        [
            "",
            "A negative, deferred, indeterminate, or null-compatible scientific result is valid when it reconciles to its frozen rule. A missing row, failed upstream validator, broken trace, changed hash, or softened causal boundary is not.",
            "",
        ]
    )
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(frame.to_string(index=False))
    print(f"\nPhase 5B final validation: {passes} PASS, 0 WARN, {failures} FAIL")
    return failures


def self_test() -> None:
    fixture = pd.DataFrame(
        {
            "log2_enrichment": [1.1, 1.0, 1.1, np.nan],
            "null_ci_high": [1.0, 1.0, 1.0, 0.0],
            "permutation_p_two_sided": [0.05, 0.01, 0.051, 0.01],
        }
    )
    assert beyond_localization_null(fixture).tolist() == [True, False, False, False]
    assert truthy(True) and truthy("TRUE") and not truthy("false")
    assert number_equal("0.70", 0.7) and not number_equal(float("nan"), float("nan"))
    payload = parse_browser_payload(
        '/* generated */\nwindow.PHASE5B_DATA = {"schemaVersion":"phase5b-browser-v1","x":[]};\n'
    )
    assert payload["x"] == []
    assert anchor_exists('<section id="wolf-roh-localization">', "wolf-roh-localization")
    assert anchor_exists(
        "## Wolf localization {#wolf-roh-localization}", "wolf-roh-localization"
    )
    assert pre_render_anchor_path(
        "report_anchor", "report/report.html"
    ) == "report/report.qmd"
    semantic_source = pd.DataFrame({"section": [13.1], "observed_value": [15]})
    compare_payload_records(
        [{"section": "13.1", "observed_value": 15}],
        semantic_source,
        "semantic fixture",
        semantic_string_columns={"section"},
    )
    try:
        compare_payload_records(
            [{"section": "13.1", "observed_value": 16}],
            semantic_source,
            "numeric fixture",
            semantic_string_columns={"section"},
        )
    except ValueError:
        pass
    else:
        raise AssertionError("semantic string handling weakened numeric payload comparison")
    python_fixture = (
        'caption = ("never " "scored as correct or incorrect")\n'
        'command = ("snakemake --snakefile workflow/Snakefile phase5b " '
        '"--cores 4 --resources mem_mb=7000")\n'
    )
    string_corpus = python_string_corpus(python_fixture)
    assert "never scored as correct or incorrect" in string_corpus
    assert (
        "snakemake --snakefile workflow/Snakefile phase5b --cores 4 "
        "--resources mem_mb=7000" in string_corpus
    )
    required, stale = python_literal_contract_gaps(
        python_fixture,
        required=[
            "never scored as correct or incorrect",
            "snakemake --snakefile workflow/Snakefile phase5b --cores 4 "
            "--resources mem_mb=7000",
        ],
        stale=[
            "never scored correct or incorrect",
            "snakemake --snakefile workflow/Snakefile all --cores 4 "
            "--resources mem_mb=7000",
        ],
    )
    assert required == [] and stale == []
    _, stale = python_literal_contract_gaps(
        'caption = "never scored correct or incorrect"\n',
        required=[],
        stale=["never scored correct or incorrect"],
    )
    assert stale == ["never scored correct or incorrect"]
    report_qmd_fixture = (
        "## Result {#phase5b-result}\n"
        "`{python} R.metric_value`\n"
        "not independent\nbiological-sampling uncertainty\n"
    )
    report_values_fixture = (
        'SOURCE_FILES = {"Result": "results/tables/result.tsv"}\n'
        "def _read(path):\n"
        '    return pd.read_csv(path, sep="\\t")\n'
        "def load_values():\n"
        "    return SimpleNamespace(metric_value=1)\n"
    )
    assert report_dynamic_reference(report_qmd_fixture, "metric_value")
    report_gaps = report_values_contract_gaps(
        report_values_fixture,
        required_paths=["results/tables/result.tsv"],
        required_values=["metric_value"],
    )
    assert report_gaps == {"tables": [], "dynamic values": [], "loader": [], "writes": []}
    mutating_gaps = report_values_contract_gaps(
        report_values_fixture + "def mutate(frame):\n    frame.to_csv('changed.tsv')\n",
        required_paths=["results/tables/result.tsv"],
        required_values=["metric_value"],
    )
    assert mutating_gaps["writes"] == ["to_csv"]
    assert "not independent biological-sampling uncertainty" in normalize_whitespace(
        report_qmd_fixture
    )
    assert expected_storage_dtype(
        TABLE_PATHS["claims"], "section", pd.Series([13.1])
    ) == "str"
    assert expected_storage_dtype(
        TABLE_PATHS["claims"], "change_threshold", pd.Series(["12", "1/4"])
    ) == "object"
    assert expected_storage_dtype(
        TABLE_PATHS["scorecard"], "section", pd.Series([13.1])
    ) == "str"
    assert expected_storage_dtype(
        TABLE_PATHS["wolf_scores"], "score", pd.Series([1.0])
    ) == "float64"
    assert definition_is_explicit("k", "K.") and definition_is_explicit("n", "N.")
    assert definition_is_explicit(
        "k", "Estimated full-sibling counterparts for one individual."
    )
    assert definition_is_explicit("n", "Number of observations represented by this row.")
    assert not definition_is_explicit("k", "Estimated value.")
    assert not definition_is_explicit("n", "Sample count.")
    assert definition_is_explicit("estimate", "Estimated effect.")
    assert not definition_is_explicit("x", "X.")
    localization_boundary_fixture = (
        "Spatial co-localization among genomic proxies provides mechanistic support; "
        "it does not establish phenotypic consequences."
    ).lower()
    localization_terms = REQUIRED_SCIENTIFIC_BOUNDARY_TERMS[
        "wolf_roh_localized_realized_burden"
    ]
    assert all(term in localization_boundary_fixture for term in localization_terms)
    assert "mechanistic support" in localization_terms and "mechanism" not in localization_terms
    report_anchors = [
        "damage-aware-falsification", "ne-sample-design-calibration",
        "wolf-individual-association", "wolf-roh-localization", "optional-study-decisions",
    ]
    report_values = [
        "damage_concordant_metrics", "ne_design_claim", "wolf_partial_realized_ci_positive",
        "roh_localization_support_cells", "section134_decision", "section135_decision",
    ]
    report_paths = [
        TABLE_PATHS["damage_effects"], TABLE_PATHS["ne_summary"],
        TABLE_PATHS["wolf_associations"], TABLE_PATHS["localization_cohort"],
        TABLE_PATHS["claims"],
    ]
    source_only_qmd = "\n".join(
        [f"## Result {{#{anchor}}}" for anchor in report_anchors]
        + [f"`{{python}} R.{value}`" for value in report_values]
        + [
            "not temporal genetic erosion", "not a guarantee", "not measured individual",
            "fitness", "causal inbreeding depression", "geograph", "shared-parent pedigree",
            "32 one-morgan chromosomes", "hardy–weinberg equilibrium",
            "not independent biological-sampling uncertainty",
        ]
    )
    source_only_values = (
        f"SOURCE_FILES = {dict(enumerate(report_paths))!r}\n"
        "def _read(path):\n    return pd.read_csv(path)\n"
        "def load_values():\n    return SimpleNamespace("
        + ", ".join(f"{value}=1" for value in report_values)
        + ")\n"
    )

    class SourceOnlyReportContext:
        def text(self, relative: str) -> str:
            sources = {
                "report/report.qmd": source_only_qmd,
                "report/report_values.py": source_only_values,
            }
            return sources[relative]

    assert report_check(SourceOnlyReportContext()).startswith("technical source")
    audit = Audit()
    audit.run("success", lambda: "ok")
    audit.run("caught exception", lambda: (_ for _ in ()).throw(ValueError("fixture failure")))
    assert audit.frame()["status"].tolist() == ["PASS", "FAIL"]
    print("validate_phase5b self-test: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT), help="project root containing config/, results/, and website/")
    parser.add_argument("--out-tsv", default="results/tables/validation_phase5b.tsv")
    parser.add_argument("--out-md", default="results/PHASE5B_VALIDATION.md")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    root = Path(args.root).absolute()
    context = Context(root)
    audit = Audit()
    audit.run("complete Phase-5B artifact set exists", lambda: required_files_check(context))
    for label, relative in VALIDATORS.items():
        audit.run(f"{label} validator is clear", lambda label=label, relative=relative: inspect_validator(context, label, relative))
    audit.run("claim trace has the exact six claims and schema", lambda: claims_schema_check(context))
    audit.run("all claim trace targets and anchors resolve locally", lambda: trace_targets_check(context))
    audit.run("claim observed values and falsifiers independently reconcile", lambda: claims_numeric_check(context))
    audit.run("1.5-Mb wolf localization support count independently reconciles", lambda: localization_check(context))
    audit.run("13.5 annotation deferral inventory independently reconciles", lambda: inventory_check(context))
    audit.run("claim-level scientific boundaries remain explicit", lambda: scientific_boundaries_check(context))
    audit.run("Phase-5B fragility scorecard has four reconciled rows", lambda: scorecard_check(context))
    audit.run("Phase-5B data dictionary covers every delivered table column", lambda: dictionary_check(context))
    audit.run("offline Phase-5B JavaScript payload exactly matches source tables", lambda: payload_check(context))
    audit.run("synthesis provenance input and output SHA256 values reconcile", lambda: provenance_check(context))
    audit.run("technical report integrates Phase-5B results and boundaries", lambda: report_check(context))
    audit.run("Streamlit explorer integrates read-only Phase-5B results", lambda: app_check(context))
    audit.run("static portal integrates offline Phase-5B evidence", lambda: static_site_check(context))

    out_tsv = Path(args.out_tsv)
    out_md = Path(args.out_md)
    if not out_tsv.is_absolute():
        out_tsv = root / out_tsv
    if not out_md.is_absolute():
        out_md = root / out_md
    failures = write_reports(audit, out_tsv, out_md)
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise
    except SystemExit:
        raise
    except Exception as error:
        # A failure before Audit construction should still be useful at the CLI.
        print(f"validate_phase5b fatal error: {compact_exception(error)}", file=sys.stderr)
        raise SystemExit(1)
