"""The vendored India boundary, and the extent it has to keep.

Plotly's built-in `IND` polygon follows Natural Earth's convention and stops
around 35.5N, so the built-in map cannot draw India's claimed territory at all.
The shape is vendored instead. See `assets/README.md` for source, licence and
derivation.

WHAT THIS FILE PROTECTS is the extent. A resimplification at a coarser tolerance,
or a swap to a different source, could quietly clip a claimed region, and the
result would render as a smaller India rather than as an error. On a map that is
not a rendering artefact; it is a different claim.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOUNDARY = ROOT / "assets" / "india-claimed.geojson"


def points():
    data = json.loads(BOUNDARY.read_text())
    out = []
    for feature in data["features"]:
        geometry = feature["geometry"]
        polygons = (geometry["coordinates"]
                    if geometry["type"] == "MultiPolygon"
                    else [geometry["coordinates"]])
        for polygon in polygons:
            for ring in polygon:
                out.extend(ring)
    return out


class TestTheBoundaryIsPresentAndJoinable(unittest.TestCase):

    def test_the_file_is_committed(self):
        self.assertTrue(BOUNDARY.exists(),
                        "the map falls back to plotly's own India without it")

    def test_the_feature_carries_the_id_the_map_joins_on(self):
        data = json.loads(BOUNDARY.read_text())
        self.assertEqual([f.get("id") for f in data["features"]], ["IND"])

    def test_it_stays_small_enough_to_commit(self):
        # 10.5MB of source at 252,604 points renders detail no screen resolves.
        self.assertLess(BOUNDARY.stat().st_size, 400_000)


class TestTheClaimedTerritoryIsIntact(unittest.TestCase):
    """Each figure below is a place, not a tolerance.

    They are the reason the file is vendored, so they are asserted rather than
    left to be noticed on a screenshot.
    """

    def setUp(self):
        self.coords = points()
        self.lons = [x for x, _y in self.coords]
        self.lats = [y for _x, y in self.coords]

    def test_it_reaches_north_of_natural_earths_boundary(self):
        """Natural Earth's IND stops around 35.5N. Gilgit-Baltistan and the
        Siachen area are above 36N, so a boundary that ends below that is the
        shape this file exists to replace."""
        self.assertGreater(max(self.lats), 36.0)

    def test_it_reaches_east_across_arunachal_pradesh(self):
        self.assertGreater(max(self.lons), 96.0)

    def test_it_reaches_west_across_the_kutch_and_kashmir_frontier(self):
        self.assertLess(min(self.lons), 68.5)

    def test_it_reaches_south_to_the_far_end_of_the_mainland(self):
        self.assertLess(min(self.lats), 8.5)

    def test_the_ring_count_survived_simplification(self):
        # A ring reduced below four points renders as nothing, which on a map
        # reads as territory that is not there.
        data = json.loads(BOUNDARY.read_text())
        for feature in data["features"]:
            geometry = feature["geometry"]
            polygons = (geometry["coordinates"]
                        if geometry["type"] == "MultiPolygon"
                        else [geometry["coordinates"]])
            for polygon in polygons:
                for ring in polygon:
                    with self.subTest(points=len(ring)):
                        self.assertGreaterEqual(len(ring), 4)


class TestTheAttributionIsNotOnlyInAFile(unittest.TestCase):
    """CC BY 4.0 requires credit, and a licence satisfied only in a README is
    satisfied only for people who read the repository."""

    def test_the_surface_names_the_source_and_the_licence(self):
        app = (ROOT / "review_app.py").read_text()
        self.assertIn("CC BY 4.0", app)
        self.assertIn("Data{Meet}", app)

    def test_the_repository_records_where_it_came_from(self):
        notes = (ROOT / "assets" / "README.md").read_text()
        for required in ("datameet/maps", "CC BY 4.0", "simplify_boundary.py"):
            with self.subTest(term=required):
                self.assertIn(required, notes)


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
