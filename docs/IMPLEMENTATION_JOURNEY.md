# Implementation Journey

The project progressed from Hyderabad OSM footprints to parcel matching, source heights, floor IDs, topology reports and a 3D viewer. Manhattan added NYC lot/building data and deterministic unit-layout experiments. Mumbai added a government ward boundary, BMC reference audit, OSM roads and conservative source-derived strata.

FastAPI and the file provider expose one profile-aware read surface. Optional PostGIS, elevation, BIM/IFC and LiDAR adapters document a production path but are not populated in this checkout.

Active code is under app/backend, app/frontend and pipeline. Root scripts and archived artifacts are retained as reproducibility history.
