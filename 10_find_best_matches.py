import requests
import geopandas as gpd
from shapely.geometry import Polygon

buildings = gpd.read_file("data/hero_candidates.geojson")

url = (
    "https://tgrac.telangana.gov.in/arcgis/rest/services/"
    "Bhunaksha_Folder/Bhunaksha_query/MapServer/0/query"
)

results = []

for _, building in buildings.iterrows():

    building_id = building["building_id"]

    # Calculate centroid correctly
    building_series = gpd.GeoSeries(
        [building.geometry],
        crs="EPSG:4326"
    )

    building_utm = building_series.to_crs("EPSG:32644")
    centroid_utm = building_utm.centroid.iloc[0]

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

    try:
        response = requests.get(url, params=params, timeout=30)
        data = response.json()
        features = data.get("features", [])

        if not features:
            print(f"{building_id}: no parcel")
            continue

        parcel = features[0]

        rings = parcel.get("geometry", {}).get("rings", [])

        if not rings:
            continue

        parcel_polygon = Polygon(rings[0])

        # Convert both geometries to metres
        building_metric = gpd.GeoSeries(
            [building.geometry],
            crs="EPSG:4326"
        ).to_crs("EPSG:32644").iloc[0]

        parcel_metric = gpd.GeoSeries(
            [parcel_polygon],
            crs="EPSG:4326"
        ).to_crs("EPSG:32644").iloc[0]

        building_area = building_metric.area
        intersection_area = building_metric.intersection(parcel_metric).area

        overlap_pct = (
            intersection_area / building_area * 100
            if building_area > 0 else 0
        )

        attributes = parcel["attributes"]

        results.append({
            "building_id": building_id,
            "building": building.get("building"),
            "levels": building.get("building:levels"),
            "area_m2": round(building_area, 2),
            "parcel_no": attributes.get("Parcel_num"),
            "overlap_pct": round(overlap_pct, 2)
        })

        print(
            building_id,
            "→ Parcel",
            attributes.get("Parcel_num"),
            "→",
            round(overlap_pct, 2),
            "%"
        )

    except Exception as e:
        print(building_id, "ERROR:", e)


print("\n=== BEST CANDIDATES ===")

results = sorted(
    results,
    key=lambda x: x["overlap_pct"],
    reverse=True
)

for r in results:
    print(
        r["building_id"],
        "|",
        r["building"],
        "| levels:",
        r["levels"],
        "| parcel:",
        r["parcel_no"],
        "| overlap:",
        r["overlap_pct"],
        "%"
    )