# 3D ULPIN — Master Documentation

## Problem
Property records are usually horizontal (parcel/building). This prototype adds a transparent vertical view: building → floor → prototype unit, with source, confidence and height shown alongside the geometry.

## Architecture
Python pipelines create GeoJSON/CSV. FastAPI reads those files (or optional PostGIS). The browser uses Leaflet for 2D context and Three.js for approximate 3D extrusions. API routes are read-only.

## File responsibilities

| Location | Responsibility |
|---|---|
| app/backend/main.py | FastAPI routes and static-file serving |
| app/backend/providers.py | File-backed profile loading and search |
| app/backend/postgis_provider.py, database/* | Optional PostGIS schema, import and queries |
| app/backend/elevation.py, bim.py, lidar.py | Optional DEM, IFC and LAS/LAZ adapters |
| app/frontend/index.html, app.js, styles.css, config.js | Viewer layout, controls, Leaflet map and Three.js scene |
| pipeline/01–09 | Hyderabad heights, parcels, statuses, floors, IDs, quality and topology |
| pipeline/manhattan | NYC lots/buildings, matching, floors, units and validation |
| pipeline/mumbai | MCGM/BMC/OSM audit, ward profile and conservative strata |
| tests/ | API, data-contract and topology checks |

## Data categories
Authoritative means published government/service geometry (BhuNaksha, NYC data, MCGM ward layer), but it is not proof of title. Contextual means OSM streets/buildings and map tiles. Estimated means floors derived from a height or incomplete tags. Derived means intersections, confidence, equal-height strata and topology. Synthetic means demonstration unit splits and Mumbai strata.

## City profiles
Hyderabad uses OSM, Google Open Buildings 2.5D and Telangana BhuNaksha. Manhattan uses NYC PLUTO/DoITT lots and buildings. Mumbai uses the MCGM G/South ward, BMC reference footprints and OSM buildings/roads.

Prototype ULPIN values are not government-issued identifiers. Study rectangles are not entire cities or legal wards. No verified IFC, LAS/LAZ or DEM files are present. Basement geometry is not available from current sources.

See [Technology](TECHNOLOGY_GUIDE.md), [Pipeline](END_TO_END_PIPELINE.md), [Provenance](DATA_PROVENANCE.md), [Database/API](DATABASE_AND_API.md), [Vertical model](VERTICAL_UNIT_MODEL.md), [Profiles](MULTI_CITY_PROFILES.md), [Journey](IMPLEMENTATION_JOURNEY.md), [Limitations](LIMITATIONS_AND_FUTURE_WORK.md), [Business](BUSINESS_MODEL_TAM_SAM_SOM.md), [Judge Q&A](JUDGE_QA.md), and [Demo](FINAL_DEMO_SCRIPT.md).
