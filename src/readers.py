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
from pathlib import Path

import pandas as pd

from .recovery import INPUT_FIELDS as RECOVERY_INPUT_FIELDS
from .criticality import CRITICALITY_COLUMN as CRITICALITY
from .commitments import COMMITTED_UNITS
from .subtier import SUB_TIER_SOURCE
from .synthetic.model import (ANNUAL_UNITS, CHILD_PART, FINISHED_GOOD_PART,
                              LEAD_TIME_P95_DAYS, ON_HAND_UNITS, PARENT_PART,
                              PART_NUMBER, QTY_PER_PARENT,
                              QUOTED_LEAD_TIME_DAYS, RETRIEVED_AT, SOURCE_FILE,
                              SOURCE_TYPE, SOURCING_LIST_STATUS, SUPPLIER_NAME,
                              SUPPLIER_REGION, SYSTEM_OF_RECORD, TOOLING_OWNER)


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
    """part_number -> dict, with on_hand_units as int or None.

    `criticality` IS OPTIONAL AND ITS ABSENCE IS NOT AN ERROR. A part master
    that predates the column reads as every part unclassified, which keeps every
    part in scope: see `criticality.py` for why the inclusive default is the
    only honest one. Read with `.get` on the row rather than by indexing,
    because pandas raises on a column that is not there and a dataset assembled
    before a feature existed is not a malformed dataset.
    """
    frame = _frame(path)
    has_criticality = CRITICALITY in frame.columns
    parts = {}
    for _, row in frame.iterrows():
        parts[row[PART_NUMBER]] = {
            "source_type": row[SOURCE_TYPE].strip(),
            "sourcing_list_status": row[SOURCING_LIST_STATUS].strip(),
            "on_hand_units": optional_int(row[ON_HAND_UNITS]),
            "tooling_owner": row[TOOLING_OWNER].strip(),
            "criticality": row[CRITICALITY].strip() if has_criticality else "",
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


def read_suppliers(path):
    """part_number -> ((supplier_name, supplier_region, row), ...), as spelled.

    `row` is the 1-based data row, counting from the first line after the
    header. IT IS CARRIED, NOT JOINED BACK TO LATER. A part has many supplier
    rows and the name is not unique across them, so recovering "which row said
    this" from a name would be a lookup that can quietly return the wrong one.
    Attaching it here, before the sort below reorders everything, makes the
    locator an identity.
    """
    frame = _frame(path)
    rows = {}
    for position, (_, row) in enumerate(frame.iterrows(), start=1):
        rows.setdefault(row[PART_NUMBER], []).append(
            (row[SUPPLIER_NAME], row[SUPPLIER_REGION], position))
    return {part: tuple(sorted(entries)) for part, entries in rows.items()}


def read_lead_times(path):
    """part_number -> ((supplier_name, quoted, p95, row), ...), as spelled.

    Keyed by the name in THIS file, which may differ from the spelling in
    suppliers.csv. Reconciling them is the normaliser's job, not the reader's.
    `row` as in `read_suppliers`, and carried for the same reason.
    """
    frame = _frame(path)
    rows = {}
    for position, (_, row) in enumerate(frame.iterrows(), start=1):
        rows.setdefault(row[PART_NUMBER], []).append(
            (row[SUPPLIER_NAME], int(row[QUOTED_LEAD_TIME_DAYS]),
             int(row[LEAD_TIME_P95_DAYS]), position))
    return {part: tuple(sorted(entries)) for part, entries in rows.items()}


def read_demand_rows(path):
    """finished_good -> the 1-based data row it was read from.

    A SECOND READ RATHER THAN A WIDER RETURN, and the difference from the two
    readers above is not laziness. The key here is the dict key both this
    function and `read_demand_plan` build, so a duplicated finished good
    collapses the same way in both and they cannot disagree about which row
    won. Suppliers and lead times have many rows per part keyed by a name that
    repeats, so no such argument is available there and the row rides on the
    record instead.
    """
    frame = _frame(path)
    return {row[FINISHED_GOOD_PART]: position
            for position, (_, row) in enumerate(frame.iterrows(), start=1)}


def read_sources(path):
    """source_file -> (system_of_record, retrieved_at).

    The extract manifest. It is the only input that describes the others, and
    it is what lets an evidence record say WHEN the value it cites was pulled
    and out of what, instead of the interface inventing a provenance for a
    number at render time.
    """
    frame = _frame(path)
    return {row[SOURCE_FILE]: (row[SYSTEM_OF_RECORD].strip(),
                               row[RETRIEVED_AT].strip())
            for _, row in frame.iterrows()}


def read_recovery_inputs(path):
    """part_number -> {stage field: days or cycles}. OPTIONAL, and often absent.

    THE FILE IS ALLOWED NOT TO EXIST, and its absence is a fact rather than an
    error: no dataset this repository generates carries resourcing durations,
    because a qualification duration is a judgment and a generator that emitted
    one would be inventing the very input the tool is supposed to report it
    lacks. A missing file returns an empty mapping, and every part then reports
    `resource_days` as cannot-tell, naming the stages nobody has timed.

    COLUMNS ARE OPTIONAL TOO, one at a time. A file carrying only
    `tooling_lead_time_days` is valid and times one stage. That tolerance is
    what keeps the frozen eval inputs readable: they predate this file, and a
    reader that demanded the new columns would make the frozen set unreadable
    rather than incomplete.

    Blank means NO RECORD and is dropped, so the stage reads untimed. A recorded
    `0` is kept, exactly as `on_hand_units` keeps a counted zero: a stage
    somebody timed at zero days is a measurement, and an unfilled cell is not.
    """
    path = Path(path)
    if not path.exists():
        return {}
    frame = _frame(path)
    fields = [field for field in RECOVERY_INPUT_FIELDS if field in frame.columns]
    rows = {}
    for _, row in frame.iterrows():
        values = {field: optional_int(row[field]) for field in fields}
        rows[row[PART_NUMBER]] = {field: value for field, value in values.items()
                                  if value is not None}
    return rows


def read_commitments(path):
    """finished_good -> units already promised to a customer. OPTIONAL.

    RETURNS None WHEN THE FILE IS ABSENT, not an empty dict, and the difference
    is the whole contract. An empty dict means "there is an order book and this
    finished good is not in it"; None means "nobody supplied an order book".
    `committed_at_risk` abstains differently for the two, and collapsing them
    here would make a part with no promised orders look identical to a company
    that has not told us about any.

    A finished good absent from a file that DOES exist is unrecorded rather than
    zero, so the total it feeds is a lower bound. Same direction as blast
    radius, same reason: the uncertain quantity is in the numerator.
    """
    path = Path(path)
    if not path.exists():
        return None
    frame = _frame(path)
    if COMMITTED_UNITS not in frame.columns:
        return None
    return {row[FINISHED_GOOD_PART]: int(row[COMMITTED_UNITS])
            for _, row in frame.iterrows()
            if row[COMMITTED_UNITS].strip()}


def read_sub_tier_sources(path):
    """supplier_name -> where that supplier sources the critical input.

    OPTIONAL, LIKE `recovery_inputs.csv`, and absent from every dataset this
    repository generates. Roughly 95% of companies can see their own suppliers
    and fewer than half can see one level below, so a tool that required this
    would be unusable by most of the people it is for; one that refuses to model
    it at all cannot see the correlation that matters most, where two suppliers
    are the same supplier one hop down.

    ONE HOP, and the file shape says so: a supplier and a place, with no column
    for where that place buys. `tests/test_concentration.py` carries the gap
    that leaves open.

    A blank cell is dropped rather than kept as an empty source. Two suppliers
    who have both declined to say are not thereby buying from the same place,
    and a group built out of that absence would be a correlation manufactured
    from a gap and then presented to somebody for confirmation.
    """
    path = Path(path)
    if not path.exists():
        return {}
    frame = _frame(path)
    if SUB_TIER_SOURCE not in frame.columns:
        return {}
    rows = {}
    for _, row in frame.iterrows():
        source = row[SUB_TIER_SOURCE].strip()
        if source:
            rows[row[SUPPLIER_NAME].strip()] = source
    return rows


def read_bom(path):
    frame = _frame(path)
    return [(row[PARENT_PART], row[CHILD_PART], int(row[QTY_PER_PARENT]))
            for _, row in frame.iterrows()]
