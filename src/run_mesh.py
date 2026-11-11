#!/usr/bin/env python3
"""run_mesh.py — Start the three-agent mesh and run one demo job.

Usage: python3 src/run_mesh.py [n]
  n defaults to 1000 (sum of squares 1^2 + ... + n^2).
Prints the job result, the closed-form check, and per-agent message stats.
Keys are generated at runtime and never written to disk.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import mesh


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    m = mesh.Mesh()
    print("mesh: starting agents planner/worker/auditor on 127.0.0.1:19001-19003")
    print("mesh: public keys (hex):")
    for name, pk in m.public_keys_hex().items():
        print(f"mesh:   {name}: {pk}")
    m.start()
    try:
        total, verified = m.client.submit_job("demo-1", n)
        expected = mesh.closed_form_sum_squares(n)
        print(f"job demo-1: n={n} total={total} verified={verified} "
              f"expected={expected} match={total == expected}")
        for name, agent in m.agents.items():
            print(f"stats {name}: sent={agent.stats['sent']} "
                  f"received={agent.stats['received']} "
                  f"rejected={agent.stats['rejected']}")
        print(f"stats client: sent={m.client.stats['sent']} "
              f"received={m.client.stats['received']}")
        ok = total == expected and verified
        print(f"RESULT: {'PASS' if ok else 'FAIL'} demo job")
        return 0 if ok else 1
    finally:
        m.stop()


if __name__ == "__main__":
    raise SystemExit(main())
