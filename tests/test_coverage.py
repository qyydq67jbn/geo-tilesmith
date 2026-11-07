"""Tests for the coverage audit."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tilesmith import geom
from tilesmith.config import Layer, Profile
from tilesmith.stats import coverage

PROFILE = Profile(layers=(
    Layer("roads", {"highway": frozenset({"primary"})}, 10),
    Layer("waterway", {"waterway": frozenset({"river"})}, 10),
))


def line(lon: float, lat: float, count: int = 5, step: float = 0.0001) -> list[tuple[float, float]]:
    return [geom.project(lon + step * i, lat + step * (i % 2)) for i in range(count)]


class MeasureTest(unittest.TestCase):
    def test_counts_features_and_vertices(self):
        features = [("roads", line(2.16, 41.39)), ("roads", line(2.18, 41.40))]
        report = coverage.measure(features, PROFILE, 14)
        self.assertEqual(report["roads"].features, 2)
        self.assertEqual(report["roads"].rendered, 2)
        self.assertEqual(report["roads"].vertices_in, 10)
        self.assertLessEqual(report["roads"].vertices_out, 10)

    def test_inactive_layers_are_skipped(self):
        features = [("waterway", line(2.16, 41.39))]
        self.assertNotIn("waterway", coverage.measure(features, PROFILE, 8))

    def test_degenerate_feature_is_not_rendered(self):
        one = [geom.project(2.16, 41.39)]
        report = coverage.measure([("roads", one), ("roads", line(2.16, 41.39))], PROFILE, 14)
        self.assertEqual(report["roads"].rendered, 1)
        self.assertAlmostEqual(report["roads"].retention, 0.5)

    def test_below_flags_low_retention_only(self):
        features = [("roads", [geom.project(2.16, 41.39)])] * 2 + [("roads", line(2.2, 41.4))] * 8
        report = coverage.measure(features, PROFILE, 14)
        self.assertEqual(coverage.below(report), ["roads"])
        self.assertEqual(coverage.below(report, minimum=0.5), [])

    def test_format_table_lists_layers(self):
        report = coverage.measure([("roads", line(2.16, 41.39))], PROFILE, 14)
        table = coverage.format_table(report)
        self.assertIn("roads", table)
        self.assertIn("retention", table.splitlines()[0])


if __name__ == "__main__":
    unittest.main()
