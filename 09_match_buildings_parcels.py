import geopandas as gpd

# --------------------------------------------------
# 1. Load buildings and parcels
# --------------------------------------------------
buildings = gpd.read_file("data/hero_buildings.geojson")
parcels = gpd.read_file("data/hero_parcels.geojson")

# --------------------------------------------------
# 2. Convert both to metres
# --------------------------------------------------
buildings_utm = buildings.to_crs("EPSG:32644")
parcels_utm = parcels.to_crs("EPSG:32644")

results = []

# --------------------------------------------------
# 3. Compare each parcel with its selected building
# --------------------------------------------------
for _, parcel in parcels_utm.iterrows():

    building_id = parcel["building_id"]

    building = buildings_utm[
        buildings_utm["building_id"] == building_id
    ].iloc[0]

    building_geom = building.geometry
    parcel_geom = parcel.geometry

    building_area = building_geom.area

    intersection = building_geom.intersection(parcel_geom)
    intersection_area = intersection.area

    overlap_pct = (
        intersection_area / building_area * 100
        if building_area > 0 else 0
    )

    # Determine spatial relationship
    if building_geom.within(parcel_geom):
        relationship = "within"
    elif building_geom.intersects(parcel_geom):
        relationship = "intersects"
    else:
        relationship = "no_overlap"

    outside_area = building_area - intersection_area

    results.append({
        "building_id": building_id,
        "parcel_id": parcel["parcel_id"],
        "official_parcel_no": parcel["official_parcel_no"],
        "relationship": relationship,
        "building_area_m2": round(building_area, 2),
        "intersection_area_m2": round(intersection_area, 2),
        "outside_area_m2": round(outside_area, 2),
        "overlap_pct": round(overlap_pct, 2),
        "geometry": building_geom
    })

# --------------------------------------------------
# 4. Create result GeoDataFrame
# --------------------------------------------------
matches = gpd.GeoDataFrame(
    results,
    crs="EPSG:32644"
)

# Convert back to WGS84 for web/GIS use
matches = matches.to_crs("EPSG:4326")

print("\n=== BUILDING ↔ PARCEL MATCHING ===")

print(
    matches[
        [
            "building_id",
            "parcel_id",
            "official_parcel_no",
            "relationship",
            "building_area_m2",
            "intersection_area_m2",
            "outside_area_m2",
            "overlap_pct"
        ]
    ].to_string(index=False)
)

matches.to_file(
    "data/hero_building_parcel_matches.geojson",
    driver="GeoJSON"
)

print("\nSaved:")
print("data/hero_building_parcel_matches.geojson")