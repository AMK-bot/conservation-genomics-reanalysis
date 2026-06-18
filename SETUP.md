# Phase 0 — Setup & Verification status

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
- [x] Pinned `environment.lock.yml` exported (702 packages).
- [x] currentNe2 + GONE2 built from source (`scripts/build_tools.sh`; x86_64 + env libomp). currentNe2 needed a 1-line VLA-init patch for Apple clang. NeEstimator v2 = manual cross-check (not built).
- [x] Repo skeleton created (config / workflow / scripts / results / app / report / data / tools).
- [x] `git init` + commits.
- [x] `renv::init(bare=TRUE)` — scaffolding created (`.Rprofile`, `renv/`). `renv.lock` populated via `renv::snapshot()` in Phase 1 (R pkgs currently sourced from conda).
- [x] `data/` → **internal-SSD** symlinks (`data/peafowl`, `data/wolf` → `~/Desktop/MMP/congen_data/...`). Was USB, but the USB corrupts large writes → moved to internal (see Storage).

> **Solver note:** the build tool is `micromamba` (the OOM with classic conda is the
> documented Apple-Silicon/8 GB risk). The env is still a standard conda env at
> `~/opt/anaconda3/envs/congen` — `conda activate congen` works normally.

## 3.2 Verification gates

- [x] **Peafowl multi-population gate** — PASS (resolved 2026-06-17 in the plan): 3 pops, 22 unrelated.
- [~] **Wolf gate** — data downloaded + integrity-verified; `vep`/`gerp` present; tarballs extracted. TODO: confirm outgroup polarization file, per-chromosome `bcftools view` test, bounded RAM.
- [ ] Reproduce both papers' sample tables (data sanity check).
- [ ] Peafowl Phase-1 coverage check (route to ANGSD/GL stack if low-coverage).

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
