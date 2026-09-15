"""Criticality: a classification somebody supplied, used to SCOPE and never to score.

WHY THIS EXISTS. Standard practice is to tier a bill of materials by criticality
before assessing any of it, because a BOM with thousands of lines cannot be
reviewed line by line and a tool that treats every line alike is unusable at that
size. Until now this system scored everything equally, which is correct on three
hundred parts and hopeless on twelve thousand.

WHAT IT IS CAREFUL NOT TO BE, and the care is the whole file. A criticality tier
is one character away from being the composite this project refuses:

  IT IS READ, NEVER DERIVED. The tool does not compute criticality from blast
  radius, from spend, or from anything else. A tier inferred from the measures is
  a weighted sum of them wearing a letter, and it would arrive with no owner. It
  is a column a company already maintains and already argues about, and the
  argument belongs to them.

  IT NEVER ENTERS A SCORE. `sourcing_list_status` gates the verdict only;
  `annual_spend_usd` is display-only. Criticality joins that list: it decides
  which parts are PRESENTED, and no DimensionScore has ever heard of it.
  `test_criticality.py` asserts the absence rather than trusting it.

  IT IS NOT ORDERED HERE. A, B and C look like a ranking and a company may well
  mean one, but the ordering is theirs and the tool is not told it. Scope is a
  SET of labels to include, never a cut-off above or below a level, because a
  cut-off is an ordering asserted by whoever wrote the code.

  EXCLUDING IS NOT ASSESSING. A part outside the scope was not examined, which is
  different from a part that was examined and found fine. `excluded()` reports
  the count and the labels so the coverage panel can say so, and a run scoped to
  one tier is honest about the twelve thousand lines it did not look at.

ABSENT IS NOT A TIER. A part with no criticality on file is not "low": it is
unclassified, and it stays in scope, because dropping parts nobody has got round
to classifying would silently shrink the assessment to the part of the BOM
somebody has already curated. That is the one default here and it is the
inclusive one, stated rather than assumed.
"""
from dataclasses import dataclass, field

# The label a part carries when the column is absent or the cell is blank. NOT a
# tier and never offered as one: it is the absence, named so a filter can show
# how many parts are in it and a reader can see that it is not a level.
UNCLASSIFIED = "unclassified"

# The optional part_master column. Named here rather than in `synthetic/model.py`
# with the generated columns, for the reason `recovery.RECOVERY_INPUTS_FILE`
# gives: every column named there is one the generator writes, and this is one
# it never will. A company's criticality tiering is theirs.
CRITICALITY_COLUMN = "criticality"


@dataclass(frozen=True)
class Scope:
    """Which parts a run looked at, and which it did not.

    Carries both halves on purpose. A scoped run that reported only what it
    assessed would read exactly like an unscoped run over a smaller BOM, and the
    difference between those two is the whole point of scoping.
    """
    labels: tuple = ()               # every label present in the data, sorted
    included: tuple = ()             # the labels this run assessed
    parts_in_scope: tuple = ()
    parts_excluded: tuple = ()
    counts: dict = field(default_factory=dict)   # label -> parts carrying it

    @property
    def is_scoped(self):
        """Whether anything was left out. False for a run over everything."""
        return bool(self.parts_excluded)

    def excluded_labels(self):
        return tuple(label for label in self.labels
                     if label not in self.included)


def labels_of(parts):
    """part -> its criticality label, with absence named rather than dropped.

    `parts` is the part master as `readers.read_part_master` returns it. A record
    with no `criticality` key at all is a dataset whose part master predates the
    column, and it reads the same as a blank cell: unclassified. Those two ARE
    the same fact here, unlike a blank on-hand count and a counted zero, because
    there is no such thing as a recorded absence of criticality.
    """
    return {part: (record.get("criticality") or "").strip() or UNCLASSIFIED
            for part, record in parts.items()}


def scope_for(parts, include=None):
    """Which parts this run assesses, given the labels the caller asked for.

    `include` is a SET OF LABELS, not a level. None means everything, which is
    the shipped behaviour and the honest default: a tool that quietly scoped
    itself to somebody's idea of critical would report a clean bill of health
    for a BOM it had mostly not read.

    A label in `include` that appears nowhere in the data is kept in `included`
    rather than dropped, so the caller can see they asked for something the
    extract does not contain.
    """
    labels = labels_of(parts)
    counts = {}
    for label in labels.values():
        counts[label] = counts.get(label, 0) + 1

    present = tuple(sorted(counts))
    if include is None:
        wanted = present
    else:
        # Sorted and de-duplicated, so two callers asking for the same set get
        # the same Scope and a run is comparable with another run.
        wanted = tuple(sorted({label.strip() for label in include
                               if label and label.strip()}))

    in_scope = tuple(sorted(part for part, label in labels.items()
                            if label in wanted))
    excluded = tuple(sorted(part for part, label in labels.items()
                            if label not in wanted))
    return Scope(labels=present, included=wanted, parts_in_scope=in_scope,
                 parts_excluded=excluded, counts=counts)


def describe(scope):
    """What a coverage panel says about a scoped run. Neutral, and never a warning.

    A scope is a decision somebody made, not a fault, and phrasing it as one
    would train a reader to dismiss the line that tells them how much of the BOM
    this screen is about.
    """
    if not scope.is_scoped:
        return ("Every part in this extract was assessed. No criticality scope "
                "was applied.")
    left_out = ", ".join(scope.excluded_labels())
    plural = "part" if len(scope.parts_excluded) == 1 else "parts"
    return (f"{len(scope.parts_excluded)} {plural} were not assessed, because "
            f"this run was scoped to {', '.join(scope.included)} and they are "
            f"{left_out}. They were not examined and found fine; they were not "
            f"examined.")
