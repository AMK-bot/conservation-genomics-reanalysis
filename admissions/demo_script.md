# Fragility Explorer: 2–3 minute demonstration script

## Recording goal

Show one complete scientific argument in under three minutes:

> The peafowl headline remains stable while its estimates are fragile; the wolf's biological pattern
> remains stable while its magnitude is threshold-sensitive.

The demonstration should work from the local Streamlit app and tracked results. A laptop screen recorder
and microphone are sufficient.

## Before recording

1. From the project environment, launch `streamlit run app/streamlit_app.py`.
2. Set the browser to 100% zoom and close unrelated tabs or notifications.
3. Open the app at the **N_e / GBF verdict** tab with filtering set to `lenient`, structure set to
   `per_population`, and population set to `Vietnam`.
4. Keep this script on a second desktop or print it; do not show it in the recording.
5. Record one uninterrupted take. Aim for 2:40–2:55, 1080p, with a deliberate pace.

## Shot-by-shot script

### 0:00–0:18 — Title and question

**On screen:** App title and the two controls.

**Say:**

> This is my Fragility Explorer. It asks a simple conservation-genomics question: when an analyst makes
> different reasonable choices, does the biological verdict stay the same? I tested that question using
> public whole-genome data from green peafowl and Scandinavian wolves.

### 0:18–0:58 — One uncertain peafowl estimate

**On screen:** Lenient, per-population, Vietnam. Point to the point estimate, 90% interval, and badge.

**Say:**

> Here, Vietnam has a contemporary effective-population-size point estimate of about 2,293, apparently
> above the conservation target of 500. But its 90-percent interval runs from 139 to about 37,795 and
> crosses the target, so the honest verdict is uncertain—not a pass. Effective population size measures
> the rate of genetic drift and inbreeding; it is not the same as counting birds.

### 0:58–1:28 — Change the analyst choice

**On screen:** Move filtering from `lenient` to `strict`; keep Vietnam selected. Then scroll to the
robustness table.

**Say:**

> Under strict filtering, the estimator no longer converges. Across all presets, zero of three sampled
> populations confidently clears 500, so the headline is stable. Yet two populations change between
> at-risk and uncertain, and convergence itself changes. This is the central result: a robust category
> can sit above fragile estimates.

### 1:28–1:52 — Contrast the second GBF indicator

**On screen:** Scroll to **Populations Maintained** and show 0.70 with its 0.70–0.70 band.

**Say:**

> A second, non-genomic indicator asks whether historical range countries still maintain the species.
> This project estimates 0.70 after checking the live BirdLife country table. The sampled countries count as
> maintained, yet none of their sampled populations is genetically secure here. Continued presence and
> long-term genetic security are different questions. Country units are still too coarse for a
> publication-level persistence assessment.

### 1:52–2:25 — Wolf sensitivity test

**On screen:** Open **Wolf: load & ROH**. Move GERP from 2 to 4 and ROH cutoff from 0.1 to 2.0 Mb.

**Say:**

> The wolf chapter gives a stronger computational anchor. At GERP greater than four, my workflow
> reproduces the deposit's load table across all 211 wolves to floating-point precision. Changing the
> GERP threshold shifts mean realized load, and changing the ROH cutoff shifts measured inbreeding. But
> the realized-versus-masked pattern remains stable: threshold choices move the magnitude more than the
> biological direction.

### 2:25–2:48 — Limitations and next study

**On screen:** Open **About / limitations** and point to “Risk, not depression” and “Small n.”

**Say:**

> I claim conservation risk, not demonstrated inbreeding depression. The main peafowl limitation is only
> five to ten individuals per population. The most useful next study would therefore add independently
> sampled individuals within each population, rather than simply adding more SNPs.

### 2:48–2:58 — Close

**On screen:** Return to the app title or hold on the limitations panel.

**Say:**

> The project taught me that uncertainty is not an error to hide. Sometimes it is the most biologically
> responsible result.

## Optional end card text

Use a plain text slide for three seconds only if the final recording remains under three minutes:

```text
Fragility Explorer
2 public genomic datasets · 32 validation passes · 0 failures
Full methods, results, and ownership record in the repository
```

## Accuracy checklist

- Say “sampled populations,” not all wild peafowl populations.
- Say “none confidently clears 500,” not that every true $N_e$ is known to be below 500.
- Describe the confidence interval as 90%, not 95%.
- Call GONE2 context only if it appears on screen; do not present it as a verdict axis.
- Say the wolf anchor validates computational fidelity, not biological fitness effects.
- Say risk, not demonstrated inbreeding depression.
- Credit the source deposits and disclose computational/AI assistance if asked about ownership.

## Evidence used for the script

- [Peafowl cube and exact cells](../results/PHASE2_VALIDATION.md)
- [GBF headline, robustness, and Populations Maintained](../results/PHASE3_VALIDATION.md)
- [Wolf anchor and sensitivity summaries](../results/PHASE4_VALIDATION.md)
- [Full limitations and methods](../report/report.qmd)
