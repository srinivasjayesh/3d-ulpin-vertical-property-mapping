import geopandas as gpd
import pandas as pd
import numpy as np

# Load our final hero buildings
heroes = gpd.read_file("data/hero_buildings.geojson")

# Convert OSM building:levels into a number
heroes["floor_count"] = pd.to_numeric(
    heroes["building:levels"],
    errors="coerce"
)

# Record where floor information came from
heroes["floor_source"] = heroes["floor_count"].apply(
    lambda x: "OSM" if pd.notna(x) else "missing"
)

# Height has NOT been determined yet
heroes["height_m"] = np.nan
heroes["height_source"] = "missing"
heroes["is_height_estimated"] = False

print("\n=== CURRENT VERTICAL DATA ===")

print(
    heroes[
        [
            "building_id",
            "building",
            "floor_count",
            "floor_source",
            "height_m",
            "height_source"
        ]
    ].to_string(index=False)
)

heroes.to_file(
    "data/hero_vertical_baseline.geojson",
    driver="GeoJSON"
)

print("\nSaved data/hero_vertical_baseline.geojson")