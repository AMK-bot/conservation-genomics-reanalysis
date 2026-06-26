#!/usr/bin/env python3
"""VCF -> GenePop, grouped by population, for the MANUAL NeEstimator-LDNe cross-check (plan §5).

NeEstimator-LDNe assumes UNLINKED markers, so this is fed the standard-preset *LD-pruned* Set A
(the one N_e use of Phase 1's pruned output). Biallelic SNPs -> alleles 01/02, missing 0000;
populations separated by 'Pop' lines (GenePop convention). The GUI run + the comparison table
stay manual (report/ne_crosscheck.md).
"""
import argparse
import sys
import numpy as np
import pandas as pd
import allel


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--vcf", required=True)
    p.add_argument("--popmap", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--title", default="peafowl Set A standard LD-pruned — NeEstimator-LDNe cross-check")
    a = p.parse_args()

    cs = allel.read_vcf(a.vcf, fields=["samples", "variants/CHROM", "variants/POS", "calldata/GT"],
                        alt_number=1)
    if cs is None:
        sys.exit(f"no variants read from {a.vcf}")
    samples = list(cs["samples"])
    gt = allel.GenotypeArray(cs["calldata/GT"])
    loci = [f"{c}_{pos}" for c, pos in zip(cs["variants/CHROM"], cs["variants/POS"])]

    pm = pd.read_csv(a.popmap, sep="\t").iloc[:, :2]   # first two cols; tolerate extra annotation cols
    pm.columns = ["sample", "population"]
    pop_of = dict(zip(pm["sample"], pm["population"]))

    # population order as first seen in popmap (only samples present in the VCF)
    pops = []
    for s in pm["sample"]:
        if s in samples and pop_of[s] not in pops:
            pops.append(pop_of[s])

    def encode(col):                       # col: (n_var, 2) allele indices, -1 = missing
        return [("0000" if a1 < 0 or a2 < 0 else f"{a1 + 1:02d}{a2 + 1:02d}") for a1, a2 in col]

    with open(a.out, "w") as fh:
        fh.write(a.title + "\n")
        fh.write("\n".join(loci) + "\n")
        n_ind = 0
        for pop in pops:
            fh.write("Pop\n")
            for s in pm["sample"]:
                if s in samples and pop_of.get(s) == pop:
                    genos = encode(np.asarray(gt[:, samples.index(s), :]))
                    fh.write(f"{s} , " + " ".join(genos) + "\n")
                    n_ind += 1
    print(f"GenePop: {len(loci)} loci, {n_ind} individuals, {len(pops)} pops -> {a.out}")


if __name__ == "__main__":
    main()
