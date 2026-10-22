# workflow/rules/phase5b.smk — Phase 5B scientific-impact extension
#
# The dependency chain is intentional and encodes CGplan §13's locked order:
#
#   13.1 wolf robustness validator
#     -> 13.3 damage falsification validator
#       -> 13.2 N_e design validator
#         -> 13.6 core communication validator
#           -> 13.4/13.5 optional-study decision validator
#             -> 13.4 chromosome workers, collation, and validator (gate opened)
#
# A downstream rule names the preceding validator TSV as an input even when the
# analysis program does not read it.  This makes a failed scientific gate stop
# the DAG before the next section starts, rather than merely documenting order.
# Phase 5B remains offline at run time: every data input is local and simulations
# are bounded by config/config.yaml.


# Exact byte-level trust boundary recorded for the final clean verification.
# These are deliberately paths, not directory globs: a missing, extra, renamed,
# or byte-changed input must invalidate the manifest and the release gate.
PHASE5B_FROZEN_UPSTREAM_INPUTS = sorted([
    "results/qc/comparative.norm.vcf.gz",
    "results/qc/setA.standard.vcf.gz",
    "results/qc/temporal_popmap.tsv",
    "results/tables/validation_phase4.tsv",
    "results/tables/wolf_load.tsv",
    "results/tables/wolf_roh.tsv",
    "results/wolf/autosome_lengths.tsv",
    "results/wolf/popmap.tsv",
    "results/wolf/samples.txt",
] + [
    path
    for chromosome in range(1, 39)
    for path in (
        f"results/wolf/gerp/chr{chromosome}.bed",
        f"results/wolf/load/chr{chromosome}.tsv",
        f"results/wolf/roh/chr{chromosome}.rg.txt",
    )
])

PHASE5B_EXTERNAL_SOURCE_LEAVES = sorted([
    "data/peafowl/raw/Comparative_genomic_dataset_F.vcf.gz",
    "data/wolf/gerp/100S95F14R.chr1-38.allSNPs.rates.unique.bed",
    "data/wolf/vcf/Pol.2out.mac2/100S95F14R.chr1-38.allSNPs.wfm.vcf.gz",
    "data/wolf/vcf/Pol.2out.mac2/100S95F14R.chr1-38.allSNPs.wfm.vcf.gz.csi",
    "data/wolf/vcf/Pol.2out.mac2/100S95F14R.chr1-38.vepfinal.wfm.vcf.gz",
    "data/wolf/vep/Pol.2out.mac2/sifttypes.chr1-X.txt",
    "data/wolf/vep/Pol.2out.mac2/veptypes.chr1-X.txt",
])

if len(PHASE5B_FROZEN_UPSTREAM_INPUTS) != 123:
    raise ValueError("Phase-5B frozen-upstream manifest contract must contain 123 paths")
if len(set(PHASE5B_FROZEN_UPSTREAM_INPUTS)) != 123:
    raise ValueError("Phase-5B frozen-upstream manifest paths must be unique")
if len(PHASE5B_EXTERNAL_SOURCE_LEAVES) != 7:
    raise ValueError("Phase-5B external-source manifest contract must contain 7 paths")
if len(set(PHASE5B_EXTERNAL_SOURCE_LEAVES)) != 7:
    raise ValueError("Phase-5B external-source manifest paths must be unique")

PHASE5B_INPUT_MANIFEST_OUTPUTS = [
    "results/provenance/phase5b_frozen_upstream_inputs.tsv",
    "results/provenance/phase5b_external_source_leaves.tsv",
]


WOLF_ROBUSTNESS_OUTPUTS = [
    "results/tables/wolf_froh_load_associations.tsv",
    "results/tables/wolf_froh_load_rank_stability.tsv",
    "results/tables/wolf_froh_load_individual_scores.tsv",
    "results/tables/wolf_froh_load_figure_values.tsv",
    "results/figures/wolf_froh_load_surface.png",
    "results/figures/wolf_froh_load_forest.png",
    "results/provenance/wolf_froh_load.json",
    "results/tables/validation_wolf_robustness.tsv",
    "results/WOLF_ROBUSTNESS_VALIDATION.md",
]

PEAFOWL_DAMAGE_OUTPUTS = [
    "results/tables/peafowl_damage_effects.tsv",
    "results/tables/peafowl_damage_permutations.tsv",
    "results/tables/peafowl_damage_influence.tsv",
    "results/tables/peafowl_damage_blocks.tsv",
    "results/tables/peafowl_damage_classification.tsv",
    "results/tables/peafowl_damage_figure_values.tsv",
    "results/figures/peafowl_damage_falsification.png",
    "results/provenance/peafowl_damage.json",
    "results/tables/validation_peafowl_damage.tsv",
    "results/PEAFOWL_DAMAGE_VALIDATION.md",
]

PEAFOWL_NE_DESIGN_OUTPUTS = [
    "results/tables/peafowl_ne_design_replicates.tsv",
    "results/tables/peafowl_ne_design_pilot.tsv",
    "results/tables/peafowl_ne_design_summary.tsv",
    "results/tables/peafowl_ne_design_empirical.tsv",
    "results/tables/peafowl_ne_design_figure_values.tsv",
    "results/figures/peafowl_ne_design.png",
    "results/provenance/peafowl_ne_design.json",
    "results/tables/validation_peafowl_ne_design.tsv",
    "results/PEAFOWL_NE_DESIGN_VALIDATION.md",
]

# Atomic completion marker for restartable private estimator checkpoints.  It
# belongs to the workflow target but deliberately not to
# PHASE5B_PUBLIC_ARTIFACTS or the sendable ZIP.
PHASE5B_INTERNAL_OUTPUTS = [
    "results/ne/design/CACHE_MANIFEST.json",
]

PHASE5B_CORE_INTEGRATION_OUTPUTS = [
    "results/tables/phase5b_core_claim_contract.tsv",
    "results/provenance/phase5b_core_integration.json",
    "results/tables/validation_phase5b_core_integration.tsv",
    "results/PHASE5B_CORE_INTEGRATION_VALIDATION.md",
]

PHASE5B_OPTIONAL_DECISION_OUTPUTS = [
    "results/tables/phase5b_optional_decisions.tsv",
    "results/tables/phase5b_annotation_inventory.tsv",
    "results/provenance/phase5b_optional_decisions.json",
    "results/tables/validation_phase5b_decisions.tsv",
    "results/PHASE5B_DECISIONS_VALIDATION.md",
]

WOLF_ROH_LOCALIZATION_OUTPUTS = [
    "results/tables/wolf_roh_localization_individual.tsv",
    "results/tables/wolf_roh_localization_cohort.tsv",
    "results/tables/wolf_roh_localization_null.tsv",
    "results/tables/wolf_roh_localization_qc.tsv",
    "results/tables/wolf_roh_localization_figure_values.tsv",
    "results/figures/wolf_roh_localization_forest.png",
    "results/figures/wolf_roh_localization_ribbon.png",
    "results/provenance/wolf_roh_localization.json",
    "results/tables/validation_wolf_roh_localization.tsv",
    "results/WOLF_ROH_LOCALIZATION_VALIDATION.md",
]

PHASE5B_INTEGRATION_OUTPUTS = [
    "results/tables/phase5b_claim_trace.tsv",
    "results/tables/phase5b_fragility_scorecard.tsv",
    "results/tables/phase5b_data_dictionary.tsv",
    "results/PHASE5B_DATA_DICTIONARY.md",
    "website/phase5b-data.js",
    "results/provenance/phase5b_synthesis.json",
    "results/tables/validation_phase5b.tsv",
    "results/PHASE5B_VALIDATION.md",
]

PHASE5B_RELEASE_CONTENT_OUTPUTS = [
    "results/tables/validation_phase5b_release_content.tsv",
    "results/PHASE5B_RELEASE_CONTENT_VALIDATION.md",
]

PHASE5B = (
    PHASE5B_INPUT_MANIFEST_OUTPUTS
    + WOLF_ROBUSTNESS_OUTPUTS
    + PEAFOWL_DAMAGE_OUTPUTS
    + PEAFOWL_NE_DESIGN_OUTPUTS
    + PHASE5B_CORE_INTEGRATION_OUTPUTS
    + PHASE5B_OPTIONAL_DECISION_OUTPUTS
    + WOLF_ROH_LOCALIZATION_OUTPUTS
    + PHASE5B_INTEGRATION_OUTPUTS
    + PHASE5B_INTERNAL_OUTPUTS
)

# The named Phase-5B target is the reviewer-facing completion target, not only
# a scientific-table aggregate.  Each artifact below is produced by a rule in
# polish.smk after the final Phase-5B scientific validator passes.
PHASE5B_DELIVERY_OUTPUTS = [
    *PHASE5B_RELEASE_CONTENT_OUTPUTS,
    "brief/research_brief.html",
    "report/report.html",
    "results/APP_SMOKE.md",
    "results/logs/app_smoke.log",
    "results/PHASE5A_VALIDATION.md",
    "results/WEBSITE_VALIDATION.md",
    "dist/conservation-genomics-reanalysis.zip",
    "results/WEBSITE_BUNDLE_VALIDATION.md",
    "results/tables/validation_phase5b_delivery.tsv",
    "results/PHASE5B_DELIVERY_VALIDATION.md",
]

PHASE5B_COMPLETE = PHASE5B + PHASE5B_DELIVERY_OUTPUTS


rule phase5b_input_manifests:
    """Persist exact path-and-byte manifests for both Phase-5B input classes."""
    input:
        frozen   = PHASE5B_FROZEN_UPSTREAM_INPUTS,
        external = PHASE5B_EXTERNAL_SOURCE_LEAVES,
        script   = "scripts/python/build_phase5b_input_manifests.py",
    output:
        frozen   = "results/provenance/phase5b_frozen_upstream_inputs.tsv",
        external = "results/provenance/phase5b_external_source_leaves.tsv",
    log: "results/logs/build_phase5b_input_manifests.log"
    threads: 1
    resources:
        mem_mb = 512
    shell:
        "python {input.script} --root . "
        "--frozen-inputs {input.frozen} --external-inputs {input.external} "
        "--out-frozen {output.frozen} --out-external {output.external} "
        "> {log} 2>&1 || (cat {log}; exit 1)"


rule wolf_froh_load_robustness:
    """Evaluate the frozen 3 x 5 wolf F_ROH-load robustness surface (13.1)."""
    input:
        phase4_gate = "results/tables/validation_phase4.tsv",
        load        = "results/tables/wolf_load.tsv",
        roh         = "results/tables/wolf_roh.tsv",
        config      = "config/config.yaml",
        script      = "scripts/python/wolf_froh_load_robustness.py",
    output:
        associations     = "results/tables/wolf_froh_load_associations.tsv",
        rank_stability   = "results/tables/wolf_froh_load_rank_stability.tsv",
        individual_scores = "results/tables/wolf_froh_load_individual_scores.tsv",
        figure_values    = "results/tables/wolf_froh_load_figure_values.tsv",
        surface_figure   = "results/figures/wolf_froh_load_surface.png",
        forest_figure    = "results/figures/wolf_froh_load_forest.png",
        provenance       = "results/provenance/wolf_froh_load.json",
    log: "results/logs/wolf_froh_load_robustness.log"
    threads: 1
    resources:
        mem_mb = 4096
    shell:
        "python {input.script} --load {input.load} --roh {input.roh} "
        "--config {input.config} --output-root . "
        "> {log} 2>&1 || (cat {log}; exit 1)"


rule validate_wolf_robustness:
    """Independently reconcile all wolf grid, uncertainty, ranking, and figure values."""
    input:
        load              = "results/tables/wolf_load.tsv",
        roh               = "results/tables/wolf_roh.tsv",
        config            = "config/config.yaml",
        associations      = "results/tables/wolf_froh_load_associations.tsv",
        rank_stability    = "results/tables/wolf_froh_load_rank_stability.tsv",
        individual_scores = "results/tables/wolf_froh_load_individual_scores.tsv",
        figure_values     = "results/tables/wolf_froh_load_figure_values.tsv",
        surface_figure    = "results/figures/wolf_froh_load_surface.png",
        forest_figure     = "results/figures/wolf_froh_load_forest.png",
        provenance        = "results/provenance/wolf_froh_load.json",
        analysis_script   = "scripts/python/wolf_froh_load_robustness.py",
        script            = "scripts/python/validate_wolf_robustness.py",
    output:
        tsv = "results/tables/validation_wolf_robustness.tsv",
        md  = "results/WOLF_ROBUSTNESS_VALIDATION.md",
    log: "results/logs/validate_wolf_robustness.log"
    threads: 1
    resources:
        mem_mb = 4096
    shell:
        "python {input.script} --root . --out-tsv {output.tsv} --out-md {output.md} "
        "> {log} 2>&1 || (cat {log}; exit 1)"


rule peafowl_damage_falsification:
    """Run the damage-aware museum-modern falsification after 13.1 passes (13.3)."""
    input:
        wolf_gate      = "results/tables/validation_wolf_robustness.tsv",
        config         = "config/config.yaml",
        raw_vcf        = "data/peafowl/raw/Comparative_genomic_dataset_F.vcf.gz",
        normalized_vcf = "results/qc/comparative.norm.vcf.gz",
        popmap         = "results/qc/temporal_popmap.tsv",
        autosomes      = "config/peafowl_autosomes.txt",
        script         = "scripts/python/peafowl_damage_falsification.py",
    output:
        effects        = "results/tables/peafowl_damage_effects.tsv",
        permutations   = "results/tables/peafowl_damage_permutations.tsv",
        influence      = "results/tables/peafowl_damage_influence.tsv",
        blocks         = "results/tables/peafowl_damage_blocks.tsv",
        classification = "results/tables/peafowl_damage_classification.tsv",
        figure_values  = "results/tables/peafowl_damage_figure_values.tsv",
        figure         = "results/figures/peafowl_damage_falsification.png",
        provenance     = "results/provenance/peafowl_damage.json",
    log: "results/logs/peafowl_damage_falsification.log"
    threads: 1
    resources:
        mem_mb = 4096
    shell:
        "python {input.script} --config {input.config} --raw-vcf {input.raw_vcf} "
        "--normalized-vcf {input.normalized_vcf} --popmap {input.popmap} "
        "--autosomes {input.autosomes} --out-effects {output.effects} "
        "--out-permutations {output.permutations} --out-influence {output.influence} "
        "--out-blocks {output.blocks} --out-classification {output.classification} "
        "--out-figure-values {output.figure_values} --out-figure {output.figure} "
        "--out-provenance {output.provenance} > {log} 2>&1 || (cat {log}; exit 1)"


rule validate_peafowl_damage:
    """Independently rerun the damage classification, exact allocation, and CI checks."""
    input:
        config          = "config/config.yaml",
        raw_vcf         = "data/peafowl/raw/Comparative_genomic_dataset_F.vcf.gz",
        normalized_vcf  = "results/qc/comparative.norm.vcf.gz",
        popmap          = "results/qc/temporal_popmap.tsv",
        autosomes       = "config/peafowl_autosomes.txt",
        effects         = "results/tables/peafowl_damage_effects.tsv",
        permutations    = "results/tables/peafowl_damage_permutations.tsv",
        influence       = "results/tables/peafowl_damage_influence.tsv",
        blocks          = "results/tables/peafowl_damage_blocks.tsv",
        classification  = "results/tables/peafowl_damage_classification.tsv",
        figure_values   = "results/tables/peafowl_damage_figure_values.tsv",
        figure          = "results/figures/peafowl_damage_falsification.png",
        provenance      = "results/provenance/peafowl_damage.json",
        analysis_script = "scripts/python/peafowl_damage_falsification.py",
        script          = "scripts/python/validate_peafowl_damage.py",
    output:
        tsv = "results/tables/validation_peafowl_damage.tsv",
        md  = "results/PEAFOWL_DAMAGE_VALIDATION.md",
    log: "results/logs/validate_peafowl_damage.log"
    threads: 1
    resources:
        mem_mb = 4096
    shell:
        "python {input.script} --config {input.config} --raw-vcf {input.raw_vcf} "
        "--normalized-vcf {input.normalized_vcf} --popmap {input.popmap} "
        "--autosomes {input.autosomes} --effects {input.effects} "
        "--permutations {input.permutations} --influence {input.influence} "
        "--blocks {input.blocks} --classification {input.classification} "
        "--figure-values {input.figure_values} --figure {input.figure} "
        "--provenance {input.provenance} --out-tsv {output.tsv} --out-md {output.md} "
        "> {log} 2>&1 || (cat {log}; exit 1)"


rule peafowl_ne_design:
    """Run the bounded pilot/expansion and empirical N_e calibration after 13.3."""
    input:
        damage_gate  = "results/tables/validation_peafowl_damage.tsv",
        config       = "config/config.yaml",
        empirical_vcf = "results/qc/setA.standard.vcf.gz",
        popmap       = "config/peafowl_popmap.tsv",
        currentne2   = "tools/currentNe2/currentne2",
        parser       = "scripts/python/currentne2_parse.py",
        script       = "scripts/python/peafowl_ne_design.py",
    output:
        replicates    = "results/tables/peafowl_ne_design_replicates.tsv",
        pilot         = "results/tables/peafowl_ne_design_pilot.tsv",
        summary       = "results/tables/peafowl_ne_design_summary.tsv",
        empirical     = "results/tables/peafowl_ne_design_empirical.tsv",
        figure_values = "results/tables/peafowl_ne_design_figure_values.tsv",
        figure        = "results/figures/peafowl_ne_design.png",
        provenance    = "results/provenance/peafowl_ne_design.json",
        cache_manifest = "results/ne/design/CACHE_MANIFEST.json",
    log: "results/logs/peafowl_ne_design.log"
    threads: 1
    resources:
        mem_mb = 4096
    shell:
        "python {input.script} --config {input.config} "
        "--empirical-vcf {input.empirical_vcf} --popmap {input.popmap} "
        "--currentne2 {input.currentne2} --out-replicates {output.replicates} "
        "--out-pilot {output.pilot} --out-summary {output.summary} "
        "--out-empirical {output.empirical} --out-figure-values {output.figure_values} "
        "--out-figure {output.figure} --out-provenance {output.provenance} "
        "--raw-dir results/ne/design --cache-manifest {output.cache_manifest} "
        "> {log} 2>&1 || (cat {log}; exit 1)"


rule validate_peafowl_ne_design:
    """Reconcile scenario truth, decisions, failures, pilot repeatability, and plots."""
    input:
        config          = "config/config.yaml",
        empirical_vcf   = "results/qc/setA.standard.vcf.gz",
        popmap          = "config/peafowl_popmap.tsv",
        currentne2      = "tools/currentNe2/currentne2",
        parser          = "scripts/python/currentne2_parse.py",
        replicates      = "results/tables/peafowl_ne_design_replicates.tsv",
        pilot           = "results/tables/peafowl_ne_design_pilot.tsv",
        summary         = "results/tables/peafowl_ne_design_summary.tsv",
        empirical       = "results/tables/peafowl_ne_design_empirical.tsv",
        figure_values   = "results/tables/peafowl_ne_design_figure_values.tsv",
        figure          = "results/figures/peafowl_ne_design.png",
        provenance      = "results/provenance/peafowl_ne_design.json",
        cache_manifest  = "results/ne/design/CACHE_MANIFEST.json",
        analysis_script = "scripts/python/peafowl_ne_design.py",
        script          = "scripts/python/validate_peafowl_ne_design.py",
    params:
        raw_dir = "results/ne/design",
    output:
        tsv = "results/tables/validation_peafowl_ne_design.tsv",
        md  = "results/PEAFOWL_NE_DESIGN_VALIDATION.md",
    log: "results/logs/validate_peafowl_ne_design.log"
    threads: 1
    resources:
        mem_mb = 4096
    shell:
        "python {input.script} --config {input.config} --popmap {input.popmap} "
        "--empirical-vcf {input.empirical_vcf} --currentne2 {input.currentne2} "
        "--replicates {input.replicates} --pilot {input.pilot} "
        "--summary {input.summary} --empirical {input.empirical} "
        "--figure-values {input.figure_values} --figure {input.figure} "
        "--provenance {input.provenance} --raw-dir {params.raw_dir} "
        "--cache-manifest {input.cache_manifest} "
        "--out-tsv {output.tsv} --out-md {output.md} "
        "> {log} 2>&1 || (cat {log}; exit 1)"


rule phase5b_core_integration:
    """Freeze the three core claim contracts before optional-study decisions (13.6)."""
    input:
        wolf_gate        = "results/tables/validation_wolf_robustness.tsv",
        damage_gate      = "results/tables/validation_peafowl_damage.tsv",
        ne_gate          = "results/tables/validation_peafowl_ne_design.tsv",
        wolf             = "results/tables/wolf_froh_load_associations.tsv",
        damage           = "results/tables/peafowl_damage_effects.tsv",
        ne               = "results/tables/peafowl_ne_design_summary.tsv",
        config           = "config/config.yaml",
        report           = "report/report.qmd",
        app              = "app/streamlit_app.py",
        html             = "index.html",
        js               = "website/site.js",
        css              = "website/site.css",
        script           = "scripts/python/phase5b_core_integration.py",
    output:
        contract   = "results/tables/phase5b_core_claim_contract.tsv",
        provenance = "results/provenance/phase5b_core_integration.json",
    log: "results/logs/phase5b_core_integration.log"
    threads: 1
    resources:
        mem_mb = 2048
    shell:
        "python {input.script} --wolf {input.wolf} --damage {input.damage} --ne {input.ne} "
        "--wolf-validation {input.wolf_gate} --damage-validation {input.damage_gate} "
        "--ne-validation {input.ne_gate} --config {input.config} "
        "--report {input.report} --app {input.app} --html {input.html} "
        "--js {input.js} --css {input.css} "
        "--out-contract {output.contract} --out-provenance {output.provenance} "
        "> {log} 2>&1 || (cat {log}; exit 1)"


rule validate_phase5b_core_integration:
    """Reconcile numeric claims and the no-install/report/explorer implementation (13.6)."""
    input:
        contract    = "results/tables/phase5b_core_claim_contract.tsv",
        provenance  = "results/provenance/phase5b_core_integration.json",
        wolf        = "results/tables/wolf_froh_load_associations.tsv",
        damage      = "results/tables/peafowl_damage_effects.tsv",
        ne          = "results/tables/peafowl_ne_design_summary.tsv",
        config      = "config/config.yaml",
        report      = "report/report.qmd",
        app         = "app/streamlit_app.py",
        html        = "index.html",
        js          = "website/site.js",
        css         = "website/site.css",
        source      = "scripts/python/phase5b_core_integration.py",
        script      = "scripts/python/validate_phase5b_core_integration.py",
    output:
        tsv = "results/tables/validation_phase5b_core_integration.tsv",
        md  = "results/PHASE5B_CORE_INTEGRATION_VALIDATION.md",
    log: "results/logs/validate_phase5b_core_integration.log"
    threads: 1
    resources:
        mem_mb = 2048
    shell:
        "python {input.script} --contract {input.contract} --provenance {input.provenance} "
        "--wolf {input.wolf} --damage {input.damage} --ne {input.ne} --config {input.config} "
        "--report {input.report} --app {input.app} --html {input.html} --js {input.js} "
        "--css {input.css} --out-tsv {output.tsv} --out-md {output.md} "
        "> {log} 2>&1 || (cat {log}; exit 1)"


rule phase5b_optional_decisions:
    """Resolve the gated 13.4 analysis and evidence-backed 13.5 deferral."""
    input:
        integration_gate = "results/tables/validation_phase5b_core_integration.tsv",
        associations = "results/tables/wolf_froh_load_associations.tsv",
        config       = "config/config.yaml",
        wolf_load    = "results/tables/wolf_load.tsv",
        coding_vcf   = "data/wolf/vcf/Pol.2out.mac2/100S95F14R.chr1-38.vepfinal.wfm.vcf.gz",
        vep          = "data/wolf/vep/Pol.2out.mac2/veptypes.chr1-X.txt",
        sift         = "data/wolf/vep/Pol.2out.mac2/sifttypes.chr1-X.txt",
        script       = "scripts/python/phase5b_optional_decisions.py",
    output:
        decisions  = "results/tables/phase5b_optional_decisions.tsv",
        inventory  = "results/tables/phase5b_annotation_inventory.tsv",
        provenance = "results/provenance/phase5b_optional_decisions.json",
    log: "results/logs/phase5b_optional_decisions.log"
    threads: 1
    resources:
        mem_mb = 2048
    shell:
        "python {input.script} --associations {input.associations} "
        "--config {input.config} --wolf-load {input.wolf_load} "
        "--coding-vcf {input.coding_vcf} --vep {input.vep} --sift {input.sift} "
        "--out-decisions {output.decisions} --out-inventory {output.inventory} "
        "--out-provenance {output.provenance} > {log} 2>&1 || (cat {log}; exit 1)"


rule validate_phase5b_decisions:
    """Check both optional-study decisions against their predeclared numeric gates."""
    input:
        associations   = "results/tables/wolf_froh_load_associations.tsv",
        decisions      = "results/tables/phase5b_optional_decisions.tsv",
        inventory      = "results/tables/phase5b_annotation_inventory.tsv",
        provenance     = "results/provenance/phase5b_optional_decisions.json",
        config         = "config/config.yaml",
        decision_script = "scripts/python/phase5b_optional_decisions.py",
        script          = "scripts/python/validate_phase5b_decisions.py",
    output:
        tsv = "results/tables/validation_phase5b_decisions.tsv",
        md  = "results/PHASE5B_DECISIONS_VALIDATION.md",
    log: "results/logs/validate_phase5b_decisions.log"
    threads: 1
    resources:
        mem_mb = 2048
    shell:
        "python {input.script} --associations {input.associations} "
        "--decisions {input.decisions} --inventory {input.inventory} "
        "--provenance {input.provenance} --config {input.config} "
        "--out-tsv {output.tsv} --out-md {output.md} "
        "> {log} 2>&1 || (cat {log}; exit 1)"


rule wolf_roh_localization_chrom:
    """Stream one wolf chromosome only after the validated Section-13.4 gate opens."""
    input:
        decision_gate = "results/tables/validation_phase5b_decisions.tsv",
        decisions     = "results/tables/phase5b_optional_decisions.tsv",
        vcf           = WOLF["allsnps"],
        vcf_index     = WOLF["allsnps"] + ".csi",
        gerp          = "results/wolf/gerp/chr{c}.bed",
        rg            = "results/wolf/roh/chr{c}.rg.txt",
        phase4_load   = "results/wolf/load/chr{c}.tsv",
        samples       = "results/wolf/samples.txt",
        popmap        = "results/wolf/popmap.tsv",
        lengths       = "results/wolf/autosome_lengths.tsv",
        config        = "config/config.yaml",
        script        = "scripts/python/wolf_roh_localization.py",
    output:
        observed = "results/wolf/localization/chr{c}.observed.tsv",
        null     = "results/wolf/localization/chr{c}.null.tsv",
        qc       = "results/wolf/localization/chr{c}.qc.tsv",
    log: "results/logs/wolf_roh_localization_chr{c}.log"
    # The implementation is single-threaded; reserving two cores intentionally
    # caps a normal --cores 4 laptop run at two chromosome workers (<8 GB total).
    threads: 2
    resources:
        mem_mb = 3500
    shell:
        "MPLCONFIGDIR=/tmp/cg-mpl-phase5b python {input.script} chromosome "
        "--chromosome {wildcards.c} --vcf {input.vcf} --gerp-bed {input.gerp} "
        "--rg {input.rg} --phase4-chrom-load {input.phase4_load} "
        "--samples {input.samples} --popmap {input.popmap} --lengths {input.lengths} "
        "--config {input.config} --decision-table {input.decisions} "
        "--decision-validation {input.decision_gate} "
        "--out-observed {output.observed} --out-null {output.null} --out-qc {output.qc} "
        "> {log} 2>&1 || (cat {log}; exit 1)"


rule wolf_roh_localization_collate:
    """Reconcile all 38 chromosome partitions and render Section-13.4 results."""
    input:
        decision_gate = "results/tables/validation_phase5b_decisions.tsv",
        decisions     = "results/tables/phase5b_optional_decisions.tsv",
        observed      = expand("results/wolf/localization/chr{c}.observed.tsv", c=WOLF_CHROMS),
        null          = expand("results/wolf/localization/chr{c}.null.tsv", c=WOLF_CHROMS),
        qc            = expand("results/wolf/localization/chr{c}.qc.tsv", c=WOLF_CHROMS),
        wolf_load     = "results/tables/wolf_load.tsv",
        wolf_roh      = "results/tables/wolf_roh.tsv",
        lengths       = "results/wolf/autosome_lengths.tsv",
        vcf           = WOLF["allsnps"],
        gerp_source   = WOLF["gerp_allsnps_bed"],
        samples       = "results/wolf/samples.txt",
        popmap        = "results/wolf/popmap.tsv",
        config        = "config/config.yaml",
        script        = "scripts/python/wolf_roh_localization.py",
    output:
        individual    = "results/tables/wolf_roh_localization_individual.tsv",
        cohort        = "results/tables/wolf_roh_localization_cohort.tsv",
        null          = "results/tables/wolf_roh_localization_null.tsv",
        qc            = "results/tables/wolf_roh_localization_qc.tsv",
        figure_values = "results/tables/wolf_roh_localization_figure_values.tsv",
        forest        = "results/figures/wolf_roh_localization_forest.png",
        ribbon        = "results/figures/wolf_roh_localization_ribbon.png",
        provenance    = "results/provenance/wolf_roh_localization.json",
    log: "results/logs/wolf_roh_localization_collate.log"
    threads: 1
    resources:
        mem_mb = 4096
    shell:
        "MPLCONFIGDIR=/tmp/cg-mpl-phase5b python {input.script} collate "
        "--observed {input.observed} --null {input.null} --qc {input.qc} "
        "--wolf-load {input.wolf_load} --wolf-roh {input.wolf_roh} "
        "--lengths {input.lengths} --config {input.config} "
        "--decision-table {input.decisions} --decision-validation {input.decision_gate} "
        "--vcf {input.vcf} --gerp-source {input.gerp_source} "
        "--samples {input.samples} --popmap {input.popmap} "
        "--out-individual {output.individual} --out-cohort {output.cohort} "
        "--out-null {output.null} --out-qc {output.qc} "
        "--out-figure-values {output.figure_values} --out-forest {output.forest} "
        "--out-ribbon {output.ribbon} --out-provenance {output.provenance} "
        "> {log} 2>&1 || (cat {log}; exit 1)"


rule validate_wolf_roh_localization:
    """Independently audit raw ROH unions, partitions, nulls, figures, and provenance."""
    input:
        decisions       = "results/tables/phase5b_optional_decisions.tsv",
        decision_gate   = "results/tables/validation_phase5b_decisions.tsv",
        vcf             = WOLF["allsnps"],
        vcf_index       = WOLF["allsnps"] + ".csi",
        gerp_raw        = expand("results/wolf/gerp/chr{c}.bed", c=WOLF_CHROMS),
        roh_raw         = expand("results/wolf/roh/chr{c}.rg.txt", c=WOLF_CHROMS),
        phase4_load_raw = expand("results/wolf/load/chr{c}.tsv", c=WOLF_CHROMS),
        samples         = "results/wolf/samples.txt",
        popmap          = "results/wolf/popmap.tsv",
        lengths         = "results/wolf/autosome_lengths.tsv",
        config          = "config/config.yaml",
        observed        = expand("results/wolf/localization/chr{c}.observed.tsv", c=WOLF_CHROMS),
        null_chrom      = expand("results/wolf/localization/chr{c}.null.tsv", c=WOLF_CHROMS),
        qc_chrom        = expand("results/wolf/localization/chr{c}.qc.tsv", c=WOLF_CHROMS),
        individual      = "results/tables/wolf_roh_localization_individual.tsv",
        cohort          = "results/tables/wolf_roh_localization_cohort.tsv",
        null            = "results/tables/wolf_roh_localization_null.tsv",
        qc              = "results/tables/wolf_roh_localization_qc.tsv",
        figure_values   = "results/tables/wolf_roh_localization_figure_values.tsv",
        forest          = "results/figures/wolf_roh_localization_forest.png",
        ribbon          = "results/figures/wolf_roh_localization_ribbon.png",
        provenance      = "results/provenance/wolf_roh_localization.json",
        analysis_script = "scripts/python/wolf_roh_localization.py",
        script          = "scripts/python/validate_wolf_roh_localization.py",
    output:
        tsv = "results/tables/validation_wolf_roh_localization.tsv",
        md  = "results/WOLF_ROH_LOCALIZATION_VALIDATION.md",
    log: "results/logs/validate_wolf_roh_localization.log"
    threads: 1
    resources:
        mem_mb = 4096
    shell:
        "MPLCONFIGDIR=/tmp/cg-mpl-phase5b python {input.script} --root . "
        "--out-tsv {output.tsv} --out-md {output.md} "
        "> {log} 2>&1 || (cat {log}; exit 1)"


rule phase5b_synthesis:
    """Build the final claim trace, scorecard, dictionary, and offline browser payload."""
    input:
        core_gate          = "results/tables/validation_phase5b_core_integration.tsv",
        decisions_gate     = "results/tables/validation_phase5b_decisions.tsv",
        localization_gate  = "results/tables/validation_wolf_roh_localization.tsv",
        wolf_associations  = "results/tables/wolf_froh_load_associations.tsv",
        wolf_rank          = "results/tables/wolf_froh_load_rank_stability.tsv",
        wolf_scores        = "results/tables/wolf_froh_load_individual_scores.tsv",
        wolf_figure_values = "results/tables/wolf_froh_load_figure_values.tsv",
        wolf_provenance    = "results/provenance/wolf_froh_load.json",
        damage_effects     = "results/tables/peafowl_damage_effects.tsv",
        damage_permutations = "results/tables/peafowl_damage_permutations.tsv",
        damage_influence   = "results/tables/peafowl_damage_influence.tsv",
        damage_blocks      = "results/tables/peafowl_damage_blocks.tsv",
        damage_classification = "results/tables/peafowl_damage_classification.tsv",
        damage_figure_values = "results/tables/peafowl_damage_figure_values.tsv",
        damage_validation  = "results/tables/validation_peafowl_damage.tsv",
        damage_provenance  = "results/provenance/peafowl_damage.json",
        ne_replicates      = "results/tables/peafowl_ne_design_replicates.tsv",
        ne_pilot           = "results/tables/peafowl_ne_design_pilot.tsv",
        ne_summary         = "results/tables/peafowl_ne_design_summary.tsv",
        ne_empirical       = "results/tables/peafowl_ne_design_empirical.tsv",
        ne_figure_values   = "results/tables/peafowl_ne_design_figure_values.tsv",
        ne_validation      = "results/tables/validation_peafowl_ne_design.tsv",
        ne_provenance      = "results/provenance/peafowl_ne_design.json",
        localization_individual = "results/tables/wolf_roh_localization_individual.tsv",
        localization_cohort = "results/tables/wolf_roh_localization_cohort.tsv",
        localization_null = "results/tables/wolf_roh_localization_null.tsv",
        localization_qc   = "results/tables/wolf_roh_localization_qc.tsv",
        localization_figure_values = "results/tables/wolf_roh_localization_figure_values.tsv",
        localization_provenance = "results/provenance/wolf_roh_localization.json",
        decisions          = "results/tables/phase5b_optional_decisions.tsv",
        inventory          = "results/tables/phase5b_annotation_inventory.tsv",
        decisions_provenance = "results/provenance/phase5b_optional_decisions.json",
        config             = "config/config.yaml",
        script             = "scripts/python/phase5b_synthesis.py",
    output:
        claims        = "results/tables/phase5b_claim_trace.tsv",
        scorecard     = "results/tables/phase5b_fragility_scorecard.tsv",
        dictionary    = "results/tables/phase5b_data_dictionary.tsv",
        dictionary_md = "results/PHASE5B_DATA_DICTIONARY.md",
        browser_data  = "website/phase5b-data.js",
        provenance    = "results/provenance/phase5b_synthesis.json",
    log: "results/logs/phase5b_synthesis.log"
    threads: 1
    resources:
        mem_mb = 4096
    shell:
        "python {input.script} --out-claims {output.claims} --out-scorecard {output.scorecard} "
        "--out-dictionary {output.dictionary} --out-dictionary-md {output.dictionary_md} "
        "--out-js {output.browser_data} --out-provenance {output.provenance} "
        "> {log} 2>&1 || (cat {log}; exit 1)"


rule validate_phase5b:
    """Final independent numeric, traceability, report, explorer, and offline-data gate."""
    input:
        claims       = "results/tables/phase5b_claim_trace.tsv",
        scorecard    = "results/tables/phase5b_fragility_scorecard.tsv",
        dictionary   = "results/tables/phase5b_data_dictionary.tsv",
        dictionary_md = "results/PHASE5B_DATA_DICTIONARY.md",
        browser_data = "website/phase5b-data.js",
        provenance   = "results/provenance/phase5b_synthesis.json",
        wolf          = "results/tables/wolf_froh_load_associations.tsv",
        damage        = "results/tables/peafowl_damage_effects.tsv",
        ne            = "results/tables/peafowl_ne_design_summary.tsv",
        localization  = "results/tables/wolf_roh_localization_cohort.tsv",
        decisions     = "results/tables/phase5b_optional_decisions.tsv",
        report        = "report/report.qmd",
        app           = "app/streamlit_app.py",
        html          = "index.html",
        site_js       = "website/site.js",
        site_css      = "website/site.css",
        script        = "scripts/python/validate_phase5b.py",
    output:
        tsv = "results/tables/validation_phase5b.tsv",
        md  = "results/PHASE5B_VALIDATION.md",
    log: "results/logs/validate_phase5b.log"
    threads: 1
    resources:
        mem_mb = 4096
    shell:
        "python {input.script} --root . --out-tsv {output.tsv} --out-md {output.md} "
        "> {log} 2>&1 || (cat {log}; exit 1)"


rule phase5b:
    """Build the validated science and every synchronized offline delivery surface."""
    input: PHASE5B_COMPLETE


rule phase5b_science:
    """Build the dependency-ordered Phase-5B science without the self-referential release record.

    This aggregate exists so a new release can obtain truthful clean-run timing,
    return-code, RSS, validator, and science-hash evidence before writing the
    reproducibility record consumed by the full ``phase5b`` release target.
    """
    input: PHASE5B
