"""Inspect and import real IFC files from data/bim when available."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend.adapters.bim import BIMAdapter


def main() -> None:
    adapter = BIMAdapter()
    capability = adapter.capability()
    print(json.dumps(capability, indent=2))
    if capability["status"] == "BIM_NOT_LOADED":
        dependency_hint = (
            ""
            if capability.get("ifcopenshell") == "AVAILABLE"
            else " and install ifcopenshell"
        )
        print(f"BIM_NOT_LOADED: place a real .ifc file in data/bim{dependency_hint}.")
        return
    summaries = []
    for path in adapter.files():
        result = adapter.building(path.stem)
        summaries.append({
            "file": str(path),
            "status": result["status"],
            "storeys": len(result.get("hierarchy", {}).get("floors", [])),
            "space_candidates": len(result.get("spaces", [])),
            "ownership_units_claimed": 0,
        })
    output = ROOT / "data" / "bim_import_summary.json"
    output.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()
