#!/usr/bin/env python3
"""bench.py — Latency and throughput benchmarks for the mesh.

Measures, against a live three-agent mesh on localhost:
  1. crypto micro-benchmark: Ed25519 sign / verify operations per second
     (explains the latency floor of the reference implementation);
  2. end-to-end job latency: N sequential sum-of-squares jobs, per-job
     latency recorded to CSV, percentiles p50/p95/p99 reported;
  3. throughput: concurrent clients (1, 5, 10) submitting jobs, jobs/sec
     and mean latency reported to CSV.

Usage: python3 src/bench.py [--latency-n N] [--throughput-jobs K]
       [--out-dir DIR]
Defaults: latency N=200, throughput 30 jobs per concurrency level.
All timings use time.perf_counter.  Results are printed and written as
CSV files; the script exits 0 iff every submitted job returned the
correct, verified total.
"""
import argparse
import csv
import os
import statistics
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import ed25519
import mesh


def percentile(sorted_values, p):
    if not sorted_values:
        return float("nan")
    idx = (len(sorted_values) - 1) * p / 100.0
    lo = int(idx)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = idx - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def crypto_bench(n=200):
    seed = os.urandom(32)
    pk, _ = ed25519.keygen(seed)
    msg = b"bench" * 8
    t0 = time.perf_counter()
    for _ in range(n):
        sig = ed25519.sign(msg, pk, seed)
    sign_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    ok = 0
    for _ in range(n):
        ok += ed25519.verify(sig, msg, pk)
    verify_s = time.perf_counter() - t0
    sign_us = sign_s / n * 1e6
    verify_us = verify_s / n * 1e6
    print(f"crypto sign: n={n} {n / sign_s:.1f} ops/s "
          f"mean={sign_us:.0f} us/op")
    print(f"crypto verify: n={n} {n / verify_s:.1f} ops/s "
          f"mean={verify_us:.0f} us/op verified={ok}/{n}")
    return {"sign_us": sign_us, "verify_us": verify_us,
            "sign_ops": n / sign_s, "verify_ops": n / verify_s}


def latency_bench(m, n, out_dir):
    latencies = []
    failures = 0
    for i in range(n):
        job_id = f"lat-{i}"
        t0 = time.perf_counter()
        try:
            total, verified = m.client.submit_job(job_id, 1000)
            ok = total == mesh.closed_form_sum_squares(1000) and verified
        except Exception:  # noqa: BLE001 - count and continue
            ok = False
        dt_ms = (time.perf_counter() - t0) * 1000
        latencies.append(dt_ms)
        if not ok:
            failures += 1
    path = os.path.join(out_dir, "latency.csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["job", "latency_ms"])
        for i, ms in enumerate(latencies):
            w.writerow([i, f"{ms:.3f}"])
    lat_sorted = sorted(latencies)
    stats = {
        "n": n,
        "mean_ms": statistics.mean(latencies),
        "p50_ms": percentile(lat_sorted, 50),
        "p95_ms": percentile(lat_sorted, 95),
        "p99_ms": percentile(lat_sorted, 99),
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "failures": failures,
    }
    print(f"latency: n={n} mean={stats['mean_ms']:.2f} ms "
          f"p50={stats['p50_ms']:.2f} ms p95={stats['p95_ms']:.2f} ms "
          f"p99={stats['p99_ms']:.2f} ms min={stats['min_ms']:.2f} ms "
          f"max={stats['max_ms']:.2f} ms failures={failures}")
    return stats


def throughput_bench(m, jobs_per_level, out_dir):
    rows = []
    for concurrency in (1, 5, 10):
        latencies = []
        failures = 0
        lock = threading.Lock()

        def worker(wid):
            nonlocal failures
            client = m.add_client(f"client-{concurrency}-{wid}")
            for k in range(jobs_per_level):
                job_id = f"thr-{concurrency}-{wid}-{k}"
                t0 = time.perf_counter()
                try:
                    total, verified = client.submit_job(job_id, 1000)
                    ok = (total == mesh.closed_form_sum_squares(1000)
                          and verified)
                except Exception:  # noqa: BLE001
                    ok = False
                dt_ms = (time.perf_counter() - t0) * 1000
                with lock:
                    latencies.append(dt_ms)
                    if not ok:
                        failures += 1

        t0 = time.perf_counter()
        threads = [threading.Thread(target=worker, args=(w,))
                   for w in range(concurrency)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - t0
        total_jobs = concurrency * jobs_per_level
        row = {"concurrency": concurrency, "jobs": total_jobs,
               "elapsed_s": elapsed, "jobs_per_s": total_jobs / elapsed,
               "mean_ms": statistics.mean(latencies),
               "failures": failures}
        rows.append(row)
        print(f"throughput: concurrency={concurrency} jobs={total_jobs} "
              f"elapsed={elapsed:.2f} s jobs_per_s={row['jobs_per_s']:.2f} "
              f"mean_latency={row['mean_ms']:.2f} ms failures={failures}")
    path = os.path.join(out_dir, "throughput.csv")
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["concurrency", "jobs",
                                           "elapsed_s", "jobs_per_s",
                                           "mean_ms", "failures"])
        w.writeheader()
        for row in rows:
            w.writerow({k: (f"{v:.3f}" if isinstance(v, float) else v)
                        for k, v in row.items()})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latency-n", type=int, default=200)
    ap.add_argument("--throughput-jobs", type=int, default=30)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    out_dir = args.out_dir or os.path.join(
        os.path.dirname(__file__), "..", "outputs")
    os.makedirs(out_dir, exist_ok=True)
    print("bench: starting mesh (planner/worker/auditor on 127.0.0.1)")
    m = mesh.Mesh()
    m.start()
    try:
        crypto = crypto_bench()
        latency = latency_bench(m, args.latency_n, out_dir)
        throughput = throughput_bench(m, args.throughput_jobs, out_dir)
        print(f"bench: latency.csv and throughput.csv written to {out_dir}")
        ok = latency["failures"] == 0 and all(
            r["failures"] == 0 for r in throughput)
        print(f"RESULT: {'PASS' if ok else 'FAIL'} benchmarks "
              f"crypto_sign_us={crypto['sign_us']:.0f} "
              f"crypto_verify_us={crypto['verify_us']:.0f} "
              f"latency_p50_ms={latency['p50_ms']:.2f} "
              f"latency_p95_ms={latency['p95_ms']:.2f} "
              f"throughput_1c={throughput[0]['jobs_per_s']:.2f} "
              f"throughput_10c={throughput[2]['jobs_per_s']:.2f}")
        return 0 if ok else 1
    finally:
        m.stop()


if __name__ == "__main__":
    raise SystemExit(main())
