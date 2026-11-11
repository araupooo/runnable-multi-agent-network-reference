# Claims-to-evidence index

Each claim maps to the file(s) where it can be checked. "Shipped" means
the file is in this pack; run `scripts/verify_digests.sh` to check
integrity against `SHA256SUMS`.

## Cryptography

| Claim | Evidence |
|-------|----------|
| Ed25519 key generation, signing and verification match RFC 8032 §7.1 for all five test vectors | `tests/test_ed25519_vectors.py`, `outputs/integration-tests.log` (RESULT: PASS vectors=5) |
| A tampered signature fails verification | `tests/test_ed25519_vectors.py` (tampered-sig-rejected PASS, all vectors), `outputs/integration-tests.log` |
| Sign takes ~6 ms, verify ~12.5 ms (pure Python) | `src/bench.py`, `outputs/benchmarks-run1.log`, `outputs/benchmarks-run2.log` |

## Mesh behaviour

| Claim | Evidence |
|-------|----------|
| Three agents + client cooperate end-to-end; totals match the closed form n(n+1)(2n+1)/6 and are auditor-verified | `src/mesh.py` (workflow), `tests/test_mesh.py` T1, `outputs/integration-tests.log` |
| Tampered messages are rejected (`bad_signature`) | `tests/test_mesh.py` T2, `outputs/integration-tests.log` |
| Unknown keys / unknown agents are rejected (`unknown_sender`) | `tests/test_mesh.py` T3, T8, `outputs/integration-tests.log` |
| Identity spoofing is rejected (`bad_signature`) | `tests/test_mesh.py` T4, `outputs/integration-tests.log` |
| Replayed messages are rejected (`stale_seq`) | `tests/test_mesh.py` T5, `outputs/integration-tests.log` |
| Wrong-recipient messages are rejected (`wrong_recipient`) | `tests/test_mesh.py` T6, `outputs/integration-tests.log` |
| Unauthorised senders for a type are rejected (`unauthorised_sender`) | `tests/test_mesh.py` T7, `outputs/integration-tests.log` |
| Malformed frames are rejected (`malformed`) | `tests/test_mesh.py` T9, `outputs/integration-tests.log` |
| Exactly 8 attack deliveries rejected, 0 legitimate messages rejected | `tests/test_mesh.py` T10, `outputs/integration-tests.log` |
| Strictly-increasing sequence numbers broke under concurrency; sliding window of 128 + seen-set fixed it | `docs/threat-model.md` F7, `src/mesh.py` (`REPLAY_WINDOW`), `outputs/benchmarks-run1.log` (0 failures at all levels) |

## Benchmarks

| Claim | Evidence |
|-------|----------|
| End-to-end latency p50 ≈ 151 ms, p95 ≈ 180–191 ms (n=200) | `outputs/latency.csv`, `outputs/benchmarks-run1.log`, `outputs/benchmarks-run2.log` |
| Throughput is flat ~6.1–6.3 jobs/s at 1/5/10 concurrent clients (GIL-bound) | `outputs/throughput.csv`, `outputs/benchmarks-run1.log`, `outputs/benchmarks-run2.log` |
| Mean latency grows with concurrency (158 ms → ~1,617 ms at 10 clients) due to queueing | `outputs/throughput.csv`, benchmark logs |
| The crypto floor (~148 ms/job) explains the latency p50 | `docs/index.html` Table 3, benchmark logs |
| Fresh-clone re-run reproduces the headline numbers | `outputs/fresh-clone-run.log`, `outputs/fresh-clone-tests.log`, `outputs/fresh-clone-benchmarks.log`, `outputs/fresh-clone-latency.csv`, `outputs/fresh-clone-throughput.csv` |

## Architecture and threat model

| Claim | Evidence |
|-------|----------|
| Topology (agents, channels, trust boundary) matches the implementation | `docs/topology.svg` (generated from `src/mesh.py` by `scripts/make_topology.py`), `src/mesh.py` (`PORTS`, `ALLOWED_SENDERS`) |
| Threat model, severity-rated findings F1–F8 | `docs/threat-model.md` |
| Methodology (envelope format, verification order, workflow, environment) | `docs/methodology.md`, `fixtures/environment.txt` |
| Primary sources for every specification-derived claim | `docs/citations.md` |

## Reproducibility

| Claim | Evidence |
|-------|----------|
| Full test suite + full benchmarks re-run from a fresh copy; fresh logs shipped under `outputs/` | `scripts/clean_reproduce.sh`, `outputs/fresh-clone-run.log` |
| Every pack file matches its SHA-256 digest | `SHA256SUMS`, `scripts/verify_digests.sh` |
| Run manifest lists every output file with SHA-256 and headline results | `outputs/run-manifest.md` |
