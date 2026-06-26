#!/usr/bin/env python3
"""Normalize a GONE2 trajectory into a clean 2-column TSV: generation<TAB>Ne (context only, §5).

GONE2 writes two layouts depending on -x:
  * panmictic  (_GONE2_Ne):      header 'Generation  Ne_diploids', one row per generation.
  * metapop -x (_GONE2_Ne_mix):  a comment header (Fst, migration, n_subpops) then a table
                                 'Rec_rate_bin generation N_T_metapop Ne_metapop d²_metapop'.
For -x we take N_T_metapop (the total metapopulation N_e = the species-level trajectory).
"""
import argparse


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--infile", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    lines = open(a.infile).read().splitlines()
    rows = []
    mix = any("Rec_rate_bin" in ln for ln in lines)

    if mix:
        start = next(i for i, ln in enumerate(lines) if "Rec_rate_bin" in ln) + 1
        for ln in lines[start:]:
            if ln.startswith("#") or not ln.strip():
                continue
            parts = ln.split("\t")
            if len(parts) >= 3:
                rows.append((parts[1], parts[2]))     # generation, N_T_metapop
    else:
        for ln in lines:
            if ln.startswith(("Generation", "#")) or not ln.strip():
                continue
            parts = ln.split("\t")
            if len(parts) >= 2:
                rows.append((parts[0], parts[1]))     # generation, Ne_diploids

    with open(a.out, "w") as fh:
        fh.write("generation\tNe\n")
        for g, n in rows:
            fh.write(f"{g}\t{n}\n")
    print(f"{len(rows)} generations -> {a.out} "
          f"({'metapopulation N_T (-x)' if mix else 'panmictic'})")


if __name__ == "__main__":
    main()
