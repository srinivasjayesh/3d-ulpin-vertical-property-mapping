from pathlib import Path
import re
import time

import geopandas as gpd
import osmnx as ox
import pandas as pd
import requests

from shapely.geometry import Polygon
from shapely.ops import unary_union


# ==========================================================
# PATHS
# ==========================================================

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

SCOUT_DIR = DATA / "study_area_scouting"
SCOUT_DIR.mkdir(parents=True, exist_ok=True)

SUMMARY_FILE = SCOUT_DIR / "study_area_scout_summary.csv"


# ==========================================================
# SETTINGS
# ==========================================================

# Small area deliberately.
# We want GOOD DATA, not maximum building count.
RADIUS_M = 600

TARGET_CRS = "EPSG:32644"

BHUNAKSHA_URL = (
    "https://tgrac.telangana.gov.in/arcgis/rest/services/"
    "Bhunaksha_Folder/Bhunaksha_query/MapServer/0/query"
)


CANDIDATE_AREAS = [
    "Kondapur, Hyderabad, Telangana, India",
    "Nallagandla, Hyderabad, Telangana, India",
    "Tellapur, Telangana, India",
    "Manikonda, Hyderabad, Telangana, India",
    "Miyapur, Hyderabad, Telangana, India",
]


# ==========================================================
# HELPERS
# ==========================================================

def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def create_bbox(lat, lon, radius_m):

    center = gpd.GeoDataFrame(
        {"name": ["center"]},
        geometry=gpd.points_from_xy([lon], [lat]),
        crs="EPSG:4326"
    )

    center_metric = center.to_crs(TARGET_CRS)

    search_area = center_metric.geometry.iloc[0].buffer(radius_m)

    search_gdf = gpd.GeoDataFrame(
        {"name": ["search_area"]},
        geometry=[search_area],
        crs=TARGET_CRS
    ).to_crs("EPSG:4326")

    xmin, ymin, xmax, ymax = search_gdf.total_bounds

    return xmin, ymin, xmax, ymax


# ==========================================================
# DOWNLOAD OSM BUILDINGS
# ==========================================================

def get_osm_buildings(lat, lon):

    print("  Downloading OSM buildings...")

    gdf = ox.features_from_point(
        (lat, lon),
        tags={"building": True},
        dist=RADIUS_M
    )

    if gdf.empty:
        return gpd.GeoDataFrame(
            geometry=[],
            crs="EPSG:4326"
        )

    gdf = gdf[
        gdf.geometry.geom_type.isin(
            ["Polygon", "MultiPolygon"]
        )
    ].copy()

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    gdf = gdf.to_crs("EPSG:4326")

    gdf = gdf.reset_index()

    gdf["scout_building_id"] = [
        f"B{i:04d}"
        for i in range(1, len(gdf) + 1)
    ]

    return gdf


# ==========================================================
# DOWNLOAD BHUNAKSHA PARCELS
# ==========================================================

def get_bhunaksha_parcels(lat, lon):

    print("  Querying Telangana BhuNaksha...")

    xmin, ymin, xmax, ymax = create_bbox(
        lat,
        lon,
        RADIUS_M
    )

    envelope = (
        f"{xmin},{ymin},{xmax},{ymax}"
    )

    params = {
        "where": "1=1",
        "geometry": envelope,
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "resultRecordCount": "2000",
        "f": "json"
    }

    response = requests.get(
        BHUNAKSHA_URL,
        params=params,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise RuntimeError(
            f"BhuNaksha API error: {data['error']}"
        )

    features = data.get(
        "features",
        []
    )

    parcel_records = []

    for index, feature in enumerate(features):

        geometry_data = feature.get(
            "geometry",
            {}
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
                polygon = Polygon(ring)

                if not polygon.is_valid:
                    polygon = polygon.buffer(0)

                if not polygon.is_empty:
                    polygons.append(polygon)

            except Exception:
                continue

        if not polygons:
            continue

        geometry = unary_union(polygons)

        attributes = feature.get(
            "attributes",
            {}
        )

        record = {
            "scout_parcel_id": f"P{index + 1:04d}",
            "geometry": geometry
        }

        # Preserve returned BhuNaksha attributes
        for key, value in attributes.items():
            record[str(key)] = value

        parcel_records.append(record)

    parcels = gpd.GeoDataFrame(
        parcel_records,
        geometry="geometry",
        crs="EPSG:4326"
    )

    return parcels


# ==========================================================
# MATCH BUILDINGS TO PARCELS
# ==========================================================

def analyze_matches(buildings, parcels):

    if buildings.empty:

        return None, {
            "total_buildings": 0,
            "total_parcels": len(parcels),
            "plot_like": 0,
            "site_parcel": 0,
            "large_survey": 0,
            "multi_building": 0,
            "no_reliable": 0,
            "good_match_rate_pct": 0,
            "score": 0
        }

    buildings_m = buildings.to_crs(
        TARGET_CRS
    ).copy()

    parcels_m = parcels.to_crs(
        TARGET_CRS
    ).copy()

    if parcels_m.empty:

        return None, {
            "total_buildings": len(buildings),
            "total_parcels": 0,
            "plot_like": 0,
            "site_parcel": 0,
            "large_survey": 0,
            "multi_building": 0,
            "no_reliable": len(buildings),
            "good_match_rate_pct": 0,
            "score": 0
        }


    # ------------------------------------------------------
    # FIRST PASS:
    # find best parcel for every building
    # ------------------------------------------------------

    assignments = []

    parcel_spatial_index = parcels_m.sindex

    for building_index, building in buildings_m.iterrows():

        building_geom = building.geometry

        building_area = float(
            building_geom.area
        )

        candidate_indices = list(
            parcel_spatial_index.intersection(
                building_geom.bounds
            )
        )

        best = None

        for parcel_index in candidate_indices:

            parcel = parcels_m.iloc[
                parcel_index
            ]

            parcel_geom = parcel.geometry

            if not building_geom.intersects(
                parcel_geom
            ):
                continue

            intersection = (
                building_geom.intersection(
                    parcel_geom
                )
            )

            intersection_area = float(
                intersection.area
            )

            if building_area <= 0:
                continue

            building_coverage = (
                intersection_area /
                building_area *
                100
            )

            if (
                best is None
                or
                intersection_area >
                best["intersection_area_m2"]
            ):
                best = {
                    "parcel_index": parcel_index,
                    "intersection_area_m2":
                        intersection_area,
                    "building_coverage_pct":
                        building_coverage
                }

        if best is None:

            assignments.append({
                "building_index":
                    building_index,
                "parcel_index":
                    None,
                "intersection_area_m2":
                    0,
                "building_coverage_pct":
                    0
            })

        else:

            assignments.append({
                "building_index":
                    building_index,
                **best
            })


    # ------------------------------------------------------
    # COUNT HOW MANY BUILDINGS USE EACH PARCEL
    # ------------------------------------------------------

    parcel_counts = {}

    for item in assignments:

        parcel_index = item[
            "parcel_index"
        ]

        if parcel_index is None:
            continue

        # Only count reasonably valid associations
        if item[
            "building_coverage_pct"
        ] < 70:
            continue

        parcel_counts[
            parcel_index
        ] = (
            parcel_counts.get(
                parcel_index,
                0
            ) + 1
        )


    # ------------------------------------------------------
    # SECOND PASS:
    # classify parcel relationship
    # ------------------------------------------------------

    records = []

    class_counts = {
        "PLOT_LIKE_MATCH": 0,
        "SITE_PARCEL": 0,
        "LARGE_SURVEY_PARCEL": 0,
        "MULTI_BUILDING_PARCEL": 0,
        "NO_RELIABLE_MATCH": 0
    }

    ratios = []

    occupancies = []

    for item in assignments:

        building = buildings_m.loc[
            item["building_index"]
        ]

        building_area = float(
            building.geometry.area
        )

        parcel_index = item[
            "parcel_index"
        ]

        coverage = item[
            "building_coverage_pct"
        ]


        # --------------------------------------------------
        # NO RELIABLE MATCH
        # --------------------------------------------------

        if (
            parcel_index is None
            or
            coverage < 70
        ):

            classification = (
                "NO_RELIABLE_MATCH"
            )

            class_counts[
                classification
            ] += 1

            records.append({
                "scout_building_id":
                    building[
                        "scout_building_id"
                    ],
                "matched_parcel_id":
                    None,
                "building_area_m2":
                    round(
                        building_area,
                        2
                    ),
                "parcel_area_m2":
                    None,
                "building_coverage_pct":
                    round(
                        coverage,
                        2
                    ),
                "parcel_occupancy_pct":
                    0,
                "parcel_building_count":
                    0,
                "parcel_to_building_ratio":
                    None,
                "classification":
                    classification
            })

            continue


        parcel = parcels_m.iloc[
            parcel_index
        ]

        parcel_area = float(
            parcel.geometry.area
        )

        intersection_area = item[
            "intersection_area_m2"
        ]

        occupancy = (
            intersection_area /
            parcel_area *
            100
            if parcel_area > 0
            else 0
        )

        ratio = (
            parcel_area /
            building_area
            if building_area > 0
            else None
        )

        buildings_on_parcel = (
            parcel_counts.get(
                parcel_index,
                0
            )
        )

        if ratio is not None:
            ratios.append(ratio)

        occupancies.append(
            occupancy
        )


        # --------------------------------------------------
        # CLASSIFICATION
        # --------------------------------------------------

        if buildings_on_parcel >= 2:

            classification = (
                "MULTI_BUILDING_PARCEL"
            )

        elif occupancy < 10:

            classification = (
                "LARGE_SURVEY_PARCEL"
            )

        elif occupancy < 20:

            classification = (
                "SITE_PARCEL"
            )

        else:

            classification = (
                "PLOT_LIKE_MATCH"
            )


        class_counts[
            classification
        ] += 1


        records.append({
            "scout_building_id":
                building[
                    "scout_building_id"
                ],

            "matched_parcel_id":
                parcel[
                    "scout_parcel_id"
                ],

            "building_area_m2":
                round(
                    building_area,
                    2
                ),

            "parcel_area_m2":
                round(
                    parcel_area,
                    2
                ),

            "building_coverage_pct":
                round(
                    coverage,
                    2
                ),

            "parcel_occupancy_pct":
                round(
                    occupancy,
                    2
                ),

            "parcel_building_count":
                buildings_on_parcel,

            "parcel_to_building_ratio":
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


    # ------------------------------------------------------
    # SCORE
    # ------------------------------------------------------

    total = len(buildings)

    good = (
        class_counts[
            "PLOT_LIKE_MATCH"
        ]
        +
        class_counts[
            "SITE_PARCEL"
        ]
    )

    unreliable = class_counts[
        "NO_RELIABLE_MATCH"
    ]

    multi = class_counts[
        "MULTI_BUILDING_PARCEL"
    ]


    good_rate = (
        good / total
        if total
        else 0
    )

    reliable_rate = (
        1 -
        unreliable / total
        if total
        else 0
    )

    non_multi_rate = (
        1 -
        multi / total
        if total
        else 0
    )


    score = 100 * (
        0.60 * good_rate
        +
        0.25 * reliable_rate
        +
        0.15 * non_multi_rate
    )


    summary = {
        "total_buildings":
            total,

        "total_parcels":
            len(parcels),

        "plot_like":
            class_counts[
                "PLOT_LIKE_MATCH"
            ],

        "site_parcel":
            class_counts[
                "SITE_PARCEL"
            ],

        "large_survey":
            class_counts[
                "LARGE_SURVEY_PARCEL"
            ],

        "multi_building":
            class_counts[
                "MULTI_BUILDING_PARCEL"
            ],

        "no_reliable":
            class_counts[
                "NO_RELIABLE_MATCH"
            ],

        "good_match_rate_pct":
            round(
                good_rate * 100,
                2
            ),

        "median_parcel_building_ratio":
            round(
                pd.Series(
                    ratios
                ).median(),
                2
            )
            if ratios
            else None,

        "median_parcel_occupancy_pct":
            round(
                pd.Series(
                    occupancies
                ).median(),
                2
            )
            if occupancies
            else None,

        "score":
            round(
                score,
                2
            )
    }


    result_df = pd.DataFrame(
        records
    )

    return result_df, summary


# ==========================================================
# MAIN
# ==========================================================

print(
    "\n=== 3D ULPIN STUDY AREA SCOUT ===\n"
)

all_summaries = []


for area_name in CANDIDATE_AREAS:

    print(
        "\n=================================================="
    )

    print(
        f"SCOUTING: {area_name}"
    )

    print(
        "=================================================="
    )

    slug = slugify(
        area_name.split(",")[0]
    )

    area_folder = (
        SCOUT_DIR / slug
    )

    area_folder.mkdir(
        parents=True,
        exist_ok=True
    )


    try:

        # --------------------------------------------------
        # GEOCODE
        # --------------------------------------------------

        print(
            "  Geocoding..."
        )

        lat, lon = ox.geocode(
            area_name
        )

        print(
            f"  Center: {lat:.6f}, {lon:.6f}"
        )


        # --------------------------------------------------
        # BUILDINGS
        # --------------------------------------------------

        buildings = get_osm_buildings(
            lat,
            lon
        )

        print(
            f"  Buildings: {len(buildings)}"
        )


        # --------------------------------------------------
        # PARCELS
        # --------------------------------------------------

        parcels = get_bhunaksha_parcels(
            lat,
            lon
        )

        print(
            f"  Parcels: {len(parcels)}"
        )


        # --------------------------------------------------
        # SAVE RAW SCOUT DATA
        # --------------------------------------------------

        if not buildings.empty:

            buildings.to_file(
                area_folder /
                "buildings.geojson",
                driver="GeoJSON"
            )


        if not parcels.empty:

            parcels.to_file(
                area_folder /
                "parcels.geojson",
                driver="GeoJSON"
            )


        # --------------------------------------------------
        # ANALYZE
        # --------------------------------------------------

        matches, summary = (
            analyze_matches(
                buildings,
                parcels
            )
        )


        if matches is not None:

            matches.to_csv(
                area_folder /
                "parcel_match_analysis.csv",
                index=False
            )


        summary["area"] = (
            area_name.split(",")[0]
        )

        summary["latitude"] = (
            round(lat, 6)
        )

        summary["longitude"] = (
            round(lon, 6)
        )

        all_summaries.append(
            summary
        )


        print(
            "\n  RESULTS"
        )

        print(
            f"  Plot-like:        "
            f"{summary['plot_like']}"
        )

        print(
            f"  Site parcels:     "
            f"{summary['site_parcel']}"
        )

        print(
            f"  Large survey:     "
            f"{summary['large_survey']}"
        )

        print(
            f"  Multi-building:   "
            f"{summary['multi_building']}"
        )

        print(
            f"  No reliable:      "
            f"{summary['no_reliable']}"
        )

        print(
            f"  Good match rate:  "
            f"{summary['good_match_rate_pct']}%"
        )

        print(
            f"  SCORE:            "
            f"{summary['score']}/100"
        )


    except Exception as error:

        print(
            f"\n  FAILED: {error}"
        )

        all_summaries.append({
            "area":
                area_name.split(",")[0],

            "latitude":
                None,

            "longitude":
                None,

            "total_buildings":
                0,

            "total_parcels":
                0,

            "plot_like":
                0,

            "site_parcel":
                0,

            "large_survey":
                0,

            "multi_building":
                0,

            "no_reliable":
                0,

            "good_match_rate_pct":
                0,

            "median_parcel_building_ratio":
                None,

            "median_parcel_occupancy_pct":
                None,

            "score":
                0,

            "error":
                str(error)
        })


    # Avoid hammering external services
    time.sleep(2)


# ==========================================================
# FINAL RANKING
# ==========================================================

summary_df = pd.DataFrame(
    all_summaries
)


summary_df = summary_df.sort_values(
    "score",
    ascending=False
)


summary_df.to_csv(
    SUMMARY_FILE,
    index=False
)


print(
    "\n\n=================================================="
)

print(
    "FINAL STUDY AREA RANKING"
)

print(
    "==================================================\n"
)


columns = [
    "area",
    "total_buildings",
    "total_parcels",
    "plot_like",
    "site_parcel",
    "multi_building",
    "no_reliable",
    "good_match_rate_pct",
    "score"
]


print(
    summary_df[
        columns
    ].to_string(
        index=False
    )
)


print(
    "\nSaved:"
)

print(
    SUMMARY_FILE
)


print(
    "\nSTUDY AREA SCOUT: COMPLETE"
)