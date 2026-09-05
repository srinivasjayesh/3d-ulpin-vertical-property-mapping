"""FastAPI surface for the multi-profile vertical property mapping prototype."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database.connection import postgis_status
from profiles import get_profile, list_profiles

from .adapters.bim import BIMAdapter
from .adapters.elevation import ElevationAdapter
from .adapters.lidar import LiDARAdapter
from .providers import create_provider
from .providers.base import DataProvider
from .topology import hierarchy


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = os.getenv("DATA_PROFILE", "hyderabad").strip().lower()
elevation_adapter = ElevationAdapter()
bim_adapter = BIMAdapter()


@lru_cache(maxsize=4)
def _provider_for_id(profile_id: str) -> DataProvider:
    return create_provider(profile_id)


def provider_for(profile: str | None = None) -> DataProvider:
    profile_id = (profile or DEFAULT_PROFILE).strip().lower()
    try:
        get_profile(profile_id)
        return _provider_for_id(profile_id)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


provider = provider_for(DEFAULT_PROFILE)

app = FastAPI(title="3D Vertical Property Mapping Multi-Profile API", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/profiles")
def profiles():
    results = []
    for config in list_profiles():
        selected = provider_for(config.profile_id)
        metadata = selected.profile_metadata()
        results.append({
            **config.as_dict(),
            "default_hero": metadata.get("default_hero") or config.default_hero,
            "hero_buildings": metadata.get("hero_buildings") or list(config.hero_buildings),
            "health": selected.health(),
        })
    return {"default_profile": DEFAULT_PROFILE, "profiles": results}


@app.get("/api/health")
def health(profile: str | None = None):
    return provider_for(profile).health()


@app.get("/api/stats")
def stats(profile: str | None = None):
    return provider_for(profile).stats()


@app.get("/api/profile/{profile}/stats")
def profile_stats(profile: str):
    return provider_for(profile).stats()


@app.get("/api/system/capabilities")
def capabilities(profile: str | None = None):
    selected = provider_for(profile)
    profile_id = selected.profile_id
    postgis = postgis_status()
    elevation = elevation_adapter.capability()
    bim = bim_adapter.capability()
    lidar = LiDARAdapter(ROOT / "data" / "lidar" / profile_id).capability()
    if profile_id == "manhattan":
        sources = {
            "NYC Tax Lots": "ACTIVE",
            "NYC Building Footprints": "ACTIVE",
            "NYC PLUTO Attributes": "ACTIVE",
        }
        ground_elevation = "ACTIVE_SOURCE_ATTRIBUTE"
        unit_geometry = "SYNTHETIC_DEMO"
    elif profile_id == "mumbai":
        sources = {
            "MCGM G/South Ward Boundary": "ACTIVE",
            "BMC Reference Footprints": "ACTIVE_GEOMETRY_COMPARISON",
            "OSM Buildings": "ACTIVE_SOURCE_CONTEXT",
            "OSM Streets": "ACTIVE",
            "OSM Building Levels": "ACTIVE_SOURCE_ATTRIBUTE",
            "OSM Height Tags": "ACTIVE_SOURCE_ATTRIBUTE",
        }
        ground_elevation = "PENDING"
        unit_geometry = "NOT_AVAILABLE"
    else:
        sources = {"OSM": "ACTIVE", "BhuNaksha": "ACTIVE", "Google 2.5D": "ACTIVE"}
        ground_elevation = "PENDING"
        unit_geometry = "NOT_AVAILABLE"
    return {
        "data_profile": profile_id,
        "data_backend": selected.backend_name,
        "requested_backend": selected.requested_backend,
        "provider_fallback": bool(selected.fallback_reason),
        "provider_fallback_reason": selected.fallback_reason,
        "postgis": "ACTIVE" if postgis.get("status") == "ACTIVE" else "CODE_READY",
        "dem": "ACTIVE" if elevation["status"] == "ACTIVE" else "PENDING",
        "ground_elevation": ground_elevation,
        "bim": "LOADED" if bim["status"] == "BIM_LOADED" else (
            "NOT_LOADED" if profile_id == "hyderabad" else "ADAPTER_READY_NOT_LOADED"
        ),
        "lidar": "LOADED" if lidar["status"] == "LIDAR_LOADED" else (
            "NOT_LOADED" if profile_id == "hyderabad" else "ADAPTER_READY_NOT_LOADED"
        ),
        "unit_geometry": unit_geometry,
        "absolute_z": "SOURCE_ATTRIBUTE_AVAILABLE" if profile_id == "manhattan" else (
            "ACTIVE" if elevation["status"] == "ACTIVE" else "RELATIVE_Z_ONLY"
        ),
        "sources": sources,
        "pipeline_components": {
            "GeoPandas": "ACTIVE", "Shapely": "ACTIVE", "pyproj": "ACTIVE",
            "Rasterio": "ACTIVE", "FastAPI": "ACTIVE",
        },
        "details": {"postgis": postgis, "dem": elevation, "bim": bim, "lidar": lidar},
    }


@app.get("/api/buildings")
def get_buildings(status: str | None = None, profile: str | None = None):
    return provider_for(profile).buildings(status=status)


@app.get("/api/buildings/{building_id}")
def get_building(building_id: str, profile: str | None = None):
    result = provider_for(profile).building(building_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Building not found")
    return result


@app.get("/api/buildings/{building_id}/floors")
def get_building_floors(building_id: str, profile: str | None = None):
    result = provider_for(profile).floors(building_id)
    if not result.get("features"):
        raise HTTPException(status_code=404, detail="No floor model available for this building")
    return result


@app.get("/api/buildings/{building_id}/floors/{floor_number}/units")
def get_floor_units(building_id: str, floor_number: int, profile: str | None = None):
    selected = provider_for(profile)
    if selected.building(building_id) is None:
        raise HTTPException(status_code=404, detail="Building not found")
    return selected.floor_units(building_id, floor_number)


@app.get("/api/buildings/{building_id}/bim")
def get_building_bim(building_id: str, profile: str | None = None):
    details = provider_for(profile).building(building_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Building not found")
    properties = details["building"].get("properties", {})
    parcel_id = properties.get("matched_parcel_id") or properties.get("tax_lot_id")
    return bim_adapter.building(building_id, parcel_id)


@app.get("/api/buildings/{building_id}/units")
def get_building_units(building_id: str, profile: str | None = None):
    selected = provider_for(profile)
    details = selected.building(building_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Building not found")
    result = selected.units(building_id)
    if result.get("features") or result.get("units"):
        return result
    properties = details["building"].get("properties", {})
    parcel_id = properties.get("matched_parcel_id") or properties.get("tax_lot_id")
    return bim_adapter.units(building_id, parcel_id)


@app.get("/api/units/{prototype_unit_uid}")
def get_unit(prototype_unit_uid: str, profile: str | None = None):
    result = provider_for(profile).unit_lookup(prototype_unit_uid)
    if result is None:
        raise HTTPException(status_code=404, detail="Prototype unit UID not found")
    return result


@app.get("/api/buildings/{building_id}/topology")
def get_building_topology(building_id: str, profile: str | None = None):
    selected = provider_for(profile)
    details = selected.building(building_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Building not found")
    floors = selected.floors(building_id).get("features", [])
    units = selected.units(building_id).get("features", [])
    properties = details["building"].get("properties", {})
    parcel_id = properties.get("matched_parcel_id") or properties.get("tax_lot_id")
    bim = bim_adapter.building(building_id, parcel_id)
    return hierarchy(details["building"], floors, bim, units)


@app.get("/api/parcels")
def get_parcels(profile: str | None = None):
    return provider_for(profile).parcels()


@app.get("/api/roads")
def get_roads(profile: str | None = None):
    return provider_for(profile).roads()


@app.get("/api/ward")
def get_ward(profile: str | None = None):
    return provider_for(profile).ward()


@app.get("/api/parcels/{parcel_no}")
def get_parcel(parcel_no: str, profile: str | None = None):
    result = provider_for(profile).parcel_lookup(parcel_no)
    if not result.get("features"):
        raise HTTPException(status_code=404, detail="Parcel or tax lot not found")
    return result


@app.get("/api/ulpins/{prototype_id}")
def get_ulpin(prototype_id: str, profile: str | None = None):
    result = provider_for(profile).ulpin_lookup(prototype_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Prototype ID not found")
    return result


@app.get("/api/conflicts")
def get_conflicts(profile: str | None = None):
    return provider_for(profile).conflicts()


@app.get("/api/search")
def search(q: str = Query(..., min_length=1), profile: str | None = None):
    return provider_for(profile).search(q)


FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
