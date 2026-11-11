#!/bin/bash
# verify_digests.sh — Verify SHA256SUMS over all pack files.
# Usage: bash scripts/verify_digests.sh
# Exit code 0 iff every listed file matches its recorded digest.
set -u
PACK="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PACK"
sha256sum --check SHA256SUMS
