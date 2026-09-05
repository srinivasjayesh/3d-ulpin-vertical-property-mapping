import osmnx as ox
import geopandas as gpd
import pandas as pd

heroes = gpd.read_file("data/hero_buildings.geojson")

results = []

for _, hero in heroes.iterrows():

    building_id = hero["building_id"]

    print(f"\nChecking {building_id}...")

    # Ask OSM again for buildings intersecting this exact footprint
    nearby = ox.features_from_polygon(
        hero.geometry,
        tags={"building": True}
    )

    # Keep only polygon buildings
    nearby = nearby[
        nearby.geom_type.isin(["Polygon", "MultiPolygon"])
    ].copy()

    if nearby.empty:
        print("No matching OSM building found.")
        continue

    # Convert to metric CRS for accurate overlap comparison
    hero_metric = gpd.GeoSeries(
        [hero.geometry],
        crs="EPSG:4326"
    ).to_crs("EPSG:32644").iloc[0]

    nearby_metric = nearby.to_crs("EPSG:32644")

    best_index = None
    best_overlap = 0

    for index, row in nearby_metric.iterrows():

        intersection_area = hero_metric.intersection(
            row.geometry
        ).area

        if intersection_area > best_overlap:
            best_overlap = intersection_area
            best_index = index

    if best_index is None:
        print("No usable matching building.")
        continue

    match = nearby.loc[best_index]

    height = match.get("height")
    levels = match.get("building:levels")
    building_type = match.get("building")
    name = match.get("name")

    print("Building type:", building_type)
    print("Name:", name)
    print("OSM levels:", levels)
    print("OSM height:", height)

    results.append({
        "building_id": building_id,
        "building": building_type,
        "name": name,
        "osm_levels": levels,
        "osm_height": height
    })


df = pd.DataFrame(results)

df.to_csv(
    "data/osm_vertical_check.csv",
    index=False
)

print("\n=== FINAL OSM VERTICAL CHECK ===")
print(df.to_string(index=False))

print("\nSaved data/osm_vertical_check.csv")