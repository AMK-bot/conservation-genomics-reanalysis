# workflow/rules/polish.smk — Phase 5/5A rendering, runtime smoke, and final gate
#
# These rules consume tracked summary outputs and communication artifacts. They
# do not invoke the heavy bioinformatics branches except through normal input
# dependencies already represented by the Phase 1-4 targets.


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
]

REPORT_FIGURES = [
    "results/figures/pca.png",
    "results/figures/ne_cube.png",
    "results/figures/fragility_scorecard.png",
]

ADMISSIONS_SCREENSHOTS = [
    "admissions/screenshots/01-ne-gbf-verdict.jpg",
    "admissions/screenshots/02-structure-diversity.jpg",
    "admissions/screenshots/03-wolf-load-roh.jpg",
    "admissions/screenshots/04-about-limitations.jpg",
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
]


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
    shell:
        "bash {input.render} > {log} 2>&1 || (cat {log}; exit 1)"


rule render_research_brief:
    """Render the self-contained two-page admissions research brief."""
    input:
        md          = "admissions/research_brief.md",
        css         = "admissions/brief.css",
        abstract    = "admissions/graphical_abstract.svg",
        screenshots = ADMISSIONS_SCREENSHOTS,
    output:
        html = "admissions/research_brief.html",
    log: "results/logs/render_research_brief.log"
    shell:
        "pandoc {input.md} --standalone --embed-resources --resource-path=admissions "
        "--css {input.css} --metadata pagetitle='Conservation genomics research brief' "
        "--output {output.html} > {log} 2>&1 || (cat {log}; exit 1)"


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
    shell:
        "python3 {input.runner} --test {input.test} --out-md {output.md} --log {output.log}"


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
        interview       = "INTERVIEW_NOTES.md",
        demo            = "admissions/demo_script.md",
        abstract        = "admissions/graphical_abstract.svg",
        brief_md        = "admissions/research_brief.md",
        brief_html      = "admissions/research_brief.html",
        screenshots     = ADMISSIONS_SCREENSHOTS,
        smoke_md        = "results/APP_SMOKE.md",
        smoke_log       = "results/logs/app_smoke.log",
        reproducibility = "results/PHASE5A_REPRODUCIBILITY.md",
        script          = "scripts/python/validate_phase5a.py",
    output:
        tsv = "results/tables/validation_phase5a.tsv",
        md  = "results/PHASE5A_VALIDATION.md",
    log: "results/logs/validate_phase5a.log"
    shell:
        "python3 {input.script} --root . --out-tsv {output.tsv} --out-md {output.md} "
        "> {log} 2>&1 || (cat {log}; exit 1)"
