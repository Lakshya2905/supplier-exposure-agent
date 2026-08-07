"""Aggregates for the Dashboard surface. Pure data, no Streamlit, no charts.

THE ENCODING RULE THAT FORBADE THIS SURFACE WAS RETIRED BY THE OWNER ON
2026-08-06. Charts, a choropleth and red/amber/green are permitted. CLAUDE.md
and DESIGN.md carry the decision and what it gave up; this module does not
re-argue it.

WHAT DID NOT CHANGE, and what this module is careful about: no composite. Every
series below carries the unit of exactly one dimension, and there is no function
here that combines two. A caller can draw lead time in days; nothing in this
file will hand anybody lead time and blast radius on one axis, because those do
not commensurate and no chart makes them.

Absence keeps its own count in every series rather than being dropped. A
histogram built by filtering out the unknowns is a picture of the parts that
happened to be answerable, presented as a picture of the parts.
"""
from dataclasses import dataclass, field
from fractions import Fraction

from .. import scoring

# Synthetic regions mapped to real countries so a choropleth has something to
# fill. THE GEOGRAPHY IS ILLUSTRATIVE AND THE SURFACE SAYS SO. The dataset has
# four regions and no coordinates; these countries are a drawing convention, not
# a claim that a supplier is in Poland. Every caller renders the caption that
# says this, because a map is the single most believable thing on a page.
REGION_COUNTRIES = {
    "north_america": ("United States", "Canada", "Mexico"),
    "europe": ("Germany", "France", "Italy", "Spain", "Poland",
               "United Kingdom", "Netherlands", "Czechia"),
    "east_asia": ("China", "Japan", "South Korea", "Taiwan"),
    "south_asia": ("India", "Pakistan", "Bangladesh", "Sri Lanka"),
}

REGION_LABEL = {
    "north_america": "North America",
    "europe": "Europe",
    "east_asia": "East Asia",
    "south_asia": "South Asia",
}


@dataclass(frozen=True)
class Tile:
    """One figure, its unit, and its denominator.

    `of` is not decoration. A count with no denominator is the shape that
    invites reading 21 as large or small when neither is knowable.
    """
    label: str
    value: int
    unit: str
    of: str = ""


@dataclass(frozen=True)
class RegionRow:
    region: str
    label: str
    countries: tuple
    suppliers: int
    parts: int
    exposed_parts: int


@dataclass(frozen=True)
class DimensionSeries:
    """One dimension, its own unit, and its own unknowns.

    `values` holds only the parts with a settled figure. `unknown` and
    `unbounded` are carried beside it rather than folded in, so a caller
    drawing this cannot accidentally present the answerable subset as the whole.
    """
    dimension: str
    unit: str
    values: tuple = ()
    categories: dict = field(default_factory=dict)
    unknown: int = 0
    unbounded: int = 0

    @property
    def is_categorical(self):
        return self.unit == scoring.CATEGORICAL

    @property
    def assessed(self):
        return len(self.values) + sum(self.categories.values()) + self.unbounded


def _number(value):
    """A figure as a float, or a tuple of them, or None.

    `lead_time_to_recover` carries a (quoted, p95) PAIR rather than a scalar,
    because a lead time with no tail is half a lead time. The first version of
    this function returned None for it, which counted all 188 settled figures as
    unknown and drew an empty chart under a full-looking heading. Both halves
    are days, so both belong on one axis; that is one dimension in its own unit,
    not two dimensions sharing an axis.
    """
    if isinstance(value, (tuple, list)):
        parts = tuple(_number(item) for item in value)
        return parts if all(part is not None for part in parts) else None
    if isinstance(value, Fraction):
        return float(value)
    return float(value) if isinstance(value, (int, float)) else None


def tiles(result):
    exposed = exposed_parts(result)
    dimension_results = [score for profile in result.profiles.values()
                         for score in profile.all_scores()]
    unknown = [score for score in dimension_results
               if score.completeness == scoring.CANNOT_TELL]
    return (
        Tile("Parts scored", len(result.profiles), "parts"),
        Tile("Exposed parts", len(exposed), "parts",
             of=f"of {len(result.profiles)} scored"),
        Tile("Clusters concentrated", len(result.report.concentrated()),
             "clusters"),
        Tile("Dimension results unknown", len(unknown), "results",
             of=f"of {len(dimension_results)} assessed"),
    )


def exposed_parts(result):
    """Parts that reached an archetype group, in explicit sorted order.

    Read from the same `ranking.default_view` the Exposure surface lays out, so
    the two cannot disagree about which parts are exposed. An earlier version
    fell back to every part with evidence, which is all 296 of them, and the
    tile read "296 exposed of 296 scored" without looking wrong enough to
    notice.
    """
    from .. import ranking
    view = ranking.default_view(list(result.profiles.values()), result.verdicts,
                                result.catalogue)
    return tuple(sorted({part for layer in view["layers"] for group in layer
                         for part in group.members}))


def supplier_rows(result):
    """(part, supplier, region) as the evidence actually read them."""
    seen = set()
    for part, evidence in sorted(result.evidence.items()):
        for row in evidence.supplier_rows:
            seen.add((part, row.supplier_name, row.region))
    return tuple(sorted(seen))


def regions(result):
    rows = supplier_rows(result)
    exposed = set(exposed_parts(result))
    out = []
    for region in sorted(REGION_COUNTRIES):
        here = [row for row in rows if row[2] == region]
        out.append(RegionRow(
            region=region,
            label=REGION_LABEL.get(region, region),
            countries=REGION_COUNTRIES[region],
            suppliers=len({supplier for _p, supplier, _r in here}),
            parts=len({part for part, _s, _r in here}),
            exposed_parts=len({part for part, _s, _r in here
                               if part in exposed})))
    return tuple(out)


def dimension_series(result):
    """One series per dimension, each in its own unit. NEVER COMBINED.

    Returned in `scoring.DIMENSIONS` order, which is fixed and declared
    meaningless by the surface that renders it: the order is the order the
    dimensions were defined in, and nothing about it is a ranking.
    """
    by_dimension = {}
    for profile in result.profiles.values():
        for score in profile.all_scores():
            by_dimension.setdefault(score.dimension, []).append(score)

    series = []
    for dimension in scoring.DIMENSIONS:
        scores = by_dimension.get(dimension, [])
        if not scores:
            continue
        unit = scores[0].unit
        values, categories, unknown, unbounded = [], {}, 0, 0
        for score in scores:
            if score.completeness in (scoring.CANNOT_TELL,
                                      scoring.NO_RECOVERY_PATH,
                                      scoring.NOT_APPLICABLE):
                unknown += 1
            elif score.value is scoring.UNBOUNDED:
                unbounded += 1
            elif unit == scoring.CATEGORICAL:
                categories[str(score.value)] = categories.get(
                    str(score.value), 0) + 1
            else:
                number = _number(score.value)
                if number is None:
                    unknown += 1
                else:
                    values.append(number)
        series.append(DimensionSeries(
            dimension=dimension, unit=unit, values=tuple(values),
            categories=categories, unknown=unknown, unbounded=unbounded))
    return tuple(series)


def incidence(result, limit=40):
    """Which supplier touches which exposed part, as a 0/1 grid.

    Returns (parts, suppliers, grid). Capped at `limit` parts and LOGGED BY THE
    CAPTION rather than silently truncated: a matrix that quietly showed the
    first forty would read as the whole set.
    """
    exposed = [part for part in exposed_parts(result)]
    rows = [row for row in supplier_rows(result) if row[0] in set(exposed)]
    parts = sorted({row[0] for row in rows})[:limit]
    suppliers = sorted({row[1] for row in rows if row[0] in set(parts)})
    present = {(row[0], row[1]) for row in rows}
    grid = [[1 if (part, supplier) in present else 0 for part in parts]
            for supplier in suppliers]
    return tuple(parts), tuple(suppliers), grid
