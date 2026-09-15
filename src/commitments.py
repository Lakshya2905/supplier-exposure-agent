"""The order book: what has been promised, as against what is planned.

WHY IT IS A SEPARATE FILE AND A SEPARATE MEASURE. Blast radius counts annual
demand for the finished goods a part feeds, which answers how much of the build
stops. It does not answer what a disruption COSTS, and the gap between those two
is where this tool stopped short of the question a planner is actually asked:
which of these will make us miss a promise.

They are not the same figure and neither implies the other. A part can block
enormous annual volume with nothing committed this quarter, and another can
block a trickle that is entirely spoken for next week. Both are real and a
planner does something different about each, so they are two measures in the
same unit rather than one measure with a multiplier.

UNITS, NOT MONEY, AND THAT IS DELIBERATE. `annual_spend_usd` is display-only and
unscored here because ranking by what a part COSTS US is the cost optimisation
agent's job, not this one. Revenue at risk is a near neighbour of that, and the
line this file stays on is that it counts PROMISED UNITS: an obligation already
made, in the same unit as the rest of the volumetric reading, with no price in
it. A company wanting the money can multiply outside this system, where the
price list and the argument about it both live.
"""

# The file and its columns. NOT in `synthetic/model.py`, for the reason
# `recovery.RECOVERY_INPUTS_FILE` gives: everything named there is something the
# generator writes, and an order book is not synthesisable without inventing
# commitments nobody made.
COMMITMENTS_FILE = "commitments.csv"
COMMITTED_UNITS = "committed_units"
