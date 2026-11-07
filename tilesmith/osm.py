"""Streaming reader for OSM XML extracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable
from xml.parsers import expat


class ExtractError(ValueError):
    """Raised when the extract is malformed or uses an unsupported root."""


@dataclass(frozen=True)
class Way:
    id: int
    tags: dict[str, str]
    nodes: tuple[int, ...]


@dataclass
class Extract:
    nodes: dict[int, tuple[float, float]] = field(default_factory=dict)
    ways: list[Way] = field(default_factory=list)

    def geometries(self) -> Iterable[tuple[Way, list[tuple[float, float]]]]:
        """Yield (way, lon/lat points) for every way whose nodes are all present."""
        for way in self.ways:
            points = [self.nodes[node] for node in way.nodes if node in self.nodes]
            if len(points) >= 2:
                yield way, points


def read_extract(path: str, keep: Callable[[dict[str, str]], bool]) -> Extract:
    """Parse `path`, retaining only ways for which `keep(tags)` is true.

    The node table is filled in full because ways may reference nodes that
    appear later in the document.
    """
    extract = Extract()
    parser = expat.ParserCreate()
    parser.buffer_text = True
    root: str | None = None
    state: dict[str, object] = {"way": None, "tags": {}, "nodes": []}

    def start(name: str, attrs: dict[str, str]) -> None:
        nonlocal root
        if root is None:
            root = name
            if name != "osm":
                raise ExtractError(f"expected <osm> root, got <{name}>")
        if name == "node":
            extract.nodes[int(attrs["id"])] = (float(attrs["lon"]), float(attrs["lat"]))
            return
        if name == "way":
            state["way"], state["tags"], state["nodes"] = int(attrs["id"]), {}, []
            return
        if name == "nd" and state["way"] is not None:
            cast = state["nodes"]
            assert isinstance(cast, list)
            cast.append(int(attrs["ref"]))
            return
        if name == "tag" and state["way"] is not None:
            cast = state["tags"]
            assert isinstance(cast, dict)
            cast[attrs["k"]] = attrs["v"]

    def end(name: str) -> None:
        if name != "way":
            return
        way_id, tags, nodes = state["way"], state["tags"], state["nodes"]
        assert isinstance(way_id, int) and isinstance(tags, dict) and isinstance(nodes, list)
        if nodes and keep(tags):
            extract.ways.append(Way(way_id, dict(tags), tuple(nodes)))
        state["way"], state["tags"], state["nodes"] = None, {}, []

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                parser.Parse(chunk, False)
        parser.Parse(b"", True)
    except expat.ExpatError as exc:
        raise ExtractError(f"{path}: {exc}") from exc
    except KeyError as exc:
        raise ExtractError(f"{path}: missing attribute {exc}") from exc
    if root is None:
        raise ExtractError(f"{path}: empty document")
    return extract
