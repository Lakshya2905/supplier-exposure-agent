"""Named patterns, expressed as conjunctions of conditions. Never as scores.

THERE IS NO SINGLE RANKING, AND THIS IS THE MODULE THAT REFUSES TO INVENT ONE.
Ranking needs an order, an order needs comparison, and comparison across
incommensurable units is what four stages have refused. The pressure to write a
weighted sum peaks here and it looks reasonable, because "rank these"
presupposes that a total order exists. It does not. Anything that produces one
has manufactured it, and the manufacture is always the same move: strip the
unit, rescale, add.

So severity is carried by NAMED CONJUNCTIONS. "Single source and long lead and
thin cover and supplier-owned tooling, all true at once" is a pattern with a
name, not a number, and it is what the brief's headline sentence actually
describes.

TWO FAMILIES, GOVERNED DIFFERENTLY.

  structural  every condition is a state the pipeline already computes: a
              verdict, a categorical value, a completeness state. NO THRESHOLD
              EXISTS, so none can be smuggled in. Ships with the system.
  magnitude   at least one condition compares a measure against a number.
              "Long" and "thin" are bands, and stage 4 refused to band a
              measure. The band is not hidden here, it is MOVED OUT: it lives
              in a reviewer-owned config, it has no default, and the number
              plus its config version is named in every sentence that uses it.

The measure itself stays unbanded. Stage 4's refusal was about banding inside
the scoring, and that still holds: buffer_cover returns raw Fraction days. What
happens here is a reviewer's filter applied to an unbanded measure, which is a
different act with a different owner.

THE CEILING SITS ON THE CATALOGUE, NOT ON EACH MEMBERSHIP. Deciding that a
conjunction is a pattern worth naming is a modelling judgment, exactly like
choosing a grouping definition, so it carries the same permanent `recommends`.
But it is ONE judgment reused across every part, so confirming it per part would
be three hundred confirmations of a single decision, which makes review worse
rather than stronger. Membership in a structural archetype is therefore
`executes`: a conjunction of facts each computed at `executes` is a fact, and it
asserts nothing beyond its conjuncts. The ceiling belongs where the judgment is.
"""
import pathlib
from dataclasses import dataclass, field

from . import governance as gov
from . import scoring
from .synthetic import verdicts as V

# ------------------------------------------------------ three-valued logic --
# Kleene. A part with an abstention on a condition an archetype needs can
# neither match nor be excluded honestly, so membership has three values and
# not two.
TRUE = "true"
FALSE = "false"
UNKNOWN = "unknown"
TRUTH_VALUES = (TRUE, FALSE, UNKNOWN)

MATCHED = "matched"
EXCLUDED = "excluded"
CANNOT_TELL = "cannot_tell"
MEMBERSHIPS = (MATCHED, EXCLUDED, CANNOT_TELL)


def conjoin(values):
    """Kleene AND.

    THE SECOND BRANCH IS THE LOAD-BEARING ONE: a definitely false condition
    excludes the part even while another condition is unknown. Without it every
    part carrying any abstention would fall into "cannot tell", the bucket would
    swallow the dataset, and the one genuinely useful thing about it, that its
    members are exactly the parts a missing field could still move, would be
    lost.
    """
    values = tuple(values)
    if any(value == FALSE for value in values):
        return FALSE
    if all(value == TRUE for value in values):
        return TRUE
    return UNKNOWN


def membership(values):
    return {TRUE: MATCHED, FALSE: EXCLUDED, UNKNOWN: CANNOT_TELL}[
        conjoin(values)]


# ------------------------------------------------------------- conditions --
STRUCTURAL = "structural"
MAGNITUDE = "magnitude"


@dataclass(frozen=True)
class Condition:
    """One testable clause, with the field it depends on named.

    `depends_on` is what makes the work queue possible: when a condition
    evaluates to UNKNOWN, this is the field somebody would have to go and fetch.
    """
    name: str
    kind: str
    depends_on: str
    describe: str
    test: object = None

    def evaluate(self, context):
        return self.test(context)


def _verdict_in(*verdicts):
    return lambda context: TRUE if context["verdict"] in verdicts else FALSE


def _score(context, dimension):
    return getattr(context["profile"], dimension, None)


def _tooling_is_supplier(context):
    score = _score(context, "portability")
    if score is None or score.completeness == scoring.CANNOT_TELL:
        return UNKNOWN
    return TRUE if score.value == scoring.TOOLING_SUPPLIER else FALSE


def _cover_is_zero(context):
    """Counted and empty. A STRUCTURAL fact, not a band.

    `on_hand = 0` gives `cover = 0` by arithmetic, with no threshold deciding
    what "thin" means. This is the structural stand-in for thin cover and it is
    the reason a useful archetype exists before anybody configures a number.
    """
    score = _score(context, "buffer_cover")
    if score is None or score.completeness == scoring.CANNOT_TELL:
        return UNKNOWN
    if score.value is scoring.UNBOUNDED:
        return FALSE
    return TRUE if score.value == 0 else FALSE


def _is_correlated(context):
    score = _score(context, "concentration")
    if score is None or score.completeness == scoring.CANNOT_TELL:
        return UNKNOWN
    if score.completeness == scoring.NOT_APPLICABLE:
        return FALSE
    return TRUE if score.agreement and score.agreement != "neither" else FALSE


SINGLE_SOURCE = Condition(
    name="single_source", kind=STRUCTURAL, depends_on="verdict",
    describe="one qualified supplier",
    test=_verdict_in(V.SINGLE_SOURCE, V.SINGLE_SOURCE_NO_LEAD_TIME,
                     V.HIDDEN_SINGLE_SOURCE))

NO_QUOTABLE_SOURCE = Condition(
    name="no_quotable_source", kind=STRUCTURAL, depends_on="verdict",
    describe="no supplier on file can quote a lead time",
    test=_verdict_in(V.SINGLE_SOURCE_NO_LEAD_TIME,
                     V.MULTI_SOURCE_NO_LEAD_TIMES))

NOBODY_QUALIFIED = Condition(
    name="nobody_qualified", kind=STRUCTURAL, depends_on="verdict",
    describe="the supplier list was checked and is empty",
    test=_verdict_in(V.NO_QUALIFIED_SUPPLIER))

SUPPLIER_TOOLING = Condition(
    name="supplier_tooling", kind=STRUCTURAL, depends_on="tooling_owner",
    describe="the supplier owns the tooling",
    test=_tooling_is_supplier)

COUNTED_EMPTY = Condition(
    name="counted_empty", kind=STRUCTURAL, depends_on="on_hand_units",
    describe="on-hand was counted and is zero",
    test=_cover_is_zero)

CORRELATED = Condition(
    name="correlated", kind=STRUCTURAL, depends_on="concentration",
    describe="its exposure is correlated with other parts",
    test=_is_correlated)


# ------------------------------------------------- magnitude conditions ----
# Built only when a reviewer supplies a threshold. See `catalogue()`.

def _lead_time_at_least(days):
    def test(context):
        score = _score(context, "lead_time_to_recover")
        if score is None:
            return UNKNOWN
        if score.completeness == scoring.NO_RECOVERY_PATH:
            # There is no path at all, so no wait is long enough. Definitely
            # true rather than unknown.
            return TRUE
        if score.completeness == scoring.NOT_APPLICABLE:
            return FALSE          # made in-house: no purchase lead time exists
        if score.completeness == scoring.CANNOT_TELL:
            return UNKNOWN
        return TRUE if score.detail["quoted_days"] >= days else FALSE
    return test


def _cover_at_most(days):
    def test(context):
        """A BOUND ANSWERS DEFINITELY IN ONE DIRECTION AND NOT THE OTHER.

        Cover on partial demand is an UPPER bound: the true cover is at most the
        figure carried. So if that figure is already at or below the threshold,
        the true value is too and the answer is definitely TRUE. If it is above,
        the true value could be either side and the honest answer is UNKNOWN.
        This is where carrying the bound DIRECTION since stage 4 pays out; a
        plain "incomplete" flag could not tell these apart.
        """
        score = _score(context, "buffer_cover")
        if score is None or score.completeness == scoring.CANNOT_TELL:
            return UNKNOWN
        if score.value is scoring.UNBOUNDED:
            return FALSE
        if score.completeness == scoring.UPPER_BOUND:
            return TRUE if score.value <= days else UNKNOWN
        return TRUE if score.value <= days else FALSE
    return test


def _blocks_at_least(units):
    def test(context):
        """Blast radius is a LOWER bound, so the definite direction inverts."""
        score = _score(context, "blast_radius")
        if score is None:
            return UNKNOWN
        if score.completeness == scoring.LOWER_BOUND:
            return TRUE if score.value >= units else UNKNOWN
        return TRUE if score.value >= units else FALSE
    return test


# ------------------------------------------------------------- archetypes --

@dataclass(frozen=True)
class Archetype:
    """A named conjunction. No weights, no score, no severity number."""
    name: str
    label: str
    conditions: tuple
    threshold_source: str = ""

    @property
    def kind(self):
        return (MAGNITUDE
                if any(c.kind == MAGNITUDE for c in self.conditions)
                else STRUCTURAL)

    @property
    def condition_names(self):
        return frozenset(c.name for c in self.conditions)

    @property
    def autonomy(self):
        """Membership autonomy, which is not the catalogue's autonomy.

        Structural membership EXECUTES: a conjunction of facts each computed at
        `executes` is a fact. Magnitude membership RECOMMENDS: the threshold is
        a live judgment and different reviewers set it differently. A
        conjunction that touches concentration inherits stage 5's ceiling,
        because a conjunct that may not be claimed alone may not be claimed
        inside a conjunction either.
        """
        if self.kind == MAGNITUDE:
            return gov.RECOMMENDS
        if any(c.depends_on == "concentration" for c in self.conditions):
            return gov.RECOMMENDS
        return gov.EXECUTES

    def evaluate(self, context):
        return {c.name: c.evaluate(context) for c in self.conditions}


# THE CATALOGUE'S OWN AUTONOMY. Which conjunctions are worth naming is a
# modelling judgment and carries the same permanent ceiling as grouping. It is
# confirmed ONCE, not once per part.
CATALOGUE_AUTONOMY = gov.RECOMMENDS

RESOURCING_TRAP = Archetype(
    name="resourcing_trap", label="the resourcing trap",
    conditions=(SINGLE_SOURCE, SUPPLIER_TOOLING))

NOBODY_TO_CALL = Archetype(
    name="nobody_to_call", label="nobody to call",
    conditions=(NOBODY_QUALIFIED,))

NO_QUOTABLE_SINGLE_SOURCE = Archetype(
    name="no_quotable_single_source", label="single source, nobody quoting",
    conditions=(SINGLE_SOURCE, NO_QUOTABLE_SOURCE))

COUNTED_EMPTY_SINGLE_SOURCE = Archetype(
    name="counted_empty_single_source", label="single source, counted empty",
    conditions=(SINGLE_SOURCE, COUNTED_EMPTY))

CORRELATED_RESOURCING_TRAP = Archetype(
    name="correlated_resourcing_trap", label="the correlated resourcing trap",
    conditions=(SINGLE_SOURCE, SUPPLIER_TOOLING, CORRELATED))

STRUCTURAL_CATALOGUE = (
    RESOURCING_TRAP,
    NOBODY_TO_CALL,
    NO_QUOTABLE_SINGLE_SOURCE,
    COUNTED_EMPTY_SINGLE_SOURCE,
    CORRELATED_RESOURCING_TRAP,
)


def magnitude_catalogue(thresholds):
    """Built ONLY from a reviewer's numbers. No defaults anywhere.

    With no config supplied this returns nothing, and the system ships able to
    name the resourcing trap and unable to say "long lead" until somebody states
    what long means. That is the intended out-of-the-box behaviour, not a gap.
    """
    if not thresholds:
        return ()
    version = thresholds.get("version", "unversioned")
    lead_days = thresholds.get("long_lead_days")
    cover_days = thresholds.get("thin_cover_days")
    built = []
    if lead_days is not None and cover_days is not None:
        built.append(Archetype(
            name="headline_exposure",
            label="single source, long lead, thin cover, supplier tooling",
            threshold_source=f"archetypes.yaml {version}",
            conditions=(
                SINGLE_SOURCE,
                Condition(name="long_lead", kind=MAGNITUDE,
                          depends_on="lead_time_to_recover",
                          describe=(f"quoted lead time is {lead_days} days or "
                                    f"more, a threshold set in archetypes.yaml "
                                    f"{version}"),
                          test=_lead_time_at_least(lead_days)),
                Condition(name="thin_cover", kind=MAGNITUDE,
                          depends_on="on_hand_units",
                          describe=(f"cover is {cover_days} days or less, a "
                                    f"threshold set in archetypes.yaml "
                                    f"{version}"),
                          test=_cover_at_most(cover_days)),
                SUPPLIER_TOOLING)))
    if lead_days is not None:
        built.append(Archetype(
            name="long_lead_single_source",
            label="single source on a long lead time",
            threshold_source=f"archetypes.yaml {version}",
            conditions=(
                SINGLE_SOURCE,
                Condition(name="long_lead", kind=MAGNITUDE,
                          depends_on="lead_time_to_recover",
                          describe=(f"quoted lead time is {lead_days} days or "
                                    f"more, a threshold set in archetypes.yaml "
                                    f"{version}"),
                          test=_lead_time_at_least(lead_days)))))
    return tuple(built)


def load_thresholds(path):
    """Read reviewer-owned thresholds. Absent or empty means DISABLED.

    Returns None when the file is missing, unreadable, or has every threshold
    commented out. There is deliberately no fallback set of numbers: a default
    threshold is a judgment the system made on a reviewer's behalf and then
    attributed to nobody.
    """
    import yaml

    path = pathlib.Path(path)
    if not path.exists():
        return None
    loaded = yaml.safe_load(path.read_text()) or {}
    thresholds = loaded.get("thresholds") or {}
    if not any(value is not None for value in thresholds.values()):
        return None
    return {"version": loaded.get("version", "unversioned"), **thresholds}


def catalogue(thresholds=None):
    """Structural archetypes always; magnitude archetypes only if configured."""
    return STRUCTURAL_CATALOGUE + magnitude_catalogue(thresholds)


def dominates(one, other):
    """Subset inclusion, and NOTHING ELSE.

    One archetype dominates another when its conditions are a strict superset:
    everything the weaker one asserts, plus more. That is a partial order that
    needs no weights, no common unit and no normalisation, which is exactly why
    it is the only cross-archetype ordering permitted here.

    Many pairs are incomparable, and that is a finding rather than a gap. A
    total order over archetypes could only be produced by scoring them.
    """
    return one.condition_names > other.condition_names


def dominance_layers(archetypes):
    """Group archetypes into tiers of the partial order.

    Archetypes in the same tier are INCOMPARABLE and a display should place them
    side by side rather than stacked, so the layout itself declines to imply an
    order that does not exist. Within a tier the sequence is by name: arbitrary,
    and stable so that it cannot quietly acquire meaning.
    """
    remaining = list(archetypes)
    layers = []
    while remaining:
        top = [a for a in remaining
               if not any(dominates(other, a) for other in remaining
                          if other is not a)]
        if not top:                                    # pragma: no cover
            top = list(remaining)
        layers.append(tuple(sorted(top, key=lambda a: a.name)))
        remaining = [a for a in remaining if a not in top]
    return tuple(layers)
