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
#
# ISO 3166-1 ALPHA-3, NOT COUNTRY NAMES. Names all resolved when checked, but
# they resolve by string match against a vendored gazetteer, so a country that
# gets renamed upstream (Czechia, Türkiye, Eswatini have all moved) stops
# matching and its fill DISAPPEARS WITH NO ERROR. A missing country on a map
# reads as "no suppliers there", which is a different claim from "this label
# stopped matching". Codes are stable by standard.
REGION_COUNTRIES = {
    "north_america": ("USA", "CAN", "MEX"),
    "europe": ("DEU", "FRA", "ITA", "ESP", "POL", "GBR", "NLD", "CZE"),
    "east_asia": ("CHN", "JPN", "KOR", "TWN"),
    "south_asia": ("IND", "PAK", "BGD", "LKA"),
}

# For the table and the hover, where a code is unreadable.
COUNTRY_NAME = {
    "USA": "United States", "CAN": "Canada", "MEX": "Mexico",
    "DEU": "Germany", "FRA": "France", "ITA": "Italy", "ESP": "Spain",
    "POL": "Poland", "GBR": "United Kingdom", "NLD": "Netherlands",
    "CZE": "Czechia",
    "CHN": "China", "JPN": "Japan", "KOR": "South Korea", "TWN": "Taiwan",
    "IND": "India", "PAK": "Pakistan", "BGD": "Bangladesh",
    "LKA": "Sri Lanka",
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
    """One row per region, INCLUDING ANY THE MAP CANNOT DRAW.

    The first version iterated the country mapping, so a region present in the
    data but missing from that dict vanished from the table and the map with
    nothing said. A region with no countries is drawn nowhere, and the surface
    has to be able to say so rather than simply omit it.
    """
    rows = supplier_rows(result)
    exposed = set(exposed_parts(result))
    out = []
    for region in sorted(set(REGION_COUNTRIES) | {row[2] for row in rows}):
        here = [row for row in rows if row[2] == region]
        out.append(RegionRow(
            region=region,
            label=REGION_LABEL.get(region, region),
            countries=REGION_COUNTRIES.get(region, ()),
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


# ------------------------------------------- counts for the decision surfaces
# Each returns (label, count) pairs in an EXPLICIT, STATED order, because
# CLAUDE.md still requires that any default ordering be arbitrary and stable or
# else meaningful and labelled. These are meaningful, so each caller says which
# key it sorted on. None of them mixes units: every count below is a count of
# parts, and there is no function here that puts two dimensions on one axis.


def coverage_counts(coverage):
    """What a page did not assess, largest first.

    Sorted by count because that is the question the panel is answering: which
    gap accounts for most of what is missing. A tie keeps subject order so the
    result is stable rather than dependent on dict iteration.
    """
    return tuple(sorted(
        ((note.subject, note.count) for note in coverage.notes if note.count),
        key=lambda pair: (-pair[1], pair[0])))


def group_sizes(surface):
    """Members per archetype group, IN LATTICE ORDER, never by size.

    Sorting this by member count would contradict the lattice drawn directly
    above it, which says in words that groups side by side are incomparable. A
    bar chart is a strong enough cue to overrule a caption, so it keeps the
    layout's own order and the caller says so.
    """
    return tuple((group.label, len(group.rows))
                 for layer in surface.layers for group in layer)


def field_sizes(surface):
    """Parts waiting on each missing field, largest first.

    This one IS a ranking and is meant to be: the surface asks what to go and
    get, and the answer is which single trip settles the most memberships.
    """
    return tuple(sorted(
        ((row.key, len(row.detail["parts"])) for row in surface.rows),
        key=lambda pair: (-pair[1], pair[0])))


def cluster_sizes(report):
    """(key, size, basis) per cluster awaiting confirmation, largest first.

    A reviewer confirms a cluster as one act, so size is how much one decision
    covers. That is a property of the decision rather than of the exposure, and
    it is the one number that legitimately orders this queue.

    THE BASIS IS CARRIED BECAUSE THE TWO GROUPINGS ARE NOT RIVALS. Supplier
    concentration and region concentration answer different questions, and the
    README calls that a complementary disagreement: both can be true at once,
    and no fact anybody could go and find would settle one against the other.
    Drawing them as one undifferentiated ranking would put them in exactly the
    relation the analysis says they are not in, so the caller colours by basis
    and names both.
    """
    return tuple(sorted(
        ((cluster.key, cluster.size, cluster.basis)
         for cluster in report.review_queue()),
        key=lambda row: (-row[1], row[0])))
