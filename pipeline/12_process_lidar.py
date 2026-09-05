"""Process real LAS/LAZ sources without changing original height observations."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend.adapters.lidar import LiDARAdapter


DATA = ROOT / "data"


def main() -> None:
    adapter = LiDARAdapter()
    capability = adapter.capability()
    print(json.dumps(capability, indent=2))
    if capability["status"] != "LIDAR_LOADED":
        print("LIDAR_NOT_LOADED: place real .las/.laz files with CRS metadata in data/lidar.")
        return
    collection = json.loads((DATA / "all_buildings_processed.geojson").read_text(encoding="utf-8"))
    results = [adapter.analyze_building(feature) for feature in collection["features"]]
    output = DATA / "lidar_height_results.json"
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    available = sum(result["status"] == "LIDAR_HEIGHT_AVAILABLE" for result in results)
    print(f"Buildings with LiDAR observations: {available}")
    print("Original Google/OSM height values were not overwritten.")
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()
