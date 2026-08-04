"""Expected results for tiny_bom.csv, worked out BY HAND.

The single statement of these numbers. Both the stage 1 oracle test and the
stage 2 explosion test assert against this module, so there is one place a
human checks the arithmetic rather than copies drifting apart.

Re-derivable from the tree in tiny_bom.csv's comment block without running
anything. If this file and that comment block ever disagree, both are wrong
until a human works it out again.
"""

# Quantity per ONE unit of FG-T01.
EXPECTED_QTY_PER_FG = {
    "SUB-T01": 2,
    "SUB-T02": 1,
    "SUB-T03": 3,
    "LEAF-T01": 11,          # (2 x 3) + (1 x 4) + 1  = 6 + 4 + 1
    "LEAF-T02": 2,           # 2 x 1
    "LEAF-T03": 4,           # 2 x 2
    "LEAF-T04": 5,           # 1 x 5
    "LEAF-T05": 1,           # 1 x 1
    "LEAF-T06": 6,           # 3 x 2
    "LEAF-T07": 3,           # 3 x 1
    "LEAF-T08": 2,
    "LEAF-T09": 1,
    "LEAF-T10": 4,
    "LEAF-T11": 1,
}

# Depths are SETS because depth belongs to the path, not to the part.
EXPECTED_DEPTHS = {
    "SUB-T01": {1}, "SUB-T02": {1}, "SUB-T03": {1},
    "LEAF-T01": {1, 2},      # the whole point of this fixture
    "LEAF-T02": {2}, "LEAF-T03": {2}, "LEAF-T04": {2}, "LEAF-T05": {2},
    "LEAF-T06": {2}, "LEAF-T07": {2},
    "LEAF-T08": {1}, "LEAF-T09": {1}, "LEAF-T10": {1}, "LEAF-T11": {1},
}

EXPECTED_FINISHED_GOOD = "FG-T01"
EXPECTED_PART_COUNT = 15
EXPECTED_EDGE_COUNT = 16
