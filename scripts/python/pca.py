#!/usr/bin/env python3
"""PCA on an LD-pruned callset (scikit-allel, Patterson scaler).

Outputs PC coordinates (with population labels) + variance explained per PC.
Missing genotypes are mean-imputed per variant; monomorphic sites are dropped.
"""
import argparse, sys
import numpy as np
import pandas as pd
import allel


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--vcf", required=True)
    p.add_argument("--popmap", required=True)
    p.add_argument("--n-components", type=int, default=10)
    p.add_argument("--out-coords", required=True)
    p.add_argument("--out-var", required=True)
    a = p.parse_args()

    cs = allel.read_vcf(a.vcf, fields=["samples", "calldata/GT"], alt_number=1)
    if cs is None:
        sys.exit(f"no variants read from {a.vcf}")
    samples = list(cs["samples"])
    g = allel.GenotypeArray(cs["calldata/GT"])
    gn = g.to_n_alt(fill=-1).astype("f4")              # 0/1/2, missing=-1

    # mean-impute missing per variant, drop monomorphic
    gn[gn < 0] = np.nan
    site_mean = np.nanmean(gn, axis=1, keepdims=True)
    inds = np.where(np.isnan(gn))
    gn[inds] = np.take(site_mean, inds[0])
    seg = np.nanstd(gn, axis=1) > 0
    gn = gn[seg]
    print(f"{a.vcf}: {gn.shape[0]} segregating sites x {gn.shape[1]} samples used for PCA", file=sys.stderr)

    ncomp = min(a.n_components, gn.shape[1] - 1)
    coords, model = allel.pca(gn, n_components=ncomp, scaler="patterson")

    pm = pd.read_csv(a.popmap, sep="\t")
    pm.columns = ["sample", "population"][: len(pm.columns)]
    pop = pm.set_index("sample").reindex(samples)["population"].to_numpy()

    cols = [f"PC{i+1}" for i in range(ncomp)]
    cdf = pd.DataFrame(coords, columns=cols)
    cdf.insert(0, "population", pop)
    cdf.insert(0, "sample", samples)
    cdf.to_csv(a.out_coords, sep="\t", index=False)

    ve = model.explained_variance_ratio_ * 100
    pd.DataFrame({"PC": cols, "pct_variance": ve}).to_csv(a.out_var, sep="\t", index=False)
    print("variance explained (%):", np.round(ve, 2))


if __name__ == "__main__":
    main()
