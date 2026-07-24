# Phase 5B core communication integration validation

This gate freezes Section 13.6 after the three core analyses and before optional-study decisions.

**Summary: 14 PASS, 0 FAIL**

| check | status | evidence |
|---|---|---|
| all core integration artifacts and sources exist | **PASS** | complete |
| contract has three ordered core claims and complete trace schema | **PASS** | rows=3, sections=['13.1', '13.3', '13.2'] |
| wolf result and numeric gate independently reconcile | **PASS** | observed=15/15; threshold=12 |
| damage-aware result and numeric falsifier independently reconcile | **PASS** | observed=1/4; threshold=4; geography retained |
| Ne=500 is a boundary partition and is never scored correct/incorrect | **PASS** | boundary rows=15/15; schema_ok=True |
| Ne design result and uncertainty-bounded resolution rule reconcile | **PASS** | resolving=0/15; bounds=0.7/0.25; consequence is conditional and scenario-qualified |
| each claim separates result, correction, falsifier, and consequence | **PASS** | all three contracts retain the seven-step reasoning path |
| technical report has all three core result anchors and scientific boundaries | **PASS** | anchors, finalized Ne model, empirical uncertainty, and causal boundaries present |
| Streamlit explorer reads all three core machine tables without recomputation | **PASS** | three read-only panels, boundary-specific outcomes, and boundaries present |
| static portal presents the exact seven-step scientific path in order | **PASS** | Question -> Prediction -> Stress test -> Result -> Correction -> Falsifier -> Conservation consequence |
| static portal has native core controls, causal boundary, and numeric mind-change cards | **PASS** | native selects, absent-fitness stop, trace, boundary labels, and numeric cards present |
| offline JavaScript uses generated local data and handles missing assets | **PASS** | local global payload; boundary labels switch at true Ne=500; no fetch; fallbacks present |
| responsive and reduced-motion behavior covers the decision layer | **PASS** | responsive lab/card grids and reduced-motion override present |
| core integration provenance hashes every analysis and validator input | **PASS** | inputs=12; ordered hand-off recorded |
