BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS profiles (
    profile_id text PRIMARY KEY,
    label text NOT NULL,
    city text NOT NULL,
    country text NOT NULL,
    study_area text NOT NULL,
    bbox jsonb NOT NULL,
    default_hero text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS data_sources (
    profile_id text NOT NULL REFERENCES profiles(profile_id) ON UPDATE CASCADE ON DELETE CASCADE,
    source_key text NOT NULL,
    source_name text NOT NULL,
    source_url text,
    operational_status text NOT NULL,
    source_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (profile_id, source_key)
);

CREATE TABLE IF NOT EXISTS parcels (
    parcel_id text PRIMARY KEY,
    profile_id text NOT NULL REFERENCES profiles(profile_id) ON UPDATE CASCADE ON DELETE CASCADE,
    official_parcel_no text,
    source_lot_id text,
    borough text,
    block integer,
    lot integer,
    village text,
    mandal text,
    district text,
    parcel_source text NOT NULL,
    geometry geometry(Geometry, 4326) NOT NULL,
    source_properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (profile_id, parcel_id)
);

CREATE TABLE IF NOT EXISTS buildings (
    building_id text PRIMARY KEY,
    profile_id text NOT NULL REFERENCES profiles(profile_id) ON UPDATE CASCADE ON DELETE CASCADE,
    source_building_id text,
    geometry geometry(Geometry, 4326) NOT NULL,
    height_m double precision,
    height_source text,
    height_is_estimated boolean,
    floor_count integer,
    floor_source text,
    floor_is_estimated boolean,
    floor_confidence text,
    processing_status text,
    matched_parcel_id text,
    official_parcel_no text,
    tax_lot_id text,
    borough text,
    block integer,
    lot integer,
    parcel_interpretation text,
    cadastral_boundary_label text,
    cadastral_confidence_score double precision,
    cadastral_confidence_label text,
    quality_score double precision,
    quality_class text,
    ground_elevation_m double precision,
    ground_elevation_source text,
    ground_elevation_confidence text,
    ground_elevation_status text NOT NULL DEFAULT 'GROUND_ELEVATION_PENDING',
    google_height_m double precision,
    osm_height_m double precision,
    lidar_height_m double precision,
    lidar_ground_m double precision,
    lidar_roof_m double precision,
    lidar_point_count integer,
    lidar_source text,
    lidar_confidence text,
    selected_height_m double precision,
    selected_height_source text,
    selected_height_confidence text,
    selected_height_is_estimated boolean,
    source_properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (profile_id, building_id),
    FOREIGN KEY (profile_id, matched_parcel_id)
        REFERENCES parcels(profile_id, parcel_id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS vertical_units (
    prototype_id text PRIMARY KEY,
    profile_id text NOT NULL REFERENCES profiles(profile_id) ON UPDATE CASCADE ON DELETE CASCADE,
    building_id text NOT NULL,
    parcel_id text,
    floor_number integer NOT NULL,
    z_min_relative_m double precision NOT NULL,
    z_max_relative_m double precision NOT NULL,
    ground_elevation_m double precision,
    z_min_absolute_m double precision,
    z_max_absolute_m double precision,
    footprint_area_m2 double precision,
    volume_m3 double precision,
    geometry geometry(Geometry, 4326) NOT NULL,
    identifier_type text NOT NULL,
    ulpin_is_official boolean NOT NULL DEFAULT false CHECK (ulpin_is_official = false),
    source_properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (profile_id, prototype_id),
    FOREIGN KEY (profile_id, building_id)
        REFERENCES buildings(profile_id, building_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (profile_id, parcel_id)
        REFERENCES parcels(profile_id, parcel_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CHECK (z_max_relative_m > z_min_relative_m),
    CHECK ((z_min_absolute_m IS NULL AND z_max_absolute_m IS NULL) OR z_max_absolute_m > z_min_absolute_m)
);

COMMENT ON COLUMN vertical_units.geometry IS
'Source 2D floor footprint in EPSG:4326. Vertical extent is stored as Z attributes; this is not claimed to be a volumetric PostGIS solid.';

CREATE TABLE IF NOT EXISTS units (
    prototype_unit_uid text PRIMARY KEY,
    profile_id text NOT NULL REFERENCES profiles(profile_id) ON UPDATE CASCADE ON DELETE CASCADE,
    unit_id text NOT NULL,
    building_id text NOT NULL,
    floor_prototype_id text NOT NULL,
    floor_number integer NOT NULL,
    parcel_id text,
    source_unit_id text,
    unit_label text,
    geometry geometry(Geometry, 4326) NOT NULL,
    unit_area_m2 double precision NOT NULL CHECK (unit_area_m2 > 0),
    unit_volume_m3 double precision NOT NULL CHECK (unit_volume_m3 > 0),
    z_min_relative_m double precision NOT NULL,
    z_max_relative_m double precision NOT NULL,
    z_min_absolute_m double precision,
    z_max_absolute_m double precision,
    unit_geometry_source text NOT NULL,
    unit_identifier_source text NOT NULL,
    unit_geometry_is_synthetic boolean NOT NULL,
    synthetic_layout_confidence text,
    ownership_status text NOT NULL,
    legal_status text NOT NULL,
    prototype_uid_type text NOT NULL,
    prototype_uid_is_official boolean NOT NULL DEFAULT false CHECK (prototype_uid_is_official = false),
    uid_algorithm_version text NOT NULL,
    uid_source_fields jsonb NOT NULL,
    source_properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (profile_id, unit_id),
    FOREIGN KEY (profile_id, building_id)
        REFERENCES buildings(profile_id, building_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (profile_id, floor_prototype_id)
        REFERENCES vertical_units(profile_id, prototype_id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (profile_id, parcel_id)
        REFERENCES parcels(profile_id, parcel_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CHECK (z_max_relative_m > z_min_relative_m),
    CHECK ((z_min_absolute_m IS NULL AND z_max_absolute_m IS NULL) OR z_max_absolute_m > z_min_absolute_m)
);

COMMENT ON COLUMN units.geometry IS
'2D unit/space footprint in EPSG:4326 plus explicit Z attributes. Synthetic records are demonstration subdivisions, never legal ownership boundaries.';

CREATE TABLE IF NOT EXISTS topology_issues (
    issue_key text PRIMARY KEY,
    profile_id text NOT NULL REFERENCES profiles(profile_id) ON UPDATE CASCADE ON DELETE CASCADE,
    severity text NOT NULL,
    issue_type text NOT NULL,
    issue_class text NOT NULL,
    building_id text,
    floor_id_1 text,
    floor_id_2 text,
    unit_id_1 text,
    unit_id_2 text,
    horizontal_overlap_m2 double precision,
    vertical_overlap_m double precision,
    z_reference text NOT NULL DEFAULT 'RELATIVE_Z_ONLY',
    message text,
    legal_status text NOT NULL DEFAULT 'NOT_A_LEGAL_DETERMINATION',
    source_record jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS processing_metadata (
    profile_id text NOT NULL REFERENCES profiles(profile_id) ON UPDATE CASCADE ON DELETE CASCADE,
    metadata_key text NOT NULL,
    metadata_value jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (profile_id, metadata_key)
);

CREATE INDEX IF NOT EXISTS parcels_geometry_gix ON parcels USING gist (geometry);
CREATE INDEX IF NOT EXISTS buildings_geometry_gix ON buildings USING gist (geometry);
CREATE INDEX IF NOT EXISTS vertical_units_geometry_gix ON vertical_units USING gist (geometry);
CREATE INDEX IF NOT EXISTS units_geometry_gix ON units USING gist (geometry);
CREATE INDEX IF NOT EXISTS parcels_profile_idx ON parcels (profile_id);
CREATE INDEX IF NOT EXISTS buildings_profile_idx ON buildings (profile_id);
CREATE INDEX IF NOT EXISTS vertical_units_profile_building_idx ON vertical_units (profile_id, building_id, floor_number);
CREATE INDEX IF NOT EXISTS units_profile_building_floor_idx ON units (profile_id, building_id, floor_number);
CREATE INDEX IF NOT EXISTS buildings_matched_parcel_idx ON buildings (profile_id, matched_parcel_id);
CREATE INDEX IF NOT EXISTS topology_profile_idx ON topology_issues (profile_id, building_id);

COMMIT;
