# Limitations and Future Work

Current limitations: snapshot IDs are order/source dependent; OSM and parcel matches are not title evidence; height/floor estimates are not surveys; units are synthetic in Manhattan and absent in Mumbai; below-ground geometry is unavailable; browser 3D is approximate; no auth, edit workflow, IFC mesh viewer, DEM datum normalization or LiDAR files; no CI workflow.

Production path: obtain licensed cadastral and building registers; validate footprints and vertical datums; ingest DEM/LiDAR/IFC with CRS and unit checks; model real spaces and basements; use immutable source/version IDs; add PostGIS migrations, authentication, audit logs, tests and CI; deploy tiled 3D services.
