# 3D ULPIN Hyderabad — Unified 2D + 3D Dashboard

## Overview
This standalone web dashboard integrates 2D cadastral mapping, 3D vertical floor volume rendering, and property dossier inspection for the SIH prototype **3D ULPIN Generation and Vertical Property Mapping System**.

---

## Panel Architecture

1. **Left Panel — 2D Mapbox Map**:
   - Renders 635 OSM building footprints around Financial District / Nanakramguda, Hyderabad.
   - Highlights official Telangana TGRAC BhuNaksha cadastral parcel boundaries (Parcels 140, 337, 92).
   - Highlights the 3 fully processed hero buildings (**`B0595`**, **`B0612`**, **`B0162`**).
   - Features interactive selection for hero buildings and context OSM footprints.

2. **Center Panel — Three.js 3D Viewer**:
   - Renders 3D extruded volumetric floor strata for the selected hero building using real $Z_{\text{min}}$ and $Z_{\text{max}}$ height bounds.
   - Supports OrbitControls (zoom, rotate, pan), camera resetting, floor edge wireframe rendering, and floor selection via 3D raycasting.

3. **Right Panel — Property Dossier**:
   - Displays building-level metadata, cadastral parcel information, floor count, height sources, and confidence ratings.
   - Displays floor-level metadata and canonical **Prototype 3D ULPINs** when individual floor units are clicked.
   - Prominently displays mandatory legal disclaimers and data source badges.

---

## Quick Start (Running Locally)

1. Start a local HTTP server from the project root directory:
   ```bash
   python -m http.server 8000
   ```

2. Open your web browser and navigate to:
   ```text
   http://localhost:8000/dashboard/
   ```

---

## Mapbox Access Token Configuration

The 2D map uses Mapbox GL JS. To enable vector tile basemaps:

1. Copy `dashboard/config.example.js` to `dashboard/config.js`:
   ```bash
   cp dashboard/config.example.js dashboard/config.js
   ```

2. Edit `dashboard/config.js` and insert your Mapbox public token:
   ```javascript
   window.APP_CONFIG = {
       MAPBOX_TOKEN: "<MAPBOX_PUBLIC_TOKEN>"
   };
   ```

*Note: If no Mapbox token is provided, the dashboard automatically activates an interactive vector canvas preview fallback, maintaining full functionality for testing.*

---

## Accuracy Disclaimers
- **OSM Footprints**: Non-authoritative spatial context data.
- **BhuNaksha Parcels**: Official cadastral source used for demonstrated parcels (140, 337, 92).
- **Google Height Data**: Satellite-derived statistical estimates from Google Open Buildings 2.5D (2023).
- **Prototype 3D ULPIN**: Research demonstration format (`PROTOTYPE_3D_VERTICAL_ID`), not official government-issued land titles.
- **Topology Overlaps**: Represent 3D geometric spatial validation flags, not legal ownership dispute determinations.
