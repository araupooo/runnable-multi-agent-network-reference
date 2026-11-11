# Run manifest

Generated: 2026-11-11 01:30:20 UTC

Commands: scripts/run_tests.sh (Ed25519 vectors + mesh integration tests), scripts/run_benchmarks.sh run1/run2, scripts/clean_reproduce.sh (fresh copy: full tests + full benchmarks).

## Output files (sha256)

700264366faacb010ae269829d4c7a1b97d574ebc82ae00398d7dded2d3802b5  bench-run1/latency.csv
930461b6079baf1ec8807d288a987f8d5b030b52ca49c2d433414c96f3e9b9e7  bench-run1/throughput.csv
68d27c8217ab0b634ddeb450bf226bd614c61eee6ca8c074141dd5ff46704b0f  bench-run2/latency.csv
3d7b656ecd1c1e18d90ec045f8fc656122023032fb790e22334155ff9d7f0394  bench-run2/throughput.csv
f9202b500f3a58c71736cce8c2a96f627e056101d92761e1258ef8d6bdc75ef3  benchmarks-run1.log
5837d061c18dc1eb4ebdabcb893576b5281801ac590cd691ced3c05ef6a79cec  benchmarks-run2.log
6ab722762aa063d8c5da8a3abe6a0b8e0eaced356d20fb525af2a8d91a48cbe0  fresh-clone-benchmarks.log
7fc1bf383d0ff9390a0f750f6af0a5bddea97ea75ec444af79c6620cda19dc24  fresh-clone-latency.csv
93137824dd81bc6e399100204cc494c2f3192d92cd0ab2b44330675f30732846  fresh-clone-run.log
1236804f38cf4d1aa3214586845ada0cf7ab8c3ce59c62744c95032d9997fa56  fresh-clone-tests.log
bfefe6affb342cd2337619d374359d6acce0ebeec9d91d2125a2834a78493199  fresh-clone-throughput.csv
22edcc3c3e55831fd40c79b54b5d653b4e797b06b21495be1e0038712338511a  integration-tests.log
700264366faacb010ae269829d4c7a1b97d574ebc82ae00398d7dded2d3802b5  latency.csv
930461b6079baf1ec8807d288a987f8d5b030b52ca49c2d433414c96f3e9b9e7  throughput.csv

## Headline results (from logs)

RESULT: PASS vectors=5 failures=0
RESULT: PASS integration failures=0
[run1] crypto sign: n=200 163.9 ops/s mean=6100 us/op
[run1] crypto verify: n=200 80.2 ops/s mean=12471 us/op verified=200/200
[run1] latency: n=200 mean=158.63 ms p50=151.46 ms p95=190.96 ms p99=220.46 ms min=145.97 ms max=236.86 ms failures=0
[run1] throughput: concurrency=1 jobs=30 elapsed=4.76 s jobs_per_s=6.30 mean_latency=158.40 ms failures=0
[run1] RESULT: PASS benchmarks crypto_sign_us=6100 crypto_verify_us=12471 latency_p50_ms=151.46 latency_p95_ms=190.96 throughput_1c=6.30 throughput_10c=6.11
[run2] crypto sign: n=200 172.8 ops/s mean=5786 us/op
[run2] crypto verify: n=200 80.5 ops/s mean=12419 us/op verified=200/200
[run2] latency: n=200 mean=155.46 ms p50=150.93 ms p95=179.27 ms p99=212.05 ms min=144.13 ms max=222.16 ms failures=0
[run2] throughput: concurrency=1 jobs=30 elapsed=4.80 s jobs_per_s=6.26 mean_latency=159.46 ms failures=0
[run2] RESULT: PASS benchmarks crypto_sign_us=5786 crypto_verify_us=12419 latency_p50_ms=150.93 latency_p95_ms=179.27 throughput_1c=6.26 throughput_10c=6.13
[fresh-clone] crypto sign: n=200 176.4 ops/s mean=5670 us/op
[fresh-clone] crypto verify: n=200 76.4 ops/s mean=13092 us/op verified=200/200
[fresh-clone] latency: n=200 mean=164.99 ms p50=158.60 ms p95=199.21 ms p99=242.37 ms min=147.27 ms max=295.97 ms failures=0
[fresh-clone] throughput: concurrency=1 jobs=30 elapsed=4.83 s jobs_per_s=6.21 mean_latency=160.69 ms failures=0
[fresh-clone] RESULT: PASS benchmarks crypto_sign_us=5670 crypto_verify_us=13092 latency_p50_ms=158.60 latency_p95_ms=199.21 throughput_1c=6.21 throughput_10c=6.09
clean_reproduce.sh DONE (workdir kept at /tmp/mesh-ref-repro)
