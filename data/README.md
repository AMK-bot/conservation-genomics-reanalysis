# data/

Raw VCFs + per-chromosome splits + intermediates. **Not committed** (large) — only
this README is tracked.

In the reproducible setup, `data/` is a **symlink to external storage** so the
12 GB wolf deposit and peafowl VCFs live off the 460 GB internal disk and off git.

```
data/
├── peafowl/
│   └── raw/        # Dryad 10.5061/dryad.ffbg79ctc
└── wolf/
    └── raw/        # Dryad 10.5061/dryad.7m0cfxpzj  (12 GB; VEP + GERP + outgroup)
```

> ⚠️ **Storage note (2026-06-18):** the inserted USB `PS` is **FAT32**, which caps
> single files at **4 GB** — it cannot hold the 12 GB wolf archive as one file.
> Final storage location is pending a decision (reformat USB to exFAT vs. use internal
> disk). See `SETUP.md`.
