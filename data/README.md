# data/

Raw VCFs + extracted callsets + intermediates. **Not committed** (large) — only this
README is tracked.

`data/peafowl` and `data/wolf` are **symlinks to the internal SSD**
(`~/Desktop/MMP/congen_data/`). The USB was abandoned after it was found to corrupt
large writes (see `SETUP.md`).

```
data/
├── README.md       # tracked
├── peafowl  ->  ~/Desktop/MMP/congen_data/peafowl
│   ├── raw/                                       # Dryad 10.5061/dryad.ffbg79ctc (18 files)
│   ├── Modern_genomic_dataset_unlinked_neutral/   # Set A neutral/LD-pruned — 22 samples, 790,705 SNPs
│   ├── Modern_genomic_dataset_all/                # Set B all — 22 samples, 1,139,469 SNPs
│   ├── pseudochromosomes.no_blank_shortIDname.fasta   # reference
│   └── green_peafowl_genome.all.gff
└── wolf     ->  ~/Desktop/MMP/congen_data/wolf
    ├── raw/                    # Dryad 10.5061/dryad.7m0cfxpzj (4 files)
    ├── vcf/Pol.2out.mac2/      # polarized (INFO/AA), 211 samples: allSNPs (genome-wide), vepfinal (coding), chrX
    ├── vep/                    # VEP + SIFT annotation
    └── gerp/                   # GERP conservation scores + per-individual load
```

> Re-download from Dryad with `scripts/fetch_data.sh` (needs `DRYAD_CLIENT_ID` /
> `DRYAD_CLIENT_SECRET`). All archives verified via `gzip -t`; the 11.6 GB wolf VCF
> additionally via full zlib decompression.
