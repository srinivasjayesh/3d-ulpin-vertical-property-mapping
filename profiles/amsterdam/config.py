"""Amsterdam Centrum benchmark profile based on Dutch open geodata services."""

from profiles.config import ProfileConfig


PROFILE = ProfileConfig(
    profile_id="amsterdam",
    label="Amsterdam · Centrum",
    city="Amsterdam",
    country="Netherlands",
    study_area="Amsterdam Centrum borough",
    bbox=(52.358, 4.865, 52.392, 4.925),
    center=(52.375, 4.895),
    map_zoom=14,
    default_hero="",
    hero_buildings=(),
    parcel_term="Dutch cadastral parcel",
    sources={
        "administrative_boundary": "PDOK Bestuurlijke Gebieden / Amsterdam stadsdeel boundary",
        "building_geometry": "PDOK BAG (Basisregistratie Adressen en Gebouwen)",
        "topography": "PDOK BGT (Basisregistratie Grootschalige Topografie)",
        "parcel_geometry": "PDOK Kadastrale Kaart / Kadastrale Percelen",
        "terrain_and_lidar": "AHN open raster and point-cloud data",
        "orthophoto": "PDOK Luchtfoto RGB Open",
        "roads_and_context": "PDOK BGT and OpenStreetMap",
        "height": "AHN-derived terrain/DSM plus BAG attributes where available",
        "floor_geometry": "NOT_AVAILABLE_UNTIL_FLOOR_PLAN_OR_BIM_SOURCE",
        "unit_geometry": "NOT_AVAILABLE_UNTIL_APPROVED_FLOOR_PLAN",
        "license_status": "OPEN_DATA_REVIEW_REQUIRED_PER_DATASET",
    },
)