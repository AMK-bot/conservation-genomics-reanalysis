#!/usr/bin/env Rscript
# Rarefied allelic richness (+ basic.stats Ho/Hs/Fis cross-check) per population.
# Input: a hierfstat genotype table from scripts/python/to_hierfstat.py
#   (col 1 = pop, remaining cols = loci coded 11/12/22, NA missing).
# allelic.richness rarefies to the smallest population's sample size
# (El Mousadik & Petit 1996) -> diversity comparable across unequal n.
#
# Run with `Rscript --vanilla` for a reproducible startup that uses only the
# conda-owned R library (plan: renv dropped, R conda-owned).
suppressMessages(library(hierfstat))

args <- commandArgs(trailingOnly = TRUE)
in_tsv   <- args[1]   # hierfstat table
out_ar   <- args[2]   # per-population rarefied allelic richness
out_bs   <- args[3]   # per-population basic.stats (Ho/Hs/Fis)

dat <- read.delim(in_tsv, row.names = 1, colClasses = "character",
                  na.strings = "NA", check.names = FALSE)
pop <- dat[[1]]
loci <- data.frame(lapply(dat[-1], as.integer))            # genotypes as integers
hf <- data.frame(pop = pop, loci)

ar <- allelic.richness(hf)
ar_pop <- data.frame(population = colnames(ar$Ar),
                     rarefied_allelic_richness = round(colMeans(ar$Ar, na.rm = TRUE), 5),
                     rarefied_to_n = ar$min.all / 2,       # min.all = alleles; /2 = individuals
                     row.names = NULL)
write.table(ar_pop, out_ar, sep = "\t", quote = FALSE, row.names = FALSE)

bs <- basic.stats(hf)
ho <- colMeans(bs$Ho, na.rm = TRUE); hs <- colMeans(bs$Hs, na.rm = TRUE)
fis <- colMeans(bs$Fis, na.rm = TRUE)
bs_pop <- data.frame(population = names(ho),
                     Ho = round(ho, 5), Hs = round(hs, 5), Fis = round(fis, 5),
                     row.names = NULL)
write.table(bs_pop, out_bs, sep = "\t", quote = FALSE, row.names = FALSE)

cat("allelic richness rarefied to n =", ar$min.all / 2, "individuals\n")
print(ar_pop)
