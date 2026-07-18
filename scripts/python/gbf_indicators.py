#!/usr/bin/env python3
"""Phase-3 GBF Goal-A genetic indicators, computed from the cube + curated inputs (plan §6).

The two GBF genetic indicators are meant to be reported TOGETHER:

  1. **N_e > threshold** — GENOMIC, read from the cube (`per_population` rows only; the
     `pooled`/ALL rows are the Wahlund contrast, never a GBF input). The indicator is the
     *proportion of populations whose contemporary N_e exceeds the threshold*, reported per
     filter preset so the fragility (angle C) is visible.
  2. **Populations Maintained (PM)** — NON-genomic; from range/occurrence records
     (`config/populations_maintained.tsv`). Fraction of historically-present range units
     still extant, with a sensitivity band only when the curated input contains uncertain
     *swing* cases.

Plus the census-proxy (N_c) contrast (config `gbf.census` + `ne_nc_ratio`) and the
robustness table (angle C: how each population's verdict moves across presets).

Heavy compute lives in the workflow; the Streamlit app only READS these tables (plan §2/§6).

Outputs (all tab-separated, into results/tables/):
  gbf_ne500.tsv                  per preset: n_pass/fail/indeterminate + fraction_pass/not_fail
  gbf_robustness.tsv             population x preset verdict matrix + `stable` flag
  gbf_populations_maintained.tsv per-country PM passthrough (cleaned, computed `maintained_flag`)
  gbf_summary.tsv                headline scalars (indicator, value, detail), tidy

Run `--check` for a self-test on synthetic data (no files needed).
"""
import argparse
import sys

import pandas as pd
import yaml

CUBE = "results/cube/results_cube.parquet"
CONFIG = "config/config.yaml"
PM_INPUT = "config/populations_maintained.tsv"
OUTDIR = "results/tables"

PRESET_ORDER = ["lenient", "standard", "strict"]


def _preset_key(p):
    """Sort presets lenient<standard<strict; unknown presets sort after, alphabetically."""
    return (PRESET_ORDER.index(p) if p in PRESET_ORDER else len(PRESET_ORDER), p)


def ne500_indicator(cube, threshold):
    """Per preset, the N_e>threshold indicator from the per_population rows (plan §6).

    fraction_pass    = n_pass / n_pops                      (headline; the GBF indicator)
    fraction_not_fail = (n_pass + n_indeterminate) / n_pops (upper bound if every
                        indeterminate resolved to pass — the optimistic ceiling)
    """
    pp = cube[cube["structure_mode"] == "per_population"]
    rows = []
    for preset in sorted(pp["filter_preset"].unique(), key=_preset_key):
        sub = pp[pp["filter_preset"] == preset]
        n = len(sub)
        n_pass = int((sub["gbf_state"] == "pass").sum())
        n_fail = int((sub["gbf_state"] == "fail").sum())
        n_ind = int((sub["gbf_state"] == "indeterminate").sum())
        rows.append({
            "filter_preset": preset,
            "n_pops": n,
            "n_pass": n_pass,
            "n_fail": n_fail,
            "n_indeterminate": n_ind,
            "fraction_pass": round(n_pass / n, 3) if n else float("nan"),
            "fraction_not_fail": round((n_pass + n_ind) / n, 3) if n else float("nan"),
            "ne_threshold": threshold,
        })
    return pd.DataFrame(rows)


def robustness(cube):
    """Angle C: population x preset verdict matrix + a `stable` flag (all presets agree).

    per_population only. `stable` = the population carries the identical verdict across ALL
    presets (a preset where the population is absent — currently impossible; the cube is a
    fixed cross-product — would count as instability). Instability IS the fragility finding.
    """
    pp = cube[cube["structure_mode"] == "per_population"]
    presets = sorted(pp["filter_preset"].unique(), key=_preset_key)
    rows = []
    for pop in sorted(pp["population"].unique()):
        rec = {"population": pop}
        states = []
        for preset in presets:
            cell = pp[(pp["filter_preset"] == preset) & (pp["population"] == pop)]
            state = cell["gbf_state"].iloc[0] if len(cell) else "missing"
            rec[preset] = state
            states.append(state)
        rec["stable"] = len(set(states)) == 1
        rows.append(rec)
    return pd.DataFrame(rows)


def pm_indicator(pm):
    """Populations Maintained from the curated per-country table.

    denominator = historically-present units. `maintained` in {yes,no,swing}:
      headline = yes / total                 (swing cases counted as NOT maintained — conservative)
      band_high = (yes + swing) / total      (swing cases counted as maintained)
    Returns (per_country_df, summary_dict).
    """
    hist = pm[pm["historically_present"].astype(str).str.strip().str.lower() == "yes"].copy()
    total = len(hist)
    flag = hist["maintained"].astype(str).str.strip().str.lower()
    n_yes = int((flag == "yes").sum())
    n_swing = int((flag == "swing").sum())
    n_no = int((flag == "no").sum())
    hist["maintained_flag"] = flag
    headline = round(n_yes / total, 3) if total else float("nan")
    band_high = round((n_yes + n_swing) / total, 3) if total else float("nan")
    summary = {
        "total": total, "n_maintained": n_yes, "n_swing": n_swing, "n_lost": n_no,
        "headline": headline, "band_low": headline, "band_high": band_high,
    }
    return hist, summary


def census_contrast(cfg):
    """N_c proxy contrast from config gbf.census + ne_nc_ratio (plan §6)."""
    g = cfg["gbf"]
    census = g.get("census", {}).get("peafowl", {})
    return {
        "ne_threshold": g["ne_threshold"],
        "ne_nc_ratio": g["ne_nc_ratio"],
        "nc_proxy_threshold": g["nc_proxy_threshold"],
        "n_mature_low": census.get("n_mature_low"),
        "n_mature_high": census.get("n_mature_high"),
        "iucn_category": census.get("iucn_category"),
        "source": census.get("source"),
    }


def build_summary(ne500, robust, pm_sum, census):
    """Tidy (indicator, value, detail) scalar table for the app's headline row."""
    rows = []
    # N_e>500 indicator, per preset + a one-line headline
    for _, r in ne500.iterrows():
        rows.append((
            f"ne500_fraction_pass_{r['filter_preset']}",
            f"{r['n_pass']}/{r['n_pops']}",
            f"{r['n_indeterminate']} indeterminate, {r['n_fail']} fail "
            f"(fraction_pass={r['fraction_pass']})",
        ))
    n_changes = int((~robust["stable"]).sum())
    fracs = sorted(set(ne500["fraction_pass"].tolist()))
    headline_robust = len(fracs) == 1
    # best-case pass = the single best preset's real (n_pass / n_pops) pair — NOT max(n_pass) over
    # max(n_pops), which could print a numerator/denominator pair no single preset produced.
    best = ne500.loc[ne500["fraction_pass"].idxmax()]
    rows.append((
        "ne500_headline",
        f"{int(best['n_pass'])}/{int(best['n_pops'])} best-case pass (at {best['filter_preset']})",
        ("fraction_pass identical across presets (headline robust); "
         if headline_robust else "fraction_pass varies across presets; ")
        + f"{n_changes}/{len(robust)} populations change verdict across presets "
        "(point estimates preset-fragile)",
    ))
    # Populations Maintained
    rows.append(("pm_headline", pm_sum["headline"],
                 f"{pm_sum['n_maintained']}/{pm_sum['total']} range units maintained; "
                 f"{pm_sum['n_swing']} unresolved swing case(s)"))
    band_detail = (
        f"band spans {pm_sum['n_swing']} unresolved range-unit flag(s)"
        if pm_sum["n_swing"]
        else "no unresolved range-unit flags in the curated table"
    )
    rows.append(("pm_band", f"{pm_sum['band_low']}-{pm_sum['band_high']}", band_detail))
    # Census / N_c contrast
    rows.append(("census_nc_proxy_threshold", census["nc_proxy_threshold"],
                 f"N_e={census['ne_threshold']} <-> N_c={census['nc_proxy_threshold']} "
                 f"at N_e:N_c={census['ne_nc_ratio']}"))
    rows.append(("census_n_mature", f"{census['n_mature_low']}-{census['n_mature_high']}",
                 f"{census['iucn_category']}; {census['source']}"))
    return pd.DataFrame(rows, columns=["indicator", "value", "detail"])


def _self_check():
    """Assert the non-trivial logic on synthetic data — no files needed."""
    cube = pd.DataFrame([
        # per_population: 1 pass, 1 fail, 1 indeterminate under lenient; all fail under strict
        {"structure_mode": "per_population", "filter_preset": "lenient", "population": "A", "gbf_state": "pass"},
        {"structure_mode": "per_population", "filter_preset": "lenient", "population": "B", "gbf_state": "fail"},
        {"structure_mode": "per_population", "filter_preset": "lenient", "population": "C", "gbf_state": "indeterminate"},
        {"structure_mode": "per_population", "filter_preset": "strict", "population": "A", "gbf_state": "fail"},
        {"structure_mode": "per_population", "filter_preset": "strict", "population": "B", "gbf_state": "fail"},
        {"structure_mode": "per_population", "filter_preset": "strict", "population": "C", "gbf_state": "fail"},
        {"structure_mode": "pooled", "filter_preset": "lenient", "population": "ALL", "gbf_state": "fail"},
    ])
    ne_df = ne500_indicator(cube, 500)
    ne = ne_df.set_index("filter_preset")
    assert ne.loc["lenient", "n_pass"] == 1 and ne.loc["lenient", "n_indeterminate"] == 1
    assert ne.loc["lenient", "fraction_pass"] == round(1 / 3, 3)
    assert ne.loc["lenient", "fraction_not_fail"] == round(2 / 3, 3)
    assert ne.loc["strict", "n_fail"] == 3 and ne.loc["strict", "fraction_pass"] == 0.0
    assert list(ne.index) == ["lenient", "strict"]           # preset order honored (no 'standard' here)

    rob_df = robustness(cube)
    rob = rob_df.set_index("population")
    assert bool(rob.loc["B", "stable"]) is True              # fail under both presets
    assert bool(rob.loc["A", "stable"]) is False             # pass -> fail

    pm = pd.DataFrame({
        "historically_present": ["yes"] * 5,
        "maintained": ["yes", "yes", "yes", "no", "swing"],
    })
    _, s = pm_indicator(pm)
    assert s["total"] == 5 and s["n_maintained"] == 3 and s["n_swing"] == 1
    assert s["headline"] == 0.6 and s["band_low"] == 0.6 and s["band_high"] == 0.8

    # build_summary: best-case pair must be a REAL preset's pair (lenient 1/3 here, not a max/max phantom)
    census = census_contrast({"gbf": {"ne_threshold": 500, "ne_nc_ratio": 0.1, "nc_proxy_threshold": 5000,
                                      "census": {"peafowl": {"n_mature_low": 1, "n_mature_high": 2}}}})
    summ = build_summary(ne_df, rob_df, s, census).set_index("indicator")["value"]
    assert summ["ne500_headline"] == "1/3 best-case pass (at lenient)", summ["ne500_headline"]
    assert summ["pm_headline"] == 0.6
    print("gbf_indicators self-check: OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="run the self-test and exit")
    a = ap.parse_args()
    if a.check:
        _self_check()
        return

    cfg = yaml.safe_load(open(CONFIG))
    threshold = cfg["gbf"]["ne_threshold"]
    cube = pd.read_parquet(CUBE)
    pm_raw = pd.read_csv(PM_INPUT, sep="\t")

    ne500 = ne500_indicator(cube, threshold)
    robust = robustness(cube)
    pm_country, pm_sum = pm_indicator(pm_raw)
    census = census_contrast(cfg)
    summary = build_summary(ne500, robust, pm_sum, census)

    ne500.to_csv(f"{OUTDIR}/gbf_ne500.tsv", sep="\t", index=False)
    robust.to_csv(f"{OUTDIR}/gbf_robustness.tsv", sep="\t", index=False)
    pm_country.to_csv(f"{OUTDIR}/gbf_populations_maintained.tsv", sep="\t", index=False)
    summary.to_csv(f"{OUTDIR}/gbf_summary.tsv", sep="\t", index=False)

    print("GBF indicators written to", OUTDIR)
    print(f"  N_e>{threshold}: " + "; ".join(
        f"{r.filter_preset} {r.n_pass}/{r.n_pops} pass ({r.n_indeterminate} indet)"
        for r in ne500.itertuples()))
    print(f"  Populations Maintained: {pm_sum['headline']} "
          f"(band {pm_sum['band_low']}-{pm_sum['band_high']}, "
          f"{pm_sum['n_maintained']}/{pm_sum['total']})")
    print(f"  Robustness: {int((~robust['stable']).sum())}/{len(robust)} populations "
          "change verdict across presets")


if __name__ == "__main__":
    main()
