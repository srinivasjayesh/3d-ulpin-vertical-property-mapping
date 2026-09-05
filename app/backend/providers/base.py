"""Provider contract shared by file and PostGIS implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


Feature = dict[str, Any]


class DataProvider(ABC):
    backend_name = "unknown"
    requested_backend = "unknown"
    fallback_reason: str | None = None
    profile_id = "unknown"

    @abstractmethod
    def health(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def stats(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def buildings(self, status: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def building(self, building_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def floors(self, building_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def parcels(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def parcel_lookup(self, parcel_no: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def ulpin_lookup(self, prototype_id: str) -> Feature | None:
        raise NotImplementedError

    @abstractmethod
    def conflicts(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str) -> dict[str, Any]:
        raise NotImplementedError

    def units(self, building_id: str) -> dict[str, Any]:
        return {"type": "FeatureCollection", "features": [], "units": []}

    def floor_units(self, building_id: str, floor_number: int) -> dict[str, Any]:
        return {"type": "FeatureCollection", "features": [], "units": []}

    def unit_lookup(self, prototype_unit_uid: str) -> Feature | None:
        return None

    def roads(self) -> dict[str, Any]:
        return {"type": "FeatureCollection", "features": []}

    def ward(self) -> dict[str, Any]:
        return {"type": "FeatureCollection", "features": []}

    def profile_metadata(self) -> dict[str, Any]:
        return {"profile_id": self.profile_id, "hero_buildings": []}
