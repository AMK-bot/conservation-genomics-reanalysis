#!/usr/bin/env python3
"""Per-chromosome GERP genetic-load accumulator for the wolf chapter (plan §7).

Faithful re-implementation of Smeds & Ellegren 2022's `gerp_load_polarized.py`
(github.com/linneas/wolf-deleterious), extended to accumulate MULTIPLE GERP
thresholds in a single VCF pass so the cube's GERP-sensitivity axis (2/3/4) — the
wolf-side fragility knob — comes from one stream instead of three.

Streamed input on stdin (one line per site), produced by:
    bcftools query -r <chr> -f '%CHROM\\t%POS\\t%REF\\t%ALT\\t%INFO/AA[\\t%GT]\\n' <allSNPs.vcf.gz>
i.e. fields:  CHROM  POS  REF  ALT  AA  GT_1 ... GT_n   (n = 211 samples, VCF order)
plus the GERP bed slice for this chromosome (RS conservation score in column 5,
keyed by the bed END coordinate == 1-based VCF POS, exactly as upstream).

Derived allele = the non-ancestral allele (AA vs REF/ALT). A site is 'deleterious'
at threshold t only if its GERP RS > t. Per individual we accumulate, in ONE pass:
  threshold-independent : tot_der, hom_der, calls, miss
  per threshold t       : n_del, n_hom_del, and the GERP-weighted
                          sum / hom_del_sum / het_del_sum
Final loads (RELATIVE = sum/tot_der, REALIZED = hom_del_sum/calls,
MASKED = het_del_sum/calls) are computed by wolf_load_merge.py AFTER summing the
per-chromosome raw counts — so the genome-wide result is exact and 8 GB-safe.

Output (long; one row per individual x threshold):
  IND POP THRES sum hom_del_sum het_del_sum tot_der hom_der n_del n_hom_del calls miss

Run `--check` for a self-test (no files needed).
"""
import argparse
import re
import sys

_SPLIT = re.compile(r"[/|]")


def load_gerp(path):
    """{ 1-based POS (bed END, col3) -> GERP RS score (col5) } for one chromosome."""
    g = {}
    with open(path) as fh:
        for line in fh:
            t = line.rstrip("\n").split("\t")
            if len(t) < 5:
                continue
            g[int(t[2])] = float(t[4])
    return g


def _new_acc(samples, thres):
    ti = {s: {"tot_der": 0, "hom_der": 0, "calls": 0, "miss": 0} for s in samples}
    td = {s: {t: {"sum": 0.0, "hom_del_sum": 0.0, "het_del_sum": 0.0,
                  "n_del": 0, "n_hom_del": 0} for t in thres} for s in samples}
    return ti, td


def process(stream, samples, gerp, thres, ti, td):
    """Accumulate load counts from a bcftools-query stream into ti/td (in place)."""
    for line in stream:
        f = line.rstrip("\n").split("\t")
        if len(f) < 6:
            continue
        pos = int(f[1])
        g = gerp.get(pos)
        if g is None:                       # no GERP score here -> skip (upstream guard)
            continue
        ref, alt, aa = f[2].upper(), f[3].upper(), f[4].upper()
        if aa == ref:
            der = "alt"
        elif aa == alt:
            der = "ref"
        else:                               # AA neither ref nor alt (or '.') -> skip
            continue
        gts = f[5:]
        for s, gt in zip(samples, gts):
            al = _SPLIT.split(gt.split(":")[0])
            if len(al) < 2 or "." in al or any(a not in ("0", "1") for a in al):
                ti[s]["miss"] += 1          # missing or (rare) multiallelic -> not a call
                continue
            nalt = al.count("1")
            acc = ti[s]
            acc["calls"] += 1
            nder = (2 - nalt) if der == "ref" else nalt   # number of DERIVED copies
            if nder == 2:
                acc["tot_der"] += 2
                acc["hom_der"] += 2
            elif nder == 1:
                acc["tot_der"] += 1
            if nder > 0:
                for t in thres:
                    if g > t:
                        d = td[s][t]
                        if nder == 2:
                            d["n_del"] += 2
                            d["n_hom_del"] += 2
                            d["sum"] += 2 * g
                            d["hom_del_sum"] += 2 * g
                        else:               # het: one derived copy, masked
                            d["n_del"] += 1
                            d["sum"] += g
                            d["het_del_sum"] += g
    return ti, td


def write(out, samples, popmap, thres, ti, td):
    with open(out, "w") as fh:
        fh.write("IND\tPOP\tTHRES\tsum\thom_del_sum\thet_del_sum\ttot_der\t"
                 "hom_der\tn_del\tn_hom_del\tcalls\tmiss\n")
        for s in samples:
            p = popmap.get(s, "NA")
            ii = ti[s]
            for t in thres:
                d = td[s][t]
                fh.write(f"{s}\t{p}\t{t:g}\t{d['sum']}\t{d['hom_del_sum']}\t{d['het_del_sum']}\t"
                         f"{ii['tot_der']}\t{ii['hom_der']}\t{d['n_del']}\t{d['n_hom_del']}\t"
                         f"{ii['calls']}\t{ii['miss']}\n")


def _self_check():
    """Assert the polarized counting on a hand-built stream matches upstream semantics."""
    samples = ["A", "B"]
    thres = [2.0, 4.0]
    # site1 POS100 REF=G ALT=A AA=G (der=alt); gerp 5 (>4 and >2)
    #   A = 1/1 (2 derived, hom del at both thres); B = 0/1 (1 derived, masked)
    # site2 POS200 REF=C ALT=T AA=T (der=ref); gerp 3 (>2 only)
    #   A = 0/0 (ref hom => 2 derived, hom del at t=2 only); B = ./. (miss)
    gerp = {100: 5.0, 200: 3.0}
    stream = ["1\t100\tG\tA\tG\t1/1\t0/1\n",
              "1\t200\tC\tT\tT\t0/0\t./.\n"]
    ti, td = _new_acc(samples, thres)
    process(stream, samples, gerp, thres, ti, td)
    # A: site1 hom-derived (2 copies), site2 hom-derived (2 copies) -> tot_der=4, hom_der=4, calls=2
    assert ti["A"]["tot_der"] == 4 and ti["A"]["hom_der"] == 4 and ti["A"]["calls"] == 2
    # A @ t=4: only site1 (gerp5>4) counts -> hom_del_sum = 2*5 = 10, n_hom_del=2
    assert td["A"][4.0]["hom_del_sum"] == 10.0 and td["A"][4.0]["n_hom_del"] == 2
    # A @ t=2: site1 (2*5) + site2 (2*3) = 16, n_hom_del=4
    assert td["A"][2.0]["hom_del_sum"] == 16.0 and td["A"][2.0]["n_hom_del"] == 4
    # B: site1 het (1 derived) -> tot_der=1, calls=1; site2 missing -> miss=1
    assert ti["B"]["tot_der"] == 1 and ti["B"]["calls"] == 1 and ti["B"]["miss"] == 1
    # B @ t=4: het_del_sum = 5 (masked), hom_del_sum = 0
    assert td["B"][4.0]["het_del_sum"] == 5.0 and td["B"][4.0]["hom_del_sum"] == 0.0
    print("wolf_gerp_load self-check: OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="run the self-test and exit")
    ap.add_argument("--gerp-bed", help="GERP bed slice for this chromosome (RS in col5)")
    ap.add_argument("--samples", help="ordered sample list (bcftools query -l)")
    ap.add_argument("--popmap", help="IND<TAB>POP")
    ap.add_argument("--thresholds", default="2,3,4")
    ap.add_argument("--out", help="output raw-counts TSV")
    a = ap.parse_args()
    if a.check:
        _self_check()
        return
    for req in ("gerp_bed", "samples", "popmap", "out"):
        if getattr(a, req) is None:
            ap.error(f"--{req.replace('_', '-')} is required")

    thres = [float(x) for x in a.thresholds.split(",")]
    samples = [s.strip() for s in open(a.samples) if s.strip()]
    popmap = {}
    for line in open(a.popmap):
        line = line.rstrip("\n")
        if line:
            parts = line.split("\t")
            popmap[parts[0]] = parts[1] if len(parts) > 1 else "NA"
    gerp = load_gerp(a.gerp_bed)
    ti, td = _new_acc(samples, thres)
    process(sys.stdin, samples, gerp, thres, ti, td)
    write(a.out, samples, popmap, thres, ti, td)
    print(f"wolf_gerp_load: {len(gerp)} GERP sites, {len(samples)} samples, thresholds {thres}")


if __name__ == "__main__":
    main()
