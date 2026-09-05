import geopandas as gpd

buildings = gpd.read_file("data/buildings_clean.geojson")

# Our selected demo buildings
hero_ids = ["B0595", "B0612", "B0162"]

heroes = buildings[
    buildings["building_id"].isin(hero_ids)
].copy()

print(
    heroes[
        [
            "building_id",
            "building",
            "building:levels",
            "area_m2"
        ]
    ].to_string(index=False)
)

heroes.to_file(
    "data/hero_buildings.geojson",
    driver="GeoJSON"
)

print("\nSaved data/hero_buildings.geojson")