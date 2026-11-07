"""Projection, Douglas-Peucker simplification and tile bucketing."""

from __future__ import annotations

import math
from typing import Callable, Iterable, Sequence

EARTH_RADIUS_M = 6378137.0
EXTENT = 4096
MAX_LAT = 85.05112878

Point = tuple[float, float]


def project(lon: float, lat: float) -> Point:
    """WGS84 degrees to web mercator meters."""
    lat = max(-MAX_LAT, min(MAX_LAT, lat))
    x = math.radians(lon) * EARTH_RADIUS_M
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * EARTH_RADIUS_M
    return x, y


def tile_bounds(zoom: int) -> float:
    """Edge length of one tile in mercator meters."""
    return 2 * math.pi * EARTH_RADIUS_M / 2**zoom


def tile_of(x: float, y: float, zoom: int) -> tuple[int, int]:
    size = tile_bounds(zoom)
    limit = 2**zoom - 1
    tx = int((x + math.pi * EARTH_RADIUS_M) // size)
    ty = int((math.pi * EARTH_RADIUS_M - y) // size)
    return max(0, min(limit, tx)), max(0, min(limit, ty))


def _segment_distance(point: Point, ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(point[0] - ax, point[1] - ay)
    t = ((point[0] - ax) * dx + (point[1] - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(point[0] - (ax + t * dx), point[1] - (ay + t * dy))


def simplify(points: Sequence[Point], tolerance_m: float) -> list[Point]:
    """Douglas-Peucker; endpoints always survive."""
    if len(points) < 3 or tolerance_m <= 0:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        ax, ay = points[first]
        bx, by = points[last]
        worst = tolerance_m
        index = -1
        for i in range(first + 1, last):
            distance = _segment_distance(points[i], ax, ay, bx, by)
            if distance > worst:
                worst = distance
                index = i
        if index >= 0:
            keep[index] = True
            stack.append((first, index))
            stack.append((index, last))
    return [point for point, kept in zip(points, keep) if kept]


def split_by_tile(points: Iterable[Point], zoom: int) -> dict[tuple[int, int], list[Point]]:
    """Split a projected line into per-tile runs, one run per tile change."""
    runs: dict[tuple[int, int], list[Point]] = {}
    current: tuple[int, int] | None = None
    run: list[Point] = []
    for point in points:
        tile = tile_of(point[0], point[1], zoom)
        if tile != current:
            if current is not None and run:
                runs.setdefault(current, []).append(run)
            current, run = tile, [point]
        else:
            run.append(point)
    if current is not None and run:
        runs.setdefault(current, []).append(run)
    return runs


def to_tile_coords(points: Sequence[Point], tile: tuple[int, int], zoom: int) -> list[list[int]]:
    """Tile-local integers clamped to the extent, so overflow folds to the edge."""
    size = tile_bounds(zoom)
    offset_x = tile[0] * size - math.pi * EARTH_RADIUS_M
    offset_y = math.pi * EARTH_RADIUS_M - tile[1] * size
    coords = []
    for x, y in points:
        local_x = (x - offset_x) / size * EXTENT
        local_y = (offset_y - y) / size * EXTENT
        coords.append([
            max(0, min(EXTENT, round(local_x))),
            max(0, min(EXTENT, round(local_y))),
        ])
    return coords


def shard_path(tile: tuple[int, int], zoom: int) -> str:
    """Relative path for a tile JSON document."""
    return f"{zoom}/{tile[0]}/{tile[1]}.json"


def tile_center(tile: tuple[int, int], zoom: int) -> Callable[[], Point]:
    size = tile_bounds(zoom)
    return lambda: (
        tile[0] * size - math.pi * EARTH_RADIUS_M + size / 2,
        math.pi * EARTH_RADIUS_M - tile[1] * size - size / 2,
    )
