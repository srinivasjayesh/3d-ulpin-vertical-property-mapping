# Technology Guide

Python, GeoPandas, Shapely, pyproj and Rasterio implement the geospatial pipelines. OSM/Overpass and OSMnx provide open building/street context. GeoJSON is the interchange format. EPSG:4326 is the exchange CRS; Hyderabad uses EPSG:32644, Manhattan EPSG:32618 and Mumbai EPSG:32643 for metric calculations.

Google Open Buildings 2.5D supplies Hyderabad relative-height/presence observations; it is not a DEM or survey. BhuNaksha supplies Telangana parcel context. Leaflet renders the 2D map and Three.js renders approximate extrusions.

FastAPI is the read-only API. PostgreSQL/PostGIS has an optional schema/provider. DEM, LiDAR (LAS/LAZ with laspy) and BIM/IFC (IfcOpenShell) adapters exist, but no corresponding production files are present. pytest is used (22 passed, one PostGIS test skipped); GitHub Actions is not implemented.
