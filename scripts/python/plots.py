#!/usr/bin/env python3
"""Phase-1/2 static figures. Subcommands: pca | admixture | kinship | diversity | temporal | gone2 | cube.

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


def gone2(a):
    """GONE2 recent-N_e trajectory — CONTEXT ONLY (plan §5). Caveats are ON the figure."""
    df = pd.read_csv(a.ne, sep="\t")   # normalized: generation, Ne
    if getattr(a, "max_gen", None):    # cutoff in GENERATIONS (rows are non-contiguous binned gens)
        df = df[df["generation"] <= float(a.max_gen)]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(df["generation"], df["Ne"], color="#1f77b4", lw=2, marker="o", ms=3)
    ax.set_yscale("log")
    ax.set_xlabel("Generations before present (1 = most recent)")
    ax.set_ylabel("N_e (diploids)")
    ax.set_title("GONE2 recent N_e trajectory — CONTEXT ONLY (not the GBF badge)\n"
                 "all 22 birds, -x metapopulation, -g 0; borrowed constant rate 3 cM/Mb "
                 "(peafowl has no\ngenetic map); microchromosomes <20 cM dropped; "
                 "recent-past ≠ contemporary N_e; thin n", fontsize=9)
    fig.tight_layout(); fig.savefig(a.out, dpi=150, bbox_inches="tight")


def cube(a):
    """Static fragility view of the results cube: per-population N_e across presets, with the
    N_e=500 line and the pooled (Wahlund) contrast. Phase 3 makes the interactive version."""
    df = pd.read_parquet(a.cube)
    presets = ["lenient", "standard", "strict"]
    xmap = {p: i for i, p in enumerate(presets)}
    perpop = df[df.structure_mode == "per_population"]
    pops = _order(perpop["population"])
    fig, ax = plt.subplots(figsize=(9, 5.5))
    # display cap for unbounded (inf) upper CIs -> open arrows
    finite_hi = df["ci_high"].replace([np.inf], np.nan).dropna()
    cap = (finite_hi.max() if len(finite_hi) else 1000) * 3
    for k, pop in enumerate(pops):
        sub = perpop[perpop.population == pop].set_index("filter_preset").reindex(presets)
        xs = np.array([xmap[p] for p in presets]) + (k - len(pops) / 2) * 0.06
        ys = sub["ne_point"].to_numpy(float)
        lo = sub["ci_low"].to_numpy(float)
        hi = sub["ci_high"].to_numpy(float)
        inf_up = np.isinf(hi)
        hi_disp = np.where(inf_up, cap, hi)
        yerr = np.vstack([np.clip(ys - lo, 0, None), np.clip(hi_disp - ys, 0, None)])
        ax.errorbar(xs, ys, yerr=yerr, fmt="o", color=COLORS.get(pop, f"C{k}"),
                    label=pop, capsize=3, uplims=inf_up, lw=1.2)
    pooled = df[df.structure_mode == "pooled"].set_index("filter_preset").reindex(presets)
    ax.plot(range(len(presets)), pooled["ne_point"], "kx--", label="pooled (Wahlund-biased low)")
    thr = float(getattr(a, "threshold", None) or 500)   # GBF N_e threshold (config-driven via the rule)
    ax.axhline(thr, color="red", ls=":", lw=1.5, label=f"N_e = {thr:.0f} (GBF)")
    ax.set_yscale("log"); ax.set_xticks(range(len(presets))); ax.set_xticklabels(presets)
    ax.set_xlabel("filtering preset"); ax.set_ylabel("contemporary N_e (cross-chromosome)")
    ax.set_title("Fragility cube — currentNe2 N_e (90% CI; ↑ = unbounded). "
                 "n = 7/10/5 -> wide CIs by design", fontsize=10)
    ax.legend(frameon=False, fontsize=8, ncol=2)
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
    s = sub.add_parser("gone2"); s.add_argument("--ne"); s.add_argument("--out"); s.add_argument("--max-gen")
    s = sub.add_parser("cube");  s.add_argument("--cube"); s.add_argument("--out"); s.add_argument("--threshold")
    a = p.parse_args()
    {"pca": pca, "admixture": admixture, "kinship": kinship,
     "diversity": diversity, "temporal": temporal, "gone2": gone2, "cube": cube}[a.cmd](a)


if __name__ == "__main__":
    main()
