# Project status — 2026-07-18

**Current position:** Phases 0–5A are complete under the project's local, admissions-ready
acceptance gates. The strict Phase-5A gate reports **24 PASS, 0 FAIL**, and the project website's
separate gate reports **10 PASS, 0 FAIL**. Its sendable ZIP passes a further **10 PASS, 0 FAIL**, so
**Phase 6 is ready to begin** but remains an optional preprint stretch.

Percentages below measure completion of the named local outputs and acceptance checks, not elapsed
time. Optional external publication, public hosting, and personal rehearsal are shown separately and
do not reduce the local technical percentage.

## Phase completion

| phase | completion | completion evidence | missing / needs work |
|---|---:|---|---|
| 0 — Setup and verification | **100%** | environment, public deposits, sample gates, source-built tools, and laptop-safe paths verified | None; fallback dataset ladder was not triggered |
| 1 — Peafowl QC, structure, diversity | **100%** | 7 PASS, 3 reported-not-asserted WARN, 0 FAIL | None |
| 2 — Contemporary $N_e$ and results cube | **100%** | 9 PASS, 3 WARN, 0 FAIL; 12-row currentNe2 cube, GONE2 context, and metapopulation cross-check reproduce | Nothing required; NeEstimator GUI table remains optional |
| 3 — GBF indicators and explorer MVP | **100% locally** | 9 PASS, 3 WARN, 0 FAIL; four-tab explorer and all knob states pass locally | Public URL is optional and requires the student's hosting/account authorization |
| 4 — Wolf load and ROH | **100%** | 7 PASS, 3 WARN, 0 FAIL; GERP>4 anchor reconciliation with exact raw counts and floating-precision load agreement | None |
| 5 — Polish and paper-grade report | **100% locally** | explorer polish, limitations, self-contained report, project website (10 PASS, 0 FAIL), sendable bundle (10 PASS, 0 FAIL), portable lock, clean-clone proof, and deterministic rendering complete | Nothing required for Phase 6 readiness |
| 5A — Admissions-facing completion | **100% locally** | strict gate: 24 PASS, 0 FAIL | No missing technical subphase; personal review/rehearsal remains a student action |
| 6 — Preprint stretch | **0% formally** | paper-grade report provides a strong starting manuscript | Formatting, upload, and DOI only if the student chooses the optional publication route |

The 12 scientific WARN rows across Phases 1–4 are explicitly reported biological findings or
caveats, not failed checks. See `results/PHASE5A_VALIDATION.md` and
`results/PHASE5A_REPRODUCIBILITY.md` for the exact evidence.

## Phase 5A subphases

| subphase | completion | evidence | remaining student action |
|---|---:|---|---|
| 5A.1 Fragility scorecard | **100%** | machine-readable table, figure, explorer panel; 10 PASS, 0 FAIL | None |
| 5A.2 Evidence-change map | **100%** | all six evidence concepts present in both explorer and report | None |
| 5A.3 Research journey and ownership | **100% artifact** | `RESEARCH_JOURNEY.md` records decisions, errors, corrections, limits, and assistance | Personally verify that every first-person sentence matches the student's experience |
| 5A.4 Offline admissions package | **100%** | project website, validated sendable ZIP, graphical abstract, illustrated brief, four screenshots, 60-second README, demo plan, HTML report | None |
| 5A.5 Local reproducibility proof | **100%** | 162/162 clean-clone jobs; deterministic GONE2/report hashes; final gate 0 FAIL | None |
| 5A.6 Interview preparation | **100% materials** | interview notes, figure exercise, and 60–90 second summary exist | Rehearse aloud until the answers no longer require reading |

## Current scenario versus final presentation goal

| state | what is true | next action |
|---|---|---|
| Current local project | Complete through Phase 5A; Phase 6-ready; reviewer can understand the project offline in about five minutes | Open `index.html` locally or send `dist/conservation-genomics-portfolio.zip`; preserve the validated brief/report as canonical scientific artifacts |
| Admissions presentation | All materials exist, but authentic delivery cannot be automated | Student reviews ownership wording, rehearses the short explanation, and confirms the preferred author name |
| Optional public version | App works locally; no live URL is required by the completion gate | Student authorizes a repository/hosting account, then deploys if a link is desirable |
| Optional Phase 6 | Not started formally; manuscript-grade report already exists | Reformat/upload only if a preprint is genuinely wanted; do not let publication delay the application artifact |

No remaining required work calls for extra hardware, an external researcher, fieldwork, an ML model,
or a long publication process.
