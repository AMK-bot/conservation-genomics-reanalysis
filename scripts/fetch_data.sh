#!/usr/bin/env bash
# Fetch raw datasets from Dryad into data/ (symlinked to USB).
# Reproducible: resolves the CURRENT file list + download URLs from the Dryad API
# by DOI, so it keeps working if Dryad re-issues file IDs.
#
#   Peafowl: 10.5061/dryad.ffbg79ctc  (~0.79 GB)
#   Wolf:    10.5061/dryad.7m0cfxpzj  (~11.9 GB; vcf.tar.gz is one 11.6 GB file)
#
# Usage: scripts/fetch_data.sh [DEST_ROOT]   (default: <repo>/data)
set -euo pipefail

DEST_ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)/data}"
PEAFOWL_DOI="10.5061/dryad.ffbg79ctc"
WOLF_DOI="10.5061/dryad.7m0cfxpzj"

resolve() {  # doi -> "path<TAB>url" lines, via the Dryad REST API
  python3 - "$1" <<'PY'
import json, sys, urllib.request, urllib.parse
BASE = "https://datadryad.org/api/v2"
def get(u):
    req = urllib.request.Request(u, headers={"Accept": "application/json", "User-Agent": "congen"})
    with urllib.request.urlopen(req, timeout=60) as x:
        return json.load(x)
doi = sys.argv[1]; enc = urllib.parse.quote(f"doi:{doi}", safe="")
ds = get(f"{BASE}/datasets/{enc}")
ver = get("https://datadryad.org" + ds["_links"]["stash:version"]["href"])
fh = ver["_links"]["stash:files"]["href"]; page = 1
while True:
    fl = get(f"https://datadryad.org{fh}?per_page=100&page={page}")
    emb = fl.get("_embedded", {}).get("stash:files", [])
    if not emb: break
    for f in emb:
        print(f["path"] + "\t" + "https://datadryad.org" + f["_links"]["stash:download"]["href"])
    if "next" not in fl.get("_links", {}): break
    page += 1
PY
}

fetch() {  # subdir doi
  local sub="$1" doi="$2" dir="$DEST_ROOT/$1/raw"
  mkdir -p "$dir"
  echo "[$(date +%H:%M:%S)] resolving $sub ($doi) ..."
  resolve "$doi" | while IFS=$'\t' read -r path url; do
    echo "[$(date +%H:%M:%S)] -> $sub/$path"
    curl -L -C - --retry 5 --retry-delay 5 --fail -sS -o "$dir/$path" "$url"
  done
}

fetch peafowl "$PEAFOWL_DOI"
fetch wolf "$WOLF_DOI"

echo "[$(date +%H:%M:%S)] verifying gzip integrity ..."
find "$DEST_ROOT" -name '*.gz' -print0 | while IFS= read -r -d '' f; do
  if gzip -t "$f" 2>/dev/null; then echo "ok:      $f"; else echo "CORRUPT: $f"; fi
done
echo "[$(date +%H:%M:%S)] done."
