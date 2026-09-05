from pathlib import Path

import geopandas as gpd
import osmnx as ox
import pandas as pd


# ==========================================================
# PATHS
# ==========================================================

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

BUILDINGS_FILE = DATA / "all_buildings_processed.geojson"

OUT_DIR = DATA / "osm_site_boundary_check"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# HERO BUILDINGS
# ==========================================================

HERO_IDS = [
    "B0595",
    "B0612",
    "B0589",
]


# ==========================================================
# OSM TAGS TO INVESTIGATE
#
# We are looking for possible:
# - site boundaries
# - commercial areas
# - campuses
# - amenities
# - office complexes
# - other polygon features
# ==========================================================

OSM_TAGS = {
    "building": True,
    "landuse": True,
    "amenity": True,
    "office": True,
    "leisure": True,
    "tourism": True,
    "shop": True,
    "place": True,
    "boundary": True,
    "man_made": True,
}


TARGET_CRS = "EPSG:32644"

SEARCH_BUFFER_M = 120


# ==========================================================
# LOAD BUILDINGS
# ==========================================================

print("\n=== OSM SITE / BOUNDARY INVESTIGATION ===\n")


buildings = gpd.read_file(
    BUILDINGS_FILE
)


if buildings.crs is None:
    buildings = buildings.set_crs(
        "EPSG:4326"
    )


buildings = buildings.to_crs(
    "EPSG:4326"
)


print(
    "Buildings loaded:",
    len(buildings)
)


all_candidate_records = []


# ==========================================================
# ANALYZE EACH HERO
# ==========================================================

for hero_id in HERO_IDS:

    print(
        "\n=================================================="
    )

    print(
        f"BUILDING: {hero_id}"
    )

    print(
        "=================================================="
    )


    hero = buildings[
        buildings["building_id"] == hero_id
    ]


    if hero.empty:

        print(
            "Building not found."
        )

        continue


    hero = hero.iloc[0]


    # ------------------------------------------------------
    # HERO GEOMETRY IN METRES
    # ------------------------------------------------------

    hero_gdf = gpd.GeoDataFrame(
        [hero],
        geometry="geometry",
        crs="EPSG:4326"
    )


    hero_metric = hero_gdf.to_crs(
        TARGET_CRS
    )


    hero_geom_metric = (
        hero_metric.geometry.iloc[0]
    )


    hero_area = float(
        hero_geom_metric.area
    )


    print(
        f"Building area: {hero_area:.2f} m²"
    )


    # ------------------------------------------------------
    # CREATE SEARCH AREA
    # ------------------------------------------------------

    search_geom_metric = (
        hero_geom_metric.buffer(
            SEARCH_BUFFER_M
        )
    )


    search_area = gpd.GeoDataFrame(
        {"id": [1]},
        geometry=[search_geom_metric],
        crs=TARGET_CRS
    ).to_crs(
        "EPSG:4326"
    )


    search_polygon = (
        search_area.geometry.iloc[0]
    )


    # ------------------------------------------------------
    # QUERY OSM
    # ------------------------------------------------------

    print(
        "Querying nearby OSM polygon features..."
    )


    try:

        features = ox.features_from_polygon(
            search_polygon,
            tags=OSM_TAGS
        )

    except Exception as error:

        print(
            "OSM query failed:",
            error
        )

        continue


    if features.empty:

        print(
            "No nearby OSM features found."
        )

        continue


    # ------------------------------------------------------
    # KEEP POLYGONS ONLY
    # ------------------------------------------------------

    features = features[
        features.geometry.geom_type.isin(
            [
                "Polygon",
                "MultiPolygon"
            ]
        )
    ].copy()


    print(
        "Polygon features found:",
        len(features)
    )


    if features.empty:
        continue


    features = features.reset_index()


    # ------------------------------------------------------
    # METRIC VERSION
    # ------------------------------------------------------

    features_metric = features.to_crs(
        TARGET_CRS
    )


    hero_records = []


    # ======================================================
    # INSPECT EVERY NEARBY POLYGON
    # ======================================================

    for idx, feature in (
        features_metric.iterrows()
    ):

        geometry = feature.geometry


        if geometry is None:
            continue


        if geometry.is_empty:
            continue


        feature_area = float(
            geometry.area
        )


        # --------------------------------------------------
        # SPATIAL RELATIONSHIP
        # --------------------------------------------------

        intersects = geometry.intersects(
            hero_geom_metric
        )


        contains_building = geometry.contains(
            hero_geom_metric
        )


        building_within = hero_geom_metric.within(
            geometry
        )


        intersection_area = float(

            geometry.intersection(
                hero_geom_metric
            ).area

        ) if intersects else 0.0


        building_coverage_pct = (

            intersection_area
            /
            hero_area
            *
            100

            if hero_area > 0
            else 0
        )


        area_ratio = (

            feature_area
            /
            hero_area

            if hero_area > 0
            else None
        )


        distance_m = float(
            geometry.distance(
                hero_geom_metric
            )
        )


        # --------------------------------------------------
        # OSM ATTRIBUTES
        # --------------------------------------------------

        original = features.iloc[idx]


        osm_type = (
            original.get(
                "element_type",
                ""
            )
        )


        osm_id = (
            original.get(
                "osmid",
                original.get(
                    "id",
                    ""
                )
            )
        )


        name = original.get(
            "name"
        )


        building_tag = original.get(
            "building"
        )


        landuse = original.get(
            "landuse"
        )


        amenity = original.get(
            "amenity"
        )


        office = original.get(
            "office"
        )


        leisure = original.get(
            "leisure"
        )


        tourism = original.get(
            "tourism"
        )


        boundary = original.get(
            "boundary"
        )


        place = original.get(
            "place"
        )


        man_made = original.get(
            "man_made"
        )


        # --------------------------------------------------
        # CANDIDATE SCORE
        #
        # We want polygons that:
        # - contain most/all of the building
        # - are not absurdly huge
        # - look like a site around the building
        # --------------------------------------------------

        score = 0.0


        score += min(
            building_coverage_pct,
            100
        ) * 0.60


        if area_ratio is not None:

            if 1.05 <= area_ratio <= 3:
                score += 35

            elif area_ratio <= 6:
                score += 25

            elif area_ratio <= 12:
                score += 15

            elif area_ratio <= 25:
                score += 5


        if contains_building:
            score += 10


        # Penalize the exact building footprint itself
        if (
            building_tag is not None
            and
            area_ratio is not None
            and
            0.90 <= area_ratio <= 1.10
        ):

            score -= 30


        score = round(
            score,
            2
        )


        record = {

            "hero_building_id":
                hero_id,

            "osm_type":
                osm_type,

            "osm_id":
                osm_id,

            "name":
                name,

            "building":
                building_tag,

            "landuse":
                landuse,

            "amenity":
                amenity,

            "office":
                office,

            "leisure":
                leisure,

            "tourism":
                tourism,

            "boundary":
                boundary,

            "place":
                place,

            "man_made":
                man_made,

            "feature_area_m2":
                round(
                    feature_area,
                    2
                ),

            "building_area_m2":
                round(
                    hero_area,
                    2
                ),

            "area_ratio":
                round(
                    area_ratio,
                    2
                )
                if area_ratio is not None
                else None,

            "intersects_building":
                intersects,

            "contains_building":
                contains_building,

            "building_within":
                building_within,

            "building_coverage_pct":
                round(
                    building_coverage_pct,
                    2
                ),

            "distance_m":
                round(
                    distance_m,
                    2
                ),

            "candidate_score":
                score,

            "geometry":
                features.iloc[idx].geometry
        }


        hero_records.append(
            record
        )


    # ======================================================
    # HERO OUTPUT
    # ======================================================

    hero_candidates = gpd.GeoDataFrame(
        hero_records,
        geometry="geometry",
        crs="EPSG:4326"
    )


    if hero_candidates.empty:

        print(
            "No polygon candidates."
        )

        continue


    hero_candidates = (
        hero_candidates.sort_values(
            "candidate_score",
            ascending=False
        )
    )


    hero_candidates.to_file(

        OUT_DIR /
        f"{hero_id}_osm_boundary_candidates.geojson",

        driver="GeoJSON"
    )


    hero_candidates.drop(
        columns="geometry"
    ).to_csv(

        OUT_DIR /
        f"{hero_id}_osm_boundary_candidates.csv",

        index=False
    )


    all_candidate_records.extend(
        hero_candidates.to_dict(
            "records"
        )
    )


    # ======================================================
    # PRINT TOP CANDIDATES
    # ======================================================

    print(
        "\nTOP POSSIBLE SITE / BOUNDARY POLYGONS:\n"
    )


    top = hero_candidates.head(
        10
    )


    for _, row in top.iterrows():

        print(
            "----------------------------------------"
        )

        print(
            f"Score: {row['candidate_score']}"
        )

        print(
            f"OSM type/id: "
            f"{row['osm_type']} / "
            f"{row['osm_id']}"
        )

        print(
            f"Name: {row['name']}"
        )

        print(
            f"building: {row['building']}"
        )

        print(
            f"landuse: {row['landuse']}"
        )

        print(
            f"amenity: {row['amenity']}"
        )

        print(
            f"office: {row['office']}"
        )

        print(
            f"boundary: {row['boundary']}"
        )

        print(
            f"Area ratio: "
            f"{row['area_ratio']}x"
        )

        print(
            f"Building covered: "
            f"{row['building_coverage_pct']}%"
        )

        print(
            f"Contains building: "
            f"{row['contains_building']}"
        )

        print(
            f"Distance: "
            f"{row['distance_m']} m"
        )


# ==========================================================
# FINAL
# ==========================================================

print(
    "\n=================================================="
)

print(
    "OSM SITE / BOUNDARY INVESTIGATION COMPLETE"
)

print(
    "=================================================="
)


print(
    "\nOutputs saved in:"
)

print(
    OUT_DIR
)