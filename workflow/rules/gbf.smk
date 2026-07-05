# workflow/rules/gbf.smk — Phase 3: GBF Goal-A genetic indicators + robustness (plan §6)  ← MVP
#
# From the cube (per_population rows only — pooled/ALL is the Wahlund contrast, never a GBF
# input): the N_e>threshold indicator (proportion of populations passing, per preset) + the
# robustness / verdict-stability table (angle C). Plus the NON-genomic "Populations
# Maintained" indicator (curated config/populations_maintained.tsv) and the census-proxy
# (N_c) contrast. ONE script writes all four tables; the Streamlit app only READS them.

rule gbf_indicators:
    """GBF Goal-A genetic indicators from the cube + curated PM data (plan §6)."""
    input:
        cube   = "results/cube/results_cube.parquet",
        cfg    = "config/config.yaml",
        pm     = "config/populations_maintained.tsv",
        script = "scripts/python/gbf_indicators.py",
    output:
        ne500    = "results/tables/gbf_ne500.tsv",
        robust   = "results/tables/gbf_robustness.tsv",
        pm_tbl   = "results/tables/gbf_populations_maintained.tsv",
        summary  = "results/tables/gbf_summary.tsv",
    log: "results/logs/gbf_indicators.log"
    shell:
        "python3 {input.script} > {log} 2>&1 || (cat {log}; exit 1)"
