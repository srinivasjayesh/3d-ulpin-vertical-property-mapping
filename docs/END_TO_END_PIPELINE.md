# End-to-End Pipeline

1. Download source footprints and attributes.
2. Clean valid polygons and assign snapshot building IDs.
3. Reproject to the profile UTM CRS for metric calculations.
4. Extract available heights and retain source labels.
5. Match Hyderabad buildings to BhuNaksha parcels and calculate confidence.
6. Assign full, partial or context-only status.
7. Generate equal-height floor strata and deterministic prototype IDs.
8. Generate Manhattan strip units or Mumbai strata where supported.
9. Run topology checks and write reports.
10. Serve artifacts through FastAPI and render them in Leaflet/Three.js.

Browser coordinates are display approximations; validation uses projected geometry.
