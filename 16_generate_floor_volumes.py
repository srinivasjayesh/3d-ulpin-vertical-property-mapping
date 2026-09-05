import geopandas as gpd
import pandas as pd

INPUT = "data/hero_vertical_enriched.geojson"

OUTPUT_GEOJSON = "data/hero_floor_volumes.geojson"
OUTPUT_CSV = "data/hero_floor_volumes.csv"

# --------------------------------------------------
# Load buildings
# --------------------------------------------------

buildings = gpd.read_file(INPUT)

# Use metric CRS for area calculations
buildings_utm = buildings.to_crs("EPSG:32644")

floor_records = []

# --------------------------------------------------
# Generate floors
# --------------------------------------------------

for _, building in buildings_utm.iterrows():

    building_id = building["building_id"]
    floor_count = int(building["floor_count"])
    total_height = float(building["google_height_m"])

    footprint_area = building.geometry.area

    # Divide total height across number of floors
    floor_height = total_height / floor_count

    print(
        f"\n{building_id}: "
        f"{floor_count} floors | "
        f"{total_height:.2f} m total | "
        f"{floor_height:.2f} m/floor"
    )

    for floor_number in range(1, floor_count + 1):

        z_min = (floor_number - 1) * floor_height
        z_max = floor_number * floor_height

        volume = footprint_area * floor_height

        floor_id = f"{building_id}-F{floor_number:03d}"

        floor_records.append({

            "floor_id": floor_id,
            "building_id": building_id,

            "floor_number": floor_number,

            "z_min_m": round(z_min, 2),
            "z_max_m": round(z_max, 2),
            "floor_height_m": round(floor_height, 2),

            "footprint_area_m2": round(footprint_area, 2),
            "volume_m3": round(volume, 2),

            "building_height_m": total_height,
            "building_floor_count": floor_count,

            "height_source":
                "Google Open Buildings 2.5D Temporal 2023",

            "floor_source":
                building["floor_source"],

            "is_floor_estimated":
                bool(building["is_floor_estimated"]),

            "vertical_confidence":
                building["vertical_confidence"],

            # Same horizontal footprint;
            # z_min/z_max will drive extrusion later
            "geometry":
                building.geometry
        })

# --------------------------------------------------
# Create GeoDataFrame
# --------------------------------------------------

floors = gpd.GeoDataFrame(
    floor_records,
    geometry="geometry",
    crs="EPSG:32644"
)

# Convert geometry back to latitude/longitude
floors_wgs84 = floors.to_crs("EPSG:4326")

# --------------------------------------------------
# Save GeoJSON
# --------------------------------------------------

floors_wgs84.to_file(
    OUTPUT_GEOJSON,
    driver="GeoJSON"
)

# Save non-geometry version as CSV
floors.drop(columns="geometry").to_csv(
    OUTPUT_CSV,
    index=False
)

# --------------------------------------------------
# Output summary
# --------------------------------------------------

print("\n=== FLOOR VOLUME GENERATION COMPLETE ===")

print("Buildings:", buildings.shape[0])
print("Total floor parcels:", len(floors))

print("\nFloors per building:")

print(
    floors.groupby("building_id")
    .size()
    .to_string()
)

print("\nSample records:")

print(
    floors[
        [
            "floor_id",
            "building_id",
            "floor_number",
            "z_min_m",
            "z_max_m",
            "floor_height_m",
            "volume_m3"
        ]
    ].head(10).to_string(index=False)
)

print("\nSaved:")
print(OUTPUT_GEOJSON)
print(OUTPUT_CSV)