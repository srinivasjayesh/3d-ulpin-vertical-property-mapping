"""Download public Dutch BAG and cadastral context for Amsterdam Centrum."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests
from pyproj import Transformer


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data" / "profiles" / "amsterdam"
BBOX_WGS84 = (4.865, 52.358, 4.925, 52.392)
# PDOK currently caps this WFS response at 1,000 features.
PAGE_SIZE = 1_000
SOURCES = {
    "buildings": {
        "url": "https://service.pdok.nl/lv/bag/wfs/v2_0",
        "type_name": "bag:pand",
        "output": "buildings.geojson",
        "backup": "osm_buildings.geojson",
    },
    "parcels": {
        "url": "https://service.pdok.nl/kadaster/kadastralekaart/wfs/v5_0",
        "type_name": "kadastrale kaart:Perceel".replace(" ", ""),
        "output": "parcels.geojson",
    },
}


def _bbox_28992() -> tuple[float, float, float, float]:
    west, south, east, north = BBOX_WGS84
    transformer = Transformer.from_crs(4326, 28992, always_xy=True)
    min_x, min_y = transformer.transform(west, south)
    max_x, max_y = transformer.transform(east, north)
    return min_x, min_y, max_x, max_y


def _tiles() -> list[str]:
    min_x, min_y, max_x, max_y = _bbox_28992()
    step_x = (max_x - min_x) / 4
    step_y = (max_y - min_y) / 4
    return [
        f"{min_x + col * step_x},{min_y + row * step_y},"
        f"{min_x + (col + 1) * step_x},{min_y + (row + 1) * step_y},EPSG:28992"
        for row in range(4)
        for col in range(4)
    ]


def _download(source: dict[str, str]) -> tuple[dict, int]:
    features_by_id = {}
    for tile_index, tile in enumerate(_tiles(), start=1):
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": source["type_name"],
            "bbox": tile,
            "srsName": "EPSG:4326",
            "outputFormat": "application/json",
            "count": PAGE_SIZE,
        }
        response = requests.get(source["url"], params=params, timeout=(20, 300))
        response.raise_for_status()
        payload = response.json()
        page = payload.get("features", [])
        for feature in page:
            features_by_id[str(feature.get("id") or json.dumps(feature.get("geometry")))] = feature
        print(f"{source['type_name']}: tile {tile_index}/16 -> {len(page)} features", flush=True)
        if len(page) >= PAGE_SIZE:
            print("WARNING: tile reached the PDOK feature cap; inspect before treating as complete", flush=True)
    features = list(features_by_id.values())
    return {"type": "FeatureCollection", "features": features}, len(features)


def _annotate(collection: dict, source_name: str) -> dict:
    for feature in collection["features"]:
        properties = feature.setdefault("properties", {})
        if source_name == "BAG":
            identifier = properties.get("identificatie") or feature.get("id")
            properties.update({
                "building_id": f"AMS-BAG-{identifier}",
                "source_building_id": str(identifier),
                "source": "PDOK_BAG",
                "source_license": "DUTCH_OPEN_DATA_PROVIDER_TERMS",
                "processing_status": "FOOTPRINT_ONLY",
                "data_confidence": "GOVERNMENT_REFERENCE_GEOMETRY_NOT_TITLE_PROOF",
                "floor_count": None,
                "height_m": None,
                "selected_height_source": "UNAVAILABLE",
                "cadastral_boundary_label": "PDOK_CADASTRAL_LAYER_PENDING_MATCH",
            })
        else:
            identifier = properties.get("identificatieLokaalID") or feature.get("id")
            properties.update({
                "parcel_id": f"AMS-KAD-{identifier}",
                "official_parcel_no": str(identifier),
                "parcel_source": "PDOK_KADASTRALE_KAART",
                "source_license": "DUTCH_OPEN_DATA_PROVIDER_TERMS",
                "data_confidence": "GOVERNMENT_REFERENCE_GEOMETRY_NOT_TITLE_PROOF",
            })
    return collection


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    provenance = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "bbox_wgs84": list(BBOX_WGS84),
        "bbox_crs": "EPSG:28992",
        "sources": {},
    }
    for key, source in SOURCES.items():
        if source.get("backup"):
            existing = OUTPUT / source["output"]
            backup = OUTPUT / source["backup"]
            if existing.exists() and not backup.exists():
                shutil.copyfile(existing, backup)
        collection, count = _download(source)
        source_name = "BAG" if key == "buildings" else "KADASTRALE_KAART"
        collection = _annotate(collection, source_name)
        (OUTPUT / source["output"]).write_text(json.dumps(collection), encoding="utf-8")
        provenance["sources"][key] = {
            "url": source["url"],
            "type_name": source["type_name"],
            "count": count,
        }
    (OUTPUT / "pdok_provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(json.dumps(provenance, indent=2))


if __name__ == "__main__":
    main()