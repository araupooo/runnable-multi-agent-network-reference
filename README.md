# Runnable Multi-Agent Network Reference

A public, inspectable reference implementation of a small multi-agent
service mesh: three cooperating agents (planner, worker, auditor) plus
a client, communicating over authenticated localhost TCP channels.
Every message is a signed JSON envelope (Ed25519, RFC 8032); receivers
verify the signature, the sender's identity, the recipient, the
message type, and a replay-protection sequence window.

## What it does

A client submits a job — compute 1² + 2² + … + n² — to the planner.
The planner splits the range in two, the worker computes the partial
sums, the auditor recomputes each part independently and aggregates,
and the client checks the total against the closed form
n(n+1)(2n+1)/6. Every hop is authenticated; tampered, spoofed,
replayed, misaddressed and unauthorised messages are rejected (see
`docs/threat-model.md` for the full threat model and the test
evidence).

## Quickstart

```bash
python3 src/run_mesh.py 1000   # start the mesh, run one demo job
bash scripts/run_tests.sh      # full test suite
bash scripts/run_benchmarks.sh run1   # latency + throughput benchmarks
bash scripts/clean_reproduce.sh      # fresh copy: full tests + benchmarks
bash scripts/verify_digests.sh       # SHA-256 check over the whole pack
```

Requirements: Python 3.12 (standard library only — no third-party
packages, no network access). Tested on Python 3.12.3, Ubuntu,
4 vCPU; see `fixtures/environment.txt`.

## Layout

- `src/ed25519.py` — pure-Python Ed25519 (RFC 8032), validated against
  the RFC 8032 §7.1 test vectors.
- `src/mesh.py` — envelope format, signing/verification, the three
  agents, the client, and the cooperative workflow.
- `src/run_mesh.py` — demo CLI. `src/bench.py` — benchmarks.
- `tests/` — Ed25519 vector tests + mesh integration tests (T1–T10).
- `scripts/` — test/benchmark/fresh-clone/digest scripts.
- `docs/` — findings page (`index.html`), methodology, threat model,
  claims-to-evidence index, primary sources, topology diagram.
- `outputs/` — unedited test and benchmark logs, CSVs, fresh-clone
  logs, run manifest.
- `fixtures/environment.txt` — machine and dependency record.

## Security properties (and limits)

- Channel authentication, message integrity and explicit agent
  identities via Ed25519 signatures on canonical JSON (RFC 8785
  subset). Keys are generated at runtime and never written to disk.
- Replay protection: sliding window of 128 sequence numbers per
  sender plus a seen-set (see `docs/threat-model.md` F3/F7).
- Transport is plaintext localhost TCP: messages are authenticated
  but NOT encrypted — a local observer can read contents. No TLS,
  no key rotation, no rate limiting (see `docs/threat-model.md`).
- The Ed25519 implementation is a reference: not constant-time, not
  for production use. Use a vetted library (e.g. libsodium) in
  production.
