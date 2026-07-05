# workflow/rules/load.smk — Phase 4: wolf genetic load + ROH (plan §7)
#
# CLI-streaming-first — the 11 GB allSNPs VCF never enters RAM. Per-chromosome:
#   load: bcftools query streams (CHROM POS REF ALT AA + GTs) -> wolf_gerp_load.py accumulates
#         GERP-weighted realized/masked load per individual, for GERP thresholds {2,3,4} in ONE
#         pass (the wolf-side fragility knob). Faithful to Smeds & Ellegren 2022's
#         gerp_load_polarized.py; at GERP>4 it reproduces the deposit's LoadPerInd.thres4 anchor.
#   ROH:  bcftools roh (HMM, GT-based, low RAM) per chromosome -> per-individual F_ROH swept over
#         a ROH-length cutoff (the second fragility knob).
# Uses config["wolf"] + config["paths"]["wolf"].

WOLF = config["paths"]["wolf"]
WCFG = config["wolf"]
WOLF_CHROMS = [str(c) for c in range(1, WCFG["n_autosomes"] + 1)]   # 1..38 autosomes
GERP_THRES = ",".join(str(t) for t in WCFG["load"]["gerp_sensitivity"])


rule wolf_samples:
    """Ordered sample list (VCF column order) for the load accumulator."""
    input: vcf = WOLF["allsnps"]
    output: "results/wolf/samples.txt"
    shell: "bcftools query -l {input.vcf} > {output}"


rule wolf_popmap:
    """IND<TAB>POP (POP = deposit's time-period label) from the precomputed-load anchor —
    the authoritative individual->period map, guaranteed consistent with the source."""
    input: anchor = WOLF["load_anchor"]
    output: "results/wolf/popmap.tsv"
    shell: r"""awk 'NR>1{{print $1"\t"$2}}' {input.anchor} > {output}"""


rule wolf_contig_lengths:
    """Autosome (1..38) lengths from the VCF header — denominator for F_ROH."""
    input: vcf = WOLF["allsnps"]
    output: "results/wolf/autosome_lengths.tsv"
    shell:
        r"""bcftools view -h {input.vcf} | grep '^##contig' \
          | sed -E 's/.*ID=([^,>]+).*length=([0-9]+).*/\1\t\2/' \
          | awk -F'\t' '$1 ~ /^[0-9]+$/ && $1+0>=1 && $1+0<=38' > {output}"""


rule wolf_gerp_split:
    """Split the whole-genome GERP bed into per-chromosome slices (one pass)."""
    input: bed = WOLF["gerp_allsnps_bed"]
    output: expand("results/wolf/gerp/chr{c}.bed", c=WOLF_CHROMS)
    params: outdir = "results/wolf/gerp", chroms = " ".join(WOLF_CHROMS)
    shell:
        r"""mkdir -p {params.outdir}
        for c in {params.chroms}; do : > {params.outdir}/chr$c.bed; done
        awk -v od={params.outdir} '$1 ~ /^[0-9]+$/ && $1+0>=1 && $1+0<=38 {{print >> (od"/chr"$1".bed")}}' {input.bed}"""


rule wolf_load_chrom:
    """Per-chromosome GERP-load accumulation (all thresholds in one VCF stream)."""
    input:
        vcf     = WOLF["allsnps"],
        gerp    = "results/wolf/gerp/chr{c}.bed",
        samples = "results/wolf/samples.txt",
        popmap  = "results/wolf/popmap.tsv",
        script  = "scripts/python/wolf_gerp_load.py",
    output: "results/wolf/load/chr{c}.tsv"
    params: thres = GERP_THRES
    log: "results/logs/wolf_load_chr{c}.log"
    shell:
        r"""set -euo pipefail
        bcftools query -r {wildcards.c} -f '%CHROM\t%POS\t%REF\t%ALT\t%INFO/AA[\t%GT]\n' {input.vcf} \
          | python3 {input.script} --gerp-bed {input.gerp} --samples {input.samples} \
              --popmap {input.popmap} --thresholds {params.thres} --out {output} > {log} 2>&1"""


rule wolf_load_merge:
    """Sum per-chromosome raw counts -> genome-wide per-individual realized/masked load."""
    input:
        chroms = expand("results/wolf/load/chr{c}.tsv", c=WOLF_CHROMS),
        script = "scripts/python/wolf_load_merge.py",
    output:
        tsv     = "results/tables/wolf_load.tsv",
        parquet = "results/tables/wolf_load.parquet",
    log: "results/logs/wolf_load_merge.log"
    shell:
        "python3 {input.script} --inputs {input.chroms} --out-tsv {output.tsv} "
        "--out-parquet {output.parquet} > {log} 2>&1"


rule wolf_roh_chrom:
    """bcftools roh per chromosome (GT-based HMM, low RAM); keep the RG region records."""
    input: vcf = WOLF["allsnps"]
    output: "results/wolf/roh/chr{c}.rg.txt"
    params:
        g = WCFG["roh"]["gt_error_phred"],
        rr = WCFG["roh"]["rec_rate_per_bp"],
    log: "results/logs/wolf_roh_chr{c}.log"
    shell:
        r"""set -euo pipefail
        bcftools roh -G{params.g} --AF-tag AF --rec-rate {params.rr} -r {wildcards.c} {input.vcf} 2>{log} \
          | awk '$1=="RG"' > {output}"""


rule wolf_roh_summarize:
    """Per-individual F_ROH swept over the ROH-length cutoff (the second wolf fragility knob)."""
    input:
        rg      = expand("results/wolf/roh/chr{c}.rg.txt", c=WOLF_CHROMS),
        lengths = "results/wolf/autosome_lengths.tsv",
        popmap  = "results/wolf/popmap.tsv",
        script  = "scripts/python/wolf_roh_summarize.py",
    output:
        tsv     = "results/tables/wolf_roh.tsv",
        parquet = "results/tables/wolf_roh.parquet",
    params:
        cutoffs = ",".join(str(x) for x in WCFG["roh"]["length_cutoffs_mb"]),
        longcut = WCFG["roh"]["long_roh_threshold_mb"],
    log: "results/logs/wolf_roh_summarize.log"
    shell:
        "python3 {input.script} --rg {input.rg} --lengths {input.lengths} --popmap {input.popmap} "
        "--cutoffs-mb {params.cutoffs} --long-cutoff-mb {params.longcut} "
        "--out-tsv {output.tsv} --out-parquet {output.parquet} > {log} 2>&1"
