import geopandas as gpd

# --------------------------------------------------
# 1. Load the RAW OSM building data
# --------------------------------------------------
buildings = gpd.read_file("data/raw_buildings.geojson")

print("Total raw buildings:", len(buildings))
print("Original CRS:", buildings.crs)


# --------------------------------------------------
# 2. Check geometry quality
# --------------------------------------------------
print("Invalid geometries:", (~buildings.geometry.is_valid).sum())
print("Empty geometries:", buildings.geometry.is_empty.sum())
print("Missing geometries:", buildings.geometry.isna().sum())


# --------------------------------------------------
# 3. Keep only valid building polygons
# --------------------------------------------------
buildings = buildings[
    buildings.geometry.notna()
    & (~buildings.geometry.is_empty)
    & buildings.geometry.is_valid
].copy()

print("Usable buildings:", len(buildings))


# --------------------------------------------------
# 4. Assign our own prototype building IDs
# --------------------------------------------------
buildings = buildings.reset_index(drop=True)

buildings["building_id"] = [
    f"B{i:04d}" for i in range(1, len(buildings) + 1)
]


# --------------------------------------------------
# 5. Convert to UTM Zone 44N
#    This allows measurements in metres
# --------------------------------------------------
buildings_utm = buildings.to_crs("EPSG:32644")


# --------------------------------------------------
# 6. Calculate building footprint area
# --------------------------------------------------
buildings["area_m2"] = buildings_utm.geometry.area.round(2)


# --------------------------------------------------
# 7. Save CLEAN working dataset
# --------------------------------------------------
buildings.to_file(
    "data/buildings_clean.geojson",
    driver="GeoJSON"
)


# --------------------------------------------------
# 8. Show largest buildings as hero candidates
# --------------------------------------------------
largest = buildings.sort_values(
    "area_m2",
    ascending=False
).head(10)

print("\n=== 10 LARGEST BUILDINGS ===")

print(
    largest[
        [
            "building_id",
            "building",
            "building:levels",
            "area_m2"
        ]
    ].to_string(index=False)
)

print("\nSaved cleaned buildings to:")
print("data/buildings_clean.geojson")