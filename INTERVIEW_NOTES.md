# Interview notes: conservation-genomics reanalysis

Use these notes to practise explaining the project in your own words. Do not memorise every decimal;
be able to define the quantity, describe the pattern, name the main limitation, and say what evidence
would resolve it.

## The project in one sentence

I used two public whole-genome datasets to test whether conservation-genomics conclusions remain stable
when defensible analytical choices change, and I found that a headline can be robust even when its
underlying estimates are fragile.

## Core questions and concise answers

### What is effective population size, and how is it different from census size?

**Short answer:** Census size ($N_c$) counts individuals. Effective population size ($N_e$) is the size
of an idealized population that would experience genetic drift or inbreeding at the same rate as the
real population. Unequal reproductive success, sex ratio, relatedness, and changing population size
usually make $N_e$ smaller than $N_c$.

**In this project:** The GBF threshold is $N_e>500$ per population, not a range-wide head count. A
range-wide census can therefore look adequate while individual populations remain genetically at risk.
The project uses $N_e:N_c=0.1$ only as a transparent proxy contrast, not as a conversion known to be
exact for peafowl. See the [GBF summary](results/tables/gbf_summary.tsv).

### Why can population structure bias an LD-based $N_e$ estimate?

Pooling genetically differentiated populations creates associations between alleles because their
frequencies differ among groups. That Wahlund-generated LD is not caused only by drift within one
population. An LD-based estimator can interpret the extra LD as evidence of a smaller $N_e$, biasing
the pooled estimate downward.

In the cube, pooled estimates are 52, 89, and 108 across the three presets. The expected downward
direction is visible but noisy, so I treat pooling as a cautionary contrast rather than a precise bias
calibration. The per-population cells—not the pooled cells—feed the GBF indicator. See the
[Phase 2 validation](results/PHASE2_VALIDATION.md).

### Why is LD pruning wrong for currentNe2 but useful elsewhere?

currentNe2 infers $N_e$ from linkage disequilibrium. If I prune linked markers first, I remove part of
the signal it is designed to measure. The workflow therefore supplies each preset's unpruned callset and
uses cross-chromosome LD.

PCA and ADMIXTURE have a different purpose: pruning prevents large linked regions from dominating the
structure pattern. The manual NeEstimator input is also pruned because that comparison assumes unlinked
markers. The lesson is that “more processed” does not automatically mean “more appropriate”; the input
must match the estimator's assumptions.

### Why is an indeterminate result scientifically informative?

The workflow labels a peafowl cell `indeterminate` when the 90% confidence interval crosses 500 or the
estimator does not converge. It means the data do not resolve which side of the conservation threshold
the population occupies. It does **not** mean the population passes, fails, or can be assigned whichever
label is more convenient.

For example, Vietnam's lenient point estimate is 2,293, but its interval is 139–37,795, so the correct
reading is indeterminate. Under stricter filters it does not converge. That movement exposes the limits
of $n=10$ instead of hiding them. See the [results cube](results/cube/results_cube.csv).

### What does exact reproduction of the wolf anchor validate?

At GERP $>4$, the workflow matches the deposit's per-individual realized and masked loads across all 211
wolves to floating-point precision, with zero differences in the raw call/deleterious/homozygous-
deleterious counts. This strongly validates the implementation of ancestral-allele polarization, the
load formulas, and chromosome aggregation.

It does **not** prove that GERP is a perfect measure of biological harm, validate every possible load
definition, or demonstrate fitness effects. It gives a trusted starting point for the project's GERP
threshold sweep. See the [Phase 4 validation](results/PHASE4_VALIDATION.md).

### Which result surprised you most?

I was most surprised that **zero of three peafowl populations confidently pass $N_e>500$ under every
filter preset**, even though the underlying estimates are unstable. Two populations change between
`fail` and `indeterminate`, and stricter filters often remove convergence. I expected sensitivity to
make the headline move; instead, it showed that a robust categorical result can still rest on imprecise
numbers. See the [Phase 3 validation](results/PHASE3_VALIDATION.md).

### What evidence should come next?

For the peafowl $N_e$ question, the highest-value next evidence is more individuals per population—not
merely more SNPs—because the existing $n=7/10/5$ drives wide intervals and non-convergence. Other
uncertainties need different evidence:

| Uncertainty | Most useful next evidence |
|---|---|
| Contemporary peafowl $N_e$ | More independently sampled individuals within each population |
| GONE2 recent trajectory | A peafowl-specific recombination map |
| Inbreeding depression | Direct fitness or reproductive measurements |
| Populations Maintained | Finer, current sub-country occurrence records |
| Museum–modern contrast | Matched locations, time points, and ancient-DNA-aware genotype treatment |

These are proposed study designs, not evidence already present in the project.

## Methodological choice to defend

**Question:** Why use a three-state verdict instead of forcing pass/fail?

**Answer:** A point estimate alone hides uncertainty. I use `pass` only when the estimate and its 90%
interval are above 500, `fail` when they are below, and `indeterminate` when the interval crosses 500 or
the estimator does not converge. That makes the decision rule reproducible and prevents a very uncertain
point above 500 from being misreported as secure. The validator checks that every cube cell uses one of
these states and that non-converged cells remain indeterminate.

## Figure-reading exercise

Open [the static $N_e$ cube figure](results/figures/ne_cube.png) and answer aloud before reading the
model response.

**Prompt:** Describe the figure without interpreting it first. Then identify one stable conclusion, one
unstable feature, and one limitation. What would you measure next?

**Model response:**

1. **Describe:** The figure compares contemporary $N_e$ estimates across three filtering presets and
   two structure treatments. Per-population points have uncertainty intervals; pooled points are a
   structure-bias contrast. Some cells have no converged estimate.
2. **Stable conclusion:** No per-population cell is confidently above the $N_e=500$ threshold; the GBF
   fraction passing is 0/3 under lenient, standard, and strict filtering.
3. **Unstable feature:** The point estimates, verdict states, and convergence change with filtering.
   Thailand and Yunnan change between fail and indeterminate, while Vietnam remains indeterminate but
   loses convergence under stricter presets.
4. **Limitation:** Samples are only 5–10 individuals per population, so intervals are wide. The figure
   is evidence about uncertainty and sensitivity, not a precise census of genetic status.
5. **Next measurement:** Increase the number of independently sampled individuals within each
   population using the same preregistered filtering and estimation grid.

## Likely follow-up questions

### Why not quote Vietnam's point estimate as evidence that it passes?

Because 2,293 is accompanied by a 90% interval of 139–37,795. The interval crosses 500, and the estimate
does not survive stricter filtering as a converged point. Reporting only the point would discard the
part of the result most relevant to a threshold decision.

### Are validator warnings failures?

No. The four tracked phase gates contain 32 passes, 12 warnings, and zero failures. The warnings are
deliberately “reported, not asserted”: they flag scientific directions such as metric-dependent temporal
diversity, fragile verdicts, and threshold-sensitive load magnitude. A software failure would appear as
`FAIL` and stop the gate.

### What is original here if the data are public and one wolf result is reproduced?

The source studies produced the biological data and original methods. My project contribution is the
cross-species fragility question, the filter-by-structure cube, the three-state policy reading, the
separation of GONE2 context from contemporary $N_e$, the GERP/ROH sensitivity sweeps, and the synthesis
of robust conclusions versus fragile magnitudes. I used scientific software and AI coding assistance to
implement, debug, review, and document the workflow; I am responsible for understanding the decisions
and keeping the claims within the validation evidence.

### What would falsify or change your headline?

A larger, representative within-population sample could narrow the intervals and yield one or more
confident estimates above 500. That would change the 0/3 result. The current conclusion is therefore
“none of the **sampled populations confidently passes with these data and tested presets**,” not “every
wild peafowl population is below 500 forever.”

## 60–90 second spoken summary

> My project asks whether conservation-genomics conclusions remain stable when analysts make different
> defensible choices. I reanalysed public whole-genome data from 22 green peafowl across three
> populations and 211 Scandinavian wolves. For peafowl, I built a reproducible cube that changes
> filtering stringency and whether population structure is modelled. Zero of three populations
> confidently exceeded the effective-population-size target of 500 under any preset, but the individual
> estimates were fragile: confidence intervals were wide, two populations changed verdict, and several
> stricter-filter runs did not converge. For wolves, I first reproduced the deposited GERP-greater-than-4
> load table exactly, then tested other GERP and ROH thresholds. The absolute values moved, while the
> realized-versus-masked load pattern stayed stable. The main lesson is that uncertainty is not a defect
> to hide. A robust conclusion and a precise number are different things. The most useful next step for
> peafowl would be more individuals per population, followed by genomic analysis using the same declared
> sensitivity grid.

## Evidence checklist before an interview

- [Phase 1 validation](results/PHASE1_VALIDATION.md): QC, structure, diversity, temporal caveats.
- [Phase 2 validation](results/PHASE2_VALIDATION.md): cube shape, estimates, convergence, GONE2 context.
- [Phase 3 validation](results/PHASE3_VALIDATION.md): GBF reconciliation and verdict stability.
- [Phase 4 validation](results/PHASE4_VALIDATION.md): exact wolf anchor and sensitivity summaries.
- [Research journey](RESEARCH_JOURNEY.md): mistakes, corrections, ownership, and scope boundaries.
