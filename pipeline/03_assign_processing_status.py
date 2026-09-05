import geopandas as gpd
import pandas as pd
import numpy as np
import time
import os

# --------------------------------------------------------------------------
# STAGE 5 - All-Building Vertical Processing Status Assignment
# --------------------------------------------------------------------------

INPUT_PARCEL_MATCHES = "data/all_building_parcel_matches.geojson"
OUTPUT_GEOJSON = "data/all_buildings_processed.geojson"
OUTPUT_CSV = "data/all_buildings_processed.csv"

start_time = time.time()
print(f"Loading merged building & cadastral match data from {INPUT_PARCEL_MATCHES}...")
gdf = gpd.read_file(INPUT_PARCEL_MATCHES)
total_buildings = len(gdf)
print(f"Loaded {total_buildings} building footprints.")

# Ensure optional columns like 'name' exist if absent
if "name" not in gdf.columns:
    gdf["name"] = None

# --------------------------------------------------------------------------
# STEP 2: Floor Count Logic
# --------------------------------------------------------------------------
def compute_floor_info(row):
    levels = row.get("building:levels")
    if pd.notna(levels):
        try:
            val = float(levels)
            if val > 0:
                return int(val), "OSM building:levels", False
        except (ValueError, TypeError):
            pass
    
    h = row.get("google_height_m")
    if pd.notna(h) and float(h) > 0:
        fc = max(1, int(round(float(h) / 3.0)))
        return fc, "Estimated from Google height (~3m/floor)", True
        
    return np.nan, "missing", True

floors_info = gdf.apply(compute_floor_info, axis=1)
gdf["floor_count"] = [x[0] for x in floors_info]
gdf["floor_source"] = [x[1] for x in floors_info]
gdf["is_floor_estimated"] = [x[2] for x in floors_info]

# --------------------------------------------------------------------------
# STEP 3: Height / Floor Sanity Check
# --------------------------------------------------------------------------
def compute_sanity(row):
    h = row.get("google_height_m")
    fc = row.get("floor_count")
    if pd.notna(h) and pd.notna(fc) and float(fc) > 0:
        avg_h = round(float(h) / float(fc), 2)
        if 2.2 <= avg_h <= 5.5:
            return avg_h, "FLOOR_HEIGHT_NORMAL"
        else:
            return avg_h, "FLOOR_HEIGHT_REVIEW"
    return np.nan, "NOT_APPLICABLE"

sanity_info = gdf.apply(compute_sanity, axis=1)
gdf["avg_height_per_floor_m"] = [x[0] for x in sanity_info]
gdf["floor_height_sanity"] = [x[1] for x in sanity_info]

# --------------------------------------------------------------------------
# STEP 4: Processing Status Assignment
# --------------------------------------------------------------------------
def compute_processing_status(row):
    h_valid = pd.notna(row.get("google_height_m")) and float(row.get("google_height_m")) > 0
    fc_valid = pd.notna(row.get("floor_count")) and float(row.get("floor_count")) > 0
    p_status = row.get("parcel_match_status")
    
    if h_valid and fc_valid:
        if p_status == "STRONG_MATCH":
            return "FULL_3D_CADASTRAL"
        else:
            return "VERTICAL_3D_PARTIAL"
    elif h_valid and not fc_valid:
        return "HEIGHT_ONLY_3D"
    else:
        return "CONTEXT_ONLY"

gdf["processing_status"] = gdf.apply(compute_processing_status, axis=1)

# --------------------------------------------------------------------------
# STEP 5: Source Confidence Classification
# --------------------------------------------------------------------------
def compute_confidence(row):
    h_valid = pd.notna(row.get("google_height_m")) and float(row.get("google_height_m")) > 0
    f_src = row.get("floor_source")
    p_status = row.get("parcel_match_status")
    
    if f_src == "OSM building:levels" and h_valid and p_status == "STRONG_MATCH":
        return "HIGH"
    elif row.get("is_floor_estimated") and h_valid and p_status == "STRONG_MATCH":
        return "MEDIUM"
    elif h_valid and p_status in ["MULTI_PARCEL", "PARTIAL_MATCH", "NO_MATCH", "API_UNAVAILABLE"]:
        return "MEDIUM_PARTIAL"
    else:
        return "LOW"

gdf["data_confidence"] = gdf.apply(compute_confidence, axis=1)

# --------------------------------------------------------------------------
# STEP 7: Export GeoJSON & CSV
# --------------------------------------------------------------------------
gdf.to_file(OUTPUT_GEOJSON, driver="GeoJSON")
print(f"Saved {OUTPUT_GEOJSON} ({len(gdf)} features).")

df_csv = pd.DataFrame(gdf.drop(columns=["geometry"]))
df_csv.to_csv(OUTPUT_CSV, index=False)
print(f"Saved {OUTPUT_CSV} ({len(df_csv)} records).")

elapsed = round(time.time() - start_time, 2)

# --------------------------------------------------------------------------
# STEP 8: Summary Statistics & Hero Regression Check
# --------------------------------------------------------------------------
status_counts = gdf["processing_status"].value_counts().to_dict()
conf_counts = gdf["data_confidence"].value_counts().to_dict()
sanity_counts = gdf["floor_height_sanity"].value_counts().to_dict()
floor_src_counts = gdf["floor_source"].value_counts().to_dict()

valid_heights_count = gdf["google_height_m"].notna().sum()
osm_floors_count = (gdf["floor_source"] == "OSM building:levels").sum()
est_floors_count = (gdf["floor_source"] == "Estimated from Google height (~3m/floor)").sum()
no_floors_count = (gdf["floor_source"] == "missing").sum()

print("\n==========================================")
print("STAGE 5 VERTICAL PROCESSING SUMMARY")
print("==========================================")
print(f"Total Buildings Evaluated: {total_buildings}")
print(f"Buildings with Valid Satellite Heights: {valid_heights_count}")
print(f"Buildings with OSM Floor Counts: {osm_floors_count}")
print(f"Buildings with Estimated Floor Counts: {est_floors_count}")
print(f"Buildings with No Usable Floor Count: {no_floors_count}")

print("\nProcessing Status Counts:")
print(f"  - FULL_3D_CADASTRAL: {status_counts.get('FULL_3D_CADASTRAL', 0)}")
print(f"  - VERTICAL_3D_PARTIAL: {status_counts.get('VERTICAL_3D_PARTIAL', 0)}")
print(f"  - HEIGHT_ONLY_3D: {status_counts.get('HEIGHT_ONLY_3D', 0)}")
print(f"  - CONTEXT_ONLY: {status_counts.get('CONTEXT_ONLY', 0)}")

print("\nData Confidence Counts:")
print(f"  - HIGH: {conf_counts.get('HIGH', 0)}")
print(f"  - MEDIUM: {conf_counts.get('MEDIUM', 0)}")
print(f"  - MEDIUM_PARTIAL: {conf_counts.get('MEDIUM_PARTIAL', 0)}")
print(f"  - LOW: {conf_counts.get('LOW', 0)}")

print("\nFloor Height Sanity Counts:")
print(f"  - FLOOR_HEIGHT_NORMAL: {sanity_counts.get('FLOOR_HEIGHT_NORMAL', 0)}")
print(f"  - FLOOR_HEIGHT_REVIEW: {sanity_counts.get('FLOOR_HEIGHT_REVIEW', 0)}")
print(f"  - NOT_APPLICABLE: {sanity_counts.get('NOT_APPLICABLE', 0)}")

print("\nHERO REGRESSION CHECK:")
hero_map = {
    "B0595": {"pno": "140", "status": "FULL_3D_CADASTRAL", "floors": 23, "est": False},
    "B0612": {"pno": "337", "status": "FULL_3D_CADASTRAL", "floors": 18, "est": True},
    "B0162": {"pno": "92", "status": "FULL_3D_CADASTRAL", "floors": 2, "est": True}
}

for hero_id, expected in hero_map.items():
    row = gdf[gdf["building_id"] == hero_id]
    if not row.empty:
        r = row.iloc[0]
        actual_h = r["google_height_m"]
        actual_fc = r["floor_count"]
        actual_src = r["floor_source"]
        actual_est = r["is_floor_estimated"]
        actual_pno = r["official_parcel_no"]
        actual_status = r["processing_status"]
        actual_conf = r["data_confidence"]
        
        pass_h = actual_h is not None and abs(actual_h - {"B0595": 79.5, "B0612": 53.5, "B0162": 7.5}[hero_id]) < 0.1
        pass_fc = (actual_fc == expected["floors"])
        pass_pno = (str(actual_pno) == str(expected["pno"]))
        pass_st = (actual_status == expected["status"])
        
        status_str = "PASSED" if (pass_h and pass_fc and pass_pno and pass_st) else "FAILED"
        print(f"  {hero_id}: Height={actual_h}m, Floors={actual_fc} ({'Estimated' if actual_est else 'OSM'}), Parcel={actual_pno}, Status={actual_status}, Confidence={actual_conf} [{status_str}]")

print(f"\nRuntime: {elapsed} seconds")
