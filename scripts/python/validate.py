#!/usr/bin/env python3
"""Phase-1 validation: do our re-derived numbers reproduce the deposit / paper?

Checks only what the DEPOSITED callsets can support (plan §4). Numbers from the
undeposited 31-sample raw set are out of reach — we say so rather than fake them.
Writes results/PHASE1_VALIDATION.md (human) + results/tables/validation_report.tsv.
"""
import sys
import numpy as np
import pandas as pd

T = "results/tables"
# Anchors the deposited data CAN support:
HANDOFF_POSTMAC = {"lenient": 1_044_447, "standard": 419_616, "strict": 29_851}
FROZEN_NEUTRAL = 790_705            # authors' deposited unlinked-neutral Set A
TOL = 0.02                          # post-MAC tolerance: norm -m -any splits multiallelics (+~0.2-1%)

checks = []   # (name, status, detail)


def add(name, ok, detail):
    checks.append((name, "PASS" if ok else ("WARN" if ok is None else "FAIL"), detail))


def main():
    counts = pd.read_csv(f"{T}/qc_snp_counts.tsv", sep="\t")

    # 1. frozen neutral reference exact
    fn = int(counts.query("callset=='frozen_neutral_ref'")["snps"].iloc[0])
    add("frozen_neutral_ref == 790,705", fn == FROZEN_NEUTRAL, f"got {fn:,}")

    # 2. per-preset post-MAC counts vs HANDOFF (within multiallelic-split tolerance)
    pm = counts.query("callset=='setA_postMAC'").set_index("preset")["snps"]
    for preset, target in HANDOFF_POSTMAC.items():
        got = int(pm[preset]); rel = abs(got - target) / target
        add(f"setA postMAC {preset} ~= {target:,}", rel <= TOL,
            f"got {got:,} ({rel*100:+.2f}% vs HANDOFF; norm-split margin)")

    # 3. filtering knob bites (>=20x spread lenient:strict)
    spread = int(pm["lenient"]) / int(pm["strict"])
    add("filter knob spread >= 20x", spread >= 20, f"{spread:.0f}x (lenient/strict post-MAC)")

    # 4. structure: ADMIXTURE best K (expect 3 sampled populations)
    cv = pd.read_csv(f"{T}/admixture_cv.tsv", sep="\t")
    meancv = cv.groupby("K")["cv_error"].mean()
    bestK = int(meancv.idxmin())
    add("ADMIXTURE best K", None, f"min mean-CV at K={bestK} (3 pops sampled; CV often favours fewer)")

    # 5. PCA separates the 3 populations (centroid gap > within-pop spread)
    pca = pd.read_csv(f"{T}/pca_coords.tsv", sep="\t")
    cent = pca.groupby("population")[["PC1", "PC2"]].mean()
    within = pca.groupby("population").apply(
        lambda d: np.sqrt(((d[["PC1", "PC2"]] - d[["PC1", "PC2"]].mean()) ** 2).sum(1)).mean())
    pops = cent.index.tolist()
    gaps = [np.hypot(*(cent.loc[i] - cent.loc[j]).values) for i in pops for j in pops if i < j]
    sep = min(gaps) > max(within)
    add("PCA separates 3 populations", sep,
        f"min between-centroid gap {min(gaps):.2f} vs max within-spread {max(within):.2f}")

    # 6. modern diversity ordering (small Thai pop expected lowest)
    div = pd.read_csv(f"{T}/diversity_perpop.tsv", sep="\t").set_index("population")
    ar = pd.read_csv(f"{T}/allelic_richness_modern.tsv", sep="\t").set_index("population")
    lo_he = div["He"].idxmin(); lo_ar = ar["rarefied_allelic_richness"].idxmin()
    add("Thailand lowest diversity (He & AR)", lo_he == "Thailand" and lo_ar == "Thailand",
        f"lowest He={lo_he}, lowest AR={lo_ar}")

    # 7. temporal angle G — report direction (erosion hypothesis: museum >= modern)
    tpi = pd.read_csv(f"{T}/temporal_pi_summary.tsv", sep="\t").set_index("group")
    tdiv = pd.read_csv(f"{T}/temporal_diversity.tsv", sep="\t").set_index("population")
    tar = pd.read_csv(f"{T}/temporal_allelic_richness.tsv", sep="\t").set_index("population")
    mus_pi, mod_pi = tpi.loc["museum", "median_pi"], tpi.loc["modern", "median_pi"]
    direction = "museum > modern (consistent w/ erosion)" if mus_pi > mod_pi else "modern >= museum"
    add("temporal π direction", None,
        f"median π museum={mus_pi:.3g} vs modern={mod_pi:.3g} -> {direction}; "
        f"aDNA deamination can inflate museum diversity (caveat)")
    add("temporal He/AR direction", None,
        f"He museum={tdiv.loc['museum','He']:.3g}/modern={tdiv.loc['modern','He']:.3g}; "
        f"AR museum={tar.loc['museum','rarefied_allelic_richness']:.3g}/"
        f"modern={tar.loc['modern','rarefied_allelic_richness']:.3g}")

    # ── write outputs ──
    rep = pd.DataFrame(checks, columns=["check", "status", "detail"])
    rep.to_csv(f"{T}/validation_report.tsv", sep="\t", index=False)

    n_fail = (rep.status == "FAIL").sum()
    with open("results/PHASE1_VALIDATION.md", "w") as fh:
        fh.write("# Phase 1 — validation report\n\n")
        fh.write("Reproduces only what the **deposited** callsets support (plan §4). "
                 "The undeposited 31-sample raw numbers are out of reach — not faked.\n\n")
        fh.write("| check | status | detail |\n|---|---|---|\n")
        for _, r in rep.iterrows():
            fh.write(f"| {r['check']} | **{r['status']}** | {r['detail']} |\n")
        fh.write(f"\n**{n_fail} FAIL**, "
                 f"{(rep.status=='WARN').sum()} WARN (reported-not-asserted), "
                 f"{(rep.status=='PASS').sum()} PASS.\n")
        fh.write("\n**Out of reach / caveats:** exact Dong et al. 2021 π values are not "
                 "embedded here (we reproduce the *contrast direction*, not their decimals); "
                 "Ho/He are SNP-based relative measures, not genome-wide; temporal contrast is "
                 "geographically narrow (modern mostly Thai s_*) and the deposited comparative "
                 "uses PE125_220 where the authors' raw script used s_9_2.\n")
    print(rep.to_string(index=False))
    print(f"\n{n_fail} FAIL")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
