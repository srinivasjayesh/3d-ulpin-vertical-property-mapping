import geopandas as gpd
import pandas as pd
import requests
import json
import time
import os
from shapely.geometry import Polygon

# --------------------------------------------------------------------------
# STAGE 4 - Study-Area Cadastral Matching
# --------------------------------------------------------------------------

ENRICHED_BUILDINGS_PATH = "data/all_buildings_vertical_enriched.geojson"
OUTPUT_PARCELS_GEOJSON = "data/study_area_cadastral_parcels.geojson"
OUTPUT_MATCHES_GEOJSON = "data/all_building_parcel_matches.geojson"

BHUNAKSHA_URL = (
    "https://tgrac.telangana.gov.in/arcgis/rest/services/"
    "Bhunaksha_Folder/Bhunaksha_query/MapServer/0/query"
)

start_time = time.time()
print(f"Loading {ENRICHED_BUILDINGS_PATH}...")
buildings = gpd.read_file(ENRICHED_BUILDINGS_PATH)
total_buildings = len(buildings)
print(f"Loaded {total_buildings} building footprints.")

# --------------------------------------------------------------------------
# STEP 1: Envelope Bounding-Box Retrieval with Buffer & Fallback
# --------------------------------------------------------------------------
bounds = buildings.total_bounds  # (minx, miny, maxx, maxy)
buffer_deg = 0.002  # ~200m buffer to capture border parcels

query_bounds = [
    bounds[0] - buffer_deg,
    bounds[1] - buffer_deg,
    bounds[2] + buffer_deg,
    bounds[3] + buffer_deg
]

params = {
    "geometry": f"{query_bounds[0]},{query_bounds[1]},{query_bounds[2]},{query_bounds[3]}",
    "geometryType": "esriGeometryEnvelope",
    "inSR": "4326",
    "spatialRel": "esriSpatialRelIntersects",
    "outFields": "*",
    "returnGeometry": "true",
    "outSR": "4326",
    "f": "json"
}

print("\nExecuting Esri Envelope Spatial Query on BhuNaksha MapServer Layer 0...")
http_requests_made = 0
bbox_succeeded = False
fallback_required = False
features = []

try:
    http_requests_made += 1
    response = requests.get(BHUNAKSHA_URL, params=params, timeout=30)
    if response.status_code == 200:
        data = response.json()
        features = data.get("features", [])
        print(f"Envelope Query HTTP 200: Retrieved {len(features)} cadastral features.")
        bbox_succeeded = True
    else:
        print(f"Envelope Query HTTP {response.status_code}. Fallback required.")
        fallback_required = True
except Exception as e:
    print(f"Envelope Query Exception: {e}. Fallback required.")
    fallback_required = True

# Fallback mechanism if envelope query failed or returned 0 features
if fallback_required or len(features) == 0:
    print("Executing fallback controlled point queries...")
    cache_file = "cache/point_parcels_cache.json"
    os.makedirs("cache", exist_ok=True)
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cache = json.load(f)

    # Iterate building centroids for fallback point queries
    for idx, row in buildings.iterrows():
        b_id = row["building_id"]
        if b_id in cache:
            feat = cache[b_id]
            if feat:
                features.append(feat)
            continue

        pt = row.geometry.centroid
        p_params = {
            "geometry": f"{pt.x},{pt.y}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json"
        }

        try:
            http_requests_made += 1
            res = requests.get(BHUNAKSHA_URL, params=p_params, timeout=10)
            if res.status_code == 200:
                p_feats = res.json().get("features", [])
                if p_feats:
                    cache[b_id] = p_feats[0]
                    features.append(p_feats[0])
                else:
                    cache[b_id] = None
            time.sleep(0.5)  # 2 reqs/sec max rate
        except Exception:
            cache[b_id] = None

    with open(cache_file, "w") as f:
        json.dump(cache, f)

# --------------------------------------------------------------------------
# STEP 2: Save Unique Cadastral Parcels to GeoJSON
# --------------------------------------------------------------------------
parcel_records = []
seen_geoms = set()

for i, f in enumerate(features):
    rings = f.get("geometry", {}).get("rings", [])
    if not rings:
        continue

    poly = Polygon(rings[0])
    geom_wkt = poly.wkt
    if geom_wkt in seen_geoms:
        continue
    seen_geoms.add(geom_wkt)

    attrs = f.get("attributes", {})
    p_num = attrs.get("Parcel_num")
    p_num_str = str(p_num) if p_num is not None else "UNKNOWN"

    parcel_records.append({
        "parcel_id": f"P{len(parcel_records)+1:04d}",
        "official_parcel_no": p_num_str,
        "village": attrs.get("V_Name", "Nanakramguda"),
        "mandal": attrs.get("M_Name", "Serilingampally"),
        "district": attrs.get("D_Name", "Ranga Reddy"),
        "parcel_source": "Telangana TGRAC BhuNaksha Full Cadastral",
        "geometry": poly
    })

parcels_gdf = gpd.GeoDataFrame(parcel_records, crs="EPSG:4326")
print(f"Deduplicated {len(parcels_gdf)} unique cadastral parcel polygons.")

parcels_gdf.to_file(OUTPUT_PARCELS_GEOJSON, driver="GeoJSON")
print(f"Saved {OUTPUT_PARCELS_GEOJSON}.")

# --------------------------------------------------------------------------
# STEP 3: Local Spatial Matching in EPSG:32644 (UTM Zone 44N)
# --------------------------------------------------------------------------
print("\nPerforming local spatial matching in EPSG:32644...")

buildings_utm = buildings.to_crs("EPSG:32644")
parcels_utm = parcels_gdf.to_crs("EPSG:32644")

match_results = []

for _, bldg in buildings_utm.iterrows():
    b_id = bldg["building_id"]
    b_geom = bldg.geometry
    b_area = b_geom.area if (b_geom and not b_geom.is_empty) else 0.0

    intersecting_parcels = []

    if b_area > 0:
        for _, parcel in parcels_utm.iterrows():
            if b_geom.intersects(parcel.geometry):
                inter_area = b_geom.intersection(parcel.geometry).area
                pct = (inter_area / b_area * 100) if b_area > 0 else 0.0
                if inter_area > 0.1:  # Ignore floating precision noise
                    intersecting_parcels.append({
                        "parcel_id": parcel["parcel_id"],
                        "official_parcel_no": parcel["official_parcel_no"],
                        "village": parcel["village"],
                        "mandal": parcel["mandal"],
                        "district": parcel["district"],
                        "parcel_source": parcel["parcel_source"],
                        "inter_area": inter_area,
                        "pct": pct,
                        "parcel_geom": parcel.geometry
                    })

    intersecting_parcels.sort(key=lambda x: x["inter_area"], reverse=True)

    if not intersecting_parcels:
        match_results.append({
            "building_id": b_id,
            "building_area_m2": round(b_area, 2),
            "matched_parcel_id": None,
            "official_parcel_no": None,
            "village": None,
            "mandal": None,
            "district": None,
            "intersection_area_m2": 0.0,
            "outside_area_m2": round(b_area, 2),
            "overlap_percent": 0.0,
            "spatial_relationship": "no_overlap",
            "parcel_match_status": "NO_MATCH",
            "parcel_source": "Telangana TGRAC BhuNaksha Full Cadastral"
        })
    else:
        top = intersecting_parcels[0]
        top_pct = top["pct"]
        top_inter = top["inter_area"]
        outside_area = max(0.0, b_area - top_inter)

        significant_matches = [p for p in intersecting_parcels if p["pct"] >= 10.0]

        if b_geom.within(top["parcel_geom"]):
            relationship = "within"
        else:
            relationship = "intersects"

        if len(significant_matches) >= 2:
            status = "MULTI_PARCEL"
        elif top_pct >= 70.0:
            status = "STRONG_MATCH"
        elif top_pct >= 10.0:
            status = "PARTIAL_MATCH"
        else:
            status = "NO_MATCH"

        match_results.append({
            "building_id": b_id,
            "building_area_m2": round(b_area, 2),
            "matched_parcel_id": top["parcel_id"],
            "official_parcel_no": top["official_parcel_no"],
            "village": top["village"],
            "mandal": top["mandal"],
            "district": top["district"],
            "intersection_area_m2": round(top_inter, 2),
            "outside_area_m2": round(outside_area, 2),
            "overlap_percent": round(top_pct, 2),
            "spatial_relationship": relationship,
            "parcel_match_status": status,
            "parcel_source": top["parcel_source"]
        })

# --------------------------------------------------------------------------
# STEP 4: Merge Match Attributes into Final GeoDataFrame & Export
# --------------------------------------------------------------------------
matches_df = pd.DataFrame(match_results)

# Merge back with original enriched buildings to preserve all fields
all_matches_gdf = buildings.merge(matches_df, on="building_id", how="left")

all_matches_gdf.to_file(OUTPUT_MATCHES_GEOJSON, driver="GeoJSON")
print(f"Saved {OUTPUT_MATCHES_GEOJSON} ({len(all_matches_gdf)} features).")

elapsed = round(time.time() - start_time, 2)

# --------------------------------------------------------------------------
# STEP 5: Verification & Summary Statistics
# --------------------------------------------------------------------------
status_counts = all_matches_gdf["parcel_match_status"].value_counts().to_dict()
populated_parcels = all_matches_gdf["official_parcel_no"].notna().sum()

print("\n==========================================")
print("STAGE 4 CADASTRAL MATCHING SUMMARY")
print("==========================================")
print(f"Total Buildings Evaluated: {len(all_matches_gdf)}")
print(f"Unique Cadastral Parcels Downloaded: {len(parcels_gdf)}")
print(f"HTTP Requests Made: {http_requests_made}")
print(f"Bounding-Box Retrieval Succeeded: {bbox_succeeded}")
print(f"Fallback Requests Required: {fallback_required}")
print(f"Runtime: {elapsed} seconds")
print(f"Buildings with Official Parcel Numbers: {populated_parcels}")
print("\nMatch Status Breakdowns:")
print(f"  - STRONG_MATCH: {status_counts.get('STRONG_MATCH', 0)}")
print(f"  - PARTIAL_MATCH: {status_counts.get('PARTIAL_MATCH', 0)}")
print(f"  - MULTI_PARCEL: {status_counts.get('MULTI_PARCEL', 0)}")
print(f"  - NO_MATCH: {status_counts.get('NO_MATCH', 0)}")
print(f"  - API_UNAVAILABLE: {status_counts.get('API_UNAVAILABLE', 0)}")

print("\nHERO REGRESSION CHECK:")
hero_map = {"B0595": "140", "B0612": "337", "B0162": "92"}
for hero_id, expected_pno in hero_map.items():
    row = all_matches_gdf[all_matches_gdf["building_id"] == hero_id]
    if not row.empty:
        actual_pno = row.iloc[0]["official_parcel_no"]
        overlap = row.iloc[0]["overlap_percent"]
        status = row.iloc[0]["parcel_match_status"]
        match_str = "MATCHED" if str(actual_pno) == str(expected_pno) else "MISMATCH"
        print(f"  {hero_id}: Expected Parcel {expected_pno} -> Actual Parcel {actual_pno} ({overlap}% overlap, Status: {status}) [{match_str}]")

print(f"\nOutputs Generated:")
print(f"  - Parcels GeoJSON: {OUTPUT_PARCELS_GEOJSON}")
print(f"  - Matches GeoJSON: {OUTPUT_MATCHES_GEOJSON}")
