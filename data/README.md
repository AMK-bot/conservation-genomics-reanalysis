# data/

Raw VCFs + per-chromosome splits + intermediates. **Not committed** (large) — only
this README is tracked.

`data/peafowl` and `data/wolf` are **symlinks to the USB** (`/Volumes/PS/CG/data/`)
so the 12 GB wolf deposit and peafowl VCFs live off the internal disk and off git.
Only this `README.md` is tracked.

```
data/
├── README.md       # tracked
├── peafowl  ->  /Volumes/PS/CG/data/peafowl
│   └── raw/        # Dryad 10.5061/dryad.ffbg79ctc
└── wolf     ->  /Volumes/PS/CG/data/wolf
    └── raw/        # Dryad 10.5061/dryad.7m0cfxpzj  (12 GB; VEP + GERP + outgroup)
```

> **Storage (2026-06-18):** USB `PS` was reformatted FAT32 → **exFAT** to lift the
> 4 GB single-file cap (the wolf deposit is 12 GB). If the symlinks dangle, the USB
> isn't mounted — replug `PS`. See `SETUP.md`.
