import osmnx as ox

center_point = (17.42007, 78.35068)
radius_m = 700

tags = {"building": True}

# Pull building footprints from OpenStreetMap
buildings = ox.features_from_point(
    center_point,
    tags,
    dist=radius_m
)

# Keep only the useful columns
buildings_clean = buildings.reset_index()[
    ["geometry", "building", "building:levels"]
]

# Save the buildings permanently as a GeoJSON file
buildings_clean.to_file(
    "data/raw_buildings.geojson",
    driver="GeoJSON"
)

print(f"Saved {len(buildings_clean)} buildings to data/raw_buildings.geojson")