# Manhattan profile: Hudson Yards / West Midtown

The repository now supports a second, independently selectable data profile in addition to the validated Hyderabad profile. The Manhattan profile is a compact demonstration area bounded by `40.7520,-74.0055` and `40.7590,-73.9950` (center `40.7555,-74.0002`, zoom 16).

## Official source inputs

- [NYC OTI Building Footprints](https://data.cityofnewyork.us/City-Government/BUILDING/5zhs-2jue), Socrata `5zhs-2jue`: building geometry, BIN/BBL where present, `HEIGHT_ROOF`, and `GROUND_ELEVATION` source attributes.
- [NYC DOF Digital Tax Map Tax Lot Polygon](https://data.cityofnewyork.us/City-Government/TAX_LOT_POLYGON/i38t-6if2), Socrata `i38t-6if2`: tax-lot geometry and BBL.
- [NYC DCP PLUTO](https://data.cityofnewyork.us/City-Government/Primary-Land-Use-Tax-Lot-Output-PLUTO-/64uk-42ks), Socrata `64uk-42ks`: optional lot/building attributes keyed by BBL.

The reproducible download/match/enrichment flow is in `pipeline/manhattan/01_download_tax_lots.py` through `08_validate_topology.py` (the matching stage is `03_match_buildings_taxlots.py`; UID generation is `07_generate_vertical_ids.py`). The current checked-in artifacts contain 146 source footprints, 164 tax lots, 133 matched/enriched buildings, 1,827 floor records, and 8,130 prototype unit records.

## Height and floor interpretation

`HEIGHT_ROOF` is retained as the source roof-height attribute. Floor counts are deterministic estimates derived from that height and a documented floor-height heuristic when an authoritative floor count is not available. `GROUND_ELEVATION` is exposed as a source attribute; it is not silently converted into a surveyed absolute-Z model.

## Unit interpretation

NYC public datasets used here do not provide unit ownership geometry. The unit layer is therefore a deterministic oriented subdivision of each matched building footprint, generated only to exercise floor/unit navigation. Every unit has `is_synthetic=true`, `is_official=false`, and a `P3DU-NYC-*` prototype UID. It must not be interpreted as a tax-lot, condominium, address, owner, or legal identifier.

## Rebuild and run

```powershell
.\.runtime\Scripts\python.exe pipeline/manhattan/01_download_tax_lots.py
.\.runtime\Scripts\python.exe pipeline/manhattan/02_download_buildings.py
.\.runtime\Scripts\python.exe pipeline/manhattan/03_match_buildings_taxlots.py
.\.runtime\Scripts\python.exe pipeline/manhattan/04_enrich_buildings.py
.\.runtime\Scripts\python.exe pipeline/manhattan/05_generate_floors.py
.\.runtime\Scripts\python.exe pipeline/manhattan/06_generate_units.py
.\.runtime\Scripts\python.exe pipeline/manhattan/07_generate_vertical_ids.py
.\.runtime\Scripts\python.exe pipeline/manhattan/08_validate_topology.py
```

The download steps require internet access. The FastAPI UI can switch profiles without restarting:

`GET /api/profiles`, `GET /api/stats?profile=manhattan`, and `GET /api/units/{prototype_unit_uid}?profile=manhattan` are the key integration checks.
