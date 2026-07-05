# Phase 4 — validation report

The load-bearing check **reconciles our GERP>4 load against the deposit's precomputed anchor** (`LoadPerInd.thres4`) — a faithful re-implementation must reproduce it. The rest asserts the GERP-sweep + ROH tables are well-formed and **reports** the scientific direction (realized-vs-masked across periods, GERP + ROH sensitivity) without over-asserting.

| check | status | detail |
|---|---|---|
| load has all GERP thresholds | **PASS** | got [np.int64(2), np.int64(3), np.int64(4)], expected [2.0, 3.0, 4.0] |
| load covers the anchor's individuals | **PASS** | 211 individuals vs anchor 211 |
| GERP>4 reconciles with the deposit anchor | **PASS** | 95th-pct relerr realized/masked = 1.29e-14 over 211 inds; count deltas (calls/del/homdel) max = 0/0/0 (exact) |
| raw deleterious counts match the anchor exactly | **PASS** | TOT_CALLS/TOT_DEL/HOM_DEL identical |
| deleterious-site count non-increasing in GERP threshold | **PASS** | n_del(2) >= n_del(3) >= n_del(4) per individual |
| F_ROH in [0,1] | **PASS** | range [0.022, 0.590] |
| F_ROH non-increasing as ROH-length cutoff rises | **PASS** | more restrictive cutoff keeps less ROH |
| realized vs masked load by period (GERP>4) | **WARN** | 1983-1990: real=0.096/mask=0.063; 1991-1998: real=0.093/mask=0.066; 1999-2006: real=0.105/mask=0.052; 2007-2014I: real=0.091/mask=0.079; 2007-2014S: real=0.103/mask=0.059; Finland: real=0.089/mask=0.101; Immigrants: real=0.085/mask=0.101; Russia: real=0.087/mask=0.100 |
| GERP-threshold sensitivity of realized load | **WARN** | GERP>2: mean realized=0.172; GERP>3: mean realized=0.136; GERP>4: mean realized=0.093 |
| ROH-length sensitivity of mean F_ROH | **WARN** | >=0.1Mb: 0.226; >=0.5Mb: 0.195; >=1.0Mb: 0.182; >=1.5Mb: 0.173; >=2.0Mb: 0.167 |

**0 FAIL**, 3 WARN (reported-not-asserted), 7 PASS.
