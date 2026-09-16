"""If this supplier stopped, what stops, what the ways out are, and how long.

THE COUNTERFACTUAL IS COMPUTED BY THE SAME FUNCTION THAT COMPUTED THE ACTUAL
VERDICT. `identify()` is called again with the supplier struck from the part's
lists, so the counterfactual inherits the whole tested path: the fuzzy merge,
the dual reading, the verdict table, and the exception lane when the two
readings disagree. Reasoning about the answer `identify()` already gave would be
a second implementation of the same question, and the corrections log records
twice what happens then -- the one nobody looks at is the one that drifts.

THREE QUESTIONS, ANSWERED SEPARATELY, because they have different answers and
different confidence:

  does anything break          recompute the verdict without this supplier
  is there a backup            is another supplier still on the part, and can
                               it quote
  how long to resolve it       one duration per PATH, each in its own unit and
                               carrying its own completeness

THE PATHS ARE LISTED AND NEVER CHOSEN. CLAUDE.md puts recommended actions at
`recommends` permanently: the system names what could be done and a person
selects. So a part with a backup supplier AND a resourcing chain carries both
paths with both durations, and this module does not decide that switching beats
qualifying. It cannot: which is better depends on price, on quality history and
on whether the backup has capacity, and none of those are in this data.

WHAT THIS IS NOT. It is not a probability that the supplier fails, not a
severity, and not a ranking of suppliers by how bad their loss would be. It
answers one hypothetical that a person chose to pose. Ordering the parts it
returns is by a single named axis, as everywhere else.

NOTHING HERE IS A NEW MEASURE. Every duration returned is one the scoring
library already computed, carried through with its unit and its completeness
intact. This module joins and filters; it does not score.
"""
from dataclasses import dataclass

from . import governance as gov
from . import scoring
from .identify import identify
from .normalise import canonical_key
from .synthetic import verdicts as V

# ------------------------------------------------------------- what happens --
STOPS = "stops"                    # no supplier left who could take the order
SOLE_SOURCED = "sole_sourced"      # someone is left, and now there is only one
STILL_MULTI = "still_multi"        # more than one source remains
UNSETTLED = "unsettled"            # the reading did not settle without them
DOES_NOT_APPLY = "does_not_apply"  # made in house; no purchase to lose

# ------------------------------------------------------------ the ways out --
SWITCH = "switch"        # another supplier already on this part can quote
SWITCH_UNTIMED = "switch_untimed"   # one remains, and nobody has its lead time
QUALIFY = "qualify"      # stand up a source that is not on this part today
RIDE_IT_OUT = "ride_it_out"         # stock, while either of the above happens


@dataclass(frozen=True)
class Path:
    """One way out, with how long it takes and how well that is known.

    `days` is whatever the scoring library produced -- an int, a (quoted, p95)
    pair, a Fraction, or None -- and `completeness` says what kind of figure it
    is. NEVER a number of this module's own making: a path whose duration this
    file computed would be a sixth measure nobody tested.
    """
    kind: str
    label: str
    days: object
    completeness: str
    unit: str = scoring.DAYS
    #: Permanently `recommends`. Naming a path is not choosing it, and choosing
    #: needs price, quality history and capacity, none of which are here.
    autonomy: str = gov.RECOMMENDS


@dataclass(frozen=True)
class Affected:
    part_number: str
    verdict_now: str
    verdict_without: str
    suppliers_remaining: int
    remaining_can_quote: int
    outcome: str
    paths: tuple


# The outcome, from the verdict the part would carry WITHOUT this supplier.
# A lookup rather than a chain of ifs, for the reason the sourcing verdict is
# one: the distinctions are the product. Two are easy to lose in an `if`:
#
#   no_qualified_supplier  means somebody checked and there is nobody. That is
#                          STOPS, and it is not the same as
#   supplier_list_unknown  which means nobody confirmed the list, so a source
#                          may exist that was never written down. UNSETTLED.
OUTCOME_OF_VERDICT = {
    V.NO_QUALIFIED_SUPPLIER: STOPS,
    V.SINGLE_SOURCE: SOLE_SOURCED,
    V.SINGLE_SOURCE_NO_LEAD_TIME: SOLE_SOURCED,
    V.HIDDEN_SINGLE_SOURCE: SOLE_SOURCED,
    V.MULTI_SOURCE: STILL_MULTI,
    V.MULTI_SOURCE_NO_LEAD_TIMES: STILL_MULTI,
    V.SUPPLIER_LIST_UNKNOWN: UNSETTLED,
    V.READINGS_DISAGREE: UNSETTLED,
    V.MADE_IN_HOUSE: DOES_NOT_APPLY,
}


def _without(names, supplier):
    """The list with one supplier struck, matched the way the joins match it.

    CANONICAL KEYS, NOT RAW STRINGS. `sources.csv` and `lead_times.csv` spell
    the same supplier differently and the whole identification path already
    accounts for that. Striking by raw string would remove the supplier from one
    file and leave it in the other, and the counterfactual would then describe a
    company that half exists.
    """
    target = canonical_key(supplier)
    return [name for name in names if canonical_key(name) != target]


def _paths(outcome, profile, remaining_can_quote):
    """Every way out that is open, with its duration. Never a choice between.

    RIDE IT OUT IS LISTED FIRST AND IS NOT A RESOLUTION. Stock is what buys
    time for one of the others; presenting it alongside them would let a reader
    take "82 days of cover" as a fix.
    """
    if outcome == DOES_NOT_APPLY:
        return ()

    cover = profile.buffer_cover
    paths = [Path(RIDE_IT_OUT, "hold on existing stock while one of the below "
                  "happens", cover.value, cover.completeness, cover.unit)]

    if outcome in (SOLE_SOURCED, STILL_MULTI):
        wait = profile.wait_out_days
        if remaining_can_quote:
            paths.append(Path(
                SWITCH, "move the order to a supplier already on this part",
                wait.value, wait.completeness, wait.unit))
        else:
            # A supplier remains and nobody has its lead time. That is not a
            # duration of zero and not an absence of a path: the path exists
            # and its length is unknown, which is a different thing to report.
            paths.append(Path(
                SWITCH_UNTIMED,
                "move the order to the supplier that remains, whose lead time "
                "nobody has on file", None, scoring.CANNOT_TELL, wait.unit))

    if outcome in (STOPS, SOLE_SOURCED, UNSETTLED):
        chain = profile.resource_days
        paths.append(Path(
            QUALIFY, "stand up a source that is not on this part today",
            chain.value, chain.completeness, chain.unit))
    return tuple(paths)


def if_supplier_stops(result, supplier):
    """Every part this supplier touches, and what the loss of them would mean.

    Returns rows ordered by outcome severity and then by part number, which is
    a NAMED order over a stated sequence rather than a score: stops before sole
    sourced before unsettled, because a part with nobody left is a different
    kind of finding from one with a single source remaining.
    """
    inputs = result.sourcing_inputs
    order = (STOPS, SOLE_SOURCED, UNSETTLED, STILL_MULTI, DOES_NOT_APPLY)

    affected = []
    for part, names in sorted(inputs.supplier_names.items()):
        if canonical_key(supplier) not in {canonical_key(n) for n in names}:
            continue
        source_type, list_status = inputs.part_master[part]
        remaining = _without(names, supplier)
        quoting = _without(inputs.lead_time_names.get(part, []), supplier)
        finding = identify(part, source_type, list_status, remaining, quoting)
        without = finding.verdict
        profile = result.profiles.get(part)
        if profile is None:
            continue
        outcome = OUTCOME_OF_VERDICT[without]
        affected.append(Affected(
            part_number=part,
            verdict_now=result.verdicts.get(part, ""),
            verdict_without=without,
            suppliers_remaining=len(remaining),
            remaining_can_quote=len(quoting),
            outcome=outcome,
            paths=_paths(outcome, profile, len(quoting)),
        ))
    return tuple(sorted(affected,
                        key=lambda a: (order.index(a.outcome), a.part_number)))


def order_label():
    return ("Ordered by what the loss would mean, worst first: parts with "
            "nobody left, then parts down to one source, then parts the "
            "reading could not settle. That is a stated sequence of outcomes, "
            "not a score.")
