"""Artifact-backed provider for the official-data Manhattan validation profile."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import DataProvider, Feature


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "profiles" / "manhattan"


def _load(name: str) -> Any:
    path = DATA / name
    if not path.exists():
        raise RuntimeError(
            f"Manhattan profile artifact {name!r} is missing. Run pipeline/manhattan stages 01-08."
        )
    return json.loads(path.read_text(encoding="utf-8"))


class ManhattanFileProvider(DataProvider):
    backend_name = "file"
    requested_backend = "file"
    profile_id = "manhattan"

    def __init__(self) -> None:
        self._profile = _load("profile.json")
        self._buildings = _load("buildings.geojson")
        self._floors = _load("floors.geojson")
        self._units = _load("units.geojson")
        self._parcels = _load("tax_lots.geojson")
        self._topology = _load("topology_issues.json")
        self._building_index = {
            str(feature["properties"]["building_id"]): feature
            for feature in self._buildings.get("features", [])
        }
        self._floor_index: dict[str, list[Feature]] = {}
        self._floor_uid_index: dict[str, Feature] = {}
        for feature in self._floors.get("features", []):
            properties = feature.get("properties", {})
            self._floor_index.setdefault(str(properties.get("building_id")), []).append(feature)
            self._floor_uid_index[str(properties.get("prototype_id"))] = feature
        self._unit_index: dict[str, Feature] = {}
        self._building_units: dict[str, list[Feature]] = {}
        self._floor_units: dict[tuple[str, int], list[Feature]] = {}
        for feature in self._units.get("features", []):
            properties = feature.get("properties", {})
            building_id = str(properties.get("building_id"))
            floor_number = int(properties.get("floor_number", 0))
            uid = str(properties.get("prototype_unit_uid"))
            self._unit_index[uid] = feature
            self._building_units.setdefault(building_id, []).append(feature)
            self._floor_units.setdefault((building_id, floor_number), []).append(feature)
        for values in self._floor_index.values():
            values.sort(key=lambda item: int(item["properties"].get("floor_number", 0)))

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
    def _collection(features: list[Feature], *, include_units: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {"type": "FeatureCollection", "features": features}
        if include_units:
            result["units"] = features
        return result

    def health(self) -> dict[str, Any]:
        response = {
            "status": "ok",
            "data_backend": self.backend_name,
            "data_profile": self.profile_id,
            "buildings_loaded": len(self.building_features),
            "floor_units_loaded": len(self.floor_features),
            "units_loaded": len(self.unit_features),
            "parcels_loaded": len(self.parcel_features),
        }
        if self.fallback_reason:
            response.update({
                "requested_backend": self.requested_backend,
                "fallback": True,
                "fallback_reason": self.fallback_reason,
            })
        return response

    def stats(self) -> dict[str, Any]:
        confidence: dict[str, int] = {}
        for feature in self.building_features:
            label = str(feature["properties"].get("match_confidence_label", "UNKNOWN"))
            confidence[label] = confidence.get(label, 0) + 1
        return {
            "total_buildings": len(self.building_features),
            "total_floor_units": len(self.floor_features),
            "total_vertical_units": len(self.unit_features),
            "total_cadastral_parcels": len(self.parcel_features),
            "total_tax_lots": len(self.parcel_features),
            "vertical_buildings": self._profile["counts"]["vertical_buildings"],
            "processing_status": {
                "FULL_VERTICAL_MODEL": self._profile["counts"]["vertical_buildings"],
                "FOOTPRINT_ONLY": len(self.building_features) - self._profile["counts"]["vertical_buildings"],
            },
            "confidence": confidence,
            "prototype_3d_ids": len(self.floor_features),
            "prototype_unit_uids": len(self.unit_features),
            "temporary_3d_ids": 0,
            "synthetic_unit_count": len(self.unit_features),
            "topology_warnings": self._topology.get("topology_warnings", 0),
            "topology_errors": self._topology.get("topology_errors", 0),
        }

    def buildings(self, status: str | None = None) -> dict[str, Any]:
        features = self.building_features
        if status:
            features = [f for f in features if f["properties"].get("processing_status") == status]
        return self._collection(features)

    def building(self, building_id: str) -> dict[str, Any] | None:
        feature = self._building_index.get(building_id)
        if feature is None:
            return None
        properties = feature["properties"]
        quality = {
            "building_id": building_id,
            "quality_score": properties.get("match_confidence_score"),
            "quality_class": properties.get("match_confidence_label"),
            "topology_error_count": 0,
            "topology_warning_count": 0,
        }
        return {"building": feature, "quality": quality}

    def floors(self, building_id: str) -> dict[str, Any]:
        return self._collection(self._floor_index.get(building_id, []))

    def units(self, building_id: str) -> dict[str, Any]:
        return self._collection(self._building_units.get(building_id, []), include_units=True)

    def floor_units(self, building_id: str, floor_number: int) -> dict[str, Any]:
        return self._collection(self._floor_units.get((building_id, int(floor_number)), []), include_units=True)

    def unit_lookup(self, prototype_unit_uid: str) -> Feature | None:
        return self._unit_index.get(prototype_unit_uid)

    def parcels(self) -> dict[str, Any]:
        return self._parcels

    def parcel_lookup(self, parcel_no: str) -> dict[str, Any]:
        query = str(parcel_no).strip().lower()
        features = [
            feature for feature in self.parcel_features
            if query in {
                str(feature["properties"].get("tax_lot_id", "")).lower(),
                str(feature["properties"].get("source_lot_id", "")).lower(),
            }
        ]
        return self._collection(features)

    def ulpin_lookup(self, prototype_id: str) -> Feature | None:
        return self._floor_uid_index.get(prototype_id)

    def conflicts(self) -> list[dict[str, Any]]:
        return self._topology.get("issues", [])

    def search(self, query: str) -> dict[str, Any]:
        normalized = query.lower().strip()
        buildings = [
            feature for feature in self.building_features
            if any(normalized in str(feature["properties"].get(key, "")).lower() for key in (
                "building_id", "source_building_id", "tax_lot_id", "address", "name"
            ))
        ][:50]
        floors = [
            feature for feature in self.floor_features
            if normalized in str(feature["properties"].get("prototype_id", "")).lower()
        ][:50]
        units = [
            feature for feature in self.unit_features
            if any(normalized in str(feature["properties"].get(key, "")).lower() for key in (
                "prototype_unit_uid", "unit_id", "unit_label"
            ))
        ][:50]
        return {"query": query, "buildings": buildings, "floor_units": floors, "units": units}

    def profile_metadata(self) -> dict[str, Any]:
        return dict(self._profile)
