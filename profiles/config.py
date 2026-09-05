"""Shared profile configuration and discovery."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ProfileConfig:
    profile_id: str
    label: str
    city: str
    country: str
    study_area: str
    bbox: tuple[float, float, float, float]
    center: tuple[float, float]
    map_zoom: int
    default_hero: str
    hero_buildings: tuple[str, ...]
    parcel_term: str
    sources: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["bbox"] = list(self.bbox)
        result["center"] = list(self.center)
        result["hero_buildings"] = list(self.hero_buildings)
        return result


def _registry() -> dict[str, ProfileConfig]:
    from .hyderabad.config import PROFILE as hyderabad
    from .manhattan.config import PROFILE as manhattan
    from .mumbai.config import PROFILE as mumbai

    return {item.profile_id: item for item in (hyderabad, manhattan, mumbai)}


def get_profile(profile_id: str) -> ProfileConfig:
    normalized = profile_id.strip().lower()
    try:
        return _registry()[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported DATA_PROFILE={profile_id!r}") from exc


def list_profiles() -> list[ProfileConfig]:
    return list(_registry().values())
