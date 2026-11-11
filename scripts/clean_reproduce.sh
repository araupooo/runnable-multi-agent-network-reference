#!/bin/bash
# clean_reproduce.sh — Fresh-clone verification for the whole pack.
#
# Copies this pack to a fresh directory, re-runs the FULL test suite and
# the FULL benchmark suite there (not a subset), copies the fresh logs
# into the shipped outputs/ directory, and prints a comparison of the
# headline numbers (fresh clone vs shipped).
#
# Usage: bash scripts/clean_reproduce.sh [workdir]
#   workdir defaults to /tmp/mesh-ref-repro.
# Writes (into the shipped pack's outputs/):
#   fresh-clone-run.log         this script's own output (incl. comparison)
#   fresh-clone-tests.log       fresh full test-suite output
#   fresh-clone-benchmarks.log  fresh full benchmark output
#   fresh-clone-latency.csv     fresh per-job latency data
#   fresh-clone-throughput.csv  fresh throughput data
# Exit code 0 iff the fresh test suite AND the fresh benchmarks pass.
set -u
PACK="$(cd "$(dirname "$0")/.." && pwd)"
R="${1:-/tmp/mesh-ref-repro}"
LOG="$PACK/outputs/fresh-clone-run.log"
mkdir -p "$PACK/outputs"

run() {
  echo "clean_reproduce: workdir=$R"
  echo "clean_reproduce: source pack=$PACK"
  echo "clean_reproduce: python=$(python3 --version 2>&1)"
  rm -rf "$R"
  mkdir -p "$R"
  cp -r "$PACK" "$R/pack"
  cd "$R/pack"
  echo "--- fresh-clone test suite (full) ---"
  bash scripts/run_tests.sh
  t=$?
  echo "fresh tests exit=$t"
  echo "--- fresh-clone benchmarks (full) ---"
  bash scripts/run_benchmarks.sh repro
  b=$?
  echo "fresh benchmarks exit=$b"
  cp outputs/integration-tests.log "$PACK/outputs/fresh-clone-tests.log"
  cp outputs/benchmarks-repro.log "$PACK/outputs/fresh-clone-benchmarks.log"
  cp outputs/bench-repro/latency.csv "$PACK/outputs/fresh-clone-latency.csv"
  cp outputs/bench-repro/throughput.csv \
     "$PACK/outputs/fresh-clone-throughput.csv"
  echo "=== headline comparison (fresh clone vs shipped) ==="
  echo "--- ed25519 vectors ---"
  echo "fresh:   $(grep '^RESULT: PASS vectors=' outputs/integration-tests.log || echo MISSING)"
  echo "shipped: $(grep '^RESULT: PASS vectors=' "$PACK/outputs/integration-tests.log" || echo MISSING)"
  echo "--- mesh integration ---"
  echo "fresh:   $(grep '^RESULT: PASS integration' outputs/integration-tests.log || echo MISSING)"
  echo "shipped: $(grep '^RESULT: PASS integration' "$PACK/outputs/integration-tests.log" || echo MISSING)"
  echo "--- latency ---"
  echo "fresh:   $(grep '^latency:' outputs/benchmarks-repro.log || echo MISSING)"
  echo "shipped: $(grep '^latency:' "$PACK/outputs/benchmarks-run1.log" || echo MISSING)"
  echo "--- throughput ---"
  echo "fresh:"
  grep '^throughput:' outputs/benchmarks-repro.log || echo MISSING
  echo "shipped:"
  grep '^throughput:' "$PACK/outputs/benchmarks-run1.log" || echo MISSING
  echo "--- crypto ---"
  echo "fresh:   $(grep '^crypto sign:' outputs/benchmarks-repro.log || echo MISSING)"
  echo "shipped: $(grep '^crypto sign:' "$PACK/outputs/benchmarks-run1.log" || echo MISSING)"
  echo "clean_reproduce.sh DONE (workdir kept at $R)"
  [ "$t" -eq 0 ] && [ "$b" -eq 0 ]
}

run 2>&1 | tee "$LOG"
exit ${PIPESTATUS[0]}
