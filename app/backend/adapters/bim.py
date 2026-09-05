"""Optional IFC adapter that exposes spaces as candidates, never ownership units."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BIM_DIR = ROOT / "data" / "bim"


def _text(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def _quantity(element, names: tuple[str, ...]) -> float | None:
    try:
        from ifcopenshell.util.element import get_psets

        psets = get_psets(element, qtos_only=True)
        for quantities in psets.values():
            for name in names:
                value = quantities.get(name)
                if value is not None:
                    return float(value)
    except Exception:
        pass
    return None


def _placement_z(element) -> float | None:
    try:
        from ifcopenshell.util.placement import get_local_placement

        matrix = get_local_placement(element.ObjectPlacement)
        return float(matrix[2][3])
    except Exception:
        return None


def _space_geometry(space) -> dict[str, Any] | None:
    """Return a clearly labelled local-coordinate bounding prism when possible."""

    try:
        import ifcopenshell.geom

        settings = ifcopenshell.geom.settings()
        shape = ifcopenshell.geom.create_shape(settings, space)
        values = list(shape.geometry.verts)
        points = list(zip(values[0::3], values[1::3], values[2::3]))
        if not points:
            return None
        xs, ys, zs = zip(*points)
        ring = [
            [min(xs), min(ys)], [max(xs), min(ys)], [max(xs), max(ys)],
            [min(xs), max(ys)], [min(xs), min(ys)],
        ]
        return {
            "type": "Polygon",
            "coordinates": [ring],
            "coordinate_system": "IFC_LOCAL",
            "derivation": "BOUNDING_ENVELOPE_OF_IFC_SPACE_GEOMETRY",
            "z_min": float(min(zs)),
            "z_max": float(max(zs)),
        }
    except Exception:
        return None


class BIMAdapter:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or DEFAULT_BIM_DIR
        self._records: dict[str, dict[str, Any]] | None = None

    def files(self) -> list[Path]:
        return sorted(self.data_dir.glob("*.ifc")) if self.data_dir.exists() else []

    def capability(self) -> dict[str, Any]:
        files = self.files()
        installed = importlib.util.find_spec("ifcopenshell") is not None
        if not files:
            return {
                "status": "BIM_NOT_LOADED",
                "adapter": "READY",
                "ifcopenshell": "AVAILABLE" if installed else "NOT_INSTALLED",
                "file_count": 0,
            }
        if not installed:
            return {
                "status": "BIM_NOT_LOADED",
                "adapter": "READY",
                "ifcopenshell": "NOT_INSTALLED",
                "file_count": len(files),
                "detail": "IFC files exist but ifcopenshell is required to parse them.",
            }
        return {
            "status": "BIM_LOADED" if self._records is not None else "BIM_ADAPTER_READY",
            "adapter": "READY",
            "ifcopenshell": "AVAILABLE",
            "file_count": len(files),
        }

    def _parse_file(self, path: Path) -> list[dict[str, Any]]:
        import ifcopenshell

        model = ifcopenshell.open(str(path))
        georeferenced = bool(model.by_type("IfcMapConversion"))
        records = []
        for building in model.by_type("IfcBuilding"):
            storeys = []
            for relation in getattr(building, "IsDecomposedBy", ()):
                for candidate in getattr(relation, "RelatedObjects", ()):
                    if not candidate.is_a("IfcBuildingStorey"):
                        continue
                    spaces = []
                    for containment in getattr(candidate, "ContainsElements", ()):
                        for element in getattr(containment, "RelatedElements", ()):
                            if element.is_a("IfcSpace"):
                                geometry = _space_geometry(element)
                                z_min = geometry.get("z_min") if geometry else _placement_z(element)
                                z_max = geometry.get("z_max") if geometry else None
                                spaces.append({
                                    "space_identifier": _text(getattr(element, "GlobalId", None)),
                                    "space_name": _text(getattr(element, "Name", None)),
                                    "long_name": _text(getattr(element, "LongName", None)),
                                    "storey": _text(getattr(candidate, "Name", None)),
                                    "geometry": geometry,
                                    "z_min": z_min,
                                    "z_max": z_max,
                                    "area_m2": _quantity(element, ("NetFloorArea", "GrossFloorArea")),
                                    "volume_m3": _quantity(element, ("NetVolume", "GrossVolume")),
                                    "semantic_type": "BIM_SPACE_OR_UNIT_CANDIDATE",
                                    "ownership_unit": False,
                                })
                    storeys.append({
                        "storey_identifier": _text(getattr(candidate, "GlobalId", None)),
                        "storey_name": _text(getattr(candidate, "Name", None)),
                        "elevation_m": getattr(candidate, "Elevation", None),
                        "spaces": spaces,
                    })
            identifiers = {
                path.stem,
                _text(getattr(building, "GlobalId", None)),
                _text(getattr(building, "Name", None)),
                _text(getattr(building, "LongName", None)),
                _text(getattr(building, "Tag", None)),
            }
            records.append({
                "identifiers": sorted(value for value in identifiers if value),
                "ifc_file": str(path),
                "building_identifier": _text(getattr(building, "GlobalId", None)),
                "building_name": _text(getattr(building, "Name", None)),
                "coordinate_reference": "IFC_GEOREFERENCED_METADATA_PRESENT" if georeferenced else "IFC_LOCAL",
                "storeys": storeys,
            })
        return records

    def _load(self) -> None:
        self._records = {}
        if not self.files() or importlib.util.find_spec("ifcopenshell") is None:
            return
        for path in self.files():
            for record in self._parse_file(path):
                for identifier in record.pop("identifiers"):
                    self._records[identifier.casefold()] = record

    def building(self, building_id: str, parcel_id: str | None = None) -> dict[str, Any]:
        if self._records is None:
            self._load()
        assert self._records is not None
        record = self._records.get(building_id.casefold())
        if record is None:
            status = "BIM_NOT_LOADED" if not self.files() else "BIM_NOT_AVAILABLE_FOR_BUILDING"
            return {
                "status": status,
                "building_id": building_id,
                "hierarchy": {
                    "parcel": parcel_id,
                    "site": None,
                    "building": building_id,
                    "floors": [],
                },
                "spaces": [],
                "ownership_semantics": "NOT_AVAILABLE",
            }
        spaces = [space for storey in record["storeys"] for space in storey["spaces"]]
        return {
            "status": "BIM_LOADED",
            "building_id": building_id,
            "hierarchy": {
                "parcel": parcel_id,
                "site": record.get("building_name"),
                "building": building_id,
                "floors": record["storeys"],
            },
            "spaces": spaces,
            "ownership_semantics": "IFC_SPACES_ARE_CANDIDATES_NOT_OWNERSHIP_UNITS",
            "source": record["ifc_file"],
            "coordinate_reference": record["coordinate_reference"],
        }

    def units(self, building_id: str, parcel_id: str | None = None) -> dict[str, Any]:
        result = self.building(building_id, parcel_id)
        return {
            "status": result["status"],
            "building_id": building_id,
            "units": result.get("spaces", []),
            "unit_semantics": result.get("ownership_semantics", "NOT_AVAILABLE"),
        }
