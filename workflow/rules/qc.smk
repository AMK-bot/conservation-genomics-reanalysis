# workflow/rules/qc.smk — Phase 1: QC & filtering (plan §4)
#
# Two callsets from the raw peafowl VCF:
#   Set A (structure/N_e): biallelic SNPs -> depth/GQ/missingness -> MAC>=3
#                          -> per-population HWE -> LD-prune (--indep-pairwise)
#   Set B (diversity):     lightly filtered, no MAF
# Plus the kin/duplicate screen (PLINK2 --king) — run BEFORE structure/N_e so that
# undetected relatives don't bias everything downstream.
#
# Every threshold comes from config["peafowl"]["filtering"] / ["kinship"].
# Stub — rules implemented in Phase 1.

# rule normalize_biallelic:        # bcftools norm -m -any -> biallelic SNPs
# rule filter_callset_A:           # per-preset depth/GQ/missingness/MAC + per-pop HWE
# rule filter_callset_B:           # lightly filtered, no MAF (diversity)
# rule ld_prune:                   # PLINK --indep-pairwise {config ld_prune}
# rule kin_screen:                 # PLINK2 --make-king; drop relatives >= cutoff
