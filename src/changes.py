"""What changed between two runs, and the four ways a diff usually lies.

WHY A DIFF AT ALL. A single run answers "what is exposed". The question a person
actually asks on a Monday is "what is exposed THAT WAS NOT LAST WEEK", and
answering it by reading two screens side by side is how a new single source goes
unnoticed for a month.

THE FOUR WAYS THIS GOES WRONG, each of which is a defect this project has a name
for already:

  1. AN UNKNOWN IS NOT A DECREASE. A part whose cover went from 40 days to "no
     stock count on file" has not improved and has not worsened: it has stopped
     being answerable. Subtracting the two would read as a fall to zero, which is
     the missing-versus-zero collapse arriving in the diff layer, where neither
     run made the mistake. Appearing and disappearing answers are their own kind
     of change and are reported as such.

  2. A BOUND IS NOT A MEASUREMENT. Cover at "at most 40" last week and "at most
     30" this week may not have moved at all: both are upper bounds and the true
     figures could be anything below them. A comparison between two bounds is
     only sound in the direction the bound points, so a change involving one is
     reported WITH its direction attached and never as a bare delta.

  3. A PART THAT LEFT THE SCOPE DID NOT GET BETTER. A run scoped to one
     criticality tier does not contain the parts it did not assess, and reading
     their absence as "no longer exposed" would let somebody make the exposure
     count fall by narrowing the question. Departures are reported as departures.

  4. TWO RUNS OF DIFFERENT DATA ARE NOT A TREND. The comparison states which
     datasets it read and when, because "cover fell across the board" means one
     thing between two Mondays and another between an ERP extract and a
     hand-built spreadsheet.

NOTHING HERE IS RANKED ACROSS KINDS. A new single source and a supplier that
gained a part are different events, and the only ordering inside each kind is by
part number, which the output labels as carrying no meaning.
"""
from dataclasses import dataclass, field
from fractions import Fraction

from . import scoring

# The kinds of change, named rather than inferred from a sign. A consumer
# switching on these cannot accidentally treat "became unknown" as a fall,
# because there is no number in it to compare.
NEWLY_EXPOSED = "newly_exposed"
NO_LONGER_EXPOSED = "no_longer_exposed"
VERDICT_CHANGED = "verdict_changed"
MEASURE_MOVED = "measure_moved"
BECAME_UNKNOWN = "became_unknown"
BECAME_KNOWN = "became_known"
ENTERED_SCOPE = "entered_scope"
LEFT_SCOPE = "left_scope"
CLUSTER_GREW = "cluster_grew"
CLUSTER_SHRANK = "cluster_shrank"
CLUSTER_APPEARED = "cluster_appeared"

KINDS = (NEWLY_EXPOSED, NO_LONGER_EXPOSED, VERDICT_CHANGED, MEASURE_MOVED,
         BECAME_UNKNOWN, BECAME_KNOWN, ENTERED_SCOPE, LEFT_SCOPE,
         CLUSTER_GREW, CLUSTER_SHRANK, CLUSTER_APPEARED)

# Which direction is worse, per measure, reused from `ranking` rather than
# restated: a second copy would be a second place for "lower cover is worse" to
# be got backwards.
from .ranking import WORSE_IS  # noqa: E402


@dataclass(frozen=True)
class Change:
    """One thing that is different, with enough context to judge it.

    `worsened` IS THREE-VALUED, and that is the point. True, False, or None for
    a change where the question does not apply or cannot be answered: a measure
    that became unknown has not worsened and has not improved, and forcing it
    into a boolean would make it one or the other.
    """
    kind: str
    subject: str
    dimension: str = ""
    before: object = None
    after: object = None
    worsened: object = None
    detail: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"unknown change kind: {self.kind!r}")


def _comparable(score):
    """A number to compare, or None when comparing would be a lie.

    Returns None for every unsettled state and for `unbounded`, which is a
    settled answer with no numeric position. A caller that got None must report
    the change by NAME rather than by delta.
    """
    if score is None or score.completeness == scoring.CANNOT_TELL:
        return None
    if score.value is None or score.value is scoring.UNBOUNDED:
        return None
    value = score.value
    if isinstance(value, (tuple, list)):
        # A pair travels together and the first element is the reported figure,
        # matching what `ranking` orders on, so the two cannot disagree.
        value = value[0] if value else None
    if isinstance(value, (int, Fraction)):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(value).limit_denominator()
    return None                      # categorical: compared by equality instead


def _is_bound(score):
    return score is not None and score.completeness in (
        scoring.UPPER_BOUND, scoring.LOWER_BOUND)


def compare_profiles(before, after):
    """Per-part, per-measure changes between two runs' profiles.

    Iterates the UNION of the parts, so a part that appeared and a part that
    vanished are both visible. A diff over the intersection is the one that
    quietly loses the new single source nobody had last week.
    """
    changes = []
    for part in sorted(set(before) | set(after)):
        old, new = before.get(part), after.get(part)
        if old is None or new is None:
            continue                 # membership is handled by compare_runs
        old_scores = {s.dimension: s for s in old.all_scores()}
        new_scores = {s.dimension: s for s in new.all_scores()}
        for dimension in sorted(set(old_scores) | set(new_scores)):
            changes.extend(_compare_one(part, dimension,
                                        old_scores.get(dimension),
                                        new_scores.get(dimension)))
    return tuple(changes)


def _compare_one(part, dimension, old, new):
    """One measure on one part. Returns zero or one change, never a guess."""
    if old is None or new is None:
        return ()

    old_settled = old.completeness != scoring.CANNOT_TELL
    new_settled = new.completeness != scoring.CANNOT_TELL

    # THE TWO ASYMMETRIC CASES FIRST, so neither can fall through to a delta.
    if old_settled and not new_settled:
        return (Change(kind=BECAME_UNKNOWN, subject=part, dimension=dimension,
                       before=old.value, after=None, worsened=None,
                       detail={"reason": new.reasons[0]}),)
    if new_settled and not old_settled:
        return (Change(kind=BECAME_KNOWN, subject=part, dimension=dimension,
                       before=None, after=new.value, worsened=None,
                       detail={"reason": new.reasons[0]}),)
    if not old_settled and not new_settled:
        return ()

    left, right = _comparable(old), _comparable(new)
    if left is None or right is None:
        # Categorical, unbounded, or a state with no number. Compared by
        # equality, because a change between two of these is real and a
        # subtraction between them is not.
        if str(old.value) == str(new.value) \
                and old.completeness == new.completeness:
            return ()
        return (Change(kind=MEASURE_MOVED, subject=part, dimension=dimension,
                       before=old.value, after=new.value, worsened=None,
                       detail={"comparable": False,
                               "before_completeness": old.completeness,
                               "after_completeness": new.completeness}),)

    if left == right and old.completeness == new.completeness:
        return ()

    direction = WORSE_IS.get(dimension)
    worsened = None
    if direction == "higher":
        worsened = right > left
    elif direction == "lower":
        worsened = right < left
    # A COMPARISON INVOLVING A BOUND KEEPS ITS DIRECTION AND LOSES ITS VERDICT.
    # Two upper bounds can both fall while the true figures rise, so the change
    # is reported and the judgment is withheld.
    if _is_bound(old) or _is_bound(new):
        worsened = None

    return (Change(kind=MEASURE_MOVED, subject=part, dimension=dimension,
                   before=old.value, after=new.value, worsened=worsened,
                   detail={"comparable": True,
                           "before_completeness": old.completeness,
                           "after_completeness": new.completeness,
                           "involves_a_bound": _is_bound(old)
                           or _is_bound(new)}),)


EXPOSED_VERDICTS = ("single_source", "single_source_no_lead_time",
                    "hidden_single_source")


def compare_verdicts(before, after, in_scope_before, in_scope_after):
    """Parts that became exposed, stopped being, or changed verdict.

    SCOPE IS SEPARATED FROM EXPOSURE, per the module docstring. A part missing
    from the later run because nobody assessed it is a departure, not a
    recovery, and the two are never merged: `left_scope` and `no_longer_exposed`
    are different rows and a reader can act on only one of them.
    """
    changes = []
    for part in sorted(set(before) | set(after)):
        was_present, is_present = part in in_scope_before, part in in_scope_after
        if was_present and not is_present:
            changes.append(Change(kind=LEFT_SCOPE, subject=part,
                                  before=before.get(part), after=None))
            continue
        if is_present and not was_present:
            changes.append(Change(kind=ENTERED_SCOPE, subject=part,
                                  before=None, after=after.get(part)))
            # A part that arrived AND is exposed is worth saying twice: it is
            # new to the assessment and it is a single point of failure.
            if after.get(part) in EXPOSED_VERDICTS:
                changes.append(Change(kind=NEWLY_EXPOSED, subject=part,
                                      before=None, after=after.get(part),
                                      worsened=True))
            continue
        if not (was_present and is_present):
            continue

        old, new = before.get(part, ""), after.get(part, "")
        if old == new:
            continue
        was, now = old in EXPOSED_VERDICTS, new in EXPOSED_VERDICTS
        if now and not was:
            changes.append(Change(kind=NEWLY_EXPOSED, subject=part,
                                  before=old, after=new, worsened=True))
        elif was and not now:
            changes.append(Change(kind=NO_LONGER_EXPOSED, subject=part,
                                  before=old, after=new, worsened=False))
        else:
            changes.append(Change(kind=VERDICT_CHANGED, subject=part,
                                  before=old, after=new, worsened=None))
    return tuple(changes)


def compare_clusters(before, after):
    """Clusters that grew, shrank or appeared, keyed by basis and key.

    A cluster is identified by (basis, key), never by key alone: a supplier and
    a region can share a name, and merging them would report a supplier growing
    when a region did.
    """
    def by_id(report):
        return {(c.basis, c.key): c for c in report.clusters
                if c.is_concentrated}

    old, new = by_id(before), by_id(after)
    changes = []
    for identity in sorted(set(old) | set(new)):
        basis, key = identity
        was, now = old.get(identity), new.get(identity)
        detail = {"basis": basis}
        if was is None:
            changes.append(Change(kind=CLUSTER_APPEARED, subject=key,
                                  before=None, after=now.size, worsened=True,
                                  detail=dict(detail, members=list(now.members))))
            continue
        if now is None:
            # Not "cluster disappeared": the parts may simply have left the
            # scope. Reported as a shrink to nothing, with the members that were
            # in it, so a reader can tell which.
            changes.append(Change(kind=CLUSTER_SHRANK, subject=key,
                                  before=was.size, after=0, worsened=False,
                                  detail=dict(detail,
                                              members=list(was.members))))
            continue
        if now.size == was.size and now.members == was.members:
            continue
        gained = [m for m in now.members if m not in was.members]
        lost = [m for m in was.members if m not in now.members]
        changes.append(Change(
            kind=CLUSTER_GREW if now.size > was.size else CLUSTER_SHRANK,
            subject=key, before=was.size, after=now.size,
            worsened=now.size > was.size,
            detail=dict(detail, gained=gained, lost=lost)))
    return tuple(changes)


@dataclass(frozen=True)
class Comparison:
    """Everything that is different, plus what was compared with what."""
    changes: tuple
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)

    def of_kind(self, kind):
        return tuple(c for c in self.changes if c.kind == kind)

    def worsened(self):
        return tuple(c for c in self.changes if c.worsened is True)

    def unjudged(self):
        """Changes where "better or worse" has no answer. NOT an empty result.

        These are the ones a diff usually drops, and they are the ones worth
        reading: a measure that stopped being answerable, and a bound that moved
        in a direction that says nothing about the true figure.
        """
        return tuple(c for c in self.changes if c.worsened is None)


def compare_runs(before, after):
    """Two `pipeline.Result`s, compared. Order is (older, newer).

    THE PROVENANCE OF BOTH IS CARRIED, because two runs of different datasets
    are not a trend and a reader has to be able to see which two this was.
    """
    in_before, in_after = set(before.profiles), set(after.profiles)
    changes = (
        compare_verdicts(before.verdicts, after.verdicts, in_before, in_after)
        + compare_profiles(before.profiles, after.profiles)
        + compare_clusters(before.report, after.report))

    def provenance(result):
        scope = result.scope
        return {"data_dir": str(result.data_dir),
                "parts_assessed": len(result.profiles),
                "scoped": bool(scope and scope.is_scoped),
                "criticality_included": list(scope.included) if scope else []}

    return Comparison(changes=tuple(changes), before=provenance(before),
                      after=provenance(after))
