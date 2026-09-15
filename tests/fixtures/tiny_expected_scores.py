"""Hand-written expectations for tiny_scoring_bom.csv.

A SINGLE STATEMENT OF EXPECTED VALUES, written by hand from the tree and the
demand plan, never produced by running the code under test. The arithmetic is
laid out in the comment block at the top of tiny_scoring_bom.csv so a reader can
re-derive every figure here without executing anything.

Fractions are exact and stay exact. `Fraction(73, 2)` is 36.5 days of cover, and
writing it as a float would need a tolerance, at which point the fixture stops
being an oracle and starts being an approximation of one.
"""
from fractions import Fraction

# part -> annual usage, in units of that part per year
EXPECTED_USAGE = {
    "SHARED-M01": Fraction(3500),    # 2 x 1000 + 3 x 500, FG-M03 not counted
    "ONLY-M01": Fraction(1000),      # 1 x 1000
    "ONLY-M02": Fraction(500),       # 1 x 500
    "MISSING-M01": Fraction(1000),   # 1 x 1000
    "ORPHAN-M01": Fraction(0),       # nothing recorded to sum
    "ZEROUSE-M01": Fraction(0),      # 1 x 0, and the zero is recorded
}

# part -> completeness of the demand join
EXPECTED_USAGE_COMPLETENESS = {
    "SHARED-M01": "partial",
    "ONLY-M01": "known",
    "ONLY-M02": "known",
    "MISSING-M01": "known",
    "ORPHAN-M01": "cannot_tell",
    "ZEROUSE-M01": "known",
}

# part -> finished-good units blocked, counting recorded finished goods only
EXPECTED_BLOCKED_UNITS = {
    "SHARED-M01": 1500,   # 1000 + 500
    "ONLY-M01": 1000,
    "ONLY-M02": 500,
    "MISSING-M01": 1000,
    "ORPHAN-M01": 0,
    "ZEROUSE-M01": 0,
}

# part -> how many finished goods stop, STRUCTURAL and therefore always known
EXPECTED_FINISHED_GOODS_BLOCKED = {
    "SHARED-M01": 3,      # FG-M01, FG-M02 and FG-M03; the absent one still stops
    "ONLY-M01": 1,
    "ONLY-M02": 1,
    "MISSING-M01": 1,
    "ORPHAN-M01": 1,      # known even though its volume is not
    "ZEROUSE-M01": 1,
}

EXPECTED_BLAST_RADIUS_COMPLETENESS = {
    "SHARED-M01": "lower_bound",   # unrecorded demand can only ADD to this
    "ONLY-M01": "known",
    "ONLY-M02": "known",
    "MISSING-M01": "known",
    "ORPHAN-M01": "lower_bound",
    "ZEROUSE-M01": "known",
}

# part -> cover in days. None where there is no value, and the completeness map
# below says whether that None is an abstention or an unbounded answer.
EXPECTED_COVER_DAYS = {
    "SHARED-M01": Fraction(73),       # 700 x 365 / 3500
    "ONLY-M01": Fraction(73, 2),      # 100 x 365 / 1000 = 36.5 exactly
    "ONLY-M02": Fraction(0),          # counted and empty: an answer
    "MISSING-M01": None,              # no record: not an answer
    "ORPHAN-M01": None,
    # The string is a MARKER, not a value. This fixture imports nothing from
    # src, so it cannot name the sentinel; the test maps the marker across.
    "ZEROUSE-M01": "unbounded",
}

EXPECTED_COVER_COMPLETENESS = {
    "SHARED-M01": "upper_bound",   # unrecorded demand can only REDUCE this
    "ONLY-M01": "known",
    "ONLY-M02": "known",           # zero cover is settled, and it executes
    "MISSING-M01": "cannot_tell",
    "ORPHAN-M01": "cannot_tell",
    "ZEROUSE-M01": "known",        # unbounded is settled too
}

# part -> first-pass resourcing chain total in days, hand-summed in the comment
# block at the top of tiny_recovery.csv. None where nothing is timed, which is
# an abstention rather than a total of zero.
EXPECTED_RESOURCE_DAYS = {
    "SHARED-M01": 300,      # 45 + 120 + 30 + 20 + 60 + 25
    "ONLY-M01": 80,         # 35 + 20 + 10 + 15, tooling off the path
    "ONLY-M02": 100,        # 25 + 10 + 5 + 50 + 10, tooling off the path
    "MISSING-M01": 70,      # 40 + 30
    "ORPHAN-M01": None,     # no row at all
    "ZEROUSE-M01": 115,     # 30 + 15 + 10 + 40 + 20, tooling untimed
}

EXPECTED_RESOURCE_COMPLETENESS = {
    "SHARED-M01": "known",        # every stage timed AND a cycle count on file
    "ONLY-M01": "lower_bound",    # no qualification duration, no cycle count
    "ONLY-M02": "lower_bound",    # every stage timed; the CYCLE COUNT is absent
    "MISSING-M01": "lower_bound", # four stages untimed, tooling among them
    "ORPHAN-M01": "cannot_tell",  # nothing timed is not a bound
    "ZEROUSE-M01": "lower_bound", # supplier tooling with no tooling lead time
}

# part -> days if qualification takes the number of cycles somebody planned for.
# None where no cycle count is on file, which is NOT the same as one cycle.
EXPECTED_RESOURCE_WITH_RETRY = {
    "SHARED-M01": 360,      # 300 + 1 x 60, over 2 cycles
    "ONLY-M01": None,       # no cycle count
    "ONLY-M02": None,       # no cycle count
    "MISSING-M01": 130,     # 70 + 2 x 30, over 3 cycles
    "ORPHAN-M01": None,
    "ZEROUSE-M01": 115,     # 115 + 0 x 40, one cycle planned for
}

# part -> days per confidence class. KEPT APART: the classes are three different
# kinds of claim and nothing in the system combines them into one figure.
EXPECTED_RESOURCE_DAYS_BY_CLASS = {
    "SHARED-M01": {"judgment": 180, "knowable": 120},
    "ONLY-M01": {"judgment": 80},
    "ONLY-M02": {"judgment": 100},
    "MISSING-M01": {"judgment": 70},
    "ORPHAN-M01": {},
    "ZEROUSE-M01": {"judgment": 115},
}

EXPECTED_PORTABILITY = {
    "SHARED-M01": "supplier",
    "ONLY-M01": "company",
    "ONLY-M02": "company",
    "MISSING-M01": None,
    "ORPHAN-M01": "company",
    "ZEROUSE-M01": "supplier",
}

# The parts stage 4 scores. The four finished goods are made in-house and are
# not scored as purchased parts.
SCORED_PARTS = tuple(sorted(EXPECTED_USAGE))

EXPECTED_PART_COUNT = 10
EXPECTED_EDGE_COUNT = 8
ABSENT_FINISHED_GOOD = "FG-M03"
