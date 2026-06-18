# workflow/rules/load.smk — Phase 4: wolf genetic load + ROH (plan §7)
#
# CLI-streaming-first — the 12 GB VCF never enters RAM:
#   per-chromosome `bcftools view` splits (on USB) -> stream-filter
#   ROH:  `bcftools roh` per sample/chr (HMM, low RAM); long (recent) vs short (ancient); F_ROH
#   load: stream VEP impact classes + GERP; polarize derived alleles with deposited outgroups;
#         tally realized (homozygous derived-deleterious) vs masked (heterozygous) per individual
# Uses config["wolf"].
# Stub — rules implemented in Phase 4.

# rule split_by_chrom:     # bcftools view -r {chrom} (on USB)
# rule roh:                # bcftools roh per sample/chrom -> F_ROH
# rule classify_roh:       # long vs short ROH
# rule genetic_load:       # VEP x GERP -> realized vs masked load per individual
