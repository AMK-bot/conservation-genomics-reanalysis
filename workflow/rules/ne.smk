# workflow/rules/ne.smk — Phase 2: contemporary N_e + the results cube (plan §5)
#
# THE ENGINEERING CORE. For each (filter preset x structure mode x population) cell, run
# currentNe2 once -> one N_e + 90% CI -> long/tidy results/cube/results_cube.parquet.
#
#   cube = filter (lenient/standard/strict) x structure (per_population vs pooled)
#   * per_population : currentNe2 on each of the 3 pops  -> the GBF "fraction > 500" inputs
#   * pooled         : currentNe2 on all 22 (population=ALL) -> Wahlund-biased-low contrast
#   -> 3 per-pop + 1 pooled, per preset = 4 rows/preset = 12 rows.
#
# Input is the UN-pruned Set A (LD-N_e reads N_e *from* LD; pruning destroys the signal).
# Genome size = 32 Morgans -> currentNe2's cross-chromosome estimate (the cleaner one).
# GONE2 = recent-trajectory CONTEXT panel only (NOT a cube axis, NOT in the badge).
# NeEstimator-LDNe stays a MANUAL GUI cross-check (outside the DAG; see report/ne_crosscheck.md).

_PEA        = config["paths"]["peafowl"]
_POPS       = config["peafowl"]["populations"]
_PRESETS    = config["cube"]["filter_presets"]
_NE         = config["peafowl"]["ne"]
_GENOME_M   = _NE["genome_size_morgans"]
_SNP_CAP    = _NE["snp_cap"]
_NE_THREADS = _NE["threads"]
_NE_THRESH  = config["gbf"]["ne_threshold"]
_SEED       = config["project"]["seed"]
_G2         = _NE["gone2"]
CN2  = "tools/currentNe2/currentne2"
GONE = "tools/GONE2/gone2"

# Cube cells: (preset, structure_mode, population). pooled -> population = ALL.
NE_CELLS = []
for _p in _PRESETS:
    for _pop in _POPS:
        NE_CELLS.append((_p, "per_population", _pop))
    NE_CELLS.append((_p, "pooled", "ALL"))


def _cell_tsv(preset, mode, pop):
    return f"results/ne/cells/{preset}.{mode}.{pop}.tsv"


wildcard_constraints:
    mode = "per_population|pooled",
    grp  = "|".join(_POPS + ["ALL"]),   # 'pop' is reserved by Snakemake -> use 'grp'


rule currentne2_cell:
    """One cube cell. Subset Set A to {grp} (ALL = pooled 22) -> plain .vcf -> currentNe2
    (cross-chromosome estimate via genome size in Morgans) -> one tidy row. -s cap is
    reproducible (the binary is patched to a fixed RNG seed)."""
    input:
        vcf    = "results/qc/setA.{preset}.vcf.gz",
        popmap = _PEA["popmap"],
        binary = CN2,
    output:
        tsv = "results/ne/cells/{preset}.{mode}.{grp}.tsv",
        raw = "results/ne/raw/{preset}.{mode}.{grp}.currentne2.txt",
    threads: _NE_THREADS
    params:
        cap = _SNP_CAP, genome = _GENOME_M, thresh = _NE_THRESH,
    log: "results/logs/ne_currentne2.{preset}.{mode}.{grp}.log"
    shell:
        r"""
        mkdir -p results/ne/cells results/ne/raw
        tmp=$(mktemp -d)
        keep=$tmp/keep.txt
        if [ "{wildcards.grp}" = "ALL" ]; then
          tail -n +2 {input.popmap} | cut -f1 > $keep
        else
          awk -F'\t' -v p='{wildcards.grp}' 'NR>1 && $2==p {{print $1}}' {input.popmap} > $keep
        fi
        bcftools view -S $keep --force-samples {input.vcf} -Ov -o $tmp/cell.vcf 2> {log}
        # currentNe2 reads plain .vcf only; reduced-array build (8 GB-safe); cross-chrom needs the Morgans arg.
        {input.binary} -t {threads} -s {params.cap} -o {output.raw} $tmp/cell.vcf {params.genome} >> {log} 2>&1
        # n_ind is read from the raw output (what currentNe2 actually analyzed), not the keep-list count.
        python scripts/python/currentne2_parse.py --output {output.raw} \
          --preset {wildcards.preset} --structure-mode {wildcards.mode} --population {wildcards.grp} \
          --ne-threshold {params.thresh} --out {output.tsv} >> {log} 2>&1
        rm -rf $tmp
        """


rule assemble_cube:
    """All 12 cells -> results_cube.parquet (+ .csv mirror) — the fragility cube (plan §5)."""
    input:
        cells = [_cell_tsv(p, m, pop) for (p, m, pop) in NE_CELLS],
    output:
        parquet = config["paths"]["cube"],
        csv     = "results/cube/results_cube.csv",
    log: "results/logs/assemble_cube.log"
    shell:
        r"""
        python scripts/python/assemble_cube.py --cells {input.cells} \
          --out-parquet {output.parquet} --out-csv {output.csv} > {log} 2>&1
        cat {log}
        """


rule cube_figure:
    """Static fragility view (per-pop N_e across presets, N_e threshold line, pooled contrast)."""
    input:
        cube = config["paths"]["cube"],
    output:
        fig = "results/figures/ne_cube.png",
    params:
        thresh = _NE_THRESH,
    log: "results/logs/ne_cube_figure.log"
    shell:
        "python scripts/python/plots.py cube --cube {input.cube} --threshold {params.thresh} "
        "--out {output.fig} > {log} 2>&1"


rule currentne2_xcheck:
    """REPORT cross-check, NOT a cube axis (plan §5): currentNe2 -x metapopulation correction on
    the pooled 22 per preset. Confirms the structure-bias direction; never feeds the GBF badge."""
    input:
        vcf    = "results/qc/setA.{preset}.vcf.gz",
        popmap = _PEA["popmap"],
        binary = CN2,
    output:
        raw = "results/ne/raw/{preset}.metapop_x.currentne2.txt",
    threads: _NE_THREADS
    params:
        cap = _SNP_CAP, genome = _GENOME_M,
    log: "results/logs/ne_xcheck.{preset}.log"
    shell:
        r"""
        mkdir -p results/ne/raw
        tmp=$(mktemp -d)
        tail -n +2 {input.popmap} | cut -f1 > $tmp/keep.txt
        bcftools view -S $tmp/keep.txt --force-samples {input.vcf} -Ov -o $tmp/all.vcf 2> {log}
        # -x = metapopulation of equal-size subpops (the tool forbids -k with -x).
        {input.binary} -x -t {threads} -s {params.cap} -o {output.raw} $tmp/all.vcf {params.genome} >> {log} 2>&1
        rm -rf $tmp
        """


rule xcheck_table:
    """Collate the -x metapopulation cross-check into one report table (handles non-convergence)."""
    input:
        raws = expand("results/ne/raw/{preset}.metapop_x.currentne2.txt", preset=_PRESETS),
    output:
        tsv = "results/tables/ne_metapop_xcheck.tsv",
    log: "results/logs/ne_xcheck_collate.log"
    shell:
        "python scripts/python/ne_xcheck_collate.py --out {output.tsv} {input.raws} > {log} 2>&1"


rule neestimator_input:
    """GenePop input for the MANUAL NeEstimator-LDNe cross-check (plan §5): the standard-preset
    LD-PRUNED Set A (NeEstimator assumes unlinked markers -> the pruned VCF is exactly its input,
    the one N_e use of Phase 1's pruned output). The GUI run + the comparison table stay manual
    (report/ne_crosscheck.md)."""
    input:
        # PINNED to the standard preset: the LDNe cross-check is documented as standard-preset
        # throughout (report/ne_crosscheck.md), and is independent of kinship.structure_preset
        # (that knob drives the KING/PCA/ADMIXTURE figures, not this N_e cross-check).
        vcf    = "results/qc/setA.standard.pruned.vcf.gz",
        popmap = _PEA["popmap"],
    output:
        genepop = "results/ne/neestimator/setA.standard.pruned.genepop",
    log: "results/logs/neestimator_input.log"
    shell:
        r"""
        mkdir -p results/ne/neestimator
        python scripts/python/vcf_to_genepop.py --vcf {input.vcf} --popmap {input.popmap} \
          --out {output.genepop} > {log} 2>&1
        """


rule gone2_context:
    """GONE2 recent-trajectory CONTEXT panel (plan §5): all 22, standard un-pruned Set A,
    -x metapopulation, -g 0 unphased, borrowed constant rate -r (peafowl has no map),
    reproducible -S seed. NOT a cube axis, NOT in the badge — different time horizon."""
    input:
        vcf    = f"results/qc/setA.{_G2['structure_preset']}.vcf.gz",
        binary = GONE,
    output:
        ne    = "results/tables/gone2_trajectory.tsv",
        stats = "results/ne/gone2/gone2_GONE2_STATS",
        fig   = "results/figures/gone2_trajectory.png",
    threads: _NE_THREADS
    params:
        rate = _G2["rec_rate_cm_per_mb"], g = _G2["genotype_mode"],
        cap = _G2["snp_cap"], seed = _SEED,
        xflag = "-x" if _G2["metapopulation"] else "",
        min_cm = _G2["min_chrom_cm"], max_cm = _G2["max_chrom_cm"],
    log: "results/logs/gone2_context.log"
    shell:
        r"""
        mkdir -p results/ne/gone2
        tmp=$(mktemp -d)
        # GONE2 aborts unless EVERY chromosome is 20-1000 cM -> keep only macrochromosomes whose
        # SNP span * rate is within [min,max] cM (the borrowed rate makes microchromosomes too short).
        keep=$(bcftools query -f '%CHROM\t%POS\n' {input.vcf} | \
          awk -v r={params.rate} -v lo={params.min_cm} -v hi={params.max_cm} \
            '{{ if(!(($1) in mn)){{mn[$1]=$2}} mx[$1]=$2 }}
             END{{ for(c in mx){{ cm=(mx[c]-mn[c])/1e6*r; if(cm>=lo && cm<=hi) print c }} }}' | paste -sd, -)
        echo "GONE2 macrochromosomes kept: $keep" > {log}
        bcftools view -t "$keep" {input.vcf} -Ov -o $tmp/g.vcf 2>> {log}
        # -r uses the VCF physical positions to infer an approximate genetic map (no .map needed).
        {input.binary} -g {params.g} {params.xflag} -r {params.rate} -s {params.cap} \
          -S {params.seed} -t {threads} -o $tmp/gone2 $tmp/g.vcf >> {log} 2>&1
        # -x writes _GONE2_Ne_mix (metapopulation), plain run writes _GONE2_Ne -> normalize either.
        if [ -f $tmp/gone2_GONE2_Ne_mix ]; then traj=$tmp/gone2_GONE2_Ne_mix; else traj=$tmp/gone2_GONE2_Ne; fi
        python scripts/python/gone2_parse.py --infile $traj --out {output.ne} >> {log} 2>&1
        cp $tmp/gone2_GONE2_STATS {output.stats}
        python scripts/python/plots.py gone2 --ne {output.ne} --out {output.fig} >> {log} 2>&1
        rm -rf $tmp
        """
