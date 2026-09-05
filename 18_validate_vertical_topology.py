import geopandas as gpd
import pandas as pd

INPUT = "data/hero_floor_ulpins.geojson"
OUTPUT = "data/topology_validation_results.csv"

TOLERANCE = 0.02  # metres

floors = gpd.read_file(INPUT).to_crs("EPSG:32644")

issues = []

# --------------------------------------------------
# 1. Check individual floor volumes
# --------------------------------------------------

for _, row in floors.iterrows():

    if row["z_max_m"] <= row["z_min_m"]:
        issues.append({
            "type": "INVALID_Z_RANGE",
            "building_id": row["building_id"],
            "floor_1": row["floor_id"],
            "floor_2": "",
            "details": "z_max is not greater than z_min"
        })


# --------------------------------------------------
# 2. Check vertical continuity inside each building
# --------------------------------------------------

for building_id, group in floors.groupby("building_id"):

    group = group.sort_values("floor_number")

    records = list(group.iterrows())

    for i in range(len(records) - 1):

        current = records[i][1]
        nxt = records[i + 1][1]

        difference = float(nxt["z_min_m"]) - float(current["z_max_m"])

        if difference > TOLERANCE:

            issues.append({
                "type": "VERTICAL_GAP",
                "building_id": building_id,
                "floor_1": current["floor_id"],
                "floor_2": nxt["floor_id"],
                "details": f"Gap of {difference:.2f} m"
            })

        elif difference < -TOLERANCE:

            issues.append({
                "type": "VERTICAL_OVERLAP",
                "building_id": building_id,
                "floor_1": current["floor_id"],
                "floor_2": nxt["floor_id"],
                "details": f"Overlap of {abs(difference):.2f} m"
            })


# --------------------------------------------------
# 3. Check actual 3D conflicts
# --------------------------------------------------

records = list(floors.iterrows())

conflict_count = 0

for i in range(len(records)):

    a = records[i][1]

    for j in range(i + 1, len(records)):

        b = records[j][1]

        # Ignore floors from same building here.
        # Their vertical continuity was checked above.
        if a["building_id"] == b["building_id"]:
            continue

        # First test horizontal intersection
        if not a.geometry.intersects(b.geometry):
            continue

        intersection = a.geometry.intersection(b.geometry)

        horizontal_overlap_area = intersection.area

        if horizontal_overlap_area <= TOLERANCE:
            continue

        # Then test vertical intersection
        vertical_overlap = min(
            float(a["z_max_m"]),
            float(b["z_max_m"])
        ) - max(
            float(a["z_min_m"]),
            float(b["z_min_m"])
        )

        if vertical_overlap > TOLERANCE:

            overlap_volume = (
                horizontal_overlap_area *
                vertical_overlap
            )

            conflict_count += 1

            issues.append({
                "type": "3D_GEOMETRIC_CONFLICT",
                "building_id":
                    f"{a['building_id']} / {b['building_id']}",

                "floor_1": a["floor_id"],
                "floor_2": b["floor_id"],

                "details":
                    f"Horizontal overlap = "
                    f"{horizontal_overlap_area:.2f} m2, "
                    f"vertical overlap = "
                    f"{vertical_overlap:.2f} m, "
                    f"overlap volume = "
                    f"{overlap_volume:.2f} m3"
            })


# --------------------------------------------------
# 4. Save results
# --------------------------------------------------

issues_df = pd.DataFrame(issues)

if len(issues_df) == 0:

    issues_df = pd.DataFrame(columns=[
        "type",
        "building_id",
        "floor_1",
        "floor_2",
        "details"
    ])

issues_df.to_csv(
    OUTPUT,
    index=False
)


# --------------------------------------------------
# 5. Summary
# --------------------------------------------------

print("\n=== 3D TOPOLOGY VALIDATION ===")

print("Floor volumes checked:", len(floors))
print("Buildings checked:", floors["building_id"].nunique())
print("Issues detected:", len(issues_df))
print("3D geometric conflicts:", conflict_count)

if len(issues_df) == 0:
    print("\nTOPOLOGY STATUS: PASSED")
    print("No gaps, invalid Z ranges, or 3D overlaps detected.")
else:
    print("\nTOPOLOGY STATUS: ISSUES FOUND")
    print()
    print(issues_df.to_string(index=False))

print("\nSaved:")
print(OUTPUT)