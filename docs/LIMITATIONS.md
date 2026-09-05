# Limitations

- Profiles are selectable, not blended: Hyderabad and Manhattan keep separate source artifacts, IDs, counts, and provenance.
- Manhattan public sources provide building/tax-lot context, not official floor or unit ownership geometry. Its 8,130 unit polygons are deterministic synthetic subdivisions and are explicitly non-official.
- Manhattan `GROUND_ELEVATION` is retained as a source attribute; it does not by itself establish a surveyed absolute-Z model.
- The viewer's B1/B2 basement and parking compartments are derived demo volumes scaled from the building footprint. They are not verified below-ground surveys, excavation plans, or parking inventories.

- Prototype identifiers are not official government ULPINs and do not establish title, tenancy, or ownership.
- OSM footprints/tags are crowdsourced and non-cadastral.
- BhuNaksha polygons are cadastral/survey context, but matching across sources is geometric and may be affected by currency, alignment, generalization, or interpretation.
- Google Open Buildings 2.5D heights are satellite-derived estimates. They may include roof structures, temporal mismatch, or pixel/statistical error.
- Floor counts are estimated for 513 buildings. Floor strata are not apartment, office-suite, or ownership boundaries.
- All current floor Z coordinates are relative to local building ground. No real DEM is loaded, so cross-building absolute vertical conflict is not evaluated.
- Seven current cross-building overlaps are RELATIVE_Z_ONLY topology warnings, not legal conflicts or encroachments.
- No real IFC/BIM is loaded. The adapter treats IFC spaces as candidates and does not infer ownership.
- No real LAS/LAZ LiDAR is loaded. Satellite heights are not silently replaced.
- PostGIS code is ready but was not operationally tested because PostgreSQL/PostGIS is unavailable on the host.
- The frontend loads Leaflet/Three.js libraries and OSM tiles from external CDNs/services; offline use needs locally hosted assets and tiles.
- The API currently allows broad CORS for hackathon demonstration and has no authentication/authorization. Production government deployment requires identity, authorization, audit, privacy, retention, and threat controls.
- The repository has no Git metadata, so protected-script integrity is verified against preflight SHA-256 values in automated tests.
