# Conservation Genomics Reanalysis — Execution Plan

**Status:** Execution plan. Decisions locked via a structured grilling session (2026-06-17).
**Companion to:** `conservation-genomics-reanalysis-project-scoping.md` (the scoping doc — the "why/what"; this is the "how").
**Goal:** An impressive, reproducible artifact for competitive university (transfer) applications.
**Ship bound:** January 2027 (~28 weeks out). Planned as if no time limit (depth-maximizing); January is the outer ship date, not a scope constraint. See §10 for the critical path.
**Access:** 100% remote — **no fieldwork, wet lab, specimen handling, or physical-site visits**. Data-access **verified 2026-06-17**: all four turnkey datasets (peafowl, wolf, ibex, trout) are openly downloadable with **no embargo, login, or access request**. (The pangolin SEA fallback is also openly downloadable, but is *reads-only* — a scope caveat, not an access one; see §3.3.) All compute is the user's laptop; deployment/publication is online.

---

## 0. Decisions locked (the inputs to this plan)

| Decision | Resolution | Why |
|---|---|---|
| **Structure** | Two chapters: broad flagship → deep frontier | Covers the whole conservation-genomics toolkit; learns easy→hard |
| **Chapter 1 dataset** | **Green peafowl** *(Pavo muticus)* — Dryad `10.5061/dryad.ffbg79ctc`. **Gate PASSED 2026-06-17:** 31 modern + 6 museum genomes → 22 unrelated, across 3 structured populations (Yunnan ~11, Vietnam ~12, Thailand 7) | Verified turnkey WGS VCF + scripts; multi-country; SE Asian icon (IUCN Endangered). Small per-pop n → wide N_e CIs, *folded into the fragility thesis* |
| **Chapter 2 dataset** | **Scandinavian wolf** *(Canis lupus)* — Dryad `10.5061/dryad.7m0cfxpzj` | Only deposit on Earth shipping WGS + VEP + GERP → turnkey genetic load |
| **Data type** | WGS for both | Unlocks the full analysis menu (diversity, N_e, ROH, load) |
| **Chapter 1 angles** | A (GBF indicators) + B (modern N_e) + C (robustness) + D (structure) + **G (temporal erosion: 6 museum vs 31 modern — CONFIRMED feasible)** [+ F pixy — stretch] | Scoping doc's flagship, enriched by WGS; G promoted to core after the Phase-0 gate revealed museum samples |
| **Chapter 2 angles** | H (genetic load: realized vs masked) + E (ROH inbreeding history) | The field's hottest frontier, turnkey here |
| **Primary deliverables** | (1) Reproducible repo, (2) interactive **"fragility explorer"** (Streamlit) | Citable + clickable + reproducible; legible to non-specialists |
| **Paper** | Stretch, *after* the two deliverables — but `report.qmd` is written paper-grade from day one so "write the paper" = reformat, not rewrite | Keeps preprint optionality cheap |
| **Tool concept** | Fragility explorer: a **three-knob cube** (filtering stringency × N_e method × structure modeled/ignored) → live N_e + CI + treaty pass/fail verdict | Turns angle C (robustness) into the headline interaction |
| **Architecture** | Workflow computes a **"results cube"** (tidy table); Streamlit just reads it | Deployable on free hosting; reproducible; the cube *is* angle C |
| **Compute** | All local: Apple **M1 / 8 GB RAM** + large USB drive | User's machine; no cloud |
| **Workflow infra** | **Snakemake** + conda `env.yml` + R `renv.lock` | Genomics standard (snpArcher-citable); purpose-built for the parameter sweep |
| **Tooling split** | CLI (PLINK/bcftools/VCFtools/ADMIXTURE/currentNe2/GONE2) + Python (scikit-allel, Streamlit — user's strength) + R (SNPRelate/dartR/hierfstat — being learned) | Plays to strengths; R is a targeted learning goal |

**The narrative tie:** *"Assessing genetic status across the modern conservation-genomics toolkit — from the new global biodiversity-treaty indicators on an endangered SE Asian bird, to realized-vs-masked genetic load in an inbred carnivore — and showing how fragile each verdict is to analyst choices."*

---

## 1. Definition of done

- **Repo (load-bearing):** one-command reproduction (`snakemake --use-conda`), pinned `env.yml` + `renv.lock`, the Snakefile, config of all thresholds, the results cube, all figures, and a paper-grade `report.qmd`.
- **Fragility explorer (load-bearing):** live public URL; three knobs wiggle the peafowl N_e/GBF verdict in real time; tabs for structure and the wolf's load.
- **Preprint (stretch):** `report.qmd` rendered + posted to EcoEvoRxiv/bioRxiv with a DOI.

---

## 2. Architecture & repo layout

```
congen-reanalysis/
├── README.md                  # one-command reproduction + the story
├── environment.yml            # conda (osx-64), pinned
├── renv.lock                  # R packages, pinned
├── config/
│   └── config.yaml            # ALL filtering thresholds, N_e settings, paths
├── workflow/
│   ├── Snakefile              # the DAG; generates the results cube
│   └── rules/                 # qc.smk, structure.smk, ne.smk, gbf.smk, load.smk
├── scripts/                   # python/ + R/ analysis scripts called by rules
├── results/
│   ├── cube/                  # results_cube.parquet  ← the tool's backend
│   ├── tables/                # diversity, N_e, GBF, load summaries
│   └── figures/
├── app/
│   └── streamlit_app.py       # the fragility explorer (reads results/cube/)
├── report/
│   └── report.qmd             # paper-grade methods/results/limitations
└── data/  (symlinked to USB)  # raw VCFs + per-chromosome splits + intermediates
```

**Data flow:** raw VCF → (Snakemake: QC → kin-screen → structure/diversity/N_e across the parameter grid) → `results_cube.parquet` → Streamlit reads the cube. The heavy bioinformatics never runs in the app.

---

## 3. Phase 0 — Setup & verification (the foundation)

**3.1 Environment (the #1 snag — Apple Silicon).** Build a uniform `osx-64` env so every Bioconda tool installs under Rosetta:
```bash
# Rosetta (once): softwareupdate --install-rosetta --agree-to-license
CONDA_SUBDIR=osx-64 conda create -n congen python=3.11
conda activate congen
conda config --env --set subdir osx-64          # pin the env to x86_64
conda install -c bioconda -c conda-forge \
  snakemake-minimal bcftools samtools vcftools plink plink2 admixture \
  pixy scikit-allel pandas numpy scipy streamlit plotly matplotlib \
  r-base r-essentials bioconductor-snprelate r-adegenet r-hierfstat r-dartr
# currentNe2, GONE2: clone + build from source (C++; needs Xcode CLT). NeEstimator v2 = Java GUI (cross-check only).
```
Then: `git init`; `renv::init()`; export `environment.yml`; create the repo skeleton (§2); symlink `data/` → USB.

**3.2 Verification gates — DO NOT skip (the scoping doc's "verify before committing"):**
- ✅ **PEAFOWL MULTI-POPULATION GATE — RESOLVED 2026-06-17 (PASS with caveats).** Confirmed from Dong et al. 2021: **31 modern + 6 museum** genomes → **22 unrelated** across **3 structured populations** (Yunnan ~11, Vietnam ~12, Thailand 7; Cambodia n=1 dropped). Verdict: viable. Two consequences baked into the plan: (a) small per-population n → wide N_e CIs, treated as a **feature of the fragility thesis** (small-sample uncertainty in real endangered species), with `currentNe2` as the small-n-appropriate workhorse; (b) the museum/modern split **promotes the temporal-erosion angle (G) to core**. **Sharpened fallback trigger:** switch to brook trout (Dryad `10.5061/dryad.2fqz612sb`, 82 wild sites) *only if* Phase 1 finds usable individuals collapse to <5 in more than one population. **Still to confirm in Phase 1:** resequencing coverage — if low-coverage WGS, route N_e/diversity through the ANGSD/genotype-likelihood stack (deposit already ships ANGSD scripts, so this is anticipated).
- **WOLF GATE.** Download the 12 GB deposit to USB; confirm `vep.tar.gz` + `gerp.tar.gz` + the outgroup polarization file; test a per-chromosome `bcftools view`; confirm RAM stays bounded.
- Reproduce both papers' sample tables as a data sanity check.

**Output:** working env, repo skeleton, both datasets downloaded + verified, Chapter-1 dataset confirmed (peafowl, or a fallback from §3.3).
**Reading:** Speciation Genomics setup + filtering tutorials; the two source papers' methods (Dong et al. 2021; Smeds & Ellegren 2022).

### 3.3 Chapter-1 fallback ladder
*Fires only if Phase 1 reveals peafowl's usable per-population n collapses to <5 in more than one population. Try in order:*

1. **SEA option — but reads-only (escalation required): Sunda pangolin** *(Manis javanica)*, Thailand — bioRxiv 2025 (Ewart et al.), ~30 whole genomes across **4 Thai populations** (Western, Khao Yai, Mid-south, Southernmost; F_ST 0.06–0.14). Thailand-**endemic** + a wildlife-forensics / "most-trafficked-mammal" narrative. **Verified 2026-06-17:** data is **openly available but READS-ONLY** — NCBI BioProject `PRJNA1240953`, SRA `SRR32831660`–`SRR32831689` (30 runs), no deposited VCF. → Using it means **calling variants from WGS reads** = the §6 "escalation to avoid," and rough on an all-local 8 GB machine. *Viable only if you deliberately opt into that variant-calling escalation; otherwise there is no turnkey SEA fallback.*
2. **Reliable default — strongest analytical fit: Alpine ibex** *(Capra ibex)* — Dryad `10.5061/dryad.n276d`, **12 populations, 173 individuals (~15/pop)** along a documented reintroduction/drift gradient = the textbook multi-population N_e / "proportion of populations" story (better per-pop n than peafowl). **Verified 2026-06-17:** openly downloadable; single file `DRYAD.raw.SNPfile.gz` (159 MB) is a **GATK-produced VCF — NO format conversion needed** (better than the scoping doc assumed); 101,822 SNPs. Non-SEA. *Analytically stronger than peafowl for the GBF flagship — peafowl wins primary only on the SEA tie + WGS/temporal-erosion angle.*
3. **Alternative backstop: brook trout** *(Salvelinus fontinalis)* — Dryad `10.5061/dryad.2fqz612sb`. **Verified 2026-06-17:** openly downloadable; `full_dataset.vcf` (159 MB, 24,337 SNPs, 267 individuals) + sample-metadata CSV + neutral/outlier annotation. 82 wild sites + 24 hatchery strains; wild-vs-hatchery bonus. Richest but messiest; non-SEA.

---

## 4. Phase 1 — Peafowl QC & baseline *(structure + diversity)*

- **QC/filtering → TWO callsets:** `bcftools norm -m -any` → biallelic SNPs → depth/GQ/missingness (`--max-missing 0.8–0.9`) → **MAC ≥ 3** → per-**population** HWE. Set A: neutral, LD-pruned (`--indep-pairwise 50 10 0.1`) for structure/N_e. Set B: lightly filtered (no MAF) for diversity. *Document every threshold in `config.yaml`.*
- **Kin/duplicate screen FIRST** (PLINK `--king` / KING) — remove relatives before structure/N_e (undetected kin bias everything).
- **Structure:** PCA (scikit-allel or SNPRelate) + **ADMIXTURE** over a grid of K with replicate seeds; present multiple K + triangulate with PCA; don't over-interpret "best K."
- **Diversity:** Ho/He, rarefied allelic richness, individual heterozygosity. π via **pixy** only if invariant sites exist; else report Ho/He + caveat.
- Reproduce the paper's headline structure/diversity numbers.

**Conceptual checkpoint:** *Explain the difference between Ho, He, π, and F. Why screen kin before structure?*
**Reading:** O'Leary 2018 (filtering); Sopniewski & Catullo 2024 (heterozygosity pitfalls); "diversity ≠ inbreeding ≠ N_e" (scoping §8).

---

## 5. Phase 2 — Peafowl N_e + the results cube *(the engineering core)*

- **Contemporary N_e:** currentNe2 (no genetic map needed → ideal) + NeEstimator-LDNe across PCrit (cross-check). **Recent trajectory:** GONE2 (context only — GBF guidance excludes it from the contemporary indicator).
- **Structure modeling:** per-population vs pooled (unmodeled structure biases N_e 10–100× low).
- **Build the Snakemake parameter sweep → `results_cube.parquet`:** `{filter preset (lenient/standard/strict)} × {N_e method} × {structure on/off}` → `{N_e, CI}`. This declarative grid is exactly what Snakemake is for.

**Conceptual checkpoint:** *Why do LD-N_e estimates collapse when structure is unmodeled? What time horizon does each method estimate?*
**Reading:** Waples 2024 N_e review; "Idiot's Guide to N_e"; Santiago et al. 2025 (structure bias); currentNe2/GONE2 docs.

---

## 6. Phase 3 — GBF indicators + robustness + fragility-explorer MVP  ← **MVP milestone**

- Compute the **N_e > 500 indicator** (proportion of populations above threshold) + **Populations Maintained**, from the cube. Contrast genomic N_e with the census proxy (N_c ≥ 5,000).
- **Robustness (angle C):** quantify how the pass/fail verdict moves across the cube.
- **Build the Streamlit fragility explorer** reading the cube: three knobs → verdict flips live; tabs for N_e/GBF (main) + structure (PCA/ADMIXTURE). Deploy to **Streamlit Community Cloud / HF Spaces** → live URL.

**Conceptual checkpoint:** *What does N_e > 500 actually mean? Why was the indicator designed to be computable without DNA?*
**Reading:** GBF indicator guidelines (ccgenetics.github.io); Mastretta-Yanes 2024; Clark 2024.
**At this point you have a complete, shippable artifact: repo + live tool + the policy/N_e/robustness story.** If January looms, ship here.

---

## 7. Phase 4 — Wolf deep chapter: genetic load + ROH *(the frontier; 8 GB-safe)*

CLI-streaming-first throughout — the 12 GB VCF never enters RAM:
- Per-chromosome `bcftools view` splits (on USB); stream-filter.
- **ROH:** `bcftools roh` per sample/chromosome (HMM, low RAM); classify long (recent) vs short (ancient); F_ROH per individual.
- **Genetic load:** stream the VEP impact classes + GERP scores; polarize derived alleles with the deposited outgroups; tally **realized** (homozygous derived-deleterious) vs **masked** (heterozygous) load per individual / generation; track change across the ~5 inbreeding generations.
- Add a **wolf-load tab** to the explorer (realized vs masked; ROH-parameter sensitivity).

**Conceptual checkpoint:** *Realized vs masked load — why does inbreeding convert one to the other? Why prefer GERP over PolyPhen for non-human species?*
**Reading:** Bertorelle 2022 (load); Dussex 2023 (purging); Smeds & Ellegren 2022 (source); ROH sensitivity (PLOS Comp Biol 2024); Stoffel & Hoffman 2025 (long ROH & inbreeding depression).

---

## 8. Phase 5 — Polish: tool + paper-grade report  ← **"two deliverables done" milestone**

- Polish the explorer (captions, a **limitations panel** surfacing the §8 caveats — claim *risk* not *depression*, CIs, ascertainment, small-n power).
- Write `report.qmd`: intro → methods → results → **limitations** → reproducibility statement.
- Finalize repo: `env.yml`, `renv.lock`, Snakefile, config, README one-command reproduction. **Re-run the whole DAG from scratch to prove reproducibility.**

---

## 9. Phase 6 — (Stretch) Preprint

Render `report.qmd` → formatted manuscript → EcoEvoRxiv/bioRxiv. ~reformat, since the report is already paper-grade.

---

## 10. Critical path & what's droppable for January

```
Phase 0 → 1 → 2 → 3   = the load-bearing spine (peafowl + live tool). A complete artifact on its own.
        Phase 4       = depth upgrade (wolf load — the "wow" frontier).
        Phase 5       = polish.
        Phase 6       = pure stretch (preprint).
```
- **Must-ship by January:** Phases 0–3 + a polished pass of 5 on the peafowl side. This alone is impressive (live tool + reproducible repo + policy-relevant N_e/robustness story).
- **First to drop if time is tight:** Phase 6 (paper), then Phase 4's temporal sub-analysis, then Phase 4 entirely (the wolf chapter is the upgrade, not the foundation).

---

## 11. Risks & mitigations (this configuration)

| Risk | Likelihood | Mitigation |
|---|---|---|
| **Peafowl too thin for multi-pop N_e/GBF** | ~~Med~~ → **Resolved (PASS):** 3 pops, 22 unrelated; small n folded into the fragility thesis | Phase-1 coverage check (GL stack if low-cov); **fallback ladder §3.3** (pangolin → ibex → trout), fires only if usable n <5 in >1 population |
| Apple-Silicon conda fails | Med | `osx-64`/Rosetta env (§3.1); cross-compiled tools tested in Phase 0 |
| Wolf 12 GB strains 8 GB RAM | Med | CLI-streaming-first; `bcftools roh` over RZooRoH; per-chromosome; USB for storage |
| currentNe2/GONE2 won't build on osx-64 | Med | Build with Xcode CLT in Phase 0; currentNe2 is the workhorse, NeEstimator a manual cross-check |
| **Over-claiming** (beginner risk) | Med | Conceptual checkpoints each phase; limitations panel + report section; claim *risk* not *depression* |
| Scope creep into raw-read variant calling | Low | VCF-start by design; both datasets are deposited VCFs |
| NeEstimator GUI not scriptable | Low | Use it only for cross-check; currentNe2 (CLI) drives the Snakemake sweep |

---

## 12. The learning track (mapped to phases)

Phase 0–1: Speciation Genomics tutorials; O'Leary 2018. · Phase 2: Waples 2024 + "Idiot's Guide to N_e" + Santiago 2025. · Phase 3: GBF guidelines + Mastretta-Yanes 2024. · Phase 4: Bertorelle 2022 + Dussex 2023 + ROH-sensitivity. Every phase ends with a one-paragraph conceptual checkpoint you must be able to answer before interpreting results.
