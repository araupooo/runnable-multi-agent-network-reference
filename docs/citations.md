# Primary sources

Every specification-derived claim in this pack traces to one of these
primary sources. Fetched and checked 2026-11-11.

- RFC 8032, *Edwards-Curve Digital Signature Algorithm (EdDSA)*,
  Josefsson & Liusvaara, January 2017 (IRTF, Informational).
  https://www.rfc-editor.org/rfc/rfc8032.txt
  Used for: Ed25519 key generation (section 5.1.5), signing (5.1.6),
  verification (5.1.7), and the section 7.1 test vectors that
  `tests/test_ed25519_vectors.py` validates against. Note the RFC's own
  status text: it is published for informational purposes and is not an
  Internet Standards Track specification.

- RFC 8785, *JSON Canonicalization Scheme (JCS)*, Rundgren et al.,
  June 2020 (Informational).
  https://datatracker.ietf.org/doc/html/rfc8785
  Used for: the canonical JSON serialisation of signed envelopes
  (sorted keys, no insignificant whitespace, UTF-8). The mesh uses the
  restricted-data-model subset described in `docs/methodology.md`, not
  a general JCS implementation.

- RFC 8259, *The JavaScript Object Notation (JSON) Data Interchange
  Format*, Bray, December 2017 (Internet Standard).
  https://www.rfc-editor.org/rfc/rfc8259.txt
  Used for: the JSON data model of the message envelopes.

- Python 3.12.3 standard library documentation
  (https://docs.python.org/3.12/library/): `hashlib` (SHA-512),
  `json` (serialisation), `socket` / `socketserver` (TCP transport),
  `threading`, `csv`, `statistics`. Used for: every runtime behaviour
  of the implementation; no third-party code is used anywhere.

- NIST FIPS 186-5, *Digital Signature Standard (DSS)*, February 2023,
  section on EdDSA (informational reference only).
  https://csrc.nist.gov/pubs/fips/186-5/final
  Cited for: Ed25519 as a standardised signature scheme at the
  ~128-bit security level. The implementation itself follows RFC 8032,
  not FIPS 186-5.
