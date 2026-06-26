"""Fragility Explorer — how fragile is the conservation verdict?

Green peafowl N_e / GBF verdict under analyst choices. Two knobs:
    filtering stringency  x  structure (modeled per_population / ignored pooled)
-> live N_e + 90% CI + treaty pass / fail / indeterminate verdict (currentNe2).

This app ONLY reads results/cube/results_cube.parquet. All heavy bioinformatics
runs in the Snakemake workflow, never here (plan §2, §6). Phase 3 adds the GONE2
recent-trajectory panel + structure/diversity + wolf tabs.
"""
import math
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

CUBE = Path("results/cube/results_cube.parquet")
CONFIG = Path("config/config.yaml")
# GBF N_e indicator threshold — single source of truth is config (the cube's gbf_state is built
# from it); read it here so the badge label can't drift from the verdict. Fallback if config absent.
try:
    NE_THRESHOLD = yaml.safe_load(CONFIG.read_text())["gbf"]["ne_threshold"]
except Exception:
    NE_THRESHOLD = 500


def _fmt_ci(x):
    """CI bound -> display: NaN (non-convergence) -> n/a, inf (unbounded) -> ∞, else thousands."""
    if math.isnan(x):
        return "n/a"
    if math.isinf(x):
        return "∞"
    return f"{x:,.0f}"

st.set_page_config(page_title="Fragility Explorer", layout="wide")
st.title("🦚 Fragility Explorer")
st.caption(
    "How fragile is the green peafowl's conservation verdict to analyst choices? "
    "This claims *risk*, not depression — see the limitations panel."
)

if not CUBE.exists():
    st.warning(
        "The results cube hasn't been built yet. Run the workflow first:\n\n"
        "```bash\nsnakemake --cores 4\n```\n\n"
        f"Expected at `{CUBE}`."
    )
    st.stop()

cube = pd.read_parquet(CUBE)

# ── The two knobs (filter x structure); Phase 3 adds the GONE2 panel + tabs ─────
# ponytail: minimal Phase-2 read of the cube so it's demonstrably consumable; the full
# explorer (population selector polish, GONE2 panel, structure/wolf tabs) is the Phase-3 build.
c1, c2 = st.columns(2)
with c1:
    filt = st.select_slider("Filtering stringency", options=["lenient", "standard", "strict"], value="standard")
with c2:
    structure = st.radio("Population structure", ["per_population", "pooled"], horizontal=True)

sel = cube.query("filter_preset == @filt and structure_mode == @structure")
if sel.empty:
    st.error("No cube cell for that combination yet.")
    st.stop()

if structure == "per_population":
    pop = st.radio("Population", sorted(sel["population"]), horizontal=True)
    sel = sel.query("population == @pop")

# ── Verdict (three-state, precomputed in the workflow) ─────────────────────────
row = sel.iloc[0]
ne = float(row["ne_point"]); ci_lo, ci_hi = float(row["ci_low"]), float(row["ci_high"])
state = row["gbf_state"]
ne_txt = "—" if math.isnan(ne) else ("∞" if math.isinf(ne) else f"{ne:,.0f}")  # NaN -> em dash, inf -> ∞

st.metric("Contemporary N_e (cross-chromosome)", ne_txt,
          help=f"90% CI: {_fmt_ci(ci_lo)} – {_fmt_ci(ci_hi)}")
if structure == "pooled":
    # Pooled (population = ALL) is the Wahlund contrast, never a GBF input -> show no pass/fail badge.
    st.subheader("⚖️ Wahlund contrast — not a GBF verdict")
    st.caption("Pooling across structured populations biases N_e LOW (Wahlund). This is a cautionary "
               "contrast for the per-population estimates, never a GBF pass/fail input.")
else:
    badge = {"pass": "✅ PASS", "fail": "❌ FAIL", "indeterminate": "⚠️ INDETERMINATE"}[state]
    st.subheader(f"{badge}  — vs N_e = {NE_THRESHOLD} (GBF)")

st.divider()
with st.expander("Limitations"):
    st.markdown(
        "- Small per-population n → wide N_e CIs (a *feature* of the fragility thesis).\n"
        "- We report **risk**, not demonstrated inbreeding depression.\n"
        "- Ascertainment and low-coverage caveats per the report."
    )
# Tabs for structure (PCA/ADMIXTURE) and the wolf load chapter are added in Phase 3/4.
