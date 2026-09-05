from pathlib import Path
import re

import geopandas as gpd
import osmnx as ox
import pandas as pd
import requests

from shapely.geometry import Polygon
from shapely.ops import unary_union


# ==========================================================
# SETTINGS
# ==========================================================

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

OUT_DIR = DATA / "cadastral_layer_test"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_CRS = "EPSG:32644"

# Our existing Financial District study area
LAT = 17.42007
LON = 78.35068
RADIUS_M = 700


SOURCES = [

    {
        "name": "FULL_CADASTRAL",
        "url":
            "https://tgrac.telangana.gov.in/arcgis/rest/services/"
            "Bhunaksha_Folder/Bhunaksha_query/MapServer/0/query"
    },

    {
        "name": "ULB_CADASTRAL",
        "url":
            "https://tgrac.telangana.gov.in/arcgis/rest/services/"
            "Bhunaksha_Folder/Bhunaksha/MapServer/2/query"
    },

    {
        "name": "CADASTRAL_30CM",
        "url":
            "https://tgrac.telangana.gov.in/arcgis/rest/services/"
            "Bhunaksha_Folder/Bhunaksha/MapServer/3/query"
    }
]


# ==========================================================
# SEARCH BOUNDING BOX
# ==========================================================

def get_bbox():

    point = gpd.GeoDataFrame(
        {"id": [1]},
        geometry=gpd.points_from_xy(
            [LON],
            [LAT]
        ),
        crs="EPSG:4326"
    )

    point_m = point.to_crs(
        TARGET_CRS
    )

    buffer_geom = (
        point_m.geometry.iloc[0]
        .buffer(RADIUS_M)
    )

    area = gpd.GeoDataFrame(
        {"id": [1]},
        geometry=[buffer_geom],
        crs=TARGET_CRS
    ).to_crs("EPSG:4326")

    return area.total_bounds


# ==========================================================
# DOWNLOAD BUILDINGS
# ==========================================================

def load_buildings():

    print("Downloading OSM buildings...")

    buildings = ox.features_from_point(
        (LAT, LON),
        tags={"building": True},
        dist=RADIUS_M
    )

    buildings = buildings[
        buildings.geometry.geom_type.isin(
            ["Polygon", "MultiPolygon"]
        )
    ].copy()

    buildings = buildings.to_crs(
        "EPSG:4326"
    ).reset_index()

    buildings["test_building_id"] = [
        f"B{i:04d}"
        for i in range(
            1,
            len(buildings) + 1
        )
    ]

    print(
        "Buildings:",
        len(buildings)
    )

    return buildings


# ==========================================================
# DOWNLOAD PARCELS
# ==========================================================

def download_parcels(source):

    xmin, ymin, xmax, ymax = (
        get_bbox()
    )

    params = {

        "where":
            "1=1",

        "geometry":
            f"{xmin},{ymin},{xmax},{ymax}",

        "geometryType":
            "esriGeometryEnvelope",

        "inSR":
            "4326",

        "spatialRel":
            "esriSpatialRelIntersects",

        "outFields":
            "*",

        "returnGeometry":
            "true",

        "outSR":
            "4326",

        "resultRecordCount":
            "2000",

        "f":
            "json"
    }


    response = requests.get(
        source["url"],
        params=params,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()


    if "error" in data:

        raise RuntimeError(
            data["error"]
        )


    features = data.get(
        "features",
        []
    )


    records = []


    for i, feature in enumerate(
        features
    ):

        geometry_data = (
            feature.get(
                "geometry",
                {}
            )
        )

        rings = geometry_data.get(
            "rings",
            []
        )


        polygons = []


        for ring in rings:

            if len(ring) < 4:
                continue

            try:

                poly = Polygon(
                    ring
                )

                if not poly.is_valid:

                    poly = poly.buffer(
                        0
                    )

                if not poly.is_empty:

                    polygons.append(
                        poly
                    )

            except Exception:

                pass


        if not polygons:
            continue


        geometry = unary_union(
            polygons
        )


        attrs = feature.get(
            "attributes",
            {}
        )


        record = {
            "test_parcel_id":
                f"P{i + 1:04d}",

            "geometry":
                geometry
        }


        for key, value in (
            attrs.items()
        ):

            record[
                str(key)
            ] = value


        records.append(
            record
        )


    return gpd.GeoDataFrame(
        records,
        geometry="geometry",
        crs="EPSG:4326"
    )


# ==========================================================
# ANALYZE
# ==========================================================

def analyze(buildings, parcels):

    if parcels.empty:

        return {
            "parcels": 0,
            "plot_like": 0,
            "site": 0,
            "large_survey": 0,
            "multi_building": 0,
            "no_reliable": len(buildings),
            "good_rate": 0
        }


    buildings_m = buildings.to_crs(
        TARGET_CRS
    )

    parcels_m = parcels.to_crs(
        TARGET_CRS
    )


    spatial_index = (
        parcels_m.sindex
    )


    matches = []


    # ------------------------------------------------------
    # BEST PARCEL PER BUILDING
    # ------------------------------------------------------

    for b_idx, building in (
        buildings_m.iterrows()
    ):

        geom = building.geometry

        area = float(
            geom.area
        )


        candidates = list(
            spatial_index.intersection(
                geom.bounds
            )
        )


        best = None


        for p_idx in candidates:

            parcel = (
                parcels_m.iloc[
                    p_idx
                ]
            )

            if not geom.intersects(
                parcel.geometry
            ):
                continue


            intersection = (
                geom.intersection(
                    parcel.geometry
                )
            )


            intersection_area = float(
                intersection.area
            )


            coverage = (

                intersection_area /
                area *
                100

                if area > 0

                else 0
            )


            if (
                best is None
                or
                intersection_area
                >
                best[
                    "intersection_area"
                ]
            ):

                best = {

                    "parcel_index":
                        p_idx,

                    "intersection_area":
                        intersection_area,

                    "coverage":
                        coverage,

                    "building_area":
                        area
                }


        if best is None:

            matches.append({
                "parcel_index":
                    None,

                "coverage":
                    0,

                "intersection_area":
                    0,

                "building_area":
                    area
            })

        else:

            matches.append(
                best
            )


    # ------------------------------------------------------
    # NUMBER OF BUILDINGS ASSOCIATED WITH PARCEL
    # ------------------------------------------------------

    parcel_counts = {}


    for match in matches:

        p_idx = match[
            "parcel_index"
        ]


        if (
            p_idx is not None
            and
            match["coverage"] >= 70
        ):

            parcel_counts[
                p_idx
            ] = (

                parcel_counts.get(
                    p_idx,
                    0
                )
                +
                1
            )


    counts = {

        "plot_like": 0,

        "site": 0,

        "large_survey": 0,

        "multi_building": 0,

        "no_reliable": 0
    }


    detail_records = []


    for number, match in enumerate(
        matches,
        start=1
    ):

        p_idx = match[
            "parcel_index"
        ]


        if (
            p_idx is None
            or
            match["coverage"] < 70
        ):

            counts[
                "no_reliable"
            ] += 1

            continue


        parcel = parcels_m.iloc[
            p_idx
        ]


        parcel_area = float(
            parcel.geometry.area
        )


        occupancy = (

            match[
                "intersection_area"
            ]
            /
            parcel_area
            *
            100

            if parcel_area > 0

            else 0
        )


        buildings_on_parcel = (
            parcel_counts.get(
                p_idx,
                0
            )
        )


        ratio = (

            parcel_area /
            match[
                "building_area"
            ]

            if match[
                "building_area"
            ] > 0

            else None
        )


        if buildings_on_parcel >= 2:

            classification = (
                "MULTI_BUILDING"
            )

            counts[
                "multi_building"
            ] += 1


        elif occupancy < 10:

            classification = (
                "LARGE_SURVEY"
            )

            counts[
                "large_survey"
            ] += 1


        elif occupancy < 20:

            classification = (
                "SITE"
            )

            counts[
                "site"
            ] += 1


        else:

            classification = (
                "PLOT_LIKE"
            )

            counts[
                "plot_like"
            ] += 1


        detail_records.append({

            "building":
                number,

            "coverage_pct":
                round(
                    match[
                        "coverage"
                    ],
                    2
                ),

            "occupancy_pct":
                round(
                    occupancy,
                    2
                ),

            "parcel_building_count":
                buildings_on_parcel,

            "parcel_building_ratio":
                (
                    round(
                        ratio,
                        2
                    )
                    if ratio is not None
                    else None
                ),

            "classification":
                classification
        })


    total = len(
        buildings
    )


    good = (
        counts[
            "plot_like"
        ]
        +
        counts[
            "site"
        ]
    )


    good_rate = (

        good /
        total *
        100

        if total

        else 0
    )


    return {

        "parcels":
            len(parcels),

        **counts,

        "good_rate":
            round(
                good_rate,
                2
            ),

        "details":
            detail_records
    }


# ==========================================================
# MAIN
# ==========================================================

print(
    "\n=== CADASTRAL LAYER COMPARISON ===\n"
)


buildings = load_buildings()


summary = []


for source in SOURCES:

    print(
        "\n----------------------------------------"
    )

    print(
        source["name"]
    )

    print(
        "----------------------------------------"
    )


    try:

        parcels = download_parcels(
            source
        )


        print(
            "Parcels returned:",
            len(parcels)
        )


        if not parcels.empty:

            parcels.to_file(

                OUT_DIR /
                f"{source['name'].lower()}.geojson",

                driver="GeoJSON"
            )


        result = analyze(
            buildings,
            parcels
        )


        print(
            "Plot-like:",
            result["plot_like"]
        )

        print(
            "Site:",
            result["site"]
        )

        print(
            "Large survey:",
            result["large_survey"]
        )

        print(
            "Multi-building:",
            result[
                "multi_building"
            ]
        )

        print(
            "No reliable:",
            result[
                "no_reliable"
            ]
        )

        print(
            "GOOD MATCH RATE:",
            f"{result['good_rate']}%"
        )


        summary.append({

            "source":
                source["name"],

            "parcels":
                result["parcels"],

            "plot_like":
                result["plot_like"],

            "site":
                result["site"],

            "large_survey":
                result[
                    "large_survey"
                ],

            "multi_building":
                result[
                    "multi_building"
                ],

            "no_reliable":
                result[
                    "no_reliable"
                ],

            "good_match_rate":
                result[
                    "good_rate"
                ]
        })


    except Exception as error:

        print(
            "FAILED:",
            error
        )


# ==========================================================
# FINAL
# ==========================================================

summary_df = pd.DataFrame(
    summary
)


if not summary_df.empty:

    summary_df = (
        summary_df.sort_values(
            "good_match_rate",
            ascending=False
        )
    )


    summary_df.to_csv(

        OUT_DIR /
        "layer_comparison.csv",

        index=False
    )


    print(
        "\n\n========================================"
    )

    print(
        "FINAL CADASTRAL SOURCE COMPARISON"
    )

    print(
        "========================================\n"
    )


    print(
        summary_df.to_string(
            index=False
        )
    )


print(
    "\nCADASTRAL LAYER TEST COMPLETE"
)