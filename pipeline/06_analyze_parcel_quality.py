from pathlib import Path

import geopandas as gpd
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

BUILDINGS_FILE = DATA / "all_buildings_processed.geojson"
PARCELS_FILE = DATA / "study_area_cadastral_parcels.geojson"

OUT_CSV = DATA / "all_parcel_quality_analysis.csv"
OUT_GEOJSON = DATA / "all_parcel_quality_analysis.geojson"


print("\n=== PARCEL QUALITY / CADASTRAL INTERPRETATION ANALYSIS ===\n")


# ==========================================================
# LOAD DATA
# ==========================================================

buildings = gpd.read_file(BUILDINGS_FILE)
parcels = gpd.read_file(PARCELS_FILE)

print(f"Buildings loaded: {len(buildings)}")
print(f"Parcels loaded:   {len(parcels)}")


# ==========================================================
# CRS
# ==========================================================

if buildings.crs is None:
    buildings = buildings.set_crs("EPSG:4326")

if parcels.crs is None:
    parcels = parcels.set_crs("EPSG:4326")


buildings_metric = buildings.to_crs("EPSG:32644")
parcels_metric = parcels.to_crs("EPSG:32644")


# ==========================================================
# PREPARE PARCEL LOOKUP
# ==========================================================

parcel_lookup = {}

for idx, parcel in parcels_metric.iterrows():

    parcel_id = parcel.get("parcel_id")

    if parcel_id is None or pd.isna(parcel_id):
        continue

    parcel_lookup[str(parcel_id)] = parcel


# ==========================================================
# COUNT BUILDINGS ASSOCIATED WITH EACH PARCEL
# ==========================================================

parcel_building_counts = {}

for _, building in buildings_metric.iterrows():

    matched_parcel_id = building.get("matched_parcel_id")

    if (
        matched_parcel_id is None
        or pd.isna(matched_parcel_id)
        or str(matched_parcel_id).strip() == ""
    ):
        continue

    key = str(matched_parcel_id)

    parcel_building_counts[key] = (
        parcel_building_counts.get(key, 0) + 1
    )


# ==========================================================
# ANALYSIS
# ==========================================================

records = []

classification_counts = {}


for idx, building in buildings_metric.iterrows():

    building_id = building.get("building_id")
    matched_parcel_id = building.get("matched_parcel_id")

    parcel_match_status = building.get("parcel_match_status")
    official_parcel_no = building.get("official_parcel_no")

    building_geometry = building.geometry

    building_area = float(building_geometry.area)

    # ------------------------------------------------------
    # NO MATCHED PARCEL
    # ------------------------------------------------------

    if (
        matched_parcel_id is None
        or pd.isna(matched_parcel_id)
        or str(matched_parcel_id).strip() == ""
        or str(matched_parcel_id) not in parcel_lookup
    ):

        classification = "NO_RELIABLE_MATCH"

        classification_counts[classification] = (
            classification_counts.get(classification, 0) + 1
        )

        records.append({

            "building_id": building_id,

            "matched_parcel_id": None,

            "official_parcel_no": (
                official_parcel_no
                if pd.notna(official_parcel_no)
                else None
            ),

            "parcel_match_status": parcel_match_status,

            "building_area_m2": round(building_area, 2),

            "parcel_area_m2": None,

            "intersection_area_m2": None,

            "building_covered_by_parcel_pct": 0.0,

            "parcel_occupied_by_building_pct": 0.0,

            "buildings_associated_with_parcel": 0,

            "parcel_area_to_building_area_ratio": None,

            "parcel_interpretation": classification,

            "interpretation_note":
                "No reliable cadastral parcel geometry associated.",

            "geometry": buildings.loc[idx].geometry
        })

        continue


    # ------------------------------------------------------
    # PARCEL GEOMETRY
    # ------------------------------------------------------

    parcel = parcel_lookup[
                str(matched_parcel_id)
            ]
        

    parcel_geometry = parcel.geometry

    parcel_area = float(parcel_geometry.area)


    # ------------------------------------------------------
    # INTERSECTION
    # ------------------------------------------------------

    intersection_geometry = (
        building_geometry.intersection(
            parcel_geometry
        )
    )

    intersection_area = float(
        intersection_geometry.area
    )


    # ======================================================
    # TWO IMPORTANT PERCENTAGES
    # ======================================================

    # How much of the building is inside the parcel?
    building_coverage_pct = (

        intersection_area
        / building_area
        * 100

        if building_area > 0
        else 0
    )


    # How much of the parcel is occupied by THIS building?
    parcel_occupancy_pct = (

        intersection_area
        / parcel_area
        * 100

        if parcel_area > 0
        else 0
    )


    # ======================================================
    # SIZE RATIO
    # ======================================================

    parcel_to_building_ratio = (

        parcel_area
        / building_area

        if building_area > 0
        else None
    )


    # ======================================================
    # BUILDINGS ASSOCIATED WITH THIS PARCEL
    # ======================================================

    buildings_on_parcel = (
        parcel_building_counts.get(
            str(matched_parcel_id),
            0
        )
    )


    # ======================================================
    # HEURISTIC INTERPRETATION
    #
    # This is NOT a legal classification.
    # It helps us understand the geometry.
    # ======================================================

    if building_coverage_pct < 70:

        classification = "NO_RELIABLE_MATCH"

        note = (
            "Less than 70% of the building footprint is "
            "covered by the associated cadastral polygon."
        )


    elif buildings_on_parcel >= 2:

        classification = "MULTI_BUILDING_PARCEL"

        note = (
            f"{buildings_on_parcel} buildings are associated "
            "with this cadastral polygon. It likely represents "
            "a larger survey/development parcel rather than a "
            "one-building property plot."
        )


    elif parcel_occupancy_pct < 10:

        classification = "LARGE_SURVEY_PARCEL"

        note = (
            "The building lies mainly inside the parcel, but "
            "occupies less than 10% of the parcel area. "
            "Treat as a large survey/site parcel."
        )


    elif parcel_occupancy_pct < 20:

        classification = "SITE_PARCEL"

        note = (
            "The building is spatially contained, but the "
            "cadastral polygon is substantially larger than "
            "the building footprint."
        )


    elif parcel_occupancy_pct <= 100:

        classification = "PLOT_LIKE_MATCH"

        note = (
            "The parcel size is reasonably comparable to the "
            "building/site footprint. Suitable for plot-like "
            "visual interpretation in the prototype."
        )


    else:

        classification = "AMBIGUOUS"

        note = (
            "Geometry produced an unusual area relationship "
            "and should be manually reviewed."
        )


    classification_counts[classification] = (
        classification_counts.get(classification, 0) + 1
    )


    # ======================================================
    # STORE RESULT
    # ======================================================

    records.append({

        "building_id": building_id,

        "matched_parcel_id": str(matched_parcel_id),

        "official_parcel_no": (
            official_parcel_no
            if pd.notna(official_parcel_no)
            else None
        ),

        "parcel_match_status": parcel_match_status,

        "building_area_m2": round(
            building_area,
            2
        ),

        "parcel_area_m2": round(
            parcel_area,
            2
        ),

        "intersection_area_m2": round(
            intersection_area,
            2
        ),

        "building_covered_by_parcel_pct": round(
            building_coverage_pct,
            2
        ),

        "parcel_occupied_by_building_pct": round(
            parcel_occupancy_pct,
            2
        ),

        "buildings_associated_with_parcel":
            buildings_on_parcel,

        "parcel_area_to_building_area_ratio": (
            round(
                parcel_to_building_ratio,
                2
            )
            if parcel_to_building_ratio is not None
            else None
        ),

        "parcel_interpretation":
            classification,

        "interpretation_note":
            note,

        # keep building geometry for map diagnostics
        "geometry":
            buildings.loc[idx].geometry
    })


# ==========================================================
# CREATE OUTPUT
# ==========================================================

result_gdf = gpd.GeoDataFrame(
    records,
    geometry="geometry",
    crs="EPSG:4326"
)


result_gdf.to_file(
    OUT_GEOJSON,
    driver="GeoJSON"
)


result_gdf.drop(
    columns="geometry"
).to_csv(
    OUT_CSV,
    index=False
)


# ==========================================================
# SUMMARY
# ==========================================================

print("\n=== CLASSIFICATION COUNTS ===")

for classification, count in sorted(
    classification_counts.items()
):

    print(
        f"{classification}: {count}"
    )


print("\n=== EXTREME LARGE PARCEL EXAMPLES ===")

valid = result_gdf[
    result_gdf[
        "parcel_area_to_building_area_ratio"
    ].notna()
].copy()


largest = valid.sort_values(
    "parcel_area_to_building_area_ratio",
    ascending=False
).head(10)


for _, row in largest.iterrows():

    print(
        f"{row['building_id']} | "
        f"Parcel {row['official_parcel_no']} | "
        f"Building {row['building_area_m2']} m² | "
        f"Parcel {row['parcel_area_m2']} m² | "
        f"Parcel/Building ratio "
        f"{row['parcel_area_to_building_area_ratio']}x | "
        f"Occupancy "
        f"{row['parcel_occupied_by_building_pct']}% | "
        f"{row['parcel_interpretation']}"
    )


print("\nSaved:")
print(OUT_CSV)
print(OUT_GEOJSON)

print("\nPARCEL QUALITY ANALYSIS: COMPLETE")