# Fragility Explorer: 2–3 minute narrated walkthrough

## Recording goal

Show the complete Phase-5B scientific argument in under three minutes:

> Stress tests can support a proxy association, weaken a temporal interpretation, reject a sample
> prescription, authorize a bounded follow-up, and defer a duplicative study without overstating
> fitness or causation.

**Phase 5B status: COMPLETE.** The clean builds, synchronized render, offline package, and release
gates pass; use the [reproducibility record](../results/PHASE5B_REPRODUCIBILITY.md) for verification.

## Before recording

1. From the project environment, launch `streamlit run app/streamlit_app.py`.
2. Set the browser to 100% zoom and close unrelated tabs or notifications.
3. Open **N_e / GBF verdict** and scroll once to locate **Study-design calibration**.
4. Locate **Damage-aware museum–modern falsification** under **Structure & diversity**.
5. Under **Wolf: load & ROH**, locate both the individual association and localization panels; set
   the localization ROH cutoff to 1.5 Mb.
6. Under **About / limitations**, locate the optional-study decision table.
7. Record one uninterrupted take. Aim for 2:45–2:58 at a deliberate pace.

## Shot-by-shot script

### 0:00–0:16 — Title and question

**On screen:** App title and species summary.

**Say:**

> This is my Fragility Explorer. I used two public genome datasets to ask whether conservation claims
> survive reasonable analytical choices—and whether a negative or deferred result can improve the
> science.

### 0:16–0:48 — Peafowl verdict and study-design correction

**On screen:** On **N_e / GBF verdict**, show the 0/3 headline, then scroll to
**Study-design calibration** and move between sample sizes.

**Say:**

> None of the three sampled peafowl populations confidently clears the effective-population-size
> target under any filter, although estimates and convergence move. I then calibrated five sample
> sizes against three marker densities using known-truth scenarios. Zero of those 15 designs resolved
> both predeclared resolution truths, $N_e=250$ and $N_e=1{,}000$, under the declared uncertainty
> rule. So this project does not support an
> empirical sample-number prescription.

### 0:48–1:15 — Damage-aware falsification

**On screen:** Open **Structure & diversity**, then show **Damage-aware museum–modern falsification**
and the four-metric table or figure.

**Say:**

> The museum–modern contrast was also weaker than its simplest story. After transversion-only,
> equal-sample, leave-one-out, permutation, and block checks, only one of four diversity metrics was
> fully robust. Museum and modern birds are geographically mismatched, so I report a confounded
> contrast—not temporal erosion.

### 1:15–1:50 — Wolf individual association

**On screen:** Open **Wolf: load & ROH** and point to **Individual F_ROH–load robustness surface**.
Move the GERP and ROH controls to show the frozen grid.

**Say:**

> For wolves, I started from a load calculation that reproduces the deposited 211-wolf anchor. In
> Phase 5B, the group-adjusted partial realized-load interval stayed above zero in all 15 GERP-by-ROH
> cells, even after controlling generic homozygosity. That is a robust association between genomic
> proxies. It is not individual harm, fitness, or causal inbreeding depression.

### 1:50–2:23 — Predeclared localization follow-up

**On screen:** Scroll to **ROH localization**, retain the predeclared 1.5-Mb cutoff, and show the
circular-shift forest or cohort table.

**Say:**

> The 15-of-15 result crossed a gate set in advance, so Section 13.4 said IMPLEMENT before I saw the
> localization outcome. At the predeclared 1.5-megabase cutoff, all 24 population-by-GERP cells were
> beyond the within-chromosome circular-shift null rule. That is genomic colocalization using assayed
> variant opportunities—not proof that ROH caused burden or changed fitness.

### 2:23–2:45 — A defensible deferral

**On screen:** Open **About / limitations** and point to the §13.5 decision row.

**Say:**

> The other optional study was deferred because zero of one annotation definitions was independent
> and all 211 samples overlapped the source study. It reopens only with at least one independent
> definition, 95-percent common-sample coverage, and 90-percent auditable denominator coverage.

### 2:45–2:58 — Close

**On screen:** Hold on the decision table or return to the title.

**Say:**

> The lesson is that uncertainty is not an error to hide. A falsified interpretation, a no-prescription
> result, and an evidence-backed deferral can be the most responsible scientific outcomes.

## Optional end card text

Use a plain text slide only if the recording remains under three minutes:

```text
Phase 5B COMPLETE · release verified
15/15 wolf association · 1/4 damage robustness · 0/15 N_e designs
§13.4 IMPLEMENT · 24/24 localized cells · §13.5 evidence-backed deferral
Association and colocalization—not fitness or causation
```

## Accuracy checklist

- Say “sampled populations,” not all wild peafowl populations.
- Say “none confidently clears 500,” not that every true $N_e$ is known below 500.
- Say **0/15 tested designs** and **no empirical sample prescription**; do not recommend an exact n.
- Say **1/4 fully robust**, keep geography confounding prominent, and do not claim temporal erosion.
- Describe wolf **15/15** as association between genomic proxies, not fitness, harm, or causation.
- State that §13.4 was **`IMPLEMENT`** under a predeclared gate.
- Describe **24/24 at 1.5 Mb** as beyond the circular-shift null and as genomic colocalization only.
- Name §13.5 exactly as **`DEFER_DUPLICATES_SOURCE_STUDY`** because 0/1 definitions are independent
  and source overlap is 211/211. Its reopening rule is ≥1 independent definition, ≥0.95 common-sample
  coverage, and ≥0.90 auditable callable-denominator coverage.
- Credit the source deposits, tools, and AI coding assistance listed under Credits in the [README](../README.md#credits).
- If asked about reproducibility, open the clean Phase-5B record and distinguish the 169 scientific
  PASS checks from the separate release-content, website, package, and delivery gates.

## Evidence used for the script

- [Peafowl cube and exact cells](../results/PHASE2_VALIDATION.md)
- [GBF headline and robustness](../results/PHASE3_VALIDATION.md)
- [Wolf deposited anchor](../results/PHASE4_VALIDATION.md)
- [Wolf individual-association validation](../results/WOLF_ROBUSTNESS_VALIDATION.md)
- [Damage-aware peafowl validation](../results/PEAFOWL_DAMAGE_VALIDATION.md)
- [Peafowl $N_e$ design validation](../results/PEAFOWL_NE_DESIGN_VALIDATION.md)
- [Optional-study decision validation](../results/PHASE5B_DECISIONS_VALIDATION.md)
- [Wolf ROH-localization validation](../results/WOLF_ROH_LOCALIZATION_VALIDATION.md)
- [Phase-5B reproducibility record](../results/PHASE5B_REPRODUCIBILITY.md)
- [Full limitations and methods](../report/report.qmd)
