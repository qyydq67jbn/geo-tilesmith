"""Layer profiles: which tags become which layer, and at what zoom."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

MIN_TOLERANCE_M = 0.5
BASE_TOLERANCE_M = 12.0


class ProfileError(ValueError):
    """Raised for a profile that cannot be read or is incomplete."""


@dataclass(frozen=True)
class Layer:
    name: str
    tags: dict[str, frozenset[str]]
    min_zoom: int

    def matches(self, tags: dict[str, str]) -> bool:
        return any(key in tags and tags[key] in allowed for key, allowed in self.tags.items())


@dataclass(frozen=True)
class Profile:
    layers: tuple[Layer, ...]

    def active(self, zoom: int) -> tuple[Layer, ...]:
        return tuple(layer for layer in self.layers if layer.min_zoom <= zoom)

    def classify(self, tags: dict[str, str]) -> str | None:
        for layer in self.layers:
            if layer.matches(tags):
                return layer.name
        return None

    @staticmethod
    def tolerance(zoom: int) -> float:
        """Simplification distance in meters, halved per zoom level above 10."""
        return max(MIN_TOLERANCE_M, BASE_TOLERANCE_M / 2 ** max(0, zoom - 10))


def _layer(name: str, raw: object) -> Layer:
    if not isinstance(raw, dict):
        raise ProfileError(f"layer {name!r} must be an object")
    tags = raw.get("tags")
    if not isinstance(tags, dict) or not tags:
        raise ProfileError(f"layer {name!r} needs a non-empty tags map")
    parsed: dict[str, frozenset[str]] = {}
    for key, values in tags.items():
        if not isinstance(values, list) or not values:
            raise ProfileError(f"layer {name!r} tag {key!r} must be a list")
        parsed[str(key)] = frozenset(str(value) for value in values)
    min_zoom = raw.get("min_zoom", 0)
    if not isinstance(min_zoom, int) or not 0 <= min_zoom <= 22:
        raise ProfileError(f"layer {name!r} min_zoom must be 0..22")
    return Layer(name=name, tags=parsed, min_zoom=min_zoom)


def load_profile(path: str | Path) -> Profile:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileError(f"cannot read profile {path}: {exc}") from exc
    layers = raw.get("layers") if isinstance(raw, dict) else None
    if not isinstance(layers, dict) or not layers:
        raise ProfileError("profile needs a non-empty layers object")
    return Profile(layers=tuple(_layer(name, body) for name, body in layers.items()))
