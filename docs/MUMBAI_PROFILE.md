# Mumbai G/South: Worli–Lower Parel

The active Mumbai profile now covers the official BMC **G/South** administrative ward. It replaces the former A Ward (Colaba–Fort) extract. The previous active artifacts and code are recoverable in `backups/mumbai-a-before-gsouth-20260905/`; the original A Ward raw downloads remain archived in `data/profiles/mumbai/raw/`.

## Why this ward

The downloaded G/South OSM extract contains **4,626 valid building/building-part ways**, including **573 with explicit level counts**. The H/East candidate contained 2,133 building/part ways and only 49 with explicit level counts. A D Ward download timed out and was not used to claim a comparison. The former A Ward profile had 307 buildings with tagged levels.

G/South provides recognizable height-tagged towers around Worli and Lower Parel. This is the stronger of the successfully compared alternatives, not a claim that every Mumbai ward was evaluated.

## Sources and reproducibility

- [Official MCGM Wards_DP, layer 341](https://prsrvgisapp.mcgm.gov.in/server/rest/services/mcgm/MCGMGIS_Departments_Master_All_Layers/MapServer/341): G/S polygon, source OBJECTID 7.
- [Official BMC Building footprints, layer 283](https://prsrvgisapp.mcgm.gov.in/server/rest/services/mcgm/MCGMGIS_Departments_Master_All_Layers/MapServer/283): independent reference geometry and raw source attributes. This is a building layer, not a parcel/ownership survey.
- [BMC G/South ward map](https://www.mcgm.gov.in/com.mcgm.wards/docs/GS/GS.pdf): locality context.
- OpenStreetMap closed building ways, building-part ways and highway ways, retrieved through the [documented Overpass service](https://wiki.openstreetmap.org/wiki/Overpass_API). OSM source way IDs, versions, timestamps and original tags are retained. Attribution: OpenStreetMap contributors, ODbL 1.0.

Raw snapshots, candidate comparisons, exact query parameters and retrieval timestamps are generated under the ignored `data/profiles/mumbai/raw/ward_review/` directory. The active `source_manifest.json` records provenance without requiring raw snapshots in the public repository. The responding Overpass server reported an OSM snapshot timestamp of **2026-06-01T08:52:28Z**, despite retrieval in September 2026. This is snapshot coverage, not a complete or current building census.

## Active snapshot

| Item | Count |
|---|---:|
| Mapped buildings / building parts | 4,626 |
| Explicit level counts | 573 |
| Explicit, usable height attributes | 28 |
| Buildings with derived floor strata | 23 |
| Derived vertical strata | 1,046 |
| OSM street segments clipped to ward | 1,803 |
| Valid BMC reference footprints in queried envelope | 9,168 |
| OSM features with measured reference overlap | 2,456 |
| Units generated | 0 |
| Basements generated | 0 |

The BMC download retrieved all 9,169 source IDs in the ward envelope in checked batches; one invalid reference polygon is excluded from comparisons. One invalid OSM source polygon is excluded and recorded in topology warnings. Ward membership uses each building polygon's representative point; building shapes are preserved and roads are clipped to the ward.

## Geometry evidence, not invented confidence

The dossier now displays a real measured value:

**Footprint agreement = 100 × area(OSM intersection BMC) / area(OSM union BMC)**

Areas are calculated in projected **EPSG:32643**, with the best overlapping individual BMC footprint selected. The BMC reference ID and count of other overlapping candidates are displayed. Raw reference geometry is retained, so the result can be independently recomputed.

Examples in this snapshot:

- Rustomjee Crown Tower B: **68.83%** footprint agreement.
- Mahalakshmi SRA: **73.91%**.
- Nishika Terrace: **74.36%**.

These percentages are **not positional accuracy, probability of a correct building match, cadastral confidence or ownership certainty**. Differing survey ages, building parts, demolition and redevelopment can cause disagreement. No overlapping reference means **Not available**, not a fabricated number. Cadastral confidence remains explicitly **Unavailable — no surveyed parcel reference**. The API's actual confidence fields remain null.

## No fabricated heights, units or basements

- Buildings are extruded only when an explicit OSM height tag can be parsed with known units. Explicit feet are converted to metres; missing heights remain flat footprints. Heights are not guessed from level counts.
- BMC's raw `HEIGHT` values are retained for provenance but **not used**: the attribute's units are not documented in the layer metadata. The geometry coordinate system being metric does not establish the units of this separate attribute.
- Floor strata require both an explicit source height and an integer source level count. Height is divided into equal strata for navigation, with any explicit roof height excluded. These are **source-derived display strata, not verified floor boundaries or floor plans**.
- Height/level combinations outside the builder's stated plausibility screen (2–8m per level), ambiguous level tags, and uncertain raised building-part bases are withheld from floor generation, not corrected by guessing. Original tags are preserved.
- No fixed 3.2m floor-height assumption remains in Mumbai.
- No unit subdivisions or automatic B1/B2 basements are generated for Mumbai. These controls show unavailable states when evidence is absent.
- Ground elevation and actual floor layouts remain unverified. Prototype IDs are not government-issued identifiers.
- Hyderabad and Manhattan data and modelling rules are unchanged.

## Rebuild and verification

From the repository directory:

```powershell
.\.runtime\Scripts\python.exe pipeline\mumbai\audit_sources.py
.\.runtime\Scripts\python.exe pipeline\mumbai\download_candidates.py
.\.runtime\Scripts\python.exe pipeline\mumbai\download_reference.py --ward G/S
.\.runtime\Scripts\python.exe pipeline\mumbai\build_profile.py
.\.runtime\Scripts\python.exe -m pytest -q
```

Use `download_candidates.py --cached` to compare only successful saved downloads without network access. The reference downloader checks ID completeness and rejects truncated responses. Rebuilding uses saved snapshots; changing the snapshots may legitimately change counts and metrics.

When the local raw BMC snapshot is present, the automated evidence tests independently recompute demonstration IoUs from its polygons. The public checkout skips that raw-snapshot-only assertion, while still checking source height/level parsing, missing-height behavior, explicit strata evidence, ward membership, and clipped roads.
