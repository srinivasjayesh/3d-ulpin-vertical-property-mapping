# 3D ULPIN Generation and Vertical Property Mapping System

Research/hackathon prototype for turning 2D building and parcel context into an explorable vertical model. The application combines geospatial processing, source-aware height/floor evidence, deterministic prototype identifiers, topology checks, a FastAPI backend, and a Leaflet + Three.js frontend.

> Prototype vertical IDs are **not official government-issued ULPINs**. This repository does not establish ownership, title, legal boundaries, survey accuracy, or building compliance.

## Problem statement

Traditional parcel identifiers describe land in two dimensions, while dense cities also need a usable hierarchy of site → building → floor → optional space/unit. This project demonstrates that hierarchy while preserving source provenance, uncertainty, and the distinction between observed, estimated, and synthetic information.

## Architecture

```text
Public source APIs / local source files
        │
        ├─ OSM footprints and streets
        ├─ city/state parcel or reference layers
        ├─ height and level observations
        └─ optional DEM, BIM/IFC, LiDAR
        │
        ▼
pipeline/ and profile-specific processors
        │  GeoJSON/CSV + provenance + topology audits
        ▼
FileProvider (default) ─── optional PostGISProvider
        │
        ▼
FastAPI JSON API
        │
        ▼
Leaflet map + Three.js vertical viewer
```

The default file backend is offline-friendly. PostGIS is an optional provider behind the same API contract. Active profile selection uses `?profile=hyderabad|manhattan|amsterdam`; `DATA_PROFILE` controls the default.

## Key features

- Multi-profile Hyderabad, Manhattan, and Amsterdam study areas.
- Building, parcel/tax-lot context, floors, prototype 3D IDs, search, and topology endpoints.
- Source-aware vertical source fusion and explicit pending states for DEM, BIM, and LiDAR.
- Interactive floor selection, building isolation/context, study boundaries, roads, and below-ground demo compartments where supported.
- Deterministic synthetic Manhattan unit subdivisions for UI/API testing only.
- File-backed operation with optional PostgreSQL/PostGIS import and provider fallback.
- Preserved historical root scripts `01`–`21` and scalable `pipeline/` stages.

## Technology stack

- Python 3.11+; FastAPI, Uvicorn, HTTPX, pytest.
- GeoPandas, Shapely, pyproj, Rasterio, pandas, requests, OSMnx.
- Optional: PostgreSQL/PostGIS, `psycopg`, IfcOpenShell, `laspy[lazrs]`, native PDAL.
- Browser: Leaflet, Three.js, and vanilla JavaScript/CSS served by FastAPI.

## Data sources and city profiles

### Hyderabad

Nanakramguda / Financial District study area using OpenStreetMap building context and Google Open Buildings 2.5D height estimates. Telangana BhuNaksha parcel data and all parcel-derived outputs are excluded because the service metadata does not provide a clear open-redistribution license.

### Manhattan

Hudson Yards / West Midtown using NYC OTI Building Footprints, NYC DOF tax lots, and NYC DCP PLUTO. Source height and ground-elevation attributes are retained in processed profile artifacts. Floor counts are deterministic estimates where needed. Unit geometry is a deterministic subdivision for interaction testing, marked synthetic and unofficial.

### Amsterdam

Amsterdam Centrum uses OSM context plus locally regenerated PDOK BAG buildings and PDOK cadastral parcels. AHN terrain/LiDAR and PDOK orthophoto remain optional next-stage inputs. No apartment ownership or legal floor boundaries are inferred.

The former Mumbai G/South profile and its MCGM/BMC-derived artifacts were retired because redistribution permission was unclear. They are not active application data.

Detailed source and license decisions are in [docs/DATA_LICENSES.md](docs/DATA_LICENSES.md) and [data/README.md](data/README.md).

## Real, estimated, and synthetic data

- **Real/source-observed:** source geometries, OSM tags, NYC source attributes, and provider-returned metadata.
- **Estimated:** Google Open Buildings heights, derived floor counts, geometric match scores, and equal-height display strata.
- **Synthetic:** Manhattan unit subdivisions and selected below-ground visualization compartments.

Estimated heights/floors are not survey measurements. Synthetic unit subdivisions are demo-only and are not legal ownership boundaries. Geometric confidence is a prototype comparison score, not legal, cadastral, positional, or survey accuracy. OSM building footprints are not authoritative cadastral boundaries.

## Setup

PowerShell:

```powershell
python -m venv .runtime
.\.runtime\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

The checked-in `.env.example` contains placeholders only. Keep real credentials outside Git. Optional integration dependencies are in `requirements-integrations.txt`; the database driver is also documented in `database/README.md`.

## Run the backend and frontend

The FastAPI process serves the API and the main frontend:

```powershell
.\.runtime\Scripts\python.exe -m uvicorn app.backend.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/>. Use another port if needed, for example `--port 8765`; the frontend uses its own origin.

Useful API calls:

```text
GET /api/profiles
GET /api/health?profile=hyderabad
GET /api/stats?profile=manhattan
GET /api/buildings/{building_id}?profile=amsterdam
GET /api/buildings/{building_id}/floors
GET /api/units/{prototype_unit_uid}?profile=manhattan
GET /api/parcels
GET /api/system/capabilities
GET /api/search?q=...
```

The legacy standalone output remains at `viewer/index.html`. The separate `dashboard/` is retained as an additional static dashboard and uses a placeholder-only Mapbox configuration example; it is not required by the FastAPI viewer.

## Tests and CI

Run locally:

```powershell
.\.runtime\Scripts\python.exe -m pytest -q
```

GitHub Actions runs the same pytest suite on Python 3.12 for pushes to `main` and pull requests. The public checkout does not require excluded cadastral or municipal source snapshots.

## Pipeline and regeneration

Root scripts `01`–`21` are preserved historical/demo scripts. The scalable pipeline is in `pipeline/01`–`09`; optional stages cover elevation, BIM, LiDAR, source fusion, and advanced topology. Amsterdam public-data acquisition is in `pipeline/amsterdam/`. Manhattan rebuild instructions are in [docs/MANHATTAN_PROFILE.md](docs/MANHATTAN_PROFILE.md). Hyderabad parcel retrieval remains historical and must not be published without permission.

Do not publish regenerated raw cadastral, BMC, LAS/LAZ, DEM, or large raster files without a fresh provider-specific license review.

## PostgreSQL/PostGIS mode

PostGIS is optional. Install PostgreSQL with PostGIS, create the database, set values from `.env.example` or a secret manager, install `psycopg[binary]`, and run:

```powershell
.\.runtime\Scripts\python.exe -m pip install "psycopg[binary]>=3.2,<4"
.\.runtime\Scripts\python.exe database/import_data.py
$env:DATA_BACKEND = "postgis"
.\.runtime\Scripts\python.exe -m uvicorn app.backend.main:app --host 127.0.0.1 --port 8000
```

See [database/README.md](database/README.md) and [docs/DATABASE_AND_API.md](docs/DATABASE_AND_API.md). The importer is idempotent; the current development host did not have an operational PostgreSQL service, so PostGIS is code-ready rather than locally runtime-verified.

## Limitations and legal scope

This is a research/hackathon prototype. Prototype vertical IDs are not government-issued ULPINs. OSM footprints are not authoritative cadastral boundaries. Synthetic unit subdivisions are demo-only, not legal ownership boundaries. Estimated heights/floors are not survey measurements. Geometric confidence is not legal or survey accuracy. Relative-Z floor models do not prove cross-building absolute vertical conflicts. No output should be used for title, tax, enforcement, safety, or construction decisions without authoritative local validation.

## Documentation

- [Data guide](data/README.md)
- [Data licenses and redistribution review](docs/DATA_LICENSES.md)
- [System architecture](docs/ARCHITECTURE.md)
- [End-to-end pipeline](docs/END_TO_END_PIPELINE.md)
- [Hyderabad provenance](docs/DATA_PROVENANCE.md)
- [Manhattan profile](docs/MANHATTAN_PROFILE.md)
- [Mumbai profile](docs/MUMBAI_PROFILE.md)
- [Database/API](docs/DATABASE_AND_API.md)
- [Limitations](docs/LIMITATIONS.md)
- [Master project documentation](docs/MASTER_PROJECT_DOCUMENTATION.md)

## License

Project code and documentation are MIT licensed. Third-party datasets remain under their own terms; see [docs/DATA_LICENSES.md](docs/DATA_LICENSES.md).
