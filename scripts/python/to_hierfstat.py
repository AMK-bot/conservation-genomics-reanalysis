#!/usr/bin/env python3
"""VCF -> hierfstat genotype table (pop + loci coded 11/12/22, NA missing).

Lets R compute rarefied allelic richness without an R VCF reader (vcfR is not in
the env). Optionally subsamples to --max-sites (seeded) so hierfstat stays fast
and memory-bounded on an 8 GB machine — allelic richness is a per-locus mean, so
a random thin of independent-enough SNPs gives a stable estimate.
"""
import argparse, sys
import numpy as np
import pandas as pd
import allel


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--vcf", required=True)
    p.add_argument("--popmap", required=True)
    p.add_argument("--max-sites", type=int, default=50000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--complete-only", action="store_true",
                   help="keep only loci genotyped in ALL kept samples "
                        "(so allelic.richness rarefies to the true smallest-pop n, "
                        "not down to one badly-genotyped locus)")
    p.add_argument("--out", required=True)
    a = p.parse_args()

    cs = allel.read_vcf(a.vcf, fields=["samples", "calldata/GT", "variants/numalt"], alt_number=1)
    if cs is None:
        sys.exit(f"no variants read from {a.vcf}")
    vcf_samples = list(cs["samples"])
    pm = pd.read_csv(a.popmap, sep="\t")
    pm.columns = ["sample", "population"][: len(pm.columns)]
    keep = [s for s in pm["sample"] if s in vcf_samples]
    idx = [vcf_samples.index(s) for s in keep]

    g = allel.GenotypeArray(cs["calldata/GT"]).take(idx, axis=1)

    # the 11/12/22 coding below is only valid for biallelic SNPs: to_n_alt collapses ALT1/ALT2
    # into one allele, which would undercount allelic richness at multiallelic loci. Drop them
    # defensively (the normalized comparative has none, but guard anyway). Review fix #2.
    biallelic = cs["variants/numalt"] <= 1
    if not biallelic.all():
        g = g.compress(biallelic, axis=0)
        print(f"dropped {(~biallelic).sum()} multiallelic loci (11/12/22 coding needs biallelic)", file=sys.stderr)

    n = g.to_n_alt(fill=-1)                              # (variants, samples): 0/1/2/-1

    if a.complete_only:
        complete = (n >= 0).all(axis=1)
        n = n[complete]
        print(f"complete-case loci: {n.shape[0]}", file=sys.stderr)

    # subsample variants (seeded) if needed
    if a.max_sites and n.shape[0] > a.max_sites:
        rng = np.random.default_rng(a.seed)
        sel = np.sort(rng.choice(n.shape[0], a.max_sites, replace=False))
        n = n[sel]
    print(f"hierfstat table: {n.shape[1]} ind x {n.shape[0]} loci", file=sys.stderr)

    code = np.full(n.shape, "", dtype=object)           # 11/12/22, "" -> NA
    code[n == 0] = "11"
    code[n == 1] = "12"
    code[n == 2] = "22"
    df = pd.DataFrame(code.T, index=keep,               # ind x loci
                      columns=[f"L{i}" for i in range(n.shape[0])])
    df.insert(0, "pop", pm.set_index("sample").loc[keep, "population"].to_numpy())
    df.to_csv(a.out, sep="\t", na_rep="NA")
    # blanks -> NA
    print(f"wrote {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
