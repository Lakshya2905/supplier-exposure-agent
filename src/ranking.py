"""Ranked output: orders that exist, and no order that does not.

WHAT THIS MODULE PRODUCES, and what it deliberately does not:

  rank_by(dimension)   a TOTAL order, inside one named unit. Honest, because
                       everything compared is measured in the same thing.
  archetype groups     named conjunctions, laid out by subset dominance, which
                       is a PARTIAL order needing no weights.
  work_queue           the parts a missing field could still move.
  no overall rank      there is none. Producing one would require comparing
                       days with assemblies, and that comparison does not exist.

THE COUNT TRAP. Ordering parts by how many archetypes they match looks like
counting rather than scoring. It is a weighted sum with every weight set to 1,
and it is refused: `test_ranking.py` asserts no such count is computed anywhere.
Two archetypes matched is not worse than one unless one dominates the other, and
dominance is already expressed properly.

PARETO ACROSS PARTS: CONSIDERED AND DECLINED. Part X dominating part Y on every
dimension would be a legitimate weightless partial order. It is not built,
because across three hundred parts with abstentions the frontier is large and
almost everything is incomparable, and a large frontier presented as "the
answer" invites precisely the mental averaging the design refuses. Recorded here
so the decision is on file rather than rediscovered.
"""
from dataclasses import dataclass, field
from fractions import Fraction

from . import archetypes as A
from . import governance as gov
from . import scoring

# The default order within any group. ARBITRARY AND STABLE, and both halves
# matter. Arbitrary, because any plausible default is read as a ranking within
# minutes and nobody checks. Stable, because insertion order and dict order are
# arbitrary TODAY and silently become a meaningful order the moment an upstream
# function changes how it iterates, at which point the display acquires an
# ordering nobody chose and nobody can see.
#
# THE LABEL DOES NOT OFFER A CONTROL. It used to end "; choose a dimension to
# rank by", which promised a sort this interface has never had and must never
# have: a reviewer who sorts by one dimension has declared that dimension the
# ranking, which is the composite the whole system refuses to compute, arriving
# through a click. Filtering is a stated question and is offered freely; sorting
# is a smuggled conclusion. The first clause stays because the rule above
# requires the order be labelled; the invitation goes.
DEFAULT_ORDER_FIELD = "part_number"
DEFAULT_ORDER_LABEL = "ordered by part number, and the order carries no meaning"

# Which end of each dimension is worse. A DIRECTION, not a threshold: it says
# which way is bad, never where bad begins.
WORSE_IS = {
    scoring.BUFFER_COVER: "lower",
    scoring.LEAD_TIME_TO_RECOVER: "higher",
    scoring.BLAST_RADIUS: "higher",
    scoring.CONCENTRATION: "higher",
    scoring.PORTABILITY: "categorical",
}

# Portability is categorical, so it has an order but no arithmetic.
PORTABILITY_ORDER = (scoring.TOOLING_SUPPLIER, scoring.TOOLING_COMPANY)


def in_default_order(parts):
    """Sort by part number explicitly. Never rely on insertion or dict order."""
    return tuple(sorted(parts, key=lambda part: str(part)))


@dataclass(frozen=True)
class Membership:
    """One part against one archetype, in three-valued logic."""
    part_number: str
    archetype: str
    state: str
    values: dict = field(default_factory=dict)
    unknown_fields: tuple = ()
    autonomy: str = gov.EXECUTES
    threshold_source: str = ""


def evaluate(profile, verdict, archetype):
    context = {"profile": profile, "verdict": verdict}
    values = archetype.evaluate(context)
    unknown = tuple(sorted(
        condition.depends_on for condition in archetype.conditions
        if values[condition.name] == A.UNKNOWN))
    return Membership(
        part_number=profile.part_number, archetype=archetype.name,
        state=A.membership(values.values()), values=values,
        unknown_fields=unknown, autonomy=archetype.autonomy,
        threshold_source=archetype.threshold_source)


def classify(profiles, verdicts, catalogue):
    """Every part against every archetype."""
    return {
        (profile.part_number, archetype.name):
            evaluate(profile, verdicts.get(profile.part_number, ""), archetype)
        for profile in profiles for archetype in catalogue
    }


def matched(memberships, archetype_name):
    return in_default_order(
        m.part_number for m in memberships.values()
        if m.archetype == archetype_name and m.state == A.MATCHED)


@dataclass(frozen=True)
class WorkItem:
    """A part whose membership one missing field could still settle.

    CARRIES NO VALUE FOR THE MISSING FIELD, and there is no place to put one.
    """
    part_number: str
    archetype: str
    missing_fields: tuple


def work_queue(memberships, catalogue):
    """Parts a missing field could still move, grouped by archetype.

    THE MEMBERSHIP TEST *IS* THE RANKING CRITERION, and it is evaluated against
    the conditions as they actually stand with the field unknown. A part is here
    only when no condition is definitely false, which is exactly the statement
    "supplying this field could change the outcome". If some other condition
    already fails, the field cannot change anything and the part is not listed,
    however plausible its missing value would have been.

    NOTHING IS IMPUTED. No plausible cover is assumed and nothing is ordered by
    a value that was guessed. Six parts where supplying on-hand could flip them
    into an archetype is an honest queue; six parts ordered by a projected cover
    is a forecast wearing a work queue's clothes. The order is therefore by
    archetype and then by part number, which reads nothing from any dimension.
    """
    by_archetype = {}
    for archetype in catalogue:
        items = [
            WorkItem(part_number=m.part_number, archetype=archetype.name,
                     missing_fields=m.unknown_fields)
            for m in memberships.values()
            if m.archetype == archetype.name and m.state == A.CANNOT_TELL
        ]
        if items:
            by_archetype[archetype.name] = tuple(
                sorted(items, key=lambda item: item.part_number))
    return by_archetype


def _cover_key(score):
    value = score.value
    if value is scoring.UNBOUNDED:
        return Fraction(10 ** 9)
    return value


def rank_by(profiles, dimension):
    """A TOTAL order inside one unit. Worse first.

    Returns (ranked, not_comparable). Abstentions are not ranked, because a
    value that does not exist has no position, and giving it one at either end
    of the list is a claim.

    BOUNDED VALUES ARE RANKED AT THEIR BOUND and can only move toward the worse
    end: an upper bound on cover means the true cover is at most that, so its
    true position is never better than the one shown. The renderer says "at
    most" so a reader can see it.
    """
    ranked, not_comparable = [], {}
    for profile in profiles:
        score = getattr(profile, dimension, None)
        if score is None:
            not_comparable[profile.part_number] = "not computed"
            continue
        if score.completeness == scoring.CANNOT_TELL:
            not_comparable[profile.part_number] = "not answerable from the data"
            continue
        if score.completeness == scoring.NOT_APPLICABLE:
            not_comparable[profile.part_number] = "does not apply to this part"
            continue
        ranked.append(profile)

    direction = WORSE_IS[dimension]

    def key(profile):
        score = getattr(profile, dimension)
        # No recovery path is the worst possible reading of a lead time, and it
        # has no number, so it is placed rather than computed.
        worst_first = 0 if score.completeness == scoring.NO_RECOVERY_PATH else 1
        if dimension == scoring.PORTABILITY:
            rank = (PORTABILITY_ORDER.index(score.value)
                    if score.value in PORTABILITY_ORDER else len(
                        PORTABILITY_ORDER))
            return (worst_first, rank, profile.part_number)
        if dimension == scoring.LEAD_TIME_TO_RECOVER:
            measure = score.detail.get("quoted_days", 0)
        elif dimension == scoring.BUFFER_COVER:
            measure = _cover_key(score)
        else:
            measure = score.value if score.value is not None else 0
        measure = -measure if direction == "higher" else measure
        return (worst_first, measure, profile.part_number)

    return tuple(sorted(ranked, key=key)), not_comparable


@dataclass(frozen=True)
class ArchetypeGroup:
    name: str
    label: str
    members: tuple
    autonomy: str
    order_label: str = DEFAULT_ORDER_LABEL


def default_view(profiles, verdicts, catalogue):
    """The opening view. A GROUPING, not a ranking.

    Groups come back in dominance layers, so a display can place incomparable
    archetypes side by side instead of stacked and decline, in the layout
    itself, to imply an order that does not exist. Within a group the order is
    by part number and says so.

    The work queue is returned at the same level as the groups, not beneath
    them: it is frequently the most actionable list here, and placing it below
    would say otherwise.
    """
    memberships = classify(profiles, verdicts, catalogue)
    layers = []
    for layer in A.dominance_layers(catalogue):
        groups = []
        for archetype in layer:
            members = matched(memberships, archetype.name)
            groups.append(ArchetypeGroup(
                name=archetype.name, label=archetype.label, members=members,
                autonomy=archetype.autonomy))
        layers.append(tuple(groups))
    return {
        "layers": tuple(layers),
        "work_queue": work_queue(memberships, catalogue),
        "memberships": memberships,
        "order_label": DEFAULT_ORDER_LABEL,
    }


# ------------------------------------------------------------- the sentence --

def sentence_evidence(profile, verdict, memberships=()):
    """Structured clauses for the ranked sentence. NO PROSE IS STORED."""
    def clause(dimension):
        score = getattr(profile, dimension, None)
        if score is None:
            return None
        return {"dimension": dimension, "unit": score.unit,
                "completeness": score.completeness,
                "value": _plain(score.value),
                "detail": {k: _plain(v) for k, v in score.detail.items()}}

    return {
        "verdict": verdict,
        "clauses": [c for c in (clause(scoring.LEAD_TIME_TO_RECOVER),
                                clause(scoring.BUFFER_COVER),
                                clause(scoring.BLAST_RADIUS),
                                clause(scoring.PORTABILITY),
                                clause(scoring.CONCENTRATION)) if c],
        "archetypes": list(memberships),
    }


def _plain(value):
    """JSON-shaped, and EXACT until the renderer rounds it."""
    if isinstance(value, Fraction):
        return [value.numerator, value.denominator]
    if value is scoring.UNBOUNDED:
        return "unbounded"
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def log_ranked(log, profile, verdict, memberships=(),
               at="1970-01-01T00:00:00+00:00"):
    log.append(status=gov.STATUS_PROPOSED, sku_id=profile.part_number,
               field="ranked_summary", value=verdict, at=at,
               kind=gov.KIND_PART_RANKED,
               evidence=sentence_evidence(profile, verdict, memberships))
