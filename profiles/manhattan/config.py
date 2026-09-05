"""Compact Hudson Yards / West Midtown validation profile."""

from profiles.config import ProfileConfig


PROFILE = ProfileConfig(
    profile_id="manhattan",
    label="Manhattan",
    city="New York City",
    country="United States",
    study_area="Hudson Yards / West Midtown",
    bbox=(40.7520, -74.0055, 40.7590, -73.9950),
    center=(40.7555, -74.0002),
    map_zoom=16,
    default_hero="",
    hero_buildings=(),
    parcel_term="NYC tax lot",
    sources={
        "building_geometry": "NYC OTI Building Footprints (5zhs-2jue)",
        "parcel_geometry": "NYC DOF Digital Tax Map Tax Lot Polygon (i38t-6if2)",
        "attributes": "NYC DCP PLUTO (64uk-42ks)",
        "height": "NYC OTI Building Footprints HEIGHT_ROOF",
        "ground_elevation": "NYC OTI Building Footprints GROUND_ELEVATION",
        "unit_geometry": "SYNTHETIC_SUBDIVISION",
    },
)
