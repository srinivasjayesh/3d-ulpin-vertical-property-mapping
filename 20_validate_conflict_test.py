import geopandas as gpd

INPUT = "data/hero_floor_ulpins_conflict_test.geojson"

TOLERANCE = 0.02

floors = gpd.read_file(INPUT).to_crs("EPSG:32644")

records = list(floors.iterrows())

conflicts = []

for i in range(len(records)):

    a = records[i][1]

    for j in range(i + 1, len(records)):

        b = records[j][1]

        # Only compare different buildings
        if a["building_id"] == b["building_id"]:
            continue

        if not a.geometry.intersects(b.geometry):
            continue

        intersection = a.geometry.intersection(b.geometry)

        horizontal_overlap_area = intersection.area

        if horizontal_overlap_area <= TOLERANCE:
            continue

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

            conflicts.append({
                "floor_1": a["floor_id"],
                "floor_2": b["floor_id"],
                "horizontal_overlap_m2":
                    horizontal_overlap_area,
                "vertical_overlap_m":
                    vertical_overlap,
                "overlap_volume_m3":
                    overlap_volume
            })


print("\n=== 3D CONFLICT TEST ===")

print("Volumes checked:", len(floors))
print("Conflicts detected:", len(conflicts))

if conflicts:

    print("\nCONFLICT DETECTION: PASSED ✅")

    for c in conflicts:

        print("\nConflict:")
        print("Floor 1:", c["floor_1"])
        print("Floor 2:", c["floor_2"])

        print(
            "Horizontal overlap:",
            round(c["horizontal_overlap_m2"], 2),
            "m²"
        )

        print(
            "Vertical overlap:",
            round(c["vertical_overlap_m"], 2),
            "m"
        )

        print(
            "Overlap volume:",
            round(c["overlap_volume_m3"], 2),
            "m³"
        )

else:

    print("\nCONFLICT DETECTION: FAILED")