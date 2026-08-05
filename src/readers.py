"""CSV readers. The one place null encoding is decoded.

THIS IS WHERE MISSING-VERSUS-ZERO IS WON OR LOST. A blank `on_hand_units` means
no record and a `0` means counted and empty, and those are different findings:
one is a gap in a spreadsheet, the other is the worst cover in the dataset. The
collapse is not usually a decision anybody makes, it is a default: pandas reads
an integer column containing a blank as float64, so `0` becomes `0.0` and the
blank becomes `NaN`, and the first `int(x or 0)` downstream makes them identical
forever.

So every column is read as a STRING with `keep_default_na=False`, and converted
explicitly below. Nothing is inferred.

`keep_default_na=False` also fixes the second trap in the same stroke: a
`supplier_region` of `NA` is North America, and pandas reads it as NaN by
default, which would silently delete a region from stage 5's concentration
analysis.
"""
import pandas as pd

from .synthetic.model import (ANNUAL_UNITS, CHILD_PART, FINISHED_GOOD_PART,
                              ON_HAND_UNITS, PARENT_PART, PART_NUMBER,
                              QTY_PER_PARENT, SOURCE_TYPE,
                              SOURCING_LIST_STATUS, TOOLING_OWNER)


def _frame(path):
    """Every column a string, nothing inferred, `NA` left alone."""
    return pd.read_csv(path, comment="#", dtype=str, keep_default_na=False)


def optional_int(text):
    """Blank means NO RECORD and returns None. `0` means zero and returns 0.

    Deliberately not `int(text or 0)`. That expression is the bug this whole
    module exists to prevent, and it is one character away from correct.
    """
    text = (text or "").strip()
    return None if text == "" else int(text)


def read_part_master(path):
    """part_number -> dict, with on_hand_units as int or None."""
    frame = _frame(path)
    parts = {}
    for _, row in frame.iterrows():
        parts[row[PART_NUMBER]] = {
            "source_type": row[SOURCE_TYPE].strip(),
            "sourcing_list_status": row[SOURCING_LIST_STATUS].strip(),
            "on_hand_units": optional_int(row[ON_HAND_UNITS]),
            "tooling_owner": row[TOOLING_OWNER].strip(),
        }
    return parts


def read_demand_plan(path):
    """finished_good -> annual_units.

    A finished good ABSENT from this mapping is absent from the plan, and that
    absence is load-bearing: it is what makes usage partial. So absence is
    represented by the key not existing, never by a zero, because a recorded
    zero is a real demand figure that this system has to score differently.
    """
    frame = _frame(path)
    return {row[FINISHED_GOOD_PART]: int(row[ANNUAL_UNITS])
            for _, row in frame.iterrows()}


def read_bom(path):
    frame = _frame(path)
    return [(row[PARENT_PART], row[CHILD_PART], int(row[QTY_PER_PARENT]))
            for _, row in frame.iterrows()]
