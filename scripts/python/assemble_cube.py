#!/usr/bin/env python3
"""Concatenate per-cell currentNe2 rows into the results cube (plan §5).

The cube is long/tidy: one row per (filter_preset x structure_mode x population) estimate.
Pooled rows carry population = ALL. The GBF fraction (Phase 3) reads per_population rows
only; pooled rows are the structure-bias (Wahlund) contrast, never a GBF input.

Writes results_cube.parquet (the app/Phase-3 backend) + a .csv mirror for eyeballing.
"""
import argparse
import pandas as pd

NUMERIC = ["ne_point", "ci_low", "ci_high", "k"]   # "inf" -> inf, "" -> NaN


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cells", nargs="+", required=True)
    p.add_argument("--out-parquet", required=True)
    p.add_argument("--out-csv", required=True)
    a = p.parse_args()

    cube = pd.concat([pd.read_csv(f, sep="\t") for f in a.cells], ignore_index=True)
    for c in NUMERIC:
        cube[c] = pd.to_numeric(cube[c], errors="coerce")   # parses 'inf'; '' -> NaN
    cube = (cube.sort_values(["filter_preset", "structure_mode", "population"])
                .reset_index(drop=True))

    cube.to_parquet(a.out_parquet, index=False)
    cube.to_csv(a.out_csv, sep="\t", index=False)

    print(cube.to_string(index=False))
    npp = (cube.structure_mode == "per_population").sum()
    print(f"\n{len(cube)} rows ({npp} per_population + {len(cube) - npp} pooled) -> {a.out_parquet}")


if __name__ == "__main__":
    main()
