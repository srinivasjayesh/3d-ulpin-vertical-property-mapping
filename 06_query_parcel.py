import requests
import geopandas as gpd

# Load hero buildings
heroes = gpd.read_file("data/hero_buildings.geojson")

# Primary hero
hero = heroes[heroes["building_id"] == "B0595"].iloc[0]

# Calculate centroid in projected CRS
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

print("Searching parcel for B0595")
print("Latitude:", lat)
print("Longitude:", lon)

# Cadastral layers worth checking
layers = {
    0: "Full Cadastral",
    1: "ULB Cadastral",
    7: "Cadastral"
}

for layer_id, layer_name in layers.items():

    print(f"\n=== CHECKING {layer_name} (Layer {layer_id}) ===")

    url = (
        "https://tgrac.telangana.gov.in/arcgis/rest/services/"
        f"Bhunaksha_Folder/Bhunaksha_query/MapServer/{layer_id}/query"
    )

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

    print("HTTP status:", response.status_code)

    if response.status_code != 200:
        print("Request failed")
        continue

    data = response.json()

    features = data.get("features", [])

    print("Parcels found:", len(features))

    if features:

        parcel = features[0]

        print("\nPARCEL ATTRIBUTES:")

        for key, value in parcel.get("attributes", {}).items():
            if value is not None:
                print(f"{key}: {value}")

        if parcel.get("geometry"):
            print("\nParcel geometry returned: YES")
        else:
            print("\nParcel geometry returned: NO")