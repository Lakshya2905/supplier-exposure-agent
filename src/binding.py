"""What binds on a part, and what blocks it. Named in words, never ranked.

WHY THIS FILE EXISTS, AND WHAT IT IS CAREFUL NOT TO BE. Every competitor leads
with a branded composite: a Resiliency Index, an i-Score, a Risk Radar. Six
separate measures with no hierarchy read as an unfinished version of that unless
the interface says otherwise, so where an index would go this system puts words.

The obvious way to write those words is the thing the whole project refuses.
"Which dimension is worst for this part" requires comparing 300 days against
12,000 finished-good units, and there is no unit in which those are the same
quantity. Any function that answered it would be a composite with the arithmetic
hidden inside a superlative.

SO THIS COMPARES STATES, NEVER MAGNITUDES. A dimension BINDS when it has reached
the worst value it can express WITHOUT A THRESHOLD: nobody to wait on, stock
counted and empty, tooling that does not come with you. Those are categorical
facts about one dimension, read one dimension at a time, and no two of them are
ever weighed against each other.

TWO LISTS, NOT ONE, because the project's own vocabulary already separates them
and collapsing them would undo that:

    binds     a settled fact that is as bad as this measure gets
    blocks    an abstention, where nothing can be decided until somebody fetches

A part may have several of each, and this returns all of them in dimension
order. It does NOT pick one, because picking would need the comparison above.

WHAT HAS NO TERMINAL STATE, AND WHY THAT IS THE ANSWER. Blast radius and
resourcing days have no entry below. Neither has a worst value that can be named
without somebody first saying how many units is too many or how many days is too
long, and that is a threshold, which is a judgment, which lives in
`config/archetypes.yaml` under a named owner. A part whose only notable feature
is a large blast radius therefore binds on nothing here, and the interface says
so rather than promoting the largest number on the row.
"""
from . import governance as gov
from . import scoring
from .concentration import MINIMUM_CORRELATION

# ONE ENTRY PER DIMENSION, and a dimension with no terminal state is ABSENT by
# name rather than by omission: `test_binding.py` asserts every dimension is
# either in this table or in NO_TERMINAL_STATE, so a dimension added later
# cannot quietly acquire neither.
#
# Each test takes a settled DimensionScore and answers yes or no about THAT
# dimension alone. No test may read another dimension, and none may compare a
# number with anything but a constant of its own unit.


def _nobody_to_wait_on(score):
    return score.completeness == scoring.NO_RECOVERY_PATH


def _counted_and_empty(score):
    """A RECORDED zero, never a missing one.

    `completeness == KNOWN` is doing the work: a blank on-hand record produces
    `cannot_tell` and a value of None, and reading that as zero cover is the
    single collapse this codebase is built to prevent. It would also be the
    worst possible place for it, because this function's output is a headline.
    """
    return score.completeness == scoring.KNOWN and score.value == 0


def _tooling_does_not_move(score):
    return (score.completeness == scoring.KNOWN
            and score.value == scoring.TOOLING_SUPPLIER)


def _shared_with_others(score):
    """Correlated exposure. RECOMMENDS, and it still binds.

    Autonomy and bindingness are different questions. Concentration never
    executes, because grouping is a modelling judgment; that is about who may
    assert it, not about whether it is the thing hurting this part. A cluster a
    reviewer has not yet confirmed is still the reason a second source would not
    help, and hiding it until confirmation would make the queue a gate on the
    finding rather than on the claim.

    THE VALUE IS A CLUSTER SIZE, NOT A COUNT OF OTHERS, so the test is against
    `MINIMUM_CORRELATION` and not against zero. A part in a cluster of one is
    correlated with nothing, and `value > 0` would have marked every part in the
    dataset as bound by concentration. Imported rather than written as `> 1`,
    because the arity that makes a correlation exist at all is
    `concentration`'s to state and a second copy of it here would be a second
    place to change it.
    """
    return (score is not None and score.completeness == scoring.KNOWN
            and isinstance(score.value, int)
            and score.value >= MINIMUM_CORRELATION)


BINDS = {
    scoring.WAIT_OUT_DAYS: (
        _nobody_to_wait_on,
        "there is nobody to wait on: the supplier list was checked and is "
        "empty, so no purchase order can be placed at any lead time"),
    scoring.BUFFER_COVER: (
        _counted_and_empty,
        "stock is counted and empty, so there is no cover at all while a "
        "replacement is arranged"),
    scoring.PORTABILITY: (
        _tooling_does_not_move,
        "the supplier owns the tooling, so moving to another source means "
        "cutting new tooling rather than raising a purchase order"),
    scoring.CONCENTRATION: (
        _shared_with_others,
        "its exposure is shared with other parts, so a disruption here is not "
        "independent of the rest"),
}

# Named rather than omitted. See the module docstring: a worst value for either
# of these needs a threshold, and a threshold is a judgment with an owner.
NO_TERMINAL_STATE = {
    scoring.BLAST_RADIUS: (
        "how much of the build stops has no worst value until somebody says "
        "how much is too much, and that threshold lives in "
        "config/archetypes.yaml"),
    scoring.RESOURCE_DAYS: (
        "how long resourcing takes has no worst value until somebody says how "
        "long is too long, and that threshold lives in "
        "config/archetypes.yaml"),
}


def binds(profile):
    """Dimensions at their worst expressible state, in dimension order.

    ORDER IS `scoring.DIMENSIONS` ORDER, which is the order the dimensions were
    declared in and carries no meaning. Stated here and labelled on screen,
    because any plausible default order is read as a ranking within minutes.
    """
    found = []
    for score in profile.all_scores():
        entry = BINDS.get(score.dimension)
        if entry and entry[0](score):
            found.append({"dimension": score.dimension, "sentence": entry[1],
                          "autonomy": score.autonomy})
    return tuple(found)


def blocks(profile):
    """Dimensions that abstain: nothing here can be decided until a fetch.

    SEPARATE FROM `binds` ON PURPOSE. "As bad as it gets" and "nobody can tell"
    are different instructions to a reader, and a single list mixing them would
    make an unknown look like a finding and a finding look like a gap.
    """
    return tuple({"dimension": score.dimension,
                  "sentence": score.reasons[0],
                  "autonomy": score.autonomy}
                 for score in profile.all_scores()
                 if score.completeness == scoring.CANNOT_TELL)


def summary(profile):
    """Both lists, plus what to say when neither has anything in it."""
    binding, blocking = binds(profile), blocks(profile)
    return {
        "binds": binding,
        "blocks": blocking,
        # THE HONEST EMPTY CASE. A part with no terminal state and no abstention
        # has nothing this function can single out, and saying so is the answer
        # rather than a gap in it. Promoting the largest number on the row here
        # is exactly the composite the module refuses.
        "nothing_binds": not binding and not blocking,
        "no_terminal_state": dict(NO_TERMINAL_STATE),
    }


def log_binding(log, profile, at="1970-01-01T00:00:00+00:00"):
    """One event naming what binds. Structured; the sentences are the table's."""
    found = summary(profile)
    log.append(status=gov.STATUS_PROPOSED, sku_id=profile.part_number,
               field="binding", value="", at=at,
               kind=gov.KIND_DIMENSION_SCORED,
               evidence={"binds": [b["dimension"] for b in found["binds"]],
                         "blocks": [b["dimension"] for b in found["blocks"]],
                         "reasons": [b["sentence"] for b in found["binds"]]
                         or ["nothing about this part is at its worst state"]})
