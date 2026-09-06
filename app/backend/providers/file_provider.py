"""Validated artifact-backed provider used by the resilient demo default."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from app.backend.adapters.elevation import ElevationAdapter
from app.backend.source_fusion import apply_to_collection
from app.backend.topology import normalize_issue
from profiles.hyderabad.config import PROFILE

from .base import DataProvider, Feature


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"


def _load_geojson(name: str, *, required: bool = True) -> dict[str, Any]:
    path = DATA / name
    if not path.exists() and not required:
        return {"type": "FeatureCollection", "features": []}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_csv(name: str) -> list[dict[str, str]]:
    path = DATA / name
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class FileProvider(DataProvider):
    backend_name = "file"
    requested_backend = "file"
    profile_id = "hyderabad"

    def __init__(self) -> None:
        # Use parcel-free building evidence until Telangana cadastral
        # redistribution permission is confirmed.
        self._buildings_collection = _load_geojson("all_buildings_vertical_enriched.geojson")
        self._floors_collection = {"type": "FeatureCollection", "features": []}
        self._parcels_collection = {"type": "FeatureCollection", "features": []}
        self._topology = _load_csv("all_topology_results.csv")
        enriched_buildings, enriched_floors = ElevationAdapter().enrich(
            self._buildings_collection.get("features", []),
            self._floors_collection.get("features", []),
        )
        self._buildings_collection["features"] = apply_to_collection(enriched_buildings)
        self._floors_collection["features"] = enriched_floors
        quality_rows = _load_csv("all_building_quality_summary.csv")
        self._quality = {row["building_id"]: row for row in quality_rows}
        self._building_index = {
            str(item.get("properties", {}).get("building_id")): item
            for item in self._buildings_collection.get("features", [])
        }
        self._floor_index: dict[str, list[Feature]] = {}
        self._ulpin_index: dict[str, Feature] = {}
        for feature in self._floors_collection.get("features", []):
            properties = feature.get("properties", {})
            building_id = str(properties.get("building_id"))
            self._floor_index.setdefault(building_id, []).append(feature)
            for key in ("prototype_id", "prototype_3d_ulpin"):
                if properties.get(key):
                    self._ulpin_index[str(properties[key])] = feature
        for values in self._floor_index.values():
            values.sort(key=lambda item: item.get("properties", {}).get("floor_number", 0))

    @property
    def building_features(self) -> list[Feature]:
        return self._buildings_collection.get("features", [])

    @property
    def floor_features(self) -> list[Feature]:
        return self._floors_collection.get("features", [])

    @property
    def parcel_features(self) -> list[Feature]:
        return self._parcels_collection.get("features", [])

    def health(self) -> dict[str, Any]:
        response: dict[str, Any] = {
            "status": "ok",
            "data_backend": self.backend_name,
            "data_profile": self.profile_id,
            "buildings_loaded": len(self.building_features),
            "floor_units_loaded": len(self.floor_features),
            "parcels_loaded": len(self.parcel_features),
        }
        if self.fallback_reason:
            response.update({
                "requested_backend": self.requested_backend,
                "fallback": True,
                "fallback_reason": self.fallback_reason,
            })
        return response

    def profile_metadata(self) -> dict[str, Any]:
        return PROFILE.as_dict()

    def stats(self) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        confidence_counts: dict[str, int] = {}
        for feature in self.building_features:
            properties = feature.get("properties", {})
            status = str(properties.get("processing_status", "UNKNOWN"))
            confidence = str(properties.get("data_confidence", "UNKNOWN"))
            status_counts[status] = status_counts.get(status, 0) + 1
            confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1

        prototype_ids = 0
        temporary_ids = 0
        for feature in self.floor_features:
            identifier_type = feature.get("properties", {}).get("ulpin_type")
            if identifier_type == "PROTOTYPE_3D_VERTICAL_ID":
                prototype_ids += 1
            elif identifier_type == "NON_CADASTRAL_TEMPORARY_ID":
                temporary_ids += 1

        warnings = sum(row.get("severity") == "WARNING" for row in self._topology)
        errors = sum(row.get("severity") == "ERROR" for row in self._topology)
        return {
            "total_buildings": len(self.building_features),
            "total_floor_units": len(self.floor_features),
            "total_cadastral_parcels": len(self.parcel_features),
            "processing_status": status_counts,
            "confidence": confidence_counts,
            "prototype_3d_ids": prototype_ids,
            "temporary_3d_ids": temporary_ids,
            "topology_warnings": warnings,
            "topology_errors": errors,
        }

    def buildings(self, status: str | None = None) -> dict[str, Any]:
        features = self.building_features
        if status:
            features = [
                item for item in features
                if item.get("properties", {}).get("processing_status") == status
            ]
        return {"type": "FeatureCollection", "features": features}

    def building(self, building_id: str) -> dict[str, Any] | None:
        feature = self._building_index.get(building_id)
        if feature is None:
            return None
        return {"building": feature, "quality": self._quality.get(building_id)}

    def floors(self, building_id: str) -> dict[str, Any]:
        return {
            "type": "FeatureCollection",
            "features": self._floor_index.get(building_id, []),
        }

    def parcels(self) -> dict[str, Any]:
        return self._parcels_collection

    def parcel_lookup(self, parcel_no: str) -> dict[str, Any]:
        query = str(parcel_no).strip().lower()
        fields = ("official_parcel_no", "parcel_no", "survey_no", "plot_no", "parcel_id")
        matches = []
        for feature in self.parcel_features:
            properties = feature.get("properties", {})
            if any(
                value is not None and str(value).strip().lower() == query
                for value in (properties.get(field) for field in fields)
            ):
                matches.append(feature)
        return {"type": "FeatureCollection", "features": matches}

    def ulpin_lookup(self, prototype_id: str) -> Feature | None:
        return self._ulpin_index.get(prototype_id)

    def conflicts(self) -> list[dict[str, Any]]:
        return [normalize_issue(row) for row in self._topology]

    def search(self, query: str) -> dict[str, Any]:
        normalized = query.lower().strip()
        building_results = []
        for feature in self.building_features:
            properties = feature.get("properties", {})
            values = (
                properties.get("building_id"), properties.get("name"),
                properties.get("official_parcel_no"), properties.get("village"),
                properties.get("mandal"), properties.get("district"),
            )
            if any(normalized in str(value).lower() for value in values if value is not None):
                building_results.append(feature)

        floor_results = []
        for feature in self.floor_features:
            properties = feature.get("properties", {})
            values = (
                properties.get("prototype_id"), properties.get("prototype_3d_ulpin"),
                properties.get("floor_id"),
            )
            if any(normalized in str(value).lower() for value in values if value is not None):
                floor_results.append(feature)

        return {
            "query": query,
            "buildings": building_results[:50],
            "floor_units": floor_results[:50],
        }
