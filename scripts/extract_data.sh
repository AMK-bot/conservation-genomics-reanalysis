#!/usr/bin/env bash
# Extract the downloaded Dryad tarballs into the analysis layout, then index the
# genome-wide wolf VCF for per-chromosome streaming. Idempotent: skips archives whose
# top-level entry already exists. Run after scripts/fetch_data.sh.
#   scripts/extract_data.sh            # operates on <repo>/data (symlinks to internal SSD)
set -euo pipefail
D="${1:-$(cd "$(dirname "$0")/.." && pwd)/data}"

extract_dir() {                          # $1 = dataset dir (e.g. data/peafowl)
  local dir="$1" t first
  shopt -s nullglob
  for t in "$dir"/raw/*.tar.gz; do
    first=$(tar tzf "$t" 2>/dev/null | head -1)
    if [ -n "$first" ] && [ -e "$dir/$first" ]; then
      echo "  skip (present): $(basename "$t")"
    else
      tar xzf "$t" -C "$dir/" && echo "  extracted: $(basename "$t")"
    fi
  done
}

echo "== peafowl =="; extract_dir "$D/peafowl"
echo "== wolf ==";    extract_dir "$D/wolf"

# Index the 11.6 GB genome-wide wolf VCF (csi handles large contigs) for region queries.
BIG="$D/wolf/vcf/Pol.2out.mac2/100S95F14R.chr1-38.allSNPs.wfm.vcf.gz"
if [ -f "$BIG" ] && [ ! -f "$BIG.csi" ] && command -v bcftools >/dev/null 2>&1; then
  bcftools index -c "$BIG" && echo "  indexed: allSNPs (.csi)"
fi
echo "done."
