# Project website validation

The root project portal is checked as a dependency-free, offline-readable static website.

**Summary: 30 PASS, 0 FAIL**

| check | status | evidence |
|---|---|---|
| complete HTML document | **PASS** | 79,620 bytes |
| semantic and accessible page structure | **PASS** | title, description, skip link, one H1, and all landmarks present |
| narrow allowlisted website-text contract | **PASS** | exactly 37 unique allowlisted text-only narrative leaves; scientific/status contexts remain locked |
| versioned editor state and text-only application | **PASS** | all 9 editor artifacts present; revision and generated JavaScript agree for 0 saved overrides |
| private localhost editor controls and write boundary | **PASS** | complete editor controls; loopback-only token API, optimistic revision conflicts, atomic writes, and offline assets |
| Phase-5B scientific path uses the locked order | **PASS** | question → prediction → stress test → result → correction → falsifier → conservation consequence |
| hero leads with science rather than a validation counter | **PASS** | causal/scientific content occupies the hero aside |
| causal boundary stops before absent fitness outcomes | **PASS** | demographic history → choices → proxies → decisions; survival, fertility, reproduction, and fitness absent |
| all local links and media targets exist | **PASS** | 143 unique local targets |
| all in-page navigation targets exist | **PASS** | 16 page IDs indexed |
| no external runtime dependency | **PASS** | CSS, JavaScript, fonts, and images are repository-local |
| every image has alternative text | **PASS** | 11 images checked |
| essential explained deliverable coverage | **PASS** | 26 explained cards; all 29 essential artifacts linked |
| no-script deliverable count matches the library | **PASS** | placeholder and parsed library both report 26 deliverables |
| native labelled wolf, damage, N_e, and localization controls | **PASS** | 11 labelled native selects expose the exact predeclared grids |
| numeric what-would-change-my-mind cards | **PASS** | 5/5 cards contain a numeric decision condition |
| research-correction cards retain thought, check, correction, and consequence | **PASS** | 4 cards cover pruning, GONE2, temporal contrast, and homozygosity control |
| claim trace has a live region and no-script local fallback | **PASS** | dynamic trace is announced; the machine-readable TSV remains reachable without JavaScript |
| responsive, reduced-motion, focus, and print styles | **PASS** | 49,934 bytes of local CSS |
| keyboard focus remains visible and mobile menu focus is contained | **PASS** | search has an explicit focus ring; closed mobile links are hidden; Escape restores toggle focus |
| Phase-5B path, cards, trace, and controls reflow responsively | **PASS** | tablet and compact layouts collapse Phase-5B components; lab and reproduction grid tracks are min-width contained |
| reduced-motion mode exposes all scientific content | **PASS** | smooth scroll and reveal motion are removed without hiding content |
| local progressive-enhancement script | **PASS** | filter, search, copy, navigation, reveal, and lightbox behavior; no fetch/import |
| true-Ne=500 control switches to boundary outcomes | **PASS** | boundary pass/fail rates and labels replace correct/incorrect at true Ne=500 |
| Phase-5B data and image failures degrade to local readable fallbacks | **PASS** | missing data disables controls with an explanation; failed images retain alt-derived text |
| keyboard and native interaction semantics | **PASS** | 14 typed buttons, labelled selects, Escape handling, change events, and live status |
| claim trace exposes table, provenance, validation, report, and workflow links | **PASS** | six local evidence-link classes are constructed from each generated claim |
| complete local Phase-5B browser data | **PASS** | local generated JSON covers 60 wolf associations, 120 localization, 8 damage, and 60 scenario-design cells and loads before site.js |
| generated claims have numeric gates and resolvable local trace targets | **PASS** | all generated claims include uncertainty, numeric change conditions, and six verified local traces |
| offline/static-hosting support files | **PASS** | .nojekyll, preview instructions, and local favicon present |

## Scope

This gate validates structure, accessibility affordances, local targets, core deliverable coverage,
dependency-free behavior, and the Phase-5B scientific path, causal boundary, exact precomputed grids,
numeric falsifiers, correction cards, trace links, and failure fallbacks. It also validates the closed
narrative-edit allowlist, versioned override state, text-only application, and loopback editor boundary.
Browser-based visual and interaction checks complement this file-level gate.
