"""Mumbai G/South profile with source-backed geometry and measured agreement."""

from profiles.config import ProfileConfig

PROFILE = ProfileConfig(
    profile_id="mumbai",
    label="Mumbai · G/South",
    city="Mumbai",
    country="India",
    study_area="G/South (Worli–Lower Parel)",
    bbox=(18.978031021407176, 72.80582655157484, 19.026859394362994, 72.83637063620472),
    center=(18.998250976123686, 72.82175977374996),
    map_zoom=13,
    default_hero="",
    hero_buildings=(),
    parcel_term="MCGM ward",
    sources={
        "ward_geometry": "MCGM GIS Wards_DP layer (official ward boundary)",
        "building_geometry": "OpenStreetMap buildings and building parts inside MCGM G/South",
        "geometry_reference": "BMC Building layer 283; measured footprint IoU in EPSG:32643",
        "roads": "OpenStreetMap highway ways clipped to MCGM G/South",
        "height": "Explicit OSM height tags only; no assumed height",
        "floor_geometry": "Equal strata derived from source height AND levels; not verified floor plans",
        "basement_geometry": "NOT_AVAILABLE_NO_GENERATED_BASEMENTS",
        "unit_geometry": "NOT_AVAILABLE",
    },
)
