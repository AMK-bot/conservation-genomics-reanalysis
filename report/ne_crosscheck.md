# NeEstimator-LDNe — planned manual field-standard comparison (plan §5)

**Status: NOT RUN (optional, outside the completion gate).** The blank table below is a prospective
protocol, not completed evidence and not part of any current headline.

**Why:** test whether the headline contemporary-N_e is a `currentNe2`-specific artifact by
comparing it with the field-standard tool (NeEstimator v2's LDNe). This would be the **one N_e use
of Phase 1's LD-pruned output**: NeEstimator-LDNe *assumes unlinked markers*, so the pruned Set A
is exactly its input (whereas `currentNe2` wants the un-pruned set — it reads N_e *from* LD).

**Outside the DAG:** NeEstimator v2 is a Java GUI and is not scriptable, so this step is run by
hand. Only the *input* is automated.

## Input (automated)

```bash
conda activate congen
snakemake -s workflow/Snakefile results/ne/neestimator/setA.standard.pruned.genepop --cores 1
```

- Source: `results/qc/setA.standard.pruned.vcf.gz` (standard preset, LD-pruned, **~19.6k SNPs, 22 birds**).
- Format: GenePop, 3 populations (`Pop` blocks = Yunnan, Vietnam, Thailand), alleles `01`/`02`, missing `0000`.

> ⚠️ ~19.6k loci × 22 individuals is a heavy LDNe run in the GUI (LD over all locus pairs).
> If it is too slow/memory-heavy on the laptop, thin the GenePop (e.g. keep every k-th locus) and
> note the thinned locus count in the table below. Treat thinning as an additional sensitivity to
> evaluate; this unrun protocol has not established point-estimate stability under thinning.

## Procedure (manual GUI)

1. Open **NeEstimator v2** → load the GenePop file above.
2. Method: tick **Linkage Disequilibrium** (LDNe). Mating: **Random**.
3. Critical values (P_crit): **0.05, 0.02, 0.01** (the three the cube's `ne.ldne_pcrit` lists).
4. Run. LDNe reports, per population × P_crit: N̂e + the parametric (and jackknife) 95% CI.
5. Paste the numbers into the table below, alongside the `currentNe2` per-population point estimates
   from `results/cube/results_cube.csv` (`structure_mode == per_population`, standard preset).

## Comparison table (fill in after the GUI run)

`currentNe2` reference (standard preset, per_population, cross-chromosome) — from `results/cube/results_cube.csv`:

| population | currentNe2 N_e | currentNe2 90% CI | verdict vs 500 |
|---|---|---|---|
| Yunnan   | 88.4 | 26.92 – 290.31 | **fail** |
| Vietnam  | non-converged | — | indeterminate |
| Thailand | non-converged | — | indeterminate |

> At the standard preset only **Yunnan** converged (N_e = 88.4, cross-chromosome — far below 500).
> Vietnam (n = 10) and Thailand (n = 5) did **not** converge (`ne_basis = none` → indeterminate).
> Whether that non-convergence is `currentNe2`-specific is exactly what the LDNe run below tests:
> if NeEstimator-LDNe also returns low/unbounded/indeterminate for these two, the verdicts agree.

NeEstimator-LDNe (this manual run):

| population | P_crit | LDNe N_e | LDNe 95% CI (parametric) | agrees w/ currentNe2? |
|---|---|---|---|---|
| Yunnan   | 0.05 | | | |
| Yunnan   | 0.02 | | | |
| Yunnan   | 0.01 | | | |
| Vietnam  | 0.05 | | | |
| Vietnam  | 0.02 | | | |
| Vietnam  | 0.01 | | | |
| Thailand | 0.05 | | | |
| Thailand | 0.02 | | | |
| Thailand | 0.01 | | | |

## What "agreement" means here

Not identical numbers — the two estimators differ in model and in which markers they use
(LDNe = pruned/unlinked + within-sample LD; currentNe2 = un-pruned + cross-chromosome LD with a
genome-size prior). Agreement = **same order of magnitude and the same pass/fail/indeterminate
verdict vs N_e = 500**. At n = 7/10/5 both are expected to give wide CIs (often unbounded above) and
mostly indeterminate/low estimates. Only a completed, recorded run could establish concordance.
