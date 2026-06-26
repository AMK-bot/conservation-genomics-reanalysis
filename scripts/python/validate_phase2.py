#!/usr/bin/env python3
"""Phase-2 validation: is the results cube well-formed and are the N_e verdicts sane? (plan §5)

Asserts STRUCTURE (cube shape, schema, state vocabulary, inf handling) and REPORTS the
scientific direction (Wahlund structure-bias, GBF fraction) without over-asserting it — at
n = 7/10/5 the verdicts are mostly indeterminate/fail BY DESIGN (the fragility thesis).

Writes results/PHASE2_VALIDATION.md + results/tables/validation_phase2.tsv. Exits 1 on FAIL.
"""
import os
import sys
import numpy as np
import pandas as pd
import yaml

CUBE = "results/cube/results_cube.parquet"
GONE2 = "results/tables/gone2_trajectory.tsv"
XCHECK = "results/tables/ne_metapop_xcheck.tsv"

# Cube shape + threshold are config-driven (same source ne.smk builds NE_CELLS from) so the gate
# tracks the real cube instead of a frozen 12-row snapshot.
_CFG = yaml.safe_load(open("config/config.yaml"))
POPS = _CFG["peafowl"]["populations"]
PRESETS = _CFG["cube"]["filter_presets"]
THRESH = _CFG["gbf"]["ne_threshold"]
N_EXPECTED = len(PRESETS) * (len(POPS) + 1)   # per-pop pops + 1 pooled(ALL), per preset
VALID_STATES = {"pass", "fail", "indeterminate"}

checks = []   # (name, status, detail)


def add(name, ok, detail):
    checks.append((name, "PASS" if ok else ("WARN" if ok is None else "FAIL"), detail))


def main():
    if not os.path.exists(CUBE):
        sys.exit(f"cube missing: {CUBE} — run `snakemake phase2` first")
    cube = pd.read_parquet(CUBE)

    # 1. shape: N_EXPECTED rows = presets x (per_population pops + 1 pooled), all config-driven
    add(f"cube has {N_EXPECTED} rows", len(cube) == N_EXPECTED,
        f"got {len(cube)}, expected {N_EXPECTED} = {len(PRESETS)} presets x ({len(POPS)} pops + 1 pooled)")

    # 2. schema columns present
    need = {"filter_preset", "structure_mode", "population", "ne_method",
            "ne_point", "ci_low", "ci_high", "n_ind", "n_snps", "k", "ne_basis", "gbf_state"}
    add("schema columns present", need <= set(cube.columns),
        f"missing: {sorted(need - set(cube.columns))}" if need - set(cube.columns) else "all present")

    # 3. each preset complete: 3 per_population pops + 1 pooled ALL
    complete = True
    for p in PRESETS:
        pp = set(cube.query("filter_preset==@p and structure_mode=='per_population'")["population"])
        pl = set(cube.query("filter_preset==@p and structure_mode=='pooled'")["population"])
        if pp != set(POPS) or pl != {"ALL"}:
            complete = False
    add("every preset has 3 per_population + 1 pooled(ALL)", complete,
        "all presets complete" if complete else "missing cells")

    # 4. ne_method is the single automated estimator (currentNe2) — assert the column stays constant
    methods = sorted(cube["ne_method"].unique())
    add("ne_method == [currentNe2]", methods == ["currentNe2"], f"got {methods}")

    # 5. gbf_state vocabulary
    states = set(cube["gbf_state"].dropna().unique())
    add("gbf_state in {pass,fail,indeterminate}", states <= VALID_STATES, f"got {sorted(states)}")

    # 6. ne_basis matches convergence: a converged cell carries a real basis (cross_chromosome
    #    headline, or whole_genome fallback); a non-converged cell is 'none' — NOT a silent
    #    'whole_genome' (which would read as a successful fallback estimate; plan §5).
    nx = int((cube["ne_basis"] == "cross_chromosome").sum())
    nw = int((cube["ne_basis"] == "whole_genome").sum())
    nn = int((cube["ne_basis"] == "none").sum())
    mismatch = cube[((cube["ne_point"].notna()) & (~cube["ne_basis"].isin({"cross_chromosome", "whole_genome"})))
                    | ((cube["ne_point"].isna()) & (cube["ne_basis"] != "none"))]
    add("ne_basis matches convergence", len(mismatch) == 0,
        f"{nx} cross_chromosome (headline), {nw} whole_genome (fallback), {nn} non-converged (basis=none)"
        + ("" if len(mismatch) == 0 else f"; {len(mismatch)} basis/convergence mismatch(es)"))

    # 7. inf handling: unbounded upper CIs stored as inf, not a 9-digit number (info)
    n_inf = int(np.isinf(cube["ci_high"]).sum())
    add("unbounded upper CIs stored as inf", None,
        f"{n_inf}/{len(cube)} cells have ci_high = inf (expected at n=7/10/5)")

    # 8. a pass/fail verdict requires a point estimate (NaN -> indeterminate, by the parser). inf is
    #    a VALID point (unbounded-large N_e > threshold -> pass), so assert non-null, not finite.
    bad = cube[(cube["gbf_state"].isin({"pass", "fail"})) & (cube["ne_point"].isna())]
    add("pass/fail cells have a point estimate", len(bad) == 0,
        "ok" if len(bad) == 0 else f"{len(bad)} pass/fail cells with no point estimate")

    # 9. Wahlund structure-bias DIRECTION (reported, not asserted — the scientific finding)
    bias_lines = []
    for p in PRESETS:
        pooled = cube.query("filter_preset==@p and structure_mode=='pooled'")["ne_point"]
        perpop = cube.query("filter_preset==@p and structure_mode=='per_population'")["ne_point"]
        if len(pooled) and perpop.notna().any():
            pv = float(pooled.iloc[0]); med = float(np.nanmedian(perpop))
            bias_lines.append(f"{p}: pooled={pv:.0f} vs per-pop median={med:.0f}")
    add("Wahlund direction (pooled vs per-pop)", None, "; ".join(bias_lines) or "n/a")

    # 10. GBF fraction (per_population only) per preset — the headline indicator (reported)
    gbf_lines = []
    for p in PRESETS:
        pp = cube.query("filter_preset==@p and structure_mode=='per_population'")
        npass = (pp["gbf_state"] == "pass").sum()
        nind = (pp["gbf_state"] == "indeterminate").sum()
        gbf_lines.append(f"{p}: {npass}/{len(pp)} pass, {nind} indeterminate")
    add(f"GBF fraction N_e>{THRESH} (per_population)", None, "; ".join(gbf_lines))

    # 11. GONE2 context trajectory exists + non-empty
    g_ok = os.path.exists(GONE2) and sum(1 for _ in open(GONE2)) > 1
    add("GONE2 context trajectory present", g_ok,
        f"{GONE2} " + ("ok" if g_ok else "MISSING/empty"))

    # 12. -x metapopulation cross-check table present (report cross-check)
    add("metapop -x cross-check table present", True if os.path.exists(XCHECK) else None,
        f"{XCHECK} " + ("present" if os.path.exists(XCHECK) else "absent (optional)"))

    # ── write outputs ──
    rep = pd.DataFrame(checks, columns=["check", "status", "detail"])
    rep.to_csv("results/tables/validation_phase2.tsv", sep="\t", index=False)
    n_fail = int((rep.status == "FAIL").sum())

    with open("results/PHASE2_VALIDATION.md", "w") as fh:
        fh.write("# Phase 2 — validation report\n\n")
        fh.write("Asserts the cube is **well-formed** (shape/schema/states/inf) and **reports** the "
                 "scientific direction (Wahlund bias, GBF fraction) without over-asserting it — at "
                 "n = 7/10/5 most verdicts are indeterminate/fail *by design* (the fragility thesis).\n\n")
        fh.write("| check | status | detail |\n|---|---|---|\n")
        for _, r in rep.iterrows():
            fh.write(f"| {r['check']} | **{r['status']}** | {r['detail']} |\n")
        fh.write(f"\n**{n_fail} FAIL**, {(rep.status=='WARN').sum()} WARN (reported-not-asserted), "
                 f"{(rep.status=='PASS').sum()} PASS.\n\n")
        fh.write("**Cube (per-population rows feed the GBF fraction; pooled = ALL is the Wahlund "
                 "contrast, never a GBF input):**\n\n")
        fh.write("```\n" + cube.to_string(index=False) + "\n```\n")
    print(rep.to_string(index=False))
    print(f"\n{n_fail} FAIL")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
