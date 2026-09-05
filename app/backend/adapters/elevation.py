"""Cached study-area DEM adapter.

No elevation is synthesized. A real local raster is required before absolute Z
is calculated. OpenTopography acquisition is a single study-area request.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CACHE = ROOT / "data" / "elevation"
OPENTOPOGRAPHY_URL = "https://portal.opentopography.org/API/globaldem"


def _rings(geometry: dict[str, Any]):
    coordinates = geometry.get("coordinates", [])
    if geometry.get("type") == "Polygon":
        return [coordinates[0]] if coordinates else []
    if geometry.get("type") == "MultiPolygon":
        return [polygon[0] for polygon in coordinates if polygon]
    return []


def geometry_center(geometry: dict[str, Any]) -> tuple[float, float]:
    points = [point for ring in _rings(geometry) for point in ring]
    if not points:
        raise ValueError("Building geometry has no polygon coordinates")
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def collection_bounds(features: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    centers = [geometry_center(feature["geometry"]) for feature in features]
    west = min(point[0] for point in centers)
    east = max(point[0] for point in centers)
    south = min(point[1] for point in centers)
    north = max(point[1] for point in centers)
    return west, south, east, north


class ElevationAdapter:
    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir or DEFAULT_CACHE

    def raster_files(self) -> list[Path]:
        if not self.cache_dir.exists():
            return []
        return sorted([*self.cache_dir.glob("*.tif"), *self.cache_dir.glob("*.tiff")])

    def capability(self) -> dict[str, Any]:
        rasters = self.raster_files()
        rasterio_available = importlib.util.find_spec("rasterio") is not None
        if rasters and rasterio_available:
            return {
                "status": "ACTIVE",
                "ground_elevation_status": "GROUND_ELEVATION_AVAILABLE",
                "source": "CACHED_DEM_RASTER",
                "raster": str(rasters[0]),
            }
        detail = "No cached DEM raster is available."
        if rasters and not rasterio_available:
            detail = "A cached DEM exists but rasterio is not installed in this runtime."
        return {
            "status": "PENDING",
            "ground_elevation_status": "GROUND_ELEVATION_PENDING",
            "source": None,
            "detail": detail,
        }

    def acquire_opentopography_dem(
        self,
        bounds: tuple[float, float, float, float],
        destination: Path | None = None,
    ) -> Path:
        """Download one cached SRTM study-area raster using an explicit API key."""

        api_key = os.getenv("OPENTOPOGRAPHY_API_KEY")
        if not api_key:
            raise RuntimeError("OPENTOPOGRAPHY_API_KEY is not configured")
        west, south, east, north = bounds
        params = {
            "demtype": os.getenv("OPENTOPOGRAPHY_DEM_TYPE", "SRTMGL1"),
            "south": south,
            "north": north,
            "west": west,
            "east": east,
            "outputFormat": "GTiff",
            "API_Key": api_key,
        }
        target = destination or self.cache_dir / "opentopography_study_area.tif"
        target.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(f"{OPENTOPOGRAPHY_URL}?{urlencode(params)}", timeout=180) as response:
            payload = response.read()
        if not payload:
            raise RuntimeError("OpenTopography returned an empty response")
        target.write_bytes(payload)
        return target

    def sample(self, features: list[dict[str, Any]]) -> dict[str, float | None]:
        rasters = self.raster_files()
        if not rasters:
            return {str(f["properties"]["building_id"]): None for f in features}
        try:
            import rasterio
            from rasterio.warp import transform
        except ImportError as exc:
            raise RuntimeError("Sampling a DEM requires rasterio") from exc

        points = [geometry_center(feature["geometry"]) for feature in features]
        with rasterio.open(rasters[0]) as dataset:
            sample_points = points
            if dataset.crs and str(dataset.crs).upper() not in {"EPSG:4326", "OGC:CRS84"}:
                xs, ys = transform("EPSG:4326", dataset.crs, [p[0] for p in points], [p[1] for p in points])
                sample_points = list(zip(xs, ys))
            values = list(dataset.sample(sample_points, indexes=1, masked=True))

        result: dict[str, float | None] = {}
        for feature, value in zip(features, values):
            building_id = str(feature["properties"]["building_id"])
            scalar = value[0]
            result[building_id] = None if getattr(scalar, "mask", False) else float(scalar)
        return result

    def enrich(
        self,
        buildings: list[dict[str, Any]],
        floors: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        output_buildings = copy.deepcopy(buildings)
        output_floors = copy.deepcopy(floors)
        capability = self.capability()
        elevations = self.sample(output_buildings) if capability["status"] == "ACTIVE" else {}

        for feature in output_buildings:
            properties = feature.setdefault("properties", {})
            building_id = str(properties.get("building_id"))
            elevation = elevations.get(building_id)
            properties["ground_elevation_m"] = elevation
            properties["ground_elevation_source"] = capability.get("source") if elevation is not None else None
            properties["ground_elevation_confidence"] = "DEM_CELL_SAMPLE" if elevation is not None else None
            properties["ground_elevation_status"] = (
                "GROUND_ELEVATION_AVAILABLE" if elevation is not None else "GROUND_ELEVATION_PENDING"
            )

        by_building = {
            str(feature["properties"]["building_id"]): feature["properties"].get("ground_elevation_m")
            for feature in output_buildings
        }
        for feature in output_floors:
            properties = feature.setdefault("properties", {})
            elevation = by_building.get(str(properties.get("building_id")))
            properties["ground_elevation_m"] = elevation
            properties["ground_elevation_status"] = (
                "GROUND_ELEVATION_AVAILABLE" if elevation is not None else "GROUND_ELEVATION_PENDING"
            )
            if elevation is None:
                properties["absolute_z_min_m"] = None
                properties["absolute_z_max_m"] = None
            else:
                properties["absolute_z_min_m"] = elevation + float(properties["relative_z_min_m"])
                properties["absolute_z_max_m"] = elevation + float(properties["relative_z_max_m"])
        return output_buildings, output_floors


def write_geojson(path: Path, template: dict[str, Any], features: list[dict[str, Any]]) -> None:
    output = dict(template)
    output["features"] = features
    path.write_text(json.dumps(output, separators=(",", ":")), encoding="utf-8")
