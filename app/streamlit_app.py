"""Fragility Explorer — how fragile is the green peafowl's conservation verdict?

Green peafowl N_e / GBF verdict under analyst choices. Two knobs:
    filtering stringency  x  structure (modeled per_population / ignored pooled)
-> live N_e + 90% CI + threshold reading (Confidently below / Indeterminate / Confidently above).

This app ONLY READS precomputed workflow outputs — the cube
(results/cube/results_cube.parquet), the GBF indicator tables (results/tables/gbf_*.tsv),
and the static figures (results/figures/*.png). All heavy bioinformatics runs in the
Snakemake DAG, never here (plan §2, §6). Rebuild inputs with
`snakemake --snakefile workflow/Snakefile phase5b --cores 4 --resources mem_mb=7000`.

Tabs: N_e / GBF verdict (the two-knob badge, both GBF Goal-A indicators, robustness,
GONE2 context, and the Phase-5B design landscape) · Structure & diversity (PCA / ADMIXTURE /
damage-aware sample contrast) · Wolf load & ROH (association and localization) · About
(limitations, frozen claim trace, optional decisions, and reproducibility).
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
# is untouched); the app describes only confidence relative to the N_e target, not overall security.
STATE_LABEL = {"pass": "Confidently above target", "fail": "Confidently below target",
               "indeterminate": "Indeterminate", "missing": "n/a"}
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
        st.info(
            f"`{p}` not built yet — run "
            "`snakemake --snakefile workflow/Snakefile phase5b --cores 4 --resources mem_mb=7000`."
        )


CFG = load_config()
try:
    NE_THRESHOLD = CFG["gbf"]["ne_threshold"]
except Exception:
    NE_THRESHOLD = 500

st.set_page_config(page_title="Fragility Explorer", page_icon="🦚", layout="wide")
st.title("🦚 Fragility Explorer")
st.caption(
    "How fragile is the green peafowl's conservation verdict to analyst choices? "
    "The estimates and three-state per-population reading against the international N_e > 500 target "
    "move as filtering changes; the pooled result is a cautionary structure contrast, not a GBF "
    "verdict. This claims **risk**, not demonstrated "
    "inbreeding depression — see the *About* tab."
)
st.caption(
    "**Phase 5B status: COMPLETE.** This app only looks up generated workflow tables and the frozen "
    "six-row claim trace. Clean verification: `results/PHASE5B_REPRODUCIBILITY.md`."
)

if not CUBE.exists():
    st.warning(
        "The results cube hasn't been built yet. Run the workflow first:\n\n"
        "```bash\nsnakemake --snakefile workflow/Snakefile phase5b --cores 4 "
        "--resources mem_mb=7000\n```\n\n"
        f"Expected at `{CUBE}`."
    )
    st.stop()

cube = load_cube()
ne500 = load_tsv("gbf_ne500.tsv")
robust = load_tsv("gbf_robustness.tsv")
pm = load_tsv("gbf_populations_maintained.tsv")
summary = load_tsv("gbf_summary.tsv")
scorecard = load_tsv("fragility_scorecard.tsv")
wolf_associations = load_tsv("wolf_froh_load_associations.tsv")
wolf_rank_stability = load_tsv("wolf_froh_load_rank_stability.tsv")
wolf_roh_localization = load_tsv("wolf_roh_localization_cohort.tsv")
damage_effects = load_tsv("peafowl_damage_effects.tsv")
ne_design_summary = load_tsv("peafowl_ne_design_summary.tsv")
phase5b_claims = load_tsv("phase5b_claim_trace.tsv")
phase5b_decisions = load_tsv("phase5b_optional_decisions.tsv")

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
                "Read off the point estimate; **Indeterminate** when the 90% CI straddles "
                f"{NE_THRESHOLD} or the estimator did not converge. That indeterminate band *is* "
                "the fragility story, not a defect — at n = 7/10/5 many cells cannot resolve it. "
                "(These are conservation-risk readings, not a software pass/fail.)")

    st.divider()

    # ── Indicator 1: N_e > threshold (genomic, from the cube) ──────────────────────
    st.subheader(f"GBF genetic indicator 1 — populations with N_e > {NE_THRESHOLD}")
    if ne500 is not None:
        r = ne500.query("filter_preset == @filt")
        if not r.empty:
            r = r.iloc[0]
            i1, i2, i3 = st.columns(3)
            i1.metric(f"🟢 Confidently above target (at {filt})", f"{int(r['n_pass'])}/{int(r['n_pops'])}")
            i2.metric("🟠 Indeterminate", int(r["n_indeterminate"]))
            i3.metric("🔴 Confidently below target", int(r["n_fail"]))
            st.caption(
                f"Fraction meeting N_e > {NE_THRESHOLD} = **{r['fraction_pass']}**; optimistic ceiling if "
                f"every indeterminate case resolved upward = {r['fraction_not_fail']}. The headline indicator "
                "is that fraction — here **0 across every preset**.")
    else:
        st.info(
            "`gbf_ne500.tsv` not built — run "
            "`snakemake --snakefile workflow/Snakefile phase3 --cores 4 "
            "--resources mem_mb=7000`."
        )

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
            "converge under stricter filters, though its reading stays Indeterminate throughout). "
            "That fragility is the finding, honestly reported.")
    else:
        st.info(
            "`gbf_robustness.tsv` not built — run "
            "`snakemake --snakefile workflow/Snakefile phase3 --cores 4 "
            "--resources mem_mb=7000`."
        )

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
        st.info(
            "`fragility_scorecard.tsv` not built — run "
            "`snakemake --snakefile workflow/Snakefile phase5a1 --cores 4 "
            "--resources mem_mb=7000`."
        )

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
        "passes N_e > 500. **Still present ≠ confidence that a genomic proxy clears its "
        "threshold.** The indicators answer different questions and must be reported together.")
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
        f"N_e = {NE_THRESHOLD} corresponds to an illustrative census N_c ≈ **{nc_thr}** at an "
        f"N_e:N_c = {ratio} (Frankham). Range-wide mature count is ~**{nc_mature}** (EN, decreasing) "
        "— nominally above that proxy, **but it is the wrong denominator for a per-population "
        "indicator**. No matched population-level census denominator exists for the sampled cells, "
        "and N_e:N_c is not a fixed conversion. This contrast demonstrates denominator sensitivity; "
        "it does not establish an expected or measured population-specific N_e:N_c relationship.")

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

    st.divider()
    st.subheader("Study-design calibration — scenarios are not a sampling guarantee")
    st.markdown(
        "#### 0/15 tested designs resolve both predeclared resolution truths "
        "(N_e=250 and 1,000)"
    )
    st.caption(
        "The frozen claim trace reports no qualifying simulated design. Seeded neutral scenarios "
        "have known N_e. The predeclared resolution truths N_e=250 and 1,000 separate "
        "correct-confident, incorrect-confident, and indeterminate outcomes; N_e=100 is retained "
        "as an additional non-boundary diagnostic, while true N_e=500 separates boundary "
        "confident pass, boundary confident fail, and indeterminate outcomes. Empirical downsampling "
        "has no known truth and is shown only within each population's observed sample size. This "
        "calibrates the implemented estimator/decision pipeline; it is not an empirical sample-size "
        "prescription."
    )
    if ne_design_summary is None:
        st.info(
            "Phase-5B N_e design tables not built — run "
            "`snakemake --snakefile workflow/Snakefile phase5b --cores 4 "
            "--resources mem_mb=7000`."
        )
    else:
        scenario_design = ne_design_summary.loc[
            ne_design_summary["analysis_type"].astype(str).eq("scenario")
        ].copy()
        nd1, nd2, nd3 = st.columns(3)
        with nd1:
            design_truth = st.selectbox(
                "Known scenario N_e",
                sorted(int(value) for value in scenario_design["true_ne"].dropna().unique()),
                index=1,
            )
        with nd2:
            design_markers = st.selectbox(
                "Scenario marker density",
                sorted(int(value) for value in scenario_design["marker_density"].unique()),
                index=1,
            )
        with nd3:
            if int(design_truth) == 500:
                design_outcomes = [
                    "boundary_confident_pass_rate", "indeterminate_rate",
                    "boundary_confident_fail_rate",
                ]
            else:
                design_outcomes = [
                    "correct_confident_rate", "indeterminate_rate", "incorrect_confident_rate",
                ]
            design_metric = st.selectbox(
                "Decision outcome",
                design_outcomes,
                format_func=lambda value: value.replace("_rate", "").replace("_", " ").title(),
            )
        design_view = scenario_design.loc[
            scenario_design["true_ne"].astype(float).eq(float(design_truth))
            & scenario_design["marker_density"].astype(int).eq(design_markers)
        ].sort_values("sample_size")
        st.line_chart(design_view.set_index("sample_size")[[design_metric]], color="#2e7567")
        if int(design_truth) == 500:
            display_columns = [
                "sample_size", "marker_density", "n_attempted", "boundary_confident_pass_rate",
                "boundary_confident_pass_ci_low", "boundary_confident_pass_ci_high",
                "indeterminate_rate", "boundary_confident_fail_rate",
                "boundary_confident_fail_ci_low", "boundary_confident_fail_ci_high",
                "execution_failure_rate",
            ]
        else:
            display_columns = [
                "sample_size", "marker_density", "n_attempted", "correct_confident_rate",
                "correct_confident_ci_low", "correct_confident_ci_high",
                "indeterminate_rate", "incorrect_confident_rate", "execution_failure_rate",
            ]
        st.dataframe(design_view[display_columns], width="stretch", hide_index=True)
        st.caption(
            "Rates include every attempted replicate. True N_e=500 is a boundary case and is never "
            "scored as correct or incorrect. Empirical observed-n repetitions reuse the single available "
            "individual subset and lower-n subsets overlap, so their Wilson bands describe seeded "
            "subset/marker-panel sensitivity, not independent biological-sampling uncertainty."
        )
        show_figure(
            "peafowl_ne_design.png",
            "Known-truth scenario resolution (top) and observed-range empirical convergence (bottom).",
        )

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
    st.subheader("Diversity & museum–modern contrast")
    c, d = st.columns(2)
    with c:
        show_figure("diversity_perpop.png", "Per-population Ho / He / allelic richness — Thailand "
                                            "(n=5) lowest; Yunnan shows a heterozygote deficit (Fis 0.086).")
    with d:
        show_figure("temporal_diversity.png", "Museum vs modern — the museum–modern direction is "
                                              "weak and metric-dependent (π/Ho weakly museum>modern; "
                                              "He/AR essentially flat). A contrast direction, not a claim.")

    st.divider()
    st.subheader("Damage-aware museum–modern falsification")
    st.markdown("#### 1/4 metrics is fully direction-concordant")
    st.caption(
        "All SNPs are compared with transversions only, all 462 possible 5-versus-6 labels, six "
        "equal-n modern omissions, and 11 leave-one-individual checks. A persistent geographic "
        "mismatch still prevents a temporal-erosion claim under any numerical outcome. Diversity "
        "differences are not fitness measurements."
    )
    if damage_effects is None:
        st.info(
            "Phase-5B damage-aware tables not built — run "
            "`snakemake --snakefile workflow/Snakefile phase5b --cores 4 "
            "--resources mem_mb=7000`."
        )
    else:
        damage_variant = st.radio(
            "Variant set for the effect table",
            ["all_snp", "transversion_only"],
            horizontal=True,
            format_func=lambda value: "All SNPs" if value == "all_snp" else "Transversions only",
        )
        damage_view = damage_effects.loc[
            damage_effects["variant_set"].astype(str).eq(damage_variant)
        ].copy()
        damage_view["effect (museum − modern)"] = damage_view["effect_museum_minus_modern"]
        st.dataframe(
            damage_view[[
                "metric", "museum_value", "modern_value", "effect (museum − modern)",
                "ci_low", "ci_high", "exact_permutation_p_two_sided", "direction",
                "equal_n_same_direction_n", "equal_n_cases_n",
                "leave_one_same_direction_n", "leave_one_cases_n",
            ]],
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "Confidence intervals come from seeded 5-Mb chromosome blocks; exact p-values use all "
            "462 allocations. Effect sizes and unexpected directions remain visible."
        )
        show_figure(
            "peafowl_damage_falsification.png",
            "Damage-aware effect intervals and individual-influence diagnostics.",
        )

# ══════════════════════════════════════════════════════════════════════════════════
# TAB 3 — wolf genetic load + ROH (Phase 4): two knobs (GERP, ROH-length) move the readings
# ══════════════════════════════════════════════════════════════════════════════════
with tab_wolf:
    st.subheader("🐺 Scandinavian wolf — load and ROH autozygosity proxies")
    st.caption(
        "A population founded by a few individuals (~1983) and inbred since. Two analyst knobs move "
        "the readings: the **GERP** conservation score that defines the analyzed site class, and the "
        "**ROH length** that defines the autozygosity proxy. *Realized* load is the GERP-weighted "
        "homozygous derived-allele contribution; *masked* load is the corresponding heterozygous "
        "contribution. The deposited "
        "cohorts show different realized-versus-masked patterns; Phase 5B tests individual-level "
        "association and generic-homozygosity coupling without claiming causation.")
    wolf_load = load_tsv("wolf_load.tsv")
    wolf_roh = load_tsv("wolf_roh.tsv")
    if wolf_load is None or wolf_roh is None:
        st.info(
            "Wolf tables not built yet — run `snakemake --snakefile workflow/Snakefile phase4 "
            "--cores 4 --resources mem_mb=7000` (streams the 11 GB VCF per chromosome; ~30 min)."
        )
    else:
        k1, k2 = st.columns(2)
        with k1:
            gvals = sorted(wolf_load["THRES"].unique())
            gerp = st.select_slider("GERP threshold — include sites with RS >", options=gvals,
                                    value=4.0 if 4.0 in gvals else gvals[-1])
        with k2:
            rvals = sorted(wolf_roh["min_length_mb"].unique())
            roh_cut = st.select_slider("ROH length cutoff (Mb) — autozygosity proxy",
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
            f"At GERP>{gerp:g}, GERP-weighted, ancestral-polarized derived-allele load per individual. "
            "Raising the GERP threshold keeps only the most-conserved sites — the absolute load shrinks, "
            "but the realized-vs-masked *pattern* is the robust signal (the wolf-side fragility check).")

        st.markdown("#### ROH autozygosity proxy — F_ROH by time period")
        rh = wolf_roh[wolf_roh["min_length_mb"] == roh_cut]
        froh = rh.groupby("POP")["F_ROH"].mean().sort_index().rename("F_ROH").to_frame()
        st.bar_chart(froh, color="#0d7d80")
        r1, r2 = st.columns(2)
        r1.metric(f"Mean F_ROH (ROH ≥ {roh_cut:g} Mb)", f"{rh['F_ROH'].mean():.3f}")
        r2.metric("Long-ROH F_ROH proxy (≥ 1.5 Mb)", f"{rh['froh_long_recent'].mean():.3f}")
        st.caption(
            f"Fraction of the autosomes in runs of homozygosity ≥ {roh_cut:g} Mb. Long ROH (≥ 1.5 Mb) "
            "serve as a proxy for more recent autozygosity, subject to recombination and map "
            "assumptions; raising the cutoff shifts that proxy away from shorter background "
            "homozygosity. F_ROH and realized load co-vary in these deposited cohorts; "
            "the individual-level panel below quantifies that association and its negative control.")

        st.divider()
        st.subheader("Individual F_ROH–load robustness surface")
        st.markdown("#### 15/15 primary and 15/15 partial realized-load intervals are above zero")
        st.caption(
            "All 211 individuals are evaluated in the frozen 3 GERP × 5 ROH grid. Associations use "
            "within-cohort ranks, cohort-stratified bootstrap intervals, and within-cohort "
            "permutations. The partial model controls generic GERP-covered homozygosity. These are "
            "associations among genomic proxies, not fitness or causal effects."
        )
        if wolf_associations is None or wolf_rank_stability is None:
            st.info(
                "Phase-5B wolf robustness tables not built — run "
                "`snakemake --snakefile workflow/Snakefile phase5b --cores 4 "
                "--resources mem_mb=7000`."
            )
        else:
            selected_cell = wolf_associations.loc[
                wolf_associations["gerp_threshold"].astype(float).eq(float(gerp))
                & wolf_associations["roh_cutoff_mb"].astype(float).eq(float(roh_cut))
            ].copy()
            display_assoc = selected_cell[[
                "outcome", "model", "coefficient", "ci_low", "ci_high",
                "permutation_p_two_sided", "direction_matches_expected",
            ]]
            st.dataframe(display_assoc, width="stretch", hide_index=True)
            partial_realized = wolf_associations.loc[
                wolf_associations["outcome"].astype(str).eq("realized_load")
                & wolf_associations["model"].astype(str).str.contains("partial")
            ]
            positive_cells = int(partial_realized["ci_low"].gt(0).sum())
            min_spearman = float(wolf_rank_stability["spearman_rho"].min())
            min_overlap = float(wolf_rank_stability["top_overlap_fraction"].min())
            wa, wb, wc = st.columns(3)
            wa.metric("Partial realized CI > 0", f"{positive_cells}/15")
            wb.metric("Minimum rank Spearman", f"{min_spearman:.3f}")
            wc.metric("Minimum top-set overlap", f"{100 * min_overlap:.1f}%")
            show_figure(
                "wolf_froh_load_surface.png",
                "Primary and generic-homozygosity-adjusted associations across the complete 3 × 5 grid.",
            )
            show_figure(
                "wolf_froh_load_forest.png",
                "Cohort-aware individual scatter and primary association intervals.",
            )

        st.divider()
        st.subheader("ROH localization of homozygous GERP-weighted derived-allele burden")
        st.markdown("#### §13.4 IMPLEMENT · 24/24 long-ROH population × GERP cells beyond null")
        st.caption(
            "This panel asks whether homozygous derived GERP burden falls inside called ROH more "
            "often than expected after preserving each individual's ROH architecture and circularly "
            "shifting it within chromosomes. Rates use **eligible polarized GERP-threshold SNP "
            "genotype calls** as their opportunity denominator. These are assayed variant calls, "
            "not callable genomic bases, so SNP ascertainment remains a limitation. The shaded/null interval is the seeded "
            "circular-shift distribution, not a confidence interval for a causal effect."
        )
        localization_columns = {
            "POP", "gerp_threshold", "roh_cutoff_mb", "n_ind",
            "inside_burden_rate", "outside_burden_rate", "rate_ratio",
            "log2_enrichment", "null_median_log2_enrichment", "null_ci_low",
            "null_ci_high", "permutation_p_two_sided", "direction", "status",
        }
        if wolf_roh_localization is None:
            st.info(
                "Phase-5B ROH-localization table not built — run "
                "`snakemake --snakefile workflow/Snakefile phase5b --cores 4 "
                "--resources mem_mb=7000`."
            )
        elif wolf_roh_localization.empty or not localization_columns.issubset(
            wolf_roh_localization.columns
        ):
            st.warning(
                "Phase-5B ROH-localization output is empty or has an unexpected schema; "
                "rebuild it with `snakemake --snakefile workflow/Snakefile phase5b --cores 4 "
                "--resources mem_mb=7000`."
            )
        else:
            lc1, lc2 = st.columns(2)
            localization_gerp_values = sorted(
                float(value) for value in wolf_roh_localization["gerp_threshold"].dropna().unique()
            )
            localization_roh_values = sorted(
                float(value) for value in wolf_roh_localization["roh_cutoff_mb"].dropna().unique()
            )
            with lc1:
                localization_gerp = st.selectbox(
                    "Localization GERP threshold",
                    localization_gerp_values,
                    index=(
                        localization_gerp_values.index(4.0)
                        if 4.0 in localization_gerp_values
                        else len(localization_gerp_values) - 1
                    ),
                    format_func=lambda value: f"GERP > {value:g}",
                )
            with lc2:
                localization_roh = st.selectbox(
                    "Localization ROH cutoff (Mb)",
                    localization_roh_values,
                    index=(
                        localization_roh_values.index(1.5)
                        if 1.5 in localization_roh_values
                        else 0
                    ),
                    format_func=lambda value: f"ROH ≥ {value:g} Mb",
                )

            localization_view = wolf_roh_localization.loc[
                wolf_roh_localization["gerp_threshold"].astype(float).eq(localization_gerp)
                & wolf_roh_localization["roh_cutoff_mb"].astype(float).eq(localization_roh)
            ].copy().sort_values("POP")
            localization_view = localization_view.rename(columns={
                "POP": "cohort",
                "n_ind": "individuals",
                "inside_burden_rate": "inside-ROH burden / eligible genotype call",
                "outside_burden_rate": "outside-ROH burden / eligible genotype call",
                "rate_ratio": "inside : outside rate",
                "log2_enrichment": "observed log2 enrichment",
                "null_median_log2_enrichment": "circular-shift null median",
                "null_ci_low": "circular-shift lower bound",
                "null_ci_high": "circular-shift upper bound",
                "permutation_p_two_sided": "circular-shift p (two-sided)",
            })
            st.dataframe(
                localization_view[[
                    "cohort", "individuals", "inside-ROH burden / eligible genotype call",
                    "outside-ROH burden / eligible genotype call", "inside : outside rate",
                    "observed log2 enrichment", "circular-shift null median",
                    "circular-shift lower bound", "circular-shift upper bound",
                    "circular-shift p (two-sided)", "direction", "status",
                ]],
                width="stretch",
                hide_index=True,
            )
            show_figure(
                "wolf_roh_localization_ribbon.png",
                "Observed inside-versus-outside ROH enrichment across every cutoff, with the "
                "within-chromosome circular-shift null envelope.",
            )
            default_localization_cutoff = float(
                CFG.get("wolf", {}).get("roh", {}).get("long_roh_threshold_mb", 1.5)
            )
            if math.isclose(localization_roh, default_localization_cutoff):
                show_figure(
                    "wolf_roh_localization_forest.png",
                    f"Cohort localization at the prespecified {default_localization_cutoff:g}-Mb "
                    "ROH cutoff; intervals are circular-shift null ranges.",
                )
            st.caption(
                "The result localizes a genotype-derived burden within observed ROH. It does **not** "
                "show that ROH caused the burden, and the dataset contains no fitness phenotype, so "
                "it cannot demonstrate inbreeding depression or any fitness consequence."
            )

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
  cells are *Indeterminate*. The point of the tool is to show how that uncertainty interacts with
  analyst choices — the fragility thesis — not to pin a single number.
- **currentNe2 is the only automated estimator.** GONE2 is a recent-trajectory *context* panel
  (different time horizon, borrowed recombination rate). NeEstimator-LDNe is a planned optional
  **manual** GUI comparison that has not been run and is never wired into this badge.
- **Ascertainment & coverage caveats** apply per the report. Only 1/4 diversity metrics is fully
  direction-concordant, and period remains confounded with geography, so this is a sample contrast,
  not temporal genetic erosion.
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
                "Current conclusion or boundary": "Several peafowl N_e cells remain indeterminate at n=7/10/5",
                "What remains unresolved": "Fragile precision and convergence of population-level estimates",
                "Most useful next evidence": (
                    "A prospectively calibrated population-level design; 0/15 tested scenario designs "
                    "qualified, so this analysis supplies no exact sample-size prescription"
                ),
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
                "Most useful next evidence": (
                    "Test more independent genomes per population before adding SNPs: marker count "
                    "alone cannot replace individuals, and the neutral scenarios provide no exact "
                    "sample-size prescription"
                ),
            },
        ]
    )
    st.dataframe(evidence_map, width="stretch", hide_index=True)
    st.subheader("Phase-5B claim trace and optional-study decisions")
    st.markdown(
        "**Frozen decisions:** §13.4 **IMPLEMENT** after the 15/15 gate; §13.5 "
        "**DEFER_DUPLICATES_SOURCE_STUDY** with 0/1 independent definitions and a 211/211 "
        "common-sample intersection. Section 13.5 reopens only with at least one annotation "
        "definition independent of the source classes, at least 0.95 common-sample coverage, "
        "and at least 0.90 auditable callable-denominator coverage. Predicted-impact classes "
        "remain risk proxies, not proven harmful variants."
    )
    if phase5b_claims is None:
        st.info(
            "Phase-5B claim trace not built — run "
            "`snakemake --snakefile workflow/Snakefile phase5b --cores 4 "
            "--resources mem_mb=7000`."
        )
    else:
        trace_columns = [
            "section", "headline", "claim_status", "estimate", "uncertainty",
            "what_changes_mind", "result_table", "validator", "report_anchor", "workflow_rule",
        ]
        st.dataframe(
            phase5b_claims[[column for column in trace_columns if column in phase5b_claims.columns]],
            width="stretch",
            hide_index=True,
        )
    if phase5b_decisions is not None:
        st.caption(
            "A no-go or deferral is a valid scientific result when the observed gate and exact "
            "reopening condition reconcile."
        )
        st.dataframe(
            phase5b_decisions[[
                "section", "study", "decision", "observed_value", "required_operator",
                "required_value", "unit", "reopen_condition",
            ]],
            width="stretch",
            hide_index=True,
        )
    st.subheader("Reproducibility")
    st.markdown(
        """
Every analytical value here is built by the Snakemake DAG from tracked inputs: two public deposits,
the versioned curated Populations Maintained table, and transparent bounded neutral simulations.
This app reads the outputs only. The clean-build, bounded-memory, science-hash, manifest, and no-op evidence is in
`results/PHASE5B_REPRODUCIBILITY.md`.

```bash
micromamba create -n congen -f environment.lock.yml   # 8 GB / Apple-Silicon: micromamba, not classic conda
micromamba activate congen
snakemake --snakefile workflow/Snakefile phase5b --cores 4 --resources mem_mb=7000  # Phases 1–5B
streamlit run app/streamlit_app.py                     # this tool
```
"""
    )
    st.caption("Datasets: green peafowl — Dong et al. 2021 (Dryad 10.5061/dryad.ffbg79ctc). "
               "Wolf load chapter (Phase 4) — Smeds & Ellegren 2022 (Dryad 10.5061/dryad.7m0cfxpzj).")
