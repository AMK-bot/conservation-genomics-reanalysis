# Populations Maintained — GBF complementary indicator (plan §6)

**Why:** the N_e>500 indicator asks whether a contemporary genetic-drift risk proxy confidently
clears its threshold for the sampled populations;
"Populations Maintained" (PM) measures *how many coarse historical range-country units remain
extant*. They are the
two GBF Goal-A genetic indicators and are meant to be reported together. PM is **not**
genomic — it comes from range/occurrence records, not the cube — so it is hand-curated here
from the literature (the approach signed off in Phase-3 planning).

**Unit = range country.** The coarsest unit for which IUCN/BirdLife give explicit per-unit
presence flags, so the most defensible level for a small project. The cost of this choice is
real and stated below: a country counted "extant" can still have lost most of its range.

## Tally

Historically present range countries: **10**. Still extant: **7**. PM = 7/10 = **0.70**.
The live BirdLife DataZone country table was checked on **2026-07-18** and resolves the former
country-level swing cases: India is listed **Extinct**, while Laos is listed **Extant**. The
current country-unit sensitivity band is therefore **0.70–0.70**.

| range country | subspecies | historically present | current status | note | key source |
|---|---|---|---|---|---|
| Myanmar | spicifer/imperator | yes | **extant** | largest modelled habitat (~88,000 km², ~19% of historical range) | Oryx 2018; IUCN/BirdLife 2018 |
| China (Yunnan) | imperator | yes | **extant** | endemic to Yunnan now; 54→22 counties, ~485–600 birds | Kong et al. 2018; MDPI Sustainability 2021 |
| Thailand | imperator/muticus | yes | **extant** | two isolated regions (N + W); peninsula lost | BCI; Oryx 2018; IUCN/BirdLife 2018 |
| Cambodia | imperator | yes | **extant** | global stronghold; Keo Seima ~745 (2020) | Nuttall et al. 2017 (BCI) |
| Vietnam | imperator | yes | **extant** | south/SE only; north extirpated | Oryx 2018; IUCN/BirdLife 2018 |
| Indonesia (Java) | muticus | yes | **extant** | nominate ssp., Java only; W + E Java relicts | van Balen et al. 1995; IUCN/BirdLife 2018 |
| Bangladesh | spicifer | yes | extirpated | Regionally Extinct (national Red List) | IUCN Bangladesh 2015; IUCN/BirdLife 2018 |
| Malaysia (Peninsular) | muticus | yes | extirpated | "now considered extinct in Malaysia" | genomics review PMC10671381 (2023); IUCN 2018 |
| India (NE) | spicifer | yes | **extinct** | BirdLife lists India Extinct; its research table still requests status clarification | BirdLife DataZone, accessed 2026-07-18 |
| Laos | imperator | yes | **extant** | BirdLife lists Laos Extant; persistence is still sparse and country-level | BirdLife DataZone, accessed 2026-07-18 |

**Verification boundary.** These flags reproduce BirdLife's current country-level distribution
table. They do not establish abundance, within-country range retention, or genetic viability.

## Reading it against the genomic indicator

The three sampled populations (Yunnan, Vietnam, Thailand) are **all** in the maintained set —
yet none confidently passes N_e>500 (0/3, mostly indeterminate). **Still present ≠ confidence that
the genomic proxy clears its threshold.** PM=0.70 and the three-state N_e result describe different
dimensions; neither establishes genetic viability or genetic erosion. That distinction is the
conservation message.

## Caveats

1. **Country masks within-country collapse.** China holds ~485–600 birds after losing ~60% of
   its counties and all of Tibet; Vietnam lost its entire north; Thailand survives as two
   fragments. PM=0.70 therefore *overstates* persistence. A sub-country unit (subspecies n=3, or
   biogeographic subpopulation) would be a more sensitive complementary metric.
2. **Country flags verified; biological resolution remains coarse.** The live BirdLife DataZone
   distribution table was read field-by-field on 2026-07-18. It lists India Extinct and Laos and
   Vietnam Extant. A country-level Extant flag does not resolve northern-Vietnam loss or the size
   and isolation of surviving populations.
3. GBIF/eBird counts reflect observer effort and include captive/feral records (US n=74, a
   non-range country, excluded) — they corroborate presence/absence only, not population size.
4. Reintroduced/feral populations (Peninsular Malaysia ~2005; Myanmar Hlawga) are not counted as
   wild persistence.

<!-- Machine-readable source of this per-country tally = config/populations_maintained.tsv. The
     Phase-3 rule `gbf_indicators` reads it, derives PM (0.70, band 0.70-0.70) into
     results/tables/gbf_*.tsv, and the Streamlit GBF tab reads those tables. Keep this narrative
     and that TSV in sync (this markdown is the human-readable mirror, the TSV is authoritative). -->
