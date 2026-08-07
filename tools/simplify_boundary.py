"""Simplify a national boundary for map rendering. RUN BY HAND, NEVER IN CI.

The source is 10.5MB and 252,604 coordinate pairs, drawn into a map roughly
400px tall. At that size the great majority of those points fall inside a single
pixel, so committing them would put ten megabytes in the repository to render
detail no screen resolves.

    python tools/simplify_boundary.py in.geojson out.geojson --tolerance 0.02

DOUGLAS-PEUCKER, IMPLEMENTED HERE. `shapely` would do it in one line and would
be a new runtime dependency on a deployed container that never simplifies
anything. This script runs once, by hand, and its output is committed; the app
reads the output and never imports this file.

THE TOLERANCE IS DERIVED, NOT TASTED. India spans about 30 degrees of latitude.
Drawn 400px tall, one pixel is 30/400 = 0.075 degrees, so a tolerance of 0.02
degrees moves no vertex more than about a quarter of a pixel. Rounding is to
four decimal places, roughly 11 metres, which is far below the same threshold.
"""
import argparse
import json
import sys


def perpendicular_distance(point, start, end):
    (px, py), (sx, sy), (ex, ey) = point, start, end
    dx, dy = ex - sx, ey - sy
    if dx == 0 and dy == 0:
        return ((px - sx) ** 2 + (py - sy) ** 2) ** 0.5
    return abs(dy * px - dx * py + ex * sy - ey * sx) / (dx * dx + dy * dy) ** 0.5


def douglas_peucker(points, tolerance):
    """Iterative rather than recursive: a 60,000 point ring blows the stack."""
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        worst, index = 0.0, None
        for i in range(first + 1, last):
            gap = perpendicular_distance(points[i], points[first], points[last])
            if gap > worst:
                worst, index = gap, i
        if index is not None and worst > tolerance:
            keep[index] = True
            stack.append((first, index))
            stack.append((index, last))
    return [point for point, keeping in zip(points, keep) if keeping]


def simplify_ring(ring, tolerance, places):
    """A ring stays a ring: closed, and never fewer than four points.

    A ring simplified below four points is a degenerate shape that renders as
    nothing, which on a map reads as territory that is not there.
    """
    points = [(round(x, places), round(y, places)) for x, y in ring]
    reduced = douglas_peucker(points, tolerance)
    if len(reduced) < 4:
        reduced = points[:4] if len(points) >= 4 else points
    if reduced[0] != reduced[-1]:
        reduced.append(reduced[0])
    return [[x, y] for x, y in reduced]


def simplify_geometry(geometry, tolerance, places):
    kind = geometry["type"]
    if kind == "Polygon":
        rings = [simplify_ring(r, tolerance, places) for r in geometry["coordinates"]]
        return {"type": "Polygon", "coordinates": rings}
    if kind == "MultiPolygon":
        polygons = []
        for polygon in geometry["coordinates"]:
            rings = [simplify_ring(r, tolerance, places) for r in polygon]
            polygons.append(rings)
        return {"type": "MultiPolygon", "coordinates": polygons}
    raise SystemExit(f"unsupported geometry: {kind}")


def count_points(geometry):
    if geometry["type"] == "Polygon":
        return sum(len(ring) for ring in geometry["coordinates"])
    return sum(len(ring) for polygon in geometry["coordinates"] for ring in polygon)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    parser.add_argument("--tolerance", type=float, default=0.02,
                        help="degrees; 0.02 is a quarter pixel at the size the "
                             "map is drawn")
    parser.add_argument("--places", type=int, default=4,
                        help="decimal places to round to; 4 is about 11 metres")
    parser.add_argument("--id", default="IND",
                        help="feature id the map joins on")
    args = parser.parse_args(argv)

    source = json.load(open(args.source, encoding="utf-8"))
    features = source["features"] if source["type"] == "FeatureCollection" \
        else [source]
    before = sum(count_points(f["geometry"]) for f in features)

    out = []
    for feature in features:
        geometry = simplify_geometry(feature["geometry"], args.tolerance,
                                     args.places)
        out.append({"type": "Feature", "id": args.id, "properties": {},
                    "geometry": geometry})
    after = sum(count_points(f["geometry"]) for f in out)

    payload = {"type": "FeatureCollection", "features": out}
    with open(args.destination, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
        handle.write("\n")

    print(f"{args.source} -> {args.destination}")
    print(f"  coordinate pairs {before:,} -> {after:,} "
          f"({after / before:.1%} kept) at tolerance {args.tolerance} degrees")
    return 0


if __name__ == "__main__":
    sys.exit(main())
