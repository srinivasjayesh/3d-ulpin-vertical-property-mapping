"""Create a non-destructive source-fused building artifact."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend.source_fusion import apply_to_collection


DATA = ROOT / "data"
INPUT = DATA / "all_buildings_processed.geojson"
OUTPUT = DATA / "all_buildings_source_fused.geojson"
LIDAR_RESULTS = DATA / "lidar_height_results.json"


def main() -> None:
    collection = json.loads(INPUT.read_text(encoding="utf-8"))
    features = collection["features"]
    if LIDAR_RESULTS.exists():
        lidar = {
            item["building_id"]: item
            for item in json.loads(LIDAR_RESULTS.read_text(encoding="utf-8"))
            if item.get("status") == "LIDAR_HEIGHT_AVAILABLE"
        }
        for feature in features:
            observation = lidar.get(str(feature["properties"].get("building_id")))
            if observation:
                feature["properties"].update(observation)
    collection["features"] = apply_to_collection(features)
    OUTPUT.write_text(json.dumps(collection, separators=(",", ":")), encoding="utf-8")
    counts: dict[str, int] = {}
    for feature in collection["features"]:
        source = feature["properties"]["selected_height_source"]
        counts[source] = counts.get(source, 0) + 1
    print(json.dumps({"buildings": len(features), "selected_sources": counts}, indent=2))
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()
