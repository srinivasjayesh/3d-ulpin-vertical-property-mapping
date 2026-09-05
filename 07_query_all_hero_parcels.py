import requests
import geopandas as gpd

heroes = gpd.read_file("data/hero_buildings.geojson")

hero_ids = ["B0595", "B0612", "B0598"]

url = (
    "https://tgrac.telangana.gov.in/arcgis/rest/services/"
    "Bhunaksha_Folder/Bhunaksha_query/MapServer/0/query"
)

for hero_id in hero_ids:

    hero = heroes[heroes["building_id"] == hero_id].iloc[0]

    # Calculate centroid correctly
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

    print(f"\n==============================")
    print(f"Searching parcel for {hero_id}")
    print("Latitude:", lat)
    print("Longitude:", lon)

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

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    print("HTTP status:", response.status_code)

    if response.status_code != 200:
        print("Request failed")
        continue

    data = response.json()
    features = data.get("features", [])

    print("Parcels found:", len(features))

    if not features:
        print("No cadastral parcel found.")
        continue

    parcel = features[0]

    attributes = parcel.get("attributes", {})
    geometry = parcel.get("geometry", {})

    print("Parcel number:", attributes.get("Parcel_num"))
    print("Village:", attributes.get("V_Name"))
    print("Mandal:", attributes.get("M_Name"))
    print("District:", attributes.get("D_Name"))
    print("Geometry rings:", len(geometry.get("rings", [])))