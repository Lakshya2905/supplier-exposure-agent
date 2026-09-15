"""Exposure scoring across separate dimensions. No composite, ever.

SIX MEASURES, SIX SLOTS, NO TOTAL. There is no summed-with-coefficients score
here and there is no place to put one.

SIX, NOT FIVE, AND THE SIXTH IS A SPLIT RATHER THAN AN ADDITION. The brief names
five dimensions and defines the first as "how long to qualify an alternative or
wait out the disruption". That is two questions sharing one name, and they have
different answers, different inputs and different confidence: waiting it out is
a purchase lead time somebody reported, while resourcing is a chain of
activities most of which nobody has timed. `wait_out_days` and `resource_days`
are therefore separate measures, each with its own completeness and its own
autonomy. Merging them back into one figure would put a reported number and an
estimate under one heading, which is the composite in miniature.

The no-total guarantee is structural rather than a matter of discipline, and it
rests on two properties that have to hold together:

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
from . import recovery as R
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
PARTS = "parts"                      # stage 5: how many parts share a dependency

UNITS = (DAYS, UNITS_PER_YEAR, FINISHED_GOOD_UNITS, FINISHED_GOODS, ASSEMBLIES,
         CATEGORICAL, PARTS)

# Words that mean "this number has been stripped of its unit and rescaled".
# Any of them appearing as a unit is a composite in preparation.
FORBIDDEN_UNIT_WORDS = ("score", "index", "rating", "percent", "percentile",
                        "normalised", "normalized", "scaled", "weight",
                        "points", "ratio", "risk")

# --------------------------------------------------------------- dimensions --
# THE TWO HALVES OF RECOVERY, NAMED SEPARATELY. `lead_time_to_recover` was one
# name over two questions and it overclaimed: it answered only the wait-it-out
# half while carrying a name that promised both.
WAIT_OUT_DAYS = "wait_out_days"
RESOURCE_DAYS = "resource_days"
BLAST_RADIUS = "blast_radius"
# WHAT STOPS, AND WHAT WAS PROMISED, ARE TWO QUESTIONS. Blast radius counts
# annual demand for the finished goods a part feeds; this counts the orders
# already committed to a customer. They share a unit and answer differently: a
# part can block enormous annual volume with nothing promised this quarter, or
# tiny volume that is entirely spoken for next week, and a planner does
# something different about each. Optional, and cannot-tell where nobody has
# supplied an order book.
COMMITTED_AT_RISK = "committed_at_risk"
BUFFER_COVER = "buffer_cover"
PORTABILITY = "portability"
CONCENTRATION = "concentration"

DIMENSIONS = (WAIT_OUT_DAYS, RESOURCE_DAYS, BLAST_RADIUS, COMMITTED_AT_RISK,
              BUFFER_COVER, PORTABILITY, CONCENTRATION)

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
    wait_out_days: DimensionScore
    resource_days: DimensionScore
    blast_radius: DimensionScore
    committed_at_risk: DimensionScore
    buffer_cover: DimensionScore
    portability: DimensionScore
    concentration: object = None      # reserved for stage 5

    def scored(self):
        """The six dimensions stage 4 fills. Never summed, only iterated.

        `wait_out_days` and `resource_days` sit here as two entries rather than
        one, and they are both in days. THAT DOES NOT MAKE THEM ADDABLE: one is
        what a disruption costs if you ride it out with the source you have, the
        other what it costs to replace that source, and a part does both of
        those only in the sense that a person can do either. Adding them would
        answer a question nobody asked.
        """
        return (self.wait_out_days, self.resource_days, self.blast_radius,
                self.committed_at_risk, self.buffer_cover, self.portability)

    def all_scores(self):
        """The six, plus concentration once stage 5 has filled its slot.

        ADDED, never substituted. `scored()` keeps its stage 4 meaning of "the
        dimensions that are properties of the part alone", because stage 5 may
        add a method and may not change what an existing one means.
        """
        filled = self.scored()
        return filled + ((self.concentration,) if self.concentration else ())

    def abstentions(self):
        return tuple(s for s in self.scored() if not s.is_settled)


# ------------------------------------------------------------- wait out days --

def wait_out_days(part_number, verdict, lead_times):
    """Days to wait out the disruption, quoted and p95 together.

    HALF OF RECOVERY, AND THE NAME NOW SAYS SO. This used to be called
    `lead_time_to_recover`, which promised the whole of the brief's first
    dimension and delivered the purchase lead time. The other half is
    `resource_days`, and the two never combine.

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
            part_number=part_number, dimension=WAIT_OUT_DAYS,
            value=None, unit=DAYS, completeness=NO_RECOVERY_PATH,
            reasons=("somebody checked the supplier list and there is nobody "
                     "on it, so there is no order to place and nothing to wait "
                     "for. This is not a missing lead time: it is a part with "
                     "no supplier",))

    if verdict == V.MADE_IN_HOUSE:
        # The dimension does not APPLY, which is not the same as lacking an
        # input. There is no in-house capacity model anywhere in this data and
        # there is not going to be one, so a lane that keeps showing in-house
        # parts is asking a reviewer to fetch data that does not exist.
        return DimensionScore(
            part_number=part_number, dimension=WAIT_OUT_DAYS,
            value=None, unit=DAYS, completeness=NOT_APPLICABLE,
            reasons=("we make this part ourselves, so there is no purchase "
                     "lead time to wait out. This question does not apply to "
                     "the part rather than being something nobody knows",))

    if not pairs:
        return DimensionScore(
            part_number=part_number, dimension=WAIT_OUT_DAYS,
            value=None, unit=DAYS, completeness=CANNOT_TELL,
            reasons=("no supplier on this part has a lead time on file, so we "
                     "cannot say how long it would take for parts to flow "
                     "again",))

    if verdict == V.SUPPLIER_LIST_UNKNOWN:
        # A lead time exists, but the list it came from is unconfirmed, so the
        # fastest recovery path may belong to a supplier nobody wrote down.
        return DimensionScore(
            part_number=part_number, dimension=WAIT_OUT_DAYS,
            value=None, unit=DAYS, completeness=CANNOT_TELL,
            reasons=("nobody has confirmed the supplier list, so a faster "
                     "supplier may exist that was never written down",))

    quoted = min(pair[0] for pair in pairs)
    p95 = min(pair[1] for pair in pairs)
    return DimensionScore(
        part_number=part_number, dimension=WAIT_OUT_DAYS,
        value=(quoted, p95), unit=DAYS, completeness=KNOWN,
        reasons=(f"the fastest supplier quotes {quoted} days, and {p95} days "
                 f"in the worst case",),
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
        reason = (f"stops {len(goods)} finished good(s), which is "
                  f"{usage.blocked_finished_good_units} units a year")
    elif usage.completeness == USAGE_PARTIAL:
        completeness = LOWER_BOUND
        reason = (f"stops {len(goods)} finished good(s). The "
                  f"{usage.blocked_finished_good_units} units a year counts "
                  f"only the ones with demand on file, so the real figure can "
                  f"only be higher: demand nobody recorded still stops")
    else:
        completeness = LOWER_BOUND
        reason = (f"stops {len(goods)} finished good(s), none of which has "
                  f"demand on file. We know what it stops and cannot say how "
                  f"many units that is, so zero here means nothing was "
                  f"recorded rather than nothing is lost")

    return DimensionScore(
        part_number=part_number, dimension=BLAST_RADIUS,
        value=usage.blocked_finished_good_units, unit=FINISHED_GOOD_UNITS,
        completeness=completeness, reasons=(reason,),
        detail={"finished_goods_blocked": len(goods),
                "finished_goods": tuple(goods),
                "assemblies_blocked": len(goods),
                # WHICH BRANCH RAN, not what its value happened to be.
                #
                # LOWER_BOUND is assigned by two branches above: partial usage,
                # where some finished goods are recorded, and cannot-tell, where
                # none are. A reader downstream cannot tell them apart from
                # `completeness` and `value` alone, and inferring it from
                # `value == 0` would be wrong: partial usage whose recorded goods
                # happen to total zero is a RECORDED zero, while cannot-tell is
                # an absence. Collapsing those is exactly the missing-versus-zero
                # conflation this file separates before any arithmetic.
                #
                # The branch is named rather than reduced to a boolean like
                # `units_countable`, so a third usage state added later arrives
                # as an unrecognised name that a consumer must handle explicitly
                # instead of silently inheriting one of these two readings.
                "usage_completeness": usage.completeness,
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
            reasons=("there is no stock count on file for this part, so we "
                     "cannot say how long stock lasts. This is not the same as "
                     "having no stock",))

    if usage.completeness == USAGE_CANNOT_TELL:
        return DimensionScore(
            part_number=part_number, dimension=BUFFER_COVER, value=None,
            unit=DAYS, completeness=CANNOT_TELL,
            reasons=usage.reasons + (
                "so we do not know how fast this part is used, and cannot say "
                "how long stock lasts",))

    if usage.value == 0:
        # On-hand with nothing consuming it. Unbounded cover is an ANSWER, and
        # a division by zero here would be the code mistaking an answer for an
        # error.
        return DimensionScore(
            part_number=part_number, dimension=BUFFER_COVER, value=UNBOUNDED,
            unit=DAYS, completeness=KNOWN,
            reasons=(f"{on_hand_units} units in stock and nothing recorded as "
                     f"using them, so the stock lasts indefinitely. That is an "
                     f"answer, not a gap",),
            detail={"on_hand_units": on_hand_units, "unbounded": True,
                    "annual_usage": Fraction(0)})

    daily = Fraction(usage.value, DAYS_PER_YEAR)
    days = Fraction(on_hand_units) / daily

    if usage.completeness == USAGE_PARTIAL:
        # Usage sits in the DENOMINATOR, so unrecorded demand can only make the
        # divisor bigger and the cover smaller. Opposite direction to blast
        # radius, from the identical missing row.
        completeness = UPPER_BOUND
        reason = (f"{on_hand_units} units in stock lasts {float(days):.1f} "
                  f"days at the usage on file, and the real figure can only be "
                  f"lower: " + usage.reasons[0] + ", and usage nobody recorded "
                  f"still consumes this part")
    else:
        completeness = KNOWN
        reason = (f"{on_hand_units} units in stock lasts {float(days):.1f} "
                  f"days at {float(usage.value):.0f} units a year")

    return DimensionScore(
        part_number=part_number, dimension=BUFFER_COVER, value=days, unit=DAYS,
        completeness=completeness, reasons=(reason,),
        detail={"on_hand_units": on_hand_units, "annual_usage": usage.value,
                "daily_consumption": daily, "unbounded": False})


# ------------------------------------------------------------ resource days --

def _stage_phrase(timings):
    """Stage labels as prose, in chain order. Names the stages, never counts."""
    return ", ".join(timing.stage.label for timing in timings)


def resource_days(part_number, tooling_owner, stages=None):
    """Days to bring an ALTERNATIVE source to production. A chain, not a lookup.

    THE VERDICT IS NOT AN INPUT HERE, and its absence from the signature is the
    clearest evidence the split was right. Waiting it out depends entirely on
    what the supplier list says: no supplier means no wait to time, in-house
    means no purchase order to place. Resourcing does not. A part nobody
    supplies is exactly the part that has to be resourced, and a part made
    in-house can be given to an outside source. So where `wait_out_days` reports
    `no_recovery_path` or `not_applicable`, this one still answers, and those
    two readings together are what the old single dimension could not say.

    THE STATES, AND WHY EACH ONE RATHER THAN THE NEXT:

      known        every stage on the path is timed AND the cycle count is on
                   file, so nothing is being assumed
      lower_bound  a stage on the path has no duration, or the cycle count is
                   absent so the total silently assumes one pass. Either way the
                   true figure is higher and the sentence says which
      cannot_tell  nothing on the path is timed. Not a bound: zero is the
                   trivial lower bound of any duration, so calling this one
                   would promise a figure and deliver nothing

    A stage that DOES NOT HAPPEN is not a stage nobody timed. Company-owned
    tooling moves to the new source, so the tooling stage is off the path and
    contributes nothing without making the total a bound. An unrecorded tooling
    owner is the opposite: nobody knows whether it is on the path, so it bounds.
    """
    built = R.chain(tooling_owner, stages)
    timed, untimed, skipped = built.timed, built.untimed, built.skipped
    first_pass = built.first_pass_days
    with_retry = built.with_retry_days

    detail = {
        "days_by_stage": {t.stage.key: t.days for t in timed},
        # THE CLASSES STAY APART. Each subtotal is days of one kind of claim,
        # and there is nothing here that reduces them to a single figure.
        "days_by_class": built.days_by_class,
        "weakest_class": built.weakest_class,
        "stages_timed": tuple(t.stage.key for t in timed),
        "stages_untimed": tuple(t.stage.key for t in untimed),
        "stages_not_applicable": tuple(t.stage.key for t in skipped),
        "qualification_cycles": built.cycles,
        "first_pass_days": first_pass,
        "with_retry_days": with_retry,
    }

    if first_pass is None:
        return DimensionScore(
            part_number=part_number, dimension=RESOURCE_DAYS, value=None,
            unit=DAYS, completeness=CANNOT_TELL,
            reasons=("nobody has recorded how long any step of approving a "
                     "new supplier takes, so we cannot say how long it would "
                     "take. The steps nobody has timed are "
                     + _stage_phrase(untimed),),
            detail=detail)

    reasons = []
    if untimed:
        reasons.append(
            f"approving a new supplier takes at least {first_pass} days for "
            f"{_stage_phrase(timed)}. It could take longer: nobody has timed "
            f"{_stage_phrase(untimed)}")
    else:
        reasons.append(f"approving a new supplier takes {first_pass} days for "
                       f"{_stage_phrase(timed)}")

    if built.cycles is None:
        reasons.append(
            "nobody has said how many approval attempts to plan for, so this "
            "counts one. If it takes two, it will be longer than the figure "
            "above")
    elif with_retry is None:
        reasons.append(
            f"{built.cycles} approval attempts are planned for, and nobody has "
            f"timed the step that repeats, so we cannot say what a second "
            f"attempt would add")
    else:
        planned = (f"the {built.cycles} attempts" if built.cycles > 1
                   else "a single attempt")
        reasons.append(
            f"{first_pass} days if it is approved first time, {with_retry} "
            f"days over {planned} planned for")

    if skipped:
        reasons.append(f"{_stage_phrase(skipped)} does not happen for this "
                       f"part and adds no time. That is different from a step "
                       f"nobody has timed")

    completeness = LOWER_BOUND if (untimed or built.cycles is None) else KNOWN
    return DimensionScore(
        part_number=part_number, dimension=RESOURCE_DAYS, value=first_pass,
        unit=DAYS, completeness=completeness, reasons=tuple(reasons),
        detail=detail)


# ------------------------------------------------------ committed at risk --

def committed_at_risk(part_number, rows, commitments):
    """Orders already promised that this part would stop.

    `commitments` maps a finished good to units already committed to a customer,
    or None where no order book was supplied at all. THOSE TWO ARE DIFFERENT and
    the branch below separates them before any arithmetic, exactly as
    `buffer_cover` separates a missing on-hand record from a counted zero.

    THE BOUND DIRECTION IS THE SAME AS BLAST RADIUS'S, and for the same reason:
    committed units sit in the numerator, so a finished good with no row in the
    order book can only ADD to what is at risk. A partial order book therefore
    gives a lower bound, never an upper one.

    NOTHING RECORDED IS NOT A BOUND OF ZERO. Where none of the finished goods
    this part feeds appears in the order book, zero is the trivial lower bound
    of any non-negative quantity: it would promise a figure and deliver nothing.
    That case abstains, which is the repair `render._blocked_volume_absent`
    already carries for the volumetric half of blast radius.
    """
    goods = sorted({row.finished_good for row in rows})

    if commitments is None:
        return DimensionScore(
            part_number=part_number, dimension=COMMITTED_AT_RISK, value=None,
            unit=FINISHED_GOOD_UNITS, completeness=CANNOT_TELL,
            reasons=("no order book was supplied, so we cannot say what "
                     "promised orders this part would stop",),
            detail={"finished_goods_blocked": len(goods)})

    if not goods:
        # A part that feeds no finished good stops no promised order. Settled
        # rather than unknown: with an order book in hand, "nothing depends on
        # it" is an answer. Unreachable on real input, where stage 2 guarantees
        # every part reaches a finished good, and reachable in a fixture, which
        # is where a degenerate case is usually met first.
        return DimensionScore(
            part_number=part_number, dimension=COMMITTED_AT_RISK, value=0,
            unit=FINISHED_GOOD_UNITS, completeness=KNOWN,
            reasons=("this part feeds no finished good, so no promised order "
                     "depends on it",),
            detail={"finished_goods_blocked": 0})

    recorded = {good: commitments[good] for good in goods
                if good in commitments}
    missing = [good for good in goods if good not in commitments]
    total = sum(recorded.values())
    detail = {"finished_goods_blocked": len(goods),
              "finished_goods_with_orders": tuple(sorted(recorded)),
              "finished_goods_without_orders": tuple(missing),
              "committed_units": total}

    if not recorded:
        return DimensionScore(
            part_number=part_number, dimension=COMMITTED_AT_RISK, value=None,
            unit=FINISHED_GOOD_UNITS, completeness=CANNOT_TELL,
            reasons=(f"none of the {len(goods)} finished good(s) this part "
                     f"feeds appears in the order book, so what is promised "
                     f"against them is not recorded. That is not the same as "
                     f"nothing being promised",),
            detail=detail)

    if missing:
        return DimensionScore(
            part_number=part_number, dimension=COMMITTED_AT_RISK, value=total,
            unit=FINISHED_GOOD_UNITS, completeness=LOWER_BOUND,
            reasons=(f"{total} promised units would stop, counting only the "
                     f"{len(recorded)} of {len(goods)} finished good(s) that "
                     f"appear in the order book. The real figure can only be "
                     f"higher: orders nobody recorded still stop",),
            detail=detail)

    return DimensionScore(
        part_number=part_number, dimension=COMMITTED_AT_RISK, value=total,
        unit=FINISHED_GOOD_UNITS, completeness=KNOWN,
        reasons=(f"{total} promised units would stop, across every one of the "
                 f"{len(goods)} finished good(s) this part feeds",),
        detail=detail)


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
            reasons=("nobody has recorded who owns the tooling, so we cannot "
                     "say how hard this part would be to move",))

    owner = tooling_owner.strip()
    if owner == TOOLING_SUPPLIER:
        reason = ("the supplier owns the tooling, so moving to another "
                  "supplier means paying for new tooling, not just raising a "
                  "purchase order somewhere else")
    else:
        reason = ("we own the tooling, so it can move to another supplier "
                  "without anybody cutting new tooling")
    return DimensionScore(
        part_number=part_number, dimension=PORTABILITY, value=owner,
        unit=CATEGORICAL, completeness=KNOWN, reasons=(reason,))


# ------------------------------------------------------------------ profile --

def score_part(part_number, verdict, rows, usage, on_hand_units, tooling_owner,
               lead_times, recovery_stages=None, commitments=None):
    """All six dimensions for one part. Concentration stays reserved.

    `commitments` maps a finished good to units already promised, or None where
    no order book exists. None is not an empty order book: see
    `committed_at_risk`.

    `recovery_stages` is the part's row of `recovery_inputs.csv`, or None where
    no such file exists. None is not an empty plan: it means nobody has supplied
    a single stage duration, and `resource_days` says so rather than reporting a
    chain of zeroes.
    """
    return ExposureProfile(
        part_number=part_number,
        wait_out_days=wait_out_days(part_number, verdict, lead_times),
        resource_days=resource_days(part_number, tooling_owner,
                                    recovery_stages),
        blast_radius=blast_radius(part_number, rows, usage),
        committed_at_risk=committed_at_risk(part_number, rows, commitments),
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
