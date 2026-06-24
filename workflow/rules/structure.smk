# workflow/rules/structure.smk — Phase 1: population structure (plan §4)
#
# PCA (scikit-allel) + ADMIXTURE over a K x seed grid with CV error.
# Present multiple K, triangulate with PCA, don't over-interpret "best K".
# Structure figures use the standard-preset pruned Set A (config kinship.structure_preset).

_SP        = config["peafowl"]["kinship"]["structure_preset"]
_KS        = config["peafowl"]["structure"]["admixture_K"]
_SEEDS     = config["peafowl"]["structure"]["admixture_seeds"]
_CV        = config["peafowl"]["structure"]["admixture_cv_folds"]
_NPC       = config["peafowl"]["structure"]["pca_components"]


rule pca:
    input:
        vcf    = f"results/qc/setA.{_SP}.pruned.vcf.gz",
        popmap = config["paths"]["peafowl"]["popmap"],
    output:
        coords = "results/tables/pca_coords.tsv",
        var    = "results/tables/pca_variance.tsv",
        fig    = "results/figures/pca.png",
    log: "results/logs/pca.log"
    shell:
        r"""
        python3 scripts/python/pca.py --vcf {input.vcf} --popmap {input.popmap} \
          --n-components {_NPC} --out-coords {output.coords} --out-var {output.var} > {log} 2>&1
        python3 scripts/python/plots.py pca --coords {output.coords} --var {output.var} \
          --out {output.fig} >> {log} 2>&1
        """


rule admixture:
    """One (K, seed) run. ADMIXTURE writes <prefix>.<K>.Q in CWD and ignores -o, so run
    in a temp dir and move the result to a seeded name (else seeds overwrite each other)."""
    input:
        bed = f"results/qc/setA.{_SP}.pruned.bed",
        bim = f"results/qc/setA.{_SP}.pruned.bim",
        fam = f"results/qc/setA.{_SP}.pruned.fam",
    output:
        q  = "results/qc/admixture/setA.K{K}.s{seed}.Q",
        cv = "results/qc/admixture/setA.K{K}.s{seed}.cv",
    params:
        base = f"setA.{_SP}.pruned",
    log: "results/logs/admixture.K{K}.s{seed}.log"
    shell:
        r"""
        mkdir -p results/qc/admixture
        wd=$(mktemp -d)
        cp results/qc/{params.base}.bed results/qc/{params.base}.bim results/qc/{params.base}.fam $wd/
        ( cd "$wd" && admixture --cv={_CV} -s {wildcards.seed} {params.base}.bed {wildcards.K} ) > {log} 2>&1
        mv "$wd/{params.base}.{wildcards.K}.Q" {output.q}
        grep "CV error" {log} > {output.cv} || echo "CV error (K={wildcards.K}): NA" > {output.cv}
        rm -rf "$wd"
        """


rule admixture_collate:
    """Collate CV error across K x seed, pick best-seed Q per K, plot barplots."""
    input:
        q  = expand("results/qc/admixture/setA.K{K}.s{seed}.Q", K=_KS, seed=_SEEDS),
        cv = expand("results/qc/admixture/setA.K{K}.s{seed}.cv", K=_KS, seed=_SEEDS),
        fam = f"results/qc/setA.{_SP}.pruned.fam",
        popmap = config["paths"]["peafowl"]["popmap"],
    output:
        cvtsv = "results/tables/admixture_cv.tsv",
        fig   = "results/figures/admixture.png",
    log: "results/logs/admixture_collate.log"
    shell:
        r"""
        python3 scripts/python/plots.py admixture \
          --qdir results/qc/admixture --fam {input.fam} --popmap {input.popmap} \
          --Ks "{_KS}" --seeds "{_SEEDS}" \
          --out-cv {output.cvtsv} --out {output.fig} > {log} 2>&1
        """
