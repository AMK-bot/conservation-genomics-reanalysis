# Research journey: learning to report uncertainty as a result

This is my reasoning record for the conservation-genomics reanalysis. It explains how the project
changed when the data and the methods challenged my original plan. It is not a claim that I generated
the biological samples or invented the source methods: both chapters begin with published, deposited
data, and several analyses deliberately reproduce or extend methods from those studies. My contribution
is the research framing, the sensitivity design, the reproducible workflow, and the interpretation of
what remains stable when defensible analytical choices change.

## 1. Why I chose these questions and datasets

I wanted to connect molecular biology to a real conservation decision rather than produce a collection
of disconnected genomic statistics. The central question became:

> When a conservation indicator is estimated from real genomic data, does the biological verdict stay
> stable when an analyst makes different defensible choices?

I chose two public whole-genome deposits that let me ask that question at different levels. The green
peafowl data support population structure, diversity, and contemporary effective population size
($N_e$) across three regional samples. The Scandinavian wolf data include ancestral-allele
polarization, GERP scores, and a deposited per-individual load table, so they provide an unusually strong
reproduction target. Starting from deposited VCFs kept the project focused on biological reasoning and
reproducible reanalysis. The data and their original biological context come from Dong et al. (green
peafowl) and Smeds and Ellegren (wolf), as documented in the [technical report](report/report.qmd).

The deposited peafowl analysis set contains 22 individuals: Yunnan $n=7$, Vietnam $n=10$, and Thailand
$n=5$. I treated those small samples as a reason to expose uncertainty, not as permission to hide it.
The wolf deposit contains 211 individuals and therefore provides a contrasting, data-rich test. These
counts are checked in the [setup record](SETUP.md) and the phase validations.

## 2. My original mental model was too simple

At first, I thought one carefully filtered, LD-pruned peafowl callset could serve both population
structure and contemporary-$N_e$ estimation. That sounds efficient, but it confuses two different uses
of linkage disequilibrium (LD):

- PCA and ADMIXTURE should not be dominated by large blocks of linked markers, so LD pruning is useful.
- An LD-based $N_e$ estimator infers population size from LD, so pruning away that signal before running
  currentNe2 is scientifically wrong.

The mismatch became clear when I examined what currentNe2 actually estimates rather than treating the
program as a black box. I corrected the workflow so PCA, ADMIXTURE, and the manual NeEstimator input use
the pruned callset, while currentNe2 uses each preset's **unpruned** callset in cross-chromosome mode.
The biological consequence is important: an apparently tidy preprocessing step could otherwise erase
the information required by the estimator. The correction and its implementation are recorded in the
[Phase 2 deviation log](CGplan.md#deviations) and checked by the
[Phase 2 validation](results/PHASE2_VALIDATION.md).

The build also exposed a more literal pruning error. The source VCF used `.` for every variant ID, so a
PLINK extract operation silently retained the full callset instead of the intended pruned subset. Giving
each variant a unique chromosome-position-allele ID reduced the standard structure callset from 420,826
post-MAC SNPs to 19,611 pruned SNPs. This was a useful lesson: a command completing without an exception
does not prove that it performed the intended biological transformation. The before-and-after counts
are recorded in the [Phase 1 deviation log](CGplan.md#deviations).

## 3. Why GONE2 moved from a method comparison to a context panel

My first design treated currentNe2 and GONE2 as alternative settings on the same axis. That would have
made the explorer look more complex, but the comparison would have been misleading. currentNe2 supplies
the contemporary cross-chromosome estimate used for the $N_e>500$ indicator. GONE2 reconstructs a recent
trajectory and requires recombination-rate assumptions. Peafowl lacks a species-specific map in this
project, and the run uses a borrowed generic-bird rate plus macrochromosomes only.

I therefore removed GONE2 from the verdict cube and retained it as a clearly labelled context panel. Its
trajectory does not change the conservation badge. This was a scope reduction that made the biology more
honest: two programs should not be presented as interchangeable merely because both output a quantity
called $N_e$. The final distinction is documented in the [Phase 2 validation](results/PHASE2_VALIDATION.md)
and the [technical report](report/report.qmd).

## 4. Why temporal $N_e$ became a diversity contrast

The comparative peafowl callset contains only five museum and six modern individuals. I initially hoped
to use it for temporal effective population size, but that sample size cannot support a credible
LD-$N_e$ comparison. I changed the question to a narrower museum-versus-modern diversity contrast using
heterozygosity, rarefied allelic richness, and windowed nucleotide diversity.

That change did not produce a dramatic conclusion, which is itself informative. Median nucleotide
diversity and observed heterozygosity are slightly higher in the museum group, but expected
heterozygosity and rarefied allelic richness are essentially flat. Ancient-DNA damage and geographic
mismatch further limit interpretation. I therefore report a weak, metric-dependent contrast, not a
claim of temporal erosion. The exact values and caveats are in the
[Phase 1 validation](results/PHASE1_VALIDATION.md).

## 5. What the wolf anchor does—and does not—establish

For the wolf chapter, I first reimplemented the deposited GERP-weighted, ancestral-polarized load
calculation at the source threshold, GERP $>4$. Across all 211 individuals, the recalculated realized
and masked loads match the deposit's precomputed table to floating-point precision; the raw count deltas
are zero. Only after that reconciliation did the workflow extend the calculation across GERP thresholds
2, 3, and 4.

This is strong evidence that the allele polarization, formulas, and genome-wide aggregation were
implemented faithfully. It is **not** evidence that GERP perfectly predicts biological harm, nor does it
turn a reproduction into a novel biological discovery. The sensitivity extension shows that the load
magnitude changes with the GERP threshold, while the realized-versus-masked direction remains stable.
The [Phase 4 validation](results/PHASE4_VALIDATION.md) separates those claims explicitly.

## 6. The result that changed how I think about uncertainty

The most interesting outcome is a combination I did not initially expect: a stable headline can be
built from unstable estimates.

Across lenient, standard, and strict filtering, zero of the three sampled peafowl populations
confidently pass $N_e>500$. However, two populations change between `fail` and `indeterminate`, and
several stricter-filter estimates do not converge. Vietnam has a lenient point estimate above 500, but
its 90% interval crosses the threshold, so it is indeterminate rather than a pass. The headline is
robust; the individual numbers and convergence are fragile. The complete cells are in the
[results cube](results/cube/results_cube.csv), and their reconciliation is checked in the
[Phase 3 validation](results/PHASE3_VALIDATION.md).

This changed my view of an indeterminate result. It is not a failed answer to replace with a more
confident point estimate. It tells us that the present data cannot distinguish the policy categories.
Likewise, the validators' warnings report scientific sensitivity or limitations; they are not hidden
software failures. Across Phases 1–4, the tracked validation reports contain 32 passes, 12
reported-not-asserted warnings, and zero failures.

## 7. Responsible claims

I now use three boundaries when explaining the project:

1. I report **conservation risk**, not demonstrated inbreeding depression. Demonstrating depression
   would require measured fitness or reproductive outcomes.
2. I distinguish a reproduced source result from a project extension. The GERP $>4$ wolf calculation
   is a faithful reproduction; the GERP-threshold and ROH-length sweeps are sensitivity extensions.
3. I separate a robust conclusion from a robust number. The peafowl 0/3 headline is stable across the
   tested presets, but the population estimates are not precise enough to be treated as fixed values.

The full limitations are stated in the [technical report](report/report.qmd#limitations).

## 8. What I would design differently next time

For a future peafowl study, I would prioritize **more individuals within each population** before adding
more SNPs. The present analysis already samples up to 25,000 SNPs per currentNe2 cell, yet $n=7/10/5$
still produces wide intervals and non-convergence. More loci cannot fully replace independent
individuals when uncertainty is dominated by sample size.

I would also match sampling locations and time points more carefully for a temporal comparison, obtain a
species-specific recombination map before interpreting a recent-$N_e$ trajectory strongly, and pair
genomic risk indicators with fitness or reproductive measurements before testing for inbreeding
depression. For the Populations Maintained indicator, finer sub-country occurrence evidence would be
more informative than a country-level yes/no category. These are study-design conclusions, not claims
that the missing evidence has already been collected.

## 9. Ownership and assistance record

| Part of the project | Origin and responsibility |
|---|---|
| Biological samples, sequencing, deposited VCFs, population labels, wolf GERP annotations, and the GERP $>4$ anchor | Produced by the source studies and reused from their public deposits. I do not claim these as original data. |
| currentNe2, GONE2, PLINK, bcftools, VCFtools, ADMIXTURE, Streamlit, and statistical libraries | Existing scientific/software tools. Their outputs depend on the parameters and inputs recorded in this repository. |
| Research question, dataset choice, filter/structure sensitivity design, three-state verdict, scope corrections, and interpretation boundaries | Student project decisions. I am responsible for understanding and defending them. |
| Workflow implementation, debugging, validation design, code review, and prose drafting | Developed with computational tool and AI coding assistance. I selected the accepted changes, ran or inspected the checks, and remain responsible for the final scientific claims. |
| Correctness evidence | Workflow validators, result-table reconciliation, and the deposited wolf anchor. These checks support computational fidelity; they do not substitute for new biological observations. |

This project is a computational reanalysis and admissions portfolio artifact, not a publication. Its
value lies in showing a traceable change in reasoning: I made simplifying assumptions, found where they
failed, corrected the workflow, and narrowed the claims to what the evidence can support.
