#!/usr/bin/env bash
# Fetch raw datasets from Dryad into data/ (symlinked to USB).
#
# Dryad requires an OAuth2 bearer token for file downloads. Create credentials at
# https://datadryad.org/account  (My account -> API / Applications), then:
#
#   export DRYAD_CLIENT_ID=...
#   export DRYAD_CLIENT_SECRET=...
#   scripts/fetch_data.sh                 # -> <repo>/data  (symlinks to USB)
#
# Credentials are read from the environment and never written to disk or git.
# Tokens last ~10 h — ample for the 12.7 GB total.
#
#   Peafowl: 10.5061/dryad.ffbg79ctc  (~0.79 GB, 18 files)
#   Wolf:    10.5061/dryad.7m0cfxpzj  (~11.9 GB; vcf.tar.gz is one 11.6 GB file)
set -euo pipefail

DEST_ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)/data}"
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

resolve() {  # doi -> "path<TAB>download_url" lines, via the Dryad REST API
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
    curl -L -C - --retry 5 --retry-delay 5 --fail -sS \
      -H "Authorization: Bearer $TOKEN" -o "$dir/$path" "$url"
  done
}

fetch peafowl "$PEAFOWL_DOI"
fetch wolf "$WOLF_DOI"

echo "[$(date +%H:%M:%S)] verifying gzip integrity ..."
find "$DEST_ROOT" -name '*.gz' -print0 | while IFS= read -r -d '' f; do
  if gzip -t "$f" 2>/dev/null; then echo "ok:      $f"; else echo "CORRUPT: $f"; fi
done
echo "[$(date +%H:%M:%S)] done."
