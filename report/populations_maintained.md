# Populations Maintained — GBF complementary indicator (plan §6)

**Why:** the N_e>500 indicator measures *genetic viability of the populations we have*;
"Populations Maintained" (PM) measures *how many populations are left at all*. They are the
two GBF Goal-A genetic indicators and are meant to be reported together. PM is **not**
genomic — it comes from range/occurrence records, not the cube — so it is hand-curated here
from the literature (the approach signed off in Phase-3 planning).

**Unit = range country.** The coarsest unit for which IUCN/BirdLife give explicit per-unit
presence flags, so the most defensible level for a small project. The cost of this choice is
real and stated below: a country counted "extant" can still have lost most of its range.

## Tally

Historically present range countries: **10**. Still extant: **6**. PM = 6/10 = **0.60**
(conservative). Sensitivity band **0.60–0.80**, driven entirely by the two uncertain swing
cases (India, Laos).

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
| India (NE) | spicifer | yes | uncertain* | records questioned as feral/escaped; Oryx-excluded; GBIF n=34 | Oryx 2018; BirdLife/IUCN 2018 |
| Laos | imperator | yes | uncertain* | ~1 confirmed record (2002) despite ~30,000 km² habitat | McGowan et al. 1998/99; Oryx 2018 |

\* **Swing cases.** Both conservatively counted as *not* maintained → PM = 0.60. Counting Laos
extant gives 0.70; counting both extant gives 0.80. A single reclassification moves the
headline by 0.10.

## Reading it against the genomic indicator

The three sampled populations (Yunnan, Vietnam, Thailand) are **all** in the "maintained" six —
yet none confidently passes N_e>500 (0/3, mostly indeterminate). **Still present ≠ genetically
viable.** PM=0.60 looks moderate; the N_e indicator says the populations that remain are already
genetically eroded. That gap is the conservation message.

## Caveats

1. **Country masks within-country collapse.** China holds ~485–600 birds after losing ~60% of
   its counties and all of Tibet; Vietnam lost its entire north; Thailand survives as two
   fragments. PM=0.60 therefore *overstates* persistence. A sub-country unit (subspecies n=3, or
   biogeographic subpopulation) would be a more sensitive complementary metric.
2. **Sourcing not field-verified.** The live IUCN species page (taxon 22679440) returned HTTP 403
   and the BirdLife distribution table renders dynamically, so per-country presence flags were
   reconstructed from IUCN/BirdLife narrative + peer-reviewed literature + GBIF facets, **not**
   read field-by-field. Verify against the live IUCN/BirdLife table before publication —
   especially India, Laos, and northern Vietnam.
3. GBIF/eBird counts reflect observer effort and include captive/feral records (US n=74, a
   non-range country, excluded) — they corroborate presence/absence only, not population size.
4. Reintroduced/feral populations (Peninsular Malaysia ~2005; Myanmar Hlawga) are not counted as
   wild persistence.

<!-- Machine-readable source of this per-country tally = config/populations_maintained.tsv. The
     Phase-3 rule `gbf_indicators` reads it, derives PM (0.60, band 0.60-0.80) into
     results/tables/gbf_*.tsv, and the Streamlit GBF tab reads those tables. Keep this narrative
     and that TSV in sync (this markdown is the human-readable mirror, the TSV is authoritative). -->
