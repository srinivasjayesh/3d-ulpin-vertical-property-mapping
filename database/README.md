# PostgreSQL/PostGIS backend

This directory is the code-ready optional spatial database layer. The demo defaults to `DATA_BACKEND=file`; selecting PostGIS is explicit and never required for the file-backed hackathon experience.

## Geometry model

- Source geometries use SRID 4326.
- Building and parcel geometries are the supplied 2D polygons.
- `vertical_units.geometry` is also a 2D footprint. Relative and optional absolute Z extents are stored in numeric columns. The schema does **not** claim these records are volumetric PostGIS solids.
- GiST indexes support spatial filtering for buildings, parcels, and vertical-unit footprints.

## Setup

1. Install PostgreSQL with PostGIS and create an empty database/user.
2. Copy `.env.example` values into your environment or preferred secret manager. Do not commit the populated values.
3. Install the optional driver: `python -m pip install "psycopg[binary]>=3.2,<4"`.
4. Apply/import in one idempotent operation:

   ```powershell
   python database/import_data.py
   ```

5. Set `DATA_BACKEND=postgis` and start the API.

`import_data.py` upserts all source artifacts for both profiles, applies `schema.sql`, and verifies expected counts. Re-running it is safe. PostgreSQL/PostGIS was unavailable on the development host, so this layer is **POSTGIS_CODE_READY**, not operationally tested.

## Expected import verification

- buildings: 635
- parcels: 194
- vertical units: 2,100
- duplicate prototype IDs: 0

Manhattan adds 133 buildings, 164 tax lots, 1,827 floors, and 8,130 explicitly synthetic vertical units when its artifacts are present.
