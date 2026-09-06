"""Optional artifact-backed Amsterdam open-data provider.

The profile is intentionally empty until local PDOK/AHN downloads are
regenerated. It never fabricates buildings, parcels, floors, or units.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from profiles.amsterdam.config import PROFILE

from .base import DataProvider, Feature


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "profiles" / "amsterdam"


def _load(name: str) -> dict[str, Any]:
    path = DATA / name
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    return json.loads(path.read_text(encoding="utf-8"))


class AmsterdamFileProvider(DataProvider):
    backend_name = "file"
    requested_backend = "file"
    profile_id = "amsterdam"

    def __init__(self) -> None:
        self._buildings = _load("buildings.geojson")
        self._floors = _load("floors.geojson")
        self._units = _load("units.geojson")
        self._parcels = _load("parcels.geojson")
        self._roads = _load("roads.geojson")
        self._ward = _load("district.geojson")
        self._topology = _load("topology_issues.json")
        self._building_index = {
            str(feature.get("properties", {}).get("building_id")): feature
            for feature in self.building_features
        }

    @property
    def building_features(self) -> list[Feature]:
        return self._buildings.get("features", [])

    @property
    def floor_features(self) -> list[Feature]:
        return self._floors.get("features", [])

    @property
    def unit_features(self) -> list[Feature]:
        return self._units.get("features", [])

    @property
    def parcel_features(self) -> list[Feature]:
        return self._parcels.get("features", [])

    @staticmethod
    def _collection(features: list[Feature]) -> dict[str, Any]:
        return {"type": "FeatureCollection", "features": features}

    def health(self) -> dict[str, Any]:
        loaded = bool(self.building_features or self.parcel_features or self._roads.get("features"))
        return {
            "status": "ok",
            "data_backend": self.backend_name,
            "data_profile": self.profile_id,
            "buildings_loaded": len(self.building_features),
            "floor_units_loaded": len(self.floor_features),
            "units_loaded": len(self.unit_features),
            "parcels_loaded": len(self.parcel_features),
            "roads_loaded": len(self._roads.get("features", [])),
            "district_loaded": bool(self._ward.get("features")),
            "data_status": "LOCAL_ARTIFACTS_LOADED" if loaded else "LOCAL_ARTIFACTS_REQUIRED",
        }

    def stats(self) -> dict[str, Any]:
        issues = self._topology.get("issues", [])
        return {
            "total_buildings": len(self.building_features),
            "total_floor_units": len(self.floor_features),
            "total_vertical_units": len(self.unit_features),
            "total_cadastral_parcels": len(self.parcel_features),
            "total_tax_lots": len(self.parcel_features),
            "prototype_3d_ids": len(self.floor_features),
            "prototype_unit_uids": len(self.unit_features),
            "topology_warnings": sum(item.get("severity") == "WARNING" for item in issues),
            "topology_errors": sum(item.get("severity") == "ERROR" for item in issues),
        }

    def buildings(self, status: str | None = None) -> dict[str, Any]:
        features = self.building_features
        if status:
            features = [item for item in features if item.get("properties", {}).get("processing_status") == status]
        return self._collection(features)

    def building(self, building_id: str) -> dict[str, Any] | None:
        feature = self._building_index.get(building_id)
        return {"building": feature, "quality": {"building_id": building_id}} if feature else None

    def floors(self, building_id: str) -> dict[str, Any]:
        return self._collection([
            feature for feature in self.floor_features
            if str(feature.get("properties", {}).get("building_id")) == building_id
        ])

    def parcels(self) -> dict[str, Any]:
        return self._parcels

    def parcel_lookup(self, parcel_no: str) -> dict[str, Any]:
        query = str(parcel_no).lower().strip()
        return self._collection([
            feature for feature in self.parcel_features
            if query in json.dumps(feature.get("properties", {})).lower()
        ])

    def ulpin_lookup(self, prototype_id: str) -> Feature | None:
        return next((feature for feature in self.floor_features if prototype_id in {
            str(feature.get("properties", {}).get("prototype_id")),
            str(feature.get("properties", {}).get("prototype_3d_ulpin")),
        }), None)

    def conflicts(self) -> list[dict[str, Any]]:
        return self._topology.get("issues", [])

    def roads(self) -> dict[str, Any]:
        return self._roads

    def ward(self) -> dict[str, Any]:
        return self._ward

    def search(self, query: str) -> dict[str, Any]:
        normalized = query.lower().strip()
        buildings = [
            feature for feature in self.building_features
            if normalized in json.dumps(feature.get("properties", {})).lower()
        ][:50]
        return {"query": query, "buildings": buildings, "floor_units": [], "units": []}

    def profile_metadata(self) -> dict[str, Any]:
        return PROFILE.as_dict()