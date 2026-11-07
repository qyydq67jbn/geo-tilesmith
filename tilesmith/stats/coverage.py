"""Per-layer retention measurement for one zoom."""

from __future__ import annotations

from dataclasses import dataclass

from .. import geom
from ..config import Profile

Point = tuple[float, float]


@dataclass(frozen=True)
class LayerCoverage:
    layer: str
    features: int
    rendered: int
    vertices_in: int
    vertices_out: int

    @property
    def retention(self) -> float:
        """Share of features that still produce a drawable run."""
        return 1.0 if not self.features else self.rendered / self.features

    @property
    def vertex_ratio(self) -> float:
        return 1.0 if not self.vertices_in else self.vertices_out / self.vertices_in


def _drawn(points: list[Point], tolerance: float) -> bool:
    simplified = geom.simplify(points, tolerance)
    return any(len(run) >= 2 for runs in geom.split_by_tile(simplified, 14).values() for run in runs)


def measure(features: list[tuple[str, list[Point]]], profile: Profile, zoom: int) -> dict[str, LayerCoverage]:
    """Count features per active layer and how many survive simplification."""
    tolerance = Profile.tolerance(zoom)
    buckets: dict[str, dict[str, int]] = {}
    for layer, points in features:
        if layer not in {entry.name for entry in profile.active(zoom)}:
            continue
        bucket = buckets.setdefault(layer, {"features": 0, "rendered": 0, "in": 0, "out": 0})
        bucket["features"] += 1
        bucket["in"] += len(points)
        simplified = geom.simplify(points, tolerance)
        bucket["out"] += len(simplified)
        if any(len(run) >= 2 for runs in geom.split_by_tile(simplified, zoom).values() for run in runs):
            bucket["rendered"] += 1
    return {
        layer: LayerCoverage(layer, data["features"], data["rendered"], data["in"], data["out"])
        for layer, data in sorted(buckets.items())
    }


def below(coverage: dict[str, LayerCoverage], minimum: float = 0.9) -> list[str]:
    """Layers that lost more than `1 - minimum` of their features."""
    return [layer for layer, entry in coverage.items() if entry.retention < minimum]


def format_table(coverage: dict[str, LayerCoverage]) -> str:
    lines = [f"{'layer':<14}{'features':>9}{'rendered':>9}{'retention':>11}{'vertices':>11}"]
    for entry in coverage.values():
        lines.append(
            f"{entry.layer:<14}{entry.features:>9}{entry.rendered:>9}"
            f"{entry.retention:>10.0%}{entry.vertex_ratio:>10.0%}"
        )
    return "\n".join(lines)
