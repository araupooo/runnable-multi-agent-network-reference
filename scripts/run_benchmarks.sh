#!/bin/bash
# run_benchmarks.sh — Run the full benchmark suite and save unedited output.
# Usage: bash scripts/run_benchmarks.sh [label]
#   label defaults to "run1".  Logs go to outputs/benchmarks-<label>.log;
#   CSVs go to outputs/bench-<label>/ (run1 also copies its CSVs to the
#   top-level outputs/latency.csv and outputs/throughput.csv).
# Exit code 0 iff every benchmarked job returned the correct verified total.
set -u
PACK="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PACK"
LABEL="${1:-run1}"
mkdir -p "outputs/bench-$LABEL"
LOG="outputs/benchmarks-$LABEL.log"
{
  echo "run_benchmarks: label=$LABEL $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  python3 --version
  python3 src/bench.py --out-dir "outputs/bench-$LABEL"
  echo "bench exit=$?"
} 2>&1 | tee "$LOG"
if [ "$LABEL" = "run1" ]; then
  cp "outputs/bench-run1/latency.csv" outputs/latency.csv
  cp "outputs/bench-run1/throughput.csv" outputs/throughput.csv
fi
if grep -q "^RESULT: PASS" "$LOG"; then
  echo "run_benchmarks: PASS (see $LOG)"
  exit 0
else
  echo "run_benchmarks: FAIL (see $LOG)"
  exit 1
fi
