"""Does stock outlast the next delivery? An ordering, never a difference.

WHY THIS EXISTS AND WHY IT IS NOT THE THING THE README REFUSES. `buffer_cover`
and `wait_out_days` are both in days, and the README declines to subtract cover
from `resource_days`. That refusal stands and this does not touch it. Two things
separate them:

  THE OTHER QUANTITY. Resourcing is what you spend REPLACING a source, and
  comparing cover against it assumes you start on the day the source fails,
  which is a decision a person makes rather than a fact the data holds. Waiting
  for a delivery already quoted contains no such decision: nobody chooses to
  start waiting.

  ORDERING, NOT MAGNITUDE. Subtracting a lower bound from an upper bound
  compounds the error into a number that overstates the margin every time. An
  ordering states no margin. It is asserted ONLY where the two intervals do not
  overlap, and abstains everywhere they do, which is the uncertainty handling
  the README named as the thing to change if the position were ever revisited.

THE ASYMMETRY IS THE POINT AND IT IS NOT A DEFECT. `runs_out_first` is
assertable far more often than `outlasts_it`, because partial demand gives cover
a CEILING and no FLOOR: "at most 40 days" settles a comparison against a 60-day
quote and settles nothing against a 20-day one. So the alarming claim is the one
the data supports, which is the direction to be wrong in.

A TABLE RATHER THAN NESTED CONDITIONALS, for the same reason the sourcing
verdict is one: the distinctions are the product, and two of them are easy to
lose in an `if` chain.

  cover is an upper bound ABOVE the quote   is cannot_tell, not "outlasts".
                                            There is no floor under it
  wait_out is not_applicable                is a made part, and the question
                                            does not apply rather than being
                                            unknown

Tests hard-code their expected outcome by hand and must not import TABLE. If
they imported it, a wrong row would be wrong in both places and agree with
itself.
"""
from dataclasses import dataclass

from .scoring import (BUFFER_COVER, CANNOT_TELL, KNOWN, NOT_APPLICABLE,
                      NO_RECOVERY_PATH, UNBOUNDED, UPPER_BOUND, WAIT_OUT_DAYS)

# ------------------------------------------------------------------ outcomes --
RUNS_OUT_FIRST = "runs_out_first"
OUTLASTS_IT = "outlasts_it"
TOO_CLOSE_TO_CALL = "too_close_to_call"
CANNOT_SAY = "cannot_say"
DOES_NOT_APPLY = "does_not_apply"
NO_SUPPLIER_AT_ALL = "no_supplier_at_all"

# ------------------------------------------------------------------- buckets --
# What the cover figure settles on its own, given the two ends of the quote.
CEILING_BELOW_QUOTE = "ceiling_below_quote"  # at most X, and X < fastest quote
FLOOR_ABOVE_WORST = "floor_above_worst"      # at least X, and X > worst case
OVERLAPS = "overlaps"                        # known, and inside the quote range
NO_FLOOR = "no_floor"                        # an upper bound that settles nothing
COVER_UNKNOWN = "cover_unknown"
# There was no quote to compare against, so the stock figure was never read. A
# bucket of its own rather than a filler, because every other value on this axis
# is a CLAIM about the stock and this one must not be mistaken for one.
NOT_COMPARED = "not_compared"

WAIT_KNOWN = "wait_known"
WAIT_UNKNOWN = "wait_unknown"
WAIT_NOT_APPLICABLE = "wait_not_applicable"
WAIT_NO_SUPPLIER = "wait_no_supplier"

ANY = "*"


@dataclass(frozen=True)
class Row:
    cover: str
    wait: str
    outcome: str


# Ordered. First match wins, so rows about the wait side precede the cover ones:
# a part nobody buys has no purchase lead time to outlast, whatever its stock.
TABLE = (
    Row(ANY, WAIT_NOT_APPLICABLE, DOES_NOT_APPLY),
    Row(ANY, WAIT_NO_SUPPLIER, NO_SUPPLIER_AT_ALL),
    Row(ANY, WAIT_UNKNOWN, CANNOT_SAY),
    Row(COVER_UNKNOWN, ANY, CANNOT_SAY),
    Row(CEILING_BELOW_QUOTE, WAIT_KNOWN, RUNS_OUT_FIRST),
    Row(FLOOR_ABOVE_WORST, WAIT_KNOWN, OUTLASTS_IT),
    Row(OVERLAPS, WAIT_KNOWN, TOO_CLOSE_TO_CALL),
    Row(NO_FLOOR, WAIT_KNOWN, CANNOT_SAY),
)


def cover_bucket(cover, quoted, p95):
    """What the cover score settles against a quote range it is compared to.

    `quoted` and `p95` are only read where cover carries a number, so a caller
    with no wait figure may pass None for both.
    """
    if cover.completeness == CANNOT_TELL:
        return COVER_UNKNOWN
    if quoted is None:
        # Nothing to compare against. The wait side decides, and every row it
        # decides is ANY on this axis.
        return NOT_COMPARED
    if cover.value is UNBOUNDED:
        # Stock with nothing consuming it outlasts any lead time. An answer.
        return FLOOR_ABOVE_WORST
    if cover.value < quoted:
        # Holds for KNOWN and UPPER_BOUND alike: both are ceilings, and a
        # ceiling below the fastest quote settles the comparison downward.
        return CEILING_BELOW_QUOTE
    if cover.completeness == UPPER_BOUND:
        return NO_FLOOR
    return FLOOR_ABOVE_WORST if cover.value > p95 else OVERLAPS


def wait_bucket(wait):
    return {
        NOT_APPLICABLE: WAIT_NOT_APPLICABLE,
        NO_RECOVERY_PATH: WAIT_NO_SUPPLIER,
        CANNOT_TELL: WAIT_UNKNOWN,
        KNOWN: WAIT_KNOWN,
    }[wait.completeness]


def _matches(row, cover, wait):
    return all(expected in (ANY, actual) for expected, actual
               in ((row.cover, cover), (row.wait, wait)))


def _lookup(cover, wait):
    for row in TABLE:
        if _matches(row, cover, wait):
            return row.outcome
    raise KeyError(f"no row matches {(cover, wait)}")


@dataclass(frozen=True)
class RunOut:
    """The comparison, its reasons, and the two figures it read.

    CARRIES NO NUMBER OF ITS OWN, on purpose. A margin in days is the
    subtraction the README declines, and this is an ordering. The two figures
    are carried so a reader can see what was compared without a second lookup,
    and they keep their own units and their own completeness.
    """
    part_number: str
    outcome: str
    reasons: tuple
    cover_days: object = None
    quoted_days: object = None
    p95_days: object = None


def _sentence(outcome, cover, quoted, p95):
    """A planner's words. Never the bucket name, never the enum."""
    if outcome == RUNS_OUT_FIRST:
        at_most = "at most " if cover.completeness == UPPER_BOUND else ""
        return (f"stock lasts {at_most}{float(cover.value):.0f} days and the "
                f"fastest supplier quotes {quoted} days, so this part runs out "
                f"before a replacement order can arrive")
    if outcome == OUTLASTS_IT:
        if cover.value is UNBOUNDED:
            return ("nothing on file consumes this part, so stock outlasts any "
                    "lead time")
        return (f"stock lasts {float(cover.value):.0f} days and even the worst "
                f"case is {p95} days, so a replacement order arrives first")
    if outcome == TOO_CLOSE_TO_CALL:
        return (f"stock lasts {float(cover.value):.0f} days and the quote runs "
                f"from {quoted} to {p95} days, so whether this part runs out "
                f"depends on which end of the quote the supplier hits")
    if outcome == DOES_NOT_APPLY:
        return ("we make this part ourselves, so there is no purchase lead "
                "time for stock to outlast. The question does not apply to the "
                "part rather than being something nobody knows")
    if outcome == NO_SUPPLIER_AT_ALL:
        return ("there is no supplier to place a replacement order with, so "
                "there is no lead time for stock to outlast. However long the "
                "stock lasts is however long you have")
    if cover.completeness == UPPER_BOUND:
        return (f"stock lasts at most {float(cover.value):.0f} days, which is "
                f"above the {quoted}-day quote, and the real figure can only be "
                f"lower. Without complete usage there is no floor under it, so "
                f"we cannot say which runs out first")
    return "we do not have both figures, so we cannot compare them"


def run_out(profile):
    """Whether stock outlasts the next delivery, for one part.

    EXECUTES WHERE IT ANSWERS AND ABSTAINS WHERE IT DOES NOT, which needs no
    autonomy flag of its own: the abstention IS the outcome, named, carrying the
    reason it abstained. A `cannot_say` that a reader can act on is a different
    object from a finding withheld for review.
    """
    cover, wait = profile.buffer_cover, profile.wait_out_days
    assert cover.dimension == BUFFER_COVER and wait.dimension == WAIT_OUT_DAYS

    quoted, p95 = (wait.value if wait.completeness == KNOWN else (None, None))
    outcome = _lookup(cover_bucket(cover, quoted, p95), wait_bucket(wait))
    return RunOut(
        part_number=profile.part_number, outcome=outcome,
        reasons=(_sentence(outcome, cover, quoted, p95),),
        cover_days=cover.value, quoted_days=quoted, p95_days=p95)
