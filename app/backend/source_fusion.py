"""Auditable, non-destructive vertical height source selection."""

from __future__ import annotations

import copy
import math
import re
from typing import Any


def _number(value: Any) -> float | None:
    if value in (None, "", "nan", "NaN"):
        return None
    if isinstance(value, str):
        match = re.search(r"[-+]?\d+(?:\.\d+)?", value)
        if not match:
            return None
        value = match.group(0)
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result > 0 else None


def select_vertical_source(properties: dict[str, Any]) -> dict[str, Any]:
    """Select the highest-priority usable height without dropping observations."""

    candidates = [
        (
            "SURVEY_VALIDATED",
            properties.get("survey_validated_height_m"),
            properties.get("survey_height_confidence", "VALIDATED"),
            False,
            bool(properties.get("survey_height_validated")),
        ),
        (
            "BIM_VALIDATED",
            properties.get("bim_validated_height_m"),
            properties.get("bim_height_confidence", "VALIDATED"),
            False,
            bool(properties.get("bim_height_validated")),
        ),
        (
            "LIDAR",
            properties.get("lidar_height_m"),
            properties.get("lidar_confidence", "MEASURED_POINT_CLOUD"),
            False,
            True,
        ),
        (
            "DSM_DEM_DERIVED",
            properties.get("dsm_dem_height_m"),
            properties.get("dsm_dem_height_confidence", "REMOTE_SENSING_ESTIMATE"),
            True,
            True,
        ),
        (
            "GOOGLE_OPEN_BUILDINGS_2_5D",
            properties.get("google_height_m"),
            properties.get("data_confidence", "REMOTE_SENSING_ESTIMATE"),
            True,
            True,
        ),
        (
            "OSM_HEIGHT",
            properties.get("osm_height_m", properties.get("height")),
            "CROWDSOURCED",
            True,
            True,
        ),
        (
            "MODEL_ESTIMATE",
            properties.get("estimated_height_m"),
            properties.get("estimated_height_confidence", "LOW"),
            True,
            True,
        ),
    ]
    observations = {
        name: _number(value)
        for name, value, _confidence, _estimated, eligible in candidates
        if eligible and _number(value) is not None
    }
    for name, value, confidence, estimated, eligible in candidates:
        parsed = _number(value)
        if eligible and parsed is not None:
            return {
                "selected_height_m": parsed,
                "selected_height_source": name,
                "selected_height_confidence": confidence,
                "selected_height_is_estimated": estimated,
                "vertical_height_sources": observations,
            }
    return {
        "selected_height_m": None,
        "selected_height_source": "UNAVAILABLE",
        "selected_height_confidence": "NONE",
        "selected_height_is_estimated": None,
        "vertical_height_sources": observations,
    }


def apply_to_feature(feature: dict[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(feature)
    properties = output.setdefault("properties", {})
    properties.update(select_vertical_source(properties))
    return output


def apply_to_collection(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [apply_to_feature(feature) for feature in features]
