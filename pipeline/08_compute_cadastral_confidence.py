from pathlib import Path
import shutil

import geopandas as gpd
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

BUILDINGS_FILE = DATA / "all_buildings_processed.geojson"
BUILDINGS_CSV = DATA / "all_buildings_processed.csv"

BACKUP_FILE = DATA / "all_buildings_processed_before_confidence.geojson"


print("\n=== CADASTRAL MATCH CONFIDENCE SCORING ===\n")


# ==========================================================
# LOAD
# ==========================================================

if not BUILDINGS_FILE.exists():
    raise FileNotFoundError(BUILDINGS_FILE)


if not BACKUP_FILE.exists():

    shutil.copy2(
        BUILDINGS_FILE,
        BACKUP_FILE
    )

    print(
        "Backup created:",
        BACKUP_FILE
    )


buildings = gpd.read_file(
    BUILDINGS_FILE
)


print(
    "Buildings loaded:",
    len(buildings)
)


# ==========================================================
# HELPERS
# ==========================================================

def safe_number(value, default=0.0):

    try:

        if pd.isna(value):
            return default

        return float(value)

    except Exception:

        return default


# ==========================================================
# RATIO SCORE
#
# Smaller parcel/building ratio generally means the parcel
# is more comparable to the selected building/site.
# ==========================================================

def ratio_score(ratio):

    ratio = safe_number(
        ratio,
        None
    )

    if ratio is None:
        return 0


    if ratio <= 3:
        return 100

    if ratio <= 5:
        return 90

    if ratio <= 8:
        return 75

    if ratio <= 15:
        return 55

    if ratio <= 50:
        return 35

    if ratio <= 200:
        return 15

    return 5


# ==========================================================
# SHARED PARCEL SCORE
# ==========================================================

def shared_parcel_score(count):

    count = safe_number(
        count,
        0
    )


    if count <= 0:
        return 0

    if count == 1:
        return 100

    if count == 2:
        return 55

    if count <= 5:
        return 35

    if count <= 10:
        return 20

    return 5


# ==========================================================
# INTERPRETATION SCORE
# ==========================================================

def interpretation_score(
    interpretation
):

    mapping = {

        "PLOT_LIKE_MATCH":
            100,

        "SITE_PARCEL":
            80,

        "LARGE_SURVEY_PARCEL":
            45,

        "MULTI_BUILDING_PARCEL":
            25,

        "NO_RELIABLE_MATCH":
            0
    }


    return mapping.get(
        interpretation,
        0
    )


# ==========================================================
# INTERPRETATION CAPS
#
# Very important:
# even if geometry coverage is numerically high,
# a multi-building survey parcel should never receive
# a "very good" individual property-boundary score.
# ==========================================================

def interpretation_cap(
    interpretation
):

    mapping = {

        "PLOT_LIKE_MATCH":
            100,

        "SITE_PARCEL":
            88,

        "LARGE_SURVEY_PARCEL":
            55,

        "MULTI_BUILDING_PARCEL":
            45,

        "NO_RELIABLE_MATCH":
            25
    }


    return mapping.get(
        interpretation,
        25
    )


# ==========================================================
# CONFIDENCE LABEL
# ==========================================================

def confidence_label(score):

    if score >= 85:
        return "VERY_GOOD_ESTIMATE"

    if score >= 70:
        return "GOOD_ESTIMATE"

    if score >= 50:
        return "MODERATE_ESTIMATE"

    if score >= 30:
        return "LOW_CONFIDENCE"

    return "UNRELIABLE"


# ==========================================================
# HUMAN LABEL
# ==========================================================

def confidence_text(label):

    mapping = {

        "VERY_GOOD_ESTIMATE":
            "Very good estimate",

        "GOOD_ESTIMATE":
            "Good estimate",

        "MODERATE_ESTIMATE":
            "Moderate estimate",

        "LOW_CONFIDENCE":
            "Low confidence",

        "UNRELIABLE":
            "Unreliable"
    }


    return mapping.get(
        label,
        "Unknown"
    )


# ==========================================================
# UI COLOUR CLASS
#
# These are semantic names.
# Actual CSS colours will be controlled in the frontend.
# ==========================================================

def confidence_color_class(label):

    if label in (
        "VERY_GOOD_ESTIMATE",
        "GOOD_ESTIMATE"
    ):

        return "GOOD"

    if label == "MODERATE_ESTIMATE":

        return "MODERATE"

    if label == "LOW_CONFIDENCE":

        return "LOW"

    return "UNRELIABLE"


# ==========================================================
# PROPER CADASTRAL LABEL
# ==========================================================

def boundary_label(
    interpretation
):

    mapping = {

        "PLOT_LIKE_MATCH":
            "Plot-like cadastral boundary",

        "SITE_PARCEL":
            "Site / development parcel",

        "LARGE_SURVEY_PARCEL":
            "Large survey parcel — context only",

        "MULTI_BUILDING_PARCEL":
            "Multi-building survey parcel — not individual property boundary",

        "NO_RELIABLE_MATCH":
            "Individual property boundary unavailable"
    }


    return mapping.get(
        interpretation,
        "Cadastral relationship unclassified"
    )


# ==========================================================
# VISIBILITY
# ==========================================================

def parcel_visibility(
    interpretation
):

    if interpretation == "PLOT_LIKE_MATCH":
        return "SHOW"

    if interpretation == "SITE_PARCEL":
        return "SHOW_SUBTLE"

    if interpretation in (
        "LARGE_SURVEY_PARCEL",
        "MULTI_BUILDING_PARCEL"
    ):
        return "OPTIONAL_CONTEXT"

    return "HIDE"


# ==========================================================
# SCORE EACH BUILDING
# ==========================================================

scores = []
labels = []
texts = []
colors = []
boundary_labels = []
visibility_modes = []
basis_notes = []


for _, row in buildings.iterrows():

    coverage = safe_number(
        row.get(
            "building_covered_by_parcel_pct"
        )
    )

    ratio = row.get(
        "parcel_area_to_building_area_ratio"
    )

    building_count = row.get(
        "buildings_associated_with_parcel"
    )

    interpretation = row.get(
        "parcel_interpretation"
    )


    # ------------------------------------------------------
    # COMPONENTS
    # ------------------------------------------------------

    coverage_component = (
        max(
            0,
            min(
                coverage,
                100
            )
        )
    )

    ratio_component = (
        ratio_score(
            ratio
        )
    )

    shared_component = (
        shared_parcel_score(
            building_count
        )
    )

    interpretation_component = (
        interpretation_score(
            interpretation
        )
    )


    # ------------------------------------------------------
    # WEIGHTED RAW SCORE
    # ------------------------------------------------------

    raw_score = (

        0.40 *
        coverage_component

        +

        0.20 *
        ratio_component

        +

        0.20 *
        shared_component

        +

        0.20 *
        interpretation_component
    )


    # ------------------------------------------------------
    # SEMANTIC CAP
    # ------------------------------------------------------

    cap = interpretation_cap(
        interpretation
    )

    final_score = min(
        raw_score,
        cap
    )


    final_score = round(
        final_score,
        1
    )


    label = confidence_label(
        final_score
    )


    scores.append(
        final_score
    )

    labels.append(
        label
    )

    texts.append(
        confidence_text(
            label
        )
    )

    colors.append(
        confidence_color_class(
            label
        )
    )

    boundary_labels.append(
        boundary_label(
            interpretation
        )
    )

    visibility_modes.append(
        parcel_visibility(
            interpretation
        )
    )


    basis_notes.append(

        (
            f"Score derived from building coverage "
            f"({coverage_component:.1f}%), "
            f"parcel/building size relationship, "
            f"number of associated buildings, and "
            f"parcel interpretation. "
            f"This is a prototype geometric confidence score, "
            f"not survey accuracy."
        )
    )


# ==========================================================
# ADD FIELDS
# ==========================================================

buildings[
    "cadastral_confidence_score"
] = scores


buildings[
    "cadastral_confidence_label"
] = labels


buildings[
    "cadastral_confidence_text"
] = texts


buildings[
    "cadastral_confidence_color"
] = colors


buildings[
    "cadastral_boundary_label"
] = boundary_labels


buildings[
    "parcel_visibility_mode"
] = visibility_modes


buildings[
    "cadastral_confidence_basis"
] = basis_notes


# ==========================================================
# VALIDATION
# ==========================================================

if len(buildings) != 635:

    raise ValueError(
        f"Expected 635 buildings, got {len(buildings)}"
    )


duplicates = int(
    buildings[
        "building_id"
    ].duplicated().sum()
)


if duplicates != 0:

    raise ValueError(
        f"Duplicate building IDs: {duplicates}"
    )


# ==========================================================
# SAVE
# ==========================================================

buildings.to_file(

    BUILDINGS_FILE,

    driver="GeoJSON"
)


buildings.drop(
    columns="geometry"
).to_csv(

    BUILDINGS_CSV,

    index=False
)


# ==========================================================
# SUMMARY
# ==========================================================

print(
    "\n=== CONFIDENCE LABEL COUNTS ==="
)


print(

    buildings[
        "cadastral_confidence_text"
    ].value_counts()
)


print(
    "\n=== PARCEL VISIBILITY COUNTS ==="
)


print(

    buildings[
        "parcel_visibility_mode"
    ].value_counts()
)


print(
    "\n=== HERO BUILDINGS ==="
)


hero_ids = [
    "B0595",
    "B0612",
    "B0589"
]


hero_columns = [

    "building_id",

    "official_parcel_no",

    "parcel_interpretation",

    "cadastral_boundary_label",

    "building_covered_by_parcel_pct",

    "parcel_occupied_by_building_pct",

    "parcel_area_to_building_area_ratio",

    "cadastral_confidence_score",

    "cadastral_confidence_text",

    "parcel_visibility_mode"
]


heroes = buildings[
    buildings[
        "building_id"
    ].isin(
        hero_ids
    )
][
    hero_columns
]


print(
    heroes.to_string(
        index=False
    )
)


print(
    "\nUpdated:"
)

print(
    BUILDINGS_FILE
)


print(
    "\nImportant:"
)

print(
    "Confidence score = prototype geometric confidence,"
)

print(
    "NOT cadastral survey accuracy."
)


print(
    "\nCADASTRAL CONFIDENCE SCORING: PASS"
)