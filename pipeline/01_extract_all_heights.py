import geopandas as gpd
import rasterio
from rasterio.mask import mask
import numpy as np
import pandas as pd
import time
import os
from shapely.geometry import mapping

# --------------------------------------------------------------------------
# STAGE 3 - Scalable Satellite Height Extraction
# --------------------------------------------------------------------------

BUILDINGS_CLEAN_PATH = "data/buildings_clean.geojson"
RASTER_PATH = "data/tile_0PX-jEEaiBo.tif"

OUTPUT_CSV_PATH = "data/all_buildings_height_results.csv"
OUTPUT_GEOJSON_PATH = "data/all_buildings_vertical_enriched.geojson"

start_time = time.time()

# 1. Load clean building footprints
print(f"Loading {BUILDINGS_CLEAN_PATH}...")
buildings = gpd.read_file(BUILDINGS_CLEAN_PATH)
total_buildings = len(buildings)
print(f"Loaded {total_buildings} building footprints.")

results = []

# 2. Open Google Open Buildings 2.5D GeoTIFF tile
print(f"Opening raster {RASTER_PATH}...")
with rasterio.open(RASTER_PATH) as src:
    raster_crs = src.crs
    
    # Reproject building geometries to raster CRS (EPSG:32644) for masking
    buildings_raster_crs = buildings.to_crs(raster_crs)

    for idx, row in buildings_raster_crs.iterrows():
        b_id = row["building_id"]
        geom = row.geometry

        if geom is None or geom.is_empty:
            results.append({
                "building_id": b_id,
                "google_height_m": np.nan,
                "mean_height_m": np.nan,
                "max_height_m": np.nan,
                "valid_pixels": 0,
                "height_status": "EMPTY_GEOMETRY"
            })
            continue

        try:
            # Memory-efficient windowed masking: reads only the spatial bounding window
            geom_json = [mapping(geom)]

            # Band 2 = building_height
            height_data, _ = mask(
                src,
                geom_json,
                crop=True,
                indexes=2,
                filled=True,
                nodata=-99
            )

            # Band 3 = building_presence
            presence_data, _ = mask(
                src,
                geom_json,
                crop=True,
                indexes=3,
                filled=True,
                nodata=-99
            )

            height_flat = height_data.flatten()
            presence_flat = presence_data.flatten()

            # Filter valid height pixels: height > 0, presence > 0.5, NoData != -99
            valid_mask = (
                (height_flat != -99)
                & (height_flat > 0)
                & (presence_flat != -99)
                & (presence_flat > 0.5)
            )

            valid_heights = height_flat[valid_mask]

            if len(valid_heights) == 0:
                results.append({
                    "building_id": b_id,
                    "google_height_m": np.nan,
                    "mean_height_m": np.nan,
                    "max_height_m": np.nan,
                    "valid_pixels": 0,
                    "height_status": "NO_VALID_HEIGHT_PIXELS"
                })
            else:
                med_h = float(np.median(valid_heights))
                mean_h = float(np.mean(valid_heights))
                max_h = float(np.max(valid_heights))

                results.append({
                    "building_id": b_id,
                    "google_height_m": round(med_h, 2),
                    "mean_height_m": round(mean_h, 2),
                    "max_height_m": round(max_h, 2),
                    "valid_pixels": len(valid_heights),
                    "height_status": "VALID_HEIGHT"
                })

        except Exception as e:
            results.append({
                "building_id": b_id,
                "google_height_m": np.nan,
                "mean_height_m": np.nan,
                "max_height_m": np.nan,
                "valid_pixels": 0,
                "height_status": f"ERROR: {str(e)}"
            })

# 3. Create DataFrame and Merge
height_df = pd.DataFrame(results)
enriched_gdf = buildings.merge(height_df, on="building_id", how="left")

# Assign provenance attributes
enriched_gdf["height_source"] = np.where(
    enriched_gdf["google_height_m"].notna(),
    "Google Open Buildings 2.5D Temporal 2023",
    "missing"
)
enriched_gdf["height_year"] = 2023
enriched_gdf["is_height_estimated"] = enriched_gdf["google_height_m"].notna()

# 4. Export Outputs
print("Saving outputs...")
height_df.to_csv(OUTPUT_CSV_PATH, index=False)
enriched_gdf.to_file(OUTPUT_GEOJSON_PATH, driver="GeoJSON")

elapsed = round(time.time() - start_time, 2)

# 5. Verification & Summary
valid_count = enriched_gdf["google_height_m"].notna().sum()
missing_count = total_buildings - valid_count

print(f"\n==========================================")
print(f"STAGE 3 SATELLITE HEIGHT EXTRACTION SUMMARY")
print(f"==========================================")
print(f"Total Buildings Processed: {len(enriched_gdf)}")
print(f"Buildings with Valid Height: {valid_count}")
print(f"Buildings Missing Height: {missing_count}")
print(f"Runtime: {elapsed} seconds")
print(f"\nHERO REGRESSION CHECK:")
for hero_id in ["B0595", "B0612", "B0162"]:
    hero_row = enriched_gdf[enriched_gdf["building_id"] == hero_id]
    if not hero_row.empty:
        h = hero_row.iloc[0]["google_height_m"]
        px = hero_row.iloc[0]["valid_pixels"]
        print(f"  {hero_id}: Median Height = {h} m ({px} pixels)")

print(f"\nSaved Files:")
print(f"  - CSV: {OUTPUT_CSV_PATH}")
print(f"  - GeoJSON: {OUTPUT_GEOJSON_PATH}")
