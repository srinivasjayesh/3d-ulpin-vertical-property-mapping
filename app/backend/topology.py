"""Topology vocabulary and vertical-reference-aware relationship helpers."""

from __future__ import annotations

from typing import Any


def normalize_issue(row: dict[str, Any]) -> dict[str, Any]:
    output = dict(row)
    issue_type = str(output.get("issue_type", "TOPOLOGY_WARNING"))
    absolute = "ABSOLUTE" in issue_type or output.get("z_reference") == "ABSOLUTE_Z"
    output["z_reference"] = "ABSOLUTE_Z" if absolute else "RELATIVE_Z_ONLY"
    output["issue_class"] = (
        "GEOMETRIC_CONFLICT"
        if absolute and output.get("severity") == "ERROR"
        else "TOPOLOGY_WARNING"
    )
    output["legal_status"] = "NOT_A_LEGAL_DETERMINATION"
    if not absolute:
        output["interpretation"] = (
            "Relative floor heights cannot establish cross-building absolute vertical overlap."
        )
    return output


def vertical_relation(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    absolute_keys = ("absolute_z_min_m", "absolute_z_max_m")
    has_absolute = all(first.get(key) is not None and second.get(key) is not None for key in absolute_keys)
    if has_absolute:
        first_min, first_max = float(first[absolute_keys[0]]), float(first[absolute_keys[1]])
        second_min, second_max = float(second[absolute_keys[0]]), float(second[absolute_keys[1]])
        reference = "ABSOLUTE_Z"
    else:
        first_min = float(first.get("relative_z_min_m", first.get("z_min_relative_m", 0)))
        first_max = float(first.get("relative_z_max_m", first.get("z_max_relative_m", 0)))
        second_min = float(second.get("relative_z_min_m", second.get("z_min_relative_m", 0)))
        second_max = float(second.get("relative_z_max_m", second.get("z_max_relative_m", 0)))
        reference = "RELATIVE_Z_ONLY"
    overlap = min(first_max, second_max) - max(first_min, second_min)
    if overlap > 0:
        relation = "VERTICAL_OVERLAP"
    elif first_max <= second_min:
        relation = "BELOW"
    else:
        relation = "ABOVE"
    return {
        "relation": relation,
        "z_reference": reference,
        "vertical_overlap_m": max(0.0, overlap),
    }


def cross_building_vertical_assessment(
    first: dict[str, Any], second: dict[str, Any], horizontal_overlap_m2: float
) -> dict[str, Any]:
    relation = vertical_relation(first, second)
    if relation["z_reference"] != "ABSOLUTE_Z":
        return {
            "issue_class": "TOPOLOGY_WARNING",
            "issue_type": "CADASTRAL_CONTEXT_WARNING",
            "z_reference": "RELATIVE_Z_ONLY",
            "geometric_conflict": False,
            "legal_status": "NOT_A_LEGAL_DETERMINATION",
            "message": "Horizontal overlap observed, but absolute Z is unavailable; no cross-building vertical conflict is asserted.",
        }
    conflict = horizontal_overlap_m2 > 0 and relation["relation"] == "VERTICAL_OVERLAP"
    return {
        "issue_class": "GEOMETRIC_CONFLICT" if conflict else "TOPOLOGY_WARNING",
        "issue_type": "GEOMETRIC_CONFLICT" if conflict else "TOPOLOGY_WARNING",
        "z_reference": "ABSOLUTE_Z",
        "geometric_conflict": conflict,
        "vertical_overlap_m": relation["vertical_overlap_m"],
        "legal_status": "NOT_A_LEGAL_DETERMINATION",
        "message": (
            "Absolute-Z geometric overlap detected; this is not a legal encroachment finding."
            if conflict
            else "No absolute-Z vertical overlap detected."
        ),
    }


def hierarchy(
    building: dict[str, Any],
    floors: list[dict[str, Any]],
    bim: dict[str, Any] | None = None,
    units: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    properties = building.get("properties", {})
    floor_nodes = []
    relationships = []
    previous = None
    for feature in sorted(floors, key=lambda f: f.get("properties", {}).get("floor_number", 0)):
        floor = feature.get("properties", {})
        node = {
            "floor_id": floor.get("floor_id"),
            "floor_number": floor.get("floor_number"),
            "relative_z_min_m": floor.get("relative_z_min_m"),
            "relative_z_max_m": floor.get("relative_z_max_m"),
            "absolute_z_min_m": floor.get("absolute_z_min_m"),
            "absolute_z_max_m": floor.get("absolute_z_max_m"),
            "prototype_id": floor.get("prototype_id"),
        }
        floor_nodes.append(node)
        relationships.append({
            "subject": node["floor_id"],
            "predicate": "WITHIN",
            "object": properties.get("building_id"),
        })
        if previous is not None:
            relationships.append({
                "subject": node["floor_id"],
                "predicate": "ABOVE",
                "object": previous["floor_id"],
                **vertical_relation(node, previous),
            })
        previous = node

    unit_nodes = []
    for feature in units or []:
        unit = feature.get("properties", {})
        node = {
            "unit_id": unit.get("unit_id"),
            "floor_id": unit.get("floor_id"),
            "prototype_unit_uid": unit.get("prototype_unit_uid"),
            "unit_geometry_source": unit.get("unit_geometry_source"),
            "unit_geometry_is_synthetic": unit.get("unit_geometry_is_synthetic"),
        }
        unit_nodes.append(node)
        relationships.append({
            "subject": node["unit_id"],
            "predicate": "WITHIN",
            "object": node["floor_id"],
            "legal_status": "NOT_A_LEGAL_DETERMINATION",
        })

    parcel_id = properties.get("matched_parcel_id") or properties.get("tax_lot_id")
    if parcel_id:
        relationships.append({
            "subject": properties.get("building_id"),
            "predicate": str(properties.get("spatial_relationship", "INTERSECTS")).upper(),
            "object": parcel_id,
            "classification": "CADASTRAL_CONTEXT_WARNING" if properties.get("parcel_visibility_mode") in {"OPTIONAL_CONTEXT", "HIDE"} else "CADASTRAL_CONTEXT",
        })
    return {
        "z_reference": (
            "ABSOLUTE_Z"
            if floor_nodes and all(item.get("absolute_z_min_m") is not None for item in floor_nodes)
            else "RELATIVE_Z_ONLY"
        ),
        "hierarchy": {
            "parcel": parcel_id,
            "site": properties.get("official_parcel_no"),
            "building": properties.get("building_id"),
            "floors": floor_nodes,
            "units": unit_nodes,
            "bim_spaces_or_unit_candidates": (bim or {}).get("spaces", []),
        },
        "relationships": relationships,
        "legal_status": "NOT_A_LEGAL_DETERMINATION",
    }
