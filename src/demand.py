"""Annual usage: the demand-plan join, and the completeness it carries.

This is the function stage 2's `rollup` would have become if it had been allowed
to exist. Summing `qty_per_finished_good` across finished goods produces an
unlabelled scalar with no unit; multiplying by the demand plan first produces
units per year, which is a real measure that can be divided into on-hand to give
a duration. The demand plan is what supplies the unit, which is why the join
lives here and not in explosion.

PARTIAL NAMES NO DIRECTION, AND THAT IS DELIBERATE. A finished good absent from
the demand plan means the usage computed here is incomplete, but which way it is
wrong depends on where the number lands:

    buffer cover      usage sits in the DENOMINATOR. Unrecorded demand can only
                      reduce cover, so cover is an UPPER bound.
    blast radius      blocked units sit in the NUMERATOR. Unrecorded demand can
                      only add, so blocked units are a LOWER bound.

Same missing row, opposite directions, so the direction belongs to the consumer.
Encoding it here would hard-code one consumer's perspective into a function two
consumers share, and the second one would silently read its bound backwards.
"""
from dataclasses import dataclass, field
from fractions import Fraction

# Completeness of the join itself. The scoring dimensions translate these into
# their own bound directions; see the module docstring.
USAGE_KNOWN = "known"
USAGE_PARTIAL = "partial"
USAGE_CANNOT_TELL = "cannot_tell"


@dataclass(frozen=True)
class Usage:
    """Annual usage of one part, with what the demand plan could not tell us.

    `value` is exact. Quantities are Fraction and demand is int, so the product
    and the sum are both exact, and nothing here rounds. Rounding happens at
    render only, so a three-level explosion cannot accumulate drift.
    """
    part_number: str
    value: Fraction
    completeness: str
    recorded_finished_goods: tuple = ()
    absent_finished_goods: tuple = ()
    blocked_finished_good_units: int = 0
    reasons: tuple = field(default_factory=tuple)

    @property
    def is_partial(self):
        return self.completeness == USAGE_PARTIAL


def annual_usage(rows, demand_plan):
    """Usage for ONE part, from its exploded rows and the demand plan.

    `rows` are the ExplodedPart rows for a single part, one per finished good
    that contains it. `demand_plan` maps finished_good -> annual_units.

      every blocking finished good is in the plan   -> known
      some are, some are not                        -> partial
      none are                                      -> cannot tell

    A part fed only by the demand-absent finished good is the full abstention:
    there is no known demand to compute a bound from, so there is no bound.
    """
    rows = tuple(rows)
    if not rows:
        raise ValueError("annual_usage needs at least one exploded row; a part "
                         "with no rows never reached a finished good, which "
                         "stage 2 already refuses to produce")

    part_number = rows[0].part_number
    if any(row.part_number != part_number for row in rows):
        raise ValueError("annual_usage takes the rows for ONE part; mixing "
                         "parts would sum quantities of different things")

    recorded = tuple(sorted(row.finished_good for row in rows
                            if row.finished_good in demand_plan))
    absent = tuple(sorted(row.finished_good for row in rows
                          if row.finished_good not in demand_plan))

    value = sum((row.qty_per_finished_good * demand_plan[row.finished_good]
                 for row in rows if row.finished_good in demand_plan),
                Fraction(0))
    blocked = sum(demand_plan[fg] for fg in recorded)

    if not recorded:
        completeness = USAGE_CANNOT_TELL
        reasons = (f"every finished good containing this part is absent from "
                   f"the demand plan ({', '.join(absent)}), so there is no "
                   f"known demand to compute a bound from",)
    elif absent:
        completeness = USAGE_PARTIAL
        reasons = (f"computed on {len(recorded)} of {len(rows)} finished goods; "
                   f"{', '.join(absent)} is absent from the demand plan",)
    else:
        completeness = USAGE_KNOWN
        reasons = (f"every finished good containing this part is in the demand "
                   f"plan ({', '.join(recorded)})",)

    return Usage(part_number=part_number, value=value,
                 completeness=completeness, recorded_finished_goods=recorded,
                 absent_finished_goods=absent,
                 blocked_finished_good_units=blocked, reasons=reasons)


def usage_by_part(rows_by_part, demand_plan):
    return {part: annual_usage(rows, demand_plan)
            for part, rows in rows_by_part.items()}
