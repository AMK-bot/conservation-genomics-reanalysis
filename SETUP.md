# Phase 0 — Setup & Verification status

Tracks the plan's §3 Phase 0 (CGplan.md). Updated 2026-06-18.

## Machine (verified 2026-06-18)

| Item | Status |
|---|---|
| Chip | Apple **M1** (arm64), 8 GB RAM |
| Rosetta 2 | ✅ installed |
| Xcode Command Line Tools | ✅ clang 15 (source builds OK for currentNe2/GONE2) |
| conda | Anaconda3 base, **already `osx-64`/x86_64 under Rosetta** — conda **4.12.0** (old classic solver) |
| R | ✅ 4.4.3 (via the `congen` env) |
| Internal disk free | ~206 GB |
| USB `PS` | **exFAT** (reformatted 2026-06-18 from FAT32 to lift the 4 GB cap; GPT, 988 GB); data root `/Volumes/PS/CG/data` |

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
- [x] `data/` → USB symlinks (`data/peafowl`, `data/wolf` → `/Volumes/PS/CG/data/...`; `data/README.md` stays tracked).

> **Solver note:** the build tool is `micromamba` (the OOM with classic conda is the
> documented Apple-Silicon/8 GB risk). The env is still a standard conda env at
> `~/opt/anaconda3/envs/congen` — `conda activate congen` works normally.

## 3.2 Verification gates

- [x] **Peafowl multi-population gate** — PASS (resolved 2026-06-17 in the plan): 3 pops, 22 unrelated.
- [ ] **Wolf gate** — `vep.tar.gz` + `gerp.tar.gz` **confirmed present** in the deposit (file list resolved); still TODO after download: confirm outgroup polarization file, test per-chromosome `bcftools view`, confirm RAM stays bounded.
- [ ] Reproduce both papers' sample tables (data sanity check).
- [ ] Peafowl Phase-1 coverage check (route to ANGSD/GL stack if low-coverage).

## ⏳ Only remaining blocker — data download (gated on you)

Dryad now requires an **OAuth2 bearer token** for file downloads (`401 "must have
current bearer token"`). Create API credentials at <https://datadryad.org/account>
and provide them, then `scripts/fetch_data.sh` pulls all 22 files (12.7 GB) to the USB:

```bash
export DRYAD_CLIENT_ID=...  DRYAD_CLIENT_SECRET=...
scripts/fetch_data.sh
```

## Storage — RESOLVED (2026-06-18)

The USB `PS` was reformatted **FAT32 → exFAT** (GPT) to lift the 4 GB single-file
cap so the 12 GB wolf deposit fits. Pre-erase contents were backed up to
`~/Desktop/PS-backup-20260618/` (verified) and the user's `Polygraph` +
`Sandisk Original` folders were restored afterward. The repo's `data/peafowl` and
`data/wolf` are now symlinks into `/Volumes/PS/CG/data/`. Downloads can proceed.

> The backup at `~/Desktop/PS-backup-20260618/` can be deleted once you're satisfied
> the USB restore is intact.
