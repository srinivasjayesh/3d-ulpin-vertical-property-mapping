# Data guide

The repository ships lightweight processed artifacts so the file-backed API and 3D viewer can be exercised offline. They are demonstration outputs, not an authoritative property database.

## Included demo artifacts

- `all_buildings_processed.geojson`: Hyderabad building features and derived processing fields.
- `all_floor_ulpins.geojson`: Hyderabad relative-Z floor strata and prototype IDs.
- `all_*_results.csv` and the small `hero_*` files: audit, quality, and demo outputs.
- `profiles/manhattan/`: processed NYC building, tax-lot, floor, and synthetic-unit outputs.
- `profiles/mumbai/`: processed G/South OSM/MCGM profile outputs; no unit geometry is claimed.

The application can start without the excluded Hyderabad parcel layer. In that mode `/api/parcels` is an empty collection and the rest of the file-backed demo remains available.

## Excluded inputs and regeneration

The following remain local-only and are ignored by Git:

- Google Open Buildings 2.5D GeoTIFF (`data/tile_*.tif`, approximately 849 MB).
- Telangana BhuNaksha cadastral parcel snapshots and comparison GeoJSON.
- The small `hero_parcels.geojson` BhuNaksha sample, which is also kept local because its redistribution terms are not confirmed.
- Mumbai raw BMC reference footprints, raw OSM extracts, and other raw source snapshots.
- Manhattan raw NYC Open Data downloads.
- DEM, IFC/BIM, and LAS/LAZ inputs.

Use the retrieval and processing scripts in `pipeline/`, `pipeline/manhattan/`, and `pipeline/mumbai/` to regenerate source artifacts locally. Network access and any provider-specific terms must be reviewed before redistributing regenerated data.

## Provenance

See [docs/DATA_LICENSES.md](../docs/DATA_LICENSES.md), [docs/DATA_PROVENANCE.md](../docs/DATA_PROVENANCE.md), [docs/MANHATTAN_PROFILE.md](../docs/MANHATTAN_PROFILE.md), and [docs/MUMBAI_PROFILE.md](../docs/MUMBAI_PROFILE.md).
