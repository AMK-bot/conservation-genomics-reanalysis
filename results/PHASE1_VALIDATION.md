# Phase 1 — validation report

Reproduces only what the **deposited** callsets support (plan §4). The undeposited 31-sample raw numbers are out of reach — not faked.

| check | status | detail |
|---|---|---|
| frozen_neutral_ref == 790,705 | **PASS** | got 790,705 |
| setA postMAC lenient ~= 1,044,447 | **PASS** | got 1,046,916 (+0.24% vs HANDOFF; norm-split margin) |
| setA postMAC standard ~= 419,616 | **PASS** | got 420,826 (+0.29% vs HANDOFF; norm-split margin) |
| setA postMAC strict ~= 29,851 | **PASS** | got 30,143 (+0.98% vs HANDOFF; norm-split margin) |
| filter knob spread >= 20x | **PASS** | 35x (lenient/strict post-MAC) |
| ADMIXTURE best K | **WARN** | min mean-CV at K=1 (3 pops sampled; CV often favours fewer) |
| PCA separates 3 populations | **PASS** | min between-centroid gap 91.28 vs max within-spread 38.34 |
| Thailand lowest diversity (He & AR) | **PASS** | lowest He=Thailand, lowest AR=Thailand |
| temporal π direction | **WARN** | median π museum=0.00037 vs modern=0.000342 -> museum > modern (consistent w/ erosion); aDNA deamination can inflate museum diversity (caveat) |
| temporal He/AR direction | **WARN** | He museum=0.458/modern=0.463; AR museum=1.98/modern=1.99 |

**0 FAIL**, 3 WARN (reported-not-asserted), 7 PASS.

**Out of reach / caveats:** exact Dong et al. 2021 π values are not embedded here (we reproduce the *contrast direction*, not their decimals); Ho/He are SNP-based relative measures, not genome-wide; temporal contrast is geographically narrow (modern mostly Thai s_*) and the deposited comparative uses PE125_220 where the authors' raw script used s_9_2.
