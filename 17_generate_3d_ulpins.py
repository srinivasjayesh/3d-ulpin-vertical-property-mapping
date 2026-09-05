import geopandas as gpd
import pandas as pd
import hashlib
import re

FLOORS_FILE = "data/hero_floor_volumes.geojson"
PARCELS_FILE = "data/hero_parcels.geojson"

OUTPUT_GEOJSON = "data/hero_floor_ulpins.geojson"
OUTPUT_CSV = "data/hero_floor_ulpins.csv"


# --------------------------------------------------
# Helper
# --------------------------------------------------

def clean_text(value):
    if pd.isna(value):
        return "UNKNOWN"

    value = str(value).upper()
    value = re.sub(r"[^A-Z0-9]+", "-", value)
    return value.strip("-")


# --------------------------------------------------
# Load floor volumes + official parcels
# --------------------------------------------------

floors = gpd.read_file(FLOORS_FILE)
parcels = gpd.read_file(PARCELS_FILE)

print("Floor parcels:", len(floors))
print("Official parcels:", len(parcels))


# --------------------------------------------------
# Keep parcel metadata
# --------------------------------------------------

parcel_columns = [
    "building_id",
    "parcel_id",
    "official_parcel_no",
    "V_Name",
    "M_Name",
    "D_Name"
]

# Keep only columns which actually exist
parcel_columns = [
    col for col in parcel_columns
    if col in parcels.columns
]

parcel_info = parcels[parcel_columns].copy()


# --------------------------------------------------
# Join parcel information to floors
# --------------------------------------------------

floors = floors.merge(
    parcel_info,
    on="building_id",
    how="left"
)


# --------------------------------------------------
# Generate prototype 3D ULPIN
# --------------------------------------------------

prototype_ids = []
canonical_strings = []

for _, row in floors.iterrows():

    building_id = row["building_id"]
    floor_number = int(row["floor_number"])

    z_min = float(row["z_min_m"])
    z_max = float(row["z_max_m"])

    parcel_no = clean_text(
        row.get("official_parcel_no", "UNKNOWN")
    )

    village = clean_text(
        row.get("V_Name", "UNKNOWN")
    )

    mandal = clean_text(
        row.get("M_Name", "UNKNOWN")
    )

    district = clean_text(
        row.get("D_Name", "UNKNOWN")
    )

    # Centroid of vertical parcel footprint
    centroid = row.geometry.centroid

    lon = centroid.x
    lat = centroid.y

    # Deterministic string representing this 3D property
    canonical = (
        f"{district}|"
        f"{mandal}|"
        f"{village}|"
        f"{parcel_no}|"
        f"{building_id}|"
        f"{floor_number}|"
        f"{lat:.7f}|"
        f"{lon:.7f}|"
        f"{z_min:.2f}|"
        f"{z_max:.2f}"
    )

    # Stable fingerprint
    digest = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()[:12].upper()

    prototype_id = (
        f"P3D-{parcel_no}-"
        f"{building_id}-"
        f"F{floor_number:03d}-"
        f"{digest}"
    )

    prototype_ids.append(prototype_id)
    canonical_strings.append(canonical)


floors["prototype_3d_ulpin"] = prototype_ids
floors["ulpin_type"] = "PROTOTYPE_3D_VERTICAL_ID"
floors["ulpin_is_official"] = False


# --------------------------------------------------
# Output summary
# --------------------------------------------------

print("\n=== PROTOTYPE 3D ULPINS ===")

print(
    floors[
        [
            "prototype_3d_ulpin",
            "building_id",
            "floor_number",
            "z_min_m",
            "z_max_m"
        ]
    ].head(15).to_string(index=False)
)


# Check uniqueness
duplicate_count = floors[
    "prototype_3d_ulpin"
].duplicated().sum()

print("\nTotal IDs:", len(floors))
print("Duplicate IDs:", duplicate_count)

if duplicate_count == 0:
    print("ULPIN uniqueness check: PASSED")
else:
    print("ULPIN uniqueness check: FAILED")


# --------------------------------------------------
# Save
# --------------------------------------------------

floors.to_file(
    OUTPUT_GEOJSON,
    driver="GeoJSON"
)

floors.drop(
    columns="geometry"
).to_csv(
    OUTPUT_CSV,
    index=False
)

print("\nSaved:")
print(OUTPUT_GEOJSON)
print(OUTPUT_CSV)