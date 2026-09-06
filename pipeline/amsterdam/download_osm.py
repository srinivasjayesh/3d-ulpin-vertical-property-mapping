"""Download public OSM context for the Amsterdam benchmark profile.

This creates local demo artifacts only. OSM buildings are contextual reference
geometry, not cadastral parcels or legal property boundaries.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from shapely.geometry import LineString, Polygon, mapping


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data" / "profiles" / "amsterdam"
BBOX = (52.358, 4.865, 52.392, 4.925)
ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)


def _collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def _height(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("m", "")
    try:
        result = float(text)
    except ValueError:
        return None
    return result if result > 0 else None


def _levels(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text.isdigit():
        return None
    result = int(text)
    return result if result > 0 else None


def _download() -> tuple[dict, str]:
    south, west, north, east = BBOX
    query = (
        f"[out:json][timeout:180];"
        f"(way[building]({south},{west},{north},{east});"
        f"way[\"building:part\"]({south},{west},{north},{east});"
        f"way[highway]({south},{west},{north},{east}););out body geom;"
    )
    for endpoint in ENDPOINTS:
        try:
            response = requests.get(
                endpoint,
                params={"data": query},
                headers={"User-Agent": "ULPIN-research-prototype/1.0"},
                timeout=(15, 240),
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("remark"):
                raise RuntimeError(payload["remark"])
            return payload, endpoint
        except Exception as exc:
            print(f"OSM endpoint failed: {endpoint}: {exc}")
    raise RuntimeError("All OSM Overpass endpoints failed")


def main() -> None:
    payload, endpoint = _download()
    buildings = []
    roads = []
    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        points = [(node["lon"], node["lat"]) for node in element.get("geometry", [])]
        if len(points) < 2:
            continue
        if "building" in tags or "building:part" in tags:
            if points[0] != points[-1] or len(points) < 4:
                continue
            geometry = Polygon(points)
            if geometry.is_empty or not geometry.is_valid:
                continue
            levels = _levels(tags.get("building:levels"))
            height = _height(tags.get("height"))
            buildings.append({
                "type": "Feature",
                "geometry": mapping(geometry),
                "properties": {
                    "building_id": f"AMS-OSM-{element['id']}",
                    "source_building_id": str(element["id"]),
                    "source": "OPENSTREETMAP",
                    "source_license": "ODbL-1.0",
                    "source_tags": tags,
                    "height_m": height,
                    "selected_height_m": height,
                    "selected_height_source": "OSM_HEIGHT" if height else "UNAVAILABLE",
                    "selected_height_is_estimated": height is not None,
                    "floor_count": levels,
                    "floor_count_source": "OSM_BUILDING_LEVELS" if levels else "UNAVAILABLE",
                    "floor_count_is_estimated": False,
                    "processing_status": "VERTICAL_CONTEXT" if height and levels else "FOOTPRINT_ONLY",
                    "data_confidence": "PUBLIC_REFERENCE_NOT_SURVEYED",
                    "cadastral_boundary_label": "NOT_LOADED",
                },
            })
        elif "highway" in tags:
            line = LineString(points)
            if not line.is_empty and line.is_valid:
                roads.append({
                    "type": "Feature",
                    "geometry": mapping(line),
                    "properties": {
                        "road_id": f"AMS-OSM-{element['id']}",
                        "source": "OPENSTREETMAP",
                        "source_license": "ODbL-1.0",
                        "highway": tags.get("highway"),
                        "name": tags.get("name"),
                    },
                })

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "buildings.geojson").write_text(json.dumps(_collection(buildings)), encoding="utf-8")
    (OUTPUT / "roads.geojson").write_text(json.dumps(_collection(roads)), encoding="utf-8")
    provenance = {
        "source": "OpenStreetMap contributors",
        "license": "ODbL-1.0",
        "endpoint": endpoint,
        "bbox": list(BBOX),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "building_count": len(buildings),
        "road_count": len(roads),
        "limitations": [
            "OSM buildings are not authoritative cadastral boundaries.",
            "No apartment units, ownership, parcels, or legal heights are inferred.",
        ],
    }
    (OUTPUT / "osm_provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(json.dumps(provenance, indent=2))


if __name__ == "__main__":
    main()