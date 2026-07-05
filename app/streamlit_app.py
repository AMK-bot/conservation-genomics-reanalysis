"""Fragility Explorer — how fragile is the green peafowl's conservation verdict?

Green peafowl N_e / GBF verdict under analyst choices. Two knobs:
    filtering stringency  x  structure (modeled per_population / ignored pooled)
-> live N_e + 90% CI + conservation-risk reading (At risk / Uncertain / Likely secure).

This app ONLY READS precomputed workflow outputs — the cube
(results/cube/results_cube.parquet), the GBF indicator tables (results/tables/gbf_*.tsv),
and the static figures (results/figures/*.png). All heavy bioinformatics runs in the
Snakemake DAG, never here (plan §2, §6). Rebuild inputs with `snakemake all`.

Tabs: N_e / GBF verdict (the two-knob badge + both GBF Goal-A indicators + robustness +
the GONE2 recent-trajectory context panel) · Structure & diversity (PCA / ADMIXTURE /
temporal figures) · About (limitations + reproducibility). [Wolf load tab lands in Phase 4.]
"""
import math
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

CUBE = Path("results/cube/results_cube.parquet")
TABLES = Path("results/tables")
FIGURES = Path("results/figures")
CONFIG = Path("config/config.yaml")

# Verdict DISPLAY labels. Internal gbf_state keys stay pass/fail/indeterminate (the pipeline logic
# is untouched); the app shows conservation-risk wording so a red badge doesn't read as a software
# "fail": pass -> Likely secure, indeterminate -> Uncertain, fail -> At risk.
STATE_LABEL = {"pass": "Likely secure", "fail": "At risk", "indeterminate": "Uncertain", "missing": "n/a"}
STATE_DOT = {"pass": "🟢", "fail": "🔴", "indeterminate": "🟠", "missing": "·"}
STATE_BADGE = {k: f"{STATE_DOT[k]} {STATE_LABEL[k]}" for k in ("pass", "fail", "indeterminate")}


@st.cache_data
def load_config():
    try:
        return yaml.safe_load(CONFIG.read_text())
    except Exception:
        return {}


@st.cache_data
def load_cube():
    return pd.read_parquet(CUBE)


@st.cache_data
def load_tsv(name):
    """A results/tables/*.tsv, or None if the workflow hasn't built it yet."""
    p = TABLES / name
    return pd.read_csv(p, sep="\t") if p.exists() else None


def fmt_ci(x):
    """CI bound -> display: NaN (non-convergence) -> n/a, inf (unbounded) -> ∞, else thousands."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    if isinstance(x, float) and math.isinf(x):
        return "∞"
    return f"{x:,.0f}"


def fmt_ne(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    if isinstance(x, float) and math.isinf(x):
        return "∞"
    return f"{x:,.0f}"


def show_figure(name, caption):
    p = FIGURES / name
    if p.exists():
        st.image(str(p), caption=caption, width="stretch")
    else:
        st.info(f"`{p}` not built yet — run `snakemake all`.")


CFG = load_config()
try:
    NE_THRESHOLD = CFG["gbf"]["ne_threshold"]
except Exception:
    NE_THRESHOLD = 500

st.set_page_config(page_title="Fragility Explorer", page_icon="🦚", layout="wide")
st.title("🦚 Fragility Explorer")
st.caption(
    "How fragile is the green peafowl's conservation verdict to analyst choices? "
    "The risk reading against the international N_e > 500 target flips as you change how the data is "
    "filtered and whether population structure is modeled. This claims **risk**, not demonstrated "
    "inbreeding depression — see the *About* tab."
)

if not CUBE.exists():
    st.warning(
        "The results cube hasn't been built yet. Run the workflow first:\n\n"
        "```bash\nsnakemake all --cores 4\n```\n\n"
        f"Expected at `{CUBE}`."
    )
    st.stop()

cube = load_cube()
ne500 = load_tsv("gbf_ne500.tsv")
robust = load_tsv("gbf_robustness.tsv")
pm = load_tsv("gbf_populations_maintained.tsv")
summary = load_tsv("gbf_summary.tsv")

tab_ne, tab_struct, tab_about = st.tabs(
    ["N_e / GBF verdict", "Structure & diversity", "About / limitations"]
)

# ══════════════════════════════════════════════════════════════════════════════════
# TAB 1 — the two-knob verdict + both GBF indicators + robustness + GONE2 context
# ══════════════════════════════════════════════════════════════════════════════════
with tab_ne:
    st.subheader("The two knobs")
    c1, c2 = st.columns(2)
    with c1:
        filt = st.select_slider(
            "Filtering stringency", options=["lenient", "standard", "strict"], value="standard",
            help="How hard the genotypes are filtered before N_e is estimated. Re-derived per preset.")
    with c2:
        structure = st.radio(
            "Population structure", ["per_population", "pooled"], horizontal=True,
            help="Model each population separately (correct) vs. lump all 22 birds together "
                 "(Wahlund effect biases N_e low — a cautionary contrast, never a GBF input).")

    sel = cube.query("filter_preset == @filt and structure_mode == @structure")
    if sel.empty:
        st.error("No cube cell for that combination.")
        st.stop()

    if structure == "per_population":
        pop = st.radio("Population", sorted(sel["population"]), horizontal=True)
        sel = sel.query("population == @pop")

    row = sel.iloc[0]
    ne = float(row["ne_point"]); ci_lo, ci_hi = float(row["ci_low"]), float(row["ci_high"])
    state = row["gbf_state"]

    m1, m2 = st.columns([1, 2])
    m1.metric("Contemporary N_e (cross-chromosome)", fmt_ne(ne),
              help=f"90% CI: {fmt_ci(ci_lo)} – {fmt_ci(ci_hi)} · n = {int(row['n_ind'])} · "
                   f"{int(row['n_snps']):,} SNPs · basis: {row['ne_basis']}")
    with m2:
        if structure == "pooled":
            st.markdown("#### ⚖️ Wahlund contrast — *not* a GBF verdict")
            st.caption(
                "Pooling across structured populations inflates linkage disequilibrium, biasing "
                "N_e **low** (Wahlund). This is the cautionary contrast for the per-population "
                "estimates, never a GBF verdict input.")
        else:
            st.markdown(f"#### {STATE_BADGE[state]}  — vs N_e = {NE_THRESHOLD} (GBF target)")
            st.caption(
                "Read off the point estimate; **Uncertain** when the 90% CI straddles "
                f"{NE_THRESHOLD} or the estimator did not converge. That uncertain band *is* "
                "the fragility story, not a defect — at n = 7/10/5 the data cannot resolve it. "
                "(These are conservation-risk readings, not a software pass/fail.)")

    st.divider()

    # ── Indicator 1: N_e > threshold (genomic, from the cube) ──────────────────────
    st.subheader(f"GBF genetic indicator 1 — populations with N_e > {NE_THRESHOLD}")
    if ne500 is not None:
        r = ne500.query("filter_preset == @filt")
        if not r.empty:
            r = r.iloc[0]
            i1, i2, i3 = st.columns(3)
            i1.metric(f"🟢 Likely secure (at {filt})", f"{int(r['n_pass'])}/{int(r['n_pops'])}")
            i2.metric("🟠 Uncertain", int(r["n_indeterminate"]))
            i3.metric("🔴 At risk", int(r["n_fail"]))
            st.caption(
                f"Fraction meeting N_e > {NE_THRESHOLD} = **{r['fraction_pass']}**; optimistic ceiling if "
                f"every uncertain case resolved upward = {r['fraction_not_fail']}. The headline indicator "
                "is that fraction — here **0 across every preset**.")
    else:
        st.info("`gbf_ne500.tsv` not built — run `snakemake phase3`.")

    # ── Robustness (angle C): verdict across the whole cube ────────────────────────
    st.subheader("Robustness — does the verdict hold across analyst choices? (angle C)")
    if robust is not None:
        presets = [c for c in ["lenient", "standard", "strict"] if c in robust.columns]
        disp = robust.set_index("population")[presets].copy()
        for p in presets:
            disp[p] = disp[p].map(lambda s: f"{STATE_DOT.get(s, '·')} {STATE_LABEL.get(s, s)}")

        def _hl(_col):
            # highlight the currently-selected preset column
            return ["font-weight: 700; background-color: rgba(127,127,127,0.15)"
                    if _col.name == filt else "" for _ in _col]

        st.dataframe(disp.style.apply(_hl, axis=0), width="stretch")
        n_changes = int((~robust["stable"]).sum())
        st.caption(
            f"**{n_changes}/{len(robust)} populations change verdict across presets.** The *headline* "
            "(0 of 3 clearing N_e > 500) is robust; the underlying point estimates and even convergence "
            "are preset-fragile (e.g. Vietnam converges to a point estimate under lenient but fails to "
            "converge under stricter filters, though its reading stays Uncertain throughout). "
            "That fragility is the finding, honestly reported.")
    else:
        st.info("`gbf_robustness.tsv` not built — run `snakemake phase3`.")

    st.divider()

    # ── Indicator 2: Populations Maintained (non-genomic, curated) ─────────────────
    st.subheader("GBF genetic indicator 2 — Populations Maintained")
    sm = summary.set_index("indicator")["value"] if summary is not None else pd.Series(dtype=object)
    pm_head = sm.get("pm_headline", "?")
    pm_band = sm.get("pm_band", "?")
    p1, p2 = st.columns([1, 2])
    p1.metric("Populations Maintained (PM)", pm_head, help=f"Sensitivity band {pm_band}")
    p2.caption(
        f"PM = **{pm_head}** (band {pm_band}) — the fraction of historically-present range countries "
        "still extant. **Non-genomic**, curated from IUCN/BirdLife + literature (range unit = "
        "country; a single reclassification of the India/Laos swing cases moves it by 0.10). "
        "The three sampled populations are *all* in the maintained set — yet none confidently "
        "passes N_e > 500. **Still present ≠ genetically viable** — that gap is the message.")
    if pm is not None:
        with st.expander("Per-country Populations-Maintained tally"):
            cols = [c for c in ["country", "subspecies", "current_status", "maintained_flag", "note"]
                    if c in pm.columns]
            st.dataframe(pm[cols], width="stretch", hide_index=True)
            st.caption("Sourcing not field-verified — reconstructed from IUCN/BirdLife narrative + "
                       "peer-reviewed literature + GBIF; verify India / Laos / N. Vietnam against the "
                       "live IUCN table before publication.")

    # ── Census / N_c contrast ──────────────────────────────────────────────────────
    st.subheader("Census (N_c) contrast")
    nc_thr = sm.get("census_nc_proxy_threshold", CFG.get("gbf", {}).get("nc_proxy_threshold", 5000))
    nc_mature = sm.get("census_n_mature", "?")
    ratio = CFG.get("gbf", {}).get("ne_nc_ratio", 0.1)
    st.caption(
        f"N_e = {NE_THRESHOLD} corresponds to a census N_c ≈ **{nc_thr}** at a conservative "
        f"N_e:N_c = {ratio} (Frankham). Range-wide mature count is ~**{nc_mature}** (EN, decreasing) "
        "— nominally above the proxy, **but that is the wrong denominator for a per-population "
        "indicator**: the species is fragmented into subpopulations far below it (e.g. Keo Seima, "
        "Cambodia ~745), so expected per-population N_e ≪ 500 — and the measured genomic N_e is "
        "lower still. The N_e:N_c gap is the conservation signal.")

    st.divider()

    # ── GONE2 recent-trajectory context panel (NOT a cube axis, NOT the badge) ──────
    st.subheader("Recent-N_e trajectory — context only (GONE2)")
    show_figure("gone2_trajectory.png",
                "GONE2 recent species-level N_e trajectory — 17 macrochromosomes, ~377k SNPs.")
    st.caption(
        "**Context only, never the verdict.** A different time horizon (recent past, not "
        "contemporary), thin n, a *borrowed* generic-bird recombination rate (peafowl has no map), "
        "and macrochromosomes only. GBF guidance excludes recent-trajectory estimates from the "
        "contemporary N_e indicator, so this curve never touches the badge above.")

    with st.expander("Static fragility view (all cells)"):
        show_figure("ne_cube.png", "N_e across filter × structure — the full cube at a glance.")

# ══════════════════════════════════════════════════════════════════════════════════
# TAB 2 — structure & diversity (precomputed figures)
# ══════════════════════════════════════════════════════════════════════════════════
with tab_struct:
    st.subheader("Population structure")
    a, b = st.columns(2)
    with a:
        show_figure("pca.png", "PCA — three populations separate cleanly (centroid gap ≫ spread), "
                               "but per-PC variance is low (PC1 ≈ 9%).")
    with b:
        show_figure("admixture.png", "ADMIXTURE — CV is monotonic in K (favours K=1), a small-n "
                                     "artifact; structure is read from PCA, not the CV curve.")
    show_figure("kinship_heatmap.png", "KING kinship — cross-population values are unreliable under "
                                       "strong structure; the interpretable signal is within-population.")
    st.divider()
    st.subheader("Diversity & temporal erosion (angle G)")
    c, d = st.columns(2)
    with c:
        show_figure("diversity_perpop.png", "Per-population Ho / He / allelic richness — Thailand "
                                            "(n=5) lowest; Yunnan shows a heterozygote deficit (Fis 0.086).")
    with d:
        show_figure("temporal_diversity.png", "Museum vs modern — the temporal-erosion signal is "
                                              "weak and metric-dependent (π/Ho weakly museum>modern; "
                                              "He/AR essentially flat). A contrast direction, not a claim.")

# ══════════════════════════════════════════════════════════════════════════════════
# TAB 3 — about / limitations / reproducibility
# ══════════════════════════════════════════════════════════════════════════════════
with tab_about:
    st.subheader("What this tool claims — and what it does not")
    st.markdown(
        f"""
- **Risk, not depression.** The N_e > {NE_THRESHOLD} indicator flags *loss-of-adaptive-potential
  risk*. It is **not** a measurement of realized inbreeding depression.
- **Small n is a feature, not a bug.** At n = 7/10/5 per population the CIs are wide and many
  cells are *Uncertain*. The point of the tool is to show how that uncertainty interacts with
  analyst choices — the fragility thesis — not to pin a single number.
- **currentNe2 is the only automated estimator.** GONE2 is a recent-trajectory *context* panel
  (different time horizon, borrowed recombination rate). NeEstimator-LDNe is a **manual** GUI
  cross-check reported separately, never wired into this badge.
- **Ascertainment & coverage caveats** apply per the report. The comparative (temporal) contrast
  is geographically narrow and subject to aDNA deamination.
- **Populations Maintained is non-genomic** and country-unit — it *overstates* persistence
  (a country counted extant can have lost most of its range).
"""
    )
    st.subheader("Reproducibility")
    st.markdown(
        """
Every number here is built by the Snakemake DAG from two public deposits; this app reads the
outputs only.

```bash
micromamba create -n congen -f environment.lock.yml   # 8 GB / Apple-Silicon: micromamba, not classic conda
micromamba activate congen
snakemake all --cores 4                                # builds the cube + GBF tables + figures
streamlit run app/streamlit_app.py                     # this tool
```
"""
    )
    st.caption("Datasets: green peafowl — Dong et al. 2021 (Dryad 10.5061/dryad.ffbg79ctc). "
               "Wolf load chapter (Phase 4) — Smeds & Ellegren 2022 (Dryad 10.5061/dryad.7m0cfxpzj).")
