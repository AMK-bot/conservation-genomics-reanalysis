# Conservation Genomics Reanalysis — Execution Plan

**Status:** Execution plan. Decisions locked via a structured grilling session (2026-06-17).
**Companion to:** `conservation-genomics-reanalysis-project-scoping.md` (the scoping doc — the "why/what"; this is the "how").
**Goal:** An impressive, reproducible artifact for competitive university (transfer) applications.
**Ship bound:** January 2027 (~28 weeks out). Planned as if no time limit (depth-maximizing); January is the outer ship date, not a scope constraint. See §10 for the critical path.
**Access:** 100% remote — **no fieldwork, wet lab, specimen handling, or physical-site visits**. Data-access **verified 2026-06-17**: all four turnkey datasets (peafowl, wolf, ibex, trout) are openly downloadable with **no embargo, login, or access request**. (The pangolin SEA fallback is also openly downloadable, but is *reads-only* — a scope caveat, not an access one; see §3.3.) All compute is the user's laptop; deployment/publication is online.

---

> **Adaptation note (2026-06-19):** Phase 0 is **COMPLETE**. This plan was revised in a structured grilling session to match what Phase 0 actually built — see `SETUP.md` (verified status) + `HANDOFF.md` (audit trail). Material changes from the original: storage **USB → internal SSD** (USB corrupts large writes); env built with **micromamba**, not classic conda (8 GB OOM); **R is conda-owned**, `renv.lock` dropped; **`--use-conda` dropped** (single env); **angle G rescoped** from temporal *N_e* to temporal *diversity* erosion (comparative set is only 5 museum + 6 modern); ~~the cube's **N_e-method knob = currentNe2 vs GONE2**~~ (*superseded 2026-06-26 — see §5 adaptation note: the method knob is dropped, GONE2 is context-only, cube = filter × structure*; NeEstimator demoted to a manual cross-check table); the **wolf tab = two live sensitivity tables** (load×GERP, F_ROH×ROH-length); per-population n is **7 / 10 / 5**, not 11/12/7. Sections below reflect these.

## 0. Decisions locked (the inputs to this plan)

| Decision | Resolution | Why |
|---|---|---|
| **Structure** | Two chapters: broad flagship → deep frontier | Covers the whole conservation-genomics toolkit; learns easy→hard |
| **Chapter 1 dataset** | **Green peafowl** *(Pavo muticus)* — Dryad `10.5061/dryad.ffbg79ctc`. **Gate PASSED:** the deposited modern callset *is* the authors' **22 unrelated** across 3 structured pops; **per-pop n = 7 / 10 / 5** (KQ+PE / g_* / s_*) — thinner than first estimated. Comparative callset = **5 museum (`kiz*`) + 6 modern** (temporal contrast). The 31-sample pre-kin callset is **not** deposited. | Verified turnkey WGS VCF + scripts; multi-country; SE Asian icon (IUCN Endangered). Small per-pop n → wide N_e CIs, *folded into the fragility thesis* |
| **Chapter 2 dataset** | **Scandinavian wolf** *(Canis lupus)* — Dryad `10.5061/dryad.7m0cfxpzj` | Only deposit on Earth shipping WGS + VEP + GERP → turnkey genetic load |
| **Data type** | WGS for both | Unlocks the full analysis menu (diversity, N_e, ROH, load) |
| **Chapter 1 angles** | A (GBF indicators) + B (modern N_e) + C (robustness) + D (structure) + **G (temporal *diversity* erosion: 5 museum vs 6 modern — Ho/He + rarefied allelic richness, *not* N_e)** [+ F pixy — stretch] | Scoping doc's flagship, enriched by WGS; G kept as a *supporting diversity contrast* — rescoped from N_e (comparative n too small for credible LD-N_e); presented as a static figure, not a tool knob |
| **Chapter 2 angles** | H (genetic load: realized vs masked) + E (ROH inbreeding history) | The field's hottest frontier, turnkey here |
| **Primary deliverables** | (1) Reproducible repo, (2) interactive **"fragility explorer"** (Streamlit) | Citable + clickable + reproducible; legible to non-specialists |
| **Paper** | Stretch, *after* the two deliverables — but `report.qmd` is written paper-grade from day one so "write the paper" = reformat, not rewrite | Keeps preprint optionality cheap |
| **Tool concept** | Fragility explorer: a **two-knob cube** (filtering stringency × structure modeled/ignored) → live N_e + CI + treaty pass/fail/**indeterminate** verdict, all from **currentNe2**. **GONE2** = a recent-trajectory **context panel** (not a knob, not in the badge — different time horizon, borrowed recombination rate; see §5 adaptation note) | Turns angle C (robustness) into the headline interaction |
| **Architecture** | Workflow computes a **"results cube"** (tidy table); Streamlit just reads it | Deployable on free hosting; reproducible; the cube *is* angle C |
| **Compute** | All local: Apple **M1 / 8 GB RAM** + **internal SSD** (USB abandoned — corrupts large writes) | User's machine; no cloud |
| **Workflow infra** | **Snakemake** + **micromamba** env (osx-64) pinned in `environment.lock.yml`; **R conda-owned** (renv dropped) | Genomics standard (snpArcher-citable); micromamba because classic conda OOMs on 8 GB |
| **Tooling split** | CLI (PLINK/bcftools/VCFtools/ADMIXTURE/currentNe2/GONE2) + Python (scikit-allel, Streamlit — user's strength) + R (SNPRelate/dartR/hierfstat — being learned) | Plays to strengths; R is a targeted learning goal |

**The narrative tie:** *"Assessing genetic status across the modern conservation-genomics toolkit — from the new global biodiversity-treaty indicators on an endangered SE Asian bird, to realized-vs-masked genetic load in an inbred carnivore — and showing how fragile each verdict is to analyst choices."*

---

## 1. Definition of done

- **Repo (load-bearing):** one-command reproduction (`snakemake --cores N` inside the activated `congen` env), pinned `environment.lock.yml` (R packages included — R is conda-owned; no `renv.lock`), the Snakefile, config of all thresholds, the results cube (+ `wolf_load`/`wolf_roh` tables), all figures, and a paper-grade `report.qmd`.
- **Fragility explorer (load-bearing):** live public URL; **two knobs (filter × structure)** wiggle the peafowl N_e/GBF verdict in real time (currentNe2; verdict can read pass / fail / **indeterminate**) **+ a GONE2 recent-trajectory context panel**; a structure/diversity tab (PCA/ADMIXTURE + the static museum-vs-modern temporal-G figure); a wolf tab with two live sensitivity knobs (load×GERP, F_ROH×ROH-length).
- **Preprint (stretch):** `report.qmd` rendered + posted to EcoEvoRxiv/bioRxiv with a DOI.

---

## 2. Architecture & repo layout

```
congen-reanalysis/
├── README.md                  # one-command reproduction + the story
├── environment.yml            # loose spec; build with micromamba
├── environment.lock.yml       # 702 pkgs pinned (R included — conda-owned; no renv.lock)
├── config/
│   └── config.yaml            # ALL filtering thresholds, N_e settings, paths
├── workflow/
│   ├── Snakefile              # the DAG; generates the results cube
│   └── rules/                 # qc.smk, structure.smk, ne.smk, gbf.smk, load.smk
├── scripts/                   # python/ + R/ analysis scripts called by rules
├── results/
│   ├── cube/                  # results_cube.parquet (peafowl) + wolf_load.parquet + wolf_roh.parquet  ← the tool's backends
│   ├── tables/                # diversity, N_e, GBF, load summaries
│   └── figures/
├── app/
│   └── streamlit_app.py       # the fragility explorer (reads results/cube/)
├── report/
│   └── report.qmd             # paper-grade methods/results/limitations
└── data/  (symlinked to internal SSD)  # raw VCFs + per-chromosome splits + intermediates
```

**Data flow:** raw VCF → (Snakemake: QC → kin-screen → structure/diversity/N_e across the parameter grid) → `results_cube.parquet` → Streamlit reads the cube. The heavy bioinformatics never runs in the app.

---

## 3. Phase 0 — Setup & verification (the foundation)  ✅ COMPLETE (2026-06-19)

> **Done — see `SETUP.md` (verified status) + `HANDOFF.md` (audit).** Deltas from the recipe below as actually executed: env built with **micromamba** (classic conda OOM'd on 8 GB); data on **internal SSD** (not USB); **renv dropped** (R conda-owned). The §3.1 code block is kept as historical intent.

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
- ✅ **PEAFOWL MULTI-POPULATION GATE — PASS (verified on the actual deposit).** The deposited modern callset *is* the authors' **22 unrelated** across **3 structured populations** — actual **n = 7 / 10 / 5** (KQ+PE / g_* / s_*; the Dong et al. 2021 paper's pre-kin estimate of ~11/12/7 refers to the undeposited 31-sample set). Comparative callset = **5 museum (`kiz*`) + 6 modern**. Verdict: viable. Two consequences baked into the plan: (a) small per-population n → wide N_e CIs, treated as a **feature of the fragility thesis**, with `currentNe2` as the small-n workhorse; (b) the museum/modern split feeds the **temporal angle (G) — rescoped to a *diversity* contrast** (Ho/He + rarefied allelic richness), since 5-vs-6 is too thin for credible LD-N_e. **Fallback trigger:** brook trout (Dryad `10.5061/dryad.2fqz612sb`) *only if* usable individuals collapse to <5 in more than one population (not fired — see §3.3). **Coverage RESOLVED:** comparative samples all **≥9× (range 9–86×)** → adequate for the deposited hard calls; ANGSD/GL not forced (available as fallback).
- ✅ **WOLF GATE — PASS (2026-06-19).** 211 samples (confirmed `bcftools query -l`); `vep`/`gerp` present + extracted; polarization **already baked into the VCF** (`INFO/AA`, `Pol.2out` = 2 outgroups — no separate file needed); per-chromosome `bcftools view -r 1` = 443,717 records at **24 MB peak RAM** (csi-indexed streaming) → RAM bounded. Data on internal SSD.
- Reproduce both papers' sample tables as a data sanity check.

**Output:** working env, repo skeleton, both datasets downloaded + verified, Chapter-1 dataset confirmed (peafowl, or a fallback from §3.3).
**Reading:** Speciation Genomics setup + filtering tutorials; the two source papers' methods (Dong et al. 2021; Smeds & Ellegren 2022).

### 3.3 Chapter-1 fallback ladder
*Fires only if Phase 1 reveals peafowl's usable per-population n collapses to <5 in more than one population.* **Current n = 7 / 10 / 5 → not fired** (Thailand `s_*` sits at the n=5 boundary; the Phase-1 kin policy in §4 is designed not to breach it). *Try in order:*

1. **SEA option — but reads-only (escalation required): Sunda pangolin** *(Manis javanica)*, Thailand — bioRxiv 2025 (Ewart et al.), ~30 whole genomes across **4 Thai populations** (Western, Khao Yai, Mid-south, Southernmost; F_ST 0.06–0.14). Thailand-**endemic** + a wildlife-forensics / "most-trafficked-mammal" narrative. **Verified 2026-06-17:** data is **openly available but READS-ONLY** — NCBI BioProject `PRJNA1240953`, SRA `SRR32831660`–`SRR32831689` (30 runs), no deposited VCF. → Using it means **calling variants from WGS reads** = the §6 "escalation to avoid," and rough on an all-local 8 GB machine. *Viable only if you deliberately opt into that variant-calling escalation; otherwise there is no turnkey SEA fallback.*
2. **Reliable default — strongest analytical fit: Alpine ibex** *(Capra ibex)* — Dryad `10.5061/dryad.n276d`, **12 populations, 173 individuals (~15/pop)** along a documented reintroduction/drift gradient = the textbook multi-population N_e / "proportion of populations" story (better per-pop n than peafowl). **Verified 2026-06-17:** openly downloadable; single file `DRYAD.raw.SNPfile.gz` (159 MB) is a **GATK-produced VCF — NO format conversion needed** (better than the scoping doc assumed); 101,822 SNPs. Non-SEA. *Analytically stronger than peafowl for the GBF flagship — peafowl wins primary only on the SEA tie + WGS/temporal-erosion angle.*
3. **Alternative backstop: brook trout** *(Salvelinus fontinalis)* — Dryad `10.5061/dryad.2fqz612sb`. **Verified 2026-06-17:** openly downloadable; `full_dataset.vcf` (159 MB, 24,337 SNPs, 267 individuals) + sample-metadata CSV + neutral/outlier annotation. 82 wild sites + 24 hatchery strains; wild-vs-hatchery bonus. Richest but messiest; non-SEA.

---

## 4. Phase 1 — Peafowl QC & baseline *(structure + diversity)*

- **QC/filtering → TWO callsets:** `bcftools norm -m -any` → biallelic SNPs → depth/GQ/missingness → **MAC ≥ 3** → per-**population** HWE. **Set A (structure/N_e) is re-derived *per filter preset* from `Modern_all`** (then LD-pruned `--indep-pairwise 50 10 0.1`) — this *is* the cube's filtering knob: lenient/standard/strict → **1,044k / 420k / 30k** SNPs (~35× spread, confirmed). The authors' pre-pruned neutral set (790,705 SNPs) is a **frozen validation reference only**, never a cube input. Set B (diversity): lightly filtered, no MAF. *Every threshold in `config.yaml`.*
- **Kin/duplicate screen** (PLINK2 KING) — but the deposited 22 are *already* the authors' post-kin set (31→22 happened pre-deposit). So run KING as a **confirmatory QC gate**: report the relatedness matrix as a figure; if a pair exceeds our cutoff but the authors kept it, **keep the published 22 and document it** (don't drop from an n=5 pop). "Where you draw the kin cutoff" is itself an analyst degree of freedom — note it.
- **Structure:** PCA (scikit-allel or SNPRelate) + **ADMIXTURE** over a grid of K with replicate seeds; present multiple K + triangulate with PCA; don't over-interpret "best K."
- **Diversity (incl. angle G):** Ho/He, rarefied allelic richness, individual heterozygosity. π via **pixy** only if invariant sites exist; else Ho/He + caveat. **Angle G (temporal diversity erosion):** museum (5 `kiz*`) vs modern (6) Ho/He + allelic richness **rarefied to equal n**, with an **ancient-DNA damage caveat** (deamination can inflate apparent diversity). The contrast is geographically narrow (modern side is mostly Thailand `s_*`) → report as a **static figure** (diversity tab + report), not a tool knob.
- Reproduce the paper's headline numbers **that the deposited callsets support** (structure/diversity on the 22 + the comparative contrast). Numbers computed on the undeposited 31-sample raw set are out of reach — say so.

**Conceptual checkpoint:** *Explain the difference between Ho, He, π, and F. Why screen kin before structure?*
**Reading:** O'Leary 2018 (filtering); Sopniewski & Catullo 2024 (heterozygosity pitfalls); "diversity ≠ inbreeding ≠ N_e" (scoping §8).

---

## 5. Phase 2 — Peafowl N_e + the results cube *(the engineering core)*

> **Adaptation note (2026-06-26):** §5 rewritten *after* Phase 1 deployed, in a structured grilling session — six decisions, all forced by what Phase 1 actually built (an **LD-pruned** Set A) and by how the N_e tools actually work (they read N_e *out of* LD). The deployed `config.yaml` already encodes the result (cube = filter × structure, `ne_methods: [currentNe2]`); this prose now matches it. **Headline change vs the original §5:** the **N_e-method knob is dropped** — GONE2 measures a different time horizon than currentNe2 *and* structurally needs a recombination map peafowl lacks — so the cube is **filter × structure** only, and **GONE2 becomes a context panel**, not an axis. The "three-knob cube" framing in §0/§1 is corrected to two knobs + a trajectory panel.

- **Input — the load-bearing Phase-1 correction.** LD-N_e estimators read N_e *from* linkage disequilibrium, so the **LD-pruned** Set A (right for PCA/ADMIXTURE/KING) is the **wrong** input here. Phase 2 feeds the per-preset **un-pruned** `results/qc/setA.{preset}.vcf.gz`, and hands currentNe2 the **genome size = 32 Morgans** (the autosome count) so it uses SNP pairs **on different chromosomes** — its "no genetic-map needed" mode, the reason it was chosen. *(The pruned Set A is reused exactly once downstream, as the NeEstimator cross-check input — see below — so it isn't wasted.)*
- **Contemporary N_e (the badge): `currentNe2`, one run per cube cell.** `-k` (full-sib correction) left at default = estimated from the data. **Unbounded upper CIs (∞) are expected at n = 7/10/5** and stored as `inf`. Pass/fail-vs-500 is read off the **point estimate**; when the **CI straddles 500 the verdict is `indeterminate`** — a third badge state, not a forced pass/fail. That indeterminate band *is* the robustness/fragility story (angle C), not a defect. *8 GB guard:* currentNe2 is RAM-hungry; cap SNPs with `-s` (seeded) when a preset exceeds ~200k sites (lenient ≈ 1M). `# ponytail: -s cap only if it OOMs; raise the cap when RAM allows`.
- **The two knobs → cube = filter × structure (currentNe2 only):**
  - **filter** = lenient/standard/strict (the Phase-1 knob, re-used: each preset's *un-pruned* Set A).
  - **structure** = **modeled** (`per_population`: currentNe2 run separately on each of the 3 pops → the three values feeding the GBF "fraction > 500") **vs ignored** (`pooled`: all 22 lumped, no correction → Wahlund-biased low — the cautionary "10–100× low" contrast). currentNe2's `-x` metapopulation correction is a **report cross-check, not a third knob position**.
  - → 3 × 2 = **6 currentNe2 runs per preset-set** (3 per-pop + 1 pooled, per preset).
- **The cube — `results/cube/results_cube.parquet`, long/tidy, one row per estimate:** `preset · structure_mode · population · ne_method · ne_point · ci_low · ci_high · n_ind · n_snps · k`. `ne_method` is the constant `currentNe2` (the single automated estimator; the validator asserts it stays constant). **Pooled rows carry `population = ALL`.** The GBF fraction (Phase 3) reads **per_population rows only**; pooled rows are the structure-bias contrast, never a GBF input.
- **GONE2 — recent-trajectory *context panel* (NOT a cube axis, NOT in the badge):** one curve, **all 22** birds, `-x` (metapopulation of equal-size subpops), standard-preset **un-pruned** Set A, `-g 0` (unphased diploids), and a **documented constant `-r ≈ 3 cM/Mb`** (generic-bird stand-in — peafowl has no map). One figure, "recent species-level trajectory — context only," with the caveats on it: thin n, borrowed rate, recent-past ≠ contemporary. GBF guidance excludes recent-trajectory from the contemporary indicator, so it never touches the verdict.
- **NeEstimator-LDNe — manual field-standard cross-check (outside the DAG):** Java GUI → hand-run on the **standard-preset LD-pruned Set A** (NeEstimator *assumes unlinked* markers, so the pruned VCF is exactly its input — the one N_e use of Phase 1's pruned output), **3 pops × 3 PCrit** (0.05/0.02/0.01), pasted into **one report table** against currentNe2's per-pop numbers. Confirms the headline N_e isn't a currentNe2-specific artifact.
- **New code:** `workflow/rules/ne.smk` (`currentne2` [one preset × structure cell], `gone2_context`, `assemble_cube`); thin `scripts/python/{currentne2_parse,assemble_cube}.py` (tool text → tidy rows); Snakefile `phase2` target + a `validate` extension (cube non-empty; 6 cells/preset present; badge states sane; ∞ handled). NeEstimator stays manual.

**Conceptual checkpoint:** *Why do LD-N_e estimates collapse when structure is unmodeled (Wahlund inflates LD → N_e biased low)? Why is currentNe2's "different-chromosome" estimate the cleaner one — and why does LD-pruning destroy the very signal it measures? What time horizon does each tool see: currentNe2 (now) vs GONE2 (recent past)?*
**Reading:** Waples 2024 N_e review; "Idiot's Guide to N_e"; Santiago et al. 2024/2025 (currentNe + structure bias); Do et al. 2014 (NeEstimator); currentNe2/GONE2 docs.

---

## 6. Phase 3 — GBF indicators + robustness + fragility-explorer MVP  ← **MVP milestone**

- Compute the **N_e > 500 indicator** (proportion of populations above threshold) + **Populations Maintained**, from the cube. Contrast genomic N_e with the census proxy (N_c ≥ 5,000).
- **Robustness (angle C):** quantify how the pass/fail verdict moves across the cube.
- **Build the Streamlit fragility explorer** reading the cube: **two knobs (filter × structure) → verdict flips live** (currentNe2 badge: pass / fail / **indeterminate**). A **separate GONE2 trajectory panel** shows the recent-N_e curve with a time-horizon + borrowed-rate note (context only, not wired to the verdict). Tabs: **N_e/GBF** (main) + **structure/diversity** (PCA/ADMIXTURE + the static museum-vs-modern temporal-G figure). [Wolf tab added in Phase 4.] Deploy to **Streamlit Community Cloud / HF Spaces** → live URL.

**Conceptual checkpoint:** *What does N_e > 500 actually mean? Why was the indicator designed to be computable without DNA?*
**Reading:** GBF indicator guidelines (ccgenetics.github.io); Mastretta-Yanes 2024; Clark 2024.
**At this point you have a complete, shippable artifact: repo + live tool + the policy/N_e/robustness story.** If January looms, ship here.

---

## 7. Phase 4 — Wolf deep chapter: genetic load + ROH *(the frontier; 8 GB-safe)*

CLI-streaming-first throughout — the 12 GB VCF never enters RAM (verified: per-chrom view = 24 MB peak). Data on **internal SSD** (not USB):
- Per-chromosome `bcftools view` splits; stream-filter. 211-sample `Pol.2out.mac2` callset; `chrX` = 74 females (separate file).
- **ROH:** `bcftools roh` per sample/chromosome (HMM, low RAM); classify long (recent) vs short (ancient); F_ROH per individual.
- **Genetic load:** stream the VEP impact classes + GERP scores (derived-allele polarization **already baked into the VCF** as `INFO/AA`); tally **realized** (homozygous derived-deleterious) vs **masked** (heterozygous) load per individual / generation; track change across the ~5 inbreeding generations. GERP default **4.0** (source value), swept over **[2,3,4]**.
- Add a **wolf tab** to the explorer driven by **two live sensitivity tables** the workflow builds: `wolf_load.parquet` (per-individual realized vs masked load **× GERP threshold [2,3,4]**) and `wolf_roh.parquet` (per-individual F_ROH **× ROH-length cutoff**). Two knobs (GERP, ROH-length) → the load/inbreeding verdicts move live (fragility thesis on the wolf side).

**Conceptual checkpoint:** *Realized vs masked load — why does inbreeding convert one to the other? Why prefer GERP over PolyPhen for non-human species?*
**Reading:** Bertorelle 2022 (load); Dussex 2023 (purging); Smeds & Ellegren 2022 (source); ROH sensitivity (PLOS Comp Biol 2024); Stoffel & Hoffman 2025 (long ROH & inbreeding depression).

---

## 8. Phase 5 — Polish: tool + paper-grade report  ← **"two deliverables done" milestone**

- Polish the explorer (captions, a **limitations panel** surfacing the §8 caveats — claim *risk* not *depression*, CIs, ascertainment, small-n power).
- Write `report.qmd`: intro → methods → results → **limitations** → reproducibility statement.
- Finalize repo: `environment.lock.yml` (R included — no `renv.lock`), Snakefile, config, README one-command reproduction (`micromamba create -f environment.lock.yml` → activate → `snakemake --cores N`). **Re-run the whole DAG from scratch to prove reproducibility.**

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
| **Peafowl too thin for multi-pop N_e/GBF** | ~~Med~~ → **Resolved (PASS):** 3 pops, 22 unrelated (**n = 7/10/5**); small n folded into the fragility thesis | Confirmatory kin gate keeps the published 22 (§4); **fallback ladder §3.3** (pangolin → ibex → trout), fires only if usable n <5 in >1 population |
| Apple-Silicon conda fails | ~~Med~~ → **Resolved:** classic conda OOM'd on 8 GB → built with **micromamba** (osx-64/Rosetta); tools cross-compiled + tested |
| Wolf 12 GB strains 8 GB RAM | ~~Med~~ → **Resolved (low):** verified **24 MB peak** per-chrom; CLI-streaming-first; `bcftools roh`; per-chromosome; **internal SSD** (USB abandoned) |
| currentNe2/GONE2 won't build on osx-64 | ~~Med~~ → **Resolved:** both built (osx-64, pinned SHAs); currentNe2 needed a 1-line clang patch; NeEstimator = manual cross-check |
| **GONE2 vs currentNe2 conflated** (different time horizons) | ~~Med~~ → **Resolved (plan-adapt §5):** GONE2 is **context-only**, not a cube axis; cube knob is filter × structure (currentNe2); badge currentNe2-only | GONE2 panel labelled "recent trajectory" + borrowed-rate caveat; report explains the two tools answer different questions |
| **Over-claiming** (beginner risk) | Med | Conceptual checkpoints each phase; limitations panel + report section; claim *risk* not *depression* |
| Scope creep into raw-read variant calling | Low | VCF-start by design; both datasets are deposited VCFs |
| NeEstimator GUI not scriptable | Low | Use it only for cross-check; currentNe2 (CLI) drives the Snakemake sweep |

---

## 12. The learning track (mapped to phases)

Phase 0–1: Speciation Genomics tutorials; O'Leary 2018. · Phase 2: Waples 2024 + "Idiot's Guide to N_e" + Santiago 2025. · Phase 3: GBF guidelines + Mastretta-Yanes 2024. · Phase 4: Bertorelle 2022 + Dussex 2023 + ROH-sensitivity. Every phase ends with a one-paragraph conceptual checkpoint you must be able to answer before interpreting results.

## Deviations

deviations from phase 1:

**Phase 1 status: COMPLETE (2026-06-20).** Full DAG (`snakemake -s workflow/Snakefile phase1`, 42 jobs)
runs clean from the cached norm-parent; validation = **0 FAIL / 7 PASS / 3 WARN** (`results/PHASE1_VALIDATION.md`).
Implementation = `workflow/rules/{qc,structure,diversity}.smk` + `scripts/python/{diversity,pca,to_hierfstat,plots,validate}.py`
+ `scripts/R/allelic_richness.R` + `scripts/filter_preset.sh`. Verified by an adversarial code-review workflow
(5 dimensions → find → verify; 3 confirmed bugs fixed, 11 refuted) plus runtime diagnosis.

*Structural / tooling deviations:*
- **(A) New rule file `diversity.smk`.** Plan §2 listed qc/structure/ne/gbf/load; diversity (Ho/He/AR + temporal)
  got its own file rather than being folded into structure.smk — clearer separation.
- **(B) Autosomes made explicit.** Set A/B restricted to the 32 `chromosome_<int>` contigs;
  `chromosome_Z`, `chromosome_W`, `mitochondrion`, and 157 scaffolds dropped (`config/peafowl_autosomes.txt`).
  Plan didn't specify; required for LD/structure/N_e. Z/W are explicitly named in the assembly → no sex-chr ambiguity.
- **(E) Set B params added to config** (`peafowl.set_b`: DP≥4, GQ≥15, max_missing 0.5; no MAF/MAC/HWE/LD-prune).
- **(F) Allelic richness via a Python→hierfstat bridge.** `dartR::gl.read.vcf` needs **vcfR**, which is NOT in the
  locked env. Rather than mutate `environment.lock.yml`, `to_hierfstat.py` (scikit-allel) writes the hierfstat
  genotype table and `allelic_richness.R` does only the stats. Rarefaction reaches the true smallest-pop n=5 via
  `--complete-only` (complete-case loci) + a seeded thin (`peafowl.diversity.ar_max_sites: 50000`) for 8 GB safety.
- **(G) R invoked as `Rscript --vanilla`.** The repo's inert renv `.Rprofile` (`source("renv/activate.R")`) shadows
  the conda R library (plan already dropped renv) → without `--vanilla`, R sees an empty library. Every R rule uses
  it. *Recommend the user eventually neuter `.Rprofile` so interactive R in this dir also works.*
- **(H) plink `--double-id` everywhere.** Sample IDs contain `_` (PE125_220, s_9_1, g_1); plink's default FID/IID
  split errors otherwise.
- **(J) ADMIXTURE bed uses integer chromosomes** — `.bim` chr column stripped of the `chromosome_` prefix (portable
  `sed`, no `-i`) so ADMIXTURE accepts the codes.
- **(N) Structure/kinship preset = standard** (`peafowl.kinship.structure_preset`); PCA/ADMIXTURE/KING figures use the
  standard-preset pruned Set A.

*Counts / methods:*
- **(C) Re-derived per-preset post-MAC counts** = lenient **1,046,916** / standard **420,826** / strict **30,143**,
  vs the HANDOFF targets 1,044,447 / 419,616 / 29,851 (**+0.2 to +1.0%**). The excess is `bcftools norm -m -any`
  splitting multiallelic SNP sites into biallelic records (the plan's stated method); the HANDOFF figures likely
  dropped multiallelics outright. The 35× filter-knob spread is fully reproduced. Persisted to `*.postmac_count`.
- **(D) Per-population HWE via `vcftools --hardy` union.** A site is dropped if P_HWE < 1e-6 in ANY of the 3
  populations (pooled HWE rejected — population structure / Wahlund creates false departures). P_HWE column located
  by header name for version robustness (`scripts/filter_preset.sh`).

*Bugs caught + fixed during build (the verification half earned its keep):*
- **(I) LD-prune was a silent no-op — REAL BUG (high), caught at runtime.** All VCF IDs are `.`, so `--extract
  prune.in` matched every `.`-ID variant and kept the FULL set (standard "pruned" = 420,826, not 19,611). ADMIXTURE
  was crunching 420k *linked* SNPs (slow + scientifically wrong). Fixed with `--set-missing-var-ids '@:#:$1:$2'`
  (unique chr:pos:allele IDs) → standard prunes correctly to **19,611**. plink **1.9** kept (plink2 refuses LD
  pruning at n<50; small-n is folded into the fragility thesis, not avoided).
- **(K) KING read from the pruned VCF, not the bed — REAL BUG, caught at runtime.** Because (J) made the bed's chr
  codes integers, plink2 reads `27` as human-autosome-27 (invalid) even with `--allow-extra-chr`. KING now runs on
  the pruned **VCF** (non-numeric `chromosome_*` names, which `--allow-extra-chr` does handle).
- **(L) Temporal callset normalized for diversity, raw for π — from the review (med).** Ho/He/AR were computed on the
  RAW comparative VCF (2,056 indels/multiallelics), inconsistent with the normalized Set B, and `to_hierfstat.py`'s
  11/12/22 coding mis-counted multiallelic alleles. New `comparative_norm` rule → biallelic SNP autosomes + Set-B
  mask feeds `temporal_diversity`; `temporal_pi` **deliberately stays on the raw deposited comparative** (faithful to
  Dong et al. 2021's `vcftools --window-pi`). `to_hierfstat.py` also drops multiallelic loci defensively.
- **(O) plots.py ADMIXTURE NaN-CV guard** (drop NaN before best-seed `idxmin`) — low-severity robustness, from review.

*Data-level deviation (documented as a caveat, not fixable):*
- **(M) `s_9_2 → PE125_220` in the temporal modern group.** The authors' raw `Nucleotide_diversity_.sh` used 6 Thai
  `s_*` (incl. `s_9_2`, which is NOT in the deposit). The deposited comparative substitutes `PE125_220` (Yunnan), so
  the museum-vs-modern contrast is geographically narrow (modern = 5 Thai + 1 Yunnan vs museum `kiz*`).

**Phase-1 scientific findings to carry forward (honest, non-overclaimed):**
- **Modern diversity:** Thailand (n=5) lowest (He 0.395 / rarefied AR 1.93); Vietnam highest Ho; **Yunnan Fis = 0.086**
  (heterozygote deficit), coherent with elevated within-Yunnan KING relatedness — a related/captive-source signal.
- **Structure:** PCA cleanly separates 3 pops (centroid gap 91 vs within-spread 38) but per-PC variance is low
  (PC1 ≈ 9%); ADMIXTURE CV is **monotonic in K (favours K=1)** — a small-n artifact, so structure is read from PCA,
  not CV. (Triangulate, don't over-interpret "best K" — as planned.)
- **Kinship gate:** KING flags **151/231 pairs ≥ 0.0884** — KING-robust is biased under strong structure, so the
  cross-population values are unreliable; the interpretable signal is within-population. **All 22 birds kept** (plan §4).
- **Temporal erosion (angle G):** the signal is **weak and metric-dependent** — median π and Ho weakly museum>modern
  (erosion-consistent: π 3.70e-4 vs 3.42e-4), but He (0.458 vs 0.463) and rarefied AR (1.984 vs 1.989) are essentially
  flat. Reported as a contrast direction only, with aDNA-deamination + geographic-mismatch caveats. No strong erosion claim.

**Known follow-ups (deferred, not blockers):** (1) the kinship figure could split within- vs cross-population pairs to
make the KING-under-structure caveat visual; (2) neuter the renv `.Rprofile`; (3) the 3 WARN checks are reported-not-asserted by design.

---

deviations from phase 2:

**Phase 2 status: COMPLETE (2026-06-26).** `snakemake -s workflow/Snakefile phase2 --cores 8` (20-job DAG) runs clean;
validation = **0 FAIL / 9 PASS / 3 WARN** (`results/PHASE2_VALIDATION.md`). Deliverables built: the fragility cube
`results/cube/results_cube.parquet` (+ `.csv` mirror, 12 rows), `results/figures/ne_cube.png`, the GONE2 context trajectory
(`results/tables/gone2_trajectory.tsv` + `results/figures/gone2_trajectory.png`), the currentNe2 `-x` cross-check
(`results/tables/ne_metapop_xcheck.tsv`), and the NeEstimator GenePop input (`results/ne/neestimator/setA.standard.pruned.genepop`).
Every currentNe2 output is kept raw under `results/ne/raw/` for audit.

*Tooling fixes — the N_e binaries had never actually been run on data (HANDOFF only verified `--help`):*
- **(P2-A) currentNe2 segfaulted on EVERY run — REAL BUG (high), caught at first data run.** `build_tools.sh` compiled
  without upstream's `-mcmodel=medium`, but the source declares a **4 GB static array** `char indi[2000][2000000]`. Under
  the x86_64 small code model that symbol isn't addressable → SIGSEGV on any input (even 200 SNPs), independent of data size.
  **Fix:** shrink the compile-time caps to what our data needs — `MAXIND 2000→64`, `MAXLOCI 2000000→1100000` (covers the full
  un-pruned lenient ~1.05M) → arrays ~70 MB. Measured peak RSS **8.5 MB**. Baked into `build_tools.sh` (idempotent sed). The
  plan's "8 GB RAM guard / cap when >200k sites" was aimed at RAM, which turns out to be a non-issue.
- **(P2-B) Deterministic RNG seed for reproducible `-s` — patch.** currentNe2 seeds `std::mt19937` from
  `std::random_device` (and exposes **no seed CLI flag**), so its `-s` SNP subsampling is non-reproducible — fatal for a
  re-runnable cube. Patched the seed to a fixed constant (`g(42)`). Verified: identical cross-chromosome estimates across
  repeat runs **and** across thread counts (`-t 2` vs `-t 4`). This is the only route to the plan's "`-s` (seeded)" — the
  flag the plan assumed doesn't exist.
- **(P2-C) SNP cap = 25,000, not "~200k"; chosen for RUNTIME, not RAM.** currentNe2's pair work is ~quadratic in SNP count
  (`-s 50k` ≈ 6 min per pooled run; `-s 200k` would be ~90 min **per run**, hours for the sweep). RAM is 8.5 MB regardless.
  Cap 25,000 keeps pooled runs ~50 s, per-pop ~30 s (full sweep ~9 min) while the cross-chromosome estimate is already
  saturated (~3×10⁸ SNP pairs — NeEstimator routinely uses far fewer). `config: peafowl.ne.snp_cap`.

*Method decisions (forced by how currentNe2 actually writes output):*
- **(P2-D) Headline = the cross-chromosome estimate; CI = 90%; whole-genome fallback.** With a genome size + a multi-chromosome
  VCF, currentNe2 emits TWO estimates: "integration over the whole genome" (all pairs) and "based only on LD between
  chromosomes". Per plan §5 the **cross-chromosome** one is the headline (`currentne2_parse.py` prefers it, falling back to
  whole-genome only on non-convergence, recorded in column `ne_basis`). currentNe2 reports **50% and 90% CIs (not 95%)** — the
  cube stores the **90%**, and the stub app's "95% CI" label is corrected to 90%. Verified `flag_chr` (the cross-chromosome
  branch) only fires when the input spans >1 chromosome — the un-pruned per-preset Set A does; a single-chromosome slice
  silently degrades to whole-genome. Unbounded / ≥1e7 upper bounds → `inf` (none occurred — actual CIs are wide-but-finite,
  e.g. Vietnam-lenient upper = 37,795; the plan's expectation of literal ∞ didn't materialise at these n).
- **(P2-E) Cube = 12 rows (4 per preset) — clarifies the plan's "6 cells/preset".** Concrete enumeration: 3 presets ×
  (3 `per_population` pops + 1 `pooled`=ALL) = **12 rows**. The plan's "3×2 = 6 … 6 cells/preset" double-counts (it conflates
  the 6 preset×structure_mode *combinations* with per-cell rows); the operative count is 3 per-pop + 1 pooled = 4 rows/preset.
  `validate_phase2.py` asserts exactly this shape.
- **(P2-F) Cube schema + minimal app touch.** Columns: `filter_preset, structure_mode, population, ne_method, ne_point,
  ci_low, ci_high, n_ind, n_snps, k` (plan §5) **plus two provenance columns**: `ne_basis` (cross_chromosome|whole_genome) and
  `gbf_state` (the three-state verdict). Used `filter_preset` (the app's name, clearer than the plan's `preset`) and
  `ne_point` (the plan's name). Made a **minimal** edit to the Phase-0 stub `app/streamlit_app.py` so it reads the new cube
  without a KeyError (`ne`→`ne_point`, added the population selector `per_population` needs, three-state badge); the full
  explorer build stays Phase 3.
- **(P2-G) GBF three-state verdict lives in the workflow, not the app.** `gbf_state` = `indeterminate` if no estimate
  converged OR the 90% CI straddles 500; else `pass` (point>500) / `fail`. Computed in `currentne2_parse.py` (testable,
  validated), displayed by the app — not recomputed client-side.

*GONE2 (context panel) — two hard requirements discovered at first data run:*
- **(P2-H) GONE2 aborts unless EVERY chromosome is 20–1000 cM → restricted to macrochromosomes.** `lib/sample.cpp` sets
  `okchromsize=false` and `exit(EXIT_FAILURE)` for any chromosome outside 20–1000 cM (it does **not** drop them). At the
  borrowed 3 cM/Mb the peafowl microchromosomes (<6.67 Mb SNP-span) fall below 20 cM, so GONE2 refused to run on the full
  autosome set. **Fix:** the `gone2_context` rule restricts the input to chromosomes whose SNP-span × rate ∈ **[25, 1000] cM**
  (25 = margin above 20 so `-s` subsampling can't push a near-boundary chromosome under) → **17 macrochromosomes, ~377k SNPs**.
  Stated on the figure as a caveat. `config: peafowl.ne.gone2.{min_chrom_cm,max_chrom_cm}`.
- **(P2-I) GONE2 `-x` writes `_GONE2_Ne_mix` in a different layout.** The metapopulation run outputs `…_GONE2_Ne_mix`
  (header with Fst/migration/n_subpops, then columns `Rec_rate_bin generation N_T_metapop Ne_metapop d²`), **not** the
  panmictic `…_GONE2_Ne` (`Generation Ne_diploids`). New `gone2_parse.py` normalises either into a clean `generation⇥Ne`
  TSV, taking **N_T_metapop** (the total metapopulation N_e = the species-level trajectory) for `-x`. The borrowed-rate +
  microchromosome-drop + "recent-past ≠ contemporary" caveats are printed on the figure. Result: a clear recent decline,
  N_T ≈ 3,500 (≈400 gen ago) → ≈177 (most recent) — context only, never the badge.
- **(P2-J) currentNe2 `-x` metapopulation cross-check emits no CIs in genome-size mode.** With a genome size supplied,
  currentNe2's `-x` branch prints "No CIs are calculated", so `ne_metapop_xcheck.tsv` carries N_T + Fst + migration with blank
  CI columns (handled by `ne_xcheck_collate.py`, robust to non-convergence). This is a report cross-check, never a cube axis.

*NeEstimator (manual, outside the DAG) — input automated:*
- **(P2-K)** Added `vcf_to_genepop.py` + rule `neestimator_input` producing the GenePop input (standard-preset **LD-pruned**
  Set A — the one N_e use of Phase 1's pruned output; NeEstimator assumes unlinked markers). `report/ne_crosscheck.md` has the
  GUI procedure + a fill-in comparison table. Only the GUI run + the comparison table stay manual (as the plan intends).

*New code (plan §5 "new code" delivered):* `workflow/rules/ne.smk` (`currentne2_cell`, `assemble_cube`, `cube_figure`,
`currentne2_xcheck`, `xcheck_table`, `neestimator_input`, `gone2_context`); `scripts/python/{currentne2_parse, assemble_cube,
ne_xcheck_collate, gone2_parse, vcf_to_genepop, validate_phase2}.py`; `plots.py` += `gone2`,`cube` subcommands;
`config.yaml` += `peafowl.ne.{genome_size_morgans, snp_cap, threads, ci_pct, gone2.*}`; `Snakefile` += `phase2` /
`validate_phase2` targets (and `rule all` now includes Phase 2). `build_tools.sh` += the two currentNe2 patches (P2-A/B).
Wildcard rename `pop`→`grp` (Snakemake reserves `pop`).

**Phase-2 scientific findings (honest, non-overclaimed — the fragility result, not a bug):**
- **No population confidently passes N_e > 500 under any preset.** Per-population GBF fraction = **0/3 pass** for lenient,
  standard and strict. Verdicts are `fail` (point and 90% CI below 500) or `indeterminate` (CI straddles 500, or currentNe2
  could not estimate). Exactly the plan's stated honest expectation at n = 7/10/5.
- **currentNe2 contemporary N_e is small and CIs are wide.** Lenient cross-chromosome: Yunnan 55 [20–152], Thailand 76
  [18–320], Vietnam 2,293 [139–37,795] (the lone point above 500, but its CI straddles → indeterminate). Standard/strict
  per-pop mostly **fail to converge** (extreme heterozygote excess at small n + MAC filtering, e.g. strict Thailand F = −0.89)
  → indeterminate. Convergence itself is preset-fragile (Vietnam converges lenient, not standard) — part of the story.
- **Wahlund contrast visible but noisy.** Pooled (all 22, structure ignored) trends low and rises with stringency
  (lenient 52 → standard 89 → strict 108), below most per-population estimates — the predicted "pooling biases N_e low"
  direction, muddied by small-n noise (Vietnam's wild 2,293). Reported, not asserted.
- **`-x` metapopulation cross-check** gives N_T = 65 / 132 / 1,637 (lenient/standard/strict) — itself wildly preset-fragile,
  reinforcing the robustness thesis rather than pinning a number.
- **GONE2 context trajectory** shows a recent decline (N_T ~3,500 → ~177 over ~400 generations) — consistent with an
  endangered species, but on thin n + a borrowed avian recombination rate + macrochromosomes only, so it is presented as
  context with caveats on the figure, never as the contemporary indicator.

**Known follow-ups (deferred, not blockers):** (1) the Phase-3 app build wires the GONE2 panel + structure/diversity tab and a
limitations panel onto this cube; (2) the NeEstimator-LDNe GUI run + comparison table (`report/ne_crosscheck.md`) are the one
manual step; (3) literal ∞ upper-CI handling is implemented but untriggered at these n (CIs were wide-but-finite).
