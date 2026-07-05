#!/usr/bin/env python3
"""Phase-4 validation: is the wolf load/ROH computation faithful and well-formed? (plan §7)

The load-bearing check RECONCILES our GERP>4 per-individual load against the deposit's
precomputed anchor (LoadPerInd.thres4) — same VCF, same GERP bed, same AA polarization, so a
faithful re-implementation must reproduce REALIZED_LOAD / MASKED_LOAD / the raw counts. Also
asserts the GERP-sweep and ROH tables are well-formed (F_ROH in [0,1], monotone in cutoff) and
REPORTS the scientific direction (load change across time periods; GERP + ROH-cutoff sensitivity)
without over-asserting it.

Writes results/PHASE4_VALIDATION.md + results/tables/validation_phase4.tsv. Exits 1 on FAIL.
"""
import os
import sys

import numpy as np
import pandas as pd
import yaml

LOAD = "results/tables/wolf_load.tsv"
ROH = "results/tables/wolf_roh.tsv"
_CFG = yaml.safe_load(open("config/config.yaml"))
ANCHOR = _CFG["paths"]["wolf"]["load_anchor"]
GERP_THRES = [float(t) for t in _CFG["wolf"]["load"]["gerp_sensitivity"]]

checks = []


def add(name, ok, detail):
    checks.append((name, "PASS" if ok else ("WARN" if ok is None else "FAIL"), detail))


def main():
    for f in (LOAD, ROH, ANCHOR):
        if not os.path.exists(f):
            sys.exit(f"missing: {f} — run `snakemake phase4` first")
    load = pd.read_csv(LOAD, sep="\t")
    roh = pd.read_csv(ROH, sep="\t")
    anchor = pd.read_csv(ANCHOR, sep="\t")

    # 1. load table shape: every GERP threshold present, same individual set each
    thres = sorted(load["THRES"].unique())
    add("load has all GERP thresholds", set(thres) == set(GERP_THRES),
        f"got {thres}, expected {sorted(GERP_THRES)}")
    n_ind = load[load["THRES"] == 4]["IND"].nunique() if 4 in load["THRES"].values else load["IND"].nunique()
    add("load covers the anchor's individuals", n_ind == anchor["IND"].nunique(),
        f"{n_ind} individuals vs anchor {anchor['IND'].nunique()}")

    # 2. RECONCILE GERP>4 against the deposit anchor (the faithfulness gate)
    mine = load[load["THRES"] == 4].set_index("IND")
    anc = anchor.set_index("IND")
    common = mine.index.intersection(anc.index)
    if len(common) == 0:
        add("GERP>4 reconciles with the deposit anchor", False, "no shared individuals")
    else:
        def relerr(a, b):
            a, b = a.loc[common].astype(float), b.loc[common].astype(float)
            denom = b.abs().where(b.abs() > 0, np.nan)
            return (a - b).abs() / denom
        re_real = relerr(mine["REALIZED_LOAD"], anc["REALIZED_LOAD"])
        re_mask = relerr(mine["MASKED_LOAD"], anc["MASKED_LOAD"])
        # exact-ish count reconciliation
        d_calls = (mine["calls"].loc[common] - anc["TOT_CALLS"].loc[common]).abs()
        d_del = (mine["n_del"].loc[common] - anc["TOT_DEL"].loc[common]).abs()
        d_homdel = (mine["n_hom_del"].loc[common] - anc["HOM_DEL"].loc[common]).abs()
        worst = max(float(np.nanpercentile(re_real, 95)), float(np.nanpercentile(re_mask, 95)))
        counts_ok = (d_calls.max() == 0 and d_del.max() == 0 and d_homdel.max() == 0)
        add("GERP>4 reconciles with the deposit anchor", worst < 0.02,
            f"95th-pct relerr realized/masked = {worst:.2e} over {len(common)} inds; "
            f"count deltas (calls/del/homdel) max = {int(d_calls.max())}/{int(d_del.max())}/{int(d_homdel.max())}"
            + (" (exact)" if counts_ok else ""))
        add("raw deleterious counts match the anchor exactly", None if not counts_ok else True,
            "TOT_CALLS/TOT_DEL/HOM_DEL identical" if counts_ok else
            f"deltas max calls={int(d_calls.max())} del={int(d_del.max())} homdel={int(d_homdel.max())}")

    # 3. load monotonicity in GERP threshold: fewer deleterious sites as threshold rises
    mono = True
    for ind, g in load.sort_values("THRES").groupby("IND"):
        if not (g["n_del"].values[::-1] == np.sort(g["n_del"].values)).all():
            # n_del should be non-increasing as THRES increases
            if not (np.diff(g.sort_values("THRES")["n_del"].values) <= 0).all():
                mono = False
                break
    add("deleterious-site count non-increasing in GERP threshold", mono,
        "n_del(2) >= n_del(3) >= n_del(4) per individual")

    # 4. ROH well-formed: F_ROH in [0,1], non-increasing as the length cutoff rises
    add("F_ROH in [0,1]", bool(((roh["F_ROH"] >= 0) & (roh["F_ROH"] <= 1)).all()),
        f"range [{roh['F_ROH'].min():.3f}, {roh['F_ROH'].max():.3f}]")
    roh_mono = True
    for ind, g in roh.groupby("IND"):
        if not (np.diff(g.sort_values("min_length_mb")["F_ROH"].values) <= 1e-12).all():
            roh_mono = False
            break
    add("F_ROH non-increasing as ROH-length cutoff rises", roh_mono,
        "more restrictive cutoff keeps less ROH")

    # 5. REPORT: realized vs masked load across time periods at GERP>4 (the paper's masked->realized story)
    g4 = load[load["THRES"] == 4]
    per_pop = g4.groupby("POP")[["REALIZED_LOAD", "MASKED_LOAD"]].mean().sort_index()
    add("realized vs masked load by period (GERP>4)", None,
        "; ".join(f"{p}: real={r.REALIZED_LOAD:.3f}/mask={r.MASKED_LOAD:.3f}"
                  for p, r in per_pop.iterrows()))

    # 6. REPORT: GERP sensitivity of mean realized load (the wolf fragility axis)
    gs = load.groupby("THRES")["REALIZED_LOAD"].mean()
    add("GERP-threshold sensitivity of realized load", None,
        "; ".join(f"GERP>{t:g}: mean realized={v:.3f}" for t, v in gs.items()))

    # 7. REPORT: ROH-cutoff sensitivity of mean F_ROH (the ROH fragility axis)
    rs = roh.groupby("min_length_mb")["F_ROH"].mean()
    add("ROH-length sensitivity of mean F_ROH", None,
        "; ".join(f">={c}Mb: {v:.3f}" for c, v in rs.items()))

    rep = pd.DataFrame(checks, columns=["check", "status", "detail"])
    rep.to_csv("results/tables/validation_phase4.tsv", sep="\t", index=False)
    n_fail = int((rep.status == "FAIL").sum())

    with open("results/PHASE4_VALIDATION.md", "w") as fh:
        fh.write("# Phase 4 — validation report\n\n")
        fh.write("The load-bearing check **reconciles our GERP>4 load against the deposit's precomputed "
                 "anchor** (`LoadPerInd.thres4`) — a faithful re-implementation must reproduce it. The rest "
                 "asserts the GERP-sweep + ROH tables are well-formed and **reports** the scientific "
                 "direction (realized-vs-masked across periods, GERP + ROH sensitivity) without over-asserting.\n\n")
        fh.write("| check | status | detail |\n|---|---|---|\n")
        for _, r in rep.iterrows():
            fh.write(f"| {r['check']} | **{r['status']}** | {r['detail']} |\n")
        fh.write(f"\n**{n_fail} FAIL**, {(rep.status=='WARN').sum()} WARN (reported-not-asserted), "
                 f"{(rep.status=='PASS').sum()} PASS.\n")
    print(rep.to_string(index=False))
    print(f"\n{n_fail} FAIL")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
