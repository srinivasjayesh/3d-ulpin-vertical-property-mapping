"""Optionally acquire one DEM and add honest ground/absolute-Z attributes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend.adapters.elevation import ElevationAdapter, collection_bounds, write_geojson


DATA = ROOT / "data"
BUILDINGS_INPUT = DATA / "all_buildings_processed.geojson"
FLOORS_INPUT = DATA / "all_floor_ulpins.geojson"
BUILDINGS_OUTPUT = DATA / "all_buildings_with_elevation.geojson"
FLOORS_OUTPUT = DATA / "all_floor_ulpins_absolute_z.geojson"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--download-opentopography",
        action="store_true",
        help="Make one study-area DEM request using OPENTOPOGRAPHY_API_KEY.",
    )
    args = parser.parse_args()
    buildings_collection = load(BUILDINGS_INPUT)
    floors_collection = load(FLOORS_INPUT)
    adapter = ElevationAdapter()
    if args.download_opentopography and not adapter.raster_files():
        bounds = collection_bounds(buildings_collection["features"])
        raster = adapter.acquire_opentopography_dem(bounds)
        print(f"Cached one study-area DEM: {raster}")
    capability = adapter.capability()
    print(json.dumps(capability, indent=2))
    if capability["status"] != "ACTIVE":
        print("GROUND_ELEVATION_PENDING: no data outputs were written.")
        return
    buildings, floors = adapter.enrich(buildings_collection["features"], floors_collection["features"])
    write_geojson(BUILDINGS_OUTPUT, buildings_collection, buildings)
    write_geojson(FLOORS_OUTPUT, floors_collection, floors)
    absolute_count = sum(feature["properties"].get("absolute_z_min_m") is not None for feature in floors)
    print(f"Buildings enriched: {len(buildings)}")
    print(f"Floor units with absolute Z: {absolute_count}")
    print(f"Saved: {BUILDINGS_OUTPUT}")
    print(f"Saved: {FLOORS_OUTPUT}")


if __name__ == "__main__":
    main()
