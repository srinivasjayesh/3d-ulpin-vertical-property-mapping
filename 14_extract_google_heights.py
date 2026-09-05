import geopandas as gpd
import rasterio
import numpy as np
from rasterio.mask import mask
from shapely.geometry import mapping

# --------------------------------------------------
# 1. Input files
# --------------------------------------------------
raster_path = "data/tile_0PX-jEEaiBo.tif"
heroes_path = "data/hero_buildings.geojson"

# --------------------------------------------------
# 2. Load hero buildings
# --------------------------------------------------
heroes = gpd.read_file(heroes_path)

results = []

# --------------------------------------------------
# 3. Open Google Open Buildings raster
# --------------------------------------------------
with rasterio.open(raster_path) as src:

    # Convert hero polygons to raster CRS
    heroes_utm = heroes.to_crs(src.crs)

    for _, building in heroes_utm.iterrows():

        building_id = building["building_id"]

        print(f"\nProcessing {building_id}...")

        geometry = [mapping(building.geometry)]

        # Band 2 = building_height
        height_data, _ = mask(
            src,
            geometry,
            crop=True,
            indexes=2,
            filled=True,
            nodata=-99
        )

        # Band 3 = building_presence
        presence_data, _ = mask(
            src,
            geometry,
            crop=True,
            indexes=3,
            filled=True,
            nodata=-99
        )

        height_values = height_data.flatten()
        presence_values = presence_data.flatten()

        # --------------------------------------------------
        # 4. Keep only useful building pixels
        # --------------------------------------------------
        valid = (
            (height_values != -99)
            & (height_values > 0)
            & (presence_values != -99)
            & (presence_values > 0.5)
        )

        valid_heights = height_values[valid]

        if len(valid_heights) == 0:
            print("No valid height pixels found.")

            results.append({
                "building_id": building_id,
                "google_height_m": np.nan,
                "mean_height_m": np.nan,
                "max_height_m": np.nan,
                "valid_pixels": 0
            })

            continue

        # Median is our main estimate because it is less
        # affected by unusually high/low pixels
        median_height = float(np.median(valid_heights))
        mean_height = float(np.mean(valid_heights))
        max_height = float(np.max(valid_heights))

        print("Valid pixels:", len(valid_heights))
        print("Median height:", round(median_height, 2), "m")
        print("Mean height:", round(mean_height, 2), "m")
        print("Maximum height:", round(max_height, 2), "m")

        results.append({
            "building_id": building_id,
            "google_height_m": round(median_height, 2),
            "mean_height_m": round(mean_height, 2),
            "max_height_m": round(max_height, 2),
            "valid_pixels": len(valid_heights)
        })


# --------------------------------------------------
# 5. Add results back to hero dataset
# --------------------------------------------------
import pandas as pd

height_df = pd.DataFrame(results)

heroes = heroes.merge(
    height_df,
    on="building_id",
    how="left"
)

heroes["height_source"] = "Google Open Buildings 2.5D Temporal"
heroes["height_year"] = 2023
heroes["is_height_estimated"] = True

# --------------------------------------------------
# 6. Show final result
# --------------------------------------------------
print("\n=== GOOGLE HEIGHT RESULTS ===")

print(
    heroes[
        [
            "building_id",
            "building",
            "building:levels",
            "google_height_m",
            "mean_height_m",
            "max_height_m",
            "valid_pixels"
        ]
    ].to_string(index=False)
)

# --------------------------------------------------
# 7. Save
# --------------------------------------------------
heroes.to_file(
    "data/hero_buildings_with_heights.geojson",
    driver="GeoJSON"
)

height_df.to_csv(
    "data/google_height_results.csv",
    index=False
)

print("\nSaved:")
print("data/hero_buildings_with_heights.geojson")
print("data/google_height_results.csv")