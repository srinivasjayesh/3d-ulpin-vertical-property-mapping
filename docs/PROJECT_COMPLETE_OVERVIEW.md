# 3D ULPIN Project — Complete Handoff Overview

## 1. Purpose

This project is a research/hackathon prototype for exploring vertical property mapping: a 2D site or parcel context is linked to a building, floor-level volumes, and (where publicly available) prototype unit geometry. Prototype IDs are not government-issued ULPINs and geometric confidence is not legal or survey accuracy.

## 2. Build journey

1. **Hyderabad baseline** — Nanakramguda / Financial District data was assembled from OpenStreetMap footprints, Telangana TGRAC BhuNaksha cadastral context, and Google Open Buildings height evidence. The original validation workflow and protected root scripts remain unchanged.
2. **Vertical model** — Building footprints were converted into relative-Z floor volumes, deterministic prototype floor IDs were generated, and topology checks were added.
3. **Multi-profile architecture** — FastAPI providers, profile configuration, file-backed artifacts, and the profile switch were introduced so each city can be selected without changing the UI code.
4. **Manhattan validation profile** — NYC OTI footprints, DOF tax lots, PLUTO attributes, source height/elevation fields, and deterministic synthetic unit subdivisions were added. Units are explicitly marked synthetic and non-official.
5. **Mumbai replacement profile** — The retired temporary profile was removed. The initial A Ward was subsequently replaced by G/South (Worli–Lower Parel), selected for stronger source-tag coverage among successfully compared candidates. Official BMC ward/reference footprints and OSM building/highway ways are retained with provenance. Only explicit source heights create 3D models; both height and levels are required for equal display strata. Actual floor plans remain unverified.
6. **Interaction and visual refinement** — Context-vs-isolate viewing, persistent orbit/pan/zoom camera state, direct building/floor/unit search, prominent selected IDs, below-ground cutaway controls, ward outlines, Ward 3D framing, and responsive panel layout were added.

## 3. Current profiles

| Profile | Source-backed content | Current snapshot |
|---|---|---:|
| Hyderabad | OSM + Telangana BhuNaksha + Google Open Buildings | 635 buildings, 2,100 floor records |
| Manhattan | NYC OTI + DOF Digital Tax Map + PLUTO | 133 buildings, 1,827 floors, 8,130 synthetic units |
| Mumbai · G/South | Official BMC ward/reference footprints + OSM buildings/roads | 4,626 buildings/parts, 28 height models, 1,046 derived strata, 1,803 road segments |

Mumbai ward source: [MCGM `Wards_DP` layer](https://prsrvgisapp.mcgm.gov.in/server/rest/services/mcgm/MCGMGIS_Departments_Master_All_Layers/MapServer/341).

## 4. Main application features

- **Profile switch:** Hyderabad, Manhattan, and Mumbai are served by one API/UI.
- **Study map:** Leaflet/OpenStreetMap basemap, building footprints, roads, selected-building highlight, and darker study/ward boundary.
- **3D building scene:** Three.js floor volumes, context buildings, road lines, metric grid, orbit, pan, and zoom.
- **Building fallback:** Mumbai uses an exact tagged-height mass when available; missing heights are highlighted flat footprints, never invented extrusions.
- **Ward 3D:** Frames the complete available boundary. Mumbai uses the official ward polygon; Hyderabad and Manhattan use their configured study-area boundary because no ward polygon is loaded for those profiles.
- **Isolate Building:** Hides context while preserving the selected building.
- **Panel controls:** Left map and right dossier can be collapsed and reopened. The viewer expands correctly when either or both side panels are hidden.
- **Explicit zoom controls:** 3D Zoom In and Zoom Out buttons supplement mouse-wheel zoom.
- **Below Ground:** Hyderabad and Manhattan retain clearly labelled derived B1/B2 cutaway compartments, not surveyed basement plans. Mumbai disables these controls because verified basement geometry is absent.
- **Search:** Building IDs, source IDs, tax lots, floor prototype IDs, and Manhattan synthetic unit UIDs are supported. Exact floor/unit matches select the corresponding object.
- **Dossier:** Shows source fields, floor provenance, confidence, unit status, basement evidence, ward relationship, and non-official/synthetic disclaimers.

## 5. Data integrity rules

- No official unit ownership geometry is claimed for Mumbai.
- Mumbai display strata require explicit OSM height and integer level tags. Equal divisions are explicitly labelled as source-derived, not verified floor boundaries. Unknown heights remain flat; no fixed 3.2m height assumption is used.
- Mumbai geometry evidence shows measured projected OSM/BMC footprint IoU. This is not cadastral confidence; actual confidence fields remain null. Missing overlap is unavailable, not zero or an invented score.
- Manhattan PLUTO `BsmtCode` is carried as basement type/grade evidence. It does not publish underground-level counts, so the UI does not invent extra basement floors.
- Hyderabad/Manhattan B1/B2 below-ground geometry is intentionally labelled `DERIVED_DEMO` for interaction and cutaway demonstration. Mumbai generates none.

## 6. API surface

- `GET /api/profiles`
- `GET /api/health?profile=...`
- `GET /api/stats?profile=...`
- `GET /api/system/capabilities?profile=...`
- `GET /api/buildings`, `/api/buildings/{id}`, `/api/buildings/{id}/floors`
- `GET /api/buildings/{id}/floors/{floor}/units` (Manhattan synthetic units)
- `GET /api/parcels`, `GET /api/roads`, `GET /api/ward`
- `GET /api/search?q=...`

## 7. Running the application

```powershell
cd C:\Users\srini\ulpin-prototype
.runtime\Scripts\python.exe -m uvicorn app.backend.main:app --host 127.0.0.1 --port 8765
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/). Keep the terminal open while using the app.

## 8. Verification completed

- Frontend syntax: `node --check app/frontend/app.js`
- Python compilation: `compileall` for app, database, profiles, and pipelines
- Automated tests: **22 passed, 1 skipped**, including independent Mumbai footprint-overlap recomputation and source-evidence constraints
- Dependency check: `pip check` reports no broken requirements
- Live API checks: profile discovery, Mumbai health/stats, ward geometry, roads, building lookup, floor lookup, and search

## 9. Known limitations

This remains a prototype. Relative-Z floors are not absolute surveyed elevations; Mumbai has no matched public building-specific floor-plan source in the checked-in snapshot; no profile provides authoritative basement-level counts; and Manhattan unit polygons are deterministic synthetic interaction geometry rather than ownership boundaries.
