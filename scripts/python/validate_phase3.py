#!/usr/bin/env python3
"""Phase-3 validation: are the GBF indicator tables well-formed and consistent with the cube? (plan §6)

Asserts STRUCTURE (indicator tables complete, internally consistent, the N_e>500 counts match
the cube they were derived from, the PM band brackets its headline) and REPORTS the scientific
result (0/3 pass, PM, verdict fragility) without over-asserting it — the honest fragility
finding, not a defect.

Writes results/PHASE3_VALIDATION.md + results/tables/validation_phase3.tsv. Exits 1 on FAIL.
"""
import os
import sys

import pandas as pd
import yaml

CUBE = "results/cube/results_cube.parquet"
NE500 = "results/tables/gbf_ne500.tsv"
ROBUST = "results/tables/gbf_robustness.tsv"
PM = "results/tables/gbf_populations_maintained.tsv"
SUMMARY = "results/tables/gbf_summary.tsv"

_CFG = yaml.safe_load(open("config/config.yaml"))
POPS = _CFG["peafowl"]["populations"]
PRESETS = _CFG["cube"]["filter_presets"]
THRESH = _CFG["gbf"]["ne_threshold"]

checks = []


def add(name, ok, detail):
    checks.append((name, "PASS" if ok else ("WARN" if ok is None else "FAIL"), detail))


def main():
    for f in (CUBE, NE500, ROBUST, PM, SUMMARY):
        if not os.path.exists(f):
            sys.exit(f"missing: {f} — run `snakemake phase3` first")

    cube = pd.read_parquet(CUBE)
    ne500 = pd.read_csv(NE500, sep="\t")
    robust = pd.read_csv(ROBUST, sep="\t")
    pm = pd.read_csv(PM, sep="\t")
    summary = pd.read_csv(SUMMARY, sep="\t")
    pp = cube[cube["structure_mode"] == "per_population"]

    # 1. ne500 has one row per preset present in the cube
    add("gbf_ne500 has one row per preset",
        set(ne500["filter_preset"]) == set(PRESETS),
        f"presets={sorted(ne500['filter_preset'])} vs config {sorted(PRESETS)}")

    # 2. counts sum to n_pops and fraction_pass is consistent, every row
    ok_counts = True
    ok_frac = True
    for _, r in ne500.iterrows():
        if r["n_pass"] + r["n_fail"] + r["n_indeterminate"] != r["n_pops"]:
            ok_counts = False
        expect = round(r["n_pass"] / r["n_pops"], 3) if r["n_pops"] else float("nan")
        if abs(r["fraction_pass"] - expect) > 1e-9:
            ok_frac = False
    add("ne500 counts sum to n_pops", ok_counts, "pass+fail+indeterminate == n_pops (all rows)")
    add("ne500 fraction_pass = n_pass/n_pops", ok_frac, "fraction matches its counts (all rows)")

    # 3. ne500 counts MATCH the cube (the indicator can't drift from its source of truth)
    match = True
    detail = []
    for preset in PRESETS:
        sub = pp[pp["filter_preset"] == preset]
        cube_pass = int((sub["gbf_state"] == "pass").sum())
        cube_ind = int((sub["gbf_state"] == "indeterminate").sum())
        row = ne500[ne500["filter_preset"] == preset]
        if row.empty or int(row["n_pass"].iloc[0]) != cube_pass or int(row["n_indeterminate"].iloc[0]) != cube_ind:
            match = False
        detail.append(f"{preset}: cube {cube_pass} pass/{cube_ind} indet")
    add("ne500 counts reconcile with the cube", match, "; ".join(detail))

    # 4. robustness: one row per per_population population; stable flag correct
    add("robustness has one row per population",
        set(robust["population"]) == set(pp["population"].unique()),
        f"{sorted(robust['population'])}")
    stable_ok = True
    for _, r in robust.iterrows():
        states = [r[p] for p in PRESETS if p in robust.columns]
        if bool(r["stable"]) != (len(set(states)) == 1):
            stable_ok = False
    add("robustness `stable` flag correct", stable_ok, "stable == (verdict identical across presets)")

    # 5. Populations Maintained: per-country table + band brackets headline
    srow = summary.set_index("indicator")["value"]
    pm_head = float(srow.get("pm_headline"))
    band = str(srow.get("pm_band"))
    lo, hi = (float(x) for x in band.split("-"))
    add("PM band brackets headline and is in [0,1]",
        0.0 <= lo <= pm_head <= hi <= 1.0, f"headline={pm_head}, band={band}")
    add("PM per-country flags in {yes,no,swing}",
        set(pm["maintained_flag"].astype(str)) <= {"yes", "no", "swing"},
        f"flags={sorted(set(pm['maintained_flag'].astype(str)))}")

    # 6. summary carries the headline indicator keys
    need = {"ne500_headline", "pm_headline", "pm_band", "census_nc_proxy_threshold"}
    add("summary has headline indicator keys", need <= set(summary["indicator"]),
        f"missing: {sorted(need - set(summary['indicator']))}" if need - set(summary["indicator"]) else "all present")

    # 7. REPORT: the N_e>threshold indicator per preset (the fragility finding — not asserted)
    add(f"N_e>{THRESH} fraction pass (per_population)", None,
        "; ".join(f"{r.filter_preset}: {r.n_pass}/{r.n_pops} pass, {r.n_indeterminate} indet"
                  for r in ne500.itertuples()))

    # 8. REPORT: PM headline + robustness fragility
    n_changes = int((~robust["stable"]).sum())
    add("Populations Maintained", None, f"PM={pm_head} (band {band})")
    add("verdict fragility across presets", None,
        f"{n_changes}/{len(robust)} populations change verdict across presets "
        "(estimates preset-fragile; the angle-C finding)")

    rep = pd.DataFrame(checks, columns=["check", "status", "detail"])
    rep.to_csv("results/tables/validation_phase3.tsv", sep="\t", index=False)
    n_fail = int((rep.status == "FAIL").sum())

    with open("results/PHASE3_VALIDATION.md", "w") as fh:
        fh.write("# Phase 3 — validation report\n\n")
        fh.write("Asserts the GBF indicator tables are **well-formed** and **reconcile with the "
                 "cube** they derive from, and **reports** the scientific result (0/3 pass, PM, "
                 "verdict fragility) without over-asserting it — the honest fragility finding.\n\n")
        fh.write("| check | status | detail |\n|---|---|---|\n")
        for _, r in rep.iterrows():
            fh.write(f"| {r['check']} | **{r['status']}** | {r['detail']} |\n")
        fh.write(f"\n**{n_fail} FAIL**, {(rep.status=='WARN').sum()} WARN (reported-not-asserted), "
                 f"{(rep.status=='PASS').sum()} PASS.\n\n")
        fh.write("**N_e>500 indicator (per preset):**\n\n```\n" + ne500.to_string(index=False) + "\n```\n\n")
        fh.write("**Robustness (angle C — verdict across presets):**\n\n```\n"
                 + robust.to_string(index=False) + "\n```\n")
    print(rep.to_string(index=False))
    print(f"\n{n_fail} FAIL")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
