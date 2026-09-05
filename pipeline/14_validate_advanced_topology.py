"""Normalize validated warnings with absolute/relative-Z-aware semantics."""

from __future__ import annotations

import csv
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend.topology import normalize_issue


INPUT = ROOT / "data" / "all_topology_results.csv"
OUTPUT = ROOT / "data" / "all_topology_results_advanced.csv"


def main() -> None:
    with INPUT.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [normalize_issue(row) for row in csv.DictReader(handle)]
    fields = list(rows[0]) if rows else [
        "severity", "issue_type", "issue_class", "z_reference", "legal_status", "message"
    ]
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    relative = sum(row["z_reference"] == "RELATIVE_Z_ONLY" for row in rows)
    conflicts = sum(row["issue_class"] == "GEOMETRIC_CONFLICT" for row in rows)
    print(f"Issues normalized: {len(rows)}")
    print(f"Relative-Z warnings: {relative}")
    print(f"Absolute-Z geometric conflicts: {conflicts}")
    print("Legal conflicts asserted: 0")
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()
