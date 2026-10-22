# workflow/rules/polish.smk — Phase 5/5A rendering, runtime smoke, and final gate
#
# These rules consume tracked summary outputs and communication artifacts. They
# do not invoke the heavy bioinformatics branches except through normal input
# dependencies already represented by the Phase 1-4 targets.

from pathlib import Path


PHASE5B_PUBLIC_ARTIFACTS = [
    *PHASE5B_INPUT_MANIFEST_OUTPUTS,
    *WOLF_ROBUSTNESS_OUTPUTS,
    *PEAFOWL_DAMAGE_OUTPUTS,
    *PEAFOWL_NE_DESIGN_OUTPUTS,
    *PHASE5B_CORE_INTEGRATION_OUTPUTS,
    *PHASE5B_OPTIONAL_DECISION_OUTPUTS,
    *WOLF_ROH_LOCALIZATION_OUTPUTS,
    *PHASE5B_INTEGRATION_OUTPUTS,
    *PHASE5B_RELEASE_CONTENT_OUTPUTS,
]


REPORT_TABLES = [
    "results/tables/qc_snp_counts.tsv",
    "results/tables/pca_coords.tsv",
    "results/tables/pca_variance.tsv",
    "results/tables/admixture_cv.tsv",
    "results/tables/diversity_perpop.tsv",
    "results/tables/allelic_richness_modern.tsv",
    "results/tables/temporal_diversity.tsv",
    "results/tables/temporal_pi_summary.tsv",
    "results/tables/temporal_allelic_richness.tsv",
    "results/cube/results_cube.csv",
    "results/tables/gbf_ne500.tsv",
    "results/tables/gbf_robustness.tsv",
    "results/tables/gbf_populations_maintained.tsv",
    "results/tables/gbf_summary.tsv",
    "results/tables/gone2_trajectory.tsv",
    "results/tables/wolf_load.tsv",
    "results/tables/wolf_roh.tsv",
    "results/tables/validation_phase4.tsv",
    "results/tables/fragility_scorecard.tsv",
    "results/tables/wolf_froh_load_associations.tsv",
    "results/tables/wolf_froh_load_rank_stability.tsv",
    "results/tables/peafowl_damage_effects.tsv",
    "results/tables/peafowl_ne_design_summary.tsv",
    "results/tables/wolf_roh_localization_cohort.tsv",
    "results/tables/validation_wolf_roh_localization.tsv",
    "results/tables/phase5b_optional_decisions.tsv",
    "results/tables/phase5b_claim_trace.tsv",
    "results/tables/validation_phase5b.tsv",
]

REPORT_FIGURES = [
    "results/figures/pca.png",
    "results/figures/ne_cube.png",
    "results/figures/fragility_scorecard.png",
    "results/figures/wolf_froh_load_surface.png",
    "results/figures/peafowl_damage_falsification.png",
    "results/figures/peafowl_ne_design.png",
    "results/figures/wolf_roh_localization_forest.png",
    "results/figures/wolf_roh_localization_ribbon.png",
]

BRIEF_SCREENSHOTS = [
    "brief/screenshots/01-ne-gbf-verdict.jpg",
    "brief/screenshots/02-structure-diversity.jpg",
    "brief/screenshots/03-wolf-load-roh.jpg",
    "brief/screenshots/04-about-limitations.jpg",
]

BRIEF_DIAGRAMS = [
    "brief/brief_project_route.svg",
    "brief/brief_peafowl_models.svg",
    "brief/brief_wolf_models.svg",
    "brief/brief_phase5b_tests.svg",
]

APP_ARTIFACTS = [
    "results/cube/results_cube.parquet",
    "results/tables/gbf_ne500.tsv",
    "results/tables/gbf_robustness.tsv",
    "results/tables/gbf_populations_maintained.tsv",
    "results/tables/gbf_summary.tsv",
    "results/tables/fragility_scorecard.tsv",
    "results/tables/wolf_load.tsv",
    "results/tables/wolf_roh.tsv",
    "results/figures/gone2_trajectory.png",
    "results/figures/ne_cube.png",
    "results/figures/pca.png",
    "results/figures/admixture.png",
    "results/figures/kinship_heatmap.png",
    "results/figures/diversity_perpop.png",
    "results/figures/temporal_diversity.png",
    "results/tables/wolf_froh_load_associations.tsv",
    "results/tables/wolf_froh_load_rank_stability.tsv",
    "results/tables/peafowl_damage_effects.tsv",
    "results/tables/peafowl_ne_design_summary.tsv",
    "results/tables/phase5b_claim_trace.tsv",
    "results/tables/phase5b_optional_decisions.tsv",
    "results/tables/wolf_roh_localization_cohort.tsv",
    "results/figures/wolf_froh_load_surface.png",
    "results/figures/wolf_froh_load_forest.png",
    "results/figures/peafowl_damage_falsification.png",
    "results/figures/peafowl_ne_design.png",
    "results/figures/wolf_roh_localization_forest.png",
    "results/figures/wolf_roh_localization_ribbon.png",
    "results/tables/validation_phase5b.tsv",
]

WEBSITE_BASE_ASSETS = [
    "index.html",
    ".nojekyll",
    "website/site.css",
    "website/site.js",
    "website/favicon.svg",
    "website/README.md",
]

WEBSITE_PHASE5B_ASSETS = [
    "website/phase5b-data.js",
]

WEBSITE_EDITOR_ASSETS = [
    "EDIT_WEBSITE.command",
    "EDIT_WEBSITE.md",
    "editor.html",
    "scripts/python/edit_website.py",
    "website/apply-content.js",
    "website/content-overrides.js",
    "website/content-overrides.json",
    "website/editor.css",
    "website/editor.js",
]

WEBSITE_ASSETS = WEBSITE_BASE_ASSETS + WEBSITE_PHASE5B_ASSETS + WEBSITE_EDITOR_ASSETS

# This table is produced *after* the ZIP and therefore must never become a
# parse-time package input on a subsequent invocation.  Without the exclusion,
# the broad artifact inventory below creates a rerun-only cycle:
# package_website -> validate_phase5b_delivery -> package_website.
WEBSITE_DISCOVERY_EXCLUDES = {
    "results/tables/validation_phase5b_delivery.tsv",
}

WEBSITE_DELIVERABLES = [
    "brief/research_brief.html",
    "brief/graphical_abstract.svg",
    "report/report.html",
    "RESEARCH_JOURNEY.md",
    "FAQ.md",
    "brief/walkthrough.md",
    "app/streamlit_app.py",
    "results/cube/results_cube.csv",
    "results/tables/fragility_scorecard.tsv",
    "results/PHASE5A_VALIDATION.md",
    "results/PHASE5A_REPRODUCIBILITY.md",
    "results/PHASE5B_VALIDATION.md",
    "results/PHASE5B_DATA_DICTIONARY.md",
    "results/PHASE5B_REPRODUCIBILITY.md",
    "results/PHASE5B_RELEASE_CONTENT_VALIDATION.md",
    "results/tables/validation_phase5b_release_content.tsv",
    "results/tables/phase5b_claim_trace.tsv",
    "results/tables/phase5b_fragility_scorecard.tsv",
    "PROJECT_STATUS.md",
]

WEBSITE_BUNDLE_INPUTS = sorted(set(
    WEBSITE_ASSETS
    + WEBSITE_DELIVERABLES
    + PHASE5B_PUBLIC_ARTIFACTS
    + [
        ".gitignore",
        ".Rprofile",
        "README.md",
        "CGplan.md",
        "SETUP.md",
        "data/README.md",
        "environment.yml",
        "requirements.txt",
        "renv/.gitignore",
        "renv/activate.R",
        "renv/settings.json",
        "environment.lock.yml",
        "results/APP_SMOKE.md",
        "results/PHASE1_VALIDATION.md",
        "results/PHASE2_VALIDATION.md",
        "results/PHASE3_VALIDATION.md",
        "results/PHASE4_VALIDATION.md",
        "results/PHASE5A1_VALIDATION.md",
        "results/WEBSITE_VALIDATION.md",
        "workflow/Snakefile",
        "scripts/R/README.md",
        "scripts/python/README.md",
        "scripts/python/validate_website.py",
        "tests/test_streamlit_app.py",
        "tools/README.md",
    ]
    + [
        path.as_posix()
        for directory in [
            "brief",
            "app",
            "config",
            "report",
            "results/cube",
            "results/figures",
            "results/tables",
            "scripts",
            "website",
            "workflow",
        ]
        for path in Path(directory).rglob("*")
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.as_posix() not in WEBSITE_DISCOVERY_EXCLUDES
        )
    ]
))


rule render_report_html:
    """Render the dynamically sourced technical report to an embedded HTML file."""
    input:
        qmd     = "report/report.qmd",
        bib     = "report/references.bib",
        values  = "report/report_values.py",
        render  = "report/render_report.sh",
        config  = "config/config.yaml",
        tables  = REPORT_TABLES,
        figures = REPORT_FIGURES,
    output:
        html = "report/report.html",
    log: "results/logs/render_report.log"
    threads: 1
    resources:
        mem_mb = 2048
    shell:
        "bash {input.render} > {log} 2>&1 || (cat {log}; exit 1)"


rule render_research_brief:
    """Render the self-contained four-page, project-wide research brief."""
    input:
        md          = "brief/research_brief.md",
        css         = "brief/brief.css",
        abstract    = "brief/graphical_abstract.svg",
        diagrams    = BRIEF_DIAGRAMS,
        screenshots = BRIEF_SCREENSHOTS,
    output:
        html = "brief/research_brief.html",
    log: "results/logs/render_research_brief.log"
    threads: 1
    resources:
        mem_mb = 512
    shell:
        "pandoc {input.md} --standalone --embed-resources --resource-path=brief "
        "--css {input.css} --metadata pagetitle='Conservation genomics research brief' "
        "--metadata lang=en "
        "--output {output.html} > {log} 2>&1 "
        "&& perl -pi -e 's/[ \\t]+$//' {output.html} "
        "|| (cat {log}; exit 1)"


rule app_smoke:
    """Exercise every Streamlit widget state in-process and record a compact PASS/FAIL."""
    input:
        app       = "app/streamlit_app.py",
        test      = "tests/test_streamlit_app.py",
        runner    = "scripts/python/run_app_smoke.py",
        config    = "config/config.yaml",
        artifacts = APP_ARTIFACTS,
    output:
        md  = "results/APP_SMOKE.md",
        log = "results/logs/app_smoke.log",
    threads: 1
    resources:
        mem_mb = 2048
    shell:
        "python {input.runner} --test {input.test} --out-md {output.md} --log {output.log}"


rule validate_website:
    """Check the static portal's structure, accessibility affordances, and every local link."""
    input:
        site         = WEBSITE_ASSETS,
        deliverables = WEBSITE_DELIVERABLES,
        phase5b_gate  = "results/tables/validation_phase5b.tsv",
        report        = "report/report.html",
        app_smoke     = "results/APP_SMOKE.md",
        script       = "scripts/python/validate_website.py",
    output:
        md = "results/WEBSITE_VALIDATION.md",
    log: "results/logs/validate_website.log"
    threads: 1
    resources:
        mem_mb = 1024
    shell:
        "python {input.script} --root . --html index.html --out {output.md} "
        "> {log} 2>&1 || (cat {log}; exit 1)"


rule validate_phase5b_release_content:
    """Fail closed on synchronized claims, completion markers, and clean-run evidence."""
    input:
        # The reproducibility record independently reconciles these seven TSVs.
        # Keep them direct inputs so later corruption or regeneration always
        # invalidates this gate, even when the final science gate is unchanged.
        validators         = [
            "results/tables/validation_wolf_robustness.tsv",
            "results/tables/validation_peafowl_damage.tsv",
            "results/tables/validation_peafowl_ne_design.tsv",
            "results/tables/validation_phase5b_core_integration.tsv",
            "results/tables/validation_phase5b_decisions.tsv",
            "results/tables/validation_wolf_roh_localization.tsv",
            "results/tables/validation_phase5b.tsv",
        ],
        claims             = "results/tables/phase5b_claim_trace.tsv",
        decisions          = "results/tables/phase5b_optional_decisions.tsv",
        reproducibility    = "results/PHASE5B_REPRODUCIBILITY.md",
        input_manifests    = PHASE5B_INPUT_MANIFEST_OUTPUTS,
        # These four unique files supply five of the six frozen science hashes:
        # the Ne provenance carries separate scenario and empirical hashes. The
        # sixth is the claim trace already declared above as `claims`.
        science_hash_artifacts = [
            "results/provenance/wolf_froh_load.json",
            "results/tables/peafowl_damage_effects.tsv",
            "results/provenance/peafowl_ne_design.json",
            "results/provenance/wolf_roh_localization.json",
        ],
        surfaces           = [
            "README.md",
            "PROJECT_STATUS.md",
            "CGplan.md",
            "scripts/python/README.md",
            "website/README.md",
            "RESEARCH_JOURNEY.md",
            "FAQ.md",
            "brief/research_brief.md",
            "brief/research_brief.html",
            "brief/walkthrough.md",
            "app/streamlit_app.py",
            "index.html",
            "brief/graphical_abstract.svg",
            "report/report.qmd",
            "report/report.html",
        ],
        workflow           = "workflow/rules/phase5b.smk",
        script             = "scripts/python/validate_phase5b_release_content.py",
    output:
        tsv = "results/tables/validation_phase5b_release_content.tsv",
        md  = "results/PHASE5B_RELEASE_CONTENT_VALIDATION.md",
    log: "results/logs/validate_phase5b_release_content.log"
    threads: 1
    resources:
        mem_mb = 1024
    shell:
        "python {input.script} --root . --claims {input.claims} "
        "--decisions {input.decisions} --reproducibility {input.reproducibility} "
        "--out-tsv {output.tsv} --out-md {output.md} "
        "> {log} 2>&1 || (cat {log}; exit 1)"


rule package_website:
    """Create and verify the single-file, offline-sendable project portfolio."""
    input:
        sources = WEBSITE_BUNDLE_INPUTS,
        phase5b = PHASE5B_PUBLIC_ARTIFACTS,
        website_gate = "results/WEBSITE_VALIDATION.md",
        phase5b_gate = "results/tables/validation_phase5b.tsv",
        release_content_gate = "results/tables/validation_phase5b_release_content.tsv",
        app_smoke = "results/APP_SMOKE.md",
        report_html = "report/report.html",
        builder = "scripts/python/package_website.py",
    output:
        archive = "dist/conservation-genomics-reanalysis.zip",
        report  = "results/WEBSITE_BUNDLE_VALIDATION.md",
    log: "results/logs/package_website.log"
    threads: 1
    resources:
        mem_mb = 2048
    shell:
        "python {input.builder} --root . --html index.html --out {output.archive} "
        "--required-files {input.phase5b} --report {output.report} "
        "> {log} 2>&1 || (cat {log}; exit 1)"


rule validate_phase5b_delivery:
    """Fail closed after science, rendering, app smoke, website, and ZIP packaging reconcile."""
    input:
        science       = PHASE5B_PUBLIC_ARTIFACTS,
        report        = "report/report.html",
        brief         = "brief/research_brief.html",
        smoke_md      = "results/APP_SMOKE.md",
        smoke_log     = "results/logs/app_smoke.log",
        website_gate  = "results/WEBSITE_VALIDATION.md",
        archive       = "dist/conservation-genomics-reanalysis.zip",
        bundle_gate   = "results/WEBSITE_BUNDLE_VALIDATION.md",
        readme        = "README.md",
        status        = "PROJECT_STATUS.md",
        plan          = "CGplan.md",
        script        = "scripts/python/validate_phase5b_delivery.py",
    output:
        tsv = "results/tables/validation_phase5b_delivery.tsv",
        md  = "results/PHASE5B_DELIVERY_VALIDATION.md",
    log: "results/logs/validate_phase5b_delivery.log"
    threads: 1
    resources:
        mem_mb = 2048
    shell:
        "python {input.script} --root . --out-tsv {output.tsv} --out-md {output.md} "
        "--science-files {input.science} > {log} 2>&1 || (cat {log}; exit 1)"


rule validate_phase5a:
    """Strict final gate: scientific checks + artifacts + portability + clean reproduction."""
    input:
        validations = [
            "results/tables/validation_report.tsv",
            "results/tables/validation_phase2.tsv",
            "results/tables/validation_phase3.tsv",
            "results/tables/validation_phase4.tsv",
            "results/tables/validation_fragility_scorecard.tsv",
        ],
        app             = "app/streamlit_app.py",
        report_qmd      = "report/report.qmd",
        report_html     = "report/report.html",
        readme          = "README.md",
        lock            = "environment.lock.yml",
        rprofile        = ".Rprofile",
        journey         = "RESEARCH_JOURNEY.md",
        faq             = "FAQ.md",
        walkthrough     = "brief/walkthrough.md",
        abstract        = "brief/graphical_abstract.svg",
        brief_md        = "brief/research_brief.md",
        brief_html      = "brief/research_brief.html",
        screenshots     = BRIEF_SCREENSHOTS,
        smoke_md        = "results/APP_SMOKE.md",
        smoke_log       = "results/logs/app_smoke.log",
        reproducibility = "results/PHASE5A_REPRODUCIBILITY.md",
        script          = "scripts/python/validate_phase5a.py",
    output:
        tsv = "results/tables/validation_phase5a.tsv",
        md  = "results/PHASE5A_VALIDATION.md",
    log: "results/logs/validate_phase5a.log"
    threads: 1
    resources:
        mem_mb = 1024
    shell:
        "python {input.script} --root . --out-tsv {output.tsv} --out-md {output.md} "
        "> {log} 2>&1 || (cat {log}; exit 1)"
