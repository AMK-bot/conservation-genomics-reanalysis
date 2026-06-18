# workflow/rules/structure.smk — Phase 1: population structure (plan §4)
#
# PCA (scikit-allel or SNPRelate) + ADMIXTURE over a grid of K with replicate seeds.
# Present multiple K, triangulate with PCA, don't over-interpret "best K".
# Uses config["peafowl"]["structure"].
# Stub — rules implemented in Phase 1.

# rule pca:                # scikit-allel / SNPRelate on Set A
# rule admixture:          # ADMIXTURE over K x seed grid (+ CV error)
# rule admixture_cv:       # collate cross-validation error across K
