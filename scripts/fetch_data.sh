#!/usr/bin/env bash
# Fetch raw datasets from Dryad into data/ (symlinked to the internal SSD data root).
#
# Dryad requires an OAuth2 bearer token for file downloads. Create credentials at
# https://datadryad.org/account  (My account), then:
#   export DRYAD_CLIENT_ID=...
#   export DRYAD_CLIENT_SECRET=...
#   scripts/fetch_data.sh                  # -> <repo>/data  (internal-SSD symlinks)
#
# Optional:
#   DRYAD_SKIP_REGEX='vcf\.tar\.gz' scripts/fetch_data.sh
#     defers files whose path matches the regex (e.g. the 11.6 GB wolf VCF).
#     Re-run later with no DRYAD_SKIP_REGEX to grab the deferred file(s).
#
# Idempotent: a file already present at its full Dryad size is skipped; a partial
# file resumes (curl -C -). Credentials are read from env vars, never written to disk.
#
#   Peafowl: 10.5061/dryad.ffbg79ctc  (~0.79 GB, 18 files)
#   Wolf:    10.5061/dryad.7m0cfxpzj  (~11.9 GB; vcf.tar.gz is one 11.6 GB file)
set -euo pipefail

DEST_ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)/data}"
SKIP_REGEX="${DRYAD_SKIP_REGEX:-}"
PEAFOWL_DOI="10.5061/dryad.ffbg79ctc"
WOLF_DOI="10.5061/dryad.7m0cfxpzj"
: "${DRYAD_CLIENT_ID:?set DRYAD_CLIENT_ID — create at https://datadryad.org/account}"
: "${DRYAD_CLIENT_SECRET:?set DRYAD_CLIENT_SECRET}"

echo "[$(date +%H:%M:%S)] requesting Dryad access token ..."
TOKEN=$(curl -sS --fail -X POST "https://datadryad.org/oauth/token" \
  -d grant_type=client_credentials \
  -d "client_id=${DRYAD_CLIENT_ID}" \
  -d "client_secret=${DRYAD_CLIENT_SECRET}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
[ -n "${TOKEN:-}" ] || { echo "ERROR: could not obtain access token"; exit 1; }
echo "[$(date +%H:%M:%S)] token acquired."

resolve() {  # doi -> "path<TAB>size_bytes<TAB>download_url" lines
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
        print(f"{f['path']}\t{f.get('size',0)}\thttps://datadryad.org{f['_links']['stash:download']['href']}")
    if "next" not in fl.get("_links", {}): break
    page += 1
PY
}

fetch() {  # subdir doi
  local sub="$1" doi="$2" dir="$DEST_ROOT/$1/raw"
  mkdir -p "$dir"
  echo "[$(date +%H:%M:%S)] resolving $sub ($doi) ..."
  resolve "$doi" | while IFS=$'\t' read -r path size url; do
    local dest="$dir/$path"
    if [ -n "$SKIP_REGEX" ] && printf '%s' "$path" | grep -qE "$SKIP_REGEX"; then
      echo "[$(date +%H:%M:%S)] deferred: $sub/$path"; continue
    fi
    if [ -f "$dest" ] && [ "$(stat -f%z "$dest" 2>/dev/null || echo 0)" = "$size" ]; then
      echo "[$(date +%H:%M:%S)] have:     $sub/$path"; continue
    fi
    echo "[$(date +%H:%M:%S)] -> $sub/$path ($((size/1000000)) MB)"
    curl -L -C - --retry 5 --retry-delay 5 --fail -sS \
      -H "Authorization: Bearer $TOKEN" -o "$dest" "$url"
  done
}

fetch peafowl "$PEAFOWL_DOI"
fetch wolf "$WOLF_DOI"

echo "[$(date +%H:%M:%S)] verifying gzip integrity ..."
# -L follows the data/ -> internal-SSD symlinks (without it, find skips the real files).
find -L "$DEST_ROOT" -name '*.gz' -print0 | while IFS= read -r -d '' f; do
  if gzip -t "$f" 2>/dev/null; then echo "ok:      $f"; else echo "CORRUPT: $f"; fi
done
echo "[$(date +%H:%M:%S)] done."
