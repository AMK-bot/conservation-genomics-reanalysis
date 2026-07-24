#!/usr/bin/env python3
"""Merge per-chromosome wolf GERP-load raw counts -> genome-wide per-individual load (plan §7).

Sums the raw counts from wolf_gerp_load.py across all chromosomes by (IND, POP, THRES),
then computes the three load measures exactly as Smeds & Ellegren 2022:
    RELATIVE_LOAD = sum / tot_der          (GERP-weighted derived-allele proxy fraction)
    REALIZED_LOAD = hom_del_sum / calls    (homozygous-derived GERP-weighted proxy)
    MASKED_LOAD   = het_del_sum / calls    (heterozygous-derived GERP-weighted proxy)

These inherited measure names reproduce the source analysis; they do not establish
expression, phenotypic harm, or a causal masked-to-realized conversion.

Writes results/tables/wolf_load.tsv (+ .parquet). The THRES column IS the wolf-side
fragility axis (GERP 2/3/4): at THRES=4 this reproduces the deposit's LoadPerInd.thres4.
"""
import argparse
import sys

import pandas as pd

RAW_COLS = ["sum", "hom_del_sum", "het_del_sum", "tot_der", "hom_der",
            "n_del", "n_hom_del", "calls", "miss"]


def merge(paths):
    frames = [pd.read_csv(p, sep="\t") for p in paths]
    df = pd.concat(frames, ignore_index=True)
    agg = df.groupby(["IND", "POP", "THRES"], as_index=False)[RAW_COLS].sum()
    # per-individual load measures (guard div-by-zero the way upstream does: NA if no derived)
    agg["RELATIVE_LOAD"] = agg["sum"] / agg["tot_der"].where(agg["tot_der"] != 0)
    agg["REALIZED_LOAD"] = agg["hom_del_sum"] / agg["calls"].where(agg["calls"] != 0)
    agg["MASKED_LOAD"] = agg["het_del_sum"] / agg["calls"].where(agg["calls"] != 0)
    cols = ["IND", "POP", "THRES", "RELATIVE_LOAD", "REALIZED_LOAD", "MASKED_LOAD",
            "sum", "hom_del_sum", "het_del_sum", "tot_der", "hom_der",
            "n_del", "n_hom_del", "calls", "miss"]
    return agg[cols].sort_values(["THRES", "POP", "IND"]).reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inputs", nargs="+", required=True, help="per-chromosome raw-count TSVs")
    ap.add_argument("--out-tsv", required=True)
    ap.add_argument("--out-parquet", required=True)
    a = ap.parse_args()

    out = merge(a.inputs)
    if out.empty:
        sys.exit("wolf_load_merge: empty result — no per-chromosome inputs had rows")
    out.to_csv(a.out_tsv, sep="\t", index=False)
    out.to_parquet(a.out_parquet, index=False)
    n_ind = out["IND"].nunique()
    thres = sorted(out["THRES"].unique())
    print(f"wolf_load: {n_ind} individuals x {len(thres)} GERP thresholds {thres} "
          f"-> {len(out)} rows ({a.out_tsv})")
    # quick population-mean realized load per threshold (the headline the app plots)
    for t in thres:
        sub = out[out["THRES"] == t]
        print(f"  GERP>{t:g}: mean realized={sub['REALIZED_LOAD'].mean():.4f} "
              f"masked={sub['MASKED_LOAD'].mean():.4f}")


if __name__ == "__main__":
    main()
