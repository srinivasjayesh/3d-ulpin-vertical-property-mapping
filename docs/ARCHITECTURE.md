# System Architecture

> **Implemented architecture update (2026-09-05):** The production-shaped prototype uses Leaflet (not Mapbox) plus Three.js, a FastAPI provider interface, default file artifacts, and an optional PostGIS provider. PostGIS stores source geometry in SRID 4326 and floor footprints as 2D geometry with Z attributes; no current volumetric-solid claim is made. Optional adapters report honest DEM/BIM/LiDAR availability, source fusion preserves every observation, and cross-building conflicts require absolute Z. The older current/target design below is retained as historical planning context and is superseded where inconsistent with this update.

### Profile extension

The same provider contract now serves `hyderabad`, `manhattan`, and `mumbai`. Profile-specific source metadata and artifacts are selected through `?profile=` (or `DATA_PROFILE` for the default). Manhattan adds a synthetic vertical-unit layer solely for interaction testing; Mumbai uses official MCGM ward geometry plus OSM context and does not fabricate units.

## 1. Current Architecture Pipeline

The current working prototype follows a batch file-based pipeline from data ingestion to client visualization:

```
+-----------------------------------------------------------------------------+
|                            CURRENT PIPELINE                                 |
+-----------------------------------------------------------------------------+

 [ OpenStreetMap ] ──(osmnx)──> Raw Footprints (635 buildings)
                                       │
                                   (GeoPandas)
                                       │
                                       ▼
                              Clean Footprints (EPSG:32644)
                                       │
                                       ├─────────────────────────────┐
                                       ▼                             ▼
 [ Telangana BhuNaksha REST ] ──> Cadastral Parcels       Hero Building Selection
                                  (Parcels 140, 337, 92)  (B0595, B0612, B0162)
                                       │                             │
                                       └──────────────┬──────────────┘
                                                      │
                                                      ▼
 [ Google Open Buildings 2.5D ] ──(Rasterio)──> Height Extraction
                                                      │
                                                      ▼
                                            Vertical Floor Enrichment
                                            (Levels & Confidence)
                                                      │
                                                      ▼
                                            Floor Stratum Volume Gen
                                            (43 Volumetric Strata)
                                                      │
                                                      ▼
                                            Prototype 3D ULPIN Gen
                                            (SHA-256 Hashing)
                                                      │
                                                      ▼
                                            3D Topology & Conflict Check
                                                      │
                                                      ▼
                                            Three.js Web Viewer Builder
                                            (viewer/index.html)
```

### Component Details (Current):
1. **Data Pull & Prep (`osmnx`, GeoPandas)**: Downloads 635 OSM building footprints around Nanakramguda/Financial District, Hyderabad. Cleans geometries, reprojects to UTM Zone 44N (`EPSG:32644`), and calculates metric footprint areas.
2. **Cadastral Matching (`requests`, Shapely)**: Queries Telangana TGRAC BhuNaksha ArcGIS REST service at building centroids to extract official land parcel polygons and attributes.
3. **Satellite Height Extraction (`rasterio`)**: Crops Google Open Buildings 2.5D GeoTIFF tile (`tile_0PX-jEEaiBo.tif`) to calculate median building height per hero building footprint.
4. **Vertical Enrichment & Slicing (GeoPandas, Pandas)**: Combines OSM levels and satellite heights to derive floor counts, floor height strata ($Z_{\text{min}}, Z_{\text{max}}$), and confidence ratings.
5. **Prototype 3D ULPIN Generation (`hashlib`)**: Generates deterministic SHA-256 hashes from canonical property strings (`DISTRICT|MANDAL|VILLAGE|PARCEL|BUILDING|FLOOR|LAT|LON|ZMIN|ZMAX`).
6. **3D Topology Engine (GeoPandas, Shapely)**: Evaluates $Z_{\text{max}} > Z_{\text{min}}$, verifies vertical continuity between adjacent floors, and checks 3D geometric overlaps between distinct buildings.
7. **3D Web Viewer Builder (`21_build_3d_viewer.py`)**: Serializes UTM-centered GIS datasets into a single standalone Three.js HTML/JS application (`viewer/index.html`).

---

## 2. Target Architecture (Future Integrated Application)

The target architecture transitions the system from batch file processing into a **unified 3-pane web application** backed by a spatial REST API and a 3D PostGIS database.

```
+---------------------------------------------------------------------------------+
|                              TARGET ARCHITECTURE                                |
+---------------------------------------------------------------------------------+

┌─────────────────────────────────────────────────────────────────────────────────┐
│                           UNIFIED 3-PANE FRONTEND                               │
│                                                                                 │
│  ┌───────────────────────┬───────────────────────────────┬───────────────────┐  │
│  │   LEFT PANE           │         CENTER PANE           │    RIGHT PANE     │  │
│  │                       │                               │                   │  │
│  │   Mapbox GL 2D Map    │     Three.js 3D Viewer        │  Property Dossier │  │
│  │   - 2D Footprints     │     - 3D Floor Strata         │  - 3D ULPIN       │  │
│  │   - BhuNaksha Parcels │     - Vertical Navigation     │  - Parcel Meta    │  │
│  │   - User Selection    │     - Interactive Floor Click │  - Height/Confidence│
│  └───────────┬───────────┴───────────────┬───────────────┴─────────▲─────────┘  │
└──────────────│───────────────────────────│─────────────────────────│────────────┘
               │                           │                         │
               └───────────────────┬───────┴─────────────────────────┘
                                   │ (REST API / GeoJSON)
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              FASTAPI BACKEND                                    │
│                                                                                 │
│  - GET /api/v1/buildings (2D Footprints)                                        │
│  - GET /api/v1/parcels (BhuNaksha Cadastral)                                    │
│  - GET /api/v1/floors/{building_id} (3D Vertical Volumes)                       │
│  - GET /api/v1/dossier/{ulpin} (Property Dossier Metadata)                      │
│  - POST /api/v1/topology/validate (3D Conflict Validation Engine)               │
└──────────────────────────────────┬──────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       POSTGRESQL / POSTGIS DATABASE                             │
│                                                                                 │
│  - 2D/3D Geometry Storage (ST_3DExtrude, ST_3DIntersects)                       │
│  - Cadastral Parcel & Building Relationships                                    │
│  - Vertical Floor Strata & Prototype 3D ULPIN Indexing                          │
└──────────────────────────────────┬──────────────────────────────────────────────┘
                                   │
                                   ▼ (Future Extension)
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      OPENTOPOGRAPHY GROUND ELEVATION                            │
│                                                                                 │
│  - DEM Rasters / API for Absolute Terrain Elevation (Above Sea Level)           │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Component Details (Target):
1. **Unified 3-Pane Web Application**:
   - **LEFT PANE (Mapbox GL 2D Map)**: Renders 2D building footprints and BhuNaksha land parcel boundaries. Allows users to click and select buildings or parcels visually.
   - **CENTER PANE (Three.js 3D Viewer)**: Displays interactive 3D extruded floor volumes for selected buildings, with orbit controls, floor level selection, and vertical height controls.
   - **RIGHT PANE (Property Dossier)**: Displays comprehensive dossier cards for selected floors/ULPINs (prototype 3D ULPIN, BhuNaksha parcel details, height/floor confidence, volume, topology status).
2. **FastAPI Backend Services**:
   - Serves spatial data endpoints (GeoJSON/JSON) to the frontend.
   - Executes real-time 3D topology validation and conflict checks on demand.
3. **PostgreSQL / PostGIS Database**:
   - Persists 2D footprints, cadastral parcels, floor volume geometries, and 3D ULPIN indices using PostGIS 3D spatial capabilities (`ST_3DExtrude`, `ST_3DIntersects`, `ST_ZMin`, `ST_ZMax`).
4. **OpenTopography Terrain Integration (Later Phase)**:
   - Queries OpenTopography API / DEM datasets to obtain ground surface elevations above sea level (ASL), anchoring floor $Z_{\text{min}}$ and $Z_{\text{max}}$ values to actual physical terrain.

---

## 3. Explicit Accuracy & Domain Constraints

> [!IMPORTANT]
> All components of this system—both current and target—must adhere strictly to the following accuracy rules:
>
> 1. **OSM is Non-Authoritative Cadastral Data**: OpenStreetMap building footprints provide geometric boundaries for demonstration only and carry no official cadastral or legal authority.
> 2. **BhuNaksha is the Cadastral Source**: Telangana TGRAC BhuNaksha is the authoritative cadastral source used for the demonstrated land parcels (Parcels 140, 337, 92).
> 3. **Google Height Values are Satellite Estimates**: Building heights derived from Google Open Buildings 2.5D Temporal 2023 GeoTIFF rasters are remote sensing statistical estimates, not field-surveyed measurements.
> 4. **Estimated Floors Remain Marked Estimated**: Any floor count derived from height estimates (~3m/floor) must remain explicitly tagged as `is_floor_estimated=True` with confidence marked as `medium` or `low`.
> 5. **Prototype 3D ULPINs are Unofficial**: Prototype 3D ULPINs generated by this system (`PROTOTYPE_3D_VERTICAL_ID`) are research demonstration fingerprints and do NOT represent official government-issued land identifiers.
> 6. **Topology Conflicts are Geometric, Not Legal**: Identified 3D spatial overlaps are 3D geometric topology validation flags within the spatial dataset, not automated legal ownership dispute determinations.
