from pathlib import Path
import shutil

import geopandas as gpd
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

BUILDINGS_GEOJSON = DATA / "all_buildings_processed.geojson"
BUILDINGS_CSV = DATA / "all_buildings_processed.csv"

QUALITY_CSV = DATA / "all_parcel_quality_analysis.csv"

BACKUP_GEOJSON = DATA / "all_buildings_processed_before_parcel_quality.geojson"
BACKUP_CSV = DATA / "all_buildings_processed_before_parcel_quality.csv"


print("\n=== MERGING PARCEL QUALITY INTO MAIN BUILDING DATASET ===\n")


# ==========================================================
# VERIFY INPUTS
# ==========================================================

if not BUILDINGS_GEOJSON.exists():
    raise FileNotFoundError(BUILDINGS_GEOJSON)

if not QUALITY_CSV.exists():
    raise FileNotFoundError(QUALITY_CSV)


# ==========================================================
# BACKUP EXISTING STAGE 5 DATA
# ==========================================================

if not BACKUP_GEOJSON.exists():

    shutil.copy2(
        BUILDINGS_GEOJSON,
        BACKUP_GEOJSON
    )

    print(
        "Backup created:",
        BACKUP_GEOJSON
    )

else:

    print(
        "GeoJSON backup already exists:",
        BACKUP_GEOJSON
    )


if (
    BUILDINGS_CSV.exists()
    and not BACKUP_CSV.exists()
):

    shutil.copy2(
        BUILDINGS_CSV,
        BACKUP_CSV
    )

    print(
        "CSV backup created:",
        BACKUP_CSV
    )


# ==========================================================
# LOAD DATA
# ==========================================================

buildings = gpd.read_file(
    BUILDINGS_GEOJSON
)

quality = pd.read_csv(
    QUALITY_CSV
)


print(
    "Buildings:",
    len(buildings)
)

print(
    "Parcel-quality records:",
    len(quality)
)


# ==========================================================
# FIELDS TO ADD
# ==========================================================

quality_fields = [

    "building_id",

    "parcel_area_m2",

    "intersection_area_m2",

    "building_covered_by_parcel_pct",

    "parcel_occupied_by_building_pct",

    "buildings_associated_with_parcel",

    "parcel_area_to_building_area_ratio",

    "parcel_interpretation",

    "interpretation_note"
]


missing_fields = [

    field
    for field in quality_fields
    if field not in quality.columns
]


if missing_fields:

    raise ValueError(
        f"Missing parcel-quality fields: {missing_fields}"
    )


quality_subset = quality[
    quality_fields
].copy()


# ==========================================================
# REMOVE OLD QUALITY FIELDS IF SCRIPT IS RE-RUN
# ==========================================================

for field in quality_fields:

    if (
        field != "building_id"
        and field in buildings.columns
    ):

        buildings = buildings.drop(
            columns=[field]
        )


# ==========================================================
# MERGE
# ==========================================================

merged = buildings.merge(

    quality_subset,

    on="building_id",

    how="left"
)


# ==========================================================
# CADASTRAL CONTEXT LEVEL
# ==========================================================

def get_context_level(parcel_interpretation):

    if pd.isna(parcel_interpretation):

        return "UNKNOWN"


    if parcel_interpretation == "PLOT_LIKE_MATCH":

        return "PLOT_LIKE"


    if parcel_interpretation == "SITE_PARCEL":

        return "SITE_CONTEXT"


    if parcel_interpretation in (
        "LARGE_SURVEY_PARCEL",
        "MULTI_BUILDING_PARCEL"
    ):

        return "SURVEY_CONTEXT"


    if parcel_interpretation == "NO_RELIABLE_MATCH":

        return "UNRELIABLE"


    return "UNKNOWN"


merged["cadastral_context_level"] = (

    merged["parcel_interpretation"]
    .apply(
        get_context_level
    )
)


# ==========================================================
# DISPLAY STATUS
#
# IMPORTANT:
# We preserve processing_status because it describes
# vertical-data completeness.
#
# display_status is the safer label shown to users.
# ==========================================================

def make_display_status(row):

    processing = row.get(
        "processing_status"
    )

    interpretation = row.get(
        "parcel_interpretation"
    )


    # No usable vertical model
    if processing == "CONTEXT_ONLY":

        return "2D_CONTEXT_ONLY"


    # Reliable plot-like cadastral relationship
    if interpretation == "PLOT_LIKE_MATCH":

        return "3D_PLOT_LIKE_CADASTRAL"


    # Site parcel
    if interpretation == "SITE_PARCEL":

        return "3D_SITE_CONTEXT"


    # Large / multi-building official survey parcel
    if interpretation in (
        "LARGE_SURVEY_PARCEL",
        "MULTI_BUILDING_PARCEL"
    ):

        return "3D_SURVEY_CONTEXT"


    # Weak / unreliable relationship
    if interpretation == "NO_RELIABLE_MATCH":

        return "3D_NO_RELIABLE_CADASTRAL_MATCH"


    return "3D_CONTEXT_UNCLASSIFIED"


merged["display_status"] = merged.apply(
    make_display_status,
    axis=1
)


# ==========================================================
# PARCEL DISPLAY MODE
#
# Used by frontend.
# ==========================================================

def parcel_display_mode(parcel_interpretation):

    if parcel_interpretation == "PLOT_LIKE_MATCH":

        return "PROMINENT"


    if parcel_interpretation == "SITE_PARCEL":

        return "NORMAL"


    if parcel_interpretation in (
        "LARGE_SURVEY_PARCEL",
        "MULTI_BUILDING_PARCEL"
    ):

        return "SUBTLE"


    return "HIDDEN"


merged["parcel_display_mode"] = (

    merged["parcel_interpretation"]
    .apply(
        parcel_display_mode
    )
)


# ==========================================================
# HUMAN-READABLE CADASTRAL LABEL
# ==========================================================

def context_label(parcel_interpretation):

    mapping = {

        "PLOT_LIKE_MATCH":
            "Plot-like cadastral match",

        "SITE_PARCEL":
            "Site / development parcel",

        "LARGE_SURVEY_PARCEL":
            "Large cadastral survey parcel",

        "MULTI_BUILDING_PARCEL":
            "Multi-building cadastral survey parcel",

        "NO_RELIABLE_MATCH":
            "No reliable cadastral relationship"
    }


    return mapping.get(

        parcel_interpretation,

        "Unclassified cadastral context"
    )


merged["cadastral_context_label"] = (

    merged["parcel_interpretation"]
    .apply(
        context_label
    )
)


# ==========================================================
# VALIDATION
# ==========================================================

if len(merged) != 635:

    raise ValueError(
        f"Expected 635 buildings, got {len(merged)}"
    )


duplicate_buildings = int(

    merged[
        "building_id"
    ].duplicated().sum()
)


if duplicate_buildings != 0:

    raise ValueError(
        f"Duplicate building IDs detected: {duplicate_buildings}"
    )


# ==========================================================
# SAVE UPDATED MAIN DATASET
# ==========================================================

merged.to_file(

    BUILDINGS_GEOJSON,

    driver="GeoJSON"
)


merged.drop(
    columns="geometry"
).to_csv(

    BUILDINGS_CSV,

    index=False
)


# ==========================================================
# REPORT
# ==========================================================

print(
    "\n=== CADASTRAL CONTEXT COUNTS ==="
)


print(

    merged[
        "cadastral_context_level"
    ].value_counts(
        dropna=False
    )
)


print(
    "\n=== DISPLAY STATUS COUNTS ==="
)


print(

    merged[
        "display_status"
    ].value_counts(
        dropna=False
    )
)


print(
    "\n=== VALIDATION ==="
)

print(
    "Buildings:",
    len(merged)
)

print(
    "Duplicate building IDs:",
    duplicate_buildings
)


print(
    "\nAdded fields:"
)

for field in [

    "parcel_area_m2",
    "building_covered_by_parcel_pct",
    "parcel_occupied_by_building_pct",
    "buildings_associated_with_parcel",
    "parcel_area_to_building_area_ratio",
    "parcel_interpretation",
    "interpretation_note",
    "cadastral_context_level",
    "cadastral_context_label",
    "display_status",
    "parcel_display_mode"

]:

    print(
        " -",
        field
    )


print(
    "\nUpdated:"
)

print(
    BUILDINGS_GEOJSON
)

print(
    BUILDINGS_CSV
)


print(
    "\nOriginal backup:"
)

print(
    BACKUP_GEOJSON
)


print(
    "\nPARCEL QUALITY MERGE: PASS"
)