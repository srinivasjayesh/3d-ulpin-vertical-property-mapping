"""Validated Nanakramguda / Financial District profile."""

from profiles.config import ProfileConfig


PROFILE = ProfileConfig(
    profile_id="hyderabad",
    label="Hyderabad",
    city="Hyderabad",
    country="India",
    study_area="Nanakramguda / Financial District",
    bbox=(17.405, 78.337, 17.430, 78.370),
    center=(17.4177, 78.3542),
    map_zoom=15,
    default_hero="B0595",
    hero_buildings=("B0595", "B0612", "B0589"),
    parcel_term="Cadastral / survey parcel",
    sources={
        "building_geometry": "OpenStreetMap",
        "parcel_geometry": "Telangana TGRAC BhuNaksha",
        "height": "Google Open Buildings 2.5D Temporal 2023",
        "unit_geometry": "NOT_AVAILABLE",
    },
)
