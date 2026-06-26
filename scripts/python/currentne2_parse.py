#!/usr/bin/env python3
"""Parse one currentNe2 OUTPUT file into a single tidy results-cube row (plan §5).

currentNe2, given a genome size and a multi-chromosome VCF, writes TWO estimates:
  1. "Ne estimation by integration over the whole genome"   (ALL SNP pairs)
  2. "Ne estimation based only on LD between chromosomes"    (cross-chromosome pairs)

(2) is the headline. LD-pruning would have destroyed exactly the signal (2) reads, and
the across-chromosome estimate is the cleaner one (no within-chromosome physical-distance
assumptions) — this is *why* Phase 2 feeds the UN-pruned Set A + genome size = 32 Morgans
(plan §5). (1) is kept only as a fallback when (2) does not converge.

CI stored = the **90%** interval (the wider of the two currentNe2 emits; it labels them
50% and 90%, not 95% — the app/report say 90%). Unbounded / astronomically-large upper
bounds at n = 7/10/5 are stored as `inf` (plan §5: "stored as inf").

Output: a one-row TSV (with header) carrying the cube schema for this cell.
"""
import argparse
import math

# currentNe2 caps Ne below 1e8; any CI bound at/above this is effectively unbounded for a
# peafowl population. Mark as inf rather than print a meaningless 9-digit number.
INF_THRESHOLD = 1e7

XCHROM_HDR = "Ne estimation based only on LD between chromosomes"
WHOLE_HDR = "Ne estimation by integration over the whole genome"

# full-sib line; cross-chromosome block suffixes it "(c=0.5):", whole-genome has no suffix.
K_PREFIX = "# Estimated Number of full siblings that a random individuals has in the population"
N_IND_LABEL = "# Total number of individuals in the input file:"


def _to_float(s):
    """currentNe2 value -> float; 'inf'/'nan'/huge -> inf/nan."""
    if s is None:
        return math.nan
    s = s.strip()
    try:
        v = float(s)
    except ValueError:
        return math.nan
    if not math.isfinite(v) or abs(v) >= INF_THRESHOLD:
        return math.inf
    return v


def _block(lines, header):
    """Lines of the estimate block starting at `header`, up to the next estimate/end."""
    start = None
    for i, ln in enumerate(lines):
        if header in ln:
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("# Ne estimation") or "(end of output)" in lines[j]:
            end = j
            break
    return lines[start:end]


def _value_after(block, label):
    """The value line immediately following a `# label:` line within a block."""
    for i, ln in enumerate(block):
        if ln.strip() == label and i + 1 < len(block):
            return block[i + 1]
    return None


def _value_startswith(block, prefix):
    """The value line immediately following the first line that starts with `prefix`."""
    if block is None:
        return None
    for i, ln in enumerate(block):
        if ln.strip().startswith(prefix) and i + 1 < len(block):
            return block[i + 1]
    return None


def _estimate(block):
    """(point, ci_low_90, ci_high_90) from an estimate block, or (nan, nan, nan)."""
    if block is None:
        return math.nan, math.nan, math.nan
    point = _to_float(_value_after(block, "# Ne point estimate:"))
    lo = _to_float(_value_after(block, "# Lower limit of 90% CI:"))
    hi = _to_float(_value_after(block, "# Upper limit of 90% CI:"))
    return point, lo, hi


def gbf_state(point, ci_low, ci_high, threshold):
    """pass / fail / indeterminate vs the N_e>threshold indicator (plan §5).

    Verdict read off the point estimate; if the CI straddles the threshold (or no estimate
    converged) it is `indeterminate` — that band IS the fragility story, not a defect.
    """
    if math.isnan(point):
        return "indeterminate"          # no convergence -> cannot decide
    lo = -math.inf if math.isnan(ci_low) else ci_low
    hi = math.inf if math.isnan(ci_high) else ci_high
    if lo <= threshold <= hi:
        return "indeterminate"          # CI straddles the threshold
    return "pass" if point > threshold else "fail"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, help="currentNe2 OUTPUT file")
    p.add_argument("--preset", required=True)
    p.add_argument("--structure-mode", required=True)
    p.add_argument("--population", required=True)
    p.add_argument("--ne-threshold", type=float, default=500.0)
    p.add_argument("--out", required=True)
    a = p.parse_args()

    with open(a.output) as fh:
        lines = fh.read().splitlines()

    # headline = cross-chromosome; fall back to whole-genome only if it didn't converge
    block = _block(lines, XCHROM_HDR)
    point, lo, hi = _estimate(block)
    basis = "cross_chromosome"
    if math.isnan(point):
        block = _block(lines, WHOLE_HDR)
        point, lo, hi = _estimate(block)
        basis = "whole_genome"
    if math.isnan(point):
        basis = "none"          # neither block converged -> NOT a whole-genome estimate

    n_snps = _value_after(lines, "# Number of SNPs included in the analysis (only polymorphic and "
                                 "with less than 20% missing data):")
    n_snps = int(float(n_snps)) if n_snps and n_snps.strip().replace(".", "").isdigit() else -1

    # full-sib count from the SAME block the headline estimate came from (a whole-file exact
    # match always returned the whole-genome value, even for a cross-chromosome headline).
    k = math.nan
    if basis != "none":
        try:
            k = float(_value_startswith(block, K_PREFIX))
        except (TypeError, ValueError):
            k = math.nan

    # n_ind = what currentNe2 actually analyzed (authoritative), not the popmap keep-list count:
    # bcftools --force-samples silently proceeds when a keep-list sample is absent from the VCF.
    try:
        n_ind = int(float(_value_after(lines, N_IND_LABEL)))
    except (TypeError, ValueError):
        n_ind = -1

    state = gbf_state(point, lo, hi, a.ne_threshold)

    cols = ["filter_preset", "structure_mode", "population", "ne_method",
            "ne_point", "ci_low", "ci_high", "n_ind", "n_snps", "k", "ne_basis", "gbf_state"]
    row = [a.preset, a.structure_mode, a.population, "currentNe2",
           point, lo, hi, n_ind, n_snps, k, basis, state]
    with open(a.out, "w") as fh:
        fh.write("\t".join(cols) + "\n")
        fh.write("\t".join("" if (isinstance(v, float) and math.isnan(v)) else
                           ("inf" if v == math.inf else str(v)) for v in row) + "\n")
    print(f"{a.preset} {a.structure_mode} {a.population}: Ne={point} "
          f"CI90=[{lo},{hi}] basis={basis} -> {state}")


if __name__ == "__main__":
    main()
