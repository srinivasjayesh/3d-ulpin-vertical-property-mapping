from pathlib import Path
import pandas as pd
import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

FLOORS_FILE = DATA / "all_floor_ulpins.geojson"
BUILDINGS_FILE = DATA / "all_buildings_processed.geojson"

OUT_TOPOLOGY = DATA / "all_topology_results.csv"
OUT_QUALITY = DATA / "all_building_quality_summary.csv"

Z_TOL = 0.02
AREA_TOL = 0.02

print("\n=== STAGE 7: SCALABLE TOPOLOGY + QUALITY VALIDATION ===\n")

floors = gpd.read_file(FLOORS_FILE)
buildings = gpd.read_file(BUILDINGS_FILE)

issues = []

# --------------------------------------------------
# 1. BASIC FLOOR VALIDATION
# --------------------------------------------------

invalid_z = 0
invalid_volume = 0

for _, row in floors.iterrows():

    bid = row["building_id"]
    fid = row["floor_id"]

    zmin = float(row["relative_z_min_m"])
    zmax = float(row["relative_z_max_m"])
    volume = float(row["volume_m3"])

    if zmax <= zmin:
        invalid_z += 1

        issues.append({
            "severity": "ERROR",
            "issue_type": "INVALID_Z_RANGE",
            "building_id": bid,
            "floor_id_1": fid,
            "floor_id_2": None,
            "horizontal_overlap_m2": None,
            "vertical_overlap_m": None,
            "message": "Floor Zmax is not greater than Zmin."
        })

    if volume <= 0:
        invalid_volume += 1

        issues.append({
            "severity": "ERROR",
            "issue_type": "INVALID_VOLUME",
            "building_id": bid,
            "floor_id_1": fid,
            "floor_id_2": None,
            "horizontal_overlap_m2": None,
            "vertical_overlap_m": None,
            "message": "Floor volume is not positive."
        })


# --------------------------------------------------
# 2. ID UNIQUENESS
# --------------------------------------------------

duplicate_mask = floors["prototype_id"].duplicated(keep=False)
duplicate_rows = floors[duplicate_mask]

duplicate_ids = duplicate_rows["prototype_id"].nunique()

for _, row in duplicate_rows.iterrows():

    issues.append({
        "severity": "ERROR",
        "issue_type": "DUPLICATE_PROTOTYPE_ID",
        "building_id": row["building_id"],
        "floor_id_1": row["floor_id"],
        "floor_id_2": None,
        "horizontal_overlap_m2": None,
        "vertical_overlap_m": None,
        "message": f"Duplicate identifier: {row['prototype_id']}"
    })


# --------------------------------------------------
# 3. FLOOR CONTINUITY
# --------------------------------------------------

gap_count = 0
internal_overlap_count = 0
height_mismatch_count = 0

for bid, group in floors.groupby("building_id"):

    group = group.sort_values("floor_number")

    rows = list(group.itertuples())

    for i in range(len(rows) - 1):

        current = rows[i]
        nxt = rows[i + 1]

        current_top = float(current.relative_z_max_m)
        next_bottom = float(nxt.relative_z_min_m)

        difference = next_bottom - current_top

        if difference > Z_TOL:

            gap_count += 1

            issues.append({
                "severity": "ERROR",
                "issue_type": "VERTICAL_GAP",
                "building_id": bid,
                "floor_id_1": current.floor_id,
                "floor_id_2": nxt.floor_id,
                "horizontal_overlap_m2": None,
                "vertical_overlap_m": round(difference, 4),
                "message": "Gap detected between adjacent floors."
            })

        elif difference < -Z_TOL:

            internal_overlap_count += 1

            issues.append({
                "severity": "ERROR",
                "issue_type": "INTERNAL_VERTICAL_OVERLAP",
                "building_id": bid,
                "floor_id_1": current.floor_id,
                "floor_id_2": nxt.floor_id,
                "horizontal_overlap_m2": None,
                "vertical_overlap_m": round(abs(difference), 4),
                "message": "Adjacent floor Z ranges overlap."
            })

    # last floor should end at building height

    last = rows[-1]

    top_z = float(last.relative_z_max_m)
    building_height = float(last.building_height_m)

    if abs(top_z - building_height) > Z_TOL:

        height_mismatch_count += 1

        issues.append({
            "severity": "ERROR",
            "issue_type": "BUILDING_HEIGHT_MISMATCH",
            "building_id": bid,
            "floor_id_1": last.floor_id,
            "floor_id_2": None,
            "horizontal_overlap_m2": None,
            "vertical_overlap_m": round(abs(top_z - building_height), 4),
            "message": "Top floor does not terminate at building height."
        })


# --------------------------------------------------
# 4. CROSS-BUILDING GEOMETRIC OVERLAP
# --------------------------------------------------

# IMPORTANT:
# Z values are currently relative to each building's own ground level.
# Therefore these are geometric overlap warnings, NOT legal conflicts
# and NOT survey-grade absolute-Z conflict determinations.

vertical_buildings = buildings[
    buildings["processing_status"].isin([
        "FULL_3D_CADASTRAL",
        "VERTICAL_3D_PARTIAL"
    ])
].copy()

vertical_metric = vertical_buildings.to_crs("EPSG:32644")

floor_groups = {
    bid: grp.sort_values("floor_number")
    for bid, grp in floors.groupby("building_id")
}

spatial_index = vertical_metric.sindex

checked_pairs = set()
cross_conflicts = 0

for idx, row in vertical_metric.iterrows():

    possible = list(
        spatial_index.intersection(row.geometry.bounds)
    )

    for position in possible:

        other_idx = vertical_metric.index[position]

        if idx == other_idx:
            continue

        pair = tuple(sorted((idx, other_idx)))

        if pair in checked_pairs:
            continue

        checked_pairs.add(pair)

        other = vertical_metric.loc[other_idx]

        if not row.geometry.intersects(other.geometry):
            continue

        intersection = row.geometry.intersection(other.geometry)

        horizontal_area = float(intersection.area)

        if horizontal_area <= AREA_TOL:
            continue

        bid1 = row["building_id"]
        bid2 = other["building_id"]

        if bid1 not in floor_groups or bid2 not in floor_groups:
            continue

        floors1 = floor_groups[bid1]
        floors2 = floor_groups[bid2]

        for _, f1 in floors1.iterrows():

            z1min = float(f1["relative_z_min_m"])
            z1max = float(f1["relative_z_max_m"])

            for _, f2 in floors2.iterrows():

                z2min = float(f2["relative_z_min_m"])
                z2max = float(f2["relative_z_max_m"])

                overlap_z = min(z1max, z2max) - max(z1min, z2min)

                if overlap_z > Z_TOL:

                    cross_conflicts += 1

                    issues.append({
                        "severity": "WARNING",
                        "issue_type": "RELATIVE_Z_GEOMETRIC_OVERLAP",
                        "building_id": bid1,
                        "floor_id_1": f1["floor_id"],
                        "floor_id_2": f2["floor_id"],
                        "horizontal_overlap_m2": round(horizontal_area, 2),
                        "vertical_overlap_m": round(overlap_z, 4),
                        "message":
                            f"Geometric overlap with building {bid2}. "
                            "Relative-Z warning only; not a legal conflict."
                    })


# --------------------------------------------------
# 5. SAVE TOPOLOGY RESULTS
# --------------------------------------------------

issue_columns = [
    "severity",
    "issue_type",
    "building_id",
    "floor_id_1",
    "floor_id_2",
    "horizontal_overlap_m2",
    "vertical_overlap_m",
    "message"
]

issues_df = pd.DataFrame(issues, columns=issue_columns)

issues_df.to_csv(
    OUT_TOPOLOGY,
    index=False
)


# --------------------------------------------------
# 6. BUILDING QUALITY SCORE
# --------------------------------------------------

quality_records = []

for _, row in buildings.iterrows():

    bid = row["building_id"]

    score = 100

    height_available = pd.notna(row.get("google_height_m"))
    floor_available = pd.notna(row.get("floor_count"))

    parcel_status = row.get("parcel_match_status")
    processing_status = row.get("processing_status")

    is_height_estimated = bool(
        row.get("is_height_estimated")
    ) if pd.notna(row.get("is_height_estimated")) else True

    is_floor_estimated = bool(
        row.get("is_floor_estimated")
    ) if pd.notna(row.get("is_floor_estimated")) else True

    sanity = row.get("floor_height_sanity")

    if not height_available:
        score -= 35

    if not floor_available:
        score -= 25

    if parcel_status == "MULTI_PARCEL":
        score -= 15

    elif parcel_status == "PARTIAL_MATCH":
        score -= 20

    elif parcel_status in ("NO_MATCH", "API_UNAVAILABLE"):
        score -= 30

    if height_available and is_height_estimated:
        score -= 5

    if floor_available and is_floor_estimated:
        score -= 10

    if sanity == "FLOOR_HEIGHT_REVIEW":
        score -= 10

    building_issues = issues_df[
        issues_df["building_id"] == bid
    ] if len(issues_df) else pd.DataFrame()

    error_count = (
        int((building_issues["severity"] == "ERROR").sum())
        if len(building_issues) else 0
    )

    warning_count = (
        int((building_issues["severity"] == "WARNING").sum())
        if len(building_issues) else 0
    )

    if error_count:
        score -= min(30, error_count * 10)

    # Warnings are source/geometric warnings, not legal findings.
    if warning_count:
        score -= min(10, warning_count * 2)

    score = max(0, min(100, score))

    if score >= 85:
        quality_class = "HIGH"

    elif score >= 60:
        quality_class = "MEDIUM"

    else:
        quality_class = "LOW"

    quality_records.append({
        "building_id": bid,
        "processing_status": processing_status,
        "parcel_match_status": parcel_status,
        "quality_score": score,
        "quality_class": quality_class,
        "topology_error_count": error_count,
        "topology_warning_count": warning_count,
        "quality_meaning":
            "Observable prototype data completeness/consistency; "
            "not survey or legal accuracy."
    })


quality_df = pd.DataFrame(quality_records)

quality_df.to_csv(
    OUT_QUALITY,
    index=False
)


# --------------------------------------------------
# 7. SUMMARY
# --------------------------------------------------

high_count = int(
    (quality_df["quality_class"] == "HIGH").sum()
)

medium_count = int(
    (quality_df["quality_class"] == "MEDIUM").sum()
)

low_count = int(
    (quality_df["quality_class"] == "LOW").sum()
)

error_total = (
    int((issues_df["severity"] == "ERROR").sum())
    if len(issues_df) else 0
)

warning_total = (
    int((issues_df["severity"] == "WARNING").sum())
    if len(issues_df) else 0
)

print("Floors checked:", len(floors))
print("Buildings checked:", len(buildings))

print("\nCore validation:")
print("Invalid Z ranges:", invalid_z)
print("Invalid volumes:", invalid_volume)
print("Duplicate IDs:", duplicate_ids)
print("Vertical gaps:", gap_count)
print("Internal floor overlaps:", internal_overlap_count)
print("Height mismatches:", height_mismatch_count)

print("\nCross-building relative-Z overlap warnings:", cross_conflicts)

print("\nIssue totals:")
print("ERROR:", error_total)
print("WARNING:", warning_total)

print("\nQuality:")
print("HIGH:", high_count)
print("MEDIUM:", medium_count)
print("LOW:", low_count)

print("\nSaved:")
print(OUT_TOPOLOGY)
print(OUT_QUALITY)

core_pass = (
    invalid_z == 0
    and invalid_volume == 0
    and duplicate_ids == 0
    and gap_count == 0
    and internal_overlap_count == 0
    and height_mismatch_count == 0
)

if core_pass:
    print("\nSTAGE 7 STATUS: PASS")
else:
    print("\nSTAGE 7 STATUS: PARTIAL")