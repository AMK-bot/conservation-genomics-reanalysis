# workflow/rules/ne.smk — Phase 2: contemporary N_e + the results cube (plan §5)
#
# THE ENGINEERING CORE. The parameter sweep that builds the fragility cube:
#   {filter preset (lenient/standard/strict)} x {N_e method} x {structure on/off}
#       -> {N_e, CI}  -> results/cube/results_cube.parquet
#
# currentNe2 (no genetic map needed -> workhorse) + NeEstimator-LDNe across PCrit
# (manual cross-check). GONE2 = recent-trajectory context only (GBF excludes it from
# the contemporary indicator). Uses config["peafowl"]["ne"] and config["cube"].
# Stub — rules implemented in Phase 2.

# rule currentne2:         # one (preset x structure_mode) cell
# rule ldne:               # NeEstimator-LDNe across PCrit (cross-check)
# rule assemble_cube:      # tidy all cells -> results_cube.parquet
