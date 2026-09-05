from pathlib import Path
import hashlib
import sys

import geopandas as gpd
import pandas as pd
from pyproj import Transformer


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

INPUT_FILE = DATA / "all_buildings_processed.geojson"
HERO_FILE = DATA / "hero_floor_ulpins.geojson"

OUT_VOLUMES_GEOJSON = DATA / "all_floor_volumes.geojson"
OUT_VOLUMES_CSV = DATA / "all_floor_volumes.csv"
OUT_ULPINS_GEOJSON = DATA / "all_floor_ulpins.geojson"
OUT_ULPINS_CSV = DATA / "all_floor_ulpins.csv"

ELIGIBLE_STATUSES = {
    "FULL_3D_CADASTRAL",
    "VERTICAL_3D_PARTIAL",
}

HERO_BUILDINGS = {"B0595", "B0612", "B0162"}

transformer_to_wgs84 = Transformer.from_crs(
    "EPSG:32644",
    "EPSG:4326",
    always_xy=True
)


def clean_text(value):
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def make_hash(canonical_string):
    return hashlib.sha256(
        canonical_string.encode("utf-8")
    ).hexdigest()[:12].upper()


def find_existing_hero_id_column(hero_gdf):
    """
    Automatically find the old column containing IDs beginning P3D-.
    """
    for column in hero_gdf.columns:
        if column == "geometry":
            continue

        values = hero_gdf[column].dropna().astype(str)

        if len(values) and values.str.startswith("P3D-").any():
            return column

    return None


print("\n=== STAGE 6: SCALABLE FLOOR VOLUMES + 3D IDS ===\n")

# ---------------------------------------------------------
# LOAD BUILDINGS
# ---------------------------------------------------------

buildings_wgs = gpd.read_file(INPUT_FILE)

if buildings_wgs.crs is None:
    buildings_wgs = buildings_wgs.set_crs("EPSG:4326")

buildings_wgs = buildings_wgs.to_crs("EPSG:4326")
buildings_metric = buildings_wgs.to_crs("EPSG:32644")

eligible = buildings_metric[
    buildings_metric["processing_status"].isin(ELIGIBLE_STATUSES)
].copy()

print(f"Total buildings in Stage 5 file: {len(buildings_metric)}")
print(f"Eligible vertical buildings: {len(eligible)}")

# ---------------------------------------------------------
# LOAD VALIDATED HERO IDS
# ---------------------------------------------------------

hero_id_lookup = {}
hero_id_column = None

if HERO_FILE.exists():
    hero = gpd.read_file(HERO_FILE)

    hero_id_column = find_existing_hero_id_column(hero)

    if hero_id_column:
        for _, row in hero.iterrows():
            building_id = clean_text(row.get("building_id"))

            try:
                floor_number = int(float(row.get("floor_number")))
            except Exception:
                continue

            existing_id = clean_text(row.get(hero_id_column))

            if building_id and existing_id:
                hero_id_lookup[(building_id, floor_number)] = existing_id

        print(
            f"Loaded {len(hero_id_lookup)} validated hero IDs "
            f"from column '{hero_id_column}'"
        )
    else:
        print("WARNING: Could not automatically locate hero ID column.")
else:
    print("WARNING: hero_floor_ulpins.geojson not found.")

# ---------------------------------------------------------
# GENERATE FLOOR RECORDS
# ---------------------------------------------------------

volume_records = []
ulpin_records = []

full_buildings = 0
partial_buildings = 0

invalid_z_ranges = 0
invalid_volumes = 0

floor_counts_by_building = []

for idx, row in eligible.iterrows():

    building_id = clean_text(row.get("building_id"))
    status = clean_text(row.get("processing_status"))

    try:
        height_m = float(row.get("google_height_m"))
        floor_count = int(round(float(row.get("floor_count"))))
    except Exception:
        print(f"Skipping {building_id}: invalid height/floor_count")
        continue

    if height_m <= 0 or floor_count <= 0:
        print(f"Skipping {building_id}: non-positive vertical data")
        continue

    if status == "FULL_3D_CADASTRAL":
        full_buildings += 1
    else:
        partial_buildings += 1

    floor_counts_by_building.append(floor_count)

    geometry_metric = row.geometry

    # Original WGS84 geometry with same index
    geometry_wgs = buildings_wgs.loc[idx].geometry

    footprint_area_m2 = float(geometry_metric.area)

    centroid_metric = geometry_metric.centroid

    centroid_lon, centroid_lat = transformer_to_wgs84.transform(
        centroid_metric.x,
        centroid_metric.y
    )

    floor_height_m = height_m / floor_count

    parcel_no = clean_text(row.get("official_parcel_no"))
    district = clean_text(row.get("district"))
    mandal = clean_text(row.get("mandal"))
    village = clean_text(row.get("village"))
    parcel_match_status = clean_text(row.get("parcel_match_status"))

    for floor_number in range(1, floor_count + 1):

        z_min = (floor_number - 1) * floor_height_m
        z_max = floor_number * floor_height_m

        # Force last floor to exactly match building height
        if floor_number == floor_count:
            z_max = height_m

        volume_m3 = footprint_area_m2 * (z_max - z_min)

        if z_max <= z_min:
            invalid_z_ranges += 1

        if volume_m3 <= 0:
            invalid_volumes += 1

        floor_id = f"{building_id}-F{floor_number:03d}"

        # -------------------------------------------------
        # IDENTIFIER
        # -------------------------------------------------

        canonical = "|".join([
            district,
            mandal,
            village,
            parcel_no if status == "FULL_3D_CADASTRAL" else "NO_CAD",
            building_id,
            str(floor_number),
            f"{centroid_lat:.7f}",
            f"{centroid_lon:.7f}",
            f"{z_min:.4f}",
            f"{z_max:.4f}",
        ])

        digest = make_hash(canonical)

        if (
            status == "FULL_3D_CADASTRAL"
            and parcel_match_status == "STRONG_MATCH"
            and parcel_no
        ):
            generated_id = (
                f"P3D-{parcel_no}-{building_id}-"
                f"F{floor_number:03d}-{digest}"
            )

            ulpin_type = "PROTOTYPE_3D_VERTICAL_ID"

        else:
            generated_id = (
                f"TEMP3D-NOCAD-{building_id}-"
                f"F{floor_number:03d}-{digest}"
            )

            ulpin_type = "NON_CADASTRAL_TEMPORARY_ID"

        # Preserve exact old IDs for the three validated hero buildings
        hero_key = (building_id, floor_number)

        if hero_key in hero_id_lookup:
            prototype_id = hero_id_lookup[hero_key]
        else:
            prototype_id = generated_id

        common_properties = {
            "building_id": building_id,
            "floor_id": floor_id,
            "floor_number": floor_number,

            "relative_z_min_m": round(z_min, 4),
            "relative_z_max_m": round(z_max, 4),
            "floor_height_m": round(z_max - z_min, 4),

            "building_height_m": round(height_m, 4),
            "floor_count": floor_count,

            "footprint_area_m2": round(footprint_area_m2, 2),
            "volume_m3": round(volume_m3, 2),

            "centroid_lat": round(centroid_lat, 7),
            "centroid_lon": round(centroid_lon, 7),

            "official_parcel_no": parcel_no or None,
            "village": village or None,
            "mandal": mandal or None,
            "district": district or None,

            "parcel_match_status": parcel_match_status or None,
            "processing_status": status,

            "height_source": row.get("height_source"),
            "height_year": row.get("height_year"),
            "is_height_estimated": row.get("is_height_estimated"),

            "floor_source": row.get("floor_source"),
            "is_floor_estimated": row.get("is_floor_estimated"),

            "data_confidence": row.get("data_confidence"),

            "geometry": geometry_wgs,
        }

        volume_records.append(common_properties.copy())

        ulpin_record = common_properties.copy()

        ulpin_record.update({
            "prototype_id": prototype_id,

            # Compatibility field for existing viewer/dashboard code
            "prototype_3d_ulpin": prototype_id,

            "ulpin_type": ulpin_type,
            "ulpin_is_official": False,
        })

        ulpin_records.append(ulpin_record)


# ---------------------------------------------------------
# CREATE GEODATAFRAMES
# ---------------------------------------------------------

volumes_gdf = gpd.GeoDataFrame(
    volume_records,
    geometry="geometry",
    crs="EPSG:4326"
)

ulpins_gdf = gpd.GeoDataFrame(
    ulpin_records,
    geometry="geometry",
    crs="EPSG:4326"
)

# ---------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------

duplicate_ids = int(
    ulpins_gdf["prototype_id"].duplicated().sum()
)

prototype_count = int(
    (
        ulpins_gdf["ulpin_type"]
        == "PROTOTYPE_3D_VERTICAL_ID"
    ).sum()
)

temporary_count = int(
    (
        ulpins_gdf["ulpin_type"]
        == "NON_CADASTRAL_TEMPORARY_ID"
    ).sum()
)

# Hero validation
hero_generated = ulpins_gdf[
    ulpins_gdf["building_id"].isin(HERO_BUILDINGS)
]

hero_floor_counts = (
    hero_generated.groupby("building_id")
    .size()
    .to_dict()
)

hero_id_mismatches = 0

for key, old_id in hero_id_lookup.items():
    building_id, floor_number = key

    match = ulpins_gdf[
        (ulpins_gdf["building_id"] == building_id)
        & (ulpins_gdf["floor_number"] == floor_number)
    ]

    if len(match) != 1:
        hero_id_mismatches += 1
        continue

    if match.iloc[0]["prototype_id"] != old_id:
        hero_id_mismatches += 1


# ---------------------------------------------------------
# SAVE OUTPUTS
# ---------------------------------------------------------

volumes_gdf.to_file(
    OUT_VOLUMES_GEOJSON,
    driver="GeoJSON"
)

ulpins_gdf.to_file(
    OUT_ULPINS_GEOJSON,
    driver="GeoJSON"
)

volumes_gdf.drop(columns="geometry").to_csv(
    OUT_VOLUMES_CSV,
    index=False
)

ulpins_gdf.drop(columns="geometry").to_csv(
    OUT_ULPINS_CSV,
    index=False
)


# ---------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------

total_floors = len(ulpins_gdf)

minimum_floors = (
    min(floor_counts_by_building)
    if floor_counts_by_building else 0
)

maximum_floors = (
    max(floor_counts_by_building)
    if floor_counts_by_building else 0
)

average_floors = (
    sum(floor_counts_by_building)
    / len(floor_counts_by_building)
    if floor_counts_by_building else 0
)

print("\n=== STAGE 6 COMPLETION SUMMARY ===")

print(f"Eligible buildings processed: {len(floor_counts_by_building)}")
print(f"FULL_3D_CADASTRAL buildings: {full_buildings}")
print(f"VERTICAL_3D_PARTIAL buildings: {partial_buildings}")

print(f"\nTotal floor volumes generated: {total_floors}")
print(f"Prototype cadastral IDs: {prototype_count}")
print(f"Temporary non-cadastral IDs: {temporary_count}")

print(f"\nDuplicate IDs: {duplicate_ids}")
print(f"Invalid Z ranges: {invalid_z_ranges}")
print(f"Invalid volumes: {invalid_volumes}")

print("\nHero floor regression:")
print(f"B0595: {hero_floor_counts.get('B0595', 0)} floors")
print(f"B0612: {hero_floor_counts.get('B0612', 0)} floors")
print(f"B0162: {hero_floor_counts.get('B0162', 0)} floors")

print(f"Hero ID mismatches: {hero_id_mismatches}")

print(f"\nMinimum floors/building: {minimum_floors}")
print(f"Maximum floors/building: {maximum_floors}")
print(f"Average floors/building: {average_floors:.2f}")

print("\nSaved:")
print(OUT_VOLUMES_GEOJSON)
print(OUT_VOLUMES_CSV)
print(OUT_ULPINS_GEOJSON)
print(OUT_ULPINS_CSV)

if (
    duplicate_ids == 0
    and invalid_z_ranges == 0
    and invalid_volumes == 0
    and hero_id_mismatches == 0
    and hero_floor_counts.get("B0595") == 23
    and hero_floor_counts.get("B0612") == 18
    and hero_floor_counts.get("B0162") == 2
):
    print("\nSTAGE 6 STATUS: PASS")
else:
    print("\nSTAGE 6 STATUS: FAIL")
    sys.exit(1)