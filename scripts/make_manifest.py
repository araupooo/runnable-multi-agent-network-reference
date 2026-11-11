#!/usr/bin/env python3
"""make_manifest.py — Generate outputs/run-manifest.md.

Lists every file under outputs/ (except the manifest itself) with its
SHA-256, plus the headline results extracted from the logs.
Usage: python3 scripts/make_manifest.py
Run AFTER all outputs exist (tests, benchmarks run1/run2, fresh-clone
logs) and BEFORE the final SHA256SUMS regeneration.
"""
import hashlib
import os
import re

PACK = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(PACK, "outputs")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def grep_line(path, pattern):
    try:
        with open(path, errors="replace") as fh:
            for line in fh:
                if re.search(pattern, line):
                    return line.rstrip()
    except FileNotFoundError:
        pass
    return None


def main():
    lines = ["# Run manifest", "",
             f"Generated: {__import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
             "",
             "Commands: scripts/run_tests.sh (Ed25519 vectors + mesh "
             "integration tests), scripts/run_benchmarks.sh run1/run2, "
             "scripts/clean_reproduce.sh (fresh copy: full tests + full "
             "benchmarks).",
             "",
             "## Output files (sha256)", ""]
    files = []
    for root, _dirs, names in os.walk(OUT):
        for name in sorted(names):
            if name == "run-manifest.md":
                continue
            full = os.path.join(root, name)
            rel = os.path.relpath(full, OUT)
            files.append((rel, sha256(full)))
    for rel, digest in sorted(files):
        lines.append(f"{digest}  {rel}")
    lines += ["", "## Headline results (from logs)", ""]
    tests_log = os.path.join(OUT, "integration-tests.log")
    for pat in (r"^RESULT: PASS vectors=", r"^RESULT: PASS integration"):
        hit = grep_line(tests_log, pat)
        if hit:
            lines.append(f"{hit}")
    for label in ("run1", "run2"):
        log = os.path.join(OUT, f"benchmarks-{label}.log")
        for pat in (r"^crypto sign:", r"^crypto verify:", r"^latency:",
                    r"^throughput:", r"^RESULT:"):
            hit = grep_line(log, pat)
            if hit:
                lines.append(f"[{label}] {hit}")
    log = os.path.join(OUT, "fresh-clone-benchmarks.log")
    for pat in (r"^crypto sign:", r"^crypto verify:", r"^latency:",
                r"^throughput:", r"^RESULT:"):
        hit = grep_line(log, pat)
        if hit:
            lines.append(f"[fresh-clone] {hit}")
    fresh = os.path.join(OUT, "fresh-clone-run.log")
    hit = grep_line(fresh, r"clean_reproduce.sh DONE")
    if hit:
        lines.append(hit)
    with open(os.path.join(OUT, "run-manifest.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"run-manifest: wrote outputs/run-manifest.md ({len(files)} files)")


if __name__ == "__main__":
    main()
