"""Build source-constrained G/South Mumbai artifacts and measured footprint agreement.

Only explicit OSM heights are extruded. Floor strata require both height and
level evidence and are clearly source-derived, NOT surveyed floor boundaries.
BMC HEIGHT is retained raw; its attribute units are undocumented.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
from pyproj import Transformer
from shapely.geometry import LineString, Polygon, shape, mapping
from shapely.ops import transform
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/profiles/mumbai"
RAW = OUT / "raw/ward_review"
WARD_CODE = "G/S"
WARD_LABEL = "G/South"
UID_VERSION = "MUM02_SOURCE_STRATA"
BMC_SOURCE = "https://prsrvgisapp.mcgm.gov.in/server/rest/services/mcgm/MCGMGIS_Departments_Master_All_Layers/MapServer/283"
PROJECT = Transformer.from_crs(4326, 32643, always_xy=True).transform

def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

def _collection(features): return {"type": "FeatureCollection", "features": features}
def _feature(geometry, properties): return {"type": "Feature", "geometry": mapping(geometry), "properties": properties}

def _levels(tags):
    value = str(tags.get("building:levels", "")).strip()
    if not re.fullmatch(r"\d+(?:\.0+)?", value): return None
    count = int(float(value))
    return count if 0 < count <= 300 else None

def height_metres(value):
    if value is None: return None
    value = str(value).strip().lower()
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(m|metres|meters|ft|feet|')?", value)
    if not match: return None
    result = float(match[1]) * (0.3048 if match[2] in ("ft", "feet", "'") else 1)
    return result if result > 0 else None

def reference_index():
    raw = json.loads((RAW / "bmc_buildings_gs.geojson").read_text(encoding="utf-8"))
    refs, geometries = [], []
    for f in raw["features"]:
        g = shape(f["geometry"])
        if g.is_empty or not g.is_valid: continue
        refs.append(f); geometries.append(transform(PROJECT, g))
    return refs, geometries, STRtree(geometries)

def agreement(geometry, refs, geometries, tree):
    metric = transform(PROJECT, geometry)
    matches = []
    for index in tree.query(metric, predicate="intersects"):
        reference = geometries[index]
        intersection = metric.intersection(reference).area
        if intersection <= 0: continue
        union = metric.area + reference.area - intersection
        matches.append((intersection / union, int(index), intersection))
    matches.sort(reverse=True)
    if not matches:
        return {"footprint_agreement_pct": None, "footprint_agreement_status": "NO_OVERLAPPING_REFERENCE",
                "geometry_confidence_score": None, "geometry_confidence_reason": "No overlapping BMC reference footprint. No survey-confidence score can be inferred."}
    iou, index, area = matches[0]
    attrs = refs[index]["properties"]
    return {
        "footprint_agreement_pct": round(iou * 100, 2),
        "footprint_agreement_status": "MEASURED_CROSS_SOURCE_OVERLAP",
        "footprint_agreement_method": "100 * intersection_area / union_area; EPSG:32643",
        "reference_building_id": str(attrs["OBJECTID"]),
        "reference_building_source": "BMC_BUILDING_LAYER_283",
        "reference_source_url": BMC_SOURCE,
        "reference_building_name": attrs.get("NAME"),
        "reference_floor_description": attrs.get("NO_OF_FLOO"),
        "reference_height_raw": attrs.get("HEIGHT"),
        "reference_height_units": "UNDOCUMENTED_NOT_USED",
        "overlapping_reference_count": len(matches),
        "next_best_agreement_pct": round(matches[1][0] * 100, 2) if len(matches) > 1 else None,
        "geometry_confidence_score": None,
        "geometry_confidence_reason": "Measured footprint agreement is not positional accuracy, cadastral confidence or a verified building identity.",
    }

def build():
    ward = next(f for f in json.loads((RAW / "wards.geojson").read_text(encoding="utf-8"))["features"] if f["properties"]["NAME"] == WARD_CODE)
    ward_geom = shape(ward["geometry"])
    osm = json.loads((RAW / "osm_gs.json").read_text(encoding="utf-8"))
    refs, reference_geometries, tree = reference_index()
    buildings, floors, roads, issues = [], [], [], []
    seen = set()
    for element in osm.get("elements", []):
        tags = element.get("tags", {}) or {}
        points = [(p["lon"], p["lat"]) for p in element.get("geometry", []) if "lon" in p and "lat" in p]
        osm_id = element.get("id")
        if (tags.get("building") or tags.get("building:part")) and len(points) >= 4 and points[0] == points[-1]:
            geometry = Polygon(points)
            if geometry.is_empty or not geometry.is_valid:
                issues.append({"source": f"OSM_way_{osm_id}", "issue": "INVALID_SOURCE_FOOTPRINT_EXCLUDED"})
                continue
            if not ward_geom.covers(geometry.representative_point()) or osm_id in seen: continue
            seen.add(osm_id)
            building_id = f"MUM-GS-OSM-{osm_id}"
            levels = _levels(tags)
            height = height_metres(tags.get("height"))
            roof = height_metres(tags.get("roof:height")) or 0
            raised = tags.get("min_height") not in (None, "0", "0.0") or tags.get("building:min_level") not in (None, "0", "0.0")
            raw_height = height
            if raised:
                # Do not assume where a building part begins when vertical base is uncertain.
                height = None
            usable = bool(height and levels and height > roof)
            source_note = "SOURCE_HEIGHT_AND_LEVELS" if usable else "NO_COMPLETE_VERTICAL_EVIDENCE"
            if usable and not 2 <= (height-roof) / levels <= 8:
                usable = False
                source_note = "HEIGHT_LEVEL_TAGS_REQUIRE_REVIEW"
            area = transform(PROJECT, geometry).area
            props = {
                "profile_id": "mumbai", "building_id": building_id, "source_building_id": f"OSM_way_{osm_id}",
                "source_url": f"https://www.openstreetmap.org/way/{osm_id}", "source_version": element.get("version"),
                "source_updated_at": element.get("timestamp"), "source_tags": tags,
                "name": tags.get("name") or tags.get("addr:housename") or "",
                "address": " ".join(str(tags[k]) for k in ("addr:housenumber", "addr:street") if tags.get(k)),
                "building": tags.get("building") or tags.get("building:part"),
                "source_geometry_kind": "BUILDING_PART" if tags.get("building:part") else "BUILDING",
                "floor_count": levels, "floor_count_source": "OSM_BUILDING_LEVELS" if levels else "NO_VERTICAL_ATTRIBUTE",
                "floor_count_is_estimated": False,
                "selected_height_m": height, "source_height_m": raw_height,
                "selected_height_source": "OSM_HEIGHT_TAG" if height else "HEIGHT_NOT_AVAILABLE_FOR_RENDERING",
                "building_geometry_source": "OPENSTREETMAP_BUILDING",
                "processing_status": "VERTICAL_3D_PARTIAL" if height else "CONTEXT_ONLY",
                "vertical_evidence_status": source_note, "footprint_area_m2": round(area, 3),
                "floor_model_available": usable,
                "ground_elevation_status": "GROUND_ELEVATION_PENDING", "vertical_reference": "RELATIVE_Z_ONLY",
                "unit_geometry_mode": "NOT_AVAILABLE", "public_floor_plan_status": "NOT_AVAILABLE_IN_SNAPSHOT",
                "basement_evidence_status": "NOT_VERIFIED_NO_GEOMETRY", "basement_count": None,
                "ward_name": WARD_CODE, "ward_label": WARD_LABEL, "ward_source": "MCGM_WARDS_DP_OFFICIAL",
                "cadastral_confidence_score": None,
                **agreement(geometry, refs, reference_geometries, tree),
            }
            buildings.append(_feature(geometry, props))
            if usable:
                step = (height-roof) / levels
                for number in range(1, levels+1):
                    digest = hashlib.sha1(f"{building_id}|{number}|{UID_VERSION}".encode()).hexdigest()[:12].upper()
                    floors.append(_feature(geometry, {
                        "profile_id": "mumbai", "building_id": building_id, "floor_number": number,
                        "floor_height_m": step, "relative_z_min_m": (number-1)*step,
                        "relative_z_max_m": number*step, "absolute_z_min_m": None, "absolute_z_max_m": None,
                        "floor_area_m2": round(area,3), "volume_m3": round(area*step,3),
                        "floor_height_source": "DERIVED_EQUAL_STRATA_FROM_OSM_HEIGHT_AND_LEVELS",
                        "prototype_id": f"P3D-MUM-{building_id}-F{number:03d}-{digest}",
                        "geometry_source": "SOURCE_DERIVED_VERTICAL_STRATUM_NOT_FLOOR_PLAN",
                        "floor_count_source": "OSM_BUILDING_LEVELS", "height_source": "OSM_HEIGHT_TAG",
                        "floor_layout_verified": False, "is_synthetic": True, "is_official": False,
                    }))
        if tags.get("highway") and len(points) >= 2:
            line = LineString(points)
            if not line.is_empty and line.intersects(ward_geom):
                clipped = line.intersection(ward_geom)
                parts = [clipped] if clipped.geom_type == "LineString" else list(getattr(clipped,"geoms",[]))
                for part in parts:
                    if part.geom_type != "LineString" or part.is_empty: continue
                    roads.append(_feature(part, {"profile_id":"mumbai","road_type":tags["highway"],"name":tags.get("name") or tags.get("ref") or "Unnamed OSM street","source":"OPENSTREETMAP_HIGHWAY_WAY","source_way_id":osm_id}))

    # Prefer named, height-supported buildings with good independent overlap.
    # This ranks demonstration shortcuts only; scores are never altered.
    floor_ids = {f["properties"]["building_id"] for f in floors}
    eligible = [f for f in buildings if f["properties"]["building_id"] in floor_ids and f["properties"]["name"]]
    eligible.sort(key=lambda f: ((f["properties"].get("footprint_agreement_pct") or 0) >= 60, f["properties"].get("selected_height_m") or 0, f["properties"].get("footprint_agreement_pct") or 0), reverse=True)
    heroes = [f["properties"]["building_id"] for f in eligible[:3]]
    assert heroes, "No source-supported demonstration buildings"
    bounds = ward_geom.bounds
    center = ward_geom.centroid
    counts = {"buildings":len(buildings),"floors":len(floors),"parcels":0,"roads":len(roads),
              "vertical_buildings":sum(bool(f["properties"]["selected_height_m"]) for f in buildings),
              "tagged_level_buildings":sum(bool(f["properties"]["floor_count"]) for f in buildings),
              "floor_models":len(floor_ids),"reference_footprints":len(refs),
              "with_footprint_agreement":sum(f["properties"].get("footprint_agreement_pct") is not None for f in buildings)}
    for name, features in [("buildings",buildings),("floors",floors),("units",[]),("tax_lots",[]),("roads",roads)]:
        _write(OUT/f"{name}.geojson",_collection(features))
    _write(OUT/"ward.geojson",_collection([_feature(ward_geom,{"profile_id":"mumbai","ward_name":WARD_CODE,"ward_label":WARD_LABEL,"source":"MCGM_WARDS_DP_OFFICIAL","source_object_id":ward["properties"]["OBJECTID"]})]))
    _write(OUT/"topology_issues.json",{"topology_errors":0,"topology_warnings":len(issues),"issues":issues,"validation_scope":"Exported polygons are valid; source-invalid footprints excluded. Strata have contiguous non-overlapping relative Z. No survey verification."})
    _write(OUT/"profile.json",{
        "profile_id":"mumbai","label":"Mumbai · G/South","city":"Mumbai","study_area":"G/South (Worli–Lower Parel)",
        "ward_name":WARD_CODE,"ward_label":WARD_LABEL,"bbox":[bounds[1],bounds[0],bounds[3],bounds[2]],
        "center":[center.y,center.x],"default_hero":heroes[0],"hero_buildings":heroes,"counts":counts,
        "built_at":datetime.now(timezone.utc).isoformat(),
        "sources":{"ward_geometry":"MCGM_WARDS_DP_OFFICIAL","building_geometry":"OPENSTREETMAP_BUILDING",
                   "geometry_reference":"BMC_BUILDING_LAYER_283","roads":"OPENSTREETMAP_HIGHWAY_WAY",
                   "height":"EXPLICIT_OSM_HEIGHT_TAG_ONLY","floor_geometry":"DERIVED_STRATA_FROM_SOURCE_HEIGHT_AND_LEVELS",
                   "unit_geometry":"NOT_AVAILABLE","basement_geometry":"NOT_AVAILABLE"},
        "limitations":["OSM and BMC snapshots may differ in age and representation.","Footprint IoU is measured agreement, not cadastral confidence or positional accuracy.","No units or basements generated. No height guessed. Equal-height strata are derived displays, not actual floor plans.","Only OSM closed ways and building parts are included; coverage is not a complete building census."],
    })
    _write(OUT/"source_manifest.json",{"ward_source_url":BMC_SOURCE.rsplit("/",1)[0]+"/341","building_reference":json.loads((RAW/"bmc_buildings_gs_provenance.json").read_text()),"osm":json.loads((RAW/"osm_gs_provenance.json").read_text()),"metric_crs":"EPSG:32643","comparison":json.loads((RAW/"comparison.json").read_text()) if (RAW/"comparison.json").exists() else []})
    print("DEMO BUILDINGS",[(f["properties"]["name"],f["properties"]["selected_height_m"],f["properties"]["footprint_agreement_pct"]) for f in eligible[:6]])
    return counts

if __name__ == "__main__":
    print(json.dumps(build(),indent=2))
