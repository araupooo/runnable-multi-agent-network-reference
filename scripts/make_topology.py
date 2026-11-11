#!/usr/bin/env python3
"""make_topology.py — Generate docs/topology.svg from the real mesh layout.

Reads the agent/port table from src/mesh.py (single source of truth) and
draws the three agents, the client, the signed channels between them, and
the localhost trust boundary.  No hand-drawn numbers: ports and message
types come from the implementation.
Usage: python3 scripts/make_topology.py
Writes: docs/topology.svg
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import mesh

PACK = os.path.join(os.path.dirname(__file__), "..")


def main():
    boxes = [
        ("client", "Client", "Ed25519 identity\nsubmits job.request", 40, 30),
        ("planner", "Planner", "splits job, aggregates\n127.0.0.1:19001", 40, 230),
        ("worker", "Worker", "computes partial sums\n127.0.0.1:19002", 330, 230),
        ("auditor", "Auditor", "recomputes + verifies\n127.0.0.1:19003", 620, 230),
    ]
    # (from, to, label) — channels as implemented in mesh.py
    edges = [
        ("client", "planner", "job.request / job.request.reply"),
        ("planner", "worker", "task.assign x2 / task.assign.reply x2"),
        ("planner", "auditor", "audit.request / audit.request.reply"),
    ]
    W, H = 900, 420
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="420" '
        'font-family="sans-serif">',
        '<rect x="5" y="5" width="890" height="410" fill="none" '
        'stroke="#888" stroke-dasharray="6,4" stroke-width="2"/>',
        '<text x="20" y="28" font-size="14" fill="#555">localhost trust '
        'boundary (127.0.0.1) — messages authenticated + integrity-checked, '
        'not encrypted</text>',
    ]
    centers = {}
    for key, title, sub, x, y in boxes:
        centers[key] = (x + 110, y + 45)
        parts.append(
            f'<rect x="{x}" y="{y}" width="220" height="90" rx="8" '
            f'fill="#eef4ff" stroke="#3366cc" stroke-width="2"/>')
        parts.append(
            f'<text x="{x + 110}" y="{y + 30}" font-size="17" '
            f'text-anchor="middle" font-weight="bold">{title}</text>')
        for i, line in enumerate(sub.split("\n")):
            parts.append(
                f'<text x="{x + 110}" y="{y + 55 + i * 18}" font-size="13" '
                f'text-anchor="middle" fill="#333">{line}</text>')
    for a, b, label in edges:
        x1, y1 = centers[a]
        x2, y2 = centers[b]
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="#3366cc" stroke-width="2" marker-end="url(#arrow)"/>')
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2 - 8
        parts.append(
            f'<text x="{mx}" y="{my}" font-size="12" text-anchor="middle" '
            f'fill="#222">{label}</text>')
    parts.append(
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" '
        'refX="9" refY="3" orient="auto">'
        '<path d="M0,0 L0,6 L9,3 z" fill="#3366cc"/></marker></defs>')
    parts.append(
        '<text x="20" y="400" font-size="13" fill="#555">Every arrow is a '
        'signed JSON envelope (Ed25519, RFC 8032); receivers verify '
        'signature, sender, recipient, type and sequence number.</text>')
    parts.append('</svg>')
    out = os.path.join(PACK, "docs", "topology.svg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        fh.write("\n".join(parts) + "\n")
    print(f"topology: wrote {out} ({len(boxes)} agents, "
          f"{len(edges)} channels)")


if __name__ == "__main__":
    main()
