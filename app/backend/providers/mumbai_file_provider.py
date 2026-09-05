"""Artifact-backed Mumbai G/South provider.

The artifacts contain official MCGM ward geometry plus OSM buildings/roads.
Strata require explicit OSM height and level evidence; no guessed heights.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import DataProvider, Feature

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "profiles" / "mumbai"


def _load(name: str) -> Any:
    path = DATA / name
    if not path.exists():
        raise RuntimeError(f"Mumbai profile artifact {name!r} is missing. Run pipeline/mumbai/build_profile.py.")
    return json.loads(path.read_text(encoding="utf-8"))


class MumbaiFileProvider(DataProvider):
    backend_name = "file"
    requested_backend = "file"
    profile_id = "mumbai"

    def __init__(self) -> None:
        self._profile = _load("profile.json")
        self._buildings = _load("buildings.geojson")
        self._floors = _load("floors.geojson")
        self._units = _load("units.geojson")
        self._parcels = _load("tax_lots.geojson")
        self._roads = _load("roads.geojson")
        self._ward = _load("ward.geojson")
        self._topology = _load("topology_issues.json")
        self._building_index = {str(f["properties"]["building_id"]): f for f in self.building_features}
        self._floor_index: dict[str, list[Feature]] = {}
        self._floor_uid_index: dict[str, Feature] = {}
        for feature in self.floor_features:
            props = feature.get("properties", {})
            self._floor_index.setdefault(str(props.get("building_id")), []).append(feature)
            self._floor_uid_index[str(props.get("prototype_id"))] = feature
        for values in self._floor_index.values():
            values.sort(key=lambda item: int(item["properties"].get("floor_number", 0)))

    @property
    def building_features(self) -> list[Feature]: return self._buildings.get("features", [])
    @property
    def floor_features(self) -> list[Feature]: return self._floors.get("features", [])
    @property
    def unit_features(self) -> list[Feature]: return self._units.get("features", [])
    @property
    def parcel_features(self) -> list[Feature]: return self._parcels.get("features", [])
    @staticmethod
    def _collection(features: list[Feature]) -> dict[str, Any]: return {"type": "FeatureCollection", "features": features}

    def health(self) -> dict[str, Any]:
        return {"status": "ok", "data_backend": self.backend_name, "data_profile": self.profile_id,
                "buildings_loaded": len(self.building_features), "floor_units_loaded": len(self.floor_features),
                "units_loaded": len(self.unit_features), "parcels_loaded": len(self.parcel_features),
                "roads_loaded": len(self._roads.get("features", [])), "ward_loaded": bool(self._ward.get("features"))}

    def stats(self) -> dict[str, Any]:
        return {"total_buildings": len(self.building_features), "total_floor_units": len(self.floor_features),
                "total_vertical_units": 0, "total_cadastral_parcels": 0, "total_tax_lots": 0,
                "vertical_buildings": self._profile["counts"]["vertical_buildings"],
                "processing_status": {"VERTICAL_3D_PARTIAL": self._profile["counts"]["vertical_buildings"],
                                       "CONTEXT_ONLY": len(self.building_features) - self._profile["counts"]["vertical_buildings"]},
                "prototype_3d_ids": len(self.floor_features), "prototype_unit_uids": 0, "temporary_3d_ids": 0,
                "synthetic_unit_count": 0, "topology_warnings": self._topology.get("topology_warnings", 0),
                "topology_errors": self._topology.get("topology_errors", 0)}

    def buildings(self, status: str | None = None) -> dict[str, Any]:
        features = self.building_features if not status else [f for f in self.building_features if f["properties"].get("processing_status") == status]
        return self._collection(features)
    def building(self, building_id: str) -> dict[str, Any] | None:
        feature = self._building_index.get(building_id)
        if feature is None: return None
        props = feature.get("properties", {})
        return {"building": feature, "quality": {"building_id": building_id, "quality_score": None,
                "quality_class": "SOURCE_GEOMETRY", "topology_error_count": 0, "topology_warning_count": 0,
                "footprint_agreement_pct": props.get("footprint_agreement_pct"),
                "agreement_method": props.get("footprint_agreement_method"),
                "reference_building_id": props.get("reference_building_id"),
                "confidence_reason": props.get("geometry_confidence_reason")}}
    def floors(self, building_id: str) -> dict[str, Any]: return self._collection(self._floor_index.get(building_id, []))
    def units(self, building_id: str) -> dict[str, Any]: return self._collection([])
    def floor_units(self, building_id: str, floor_number: int) -> dict[str, Any]: return self._collection([])
    def unit_lookup(self, prototype_unit_uid: str) -> Feature | None: return None
    def parcels(self) -> dict[str, Any]: return self._parcels
    def parcel_lookup(self, parcel_no: str) -> dict[str, Any]: return self._collection([])
    def ulpin_lookup(self, prototype_id: str) -> Feature | None: return self._floor_uid_index.get(prototype_id)
    def conflicts(self) -> list[dict[str, Any]]: return self._topology.get("issues", [])
    def roads(self) -> dict[str, Any]: return self._roads
    def ward(self) -> dict[str, Any]: return self._ward
    def search(self, query: str) -> dict[str, Any]:
        normalized = query.lower().strip()
        buildings = [f for f in self.building_features if any(normalized in str(f["properties"].get(k, "")).lower() for k in ("building_id", "source_building_id", "address", "name"))][:50]
        floors = [f for f in self.floor_features if normalized in str(f["properties"].get("prototype_id", "")).lower()][:50]
        return {"query": query, "buildings": buildings, "floor_units": floors, "units": []}
    def profile_metadata(self) -> dict[str, Any]: return dict(self._profile)
