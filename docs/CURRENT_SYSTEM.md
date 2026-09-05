# Current System Overview

> **Completion update (2026-09-05):** The implemented system now includes file/PostGIS provider abstraction, a PostGIS schema/importer, optional DEM/BIM/LiDAR adapters, source fusion, absolute-Z-aware topology semantics, a system-capability API/panel, single-server frontend hosting, and automated tests. Current external status is POSTGIS_CODE_READY, GROUND_ELEVATION_PENDING, BIM_NOT_LOADED, and LIDAR_NOT_LOADED. The validated baseline remains 635 buildings, 194 parcels, 2,100 vertical records, and the final heroes B0595/B0612/B0589. The historical baseline narrative below is retained for engineering traceability; where it mentions planned work or B0162, this update supersedes it.

The current UI also exposes Manhattan (Hudson Yards / West Midtown) and Mumbai G/South (Worli–Lower Parel) profiles. Manhattan demonstrates reusable unit-level API behavior. Mumbai uses the official BMC ward outline, OSM buildings/roads, explicit source heights only, and clearly labelled equal display strata where both heights and levels exist. Measured OSM/BMC footprint agreement is not cadastral confidence; missing heights, units and basements remain unavailable. See MUMBAI_PROFILE.md for evidence and limitations.

## 1. Problem Being Solved
Urban real estate in high-density Indian commercial and residential hubs (such as Hyderabad's Financial District) is increasingly vertical. Traditional land registries and cadastral systems track land in 2D parcels on the ground. This system demonstrates a prototype for **3D Unique Land Parcel Identification Numbering (3D ULPIN)** and **Vertical Property Mapping**, enabling floor-level spatial indexing, volumetric floor mapping, and 3D geometric conflict validation above 2D cadastral land parcels.

## 2. Current Study Area
- **Location**: Financial District / Nanakramguda, Hyderabad, Telangana, India.
- **Center Point**: Latitude `17.42007`, Longitude `78.35068`.
- **Bounding Radius**: 700 meters.

## 3. Base Dataset & Hero Buildings
- **OSM Footprints**: 635 building footprints extracted from OpenStreetMap (`raw_buildings.geojson` -> `buildings_clean.geojson`).
- **3 Deeply Processed Hero Buildings**:
  1. **`B0595`**: Commercial Office Tower (Footprint: ~2,580 $\text{m}^2$, Height: 79.5 m, 23 floors from OSM tags).
  2. **`B0612`**: Multi-story Apartment Complex (Footprint: ~2,642 $\text{m}^2$, Height: 53.5 m, 18 estimated floors).
  3. **`B0162`**: Low-rise Residential / Commercial Building (Footprint: ~104 $\text{m}^2$, Height: 7.5 m, 2 estimated floors).

## 4. Cadastral Parcel Sources
- **Source**: Telangana State Remote Sensing Applications Centre (TGRAC) BhuNaksha ArcGIS REST Service (`Bhunaksha_query/MapServer/0`).
- **Demonstrated Parcels**:
  - `B0595` maps to BhuNaksha Parcel **140** (Nanakramguda Village, Serilingampally Mandal, Ranga Reddy District).
  - `B0612` maps to BhuNaksha Parcel **337**.
  - `B0162` maps to BhuNaksha Parcel **92**.

## 5. Google Open Buildings Height Data
- **Source**: Google Open Buildings 2.5D Temporal 2023 GeoTIFF dataset (`tile_0PX-jEEaiBo.tif`).
- **Extraction Method**: Masked raster values using building footprints via `rasterio.mask`. Filtered valid height pixels (Band 2 height $> 0\text{m}$, Band 3 presence $> 0.5$).
- **Extracted Median Heights**:
  - `B0162`: 7.5 m
  - `B0595`: 79.5 m
  - `B0612`: 53.5 m

## 6. Floor Generation & Vertical Strata
- **Floor Count Determination**:
  - `B0595`: 23 floors (Source: OSM `building:levels`, `is_floor_estimated=False`, confidence: `high`).
  - `B0612`: 18 floors (Source: Google height estimate at ~3m/floor, `is_floor_estimated=True`, confidence: `medium`).
  - `B0162`: 2 floors (Source: Google height estimate at ~3m/floor, `is_floor_estimated=True`, confidence: `medium`).
- **Vertical Stratification**: Total height is divided equally among floor counts to yield floor height $\Delta z$. Each floor volume $i$ is assigned height boundaries $[z_{\text{min}}, z_{\text{max}}]$ where $z_{\text{min}} = (i-1) \times \Delta z$ and $z_{\text{max}} = i \times \Delta z$.
- **Total Volumes**: 43 2.5D volumetric floor parcels across the 3 hero buildings.

## 7. Prototype 3D ULPIN Generation
- **Format**: `P3D-{PARCEL_NO}-{BUILDING_ID}-F{FLOOR_NO:03d}-{SHA256_DIGEST}`
- **Canonical Input String**:
  `DISTRICT|MANDAL|VILLAGE|PARCEL_NO|BUILDING_ID|FLOOR_NO|LAT|LON|Z_MIN|Z_MAX`
- **Digest**: First 12 uppercase hexadecimal characters of SHA-256 hash.
- **Uniqueness**: 43 out of 43 prototype 3D ULPINs verified unique across the test set.

## 8. Topology & 3D Conflict Validation
- **Validation Engine (`18_validate_vertical_topology.py`)**:
  1. **Z-Range Sanity**: Checks $Z_{\text{max}} > Z_{\text{min}}$.
  2. **Vertical Continuity**: Checks for vertical gaps or overlaps between adjacent floors within a building (tolerance = 0.02 m).
  3. **3D Inter-Building Geometric Overlaps**: Checks if two volumes from different buildings intersect horizontally ($>0.02\text{m}^2$) AND overlap vertically ($>0.02\text{m}$).
- **Synthetic Conflict Verification (`19`, `20`)**: Tested by injecting a synthetic volume `TEST-CONFLICT-001` overlapping `B0595-F005`. The engine correctly detected and reported the $\text{m}^3$ overlap volume.

## 9. Web Viewers & Dashboard Systems
- **Legacy Standalone Viewer (`viewer/index.html`)**: Built by `21_build_3d_viewer.py`. Displays extruded 3D floor volumes and yellow 2D cadastral parcel outlines in a single Three.js viewport.
- **Unified 2D + 3D Dashboard (`dashboard/index.html`)**: New Stage 2 application layer:
  - **Left Panel**: Mapbox GL JS 2D map displaying 635 context buildings, BhuNaksha parcel outlines, and interactive hero building selection (with vector canvas fallback).
  - **Center Panel**: Three.js WebGL 3D viewer rendering volumetric floor strata for selected hero buildings (`B0595`, `B0612`, `B0162`).
  - **Right Panel**: Interactive property dossier rendering building metadata, cadastral parcel information, floor unit specs, prototype 3D ULPIN hashes, data source badges, and legal disclaimers.

## 10. Technology Matrix: Completed vs Pending

| Technology / Feature | Status | Implementation Details |
| :--- | :--- | :--- |
| **OSM Footprint Extraction** | Implemented | `osmnx` fetching 635 footprints |
| **Metric Vector GIS Processing** | Implemented | GeoPandas, Shapely, Pyproj (EPSG:4326 / EPSG:32644) |
| **Cadastral Parcel Integration** | Implemented | Telangana TGRAC BhuNaksha REST API |
| **Satellite Height Extraction** | Implemented | Google Open Buildings 2.5D GeoTIFF & Rasterio |
| **Volumetric Floor Stratification** | Implemented | 43 2.5D floor volume polygons |
| **Prototype 3D ULPIN Hashing** | Implemented | SHA-256 canonical hashing |
| **3D Topology & Conflict Engine** | Implemented | Vertical continuity & 3D geometric overlap detection |
| **3D Web Visualization** | Implemented | Three.js WebGL client viewer |
| **Unified 3-Panel Dashboard** | Implemented | HTML5, CSS3, Mapbox GL JS 2D + Three.js 3D + Dossier (`dashboard/`) |
| **Backend REST Service (FastAPI)** | Pending | Planned for API integration |
| **3D Spatial Database (PostGIS)** | Pending | Planned for database migration |
| **Ground Terrain Elevation (OpenTopography)**| Pending | Planned for absolute terrain alignment |

## 11. Core Accuracy & Legal Domain Rules
> [!IMPORTANT]
> 1. **OSM footprints are non-authoritative**: OpenStreetMap data provides spatial footprints for demonstration, not legal land titles.
> 2. **BhuNaksha is the cadastral source**: Telangana BhuNaksha is the official cadastral source used for the demonstrated parcels (Parcels 140, 337, 92).
> 3. **Google height values are estimates**: Building heights derived from Google Open Buildings 2.5D Temporal 2023 GeoTIFF rasters are satellite-derived statistical estimates.
> 4. **Estimated floors remain labelled estimated**: Estimated floor counts are explicitly tagged with `is_floor_estimated=True` and `medium` confidence.
> 5. **Prototype 3D ULPINs are unofficial**: Prototype 3D ULPINs generated by this system (`PROTOTYPE_3D_VERTICAL_ID`) are demonstration fingerprints, not official government-issued ULPINs.
> 6. **Topology conflicts are geometric, not legal**: Detected 3D spatial overlaps are spatial data validation flags, not legal ownership dispute determinations.
