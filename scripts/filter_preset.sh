#!/usr/bin/env bash
# Per-preset Set-A filter: genotype mask (DP/GQ) -> site missingness -> MAC -> per-population HWE.
# This IS the cube's filtering-stringency knob (plan §4). Every threshold comes from config.yaml
# (passed in as args); nothing is hard-coded here.
#
# args: NORM POPMAP "POP1 POP2 .." DP GQ MAC FMISS HWE_P OUT TMPDIR
set -euo pipefail
NORM=$1; POPMAP=$2; POPS=$3; DP=$4; GQ=$5; MAC=$6; FMISS=$7; HWE=$8; OUT=$9; TMP=${10}
mkdir -p "$TMP"

# 1) genotype-level mask (low DP/GQ -> ./.), then site missingness, then minor-allele count
PRE="$TMP/premHWE.vcf.gz"
bcftools filter -S . -e "FMT/DP<${DP} | FMT/GQ<${GQ}" "$NORM" -Ou \
  | bcftools view -e "F_MISSING > ${FMISS}" -Ou \
  | bcftools view -c "${MAC}:minor" -Oz -o "$PRE"
bcftools index -t "$PRE"
PRE_N=$(bcftools index -n "$PRE")

# 2) per-POPULATION HWE: a site is dropped if it fails (P_HWE < threshold) in ANY population.
#    Pooled HWE would be wrong here — structure (Wahlund) creates false departures.
EXCL="$TMP/hwe_excl.txt"; : > "$EXCL"
for pop in $POPS; do
  awk -v p="$pop" 'NR>1 && $2==p {print $1}' "$POPMAP" > "$TMP/$pop.samples"
  vcftools --gzvcf "$PRE" --keep "$TMP/$pop.samples" --hardy --out "$TMP/$pop" 2>/dev/null
  # locate the P_HWE column by header name (robust to vcftools version), threshold it
  awk -v thr="$HWE" 'NR==1{for(i=1;i<=NF;i++) if($i=="P_HWE") c=i; next}
                     c && $c+0 < thr {print $1"\t"$2}' "$TMP/$pop.hwe" >> "$EXCL"
done
sort -u "$EXCL" > "$EXCL.sorted"

# 3) exclude the union of HWE failures
if [ -s "$EXCL.sorted" ]; then
  bcftools view -T "^$EXCL.sorted" "$PRE" -Oz -o "$OUT"
else
  cp "$PRE" "$OUT"
fi
bcftools index -t "$OUT"

# persist the post-MAC (pre-HWE) count — this is the HANDOFF-comparable number
echo "$PRE_N" > "${OUT%.vcf.gz}.postmac_count"
echo "[$OUT] pre-HWE(post-MAC)=$PRE_N  HWE-failing(union)=$(wc -l < "$EXCL.sorted" | tr -d ' ')  final=$(bcftools index -n "$OUT")"
