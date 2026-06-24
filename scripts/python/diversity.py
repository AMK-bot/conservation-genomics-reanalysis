#!/usr/bin/env python3
"""Per-population Ho / He / Fis + per-individual heterozygosity from a VCF.

Reused for (a) the modern 3-population Set-B contrast and (b) the temporal
museum-vs-modern (angle-G) contrast — caller just supplies a different popmap.

CAVEAT baked into the output: Ho/He here are computed over a SNP-only callset,
so they are RELATIVE measures (valid for comparing groups on the *same* sites),
not absolute genome-wide heterozygosity (Sopniewski & Catullo 2024, plan §4).
He is the unbiased (sample-size-corrected) expected heterozygosity.
"""
import argparse, sys
import numpy as np
import pandas as pd
import allel


def load(vcf, samples_keep):
    cs = allel.read_vcf(vcf, fields=["samples", "calldata/GT"], alt_number=1)
    if cs is None:
        sys.exit(f"no variants read from {vcf}")
    vcf_samples = list(cs["samples"])
    idx = [vcf_samples.index(s) for s in samples_keep if s in vcf_samples]
    missing = [s for s in samples_keep if s not in vcf_samples]
    if missing:
        sys.exit(f"samples not in {vcf}: {missing}")
    g = allel.GenotypeArray(cs["calldata/GT"]).take(idx, axis=1)
    return g, [vcf_samples[i] for i in idx]


def group_stats(g):
    """Ho, unbiased He, Fis over the variant sites where the group has >=1 call."""
    ho_pv = allel.heterozygosity_observed(g)              # per-variant observed het
    ac = g.count_alleles()
    an = ac.sum(axis=1)                                   # called alleles per variant
    with np.errstate(invalid="ignore", divide="ignore"):
        af = ac.to_frequencies()
        he_pv = 1.0 - np.sum(af ** 2, axis=1)             # expected het (biased)
        # unbiased (Nei 1978): multiply by 2N/(2N-1)
        corr = np.where(an > 1, an / (an - 1.0), np.nan)
        he_unb = he_pv * corr
    keep = an > 0
    ho = np.nanmean(ho_pv[keep])
    he = np.nanmean(he_unb[keep])
    fis = 1.0 - ho / he if he > 0 else np.nan
    return dict(n_called_sites=int(keep.sum()), Ho=ho, He=he, Fis=fis)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--vcf", required=True)
    p.add_argument("--popmap", required=True, help="TSV: sample<TAB>group (header sample/population)")
    p.add_argument("--out-pop", required=True)
    p.add_argument("--out-ind", required=True)
    a = p.parse_args()

    pm = pd.read_csv(a.popmap, sep="\t")
    pm.columns = ["sample", "group"][: len(pm.columns)]
    g, samples = load(a.vcf, pm["sample"].tolist())
    grp = pm.set_index("sample").loc[samples, "group"].to_numpy()

    # per-population
    rows = []
    for pop in pd.unique(grp):
        idx = np.where(grp == pop)[0]
        st = group_stats(g.take(idx, axis=1))
        rows.append(dict(population=pop, n=len(idx), **st))
    pop_df = pd.DataFrame(rows).sort_values("population")
    pop_df.to_csv(a.out_pop, sep="\t", index=False)

    # per-individual observed heterozygosity (fraction of het among called genotypes)
    is_het = g.is_het()            # (variants, samples) bool
    is_called = g.is_called()
    het_rate = is_het.sum(axis=0) / np.maximum(is_called.sum(axis=0), 1)
    ind_df = pd.DataFrame(
        dict(sample=samples, population=grp,
             n_called=is_called.sum(axis=0), obs_het_rate=het_rate)
    ).sort_values(["population", "sample"])
    ind_df.to_csv(a.out_ind, sep="\t", index=False)

    print(pop_df.to_string(index=False))


if __name__ == "__main__":
    main()
