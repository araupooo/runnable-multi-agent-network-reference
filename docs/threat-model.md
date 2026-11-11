# Threat model — channel authentication and agent identity

## Scope

This reference runs three agents (planner, worker, auditor) plus a
client on localhost TCP (127.0.0.1, ports 19001–19003). The threat
model covers the message channel and agent identities as implemented
in `src/mesh.py`. It does not cover host compromise, the Python
runtime, or the operating system.

## Assets

- Job integrity: the sum-of-squares result returned to the client
  must equal the closed form and be verified by the auditor.
- Agent identities: each agent's Ed25519 keypair (private keys exist
  only in memory, generated at runtime).
- Message authenticity: every envelope must come from its claimed
  sender, unmodified, exactly once (within the replay window).

## Trust boundary

The dashed boundary in `docs/topology.svg` is the localhost interface.
Everything inside it is the mesh; everything outside (other local
processes, other hosts) is untrusted. The mesh binds 127.0.0.1 only
and never listens on an external interface.

## Threat actors

- **Local observer**: a process on the same host that can read
  localhost traffic.
- **Rogue agent**: a process holding a valid keypair that is not in
  the registry, or a registered agent sending messages it is not
  authorised to send.
- **Compromised agent**: a registered agent whose private key is
  stolen (out of scope for detection — see F4).
- **Replay attacker**: anyone who captured a valid envelope and
  re-sends it.

## Findings

| ID | Severity | Finding | Evidence | Mitigation / status |
|----|----------|---------|----------|---------------------|
| F1 | Low | Transport is plaintext localhost TCP: messages are authenticated and integrity-protected, but NOT encrypted — a local observer can read message contents (job parameters and partial sums). | `src/mesh.py` (no TLS); `docs/methodology.md` | Accepted for this reference. Binding is 127.0.0.1 only, so the exposure is limited to local processes. Production use must add TLS (RFC 8446) or move to Unix sockets with filesystem permissions. |
| F2 | Low | The Ed25519 implementation is pure Python and not constant-time; timing side channels are possible in principle. | `src/ed25519.py` header; RFC 8032 §8.1 | Accepted for this reference. Production use must use a vetted library (e.g. libsodium / `cryptography`). The implementation is validated against the RFC 8032 §7.1 vectors, not hardened. |
| F3 | Informational | Replay protection uses a sliding window of 128 sequence numbers per sender plus a seen-set. Replays inside the window are caught by the seen-set; replays below the window are caught by the age check. | `src/mesh.py` (`REPLAY_WINDOW`); test T5 | Mitigated. Residual: a replayed message whose seq is still inside the window but was never delivered (e.g. captured in transit) would be accepted once — the window cannot distinguish a first delivery from a replay of an undelivered original. This is inherent to sequence-number replay protection without a challenge-response handshake. |
| F4 | Low | No key rotation or forward secrecy: agent keypairs live for the process lifetime, and a stolen private key lets the attacker impersonate that agent until restart. | `src/mesh.py` (`Mesh.__init__`) | Accepted for this reference. Keys are generated fresh on every start (`os.urandom`) and never written to disk, so the exposure window is one process lifetime and there is no long-term key material to steal. |
| F5 | Informational | Sequence-number state resets on restart, so a message captured before a restart could be replayed after it. | `src/mesh.py` (in-memory `seen`) | Accepted and disclosed. Production use must persist sequence state or rotate keys on restart. |
| F6 | Informational | No rate limiting: a peer can open many connections and submit many jobs; the only bound is the 1 MiB frame cap and the 10 s socket timeout. | `src/mesh.py` (`MAX_FRAME`, `SOCKET_TIMEOUT`) | Accepted for this reference (localhost, trusted peers). Production use must add per-peer rate limits. |
| F7 | Low | A strictly-increasing sequence check would reject legitimate out-of-order messages under concurrency. Found by the benchmark suite: before the fix, throughput at 5 concurrent clients showed 80/150 failed jobs and at 10 clients 219/300, all rejected `stale_seq`; after the fix all levels show 0 failures (see `outputs/benchmarks-run1.log` and `outputs/benchmarks-run2.log`). | `src/mesh.py` window code; benchmark logs | Fixed: sliding window of 128 + seen-set. The pre-fix failure counts are quoted from the observed pre-fix runs; the shipped logs are the post-fix runs. |
| F8 | Informational | The registry is a shared in-process dictionary: any code that can call `Mesh.add_client` can register a new identity. | `src/mesh.py` (`Mesh.add_client`) | Accepted for this reference. In production the registry must be a signed key directory, not a mutable object. |

## What the tests prove

| Attack | Test | Result |
|--------|------|--------|
| Tampered payload (signature no longer matches) | T2 | Rejected `bad_signature` |
| Unknown key / unregistered sender | T3, T8 | Rejected `unknown_sender` |
| Identity spoofing (valid key, wrong identity) | T4 | Rejected `bad_signature` |
| Replay of a valid envelope | T5 | Rejected `stale_seq` |
| Message delivered to the wrong agent | T6 | Rejected `wrong_recipient` |
| Registered agent sending a type it may not send | T7 | Rejected `unauthorised_sender` |
| Malformed (non-JSON) frame | T9 | Rejected `malformed` |

All attack deliveries are counted in per-agent rejection stats; the
suite asserts exactly 8 rejections and 0 rejected legitimate messages
(test T10).

## Out of scope (not tested)

- Compromised-agent behaviour (a registered agent signing malicious
  but well-formed messages) — the auditor recomputes partial sums, so
  a malicious worker is caught by the audit step, but a malicious
  auditor could falsely claim `verified=true`. This is a known
  limitation: verification is only as trustworthy as the auditor.
- TLS / encryption (F1), key rotation (F4), rate limiting (F6).
- Behaviour across process restarts (F5).
