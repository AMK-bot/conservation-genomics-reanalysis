# workflow/rules/gbf.smk — Phase 3: GBF indicators + robustness (plan §6)  ← MVP
#
# From the cube: the N_e > 500 indicator (proportion of populations above threshold)
# + "Populations Maintained"; contrast genomic N_e with the census proxy (N_c >= 5000).
# Robustness (angle C): quantify how the pass/fail verdict moves across the cube.
# Uses config["gbf"].
# Stub — rules implemented in Phase 3.

# rule gbf_ne500:          # proportion of populations with N_e > 500, per cube cell
# rule robustness:         # verdict stability across the filter x method x structure cube
