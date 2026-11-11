# Methodology

## System under test

Three agents — planner, worker, auditor — plus a client, all in one
Python 3.12.3 process (standard library only, no third-party packages).
Each agent is an independent thread with its own Ed25519 keypair
(generated at runtime with `os.urandom`, never written to disk), its own
sequence counters, and its own TCP listener on 127.0.0.1
(planner 19001, worker 19002, auditor 19003). Agents share nothing
except the public-key registry (the analogue of a key directory in a
real deployment). All communication is localhost TCP with length-prefixed
JSON frames (4-byte big-endian length, max 1 MiB).

## Message format

Every message is a signed JSON envelope:

```json
{"version": 1, "sender": "planner", "recipient": "worker",
 "type": "task.assign", "seq": 12, "ts_ms": 1731240000123,
 "payload": {"job_id": "lat-7", "lo": 1, "hi": 500},
 "sig": "<128 hex chars>"}
```

`sig` is the 64-byte Ed25519 signature (RFC 8032) over the canonical
JSON bytes of the envelope without `sig`. Canonicalisation follows the
JSON Canonicalization Scheme (RFC 8785) for the restricted data model
used here: keys sorted, no insignificant whitespace, UTF-8 encoding.
Two JCS details are handled by restriction rather than by a full
implementation — Python's `json.dumps(sort_keys=True)` sorts by Unicode
code point, while JCS sorts by UTF-16 code unit, and JCS numbers follow
ECMAScript serialisation. Neither matters for this mesh: every key and
string value is ASCII (where the two orderings coincide) and the signed
content contains only strings, integers, booleans, null, lists and
objects — no floating point numbers. The serialiser is therefore
byte-identical to JCS output for every message this mesh sends, but it
is not a general JCS implementation and must not be reused for arbitrary
JSON.

## Verification on receipt (in order)

1. Frame parses as JSON, `version == 1`, `recipient == self`.
2. Sender is in the public-key registry (unknown sender rejected).
3. Signature verifies against the registered public key of the claimed
   sender (tampering and identity spoofing rejected).
4. Sender is authorised for this message type (see `ALLOWED_SENDERS` in
   `src/mesh.py`; replies may only come from the agent that handled the
   request).
5. `seq` passes the replay check: a sliding window of the last 128
   sequence numbers per sender. A message is accepted if its `seq` is
   new and not older than the window floor; exact duplicates and
   anything below the window are rejected. (A strictly-increasing check
   would break under concurrency: one agent sending from several threads
   can deliver messages out of order. The window plus a seen-set keeps
   replay protection while tolerating reordering within the window.)

Rejections are answered with a plain (unsigned) error frame
`{"error": "<reason>", "detail": "..."}` and counted in per-agent stats.

## Cooperative workflow

Job: sum of squares 1^2 + ... + n^2.

1. client -> planner: `job.request {job_id, n}`.
2. planner -> worker: `task.assign {job_id, lo, hi}` for each half of
   the range (two messages).
3. worker -> planner: `task.result {job_id, lo, hi, partial}` per half.
4. planner -> auditor: `audit.request {job_id, parts: [...]}`.
5. auditor recomputes each part independently and returns
   `audit.result {job_id, verified, total}`.
6. planner -> client: `job.request.reply {job_id, total, verified}`.

The client checks the total against the closed form
n(n+1)(2n+1)/6. Every hop is a signed envelope; the whole job uses
8 signatures and 8 verifications.

## Cryptography

Ed25519 is implemented in pure Python (`src/ed25519.py`, extended
twisted-Edwards coordinates, RFC 8032 sections 5.1.5–5.1.7) and
validated against all five RFC 8032 section 7.1 test vectors (TEST 1,
TEST 2, TEST 3, TEST 1024, TEST SHA(abc)): key generation, signing and
verification all match, and a tampered signature is rejected
(`tests/test_ed25519_vectors.py`). The implementation is a reference:
it is not constant-time and is not intended for production use.

## Benchmarks

- Crypto micro-benchmark: 200 Ed25519 signs and 200 verifies of a
  40-byte message, timed with `time.perf_counter`.
- Latency: 200 sequential end-to-end jobs (n=1000), per-job latency to
  `outputs/latency.csv`; mean, p50, p95, p99, min, max reported.
- Throughput: concurrency levels 1, 5, 10, each submitting 30 jobs per
  client thread; each concurrent client has its own identity and
  keypair (see `Mesh.add_client`), because per-sender sequence numbers
  require one sequence space per identity. Results to
  `outputs/throughput.csv`.
- Every benchmark run is repeated (run1, run2) and the full suite is
  re-run once more from a fresh copy by `scripts/clean_reproduce.sh`;
  all three runs are shipped under `outputs/`.

## Environment

See `fixtures/environment.txt`: Python 3.12.3, Intel Xeon Platinum
8321HC @ 1.40 GHz, 4 vCPU, 8 GiB RAM, Ubuntu. The machine is a shared
virtual machine; background load can inflate latency outliers (see
limitations).

## Reproduce

```bash
bash scripts/run_tests.sh        # full test suite -> outputs/integration-tests.log
bash scripts/run_benchmarks.sh run1   # benchmarks -> outputs/benchmarks-run1.log
bash scripts/clean_reproduce.sh  # fresh copy: full tests + full benchmarks
bash scripts/verify_digests.sh   # SHA256SUMS check over the whole pack
```
