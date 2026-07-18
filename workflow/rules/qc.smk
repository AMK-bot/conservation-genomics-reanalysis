# workflow/rules/qc.smk — Phase 1: QC & filtering (plan §4)
#
# Two callsets from the Modern_all peafowl VCF:
#   Set A (structure/N_e): biallelic SNP autosomes -> per-preset depth/GQ/missingness/MAC
#                          -> per-population HWE -> LD-prune (--indep-pairwise).
#                          Re-derived PER PRESET -> this is the cube's filtering knob.
#   Set B (diversity):     lightly filtered, NO MAF/MAC/HWE/LD-prune.
# Plus the confirmatory kin screen (PLINK2 KING) — run BEFORE structure so undetected
# relatives can't bias it; but the deposited 22 are already the authors' post-kin set,
# so KING is a GATE that reports + keeps the published 22 (plan §4), never a cutter.
#
# Every threshold comes from config["peafowl"]. Nothing here is hard-coded.

PEA       = config["paths"]["peafowl"]
NORM      = PEA["norm_parent"]
PRESETS   = config["cube"]["filter_presets"]
POPS      = config["peafowl"]["populations"]
STRUCT_PRESET = config["peafowl"]["kinship"]["structure_preset"]


wildcard_constraints:
    preset = "|".join(PRESETS),     # keep {preset} from greedily matching 'lenient.pruned'
    K      = r"\d+",
    seed   = r"\d+",


def _preset(w):
    return config["peafowl"]["filtering"]["presets"][w.preset]


rule norm_parent:
    """Modern_all -> bcftools norm -m -any -> biallelic SNPs on autosomes (shared parent)."""
    input:
        vcf  = PEA["set_b_all"],
        auto = PEA["autosomes"],
    output:
        vcf = NORM,
        idx = NORM + ".tbi",
    threads: 3
    log: "results/logs/norm_parent.log"
    shell:
        r"""
        # ponytail: paste -sd, makes -t robust to the file being comma- OR newline-separated.
        AUTO=$(paste -sd, {input.auto})
        bcftools norm -m -any {input.vcf} -Ou 2> {log} \
          | bcftools view -t "$AUTO" -m2 -M2 -v snps --threads {threads} -Oz -o {output.vcf} 2>> {log}
        bcftools index -t {output.vcf} 2>> {log}
        """


rule filter_setA:
    """Per-preset Set A pre-prune (the filtering knob). See scripts/filter_preset.sh."""
    input:
        vcf    = NORM,
        idx    = NORM + ".tbi",
        popmap = PEA["popmap"],
    output:
        vcf     = "results/qc/setA.{preset}.vcf.gz",
        idx     = "results/qc/setA.{preset}.vcf.gz.tbi",
        postmac = "results/qc/setA.{preset}.postmac_count",   # filter_preset.sh writes ${OUT%.vcf.gz}.postmac_count
    params:
        dp    = lambda w: _preset(w)["min_dp"],
        gq    = lambda w: _preset(w)["min_gq"],
        mac   = lambda w: _preset(w)["mac"],
        fmiss = lambda w: round(1 - _preset(w)["max_missing"], 4),
        hwe   = config["peafowl"]["filtering"]["hwe_per_population"],
        pops  = " ".join(POPS),
        tmp   = "results/qc/tmp_setA_{preset}",
    log: "results/logs/filter_setA.{preset}.log"
    shell:
        r"""
        bash scripts/filter_preset.sh {input.vcf} {input.popmap} "{params.pops}" \
          {params.dp} {params.gq} {params.mac} {params.fmiss} {params.hwe} \
          {output.vcf} {params.tmp} > {log} 2>&1
        rm -rf {params.tmp}
        """


rule ld_prune:
    """LD-prune Set A -> bed (ADMIXTURE) + pruned VCF (scikit-allel PCA/diversity)."""
    input:
        vcf = "results/qc/setA.{preset}.vcf.gz",
    output:
        prunein  = "results/qc/setA.{preset}.prune.in",
        bed      = "results/qc/setA.{preset}.pruned.bed",
        bim      = "results/qc/setA.{preset}.pruned.bim",
        fam      = "results/qc/setA.{preset}.pruned.fam",
        prunevcf = "results/qc/setA.{preset}.pruned.vcf.gz",
    params:
        ld  = config["peafowl"]["filtering"]["ld_prune"],
        pfx = "results/qc/setA.{preset}",
    log: "results/logs/ld_prune.{preset}.log"
    shell:
        r"""
        # VCF IDs are all '.' -> assign unique chrom:pos:allele IDs so --extract can
        # actually select the pruned set (without this, --extract '.' keeps ALL sites).
        # plink 1.9 (not plink2): plink2 refuses LD pruning at n<50; small-n is part of the thesis.
        plink --vcf {input.vcf} --allow-extra-chr --double-id \
          --set-missing-var-ids '@:#:$1:$2' \
          --indep-pairwise {params.ld} --out {params.pfx} > {log} 2>&1
        # bed for ADMIXTURE (integer chr codes: strip 'chromosome_' -> portable, no sed -i)
        plink --vcf {input.vcf} --allow-extra-chr --double-id \
          --set-missing-var-ids '@:#:$1:$2' \
          --extract {output.prunein} --make-bed --out {params.pfx}.pruned >> {log} 2>&1
        sed 's/^chromosome_//' {output.bim} > {output.bim}.tmp && mv {output.bim}.tmp {output.bim}
        # pruned VCF for scikit-allel
        plink --vcf {input.vcf} --allow-extra-chr --double-id \
          --set-missing-var-ids '@:#:$1:$2' \
          --extract {output.prunein} --recode vcf-iid bgz --out {params.pfx}.pruned >> {log} 2>&1
        bcftools index -t {output.prunevcf} >> {log} 2>&1
        """


rule filter_setB:
    """Set B (diversity): light genotype mask + light missingness, NO MAF/MAC/HWE/LD-prune."""
    input:
        vcf = NORM,
        idx = NORM + ".tbi",
    output:
        vcf = "results/qc/setB.vcf.gz",
        idx = "results/qc/setB.vcf.gz.tbi",
    params:
        dp    = config["peafowl"]["set_b"]["min_dp"],
        gq    = config["peafowl"]["set_b"]["min_gq"],
        fmiss = round(1 - config["peafowl"]["set_b"]["max_missing"], 4),
    log: "results/logs/filter_setB.log"
    shell:
        r"""
        bcftools filter -S . -e "FMT/DP<{params.dp} | FMT/GQ<{params.gq}" {input.vcf} -Ou 2> {log} \
          | bcftools view -e "F_MISSING > {params.fmiss}" -Oz -o {output.vcf} 2>> {log}
        bcftools index -t {output.vcf} 2>> {log}
        """


rule snp_counts:
    """QC accounting table: re-derived per-preset counts + Set B + the frozen neutral ref."""
    input:
        setA = expand("results/qc/setA.{preset}.vcf.gz", preset=PRESETS),
        pruned = expand("results/qc/setA.{preset}.pruned.vcf.gz", preset=PRESETS),
        postmac = expand("results/qc/setA.{preset}.postmac_count", preset=PRESETS),
        setB = "results/qc/setB.vcf.gz",
    output:
        tsv = "results/tables/qc_snp_counts.tsv",
    params:
        neutral = PEA["set_a_neutral"],
        presets = " ".join(PRESETS),   # bare list -> repr in shell; join like pops in filter_setA
    shell:
        r"""
        {{
          printf "callset\tpreset\tsnps\n"
          for p in {params.presets}; do
            printf "setA_postMAC\t%s\t%s\n"   "$p" "$(cat results/qc/setA.$p.postmac_count)"
            printf "setA_postHWE\t%s\t%s\n"   "$p" "$(bcftools index -n results/qc/setA.$p.vcf.gz)"
            printf "setA_pruned\t%s\t%s\n"    "$p" "$(bcftools index -n results/qc/setA.$p.pruned.vcf.gz)"
          done
          printf "setB\t-\t%s\n" "$(bcftools index -n {input.setB})"
          printf "frozen_neutral_ref\t-\t%s\n" "$(grep -vc '^#' '{params.neutral}')"
        }} > {output.tsv}
        cat {output.tsv}
        """


rule kin_screen:
    """Confirmatory KING relatedness on the standard-preset pruned Set A (plan §4).
    Reports the relatedness matrix; flags pairs >= cutoff but KEEPS the published 22."""
    input:
        # read the pruned VCF, not the bed: the bed's chr codes were stripped to integers for
        # ADMIXTURE, and plink2 reads int '27' as human-autosome-27 (invalid) even with
        # --allow-extra-chr. The VCF keeps non-numeric 'chromosome_*' names, which --allow-extra-chr
        # handles. KING is biased under structure -> cross-population values are unreliable (note in report).
        vcf = f"results/qc/setA.{STRUCT_PRESET}.pruned.vcf.gz",
        popmap = PEA["popmap"],
    output:
        kin = "results/tables/kinship_king.tsv",
        fig = "results/figures/kinship_heatmap.png",
    params:
        cutoff = config["peafowl"]["kinship"]["relatedness_cutoff"],
    log: "results/logs/kin_screen.log"
    shell:
        r"""
        plink2 --vcf {input.vcf} --allow-extra-chr --double-id --make-king-table --out results/qc/kinship > {log} 2>&1
        cp results/qc/kinship.kin0 {output.kin}
        python scripts/python/plots.py kinship --kin0 {output.kin} \
          --cutoff {params.cutoff} --popmap {input.popmap} --out {output.fig} >> {log} 2>&1
        """
