#!/bin/bash
# run_tests.sh — Run the full test suite and save the unedited output.
# Usage: bash scripts/run_tests.sh
# Writes: outputs/integration-tests.log (appended per section, unedited).
# Exit code 0 iff the Ed25519 vector tests AND the mesh integration
# tests both pass.
set -u
PACK="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PACK"
mkdir -p outputs
LOG="outputs/integration-tests.log"
: > "$LOG"
{
  echo "run_tests: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  python3 --version
  echo "--- ed25519 vectors (RFC 8032 section 7.1) ---"
  python3 tests/test_ed25519_vectors.py
  echo "vectors exit=$?"
  echo "--- mesh integration tests ---"
  python3 tests/test_mesh.py
  echo "mesh exit=$?"
} 2>&1 | tee "$LOG"
# Re-derive exit codes from the log's RESULT lines (tee masks them).
V_FAIL=$(grep -c "^RESULT: FAIL" "$LOG" || true)
if [ "$V_FAIL" -eq 0 ] && grep -q "^RESULT: PASS" "$LOG"; then
  echo "run_tests: PASS (see $LOG)"
  exit 0
else
  echo "run_tests: FAIL (see $LOG)"
  exit 1
fi
