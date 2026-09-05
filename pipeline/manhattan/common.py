"""Reproducible Manhattan profile pipeline using official NYC Open Data APIs."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable

import geopandas as gpd
import httpx
from shapely import affinity
from shapely.geometry import box, mapping
from shapely.ops import unary_union

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from profiles.manhattan.config import PROFILE


ROOT = REPOSITORY_ROOT
PROFILE_DIR = ROOT / "data" / "profiles" / "manhattan"
RAW_DIR = PROFILE_DIR / "raw"
BUILDING_URL = "https://data.cityofnewyork.us/resource/5zhs-2jue.geojson"
TAX_LOT_URL = "https://data.cityofnewyork.us/resource/i38t-6if2.geojson"
PLUTO_URL = "https://data.cityofnewyork.us/resource/64uk-42ks.json"
SOURCE_CRS = "EPSG:4326"
METRIC_CRS = "EPSG:32618"
FEET_TO_METERS = 0.3048
UID_VERSION = "P3DU-V1"


def _ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_sanitize_json(value), indent=2, default=_json_default, allow_nan=False),
        encoding="utf-8",
    )


def _json_default(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_json(item) for item in value]
    if hasattr(value, "item"):
        return _sanitize_json(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _bbox_where() -> str:
    south, west, north, east = PROFILE.bbox
    return f"within_box(the_geom,{north},{west},{south},{east})"


def _get_json(url: str, params: dict[str, Any]) -> Any:
    with httpx.Client(timeout=90, follow_redirects=True) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def _feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def download_tax_lots() -> dict[str, Any]:
    """Download compact official tax-lot geometry plus matching PLUTO attributes."""

    _ensure_dirs()
    collection = _get_json(TAX_LOT_URL, {"$limit": 5000, "$where": _bbox_where()})
    _write_json(RAW_DIR / "tax_lots.geojson", collection)

    bbls = sorted({
        str(feature.get("properties", {}).get("bbl", "")).split(".")[0]
        for feature in collection.get("features", [])
        if feature.get("properties", {}).get("bbl")
    })
    rows: list[dict[str, Any]] = []
    for start in range(0, len(bbls), 40):
        chunk = bbls[start:start + 40]
        where = "bbl in (" + ",".join(chunk) + ")"
        rows.extend(_get_json(PLUTO_URL, {"$limit": 5000, "$where": where}))
    _write_json(RAW_DIR / "pluto_attributes.json", rows)
    return {"tax_lots": len(collection.get("features", [])), "pluto_rows": len(rows)}


def download_buildings() -> dict[str, Any]:
    """Download official current building footprints for the configured bounding box."""

    _ensure_dirs()
    collection = _get_json(BUILDING_URL, {"$limit": 5000, "$where": _bbox_where()})
    features = [
        feature for feature in collection.get("features", [])
        if feature.get("geometry") and feature.get("properties", {}).get("last_status_type") != "Demolition"
    ]
    result = _feature_collection(features)
    _write_json(RAW_DIR / "buildings.geojson", result)
    return {"buildings": len(features)}


def _as_number(value: Any, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    number = _as_number(value)
    return int(round(number)) if number is not None else default


def _bbl(value: Any) -> str:
    raw = str(value or "").split(".")[0]
    return raw.zfill(10) if raw else ""


def _confidence_label(score: float) -> str:
    if score >= 85:
        return "VERY GOOD ESTIMATE"
    if score >= 70:
        return "GOOD ESTIMATE"
    if score >= 50:
        return "MODERATE ESTIMATE"
    if score >= 30:
        return "LOW CONFIDENCE"
    return "UNRELIABLE"


def _valid_geodata(path: Path) -> gpd.GeoDataFrame:
    frame = gpd.read_file(path).to_crs(SOURCE_CRS)
    frame = frame[frame.geometry.notna() & ~frame.geometry.is_empty].copy()
    frame.geometry = frame.geometry.make_valid()
    return frame


def match_buildings_taxlots() -> dict[str, Any]:
    """Match each footprint to the tax lot with maximum metric intersection."""

    buildings = _valid_geodata(RAW_DIR / "buildings.geojson")
    lots = _valid_geodata(RAW_DIR / "tax_lots.geojson")
    buildings_metric = buildings.to_crs(METRIC_CRS)
    lots_metric = lots.to_crs(METRIC_CRS)

    matches: list[dict[str, Any]] = []
    for building_index, building in buildings_metric.iterrows():
        geometry = building.geometry
        candidate_indexes = list(lots_metric.sindex.query(geometry, predicate="intersects"))
        best_index = None
        best_area = 0.0
        for lot_index in candidate_indexes:
            area = geometry.intersection(lots_metric.iloc[lot_index].geometry).area
            if area > best_area:
                best_index = lots_metric.index[lot_index]
                best_area = area
        if best_index is None or best_area <= 0:
            continue
        lot = lots_metric.loc[best_index]
        building_area = float(geometry.area)
        lot_area = float(lot.geometry.area)
        coverage = 100.0 * best_area / building_area if building_area else 0.0
        occupation = 100.0 * best_area / lot_area if lot_area else 0.0
        source = buildings.loc[building_index]
        source_bbl = _bbl(source.get("base_bbl") or source.get("mappluto_bbl"))
        tax_bbl = _bbl(lot.get("bbl"))
        matches.append({
            "source_index": int(building_index),
            "source_building_id": str(source.get("bin") or source.get("doitt_id") or building_index),
            "source_doitt_id": str(source.get("doitt_id") or ""),
            "tax_lot_id": tax_bbl,
            "borough": "Manhattan",
            "block": _as_int(lot.get("block")),
            "lot": _as_int(lot.get("lot")),
            "building_area_m2": round(building_area, 3),
            "tax_lot_area_m2": round(lot_area, 3),
            "intersection_area_m2": round(best_area, 3),
            "building_covered_by_lot_pct": round(coverage, 3),
            "lot_occupied_by_building_pct": round(occupation, 3),
            "source_bbl_matches_tax_lot": source_bbl == tax_bbl,
        })

    matches.sort(key=lambda row: (row["source_building_id"], row["source_doitt_id"]))
    lot_counts: dict[str, int] = {}
    for row in matches:
        lot_counts[row["tax_lot_id"]] = lot_counts.get(row["tax_lot_id"], 0) + 1
    features: list[dict[str, Any]] = []
    for sequence, row in enumerate(matches, start=1):
        count = lot_counts[row["tax_lot_id"]]
        coverage = row["building_covered_by_lot_pct"]
        occupation = row["lot_occupied_by_building_pct"]
        score = 0.70 * min(100.0, coverage)
        score += 0.15 * min(100.0, occupation * 2.0)
        score += 10.0 if row["source_bbl_matches_tax_lot"] else 0.0
        score += 5.0 / math.sqrt(count)
        score = round(min(100.0, score), 1)
        source_feature = buildings.loc[row.pop("source_index")]
        properties = {key: value for key, value in source_feature.items() if key != "geometry"}
        properties.update(row)
        properties.update({
            "profile_id": "manhattan",
            "building_id": f"NYC-B{sequence:03d}",
            "buildings_per_lot": count,
            "match_confidence_score": score,
            "match_confidence_label": _confidence_label(score),
            "match_confidence_type": "GEOMETRIC_MATCH_CONFIDENCE",
            "legal_status": "NOT_A_LEGAL_DETERMINATION",
        })
        features.append({"type": "Feature", "geometry": mapping(source_feature.geometry), "properties": properties})
    output = _feature_collection(features)
    _write_json(PROFILE_DIR / "building_lot_matches.geojson", output)
    return {"matched_buildings": len(features), "tax_lots_used": len(lot_counts)}


def _pluto_index() -> dict[str, dict[str, Any]]:
    return {_bbl(row.get("bbl")): row for row in _read_json(RAW_DIR / "pluto_attributes.json")}


def enrich_buildings() -> dict[str, Any]:
    """Attach source-derived height, elevation, floor and unit-count metadata."""

    collection = _read_json(PROFILE_DIR / "building_lot_matches.geojson")
    pluto = _pluto_index()
    enriched: list[dict[str, Any]] = []
    for feature in collection.get("features", []):
        properties = dict(feature.get("properties", {}))
        lot = pluto.get(_bbl(properties.get("tax_lot_id")), {})
        height_feet = _as_number(properties.get("height_roof"))
        ground_feet = _as_number(properties.get("ground_elevation"))
        height_m = height_feet * FEET_TO_METERS if height_feet and height_feet > 0 else None
        ground_m = ground_feet * FEET_TO_METERS if ground_feet is not None else None
        lot_floors = _as_number(lot.get("numfloors"), 0) or 0
        lot_buildings = _as_int(lot.get("numbldgs"), properties.get("buildings_per_lot", 1))
        if lot_floors > 0 and lot_buildings == 1:
            floor_count = max(1, int(round(lot_floors)))
            floor_source = "NYC_DCP_PLUTO_NUMFLOORS"
            floor_estimated = False
            floor_confidence = "HIGH"
        elif height_m:
            floor_count = max(1, int(round(height_m / 3.2)))
            floor_source = "ESTIMATED_FROM_NYC_HEIGHT_ROOF"
            floor_estimated = True
            floor_confidence = "MEDIUM"
        elif lot_floors > 0:
            floor_count = max(1, int(round(lot_floors)))
            floor_source = "NYC_DCP_PLUTO_LOT_LEVEL_NUMFLOORS"
            floor_estimated = True
            floor_confidence = "LOW"
        else:
            floor_count = 0
            floor_source = "NOT_AVAILABLE"
            floor_estimated = False
            floor_confidence = "NOT_AVAILABLE"
        if height_m is None and floor_count:
            height_m = floor_count * 3.2
            height_source = "ESTIMATED_FROM_FLOOR_COUNT"
            height_estimated = True
            height_confidence = "LOW"
        else:
            height_source = "NYC_OTI_BUILDING_FOOTPRINT_HEIGHT_ROOF" if height_m else "NOT_AVAILABLE"
            height_estimated = False
            height_confidence = "HIGH" if str(properties.get("geom_source", "")).lower() == "photogrammetric" else "MEDIUM"

        unit_total = _as_int(lot.get("unitstotal"))
        residential_units = _as_int(lot.get("unitsres"))
        basement_code = str(lot.get("bsmtcode") or "").strip() or None
        properties.update({
            "tax_lot_source": "NYC_DOF_DIGITAL_TAX_MAP",
            "tax_lot_source_dataset": "i38t-6if2",
            "building_geometry_source": "NYC_OTI_BUILDING_FOOTPRINTS",
            "building_source_dataset": "5zhs-2jue",
            "attribute_source": "NYC_DCP_PLUTO",
            "attribute_source_dataset": "64uk-42ks",
            "address": lot.get("address"),
            "building_class": lot.get("bldgclass"),
            "land_use": lot.get("landuse"),
            "year_built": _as_int(lot.get("yearbuilt")) or _as_int(properties.get("construction_year")),
            "lot_floor_count": lot_floors or None,
            "lot_building_count": lot_buildings,
            "residential_units_source_count": residential_units,
            "total_units_source_count": unit_total,
            "basement_type_code": basement_code,
            "basement_type_source": "NYC_DCP_PLUTO_BSMTCODE" if basement_code is not None else "NOT_AVAILABLE",
            "height_m": round(height_m, 3) if height_m is not None else None,
            "selected_height_m": round(height_m, 3) if height_m is not None else None,
            "selected_height_source": height_source,
            "selected_height_confidence": height_confidence,
            "selected_height_is_estimated": height_estimated,
            "floor_count": floor_count,
            "floor_count_source": floor_source,
            "floor_count_is_estimated": floor_estimated,
            "floor_count_confidence": floor_confidence,
            "ground_elevation_m": round(ground_m, 3) if ground_m is not None else None,
            "ground_elevation_source": "NYC_OTI_BUILDING_FOOTPRINT_GROUND_ELEVATION" if ground_m is not None else None,
            "ground_elevation_confidence": "MEDIUM" if ground_m is not None else "NOT_AVAILABLE",
            "ground_elevation_status": "SOURCE_ATTRIBUTE_AVAILABLE" if ground_m is not None else "GROUND_ELEVATION_PENDING",
            "vertical_reference": "ABSOLUTE_Z_SOURCE_ATTRIBUTE" if ground_m is not None else "RELATIVE_Z_ONLY",
            "processing_status": "FULL_VERTICAL_MODEL" if floor_count else "FOOTPRINT_ONLY",
            "unit_geometry_mode": "SYNTHETIC_UNIT_DEMO" if floor_count else "NOT_AVAILABLE",
        })
        enriched.append({**feature, "properties": properties})
    _write_json(PROFILE_DIR / "buildings.geojson", _feature_collection(enriched))

    lot_collection = _read_json(RAW_DIR / "tax_lots.geojson")
    output_lots = []
    for feature in lot_collection.get("features", []):
        properties = dict(feature.get("properties", {}))
        bbl = _bbl(properties.get("bbl"))
        lot = pluto.get(bbl, {})
        properties.update({
            "profile_id": "manhattan",
            "tax_lot_id": bbl,
            "source_lot_id": bbl,
            "borough": "Manhattan",
            "block": _as_int(properties.get("block")),
            "lot": _as_int(properties.get("lot")),
            "address": lot.get("address"),
            "tax_lot_source": "NYC_DOF_DIGITAL_TAX_MAP",
            "attribute_source": "NYC_DCP_PLUTO",
        })
        output_lots.append({**feature, "properties": properties})
    _write_json(PROFILE_DIR / "tax_lots.geojson", _feature_collection(output_lots))
    return {"enriched_buildings": len(enriched), "tax_lots": len(output_lots)}


def generate_floors() -> dict[str, Any]:
    buildings = _read_json(PROFILE_DIR / "buildings.geojson")
    floors: list[dict[str, Any]] = []
    for building in buildings.get("features", []):
        properties = building.get("properties", {})
        count = _as_int(properties.get("floor_count"))
        height = _as_number(properties.get("selected_height_m"))
        if count <= 0 or not height or height <= 0:
            continue
        floor_height = height / count
        area = _as_number(properties.get("building_area_m2"), 0.0) or 0.0
        ground = _as_number(properties.get("ground_elevation_m"))
        for number in range(1, count + 1):
            z_min = (number - 1) * floor_height
            z_max = number * floor_height
            prototype_id = f"P3DF-NYC-{properties['tax_lot_id']}-{properties['building_id']}-F{number:03d}"
            floor_properties = {
                "profile_id": "manhattan",
                "building_id": properties["building_id"],
                "source_building_id": properties.get("source_building_id"),
                "tax_lot_id": properties.get("tax_lot_id"),
                "floor_id": f"{properties['building_id']}-F{number:03d}",
                "floor_number": number,
                "floor_count_source": properties.get("floor_count_source"),
                "floor_count_is_estimated": properties.get("floor_count_is_estimated"),
                "floor_count_confidence": properties.get("floor_count_confidence"),
                "relative_z_min_m": round(z_min, 3),
                "relative_z_max_m": round(z_max, 3),
                "absolute_z_min_m": round(ground + z_min, 3) if ground is not None else None,
                "absolute_z_max_m": round(ground + z_max, 3) if ground is not None else None,
                "floor_height_m": round(floor_height, 3),
                "footprint_area_m2": round(area, 3),
                "floor_area_m2": round(area, 3),
                "volume_m3": round(area * floor_height, 3),
                "prototype_id": prototype_id,
                "prototype_uid_type": "PROTOTYPE_3D_VERTICAL_ID",
                "prototype_uid_is_official": False,
                "ulpin_is_official": False,
                "geometry_source": "NYC_OTI_BUILDING_FOOTPRINTS",
            }
            floors.append({"type": "Feature", "geometry": building["geometry"], "properties": floor_properties})
    _write_json(PROFILE_DIR / "floors.geojson", _feature_collection(floors))
    return {"floors": len(floors), "buildings_with_floors": len({f["properties"]["building_id"] for f in floors})}


def _polygonal(value):
    if value.is_empty:
        return None
    if value.geom_type in {"Polygon", "MultiPolygon"}:
        return value
    polygons = [item for item in getattr(value, "geoms", []) if item.geom_type in {"Polygon", "MultiPolygon"}]
    return unary_union(polygons) if polygons else None


def synthetic_layout(geometry, requested_units: int) -> list[Any]:
    """Deterministically slice a footprint along its longest oriented axis."""

    unit_count = max(1, min(8, int(requested_units)))
    rectangle = geometry.minimum_rotated_rectangle
    coords = list(rectangle.exterior.coords)[:4]
    edges = []
    for first, second in zip(coords, coords[1:] + coords[:1]):
        dx, dy = second[0] - first[0], second[1] - first[1]
        edges.append((dx * dx + dy * dy, math.degrees(math.atan2(dy, dx))))
    angle = max(edges)[1]
    rotated = affinity.rotate(geometry, -angle, origin="centroid")
    min_x, min_y, max_x, max_y = rotated.bounds
    width = max_x - min_x
    slices = []
    for index in range(unit_count):
        x0 = min_x + width * index / unit_count
        x1 = min_x + width * (index + 1) / unit_count
        padding = max(width, max_y - min_y, 1.0)
        clipped = _polygonal(rotated.intersection(box(x0, min_y - padding, x1, max_y + padding)))
        if clipped is not None and clipped.area > 0.05:
            slices.append(affinity.rotate(clipped, angle, origin=geometry.centroid))
    return slices


def _units_per_floor(properties: dict[str, Any]) -> tuple[int, str]:
    floors = max(1, _as_int(properties.get("floor_count"), 1))
    residential = _as_int(properties.get("residential_units_source_count"))
    total = _as_int(properties.get("total_units_source_count"))
    if residential > 0:
        return max(1, min(8, math.ceil(residential / floors))), "PLUTO_RESIDENTIAL_UNITS_RATIO"
    if total > 1:
        return max(1, min(8, math.ceil(total / floors))), "PLUTO_TOTAL_UNITS_RATIO"
    return 4, "SYNTHETIC_DEMO_DEFAULT"


def _unit_uid(properties: dict[str, Any], floor: int, unit: int) -> tuple[str, list[str]]:
    fields = [
        "manhattan", str(properties.get("tax_lot_id")), str(properties.get("building_id")),
        f"{floor:03d}", f"{unit:03d}", UID_VERSION,
    ]
    digest = hashlib.sha256("|".join(fields).encode("utf-8")).hexdigest()[:8].upper()
    block = _as_int(properties.get("block"))
    lot = _as_int(properties.get("lot"))
    uid = f"P3DU-NYC-{block:05d}-{lot:04d}-{properties['building_id']}-F{floor:03d}-U{unit:03d}-{digest}"
    return uid, fields


def generate_units() -> dict[str, Any]:
    buildings = _valid_geodata(PROFILE_DIR / "buildings.geojson")
    buildings_metric = buildings.to_crs(METRIC_CRS)
    floors = _read_json(PROFILE_DIR / "floors.geojson").get("features", [])
    floor_index = {(f["properties"]["building_id"], _as_int(f["properties"]["floor_number"])): f for f in floors}
    units: list[dict[str, Any]] = []
    for index, building in buildings_metric.iterrows():
        properties = {key: value for key, value in buildings.loc[index].items() if key != "geometry"}
        floor_count = _as_int(properties.get("floor_count"))
        if floor_count <= 0:
            continue
        count, basis = _units_per_floor(properties)
        layout = synthetic_layout(building.geometry, count)
        for floor_number in range(1, floor_count + 1):
            floor = floor_index[(properties["building_id"], floor_number)]["properties"]
            for unit_number, unit_geometry in enumerate(layout, start=1):
                uid, fields = _unit_uid(properties, floor_number, unit_number)
                area = float(unit_geometry.area)
                height = float(floor["floor_height_m"])
                source_geometry = gpd.GeoSeries([unit_geometry], crs=METRIC_CRS).to_crs(SOURCE_CRS).iloc[0]
                unit_properties = {
                    "profile_id": "manhattan",
                    "unit_id": f"{properties['building_id']}-F{floor_number:03d}-U{unit_number:03d}",
                    "unit_label": f"F{floor_number:03d}-U{unit_number:03d}",
                    "floor_number": floor_number,
                    "floor_id": floor["floor_id"],
                    "building_id": properties["building_id"],
                    "tax_lot_id": properties.get("tax_lot_id"),
                    "unit_count_basis": basis,
                    "unit_geometry_source": "SYNTHETIC_SUBDIVISION",
                    "unit_identifier_source": "PROTOTYPE_GENERATED",
                    "unit_geometry_is_synthetic": True,
                    "synthetic_layout_confidence": "DEMO_ONLY",
                    "ownership_status": "NOT_AVAILABLE",
                    "legal_status": "NOT_AVAILABLE",
                    "unit_area_m2": round(area, 3),
                    "unit_volume_m3": round(area * height, 3),
                    "relative_z_min_m": floor["relative_z_min_m"],
                    "relative_z_max_m": floor["relative_z_max_m"],
                    "absolute_z_min_m": floor["absolute_z_min_m"],
                    "absolute_z_max_m": floor["absolute_z_max_m"],
                    "prototype_unit_uid": uid,
                    "prototype_uid_type": "PROTOTYPE_VERTICAL_UNIT_ID",
                    "prototype_uid_is_official": False,
                    "uid_algorithm_version": UID_VERSION,
                    "uid_source_fields": fields,
                }
                units.append({"type": "Feature", "geometry": mapping(source_geometry), "properties": unit_properties})
    _write_json(PROFILE_DIR / "units.geojson", _feature_collection(units))
    return {"units": len(units), "buildings_with_units": len({u["properties"]["building_id"] for u in units})}


def validate_vertical_ids() -> dict[str, Any]:
    buildings = _read_json(PROFILE_DIR / "buildings.geojson").get("features", [])
    floors = _read_json(PROFILE_DIR / "floors.geojson").get("features", [])
    units = _read_json(PROFILE_DIR / "units.geojson").get("features", [])
    floor_ids = [item["properties"]["prototype_id"] for item in floors]
    unit_ids = [item["properties"]["prototype_unit_uid"] for item in units]
    if len(floor_ids) != len(set(floor_ids)):
        raise RuntimeError("Duplicate Manhattan floor prototype IDs detected")
    if len(unit_ids) != len(set(unit_ids)):
        raise RuntimeError("Duplicate Manhattan unit prototype UIDs detected")
    vertical = [item for item in buildings if _as_int(item["properties"].get("floor_count")) > 0]
    heroes = sorted(
        vertical,
        key=lambda item: (
            _as_number(item["properties"].get("selected_height_m"), 0.0) or 0.0,
            _as_number(item["properties"].get("match_confidence_score"), 0.0) or 0.0,
        ),
        reverse=True,
    )[:3]
    summary = {
        "profile_id": "manhattan",
        "label": "Manhattan",
        "study_area": PROFILE.study_area,
        "bbox": list(PROFILE.bbox),
        "center": list(PROFILE.center),
        "map_zoom": PROFILE.map_zoom,
        "default_hero": heroes[0]["properties"]["building_id"] if heroes else None,
        "hero_buildings": [item["properties"]["building_id"] for item in heroes],
        "counts": {
            "buildings": len(buildings),
            "tax_lots": len(_read_json(PROFILE_DIR / "tax_lots.geojson").get("features", [])),
            "floors": len(floors),
            "units": len(units),
            "vertical_buildings": len(vertical),
        },
        "unit_geometry_mode": "SYNTHETIC_UNIT_DEMO",
        "prototype_uids_are_official": False,
    }
    _write_json(PROFILE_DIR / "profile.json", summary)
    return summary


def _group_by(items: Iterable[dict[str, Any]], key: str) -> dict[Any, list[dict[str, Any]]]:
    grouped: dict[Any, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(item["properties"].get(key), []).append(item)
    return grouped


def validate_topology() -> dict[str, Any]:
    buildings = _valid_geodata(PROFILE_DIR / "buildings.geojson").to_crs(METRIC_CRS)
    units = _valid_geodata(PROFILE_DIR / "units.geojson").to_crs(METRIC_CRS)
    building_index = {row["building_id"]: row.geometry for _, row in buildings.iterrows()}
    records = [
        {"geometry": row.geometry, "properties": {key: value for key, value in row.items() if key != "geometry"}}
        for _, row in units.iterrows()
    ]
    issues: list[dict[str, Any]] = []
    uid_values = [item["properties"].get("prototype_unit_uid") for item in records]
    if len(uid_values) != len(set(uid_values)):
        issues.append({"issue_class": "GEOMETRIC_CONFLICT", "issue_type": "DUPLICATE_UNIT_UID", "severity": "ERROR"})
    for item in records:
        properties = item["properties"]
        geometry = item["geometry"]
        building_geometry = building_index.get(properties.get("building_id"))
        if building_geometry is None or geometry.difference(building_geometry).area > 0.02:
            issues.append({"issue_class": "GEOMETRIC_CONFLICT", "issue_type": "UNIT_OUTSIDE_BUILDING", "severity": "ERROR", "unit_id": properties.get("unit_id")})
        if float(properties.get("relative_z_max_m", 0)) <= float(properties.get("relative_z_min_m", 0)):
            issues.append({"issue_class": "GEOMETRIC_CONFLICT", "issue_type": "INVALID_UNIT_Z", "severity": "ERROR", "unit_id": properties.get("unit_id")})
        if geometry.area <= 0.05:
            issues.append({"issue_class": "GEOMETRIC_CONFLICT", "issue_type": "ZERO_UNIT_AREA", "severity": "ERROR", "unit_id": properties.get("unit_id")})
    for floor_key, floor_units in _group_by(records, "floor_id").items():
        for first, second in combinations(floor_units, 2):
            overlap = first["geometry"].intersection(second["geometry"]).area
            if overlap > 0.02:
                issues.append({
                    "issue_class": "GEOMETRIC_CONFLICT", "issue_type": "UNIT_XY_OVERLAP",
                    "severity": "ERROR", "floor_id": floor_key,
                    "unit_id_1": first["properties"].get("unit_id"),
                    "unit_id_2": second["properties"].get("unit_id"),
                    "horizontal_overlap_m2": round(overlap, 4),
                })
    result = {
        "profile_id": "manhattan",
        "units_checked": len(records),
        "topology_errors": sum(item.get("severity") == "ERROR" for item in issues),
        "topology_warnings": sum(item.get("severity") == "WARNING" for item in issues),
        "issues": issues,
        "legal_status": "NOT_A_LEGAL_DETERMINATION",
    }
    _write_json(PROFILE_DIR / "topology_issues.json", result)
    return result
