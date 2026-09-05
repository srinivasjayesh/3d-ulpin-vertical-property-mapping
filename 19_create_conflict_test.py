import geopandas as gpd
import pandas as pd

INPUT = "data/hero_floor_ulpins.geojson"
OUTPUT = "data/hero_floor_ulpins_conflict_test.geojson"

gdf = gpd.read_file(INPUT)

# Use one real floor as the base geometry
base = gdf[gdf["floor_id"] == "B0595-F005"].iloc[0].copy()

# Create a clearly-labelled synthetic conflicting volume
test = base.copy()

test["building_id"] = "TEST_CONFLICT"
test["floor_id"] = "TEST-CONFLICT-001"
test["prototype_3d_ulpin"] = "SYNTHETIC-CONFLICT-TEST-001"

# Deliberately overlap vertically with B0595-F005
test["z_min_m"] = 12.50
test["z_max_m"] = 15.00
test["floor_height_m"] = 2.50

test["ulpin_type"] = "SYNTHETIC_TEST_VOLUME"
test["ulpin_is_official"] = False

# Add synthetic record
test_gdf = gpd.GeoDataFrame(
    [test],
    geometry="geometry",
    crs=gdf.crs
)

combined = gpd.GeoDataFrame(
    pd.concat(
        [gdf, test_gdf],
        ignore_index=True
    ),
    geometry="geometry",
    crs=gdf.crs
)

combined.to_file(
    OUTPUT,
    driver="GeoJSON"
)

print("\n=== SYNTHETIC CONFLICT CREATED ===")
print("Original volumes:", len(gdf))
print("Test volumes:", len(combined))
print()
print("Synthetic volume:")
print("ID: TEST-CONFLICT-001")
print("Geometry copied from: B0595-F005")
print("Z range: 12.50 m - 15.00 m")
print()
print("Saved:")
print(OUTPUT)