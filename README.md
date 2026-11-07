# tilesmith

Staged tile pipeline from OpenStreetMap extracts: parse, filter, simplify, cut.

`tilesmith` is the boring middle of a vector tile build. It reads an `.osm` XML
extract, keeps only the features a profile asks for, simplifies every line to
the tolerance of its zoom, and writes one small JSON tile per z/x/y bucket plus
a manifest of stage counters. Rendering, fonts and sprite handling stay out of
scope on purpose, so the output can feed any rasteriser or be packed into a
container later.

Why: most small maps served from a laptop or a single box do not need a
database or a Planet-scale stack. They need deterministic, inspectable output
and a stage order you can measure when the result looks wrong.

## Install

Python 3.10+, no third-party dependencies.

```sh
git clone https://github.com/qyydq67jbn/geo-tilesmith
cd geo-tilesmith
python3 -m tilesmith.pipeline --help
```

## Usage

```sh
python3 -m tilesmith.pipeline \
  --extract barcelona.osm \
  --profile profiles/city.json \
  --zooms 10,12,14 \
  --out out/tiles
```

Output:

```
out/tiles/14/8309/6121.json
out/tiles/manifest.json
```

A tile is a small JSON document with integer coordinates quantised into an
extent of 4096 per axis:

```json
{"z": 14, "x": 8309, "y": 6121,
 "layers": {"roads": [[[0, 2048], [4096, 2110]]]}}
```

The manifest records, per stage and per zoom, how many ways entered, how many
survived the tag filter, how many lost vertices to simplification, and how many
features got clipped away. Compare two runs by diffing that file.

## Profile

A profile picks layers and their tag matches. Values are allow-lists; a way is
kept when any tag pair matches. `min_zoom` keeps a layer out of coarse zooms.

```json
{"layers": {
  "roads":   {"tags": {"highway": ["primary", "secondary", "residential"]}, "min_zoom": 12},
  "waterway": {"tags": {"waterway": ["river", "canal"]}, "min_zoom": 10}}}
```

## Data sources and refresh cadence

Extracts come from Geofabrik region dumps, ODbL 1.0. The profile decides what is
published, so check tag allow-lists before serving derived work. City extracts
are refreshed quarterly; the manifest keeps the run date and extract size so a
stale build is visible.

## Layout

```
tilesmith/osm.py      streaming extract parser, tag filtering, node table
tilesmith/geom.py     mercator projection, Douglas-Peucker, tile bucketing
tilesmith/config.py   profile loading and validation
tilesmith/pipeline.py CLI and stage wiring, manifest counters
profiles/             checked-in layer profiles
```

## Limits

- Lines only: polygons are not closed, so area layers need a separate pass.
- Simplification runs before cutting, and tiles are clipped by clamping, not by
  real polygon intersection.
- No deduplication across zoom levels; each zoom is built from scratch.

## License

MIT. Extract data stays under ODbL as noted above.
