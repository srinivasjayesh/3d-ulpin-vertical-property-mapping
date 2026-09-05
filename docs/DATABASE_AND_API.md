# Database and API

The default FileProvider reads profile GeoJSON/CSV. The optional PostGIS schema contains profiles, data_sources, parcels, buildings, vertical_units, units, topology_issues and processing_metadata, with GiST indexes. Geometry is stored as 2D geometry plus numeric Z fields; it is not a solid model.

Main read routes are /api/profiles, /api/buildings, /api/buildings/{id}, /api/floors/{number}/units, /api/units, /api/parcels, /api/roads, /api/ward, /api/ulpins/{id}, /api/topology, /api/system/capabilities and /api/search?q=...

There is no authentication, write API, title registry or automatic legal validation. The current import script supports Hyderabad and Manhattan artifacts; Mumbai remains file-backed.
