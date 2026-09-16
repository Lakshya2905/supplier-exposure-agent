"""The supplier as the row, for TRIAGE, and never as a score.

WHY THIS EXISTS. Every commercial tool in this market makes the supplier the
primary object and this one makes the part. That is the right primary object for
the question it answers -- which single points of failure would stop production
-- and it leaves a real gap: a buyer who owns a supplier relationship cannot ask
"what do I carry with this one" without reading three hundred part rows.

THE BRIEF PERMITS THIS AND CONSTRAINS IT, in the same sentence: portfolio-level
ranking across suppliers may be a composite because its job is triage, part-level
scoring stays uncombined because its job is deciding what to do. This module
takes the permission and declines the composite anyway, because it does not need
one: both axes are COUNTS OF PARTS, so they share a unit and nothing has to be
blended to put them side by side.

  how much of the build depends on this supplier    parts_supplied
  how exposed that dependence is                    exposed_parts

They are never multiplied, never summed, and never folded into a rank. The
ordering names the single axis it sorted on, exactly as `ranking.rank_by` does.

THE DISTINCTION THIS MODULE MUST NOT LOSE, and it is the reason to read the
autonomy note below before changing anything here. Grouping parts by supplier to
claim they are CORRELATED is a modelling judgment -- same supplier, same region
and same tier are three definitions that disagree -- and `concentration.py` is
`recommends` permanently because of it. This module makes no such claim. It
reads the supplier field and counts what is in it. "These fourteen parts name
Braxton Industries" is a fact about the data; "these fourteen parts are
correlated exposure" is a judgment, it lives in Review, and it is not made here.
A future edit that starts inferring shared exposure from these counts has moved
this module across that line and must take the decision ceiling with it.

AN UNSETTLED PART IS NOT AN UNEXPOSED ONE. A supplier whose parts are mostly
unsettled would sort to the bottom on a naive count and read as safe, which is
the imputation this project refuses everywhere else. So `exposed_parts` is a
LOWER BOUND wherever any part on that supplier could not be settled, the count
of unsettled parts is carried beside it, and the bound is stated rather than
implied by a smaller number.
"""
from dataclasses import dataclass

from . import governance as gov
from .synthetic import verdicts as V

# Verdicts that mean "one real source". Read from the verdict vocabulary rather
# than re-listed as strings: a verdict added to that module and not to this set
# should be a decision somebody makes, and `test_portfolio.py` fails until they
# make it.
EXPOSED_VERDICTS = frozenset({
    V.SINGLE_SOURCE,
    V.SINGLE_SOURCE_NO_LEAD_TIME,
    V.HIDDEN_SINGLE_SOURCE,
    V.NO_QUALIFIED_SUPPLIER,
})

# Verdicts where the reading did not settle, so the part is neither exposed nor
# cleared. Counted separately and never folded into either axis.
UNSETTLED_VERDICTS = frozenset({
    V.SUPPLIER_LIST_UNKNOWN,
    V.READINGS_DISAGREE,
})

# Neither exposed nor unsettled: the reading landed and found more than one
# real source, or the part is not bought at all. Listed EXPLICITLY rather than
# derived as "everything else", so the three sets partition the vocabulary and
# a verdict added to `verdicts.py` fails `test_portfolio.py` until somebody
# decides which of the three it is. "Everything else" would silently classify
# a new verdict as safe, which is the direction that costs.
NOT_EXPOSED_VERDICTS = frozenset({
    V.MADE_IN_HOUSE,
    V.MULTI_SOURCE,
    V.MULTI_SOURCE_NO_LEAD_TIMES,
})

BY_EXPOSED_PARTS = "exposed_parts"


@dataclass(frozen=True)
class SupplierRow:
    """One supplier, two counts, and what neither count could settle."""
    supplier: str
    parts_supplied: int
    exposed_parts: int
    #: True when some part on this supplier could not be settled, so the count
    #: above can only rise. Never a smaller number presented as a smaller risk.
    exposed_is_lower_bound: bool
    parts_unsettled: int
    regions: tuple
    #: The parts themselves, so the row drills through rather than summarising.
    #: The brief requires it: a supplier view that cannot reach part detail is
    #: the index this product exists to refuse, one level up.
    part_numbers: tuple
    exposed_part_numbers: tuple

    @property
    def autonomy(self):
        """EXECUTES, and the reason is what this row does NOT claim.

        It is a count of a field that was read, not an assertion that the parts
        under it share a fate. The correlation judgment is `concentration`'s and
        keeps its permanent ceiling there.
        """
        return gov.EXECUTES


def by_supplier(supplier_rows, verdicts):
    """One row per supplier named anywhere in the evidence.

    `supplier_rows` is (part, supplier, region) as the evidence read them, which
    is the same tuple the incidence matrix is built from, so the two surfaces
    cannot disagree about who supplies what.

    ORDERED BY ONE NAMED AXIS, exposed parts descending, then by parts supplied,
    then by name. The first key is the question this view is asked; the last two
    exist so the order is TOTAL and therefore stable, because a tie broken by
    dict iteration is arbitrary today and meaningful the day an upstream
    function changes how it iterates.
    """
    parts_by_supplier, regions_by_supplier = {}, {}
    for part, supplier, region in supplier_rows:
        parts_by_supplier.setdefault(supplier, set()).add(part)
        if region:
            regions_by_supplier.setdefault(supplier, set()).add(region)

    rows = []
    for supplier, parts in parts_by_supplier.items():
        exposed = {p for p in parts if verdicts.get(p) in EXPOSED_VERDICTS}
        unsettled = {p for p in parts if verdicts.get(p) in UNSETTLED_VERDICTS
                     or p not in verdicts}
        rows.append(SupplierRow(
            supplier=supplier,
            parts_supplied=len(parts),
            exposed_parts=len(exposed),
            exposed_is_lower_bound=bool(unsettled),
            parts_unsettled=len(unsettled),
            regions=tuple(sorted(regions_by_supplier.get(supplier, ()))),
            part_numbers=tuple(sorted(parts)),
            exposed_part_numbers=tuple(sorted(exposed)),
        ))
    return tuple(sorted(
        rows, key=lambda r: (-r.exposed_parts, -r.parts_supplied, r.supplier)))


def order_label():
    """What the default order sorted on, for the caption.

    A plausible default order is read as a ranking, so the surface states its
    key rather than leaving a reader to infer one. This returns the sentence
    rather than the key, because the key is `exposed_parts` and that is the
    thing a reader should not have to translate.
    """
    return ("Ordered by how many of a supplier's parts have one real source. "
            "That is one axis sorted, not a rank: a supplier carrying more of "
            "the build is not thereby safer, and the two counts are never "
            "combined.")
