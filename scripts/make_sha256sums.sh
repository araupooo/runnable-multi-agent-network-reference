#!/bin/bash
# make_sha256sums.sh — Regenerate SHA256SUMS over every file in the pack
# except SHA256SUMS itself.  Run AFTER all outputs exist (tests,
# benchmarks, fresh-clone logs, run manifest, docs).
# Usage: bash scripts/make_sha256sums.sh
set -u
PACK="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PACK"
find . -type f ! -name SHA256SUMS ! -path "./.git/*" | sort | xargs sha256sum > SHA256SUMS
echo "SHA256SUMS: $(wc -l < SHA256SUMS) files"
