# Questions and answers: conservation-genomics reanalysis

Short answers to the questions this project most often raises. Each answer defines the quantity,
describes the pattern, names the main limitation, and says what evidence would resolve it.

## The project in one sentence

I used two public whole-genome datasets to test whether conservation-genomics conclusions remain stable
when defensible analytical choices change, and I found that a headline can be robust even when its
underlying estimates are fragile—and that a negative stress test or a deferred study can be a useful
scientific result.

**Phase 5B status: COMPLETE.** The clean verification, synchronized rendering, offline package, and
release gates pass; the auditable record is
[`results/PHASE5B_REPRODUCIBILITY.md`](results/PHASE5B_REPRODUCIBILITY.md).

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

### What are the six Phase-5B claim-level results?

1. **Wolf individual association:** the partial realized-load bootstrap interval is above zero in
   **15/15** predeclared GERP × ROH cells. This is association between genomic proxies, not fitness,
   individual harm, or causal inbreeding depression.
2. **Damage-aware peafowl falsification:** only **1/4** diversity metrics is fully robust, and the
   museum–modern groups remain geographically confounded. I do not upgrade this to temporal erosion.
3. **Peafowl $N_e$ design:** **0/15** sample-size × marker-density designs resolve both predeclared
   resolution truths ($N_e=250$ and $N_e=1{,}000$) under the declared rule. The result provides no
   empirical sample prescription.
4. **§13.4 decision:** the predeclared wolf-association gate returned **`IMPLEMENT`**, authorizing the
   localization analysis before its result was known.
5. **Wolf localization:** at the predeclared 1.5-Mb cutoff, **24/24** population × GERP cells are beyond
   the within-chromosome circular-shift null rule. This is genomic colocalization, not fitness, harm,
   or causation.
6. **§13.5 decision:** **`DEFER_DUPLICATES_SOURCE_STUDY`** because 0/1 annotation definitions are
   independent of the source classes and all 211/211 samples overlap. Reopen only with at least one
   independent definition, at least 0.95 common-sample coverage, and at least 0.90 auditable
   callable-denominator coverage.

### What did you learn from debugging the $N_e$ parser and convergence summary?

currentNe2 can emit a preferred cross-chromosome estimate and a whole-genome fallback. I retained the
selected `ne_basis` and independently reparsed the raw output so a fallback estimate could not be
misreported as cross-chromosome convergence. A separate summary bug came from a generic rate helper:
it produced `n_convergence`, while the declared table schema required `n_converged`. I corrected the
field mapping and made the independent validator recompute it. The scientific consequence is that
execution failure, successful nonconvergence, and an indeterminate threshold decision remain distinct.

### Which result surprised you most?

I was most surprised that the study-design analysis did **not** validate the intuitive recommendation
I had been making. Across the five sample sizes and three marker densities, **0/15** designs resolved
both predeclared resolution truths ($N_e=250$ and $N_e=1{,}000$). That corrected my wording from
“collect this many more individuals” to “the
tested scenarios do not establish a real sample prescription.” I was also struck by the contrast on
the wolf side: a 15/15 individual association justified running §13.4, and the localization result was
beyond the circular-shift null in 24/24 predeclared 1.5-Mb cells, while still stopping short of a
fitness or causal claim.

### What evidence should come next?

For the peafowl $N_e$ question, Phase 5B shows that this project cannot defend an exact sample target:
0/15 tested designs resolved both predeclared resolution truths ($N_e=250$ and $N_e=1{,}000$).
Independent, representative sampling remains
relevant, but a prospective design needs assumptions matched to the population and a preregistered
decision rule. Other uncertainties need different evidence:

| Uncertainty | Most useful next evidence |
|---|---|
| Contemporary peafowl $N_e$ | A prospectively calibrated, representative sampling design; no tested sample number is a guarantee |
| GONE2 recent trajectory | A peafowl-specific recombination map |
| Inbreeding depression | Direct fitness or reproductive measurements |
| Populations Maintained | Finer, current sub-country occurrence records |
| Museum–modern contrast | Matched locations, time points, and ancient-DNA-aware genotype treatment |

The scenario calibration and damage-aware stress test are evidence already present in the project;
the new biological samples, matched time/location design, recombination map, and fitness phenotypes are
not.

## A methodological choice, explained

**Question:** Why use a three-state verdict instead of forcing pass/fail?

**Answer:** A point estimate alone hides uncertainty. I use `pass` only when the estimate and its 90%
interval are above 500, `fail` when they are below, and `indeterminate` when the interval crosses 500 or
the estimator does not converge. That makes the decision rule reproducible and prevents a very uncertain
point above 500 from being misreported as secure. The validator checks that every cube cell uses one of
these states and that non-converged cells remain indeterminate.

## How to read the $N_e$ cube figure

[The static $N_e$ cube figure](results/figures/ne_cube.png) is best read in five steps: describe it before
interpreting it, then name one stable conclusion, one unstable feature, one limitation, and the next
measurement.

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
5. **Next measurement:** Design representative within-population sampling prospectively and calibrate
   the full decision pipeline before choosing a target; the current 0/15 result supplies no guaranteed
   sample number.

## Follow-up questions

### Why not quote Vietnam's point estimate as evidence that it passes?

Because 2,293 is accompanied by a 90% interval of 139–37,795. The interval crosses 500, and the estimate
does not survive stricter filtering as a converged point. Reporting only the point would discard the
part of the result most relevant to a threshold decision.

### Are validator warnings failures?

No. Warnings are deliberately “reported, not asserted”: they flag scientific sensitivity such as
metric-dependent diversity, fragile verdicts, and threshold-sensitive magnitude. A `FAIL` is different:
it stops the dependent workflow gate. I cite the relevant named validator rather than quoting a
fixed aggregate count that can become stale as checks are added.

### What is original here if the data are public and one wolf result is reproduced?

The source studies produced the biological data and original methods. My project contribution is the
cross-species fragility question, the filter-by-structure cube, the three-state policy reading, the
separation of GONE2 context from contemporary $N_e$, the GERP/ROH sensitivity sweeps, the Phase-5B
falsification/scenario grids, and the predeclared go/no-go rules. The deposited samples, annotations,
and original methods are not mine. I used scientific software and AI coding assistance to implement,
debug, review, and document the workflow; I selected the accepted changes and remain responsible for
understanding the decisions and keeping the claims within the validation evidence.

### What would falsify or change your headline?

A larger, representative within-population sample could narrow the intervals and yield one or more
confident estimates above 500. That would change the 0/3 result. The current conclusion is therefore
“none of the **sampled populations confidently passes with these data and tested presets**,” not “every
wild peafowl population is below 500 forever.” The Phase-5B claims also have explicit change rules:
a wolf cell changes only when its partial interval crosses zero; a damage metric changes robustness
only when every declared stress test passes; a design qualifies only when both truth-specific
uncertainty rules pass; and a localization cell changes when it crosses the circular-shift bound or
two-sided permutation threshold. Section 13.5 reopens only under the coverage and independence rule
stated above.

## 60–90 second summary

> My project asks whether conservation-genomics conclusions survive defensible analytical choices. I
> reanalysed public whole-genome data from 22 green peafowl and 211 wolves. For peafowl, no sampled
> population confidently exceeded the effective-population-size target under any filter, but Phase 5B
> showed that zero of 15 sample-size-by-marker designs resolved both predeclared resolution truths
> ($N_e=250$ and $N_e=1{,}000$), so I do
> not prescribe a real sample number. Only one of four museum–modern diversity metrics survived every
> damage and influence check, with geography still confounded. For wolves, all 15 partial realized-load
> associations were positive beyond zero after the homozygosity control. That predeclared result
> authorized localization, where all 24 population-by-GERP cells at 1.5 megabases were beyond a
> circular-shift null. Those are proxy association and genomic colocalization, not fitness or causation.
> I also deferred an annotation study because it duplicated the source evidence. The lesson is that a
> negative result or a no-go decision can make a conservation claim more honest.

## Where the evidence lives

- [Phase 1 validation](results/PHASE1_VALIDATION.md): QC, structure, diversity, temporal caveats.
- [Phase 2 validation](results/PHASE2_VALIDATION.md): cube shape, estimates, convergence, GONE2 context.
- [Phase 3 validation](results/PHASE3_VALIDATION.md): GBF reconciliation and verdict stability.
- [Phase 4 validation](results/PHASE4_VALIDATION.md): exact wolf anchor and sensitivity summaries.
- [Wolf robustness validation](results/WOLF_ROBUSTNESS_VALIDATION.md): 15-cell partial association and
  proxy boundary.
- [Peafowl damage validation](results/PEAFOWL_DAMAGE_VALIDATION.md): four-metric falsification grid.
- [Peafowl $N_e$ design validation](results/PEAFOWL_NE_DESIGN_VALIDATION.md): parser, convergence,
  scenario, empirical, and uncertainty checks.
- [Phase-5B decisions](results/PHASE5B_DECISIONS_VALIDATION.md): §13.4 `IMPLEMENT` and §13.5
  `DEFER_DUPLICATES_SOURCE_STUDY` with numeric reopening rules.
- [Wolf localization validation](results/WOLF_ROH_LOCALIZATION_VALIDATION.md): circular-shift null,
  1.5-Mb claim, and causal boundaries.
- [Phase-5B reproducibility record](results/PHASE5B_REPRODUCIBILITY.md): isolated builds,
  bounded-memory evidence, matching science hashes/manifests, and final no-op verification.
- [Research journey](RESEARCH_JOURNEY.md): mistakes, corrections, ownership, and scope boundaries.
