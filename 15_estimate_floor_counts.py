import geopandas as gpd
import pandas as pd
import numpy as np

input_file = "data/hero_buildings_with_heights.geojson"
output_file = "data/hero_vertical_enriched.geojson"

gdf = gpd.read_file(input_file)

# Convert existing OSM levels to numeric
gdf["osm_levels"] = pd.to_numeric(
    gdf["building:levels"],
    errors="coerce"
)

final_floors = []
floor_sources = []
floor_estimated = []
confidence = []

for _, row in gdf.iterrows():

    height = row["google_height_m"]
    osm_levels = row["osm_levels"]

    # ------------------------------------
    # If OSM already has floor information
    # ------------------------------------
    if pd.notna(osm_levels):

        floors = int(osm_levels)

        final_floors.append(floors)
        floor_sources.append("OSM building:levels")
        floor_estimated.append(False)

        # We also have satellite height as independent support
        confidence.append("high")

    # ------------------------------------
    # Otherwise estimate from height
    # Approximation: 3 m per floor
    # ------------------------------------
    elif pd.notna(height):

        floors = max(
            1,
            int(round(height / 3.0))
        )

        final_floors.append(floors)
        floor_sources.append(
            "Estimated from Google height (~3m/floor)"
        )
        floor_estimated.append(True)
        confidence.append("medium")

    else:

        final_floors.append(np.nan)
        floor_sources.append("missing")
        floor_estimated.append(True)
        confidence.append("low")


gdf["floor_count"] = final_floors
gdf["floor_source"] = floor_sources
gdf["is_floor_estimated"] = floor_estimated
gdf["vertical_confidence"] = confidence

# Useful cross-check
gdf["avg_height_per_floor_m"] = np.where(
    gdf["floor_count"] > 0,
    gdf["google_height_m"] / gdf["floor_count"],
    np.nan
)

print("\n=== FINAL VERTICAL ATTRIBUTES ===")

print(
    gdf[
        [
            "building_id",
            "building",
            "google_height_m",
            "osm_levels",
            "floor_count",
            "floor_source",
            "is_floor_estimated",
            "avg_height_per_floor_m",
            "vertical_confidence"
        ]
    ].to_string(index=False)
)

gdf.to_file(
    output_file,
    driver="GeoJSON"
)

print("\nSaved:")
print(output_file)