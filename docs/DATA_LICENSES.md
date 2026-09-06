# Data licenses and redistribution review

Reviewed 2026-09-05. This is a practical repository-publishing review, not legal advice. Source terms can change; re-check them before publishing a new snapshot.

| Dataset | Provider | Source | License | Attribution requirement | Redistribution status | Included in GitHub | Notes |
|---|---|---|---|---|---|---|---|
| OSM buildings, building parts, and streets | OpenStreetMap contributors | [OSM copyright/license](https://www.openstreetmap.org/copyright); Overpass URLs are retained in profile provenance | ODbL 1.0 | Credit OpenStreetMap contributors and link the ODbL/license page | Permitted subject to ODbL | Yes, as processed demo outputs | OSM footprints are not authoritative cadastral boundaries. |
| Google Open Buildings 2.5D height raster | Google Research | [Open Buildings](https://sites.research.google/gr/open-buildings/) | CC BY 4.0 or ODbL 1.0, at the user’s choice | Appropriate Google/Open Buildings attribution and license link | Permitted subject to selected license | No raw raster; derived height CSV retained | The approximately 849 MB GeoTIFF is excluded. Heights are satellite estimates, not surveys. |
| Telangana TGRAC BhuNaksha cadastral parcels | Telangana TGRAC | [BhuNaksha REST service](https://tgrac.telangana.gov.in/arcgis/rest/services/Bhunaksha_Folder/Bhunaksha/MapServer) | No explicit open redistribution license found; ArcGIS `licenseInfo` is empty | Retain Telangana TGRAC/BhuNaksha attribution and source URL | Unclear; do not redistribute bulk or sample snapshots | No | Retrieval and matching code is retained. Regenerate locally after confirming permission. |
| NYC OTI Building Footprints | City of New York / OTI | [NYC Open Data dataset](https://data.cityofnewyork.us/City-Government/BUILDING/5zhs-2jue) | NYC Open Data / NYC.gov terms; dataset-specific terms may apply | Identify source, version, and modifications; include City disclaimer where applicable | Publicly available, subject to NYC terms | Yes, processed artifacts; raw downloads no | Verify current dataset terms before publishing a refreshed raw snapshot. |
| NYC DOF tax lots and NYC DCP PLUTO | City of New York | [Tax lots](https://data.cityofnewyork.us/City-Government/TAX_LOT_POLYGON/i38t-6if2), [PLUTO](https://data.cityofnewyork.us/City-Government/Primary-Land-Use-Tax-Lot-Output-PLUTO-/64uk-42ks) | NYC Open Data / NYC.gov terms; dataset-specific terms may apply | Source/version/modification attribution and required disclaimers | Publicly available, subject to NYC terms | Yes, processed profile artifacts; raw downloads no | Units in this project are synthetic and are not supplied by NYC. |
| MCGM G/South ward boundary | Municipal Corporation of Greater Mumbai | [MCGM layer 341](https://prsrvgisapp.mcgm.gov.in/server/rest/services/mcgm/MCGMGIS_Departments_Master_All_Layers/MapServer/341) | No clear open redistribution grant found in available ArcGIS metadata | Retain MCGM source URL and ward attribution | **RETIRED — permission unclear** | No | Removed from active profile and publishable artifacts. |
| BMC building reference footprints | Municipal Corporation of Greater Mumbai | [MCGM layer 283](https://prsrvgisapp.mcgm.gov.in/server/rest/services/mcgm/MCGMGIS_Departments_Master_All_Layers/MapServer/283) | No clear open redistribution grant found in available ArcGIS metadata | Retain BMC/MCGM source URL and attribution | **RETIRED — permission unclear** | No | Removed from active profile and publishable artifacts. |
| Government Open Data datasets, where used | Government of India / data.gov.in | [Government Open Data License - India](https://data.gov.in/sites/default/files/Gazette_Notification_OGDL.pdf) | Government Open Data License - India | Provider, source, license, and URL/DOI in the attribution statement | Permitted only where the specific dataset is published under the license | None currently committed as a standalone bulk dataset | Do not infer this license for unrelated state or municipal ArcGIS services. |

## Active-profile decision

- **Hyderabad:** OSM and Google Open Buildings-derived context only. Telangana BhuNaksha and parcel-derived artifacts were removed from active/publishable data because redistribution permission was unclear.
- **Manhattan:** NYC Open Data artifacts remain subject to current NYC dataset terms, attribution, and disclaimers; synthetic units are clearly marked as synthetic.
- **Amsterdam:** OSM, PDOK BAG, and PDOK cadastral artifacts are locally regenerated with provenance. Re-check current provider terms before redistribution; AHN and PDOK source terms are not replaced by the project MIT license.
- **Mumbai:** Retired from active profiles. MCGM/BMC-derived artifacts were removed because redistribution permission was unclear.

## Interpretation rules

- The MIT `LICENSE` covers project code and documentation only; it does not relicense third-party data.
- `included` processed files are intentionally limited to demo/application outputs. They do not grant permission to redistribute the underlying source datasets beyond their applicable terms.
- If a provider’s current metadata is silent or ambiguous, keep raw/bulk data out of the public repository and publish retrieval, processing, attribution, and regeneration instructions instead.
