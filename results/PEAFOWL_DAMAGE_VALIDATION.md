# Peafowl damage-aware falsification — validation

**Summary: 30 PASS, 0 WARN, 0 FAIL**

| check | status | evidence |
|---|---|---|
| frozen popmap is 5 museum versus 6 modern unique birds | **PASS** | museum=5, modern=6, total=11 |
| damage-aware transition definition is the predeclared four ordered changes | **PASS** | A>G, C>T, G>A, T>C |
| effects table has its complete audit schema | **PASS** | complete |
| permutations table has its complete audit schema | **PASS** | complete |
| influence table has its complete audit schema | **PASS** | complete |
| blocks table has its complete audit schema | **PASS** | complete |
| classification table has its complete audit schema | **PASS** | complete |
| figure values table has its complete audit schema | **PASS** | complete |
| both VCF headers contain the exact 11 frozen samples | **PASS** | raw and normalized headers independently inspected |
| normalized comparative records stay on the frozen autosomes | **PASS** | outside-autosome records=0 |
| transition, transversion, MNV, indel, multiallelic, and other counts independently reconcile | **PASS** | raw_comparative: total=1,076,258, complete SNP=880,100; normalized_comparative: total=1,074,022, complete SNP=260,031 |
| effects preserve exactly the eight variant-set by metric outcomes | **PASS** | rows=8, unique cells=8 |
| effect values, metric bases, directions, sample sizes, and derived bootstrap seeds reconcile | **PASS** | base seed=1303; reps=999; CI=95% |
| 5-Mb block table includes the complete raw and autosomal opportunity grids | **PASS** | all_snp/pi=387; all_snp/Ho=217; all_snp/He=217; all_snp/allelic_richness=217; transversion_only/pi=387; transversion_only/Ho=217; transversion_only/He=217; transversion_only/allelic_richness=217 |
| raw pi and normalized Ho/He/AR use independent complete-call frozen site bases | **PASS** | pi uses raw all-contig bp; Ho/He/AR use normalized autosomal complete SNP sites |
| independent repeated chromosome-stratified block bootstraps reproduce every point and interval | **PASS** | all_snp/He seed=1316; all_snp/Ho seed=1315; all_snp/allelic_richness seed=1317; all_snp/pi seed=1314; transversion_only/He seed=2316; transversion_only/Ho seed=2315; transversion_only/allelic_richness seed=2317; transversion_only/pi seed=2314 |
| all 462 exact 5-versus-6 allocations retain all eight labeled outcomes | **PASS** | allocations=462, outcomes=3696, observed=['P000'] |
| every exact-allocation effect, direction, metric basis, and frozen denominator reconciles | **PASS** | museum minus modern recomputed for 3,696 outcomes |
| independent exact-reference p-values and percentiles reproduce the effects table | **PASS** | all_snp/He p=0.3312; all_snp/Ho p=0.6732; all_snp/allelic_richness p=0.4026; all_snp/pi p=0.8160; transversion_only/He p=0.3701; transversion_only/Ho p=0.6667; transversion_only/allelic_richness p=0.3680; transversion_only/pi p=0.8312 |
| six equal-n omissions and all 11 leave-one cases preserve samples, groups, and rarefaction n | **PASS** | cases=17, outcomes=136; museum-LOO AR rarefies to n=4 |
| all influence effects and direction-stability labels independently reconcile | **PASS** | museum minus modern and baseline direction recomputed for 136 outcomes |
| effect scorecard independently reproduces equal-n, leave-one, and transversion stability | **PASS** | all case counts, extrema, and concordance flags recomputed |
| numeric falsifier is distinct from the unresolved geographic-design veto | **PASS** | directional condition=False; geographic mismatch=True; temporal upgrade=False |
| figure-values table exactly projects all effects, intervals, and influence cases | **PASS** | forest=8, influence=136 |
| compact forest/influence figure is a non-empty PNG | **PASS** | 127,615 bytes |
| provenance freezes configuration and exact sample identities | **PASS** | seed=1303, reps=999, blocks=5,000,000 bp, rarefy n=5 |
| provenance records raw/normalized bases, complete-call relabeling, analytical rarefaction, and reconciled other variants | **PASS** | method boundaries and exclusions are explicit |
| provenance keeps the geographic mismatch prominent under the recorded numerical outcome | **PASS** | geography cannot be isolated from time; the claim-upgrade veto is machine readable |
| provenance input paths and SHA-256 hashes reconcile | **PASS** | inputs=5 |
| provenance output paths and SHA-256 hashes reconcile | **PASS** | outputs=7 |

The exact allocation reference, block intervals, and influence checks quantify fragility; they do not make the museum and modern samples geographically exchangeable.

The temporal-erosion claim remains withheld while geography and time are confounded, even if the predeclared directional condition happens to pass.
