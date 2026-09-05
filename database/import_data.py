"""Import Hyderabad and Manhattan artifacts into the profile-aware PostGIS schema."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from .connection import database_connection
except ImportError:
    from connection import database_connection


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def _geojson(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["features"]


def _csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(round(number)) if number is not None else None


def _boolean(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _geometry(feature: dict[str, Any]) -> str:
    return json.dumps(feature["geometry"], separators=(",", ":"))


def _properties(feature: dict[str, Any]) -> dict[str, Any]:
    return feature.get("properties", {})


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), default=str)


def profile_artifacts(profile_id: str) -> dict[str, Any]:
    if profile_id == "hyderabad":
        return {
            "parcels": _geojson(DATA / "study_area_cadastral_parcels.geojson"),
            "buildings": _geojson(DATA / "all_buildings_processed.geojson"),
            "floors": _geojson(DATA / "all_floor_ulpins.geojson"),
            "units": [],
            "topology": _csv(DATA / "all_topology_results.csv"),
        }
    if profile_id == "manhattan":
        folder = DATA / "profiles" / "manhattan"
        topology = json.loads((folder / "topology_issues.json").read_text(encoding="utf-8"))
        return {
            "parcels": _geojson(folder / "tax_lots.geojson"),
            "buildings": _geojson(folder / "buildings.geojson"),
            "floors": _geojson(folder / "floors.geojson"),
            "units": _geojson(folder / "units.geojson"),
            "topology": topology.get("issues", []),
        }
    raise ValueError(f"Unsupported profile {profile_id!r}")


def import_profile_record(cursor, profile_id: str) -> None:
    from profiles import get_profile

    config = get_profile(profile_id)
    metadata = config.as_dict()
    if profile_id == "manhattan":
        profile_file = DATA / "profiles" / "manhattan" / "profile.json"
        metadata.update(json.loads(profile_file.read_text(encoding="utf-8")))
    cursor.execute(
        """INSERT INTO profiles
            (profile_id, label, city, country, study_area, bbox, default_hero, metadata)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb)
            ON CONFLICT (profile_id) DO UPDATE SET
                label=EXCLUDED.label, city=EXCLUDED.city, country=EXCLUDED.country,
                study_area=EXCLUDED.study_area, bbox=EXCLUDED.bbox,
                default_hero=EXCLUDED.default_hero, metadata=EXCLUDED.metadata, updated_at=now()
        """,
        (profile_id, config.label, config.city, config.country, config.study_area,
         _json(list(config.bbox)), metadata.get("default_hero") or config.default_hero, _json(metadata)),
    )
    source_urls = {
        "hyderabad": {
            "building_geometry": ("OpenStreetMap / OSMnx", "https://www.openstreetmap.org"),
            "parcel_geometry": ("Telangana TGRAC BhuNaksha", "https://bhunaksha.telangana.gov.in"),
            "height": ("Google Open Buildings 2.5D Temporal 2023", "https://sites.research.google/gr/open-buildings/temporal/"),
        },
        "manhattan": {
            "building_geometry": ("NYC OTI Building Footprints", "https://data.cityofnewyork.us/d/5zhs-2jue"),
            "parcel_geometry": ("NYC DOF Digital Tax Map Tax Lots", "https://data.cityofnewyork.us/d/i38t-6if2"),
            "attributes": ("NYC DCP PLUTO", "https://data.cityofnewyork.us/d/64uk-42ks"),
            "unit_geometry": ("Deterministic synthetic subdivision", None),
        },
    }
    for key, (name, url) in source_urls[profile_id].items():
        status = "SYNTHETIC_DEMO" if key == "unit_geometry" else "ACTIVE"
        cursor.execute(
            """INSERT INTO data_sources
                (profile_id, source_key, source_name, source_url, operational_status)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (profile_id, source_key) DO UPDATE SET
                    source_name=EXCLUDED.source_name, source_url=EXCLUDED.source_url,
                    operational_status=EXCLUDED.operational_status, updated_at=now()
            """, (profile_id, key, name, url, status),
        )


def import_parcels(cursor, profile_id: str, features: list[dict[str, Any]]) -> None:
    sql = """INSERT INTO parcels
        (parcel_id, profile_id, official_parcel_no, source_lot_id, borough, block, lot,
         village, mandal, district, parcel_source, geometry, source_properties)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                ST_SetSRID(ST_GeomFromGeoJSON(%s),4326),%s::jsonb)
        ON CONFLICT (parcel_id) DO UPDATE SET
            geometry=EXCLUDED.geometry, source_properties=EXCLUDED.source_properties, updated_at=now()
    """
    rows = []
    for feature in features:
        p = _properties(feature)
        parcel_id = str(p.get("parcel_id") or p.get("tax_lot_id") or p.get("source_lot_id"))
        rows.append((
            parcel_id, profile_id, p.get("official_parcel_no"), p.get("source_lot_id"),
            p.get("borough"), _integer(p.get("block")), _integer(p.get("lot")),
            p.get("village"), p.get("mandal"), p.get("district"),
            p.get("parcel_source") or p.get("tax_lot_source") or "UNKNOWN",
            _geometry(feature), _json(p),
        ))
    cursor.executemany(sql, rows)


def import_buildings(cursor, profile_id: str, features: list[dict[str, Any]]) -> None:
    sql = """INSERT INTO buildings
        (building_id, profile_id, source_building_id, geometry, height_m, height_source,
         height_is_estimated, floor_count, floor_source, floor_is_estimated, floor_confidence,
         processing_status, matched_parcel_id, official_parcel_no, tax_lot_id, borough, block, lot,
         parcel_interpretation, cadastral_boundary_label, cadastral_confidence_score,
         cadastral_confidence_label, quality_score, quality_class, ground_elevation_m,
         ground_elevation_source, ground_elevation_confidence, ground_elevation_status,
         google_height_m, osm_height_m, lidar_height_m, lidar_ground_m, lidar_roof_m,
         lidar_point_count, lidar_source, lidar_confidence, selected_height_m,
         selected_height_source, selected_height_confidence, selected_height_is_estimated,
         source_properties)
        VALUES (%s,%s,%s,ST_SetSRID(ST_GeomFromGeoJSON(%s),4326),
         %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
         %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT (building_id) DO UPDATE SET
            geometry=EXCLUDED.geometry, selected_height_m=EXCLUDED.selected_height_m,
            floor_count=EXCLUDED.floor_count, source_properties=EXCLUDED.source_properties,
            updated_at=now()
    """
    rows = []
    for feature in features:
        p = _properties(feature)
        confidence = _number(p.get("cadastral_confidence_score") or p.get("match_confidence_score"))
        confidence_label = p.get("cadastral_confidence_text") or p.get("match_confidence_label")
        parcel_id = p.get("matched_parcel_id") or p.get("tax_lot_id")
        rows.append((
            str(p["building_id"]), profile_id, p.get("source_building_id"), _geometry(feature),
            _number(p.get("height_m") or p.get("selected_height_m")), p.get("height_source") or p.get("selected_height_source"),
            _boolean(p.get("is_height_estimated") if "is_height_estimated" in p else p.get("selected_height_is_estimated")),
            _integer(p.get("floor_count")), p.get("floor_source") or p.get("floor_count_source"),
            _boolean(p.get("is_floor_estimated") if "is_floor_estimated" in p else p.get("floor_count_is_estimated")),
            p.get("floor_count_confidence"), p.get("processing_status"), parcel_id,
            p.get("official_parcel_no"), p.get("tax_lot_id"), p.get("borough"),
            _integer(p.get("block")), _integer(p.get("lot")), p.get("parcel_interpretation"),
            p.get("cadastral_boundary_label"), confidence, confidence_label,
            confidence, confidence_label, _number(p.get("ground_elevation_m")),
            p.get("ground_elevation_source"), p.get("ground_elevation_confidence"),
            p.get("ground_elevation_status") or "GROUND_ELEVATION_PENDING",
            _number(p.get("google_height_m")), _number(p.get("osm_height_m")),
            _number(p.get("lidar_height_m")), _number(p.get("lidar_ground_m")),
            _number(p.get("lidar_roof_m")), _integer(p.get("lidar_point_count")),
            p.get("lidar_source"), p.get("lidar_confidence"), _number(p.get("selected_height_m")),
            p.get("selected_height_source"), p.get("selected_height_confidence"),
            _boolean(p.get("selected_height_is_estimated")), _json(p),
        ))
    cursor.executemany(sql, rows)


def import_floors(cursor, profile_id: str, features: list[dict[str, Any]]) -> dict[tuple[str, int], str]:
    sql = """INSERT INTO vertical_units
        (prototype_id, profile_id, building_id, parcel_id, floor_number,
         z_min_relative_m, z_max_relative_m, ground_elevation_m, z_min_absolute_m,
         z_max_absolute_m, footprint_area_m2, volume_m3, geometry, identifier_type,
         ulpin_is_official, source_properties)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                ST_SetSRID(ST_GeomFromGeoJSON(%s),4326),%s,%s,%s::jsonb)
        ON CONFLICT (prototype_id) DO UPDATE SET
            geometry=EXCLUDED.geometry, source_properties=EXCLUDED.source_properties, updated_at=now()
    """
    rows = []
    index: dict[tuple[str, int], str] = {}
    for feature in features:
        p = _properties(feature)
        prototype_id = str(p.get("prototype_id") or p.get("prototype_3d_ulpin"))
        building_id = str(p["building_id"])
        floor_number = int(p["floor_number"])
        index[(building_id, floor_number)] = prototype_id
        rows.append((
            prototype_id, profile_id, building_id, p.get("parcel_id") or p.get("matched_parcel_id") or p.get("tax_lot_id"),
            floor_number, _number(p.get("relative_z_min_m")), _number(p.get("relative_z_max_m")),
            _number(p.get("ground_elevation_m")), _number(p.get("absolute_z_min_m")),
            _number(p.get("absolute_z_max_m")), _number(p.get("footprint_area_m2") or p.get("floor_area_m2")),
            _number(p.get("volume_m3")), _geometry(feature),
            p.get("prototype_uid_type") or p.get("ulpin_type") or "PROTOTYPE_3D_VERTICAL_ID",
            False, _json(p),
        ))
    cursor.executemany(sql, rows)
    return index


def import_units(cursor, profile_id: str, features: list[dict[str, Any]], floor_index: dict[tuple[str, int], str]) -> None:
    sql = """INSERT INTO units
        (prototype_unit_uid, profile_id, unit_id, building_id, floor_prototype_id,
         floor_number, parcel_id, source_unit_id, unit_label, geometry, unit_area_m2,
         unit_volume_m3, z_min_relative_m, z_max_relative_m, z_min_absolute_m,
         z_max_absolute_m, unit_geometry_source, unit_identifier_source,
         unit_geometry_is_synthetic, synthetic_layout_confidence, ownership_status,
         legal_status, prototype_uid_type, prototype_uid_is_official,
         uid_algorithm_version, uid_source_fields, source_properties)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,ST_SetSRID(ST_GeomFromGeoJSON(%s),4326),
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
        ON CONFLICT (prototype_unit_uid) DO UPDATE SET
            geometry=EXCLUDED.geometry, source_properties=EXCLUDED.source_properties, updated_at=now()
    """
    rows = []
    for feature in features:
        p = _properties(feature)
        building_id = str(p["building_id"])
        floor_number = int(p["floor_number"])
        rows.append((
            p["prototype_unit_uid"], profile_id, p["unit_id"], building_id,
            floor_index[(building_id, floor_number)], floor_number, p.get("tax_lot_id"),
            p.get("source_unit_id"), p.get("unit_label"), _geometry(feature),
            _number(p.get("unit_area_m2")), _number(p.get("unit_volume_m3")),
            _number(p.get("relative_z_min_m")), _number(p.get("relative_z_max_m")),
            _number(p.get("absolute_z_min_m")), _number(p.get("absolute_z_max_m")),
            p.get("unit_geometry_source"), p.get("unit_identifier_source"),
            _boolean(p.get("unit_geometry_is_synthetic")), p.get("synthetic_layout_confidence"),
            p.get("ownership_status"), p.get("legal_status"), p.get("prototype_uid_type"),
            False, p.get("uid_algorithm_version"), _json(p.get("uid_source_fields", [])), _json(p),
        ))
    cursor.executemany(sql, rows)


def import_topology(cursor, profile_id: str, rows: list[dict[str, Any]]) -> None:
    sql = """INSERT INTO topology_issues
        (issue_key, profile_id, severity, issue_type, issue_class, building_id,
         floor_id_1, floor_id_2, unit_id_1, unit_id_2, horizontal_overlap_m2,
         vertical_overlap_m, z_reference, message, legal_status, source_record)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT (issue_key) DO UPDATE SET source_record=EXCLUDED.source_record, updated_at=now()
    """
    values = []
    for position, row in enumerate(rows, start=1):
        raw_key = f"{profile_id}|{position}|{_json(row)}"
        key = f"{profile_id}-{hashlib.sha256(raw_key.encode()).hexdigest()[:20]}"
        values.append((
            key, profile_id, row.get("severity", "WARNING"), row.get("issue_type", "TOPOLOGY_WARNING"),
            row.get("issue_class", "TOPOLOGY_WARNING"), row.get("building_id"), row.get("floor_id_1"),
            row.get("floor_id_2"), row.get("unit_id_1"), row.get("unit_id_2"),
            _number(row.get("horizontal_overlap_m2")), _number(row.get("vertical_overlap_m")),
            row.get("z_reference", "RELATIVE_Z_ONLY"), row.get("message"),
            row.get("legal_status", "NOT_A_LEGAL_DETERMINATION"), _json(row),
        ))
    if values:
        cursor.executemany(sql, values)


def verify(cursor) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for profile_id in ("hyderabad", "manhattan"):
        cursor.execute("""SELECT
            (SELECT count(*) FROM parcels WHERE profile_id=%s),
            (SELECT count(*) FROM buildings WHERE profile_id=%s),
            (SELECT count(*) FROM vertical_units WHERE profile_id=%s),
            (SELECT count(*) FROM units WHERE profile_id=%s)
        """, (profile_id,) * 4)
        parcels, buildings, floors, units = cursor.fetchone()
        result[profile_id] = {"parcels": parcels, "buildings": buildings, "floors": floors, "units": units}
    return result


def main() -> None:
    with database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
        for profile_id in ("hyderabad", "manhattan"):
            artifacts = profile_artifacts(profile_id)
            import_profile_record(cursor, profile_id)
            import_parcels(cursor, profile_id, artifacts["parcels"])
            import_buildings(cursor, profile_id, artifacts["buildings"])
            floor_index = import_floors(cursor, profile_id, artifacts["floors"])
            import_units(cursor, profile_id, artifacts["units"], floor_index)
            import_topology(cursor, profile_id, artifacts["topology"])
            cursor.execute(
                """INSERT INTO processing_metadata (profile_id, metadata_key, metadata_value)
                   VALUES (%s,'latest_import_counts',%s::jsonb)
                   ON CONFLICT (profile_id, metadata_key) DO UPDATE SET
                       metadata_value=EXCLUDED.metadata_value, updated_at=now()""",
                (profile_id, _json({key: len(value) for key, value in artifacts.items()})),
            )
        connection.commit()
        print(json.dumps(verify(cursor), indent=2))


if __name__ == "__main__":
    main()
