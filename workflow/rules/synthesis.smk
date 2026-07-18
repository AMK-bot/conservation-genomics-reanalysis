# workflow/rules/synthesis.smk — Phase 5A.1: lightweight fragility scorecard
#
# Reads only tracked Phase-2/3/4 summary tables and validation reports. No VCF,
# bioinformatics binary, or external service is part of this branch of the DAG.


rule fragility_scorecard:
    """Synthesize four pre-specified conclusions into a TSV + offline figure."""
    input:
        cube    = "results/cube/results_cube.parquet",
        ne500   = "results/tables/gbf_ne500.tsv",
        robust  = "results/tables/gbf_robustness.tsv",
        load    = "results/tables/wolf_load.tsv",
        roh     = "results/tables/wolf_roh.tsv",
        val2    = "results/tables/validation_phase2.tsv",
        val3    = "results/tables/validation_phase3.tsv",
        val4    = "results/tables/validation_phase4.tsv",
        script  = "scripts/python/fragility_scorecard.py",
    output:
        table  = "results/tables/fragility_scorecard.tsv",
        figure = "results/figures/fragility_scorecard.png",
    log: "results/logs/fragility_scorecard.log"
    shell:
        "python3 {input.script} --cube {input.cube} --ne500 {input.ne500} "
        "--robustness {input.robust} --wolf-load {input.load} --wolf-roh {input.roh} "
        "--validation-phase2 {input.val2} --validation-phase3 {input.val3} "
        "--validation-phase4 {input.val4} --out-table {output.table} "
        "--out-figure {output.figure} > {log} 2>&1 || (cat {log}; exit 1)"


rule validate_fragility_scorecard:
    """Exact reconciliation gate for the scorecard and its offline PNG."""
    input:
        cube      = "results/cube/results_cube.parquet",
        ne500     = "results/tables/gbf_ne500.tsv",
        robust    = "results/tables/gbf_robustness.tsv",
        load      = "results/tables/wolf_load.tsv",
        roh       = "results/tables/wolf_roh.tsv",
        val2      = "results/tables/validation_phase2.tsv",
        val3      = "results/tables/validation_phase3.tsv",
        val4      = "results/tables/validation_phase4.tsv",
        scorecard = "results/tables/fragility_scorecard.tsv",
        figure    = "results/figures/fragility_scorecard.png",
        script    = "scripts/python/validate_fragility_scorecard.py",
    output:
        tsv = "results/tables/validation_fragility_scorecard.tsv",
        md  = "results/PHASE5A1_VALIDATION.md",
    log: "results/logs/validate_fragility_scorecard.log"
    shell:
        "python3 {input.script} --cube {input.cube} --ne500 {input.ne500} "
        "--robustness {input.robust} --wolf-load {input.load} --wolf-roh {input.roh} "
        "--validation-phase2 {input.val2} --validation-phase3 {input.val3} "
        "--validation-phase4 {input.val4} --scorecard {input.scorecard} "
        "--figure {input.figure} --out-tsv {output.tsv} --out-md {output.md} "
        "> {log} 2>&1 || (cat {log}; exit 1)"
