import requests
import geopandas as gpd
from shapely.geometry import Polygon

heroes = gpd.read_file("data/hero_buildings.geojson")

hero_ids = ["B0595", "B0612", "B0162"]

url = (
    "https://tgrac.telangana.gov.in/arcgis/rest/services/"
    "Bhunaksha_Folder/Bhunaksha_query/MapServer/0/query"
)

parcel_records = []

for i, hero_id in enumerate(hero_ids, start=1):

    hero = heroes[heroes["building_id"] == hero_id].iloc[0]

    # centroid in correct projected CRS
    hero_utm = gpd.GeoSeries(
        [hero.geometry],
        crs="EPSG:4326"
    ).to_crs("EPSG:32644")

    centroid_utm = hero_utm.centroid.iloc[0]

    centroid = gpd.GeoSeries(
        [centroid_utm],
        crs="EPSG:32644"
    ).to_crs("EPSG:4326").iloc[0]

    lon = centroid.x
    lat = centroid.y

    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json"
    }

    response = requests.get(url, params=params, timeout=30)

    if response.status_code != 200:
        print(f"Failed for {hero_id}")
        continue

    data = response.json()
    features = data.get("features", [])

    if not features:
        print(f"No parcel found for {hero_id}")
        continue

    parcel = features[0]
    attributes = parcel["attributes"]
    geometry = parcel["geometry"]

    rings = geometry.get("rings", [])
    if not rings:
        print(f"No geometry rings for {hero_id}")
        continue

    parcel_polygon = Polygon(rings[0])

    parcel_records.append({
        "parcel_id": f"P{i:03d}",
        "building_id": hero_id,
        "official_parcel_no": attributes.get("Parcel_num"),
        "village": attributes.get("V_Name"),
        "mandal": attributes.get("M_Name"),
        "district": attributes.get("D_Name"),
        "parcel_source": "Telangana BhuNaksha Full Cadastral",
        "is_synthetic": False,
        "geometry": parcel_polygon
    })

parcels_gdf = gpd.GeoDataFrame(parcel_records, crs="EPSG:4326")

print("\n=== HERO PARCELS ===")
print(
    parcels_gdf[
        [
            "parcel_id",
            "building_id",
            "official_parcel_no",
            "village",
            "mandal",
            "district"
        ]
    ].to_string(index=False)
)

parcels_gdf.to_file(
    "data/hero_parcels.geojson",
    driver="GeoJSON"
)

print("\nSaved data/hero_parcels.geojson")
