# Phase 0 — Setup & Verification status

Tracks the plan's §3 Phase 0 (CGplan.md). Updated 2026-06-18.

## Machine (verified 2026-06-18)

| Item | Status |
|---|---|
| Chip | Apple **M1** (arm64), 8 GB RAM |
| Rosetta 2 | ✅ installed |
| Xcode Command Line Tools | ✅ clang 15 (source builds OK for currentNe2/GONE2) |
| conda | Anaconda3 base, **already `osx-64`/x86_64 under Rosetta** — conda **4.12.0** (old classic solver) |
| R | ❌ not installed → arrives via the `congen` env (`r-base`) |
| Internal disk free | ~206 GB |
| USB `PS` | **exFAT** (reformatted 2026-06-18 from FAT32 to lift the 4 GB cap; GPT, 988 GB); data root `/Volumes/PS/CG/data` |

## 3.1 Environment

- [x] Rosetta present (no install needed).
- [x] `environment.yml` authored (osx-64; conda-forge + bioconda + defaults).
- [ ] `congen` env built (`conda env create -f environment.yml`) — **running**, log at `/tmp/congen_env_build.log`.
- [ ] `conda config --env --set subdir osx-64` (pin after create).
- [ ] Re-export pinned `environment.lock.yml` after first solve.
- [ ] currentNe2 + GONE2 built from source into `tools/` (NeEstimator v2 = manual cross-check).
- [x] Repo skeleton created (config / workflow / scripts / results / app / report / data / tools).
- [x] `git init` + initial commit.
- [ ] `renv::init()` (needs R from the env first).
- [x] `data/` → USB symlinks (`data/peafowl`, `data/wolf` → `/Volumes/PS/CG/data/...`; `data/README.md` stays tracked).

## 3.2 Verification gates

- [x] **Peafowl multi-population gate** — PASS (resolved 2026-06-17 in the plan): 3 pops, 22 unrelated.
- [ ] **Wolf gate** — download 12 GB deposit; confirm `vep.tar.gz` + `gerp.tar.gz` + outgroup polarization file; test per-chromosome `bcftools view`; confirm RAM stays bounded.
- [ ] Reproduce both papers' sample tables (data sanity check).
- [ ] Peafowl Phase-1 coverage check (route to ANGSD/GL stack if low-coverage).

## Storage — RESOLVED (2026-06-18)

The USB `PS` was reformatted **FAT32 → exFAT** (GPT) to lift the 4 GB single-file
cap so the 12 GB wolf deposit fits. Pre-erase contents were backed up to
`~/Desktop/PS-backup-20260618/` (verified) and the user's `Polygraph` +
`Sandisk Original` folders were restored afterward. The repo's `data/peafowl` and
`data/wolf` are now symlinks into `/Volumes/PS/CG/data/`. Downloads can proceed.

> The backup at `~/Desktop/PS-backup-20260618/` can be deleted once you're satisfied
> the USB restore is intact.
