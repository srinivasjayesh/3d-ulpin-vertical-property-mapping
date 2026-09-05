"""Profile-filtered PostGIS implementation of the provider contract."""

from __future__ import annotations

from typing import Any

from database.connection import database_connection, postgis_status
from profiles import get_profile

from .base import DataProvider, Feature


class PostGISProvider(DataProvider):
    backend_name = "postgis"
    requested_backend = "postgis"

    def __init__(self, profile_id: str = "hyderabad") -> None:
        self.profile_id = get_profile(profile_id).profile_id

    @staticmethod
    def _collection(features: list[Feature], *, include_units: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {"type": "FeatureCollection", "features": features}
        if include_units:
            result["units"] = features
        return result

    @staticmethod
    def _properties(table: str) -> str:
        if table == "buildings":
            return """source_properties || jsonb_strip_nulls(jsonb_build_object(
                'profile_id', profile_id, 'building_id', building_id,
                'source_building_id', source_building_id, 'matched_parcel_id', matched_parcel_id,
                'tax_lot_id', tax_lot_id, 'selected_height_m', selected_height_m,
                'selected_height_source', selected_height_source,
                'selected_height_confidence', selected_height_confidence,
                'selected_height_is_estimated', selected_height_is_estimated,
                'floor_count', floor_count, 'floor_count_source', floor_source,
                'floor_count_is_estimated', floor_is_estimated,
                'floor_count_confidence', floor_confidence,
                'ground_elevation_m', ground_elevation_m,
                'ground_elevation_source', ground_elevation_source,
                'ground_elevation_confidence', ground_elevation_confidence,
                'ground_elevation_status', ground_elevation_status
            ))"""
        if table == "vertical_units":
            return """source_properties || jsonb_strip_nulls(jsonb_build_object(
                'profile_id', profile_id, 'prototype_id', prototype_id,
                'building_id', building_id, 'floor_number', floor_number,
                'relative_z_min_m', z_min_relative_m, 'relative_z_max_m', z_max_relative_m,
                'absolute_z_min_m', z_min_absolute_m, 'absolute_z_max_m', z_max_absolute_m,
                'footprint_area_m2', footprint_area_m2, 'volume_m3', volume_m3,
                'ulpin_type', identifier_type, 'ulpin_is_official', ulpin_is_official
            ))"""
        if table == "units":
            return """source_properties || jsonb_strip_nulls(jsonb_build_object(
                'profile_id', profile_id, 'unit_id', unit_id, 'building_id', building_id,
                'floor_number', floor_number, 'unit_label', unit_label,
                'prototype_unit_uid', prototype_unit_uid,
                'unit_area_m2', unit_area_m2, 'unit_volume_m3', unit_volume_m3,
                'relative_z_min_m', z_min_relative_m, 'relative_z_max_m', z_max_relative_m,
                'absolute_z_min_m', z_min_absolute_m, 'absolute_z_max_m', z_max_absolute_m,
                'unit_geometry_source', unit_geometry_source,
                'unit_identifier_source', unit_identifier_source,
                'unit_geometry_is_synthetic', unit_geometry_is_synthetic,
                'synthetic_layout_confidence', synthetic_layout_confidence,
                'ownership_status', ownership_status, 'legal_status', legal_status,
                'prototype_uid_type', prototype_uid_type,
                'prototype_uid_is_official', prototype_uid_is_official,
                'uid_algorithm_version', uid_algorithm_version,
                'uid_source_fields', uid_source_fields
            ))"""
        return "source_properties"

    @classmethod
    def _feature_sql(cls, table: str, where: str = "TRUE", suffix: str = "") -> str:
        return f"""
            SELECT jsonb_build_object(
                'type', 'Feature', 'geometry', ST_AsGeoJSON(geometry)::jsonb,
                'properties', {cls._properties(table)}
            ) AS feature
            FROM {table}
            WHERE profile_id=%s AND ({where}) {suffix}
        """

    @staticmethod
    def _features(cursor) -> list[Feature]:
        return [row[0] for row in cursor.fetchall()]

    def health(self) -> dict[str, Any]:
        status = postgis_status()
        if status.get("status") != "ACTIVE":
            return {"status": "error", "data_backend": "postgis", "data_profile": self.profile_id, **status}
        try:
            with database_connection() as connection, connection.cursor() as cursor:
                cursor.execute("""SELECT
                    (SELECT count(*) FROM buildings WHERE profile_id=%s),
                    (SELECT count(*) FROM vertical_units WHERE profile_id=%s),
                    (SELECT count(*) FROM units WHERE profile_id=%s),
                    (SELECT count(*) FROM parcels WHERE profile_id=%s)
                """, (self.profile_id,) * 4)
                building_count, floor_count, unit_count, parcel_count = cursor.fetchone()
            return {
                "status": "ok", "data_backend": "postgis", "data_profile": self.profile_id,
                "buildings_loaded": building_count, "floor_units_loaded": floor_count,
                "units_loaded": unit_count, "parcels_loaded": parcel_count,
                "postgis_version": status.get("version"),
            }
        except Exception as exc:
            return {"status": "error", "data_backend": "postgis", "data_profile": self.profile_id, "detail": str(exc)}

    def stats(self) -> dict[str, Any]:
        with database_connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT processing_status, count(*) FROM buildings WHERE profile_id=%s GROUP BY processing_status", (self.profile_id,))
            statuses = {str(name): count for name, count in cursor.fetchall()}
            cursor.execute("SELECT source_properties->>'data_confidence', count(*) FROM buildings WHERE profile_id=%s GROUP BY 1", (self.profile_id,))
            confidence = {str(name or "UNKNOWN"): count for name, count in cursor.fetchall()}
            cursor.execute("SELECT identifier_type, count(*) FROM vertical_units WHERE profile_id=%s GROUP BY identifier_type", (self.profile_id,))
            identifiers = {str(name): count for name, count in cursor.fetchall()}
            cursor.execute("SELECT severity, count(*) FROM topology_issues WHERE profile_id=%s GROUP BY severity", (self.profile_id,))
            issues = {str(name): count for name, count in cursor.fetchall()}
            cursor.execute("""SELECT
                (SELECT count(*) FROM buildings WHERE profile_id=%s),
                (SELECT count(*) FROM vertical_units WHERE profile_id=%s),
                (SELECT count(*) FROM units WHERE profile_id=%s),
                (SELECT count(*) FROM parcels WHERE profile_id=%s)
            """, (self.profile_id,) * 4)
            building_count, floor_count, unit_count, parcel_count = cursor.fetchone()
        return {
            "total_buildings": building_count, "total_floor_units": floor_count,
            "total_vertical_units": unit_count, "total_cadastral_parcels": parcel_count,
            "total_tax_lots": parcel_count if self.profile_id == "manhattan" else 0,
            "processing_status": statuses, "confidence": confidence,
            "prototype_3d_ids": identifiers.get("PROTOTYPE_3D_VERTICAL_ID", 0),
            "prototype_unit_uids": unit_count, "temporary_3d_ids": identifiers.get("NON_CADASTRAL_TEMPORARY_ID", 0),
            "topology_warnings": issues.get("WARNING", 0), "topology_errors": issues.get("ERROR", 0),
        }

    def buildings(self, status: str | None = None) -> dict[str, Any]:
        with database_connection() as connection, connection.cursor() as cursor:
            if status:
                cursor.execute(self._feature_sql("buildings", "processing_status=%s"), (self.profile_id, status))
            else:
                cursor.execute(self._feature_sql("buildings"), (self.profile_id,))
            return self._collection(self._features(cursor))

    def building(self, building_id: str) -> dict[str, Any] | None:
        with database_connection() as connection, connection.cursor() as cursor:
            cursor.execute(self._feature_sql("buildings", "building_id=%s", "LIMIT 1"), (self.profile_id, building_id))
            row = cursor.fetchone()
            if row is None:
                return None
            cursor.execute("SELECT quality_score, quality_class FROM buildings WHERE profile_id=%s AND building_id=%s", (self.profile_id, building_id))
            score, quality_class = cursor.fetchone()
            return {"building": row[0], "quality": {"building_id": building_id, "quality_score": score, "quality_class": quality_class}}

    def floors(self, building_id: str) -> dict[str, Any]:
        with database_connection() as connection, connection.cursor() as cursor:
            cursor.execute(self._feature_sql("vertical_units", "building_id=%s", "ORDER BY floor_number"), (self.profile_id, building_id))
            return self._collection(self._features(cursor))

    def units(self, building_id: str) -> dict[str, Any]:
        with database_connection() as connection, connection.cursor() as cursor:
            cursor.execute(self._feature_sql("units", "building_id=%s", "ORDER BY floor_number, unit_id"), (self.profile_id, building_id))
            return self._collection(self._features(cursor), include_units=True)

    def floor_units(self, building_id: str, floor_number: int) -> dict[str, Any]:
        with database_connection() as connection, connection.cursor() as cursor:
            cursor.execute(self._feature_sql("units", "building_id=%s AND floor_number=%s", "ORDER BY unit_id"), (self.profile_id, building_id, floor_number))
            return self._collection(self._features(cursor), include_units=True)

    def unit_lookup(self, prototype_unit_uid: str) -> Feature | None:
        with database_connection() as connection, connection.cursor() as cursor:
            cursor.execute(self._feature_sql("units", "prototype_unit_uid=%s", "LIMIT 1"), (self.profile_id, prototype_unit_uid))
            row = cursor.fetchone()
            return row[0] if row else None

    def parcels(self) -> dict[str, Any]:
        with database_connection() as connection, connection.cursor() as cursor:
            cursor.execute(self._feature_sql("parcels"), (self.profile_id,))
            return self._collection(self._features(cursor))

    def parcel_lookup(self, parcel_no: str) -> dict[str, Any]:
        with database_connection() as connection, connection.cursor() as cursor:
            cursor.execute(self._feature_sql("parcels", "lower(coalesce(official_parcel_no,''))=lower(%s) OR lower(coalesce(source_lot_id,''))=lower(%s) OR lower(parcel_id)=lower(%s)"), (self.profile_id, parcel_no, parcel_no, parcel_no))
            return self._collection(self._features(cursor))

    def ulpin_lookup(self, prototype_id: str) -> Feature | None:
        with database_connection() as connection, connection.cursor() as cursor:
            cursor.execute(self._feature_sql("vertical_units", "prototype_id=%s", "LIMIT 1"), (self.profile_id, prototype_id))
            row = cursor.fetchone()
            return row[0] if row else None

    def conflicts(self) -> list[dict[str, Any]]:
        with database_connection() as connection, connection.cursor() as cursor:
            cursor.execute("""SELECT severity, issue_type, issue_class, building_id,
                floor_id_1, floor_id_2, unit_id_1, unit_id_2, horizontal_overlap_m2,
                vertical_overlap_m, z_reference, message, legal_status
                FROM topology_issues WHERE profile_id=%s ORDER BY issue_key""", (self.profile_id,))
            names = [item.name for item in cursor.description]
            return [dict(zip(names, row)) for row in cursor.fetchall()]

    def search(self, query: str) -> dict[str, Any]:
        pattern = f"%{query.strip()}%"
        with database_connection() as connection, connection.cursor() as cursor:
            cursor.execute(self._feature_sql("buildings", "building_id ILIKE %s OR coalesce(official_parcel_no,'') ILIKE %s OR source_properties::text ILIKE %s", "LIMIT 50"), (self.profile_id, pattern, pattern, pattern))
            buildings = self._features(cursor)
            cursor.execute(self._feature_sql("vertical_units", "prototype_id ILIKE %s", "LIMIT 50"), (self.profile_id, pattern))
            floors = self._features(cursor)
            cursor.execute(self._feature_sql("units", "prototype_unit_uid ILIKE %s OR unit_id ILIKE %s", "LIMIT 50"), (self.profile_id, pattern, pattern))
            units = self._features(cursor)
        return {"query": query, "buildings": buildings, "floor_units": floors, "units": units}

    def profile_metadata(self) -> dict[str, Any]:
        return get_profile(self.profile_id).as_dict()
