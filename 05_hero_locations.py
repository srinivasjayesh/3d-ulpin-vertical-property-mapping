import geopandas as gpd

heroes = gpd.read_file("data/hero_buildings.geojson")

# Calculate centroids correctly in metric CRS
heroes_utm = heroes.to_crs("EPSG:32644")
centroids_utm = heroes_utm.geometry.centroid

# Convert centroid points back to latitude/longitude
centroids = gpd.GeoSeries(
    centroids_utm,
    crs="EPSG:32644"
).to_crs("EPSG:4326")

locations = gpd.GeoDataFrame(
    heroes[["building_id", "building", "building:levels", "area_m2"]].copy(),
    geometry=centroids,
    crs="EPSG:4326"
)

locations["longitude"] = locations.geometry.x
locations["latitude"] = locations.geometry.y

print("\n=== HERO LOCATIONS ===")

print(
    locations[
        [
            "building_id",
            "building",
            "building:levels",
            "latitude",
            "longitude"
        ]
    ].to_string(index=False)
)

locations.to_file(
    "data/hero_locations.geojson",
    driver="GeoJSON"
)

print("\nSaved data/hero_locations.geojson")