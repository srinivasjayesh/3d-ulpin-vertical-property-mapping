"""Optional LAS/LAZ adapter. No point clouds are synthesized."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LIDAR_DIR = ROOT / "data" / "lidar"


def _outer_rings(geometry: dict[str, Any]) -> list[list[list[float]]]:
    coordinates = geometry.get("coordinates", [])
    if geometry.get("type") == "Polygon":
        return [coordinates[0]] if coordinates else []
    if geometry.get("type") == "MultiPolygon":
        return [polygon[0] for polygon in coordinates if polygon]
    return []


def _points_in_ring(xs, ys, ring):
    """Vectorized even-odd point-in-polygon test."""

    import numpy as np

    inside = np.zeros(xs.shape, dtype=bool)
    vertices = np.asarray(ring, dtype=float)
    xj, yj = vertices[-1]
    for xi, yi in vertices:
        crossing = ((yi > ys) != (yj > ys)) & (
            xs < (xj - xi) * (ys - yi) / ((yj - yi) + 1e-15) + xi
        )
        inside ^= crossing
        xj, yj = xi, yi
    return inside


class LiDARAdapter:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or DEFAULT_LIDAR_DIR

    def files(self) -> list[Path]:
        if not self.data_dir.exists():
            return []
        return sorted([*self.data_dir.glob("*.las"), *self.data_dir.glob("*.laz")])

    def capability(self) -> dict[str, Any]:
        files = self.files()
        installed = importlib.util.find_spec("laspy") is not None
        if not files:
            return {
                "status": "LIDAR_NOT_LOADED",
                "adapter": "READY",
                "laspy": "AVAILABLE" if installed else "NOT_INSTALLED",
                "pdal": "AVAILABLE" if importlib.util.find_spec("pdal") else "OPTIONAL_NOT_INSTALLED",
                "file_count": 0,
            }
        if not installed:
            return {
                "status": "LIDAR_NOT_LOADED",
                "adapter": "READY",
                "laspy": "NOT_INSTALLED",
                "file_count": len(files),
                "detail": "LAS/LAZ files exist but laspy is required to read them.",
            }
        return {
            "status": "LIDAR_LOADED",
            "adapter": "READY",
            "laspy": "AVAILABLE",
            "file_count": len(files),
        }

    @staticmethod
    def _transformed_rings(geometry: dict[str, Any], crs) -> list[list[list[float]]]:
        rings = _outer_rings(geometry)
        if crs is None:
            raise RuntimeError("LIDAR_CRS_UNKNOWN")
        crs_text = str(crs).upper()
        if "4326" in crs_text or "CRS84" in crs_text:
            return rings
        try:
            from pyproj import Transformer
        except ImportError as exc:
            raise RuntimeError("Projected LiDAR cropping requires pyproj") from exc
        transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        return [
            [[float(x), float(y)] for x, y in zip(*transformer.transform(
                [point[0] for point in ring], [point[1] for point in ring]
            ))]
            for ring in rings
        ]

    def analyze_building(self, feature: dict[str, Any]) -> dict[str, Any]:
        building_id = str(feature.get("properties", {}).get("building_id"))
        capability = self.capability()
        if capability["status"] != "LIDAR_LOADED":
            return {"status": "LIDAR_NOT_LOADED", "building_id": building_id}

        import laspy
        import numpy as np

        selected_z = []
        ground_z = []
        used_sources = []
        for path in self.files():
            with laspy.open(path) as reader:
                try:
                    rings = self._transformed_rings(feature["geometry"], reader.header.parse_crs())
                except RuntimeError as exc:
                    return {"status": str(exc), "building_id": building_id, "lidar_source": str(path)}
                if not rings:
                    continue
                for chunk in reader.chunk_iterator(1_000_000):
                    xs = np.asarray(chunk.x)
                    ys = np.asarray(chunk.y)
                    zs = np.asarray(chunk.z)
                    mask = np.zeros(xs.shape, dtype=bool)
                    for ring in rings:
                        bounds = np.asarray(ring, dtype=float)
                        bbox = (
                            (xs >= bounds[:, 0].min()) & (xs <= bounds[:, 0].max())
                            & (ys >= bounds[:, 1].min()) & (ys <= bounds[:, 1].max())
                        )
                        indices = np.flatnonzero(bbox)
                        if indices.size:
                            mask[indices] |= _points_in_ring(xs[indices], ys[indices], ring)
                    if not mask.any():
                        continue
                    selected_z.append(zs[mask])
                    try:
                        classifications = np.asarray(chunk.classification)
                        classified_ground = mask & (classifications == 2)
                        if classified_ground.any():
                            ground_z.append(zs[classified_ground])
                    except Exception:
                        pass
                    used_sources.append(str(path))

        if not selected_z:
            return {"status": "LIDAR_NO_POINTS_IN_FOOTPRINT", "building_id": building_id}
        values = np.concatenate(selected_z)
        ground_values = np.concatenate(ground_z) if ground_z else values
        ground = float(np.median(ground_values)) if ground_z else float(np.percentile(values, 5))
        roof = float(np.percentile(values, 95))
        point_count = int(values.size)
        confidence = "HIGH" if point_count >= 1000 else "MEDIUM" if point_count >= 100 else "LOW"
        return {
            "status": "LIDAR_HEIGHT_AVAILABLE",
            "building_id": building_id,
            "lidar_height_m": max(0.0, roof - ground),
            "lidar_ground_m": ground,
            "lidar_roof_m": roof,
            "lidar_point_count": point_count,
            "lidar_source": ";".join(sorted(set(used_sources))),
            "lidar_confidence": confidence,
            "ground_method": "CLASSIFICATION_2_MEDIAN" if ground_z else "FIFTH_PERCENTILE",
            "roof_method": "NINETY_FIFTH_PERCENTILE",
        }
