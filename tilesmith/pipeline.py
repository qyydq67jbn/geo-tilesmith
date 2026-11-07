"""CLI: parse, filter, simplify and cut an extract into z/x/y tiles."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import geom
from .config import Profile, ProfileError, load_profile
from .osm import Extract, ExtractError, read_extract

Point = tuple[float, float]


def parse_zooms(raw: str) -> list[int]:
    zooms = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        zoom = int(piece)
        if not 0 <= zoom <= 22:
            raise ValueError(f"zoom out of range: {zoom}")
        zooms.append(zoom)
    if not zooms:
        raise ValueError("no zooms given")
    return sorted(set(zooms))


def collect(extract: Extract, profile: Profile) -> tuple[list[tuple[str, list[Point]]], dict[str, int]]:
    """Project kept ways once; `classify` already ran during parsing."""
    counts = {"ways_kept": 0, "vertices_in": 0}
    features: list[tuple[str, list[Point]]] = []
    for way, points in extract.geometries():
        layer = profile.classify(way.tags)
        if layer is None:
            continue
        counts["ways_kept"] += 1
        counts["vertices_in"] += len(points)
        features.append((layer, [geom.project(lon, lat) for lon, lat in points]))
    return features, counts


def build_zoom(
    features: list[tuple[str, list[Point]]],
    zoom: int,
    profile: Profile,
    out_dir: Path,
) -> dict[str, int]:
    tolerance = Profile.tolerance(zoom)
    layers = {layer.name for layer in profile.active(zoom)}
    stats = {"features": 0, "vertices_in": 0, "vertices_out": 0, "runs_dropped": 0, "tiles": 0}
    tiles: dict[tuple[int, int], dict[str, list[list[list[int]]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for layer, points in features:
        if layer not in layers:
            continue
        stats["features"] += 1
        stats["vertices_in"] += len(points)
        simplified = geom.simplify(points, tolerance)
        stats["vertices_out"] += len(simplified)
        for tile, run in geom.split_by_tile(simplified, zoom).items():
            for part in run:
                if len(part) < 2:
                    stats["runs_dropped"] += 1
                    continue
                tiles[tile][layer].append(geom.to_tile_coords(part, tile, zoom))
    for tile, layers_out in sorted(tiles.items()):
        path = out_dir / geom.shard_path(tile, zoom)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"z": zoom, "x": tile[0], "y": tile[1], "layers": dict(layers_out)},
                       separators=(",", ":")),
            encoding="utf-8",
        )
    stats["tiles"] = len(tiles)
    return stats


def run(extract_path: Path, profile: Profile, zooms: list[int], out_dir: Path) -> dict:
    seen = 0

    def keep(tags: dict[str, str]) -> bool:
        nonlocal seen
        seen += 1
        return profile.classify(tags) is not None

    extract = read_extract(str(extract_path), keep)
    features, counts = collect(extract, profile)
    manifest = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "extract": extract_path.name,
        "nodes": len(extract.nodes),
        "zooms": {},
        "totals": counts | {"ways_read": seen,
                            "ways_dropped": seen - len(extract.ways),
                            "features": len(features)},
    }
    for zoom in zooms:
        if not profile.active(zoom):
            continue
        manifest["zooms"][str(zoom)] = build_zoom(features, zoom, profile, out_dir)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tilesmith", description=__doc__)
    parser.add_argument("--extract", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--zooms", default="10,12,14")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)

    try:
        profile = load_profile(args.profile)
        zooms = parse_zooms(args.zooms)
    except (ProfileError, ValueError) as exc:
        parser.error(str(exc))
        return 2

    try:
        manifest = run(args.extract, profile, zooms, args.out)
    except ExtractError as exc:
        print(f"extract: {exc}", file=sys.stderr)
        return 1

    if not manifest["totals"]["ways_kept"]:
        print("no ways matched the profile", file=sys.stderr)
        return 1

    target = args.manifest or args.out / "manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"tiles": sum(z["tiles"] for z in manifest["zooms"].values()),
                      "manifest": str(target)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
