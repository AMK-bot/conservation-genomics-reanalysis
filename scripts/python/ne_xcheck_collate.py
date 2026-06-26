#!/usr/bin/env python3
"""Collate currentNe2 -x metapopulation cross-check outputs into one report table (plan §5).

The -x run estimates N_T (metapopulation sum of subpop N_e), Fst and migration rate assuming
equal-size subpopulations. It is a REPORT cross-check on the structure-bias direction, never a
cube input. Robust to non-convergence (likely at small, strongly-structured n — itself honest).
"""
import argparse
import math


def value_after(lines, substr):
    """The value line immediately after the first line containing `substr`."""
    for i, ln in enumerate(lines):
        if substr in ln and i + 1 < len(lines):
            return lines[i + 1].strip()
    return None


def f(s):
    try:
        v = float(s)
    except (TypeError, ValueError):
        return math.nan
    return math.inf if abs(v) >= 1e7 else v


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("raws", nargs="+")
    a = p.parse_args()

    rows = []
    for path in a.raws:
        preset = path.split("/")[-1].split(".")[0]
        lines = open(path).read().splitlines()
        txt = "\n".join(lines)
        converged = "N_T of the metapopulation" in txt
        if converged:
            note = "converged (no CIs in genome-size mode)" if "No CIs are calculated" in txt else "converged"
        elif "no signs of population subdivision" in txt:
            note = "no LD subdivision signal"
        else:
            note = "no Fst convergence"
        rows.append((
            preset,
            f(value_after(lines, "N_T of the metapopulation")),
            f(value_after(lines, "Lower 90% limit of the N_T")),
            f(value_after(lines, "Upper 90% limit of the N_T")),
            f(value_after(lines, "Fst (subpopulation differentiation)")),
            f(value_after(lines, "# Migration rate:")),
            f(value_after(lines, "Number of subpopulations of equal size")),
            note,
        ))

    cols = ["preset", "NeT", "NeT_lo90", "NeT_hi90", "Fst", "migration", "n_subpops", "note"]
    with open(a.out, "w") as fh:
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join(
                "" if (isinstance(x, float) and math.isnan(x)) else
                ("inf" if x == math.inf else str(x)) for x in r) + "\n")
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
