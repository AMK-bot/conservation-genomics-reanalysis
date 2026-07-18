# Phase 0 — Setup & Verification status

> **Scope note (2026-07-18):** this file records the completed Phase-0 environment/data setup. It is
> not the whole-project status page; current completion work is tracked in `CGplan.md` Phase 5/5A.

Tracks the plan's §3 Phase 0 (CGplan.md). Updated 2026-06-19.

## Machine (verified 2026-06-18)

| Item | Status |
|---|---|
| Chip | Apple **M1** (arm64), 8 GB RAM |
| Rosetta 2 | ✅ installed |
| Xcode Command Line Tools | ✅ clang 15 (source builds OK for currentNe2/GONE2) |
| conda | Anaconda3 base, **already `osx-64`/x86_64 under Rosetta** — conda **4.12.0** (old classic solver) |
| R | ✅ 4.4.3 (via the `congen` env) |
| Internal disk free | ~178 GB (data moved here) |
| USB `PS` | exFAT (reformatted from FAT32). ⚠️ **Corrupts large writes** — both 11.6 GB wolf downloads failed integrity at random offsets; internal copy clean. **No longer used** for project data. |

## 3.1 Environment

- [x] Rosetta present (no install needed).
- [x] `environment.yml` authored (osx-64; conda-forge + bioconda + defaults).
- [x] **`congen` env built** — ⚠️ classic conda 4.12 was **OOM-killed** (exit 137) solving on 8 GB; rebuilt with **micromamba** (libsolv, low-mem). All tools verified: bcftools 1.23, samtools 1.23, vcftools 0.1.17, plink 1.9/2.0, admixture 1.3, pixy, snakemake 9.23, R 4.4.3, quarto; R pkgs SNPRelate 1.40, dartR 2.9.9, hierfstat 0.5.11, adegenet 2.1.11, renv 1.2.3.
- [x] `subdir: osx-64` pinned (env `.condarc`).
- [x] Portable `environment.lock.yml` exported (694 pinned dependencies; no user-specific prefix).
- [x] currentNe2 + GONE2 built from source (`scripts/build_tools.sh`; x86_64 + env libomp). currentNe2 needed a 1-line VLA-init patch for Apple clang. NeEstimator v2 = manual cross-check (not built).
- [x] Repo skeleton created (config / workflow / scripts / results / app / report / data / tools).
- [x] `git init` + commits.
- [x] `renv::init(bare=TRUE)` was tried during setup; its scaffold is retained as history, but the `.Rprofile` autoloader is disabled and no `renv.lock` is used. R packages are pinned by conda in `environment.lock.yml`.
- [x] `data/` → **internal-SSD** symlinks (`data/peafowl`, `data/wolf` → `~/Desktop/MMP/congen_data/...`). Was USB, but the USB corrupts large writes → moved to internal (see Storage).

> **Solver note:** the build tool is `micromamba` (the OOM with classic conda is the
> documented Apple-Silicon/8 GB risk). The env is still a standard conda env at
> `~/opt/anaconda3/envs/congen` — `conda activate congen` works normally.

## 3.2 Verification gates

- [x] **Peafowl multi-population gate** — PASS: Set A/B = **22 unrelated** × 3 pops (`KQ/PE`, `g_*`, `s_*`); 790,705 (neutral) / 1,139,469 (all) SNPs.
- [x] **Wolf gate** — PASS: 211 samples; polarized (`INFO/AA`, `Pol.2out` = 2 outgroups, **no separate file needed**); `vep`/`gerp` present + extracted; per-chromosome `bcftools view -r 1` = 443,717 records at **24 MB peak RAM** (csi-indexed streaming) → RAM bounded ✓.
- [x] Sample-table sanity — peafowl Set A/B 22, comparative 11, wolf 211; consistent with the deposits.
- [x] Peafowl coverage check — comparative callset all **≥9× (range 9–86×)**; adequate for the deposited hard-called genotypes → **ANGSD/GL not forced** by coverage (available as fallback). Angle-G *metric* = a Phase-1 design choice, not a data blocker.

## Data — DOWNLOADED + VERIFIED (2026-06-19)

All 22 files fetched via `scripts/fetch_data.sh` (Dryad OAuth2; token from env vars):
peafowl 18 files (751 MB) + wolf 4 files (11 GB). Every archive passes `gzip -t`; the
11.6 GB wolf `vcf.tar.gz` is triple-verified (Apple gzip + full zlib decompression).
Dryad now requires an OAuth2 bearer token for downloads — credentials are created at
<https://datadryad.org/account> and passed via `DRYAD_CLIENT_ID`/`DRYAD_CLIENT_SECRET`.

## Storage — internal SSD (USB abandoned, 2026-06-19)

The USB `PS` was reformatted FAT32 → exFAT to lift the 4 GB cap, but the drive
**corrupts large writes**: the 11.6 GB wolf VCF failed integrity on two separate
downloads at *different* random offsets (11.45 GB, 11.17 GB), while a copy to the
internal SSD verified clean. Diagnosis: faulty large-file write path (failing drive,
or exFAT/cable issue); files ≤293 MB wrote fine.

**Resolution: all data lives on the internal SSD** at `~/Desktop/MMP/congen_data/`;
`data/peafowl` + `data/wolf` symlink there. The USB is no longer used for the project.

> Cleanup-able: `~/Desktop/PS-backup-20260618/` and the stale `/Volumes/PS/CG/data`
> copies. Consider testing/replacing the USB before trusting it again.

## Audit (HANDOFF.md) — fixes applied 2026-06-19

A prior audit (`HANDOFF.md`) listed Phase-0 gaps; the agent-actionable ones are done:
- Real callset paths wired into `config.yaml`; `scripts/extract_data.sh` added (reproducible, idempotent extraction + wolf VCF indexing).
- Repro recipe fixed (README + report): **micromamba** (classic conda OOMs on 8 GB), dropped the unwired `--use-conda`, noted R ships with the env.
- currentNe2/GONE2 **pinned to commits** (`4ee170d` / `5896504`) in `build_tools.sh` + `tools/README.md`.
- config: GERP threshold → **4.0** (source value; a sensitivity knob); **NeEstimator removed from the automated cube axis** (Java GUI → manual cross-check).
- git hygiene: `.claude/` gitignored + untracked. *(Stray empty `data dryad api/` folder at repo root — left for the user to delete.)*

## Phase-1 decisions — RESOLVED 2026-06-19 (user)

1. **Angle-G scope → diversity/heterozygosity erosion.** Comparative set is n≈5 museum (`kiz*`) + 6 modern — too few for credible LD-based contemporary N_e (CIs uninformative). Measure Ho/He + allelic richness (rarefied to equal n) museum-vs-modern, with a museum-DNA damage caveat (deamination can inflate apparent diversity). Mirrors the deposit's own modern-vs-historical π. *(Scope reduction from the plan's "temporal N_e erosion" — flagged openly; coverage ≥9× is fine, n is the limiter.)*
2. **Filter-axis headroom → confirmed (the knob bites).** Biallelic-SNP counts on `Modern_all` (1,139,469 total): lenient (mm0.7/dp4/gq15/mac3) **1,044,447** → standard (mm0.8/dp6/gq20) **419,616** → strict (mm0.9/dp8/gq30) **29,851** — a ~35× spread. So Set A is re-derived **per preset** from `Modern_all` (carries `GT:AD:DP:FT:GQ:PL`); the authors' pre-pruned `set_a_neutral` (790,705 SNPs, frozen) is a **validation reference only**, never the cube input. (Verdict-moves-across-500 check completes once currentNe2 runs in Phase 1/2.)
3. **R ownership → conda-owned.** R + packages ship from the `congen` env; `renv::restore()` dropped from the repro recipe (README updated). renv scaffolding left inert.
4. **GERP threshold → exposed as sensitivity knob.** `wolf.load.gerp_sensitivity: [2.0, 3.0, 4.0]`, default 4.0 (source value). The wolf-load tab sweeps it (fits the fragility thesis).
