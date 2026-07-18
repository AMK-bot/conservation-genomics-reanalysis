# workflow/rules/diversity.smk — Phase 1: diversity + temporal angle G (plan §4)
#
# Modern 3 populations (Set B): Ho/He/Fis + per-individual heterozygosity (scikit-allel)
#   + rarefied allelic richness (hierfstat). Ho/He are SNP-based RELATIVE measures, not
#   genome-wide het (Sopniewski & Catullo 2024) — comparable across pops on a shared callset.
#
# Angle G (temporal): museum (5 kiz*) vs modern (6) on the comparative VCF —
#   windowed-pi (reproduces Dong et al. 2021) + Ho/He/AR rarefied to equal n.
#   Caveats (report): aDNA deamination can inflate museum diversity; geographically narrow.

_PEA   = config["paths"]["peafowl"]
_DIV   = config["peafowl"]["diversity"]
_TEMP  = config["peafowl"]["temporal"]
_SEED  = config["project"]["seed"]


# ── modern 3-population diversity (Set B) ─────────────────────────────────────
rule diversity_perpop:
    input:
        vcf    = "results/qc/setB.vcf.gz",
        popmap = _PEA["popmap"],
    output:
        perpop = "results/tables/diversity_perpop.tsv",
        ind = "results/tables/individual_het.tsv",
    log: "results/logs/diversity_perpop.log"
    shell:
        r"""
        python scripts/python/diversity.py --vcf {input.vcf} --popmap {input.popmap} \
          --out-pop {output.perpop} --out-ind {output.ind} > {log} 2>&1
        """


rule allelic_richness_modern:
    input:
        vcf    = "results/qc/setB.vcf.gz",
        popmap = _PEA["popmap"],
    output:
        hf = "results/qc/hierfstat_modern.tsv",
        ar = "results/tables/allelic_richness_modern.tsv",
        bs = "results/tables/basicstats_modern.tsv",
    params:
        maxsites = _DIV["ar_max_sites"],
    log: "results/logs/allelic_richness_modern.log"
    shell:
        r"""
        python scripts/python/to_hierfstat.py --vcf {input.vcf} --popmap {input.popmap} \
          --max-sites {params.maxsites} --complete-only --seed {_SEED} --out {output.hf} > {log} 2>&1
        Rscript --vanilla scripts/R/allelic_richness.R {output.hf} {output.ar} {output.bs} >> {log} 2>&1
        """


rule diversity_figure:
    input:
        perpop = "results/tables/diversity_perpop.tsv",
        ind = "results/tables/individual_het.tsv",
        ar  = "results/tables/allelic_richness_modern.tsv",
    output:
        fig = "results/figures/diversity_perpop.png",
    log: "results/logs/diversity_figure.log"
    shell:
        r"""
        python scripts/python/plots.py diversity --pop {input.perpop} --ind {input.ind} \
          --ar {input.ar} --out {output.fig} > {log} 2>&1
        """


# ── angle G: temporal museum vs modern (comparative VCF) ──────────────────────
rule comparative_norm:
    """Normalize the comparative VCF -> biallelic SNP autosomes + Set-B light mask, so the
    temporal Ho/He/AR sit on the SAME basis as modern Set B (the raw deposit carries 2,056
    indels/multiallelics that Set B excludes, and the 11/12/22 allelic-richness coding is only
    valid for biallelic SNPs). Review fix #1/#2.
    NOTE: windowed-pi (temporal_pi) deliberately stays on the RAW deposited comparative — that
    faithfully reproduces Dong et al. 2021's vcftools --window-pi on their filtered comparative VCF."""
    input:
        vcf  = _PEA["comparative"],
        auto = _PEA["autosomes"],
    output:
        vcf = "results/qc/comparative.norm.vcf.gz",
        idx = "results/qc/comparative.norm.vcf.gz.tbi",
    params:
        dp    = config["peafowl"]["set_b"]["min_dp"],
        gq    = config["peafowl"]["set_b"]["min_gq"],
        fmiss = round(1 - config["peafowl"]["set_b"]["max_missing"], 4),
    log: "results/logs/comparative_norm.log"
    shell:
        r"""
        AUTO=$(cat {input.auto})
        bcftools norm -m -any {input.vcf} -Ou 2> {log} \
          | bcftools view -t "$AUTO" -m2 -M2 -v snps -Ou 2>> {log} \
          | bcftools filter -S . -e "FMT/DP<{params.dp} | FMT/GQ<{params.gq}" -Ou 2>> {log} \
          | bcftools view -e "F_MISSING > {params.fmiss}" -Oz -o {output.vcf} 2>> {log}
        bcftools index -t {output.vcf} 2>> {log}
        """


rule temporal_popmap:
    output:
        tsv = "results/qc/temporal_popmap.tsv",
    run:
        with open(output.tsv, "w") as fh:
            fh.write("sample\tpopulation\n")
            for s in _TEMP["museum"]:
                fh.write(f"{s}\tmuseum\n")
            for s in _TEMP["modern"]:
                fh.write(f"{s}\tmodern\n")


rule temporal_pi:
    """Windowed nucleotide diversity museum vs modern (reproduces Nucleotide_diversity_.sh)."""
    input:
        vcf    = _PEA["comparative"],
        popmap = "results/qc/temporal_popmap.tsv",
    output:
        museum = "results/tables/temporal_pi_museum.windowed.pi",
        modern = "results/tables/temporal_pi_modern.windowed.pi",
        summary = "results/tables/temporal_pi_summary.tsv",
    params:
        win  = _TEMP["window_pi"],
        step = _TEMP["window_pi_step"],
        pfx  = "results/tables/temporal_pi",
    log: "results/logs/temporal_pi.log"
    shell:
        r"""
        for grp in museum modern; do
          awk -v g=$grp 'NR>1 && $2==g {{print $1}}' {input.popmap} > results/qc/$grp.keep
          vcftools --gzvcf {input.vcf} --keep results/qc/$grp.keep \
            --window-pi {params.win} --window-pi-step {params.step} \
            --out {params.pfx}_$grp > /dev/null 2>> {log}
        done
        python -c "
import pandas as pd
rows=[]
for g in ['museum','modern']:
    d=pd.read_csv('{params.pfx}_'+g+'.windowed.pi',sep='\t')
    rows.append(dict(group=g,n_windows=len(d),mean_pi=d.PI.mean(),median_pi=d.PI.median()))
pd.DataFrame(rows).to_csv('{output.summary}',sep='\t',index=False)
print(pd.DataFrame(rows).to_string(index=False))"
        """


rule temporal_diversity:
    """Ho/He (scikit-allel) + rarefied allelic richness (hierfstat) museum vs modern.
    Uses the NORMALIZED comparative (biallelic SNP autosomes) for parity with Set B (review fix #1/#2)."""
    input:
        vcf    = "results/qc/comparative.norm.vcf.gz",
        popmap = "results/qc/temporal_popmap.tsv",
    output:
        perpop = "results/tables/temporal_diversity.tsv",
        ind = "results/tables/temporal_individual_het.tsv",
        hf  = "results/qc/hierfstat_temporal.tsv",
        ar  = "results/tables/temporal_allelic_richness.tsv",
        bs  = "results/tables/temporal_basicstats.tsv",
    params:
        maxsites = _DIV["ar_max_sites"],
    log: "results/logs/temporal_diversity.log"
    shell:
        r"""
        python scripts/python/diversity.py --vcf {input.vcf} --popmap {input.popmap} \
          --out-pop {output.perpop} --out-ind {output.ind} > {log} 2>&1
        python scripts/python/to_hierfstat.py --vcf {input.vcf} --popmap {input.popmap} \
          --max-sites {params.maxsites} --complete-only --seed {_SEED} --out {output.hf} >> {log} 2>&1
        Rscript --vanilla scripts/R/allelic_richness.R {output.hf} {output.ar} {output.bs} >> {log} 2>&1
        """


rule temporal_figure:
    input:
        museum  = "results/tables/temporal_pi_museum.windowed.pi",
        modern  = "results/tables/temporal_pi_modern.windowed.pi",
        div     = "results/tables/temporal_diversity.tsv",
        ar      = "results/tables/temporal_allelic_richness.tsv",
    output:
        fig = "results/figures/temporal_diversity.png",
    log: "results/logs/temporal_figure.log"
    shell:
        r"""
        python scripts/python/plots.py temporal --pi-museum {input.museum} \
          --pi-modern {input.modern} --div {input.div} --ar {input.ar} \
          --out {output.fig} > {log} 2>&1
        """
