#!/usr/bin/env python3
"""Phase-1 static figures. Subcommands: pca | admixture | kinship | diversity | temporal.

Figures are for the report / validation. The load-bearing outputs are the TSVs;
the Streamlit app (Phase 3) re-plots from those, so these stay deliberately plain.
"""
import argparse, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

POP_ORDER = ["Yunnan", "Vietnam", "Thailand", "museum", "modern"]
COLORS = {"Yunnan": "#1f77b4", "Vietnam": "#2ca02c", "Thailand": "#d62728",
          "museum": "#8c564b", "modern": "#1f77b4"}


def _order(pops):
    seen = [p for p in POP_ORDER if p in set(pops)]
    return seen + [p for p in pd.unique(pops) if p not in seen]


def pca(a):
    c = pd.read_csv(a.coords, sep="\t")
    v = pd.read_csv(a.var, sep="\t")
    fig, ax = plt.subplots(1, 2, figsize=(11, 5))
    for pop in _order(c["population"]):
        sub = c[c["population"] == pop]
        ax[0].scatter(sub["PC1"], sub["PC2"], label=pop, s=60,
                      color=COLORS.get(pop), edgecolor="k", linewidth=0.4)
    ax[0].set_xlabel(f"PC1 ({v.pct_variance.iloc[0]:.1f}%)")
    ax[0].set_ylabel(f"PC2 ({v.pct_variance.iloc[1]:.1f}%)")
    ax[0].set_title("Peafowl PCA (LD-pruned Set A)")
    ax[0].legend(frameon=False)
    ax[1].bar(v["PC"], v["pct_variance"], color="#666")
    ax[1].set_ylabel("% variance"); ax[1].set_title("Scree")
    ax[1].tick_params(axis="x", rotation=90)
    fig.tight_layout(); fig.savefig(a.out, dpi=150)


def _parse_list(s):
    return [int(x) for x in s.strip("[] ").replace(",", " ").split()]


def admixture(a):
    Ks, seeds = _parse_list(a.Ks), _parse_list(a.seeds)
    fam = pd.read_csv(a.fam, sep=r"\s+", header=None)
    samples = fam[1].tolist()                         # IID column (--double-id)
    pm = pd.read_csv(a.popmap, sep="\t").set_index("sample")
    pops = pm.reindex(samples)["population"].to_numpy()

    # collate CV error
    rows = []
    for K in Ks:
        for s in seeds:
            txt = open(f"{a.qdir}/setA.K{K}.s{s}.cv").read()
            cv = np.nan
            for tok in txt.replace(":", " ").split():
                try:
                    cv = float(tok)
                except ValueError:
                    pass
            rows.append(dict(K=K, seed=s, cv_error=cv))
    cv = pd.DataFrame(rows)
    cv.to_csv(a.out_cv, sep="\t", index=False)
    valid = cv.dropna(subset=["cv_error"])                          # skip Ks whose seeds all failed CV
    best = valid.loc[valid.groupby("K")["cv_error"].idxmin()]       # best seed per K
    Ks = [k for k in Ks if k in set(best["K"])]                     # only plot Ks with a valid seed

    order = np.argsort([POP_ORDER.index(p) if p in POP_ORDER else 99 for p in pops], kind="stable")
    fig, axes = plt.subplots(len(Ks) + 1, 1, figsize=(10, 1.6 * (len(Ks) + 1)))
    for ax, K in zip(axes[:-1], Ks):
        s = int(best.loc[best.K == K, "seed"].iloc[0])
        Q = np.loadtxt(f"{a.qdir}/setA.K{K}.s{s}.Q")
        if Q.ndim == 1:
            Q = Q[:, None]
        bottom = np.zeros(len(samples))
        for k in range(Q.shape[1]):
            ax.bar(range(len(samples)), Q[order, k], bottom=bottom[order], width=1.0)
            bottom += Q[:, k]
        ax.set_ylabel(f"K={K}"); ax.set_xticks([]); ax.set_xlim(-0.5, len(samples) - 0.5)
    # population labels + CV curve
    lab = axes[-1]
    cvmin = cv.groupby("K")["cv_error"].min()
    lab.plot(cvmin.index, cvmin.values, "o-", color="k")
    lab.set_xlabel("K"); lab.set_ylabel("min CV error"); lab.set_title("Cross-validation error")
    fig.suptitle("ADMIXTURE (best seed per K) + CV", y=1.0)
    fig.tight_layout(); fig.savefig(a.out, dpi=150)


def kinship(a):
    k = pd.read_csv(a.kin0, sep=r"\s+")
    # plink2 .kin0 columns include IID1, IID2, KINSHIP (names vary by version)
    cols = {c.upper(): c for c in k.columns}
    i1 = cols.get("ID1", cols.get("IID1")); i2 = cols.get("ID2", cols.get("IID2"))
    kc = cols.get("KINSHIP")
    samples = sorted(set(k[i1]) | set(k[i2]))
    idx = {s: i for i, s in enumerate(samples)}
    M = np.full((len(samples), len(samples)), np.nan)
    np.fill_diagonal(M, 0.5)
    flagged = []
    for _, r in k.iterrows():
        a_, b_, v = idx[r[i1]], idx[r[i2]], r[kc]
        M[a_, b_] = M[b_, a_] = v
        if v >= a.cutoff:
            flagged.append((r[i1], r[i2], v))
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(M, cmap="viridis", vmin=0)
    ax.set_xticks(range(len(samples))); ax.set_xticklabels(samples, rotation=90, fontsize=6)
    ax.set_yticks(range(len(samples))); ax.set_yticklabels(samples, fontsize=6)
    fig.colorbar(im, label="KING kinship")
    title = f"KING kinship — {len(flagged)} pair(s) ≥ {a.cutoff} (2nd-degree)"
    ax.set_title(title)
    fig.tight_layout(); fig.savefig(a.out, dpi=150)
    print(title)
    for f in flagged:
        print("  FLAG (kept per plan §4):", f)


def diversity(a):
    pop = pd.read_csv(a.pop, sep="\t")
    ind = pd.read_csv(a.ind, sep="\t")
    ar = pd.read_csv(a.ar, sep="\t")
    order = _order(pop["population"])
    pop = pop.set_index("population").reindex(order).reset_index()
    ar = ar.set_index("population").reindex(order).reset_index()
    fig, ax = plt.subplots(1, 3, figsize=(14, 4.5))
    x = np.arange(len(pop))
    ax[0].bar(x - 0.2, pop["Ho"], 0.4, label="Ho")
    ax[0].bar(x + 0.2, pop["He"], 0.4, label="He")
    ax[0].set_xticks(x); ax[0].set_xticklabels(pop["population"])
    ax[0].set_title("Heterozygosity (Set B SNPs; relative)"); ax[0].legend(frameon=False)
    ax[1].bar(ar["population"], ar["rarefied_allelic_richness"], color="#9467bd")
    n = int(ar["rarefied_to_n"].iloc[0]) if "rarefied_to_n" in ar else 0
    ax[1].set_title(f"Rarefied allelic richness (n={n})")
    for pop_name in order:
        sub = ind[ind["population"] == pop_name]
        ax[2].scatter([pop_name] * len(sub), sub["obs_het_rate"],
                      color=COLORS.get(pop_name), edgecolor="k", linewidth=0.4)
    ax[2].set_title("Individual heterozygosity"); ax[2].set_ylabel("obs het rate")
    fig.tight_layout(); fig.savefig(a.out, dpi=150)


def temporal(a):
    m = pd.read_csv(a.pi_museum, sep="\t")["PI"]
    d = pd.read_csv(a.pi_modern, sep="\t")["PI"]
    div = pd.read_csv(a.div, sep="\t").set_index("population")
    ar = pd.read_csv(a.ar, sep="\t").set_index("population")
    fig, ax = plt.subplots(1, 3, figsize=(14, 4.5))
    ax[0].violinplot([m.dropna(), d.dropna()], showmedians=True)
    ax[0].set_xticks([1, 2]); ax[0].set_xticklabels(["museum", "modern"])
    ax[0].set_title("Windowed π (50 kb)"); ax[0].set_ylabel("π")
    grps = [g for g in ["museum", "modern"] if g in div.index]
    x = np.arange(len(grps))
    ax[1].bar(x - 0.2, div.loc[grps, "Ho"], 0.4, label="Ho")
    ax[1].bar(x + 0.2, div.loc[grps, "He"], 0.4, label="He")
    ax[1].set_xticks(x); ax[1].set_xticklabels(grps)
    ax[1].set_title("Heterozygosity"); ax[1].legend(frameon=False)
    ax[2].bar(grps, ar.loc[grps, "rarefied_allelic_richness"], color="#9467bd")
    ax[2].set_title(f"Rarefied allelic richness (n={int(ar['rarefied_to_n'].iloc[0])})")
    fig.suptitle("Angle G — temporal diversity (museum vs modern); aDNA-damage caveat applies", y=1.02)
    fig.tight_layout(); fig.savefig(a.out, dpi=150, bbox_inches="tight")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("pca");        [s.add_argument(f) for f in ["--coords", "--var", "--out"]]
    s = sub.add_parser("admixture")
    for f in ["--qdir", "--fam", "--popmap", "--Ks", "--seeds", "--out-cv", "--out"]:
        s.add_argument(f)
    s = sub.add_parser("kinship")
    s.add_argument("--kin0"); s.add_argument("--cutoff", type=float); s.add_argument("--popmap"); s.add_argument("--out")
    s = sub.add_parser("diversity"); [s.add_argument(f) for f in ["--pop", "--ind", "--ar", "--out"]]
    s = sub.add_parser("temporal")
    for f in ["--pi-museum", "--pi-modern", "--div", "--ar", "--out"]:
        s.add_argument(f)
    a = p.parse_args()
    {"pca": pca, "admixture": admixture, "kinship": kinship,
     "diversity": diversity, "temporal": temporal}[a.cmd](a)


if __name__ == "__main__":
    main()
