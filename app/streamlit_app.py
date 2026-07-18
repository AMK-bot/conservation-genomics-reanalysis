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
temporal figures) · Wolf load & ROH · About (limitations + reproducibility).
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
scorecard = load_tsv("fragility_scorecard.tsv")

tab_ne, tab_struct, tab_wolf, tab_about = st.tabs(
    ["N_e / GBF verdict", "Structure & diversity", "🐺 Wolf: load & ROH", "About / limitations"]
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

    # ── Phase 5A synthesis: conclusion stability vs numerical sensitivity ─────────
    st.subheader("Fragility scorecard — what survives the sensitivity tests?")
    st.caption(
        "The labels separate a stable biological conclusion from a sensitive numerical magnitude, "
        "an evidence-limited answer, and a result that depends on method settings. The scorecard is "
        "derived only from the validated summary tables; it introduces no new analysis claim."
    )
    if scorecard is not None:
        score_cols = [
            "classification",
            "conclusion",
            "settings_supporting",
            "dominant_uncertainty",
            "evidence_needed",
        ]
        st.dataframe(
            scorecard[[column for column in score_cols if column in scorecard.columns]],
            width="stretch",
            hide_index=True,
        )
        with st.expander("Offline scorecard figure"):
            show_figure(
                "fragility_scorecard.png",
                "Four conclusions classified by robustness, magnitude sensitivity, and evidence limits.",
            )
    else:
        st.info("`fragility_scorecard.tsv` not built — run `snakemake phase5a1`.")

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
        "country). The current BirdLife country table leaves no unresolved swing flag, but this "
        "country-scale tally remains too coarse to prove persistence within each country. "
        "The three sampled populations are *all* in the maintained set — yet none confidently "
        "passes N_e > 500. **Still present ≠ genetically viable** — that gap is the message.")
    if pm is not None:
        with st.expander("Per-country Populations-Maintained tally"):
            cols = [c for c in ["country", "subspecies", "current_status", "maintained_flag", "note"]
                    if c in pm.columns]
            st.dataframe(pm[cols], width="stretch", hide_index=True)
            st.caption("BirdLife's live country distribution table was checked field by field on "
                       "2026-07-18 (India: Extinct; Laos: Extant). Finer sub-country occurrence "
                       "records are still needed for a publication-grade persistence assessment.")

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
# TAB 3 — wolf genetic load + ROH (Phase 4): two knobs (GERP, ROH-length) move the readings
# ══════════════════════════════════════════════════════════════════════════════════
with tab_wolf:
    st.subheader("🐺 Scandinavian wolf — genetic load & inbreeding")
    st.caption(
        "A population founded by a few individuals (~1983) and inbred since. Two analyst knobs move "
        "the readings: the **GERP** conservation score that defines a site as 'deleterious', and the "
        "**ROH length** that counts as inbreeding. *Realized* load = deleterious variants expressed in "
        "homozygous state; *masked* load = the same load hidden in heterozygotes. Inbreeding converts "
        "masked → realized — that conversion is the story.")
    wolf_load = load_tsv("wolf_load.tsv")
    wolf_roh = load_tsv("wolf_roh.tsv")
    if wolf_load is None or wolf_roh is None:
        st.info("Wolf tables not built yet — run `snakemake phase4` (streams the 11 GB VCF "
                "per chromosome; ~30 min).")
    else:
        k1, k2 = st.columns(2)
        with k1:
            gvals = sorted(wolf_load["THRES"].unique())
            gerp = st.select_slider("GERP threshold — deleterious if RS >", options=gvals,
                                    value=4.0 if 4.0 in gvals else gvals[-1])
        with k2:
            rvals = sorted(wolf_roh["min_length_mb"].unique())
            roh_cut = st.select_slider("ROH length cutoff (Mb) — counts as inbreeding",
                                       options=rvals, value=1.5 if 1.5 in rvals else rvals[0])

        st.markdown("#### Genetic load — realized vs masked, by time period")
        ld = wolf_load[wolf_load["THRES"] == gerp]
        by_pop = (ld.groupby("POP")[["REALIZED_LOAD", "MASKED_LOAD"]].mean().sort_index()
                    .rename(columns={"REALIZED_LOAD": "realized", "MASKED_LOAD": "masked"}))
        st.bar_chart(by_pop, stack=False, color=["#b0303a", "#c98a1a"])
        lm = ld["MASKED_LOAD"].mean()
        m1, m2, m3 = st.columns(3)
        m1.metric("Mean realized load", f"{ld['REALIZED_LOAD'].mean():.3f}")
        m2.metric("Mean masked load", f"{lm:.3f}")
        m3.metric("Realized : masked", f"{ld['REALIZED_LOAD'].mean() / lm:.2f}" if lm else "—")
        st.caption(
            f"At GERP>{gerp:g}, GERP-weighted, ancestral-polarized deleterious load per individual. "
            "Raising the GERP threshold keeps only the most-conserved sites — the absolute load shrinks, "
            "but the realized-vs-masked *pattern* is the robust signal (the wolf-side fragility check).")

        st.markdown("#### Inbreeding — F_ROH by time period")
        rh = wolf_roh[wolf_roh["min_length_mb"] == roh_cut]
        froh = rh.groupby("POP")["F_ROH"].mean().sort_index().rename("F_ROH").to_frame()
        st.bar_chart(froh, color="#0d7d80")
        r1, r2 = st.columns(2)
        r1.metric(f"Mean F_ROH (ROH ≥ {roh_cut:g} Mb)", f"{rh['F_ROH'].mean():.3f}")
        r2.metric("Recent-inbreeding F_ROH (≥ 1.5 Mb)", f"{rh['froh_long_recent'].mean():.3f}")
        st.caption(
            f"Fraction of the autosomes in runs of homozygosity ≥ {roh_cut:g} Mb. Long ROH (≥ 1.5 Mb) "
            "are recent inbreeding; raising the cutoff separates that recent signal from ancient "
            "background homozygosity. F_ROH climbs alongside realized load as the population inbreeds.")

        with st.expander("Method & caveats (wolf chapter)"):
            st.markdown(
                "- Load faithfully re-implements Smeds & Ellegren 2022 (`gerp_load_polarized.py`); at "
                "GERP>4 it reproduces the deposit's precomputed per-individual load (validated).\n"
                "- Derived allele set by the ancestral allele (`INFO/AA`, polarized with two outgroups).\n"
                "- ROH from `bcftools roh` (GT-based HMM) with a **documented constant** recombination "
                "rate — the wolf has no dense genetic map.\n"
                "- Claims **inbreeding-exposure risk**, not measured fitness or demonstrated depression.")

# ══════════════════════════════════════════════════════════════════════════════════
# TAB 4 — about / limitations / reproducibility
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
    st.subheader("What evidence would change the conclusion?")
    st.caption(
        "This is a decision map for a future study, not a promise to collect new data as part of "
        "this project. It identifies the most informative next observation for each uncertainty."
    )
    evidence_map = pd.DataFrame(
        [
            {
                "Current conclusion or boundary": "Peafowl N_e verdicts remain uncertain at n=7/10/5",
                "What remains unresolved": "Precision and convergence of population-level estimates",
                "Most useful next evidence": "More independently sampled individuals per population",
            },
            {
                "Current conclusion or boundary": "GONE2 is recent-trajectory context only",
                "What remains unresolved": "Sensitivity to the borrowed generic-bird recombination rate",
                "Most useful next evidence": "A green-peafowl-specific recombination map",
            },
            {
                "Current conclusion or boundary": "The project shows risk, not inbreeding depression",
                "What remains unresolved": "Whether genomic risk predicts realized biological harm",
                "Most useful next evidence": "Measured reproductive or fitness outcomes",
            },
            {
                "Current conclusion or boundary": "Populations Maintained is 0.70 at country scale",
                "What remains unresolved": "Persistence and range loss within countries",
                "Most useful next evidence": "Current, finer sub-country occurrence records",
            },
            {
                "Current conclusion or boundary": "The workflow already samples thousands of SNPs",
                "What remains unresolved": "Whether marker count or individual count limits N_e",
                "Most useful next evidence": "Prioritize individuals: extra SNPs cannot replace independent genomes",
            },
        ]
    )
    st.dataframe(evidence_map, width="stretch", hide_index=True)
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
