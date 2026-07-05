#!/usr/bin/env python3
"""Summarize bcftools-roh RG records -> per-individual F_ROH swept over a length cutoff (plan §7).

Reads the RG (region) records bcftools roh emits, per chromosome, and for each individual
computes F_ROH = (total ROH length >= cutoff) / autosome length, at each ROH-length cutoff
(the wolf-side ROH knob: short ROH = ancient/background, long ROH >= ~1.5 Mb = recent
inbreeding). Sweeping the cutoff is the fragility axis — the recent-inbreeding signal (long
ROH) should stand out from the ancient background as the cutoff rises.

RG columns (bcftools roh): RG <sample> <chrom> <start> <end> <length_bp> <n_markers> <quality>.

Output (long; one row per individual x cutoff):
  IND POP min_length_mb F_ROH n_roh total_roh_mb  +  n_long/n_short/froh_long at the classifier cutoff
Writes results/tables/wolf_roh.tsv (+ .parquet). Run `--check` for a self-test.
"""
import argparse
import sys

import pandas as pd


def genome_length(lengths_path):
    tot = 0
    with open(lengths_path) as fh:
        for line in fh:
            t = line.split("\t")
            if len(t) >= 2:
                tot += int(t[1])
    return tot


def read_rg(paths):
    """{sample: [roh_length_bp, ...]} from all RG files."""
    d = {}
    for p in paths:
        with open(p) as fh:
            for line in fh:
                f = line.rstrip("\n").split("\t")
                if len(f) < 6 or f[0] != "RG":
                    continue
                d.setdefault(f[1], []).append(int(f[5]))
    return d


def summarize(roh, popmap, genome_len, cutoffs_mb, long_cut_mb):
    rows = []
    long_bp = long_cut_mb * 1_000_000
    # every sample that appears in the popmap gets rows (0 ROH -> F_ROH 0), so the table is complete
    samples = sorted(set(popmap) | set(roh))
    for s in samples:
        lens = roh.get(s, [])
        n_long = sum(1 for L in lens if L >= long_bp)
        froh_long = sum(L for L in lens if L >= long_bp) / genome_len if genome_len else float("nan")
        for cm in cutoffs_mb:
            cbp = cm * 1_000_000
            kept = [L for L in lens if L >= cbp]
            rows.append({
                "IND": s, "POP": popmap.get(s, "NA"),
                "min_length_mb": cm,
                "F_ROH": (sum(kept) / genome_len) if genome_len else float("nan"),
                "n_roh": len(kept),
                "total_roh_mb": sum(kept) / 1_000_000,
                "n_long_recent": n_long,               # ROH >= long_cut (recent inbreeding), fixed classifier
                "froh_long_recent": froh_long,
            })
    return pd.DataFrame(rows).sort_values(["min_length_mb", "POP", "IND"]).reset_index(drop=True)


def _self_check():
    roh = {"A": [3_000_000, 500_000, 100_000], "B": []}   # A: one long, one mid, one short; B: none
    popmap = {"A": "1983-1990", "B": "2007-2014"}
    g = 10_000_000
    out = summarize(roh, popmap, g, [0.1, 1.5], 1.5).set_index(["IND", "min_length_mb"])
    # A @ 0.1 Mb: all three ROH kept -> total 3.6 Mb, F_ROH 0.36
    assert abs(out.loc[("A", 0.1), "F_ROH"] - 0.36) < 1e-9 and out.loc[("A", 0.1), "n_roh"] == 3
    # A @ 1.5 Mb: only the 3 Mb ROH -> F_ROH 0.30, n_roh 1
    assert abs(out.loc[("A", 1.5), "F_ROH"] - 0.30) < 1e-9 and out.loc[("A", 1.5), "n_roh"] == 1
    # A long/recent classifier (>=1.5): 1 ROH, froh 0.30
    assert out.loc[("A", 0.1), "n_long_recent"] == 1 and abs(out.loc[("A", 0.1), "froh_long_recent"] - 0.30) < 1e-9
    # B has no ROH -> present with zeros at every cutoff
    assert out.loc[("B", 0.1), "F_ROH"] == 0.0 and out.loc[("B", 1.5), "n_roh"] == 0
    print("wolf_roh_summarize self-check: OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--rg", nargs="+")
    ap.add_argument("--lengths")
    ap.add_argument("--popmap")
    ap.add_argument("--cutoffs-mb", default="0.1,0.5,1.0,1.5,2.0")
    ap.add_argument("--long-cutoff-mb", type=float, default=1.5)
    ap.add_argument("--out-tsv")
    ap.add_argument("--out-parquet")
    a = ap.parse_args()
    if a.check:
        _self_check()
        return
    for req in ("rg", "lengths", "popmap", "out_tsv", "out_parquet"):
        if getattr(a, req) is None:
            ap.error(f"--{req.replace('_', '-')} is required")

    genome_len = genome_length(a.lengths)
    if genome_len == 0:
        sys.exit("wolf_roh_summarize: autosome length is 0 — check the contig-lengths file")
    popmap = {}
    for line in open(a.popmap):
        line = line.rstrip("\n")
        if line:
            parts = line.split("\t")
            popmap[parts[0]] = parts[1] if len(parts) > 1 else "NA"
    roh = read_rg(a.rg)
    cutoffs = [float(x) for x in a.cutoffs_mb.split(",")]
    out = summarize(roh, popmap, genome_len, cutoffs, a.long_cutoff_mb)
    out.to_csv(a.out_tsv, sep="\t", index=False)
    out.to_parquet(a.out_parquet, index=False)
    print(f"wolf_roh: {out['IND'].nunique()} individuals x {len(cutoffs)} cutoffs "
          f"(autosome length {genome_len/1e9:.2f} Gb) -> {len(out)} rows")
    for cm in cutoffs:
        sub = out[out["min_length_mb"] == cm]
        print(f"  >= {cm} Mb: mean F_ROH = {sub['F_ROH'].mean():.4f}")


if __name__ == "__main__":
    main()
