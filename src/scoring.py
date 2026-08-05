"""Exposure scoring across separate dimensions. No composite, ever.

FIVE DIMENSIONS, FIVE SLOTS, NO TOTAL. There is no weighted sum here and there
is no place to put one. The guarantee is structural rather than a matter of
discipline, and it rests on two properties that have to hold together:

  1. no function returns a scalar combining dimensions, and the container
     exposes no total, no overall, no score, and no __add__
  2. EVERY MEASURE KEEPS ITS UNIT, and no measure is a unitless number in a
     fixed range

The second is the one that actually does the work. Blocking the `+` is easy;
what enables the `+` is normalisation. Twenty-six days and three assemblies
cannot be added by anybody, but "0.8 lead-time risk" and "0.6 blast radius"
add up beautifully and mean nothing. So the moment any dimension is rescaled
onto 0-1 or 0-100, a composite exists whether or not anyone writes the
operator, and `test_scoring.py` asserts against exactly that.

AUTONOMY IS PER DIMENSION PER PART. A part scores at executes on portability
and abstains on buffer cover in the same breath, and neither contaminates the
other. Autonomy is derived from completeness alone, in one place, so routing
can never drift away from the value it is routing.
"""
from dataclasses import dataclass, field
from fractions import Fraction

from . import governance as gov
from .demand import USAGE_CANNOT_TELL, USAGE_KNOWN, USAGE_PARTIAL
from .synthetic import verdicts as V

# ------------------------------------------------------------ completeness --
# Six states, because five would force two genuinely different things to share
# one, and the pair that would be forced together is the pair a reviewer most
# needs separated.
KNOWN = "known"
UPPER_BOUND = "upper_bound"          # cover on partial demand
LOWER_BOUND = "lower_bound"          # blocked units on partial demand
CANNOT_TELL = "cannot_tell"          # a required input is absent
NO_RECOVERY_PATH = "no_recovery_path"  # no supplier at all: not missing data
NOT_APPLICABLE = "not_applicable"    # the dimension does not apply to this part

COMPLETENESS_STATES = (KNOWN, UPPER_BOUND, LOWER_BOUND, CANNOT_TELL,
                       NO_RECOVERY_PATH, NOT_APPLICABLE)

# THE ROUTING RULE, IN ONE PLACE. Only a genuinely missing input abstains.
#
# A bound is an answer ABOUT a bound, so it executes. NO_RECOVERY_PATH is the
# most serious finding in the dataset rather than an absence of one, so it
# executes. NOT_APPLICABLE executes because there is nothing for a reviewer to
# do: an in-house part has no purchase lead time and never will, and a lane
# that keeps presenting those asks a person to resolve them with data that does
# not exist anywhere.
#
# This is a STATE rather than a reason code the lane filters on, and the choice
# was deliberate. A filter would make CANNOT_TELL stop meaning "routes to the
# lane" and would put routing in a second place, where the next consumer that
# forgets the filter silently re-admits every in-house part. Deriving routing
# from the value alone keeps one rule with one home.
ROUTES_TO_LANE = (CANNOT_TELL,)


def autonomy_for(completeness):
    """Autonomy from completeness, derived and never passed in.

    Restates the abstention rule from the brief: autonomy requires agreement on
    a SETTLED answer, and a settled answer is what every state outside
    ROUTES_TO_LANE denotes.
    """
    if completeness not in COMPLETENESS_STATES:
        raise ValueError(f"unknown completeness state: {completeness!r}")
    return gov.RECOMMENDS if completeness in ROUTES_TO_LANE else gov.EXECUTES


# -------------------------------------------------------------------- units --
# Physical units only. Every one of these names something a measure is counted
# IN, so two of them can never be added. There is deliberately no "score",
# "index", "rating", "percent" or "normalised" here, and a test asserts the
# absence rather than trusting it.
DAYS = "days"
UNITS_PER_YEAR = "units_per_year"
FINISHED_GOOD_UNITS = "finished_good_units"
FINISHED_GOODS = "finished_goods"
ASSEMBLIES = "assemblies"
CATEGORICAL = "categorical"

UNITS = (DAYS, UNITS_PER_YEAR, FINISHED_GOOD_UNITS, FINISHED_GOODS, ASSEMBLIES,
         CATEGORICAL)

# Words that mean "this number has been stripped of its unit and rescaled".
# Any of them appearing as a unit is a composite in preparation.
FORBIDDEN_UNIT_WORDS = ("score", "index", "rating", "percent", "percentile",
                        "normalised", "normalized", "scaled", "weight",
                        "points", "ratio", "risk")

# --------------------------------------------------------------- dimensions --
LEAD_TIME_TO_RECOVER = "lead_time_to_recover"
BLAST_RADIUS = "blast_radius"
BUFFER_COVER = "buffer_cover"
PORTABILITY = "portability"
CONCENTRATION = "concentration"

DIMENSIONS = (LEAD_TIME_TO_RECOVER, BLAST_RADIUS, BUFFER_COVER, PORTABILITY,
              CONCENTRATION)

# Portability values. Categorical, so no arithmetic is possible on them at all.
TOOLING_COMPANY = "company"
TOOLING_SUPPLIER = "supplier"

# Calendar days, per the brief. A DECLARED MODELLING CONSTANT, not a fact:
# working days would be roughly 250 and would give about 1.46x the cover. It
# stays a plain constant at this stage because stage 4 returns raw durations and
# bands nothing, so the choice cannot change any answer here. It becomes a dual
# reading the moment stage 6 bands cover, and that is the point at which it
# needs computing both ways rather than choosing.
DAYS_PER_YEAR = 365


class _Unbounded:
    """Cover with nothing consuming it. A settled answer, not a missing one.

    Deliberately NOT None, because None here means "no value" and unbounded is
    a value. Deliberately not `math.inf` either: inf is a float that compares
    and arithmetics happily with every other number, so it would be the one
    measure in this module that could be summed. This supports no arithmetic at
    all, which is the same property the categorical dimension has.
    """
    __slots__ = ()

    def __repr__(self):
        return "unbounded"

    def __str__(self):
        return "unbounded"


UNBOUNDED = _Unbounded()


@dataclass(frozen=True)
class DimensionScore:
    """One dimension, one part. Carries its unit and its reasons, always.

    There is no `total`, no `overall`, no `weight` and no `__add__`, and there
    is no normalised variant of `value`. Stage 6 renders sentences from these;
    it does not add them up.
    """
    part_number: str
    dimension: str
    value: object
    unit: str
    completeness: str
    reasons: tuple = field(default_factory=tuple)
    detail: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.dimension not in DIMENSIONS:
            raise ValueError(f"unknown dimension: {self.dimension!r}")
        if self.completeness not in COMPLETENESS_STATES:
            raise ValueError(f"unknown completeness: {self.completeness!r}")
        if self.unit not in UNITS:
            raise ValueError(f"unknown unit: {self.unit!r}; every measure keeps "
                             f"a physical unit so that no two can be summed")
        if not self.reasons:
            raise ValueError("a dimension cannot produce a value without saying "
                             "why; stage 6 is sentences, not numbers")
        if self.value is None and self.completeness not in (
                CANNOT_TELL, NO_RECOVERY_PATH, NOT_APPLICABLE):
            raise ValueError("a settled answer needs a value")

    @property
    def autonomy(self):
        return autonomy_for(self.completeness)

    @property
    def is_settled(self):
        return self.completeness not in ROUTES_TO_LANE


@dataclass(frozen=True)
class ExposureProfile:
    """The five slots for one part. Concentration is RESERVED, not missing.

    Stage 5 fills the concentration slot. It is declared here and left
    deliberately unfilled so that stage 5 lands into a shape that already
    exists, rather than changing this one. A slot reading "not yet assessed" is
    distinct from an answer AND from an abstention, and collapsing it into
    either would be a lie about a stage that has not run.
    """
    part_number: str
    lead_time_to_recover: DimensionScore
    blast_radius: DimensionScore
    buffer_cover: DimensionScore
    portability: DimensionScore
    concentration: object = None      # reserved for stage 5

    def scored(self):
        """The four dimensions stage 4 fills. Never summed, only iterated."""
        return (self.lead_time_to_recover, self.blast_radius,
                self.buffer_cover, self.portability)

    def abstentions(self):
        return tuple(s for s in self.scored() if not s.is_settled)


# ------------------------------------------------------- lead time to recover --

def lead_time_to_recover(part_number, verdict, lead_times):
    """Days to wait out the disruption, quoted and p95 together.

    BOTH COLUMNS ARE RETURNED, NOT ONE. Choosing quoted over p95 is a judgment,
    and at this stage the two produce different durations but not different
    answers, so they travel as a pair rather than as a disagreement. The pair
    becomes a live dual reading the moment stage 6 bands them.

    NO BANDING HERE. "Long lead" is a threshold and a threshold is a judgment;
    introducing one would smuggle a modelling choice into a stage whose autonomy
    claim depends on having none.

    `lead_times` are the (quoted, p95) pairs for suppliers that have a record.
    """
    pairs = tuple(lead_times)

    if verdict == V.NO_QUALIFIED_SUPPLIER:
        # NOT missing data. Somebody checked the list and there is nobody on it,
        # so recovery time is undefined by absence rather than unrecorded.
        # Rendering this as "cannot tell" would understate the single most
        # serious finding in the dataset as a gap in the spreadsheet.
        return DimensionScore(
            part_number=part_number, dimension=LEAD_TIME_TO_RECOVER,
            value=None, unit=DAYS, completeness=NO_RECOVERY_PATH,
            reasons=("the supplier list was verified and contains nobody, so "
                     "there is no recovery path to time rather than a missing "
                     "lead time record",))

    if verdict == V.MADE_IN_HOUSE:
        # The dimension does not APPLY, which is not the same as lacking an
        # input. There is no in-house capacity model anywhere in this data and
        # there is not going to be one, so a lane that keeps showing in-house
        # parts is asking a reviewer to fetch data that does not exist.
        return DimensionScore(
            part_number=part_number, dimension=LEAD_TIME_TO_RECOVER,
            value=None, unit=DAYS, completeness=NOT_APPLICABLE,
            reasons=("the part is made in-house, so there is no purchase lead "
                     "time to recover over; this dimension does not apply "
                     "rather than being unknown",))

    if not pairs:
        return DimensionScore(
            part_number=part_number, dimension=LEAD_TIME_TO_RECOVER,
            value=None, unit=DAYS, completeness=CANNOT_TELL,
            reasons=("no supplier for this part has a lead time record, so how "
                     "long recovery would take is not recorded anywhere",))

    if verdict == V.SUPPLIER_LIST_UNKNOWN:
        # A lead time exists, but the list it came from is unconfirmed, so the
        # fastest recovery path may belong to a supplier nobody wrote down.
        return DimensionScore(
            part_number=part_number, dimension=LEAD_TIME_TO_RECOVER,
            value=None, unit=DAYS, completeness=CANNOT_TELL,
            reasons=("the supplier list is unconfirmed, so a shorter recovery "
                     "path may exist through a supplier that was never "
                     "recorded",))

    quoted = min(pair[0] for pair in pairs)
    p95 = min(pair[1] for pair in pairs)
    return DimensionScore(
        part_number=part_number, dimension=LEAD_TIME_TO_RECOVER,
        value=(quoted, p95), unit=DAYS, completeness=KNOWN,
        reasons=(f"the fastest qualified supplier quotes {quoted} days, and "
                 f"{p95} days at p95",),
        detail={"quoted_days": quoted, "p95_days": p95,
                "suppliers_with_lead_time": len(pairs)})


# ------------------------------------------------------------- blast radius --

def blast_radius(part_number, rows, usage):
    """What stops if this part stops.

    STRUCTURAL AND VOLUMETRIC FACETS, WITH DIFFERENT COMPLETENESS. The counts
    are always known, because stage 2 guarantees every edge resolves and every
    part reaches a finished good. The blocked-units figure inherits the demand
    plan's gaps.

    THE BOUND DIRECTION IS OPPOSITE TO BUFFER COVER'S, and this is where it
    would silently be got backwards. Blocked units sit in the NUMERATOR, so
    unrecorded demand can only ADD to them: partial demand makes this a LOWER
    bound. In buffer cover the same usage sits in the denominator and the same
    missing row makes that an UPPER bound.

    This dimension never abstains. A part fed only by the demand-absent finished
    good still blocks that finished good, and saying so is more useful than
    saying nothing.
    """
    rows = tuple(rows)
    goods = sorted({row.finished_good for row in rows})
    depths = frozenset().union(*(row.depths for row in rows)) if rows \
        else frozenset()

    if usage.completeness == USAGE_KNOWN:
        completeness = KNOWN
        reason = (f"blocks {len(goods)} finished good(s) totalling "
                  f"{usage.blocked_finished_good_units} units a year")
    elif usage.completeness == USAGE_PARTIAL:
        completeness = LOWER_BOUND
        reason = (f"blocks {len(goods)} finished good(s); the "
                  f"{usage.blocked_finished_good_units} units a year counts "
                  f"only the recorded ones, so it is a lower bound, because "
                  f"unrecorded demand can only add to what is blocked")
    else:
        completeness = LOWER_BOUND
        reason = (f"blocks {len(goods)} finished good(s), none of which is in "
                  f"the demand plan, so the structural reach is known and the "
                  f"blocked volume is a lower bound of zero recorded units")

    return DimensionScore(
        part_number=part_number, dimension=BLAST_RADIUS,
        value=usage.blocked_finished_good_units, unit=FINISHED_GOOD_UNITS,
        completeness=completeness, reasons=(reason,),
        detail={"finished_goods_blocked": len(goods),
                "finished_goods": tuple(goods),
                "assemblies_blocked": len(goods),
                "min_depth": min(depths) if depths else None,
                "max_depth": max(depths) if depths else None,
                "spans_depths": len(depths) > 1})


# -------------------------------------------------------------- buffer cover --

def buffer_cover(part_number, on_hand_units, usage):
    """Days of cover: on-hand divided by daily consumption.

    MISSING ON-HAND AND A RECORDED ZERO ARE SEPARATED BEFORE ANY ARITHMETIC.
    The branch below is the first statement that touches `on_hand_units`, and it
    tests `is None` rather than falsiness. A single `on_hand or 0` anywhere
    upstream would collapse the two, and afterwards nothing can tell them apart:
    both render as zero days and one of them is the worst finding in the
    dataset while the other is an empty cell in a spreadsheet.
    """
    if on_hand_units is None:
        return DimensionScore(
            part_number=part_number, dimension=BUFFER_COVER, value=None,
            unit=DAYS, completeness=CANNOT_TELL,
            reasons=("there is no on-hand record for this part, so cover "
                     "cannot be computed; this is not zero cover",))

    if usage.completeness == USAGE_CANNOT_TELL:
        return DimensionScore(
            part_number=part_number, dimension=BUFFER_COVER, value=None,
            unit=DAYS, completeness=CANNOT_TELL,
            reasons=usage.reasons + (
                "so there is no known consumption rate to divide on-hand by",))

    if usage.value == 0:
        # On-hand with nothing consuming it. Unbounded cover is an ANSWER, and
        # a division by zero here would be the code mistaking an answer for an
        # error.
        return DimensionScore(
            part_number=part_number, dimension=BUFFER_COVER, value=UNBOUNDED,
            unit=DAYS, completeness=KNOWN,
            reasons=(f"{on_hand_units} units on hand and no recorded annual "
                     f"consumption, so cover is unbounded rather than unknown",),
            detail={"on_hand_units": on_hand_units, "unbounded": True,
                    "annual_usage": Fraction(0)})

    daily = Fraction(usage.value, DAYS_PER_YEAR)
    days = Fraction(on_hand_units) / daily

    if usage.completeness == USAGE_PARTIAL:
        # Usage sits in the DENOMINATOR, so unrecorded demand can only make the
        # divisor bigger and the cover smaller. Opposite direction to blast
        # radius, from the identical missing row.
        completeness = UPPER_BOUND
        reason = (f"{on_hand_units} units on hand covers {float(days):.1f} days "
                  f"at the recorded consumption rate, and that is an upper "
                  f"bound: " + usage.reasons[0] + ", and unrecorded demand can "
                  f"only reduce cover")
    else:
        completeness = KNOWN
        reason = (f"{on_hand_units} units on hand covers {float(days):.1f} days "
                  f"at {float(usage.value):.0f} units a year")

    return DimensionScore(
        part_number=part_number, dimension=BUFFER_COVER, value=days, unit=DAYS,
        completeness=completeness, reasons=(reason,),
        detail={"on_hand_units": on_hand_units, "annual_usage": usage.value,
                "daily_consumption": daily, "unbounded": False})


# ---------------------------------------------------------------- portability --

def portability(part_number, tooling_owner):
    """Who owns the tooling, which sets how slowly resourcing can happen.

    Categorical, so no arithmetic is possible on it even in principle. That is
    a feature: it is the dimension a single blended number would have to invent
    a figure for, and inventing one is exactly what is refused here.
    """
    if not (tooling_owner or "").strip():
        return DimensionScore(
            part_number=part_number, dimension=PORTABILITY, value=None,
            unit=CATEGORICAL, completeness=CANNOT_TELL,
            reasons=("no tooling owner is recorded, so whether this part can be "
                     "resourced quickly is unknown",))

    owner = tooling_owner.strip()
    if owner == TOOLING_SUPPLIER:
        reason = ("the supplier owns the tooling, so resourcing means new "
                  "tooling rather than a new purchase order")
    else:
        reason = ("the company owns the tooling, so it can move to another "
                  "supplier without retooling")
    return DimensionScore(
        part_number=part_number, dimension=PORTABILITY, value=owner,
        unit=CATEGORICAL, completeness=KNOWN, reasons=(reason,))


# ------------------------------------------------------------------ profile --

def score_part(part_number, verdict, rows, usage, on_hand_units, tooling_owner,
               lead_times):
    """All four dimensions for one part. Concentration stays reserved."""
    return ExposureProfile(
        part_number=part_number,
        lead_time_to_recover=lead_time_to_recover(part_number, verdict,
                                                  lead_times),
        blast_radius=blast_radius(part_number, rows, usage),
        buffer_cover=buffer_cover(part_number, on_hand_units, usage),
        portability=portability(part_number, tooling_owner),
    )


def abstention_lane(profiles):
    """Dimensions that could not be answered, grouped by dimension.

    A SEPARATE LANE FROM STAGE 3'S, on purpose. That lane sorts by exposure
    under the worse reading, and a dimension abstention has no competing
    readings to be worse than, so the ordering would be meaningless. What a
    person needs here is every part missing the same field together, because
    those are resolved by one trip to the same system.
    """
    lane = {}
    for profile in profiles:
        for score in profile.abstentions():
            lane.setdefault(score.dimension, []).append(score)
    return {dimension: tuple(sorted(scores, key=lambda s: s.part_number))
            for dimension, scores in sorted(lane.items())}


def log_profile(log, profile, at="1970-01-01T00:00:00+00:00"):
    """Append one event per dimension. Structured only; no prose is stored."""
    for score in profile.scored():
        log.append(
            status=gov.STATUS_PROPOSED, sku_id=profile.part_number,
            field=score.dimension,
            value="" if score.value is None else str(score.value),
            at=at,
            kind=gov.KIND_DIMENSION_SCORED if score.is_settled
            else gov.KIND_DIMENSION_ABSTAINED,
            evidence={"dimension": score.dimension, "unit": score.unit,
                      "completeness": score.completeness,
                      "autonomy": score.autonomy,
                      "reasons": list(score.reasons),
                      **score.detail})
