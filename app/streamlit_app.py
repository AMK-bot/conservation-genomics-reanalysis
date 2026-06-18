"""Fragility Explorer — how fragile is the conservation verdict?

Green peafowl N_e / GBF pass-fail under analyst choices. Three knobs:
    filtering stringency  x  N_e method  x  structure (modeled / ignored)
-> live N_e + CI + treaty pass/fail verdict.

This app ONLY reads results/cube/results_cube.parquet. All heavy bioinformatics
runs in the Snakemake workflow, never here (plan §2, §6).
"""
from pathlib import Path

import pandas as pd
import streamlit as st

CUBE = Path("results/cube/results_cube.parquet")
NE_THRESHOLD = 500  # GBF N_e > 500 genetic-diversity indicator

st.set_page_config(page_title="Fragility Explorer", layout="wide")
st.title("🦚 Fragility Explorer")
st.caption(
    "How fragile is the green peafowl's conservation verdict to analyst choices? "
    "This claims *risk*, not depression — see the limitations panel."
)

if not CUBE.exists():
    st.warning(
        "The results cube hasn't been built yet. Run the workflow first:\n\n"
        "```bash\nsnakemake --use-conda --cores 4\n```\n\n"
        f"Expected at `{CUBE}`."
    )
    st.stop()

cube = pd.read_parquet(CUBE)

# ── The three knobs ────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
with c1:
    filt = st.select_slider("Filtering stringency", options=["lenient", "standard", "strict"], value="standard")
with c2:
    method = st.selectbox("N_e method", sorted(cube["ne_method"].unique()))
with c3:
    structure = st.radio("Population structure", ["per_population", "pooled"], horizontal=True)

# ── Verdict ──────────────────────────────────────────────────────────────────
sel = cube.query("filter_preset == @filt and ne_method == @method and structure_mode == @structure")
if sel.empty:
    st.error("No cube cell for that combination yet.")
    st.stop()

ne = float(sel["ne"].iloc[0])
ci_lo, ci_hi = float(sel["ci_low"].iloc[0]), float(sel["ci_high"].iloc[0])
passes = ne > NE_THRESHOLD

st.metric("Contemporary N_e", f"{ne:,.0f}", help=f"95% CI: {ci_lo:,.0f} – {ci_hi:,.0f}")
st.subheader(("✅ PASS" if passes else "❌ FAIL") + f"  — N_e {'>' if passes else '≤'} {NE_THRESHOLD}")

st.divider()
with st.expander("Limitations"):
    st.markdown(
        "- Small per-population n → wide N_e CIs (a *feature* of the fragility thesis).\n"
        "- We report **risk**, not demonstrated inbreeding depression.\n"
        "- Ascertainment and low-coverage caveats per the report."
    )
# Tabs for structure (PCA/ADMIXTURE) and the wolf load chapter are added in Phase 3/4.
