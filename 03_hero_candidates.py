import geopandas as gpd

# Load cleaned building data
buildings = gpd.read_file("data/buildings_clean.geojson")

# Pick the 10 largest buildings
candidates = buildings.sort_values(
    "area_m2",
    ascending=False
).head(10).copy()

# Convert to UTM so centroid is calculated in metres
candidates_utm = candidates.to_crs("EPSG:32644")

# Calculate centroid
centroids_utm = candidates_utm.geometry.centroid

# Convert centroid points back to latitude/longitude
centroids = gpd.GeoSeries(
    centroids_utm,
    crs="EPSG:32644"
).to_crs("EPSG:4326")

# Add coordinates to the candidate table
candidates["longitude"] = centroids.x
candidates["latitude"] = centroids.y

print("\n=== HERO BUILDING CANDIDATES ===")

print(
    candidates[
        [
            "building_id",
            "building",
            "building:levels",
            "area_m2",
            "latitude",
            "longitude"
        ]
    ].to_string(index=False)
)

# Save the 10 candidates
candidates.to_file(
    "data/hero_candidates.geojson",
    driver="GeoJSON"
)

print("\nSaved:")
print("data/hero_candidates.geojson")