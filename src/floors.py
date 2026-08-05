"""Ship-gate floors, each carrying the derivation that produced it.

A FLOOR SET JUST BELOW TODAY'S NUMBER IS NOT A FLOOR, IT IS A DESCRIPTION. So
every floor here states where it came from, in terms of what the task requires
rather than what the system currently scores, and `test_eval_integrity.py`
refuses a floor whose derivation is empty. Writing the justification is the
friction that makes "nudge it under the current measurement" hard to do without
noticing you are doing it.

Most floors are 1.0 or 0, and that is a finding rather than an ambition: **a
floor at 100% is a claim that the quantity has no legitimate source of
variance.** Only two are neither, and they are the two where a real trade-off
exists. Both were derived at stage 3 from which error costs more, before
anything was measured, and the matching threshold moved to meet them rather than
the reverse.

`wrong_if` is the other half. A floor can be mistaken, and the honest way to say
so is to state the claim about the world that would have to be false. Changing a
floor therefore edits its justification in the same commit, so the reason is
reviewed alongside the number.
"""
from dataclasses import dataclass

RATIO = "ratio"          # measured value must be >= value
ZERO = "zero"            # measured count must be exactly 0


@dataclass(frozen=True)
class Floor:
    name: str
    value: float
    kind: str
    derivation: str
    wrong_if: str

    def __post_init__(self):
        if self.kind not in (RATIO, ZERO):
            raise ValueError(f"unknown floor kind: {self.kind!r}")
        if not self.derivation.strip():
            raise ValueError(
                f"{self.name} has no derivation; a floor without one is a "
                f"description of today's behaviour")
        if not self.wrong_if.strip():
            raise ValueError(
                f"{self.name} does not say what would have to be true for it "
                f"to be wrong, so it cannot be argued with")

    def holds(self, measured):
        return measured == 0 if self.kind == ZERO else measured >= self.value

    def render(self, measured):
        if self.kind == ZERO:
            return f"{measured:.0f} violations, floor 0"
        return f"{measured:.3f}, floor {self.value:.3f}"


VERDICT_ACCURACY = Floor(
    name="verdict accuracy against the answer key",
    value=1.0, kind=RATIO,
    derivation=(
        "The verdict table is a deterministic lookup over four inputs read "
        "straight from the CSVs after name normalisation. There is no model, no "
        "threshold inside it and no sampling, so it has no legitimate source of "
        "variance. Anything below 100% is a bug rather than noise, which is why "
        "the floor is 1.000 and not 0.98."),
    wrong_if=(
        "the verdict table were to acquire an input that is estimated rather "
        "than read, at which point a rate below 1.0 could be honest"))

NAME_MATCH_PRECISION = Floor(
    name="supplier name-match precision",
    value=0.95, kind=RATIO,
    derivation=(
        "A false merge collapses two real suppliers into one and manufactures a "
        "PHANTOM SINGLE SOURCE, sending somebody to qualify a second supplier "
        "that already exists. Wasteful, and self-correcting once they arrive, "
        "so the floor sits below recall's."),
    wrong_if=(
        "qualifying a supplier were cheap enough that a wasted qualification "
        "cost less than an understated exposure, which is a business claim a "
        "named person has to make"))

NAME_MATCH_RECALL = Floor(
    name="supplier name-match recall",
    value=0.99, kind=RATIO,
    derivation=(
        "A missed merge counts one supplier as two, reads multi_source where "
        "the truth is single_source and UNDERSTATES exposure. That is the error "
        "that stops a line, so the floor is near-absolute."),
    wrong_if=(
        "understating exposure were recoverable at the same cost as overstating "
        "it, which the whole premise of the agent denies"))

ABSTENTION_SET_EQUALITY = Floor(
    name="abstention sets against generator decisions",
    value=1.0, kind=RATIO,
    derivation=(
        "Set equality over a decision the generator recorded, with no inference "
        "in between: a part with no on-hand record must abstain on cover, and a "
        "part with no tooling owner must abstain on portability. Any gap means "
        "the missing-versus-zero distinction has collapsed somewhere, which is "
        "the single failure this system exists to prevent."),
    wrong_if=(
        "a dimension gained a second legitimate reason to abstain that truth "
        "does not record, in which case the check needs splitting rather than "
        "loosening"))

AUTONOMY_VIOLATIONS = Floor(
    name="autonomy integrity",
    value=0, kind=ZERO,
    derivation=(
        "These are the claims the project makes: a finding meaning nobody can "
        "tell never executes, and no concentration finding executes however "
        "complete the data is. One violation falsifies the claim, so it cannot "
        "be expressed as a percentage."),
    wrong_if=(
        "the project stopped claiming that autonomy is decided per finding, "
        "which would be a different project"))

STRUCTURAL_GUARANTEES = Floor(
    name="BOM structural guarantees",
    value=1.0, kind=RATIO,
    derivation=(
        "Explosion runs unattended at `executes` and that autonomy level is "
        "SCOPED on exactly these guarantees: every edge resolves to a known "
        "part, every part reaches a finished good, no cycle exists. If one "
        "fails the autonomy claim is void rather than degraded, so there is no "
        "partial credit to give."),
    wrong_if=(
        "explosion were changed to answer partially on a broken BOM instead of "
        "raising, which would need its autonomy level revisited first"))

UNIT_VIOLATIONS = Floor(
    name="unit integrity",
    value=0, kind=ZERO,
    derivation=(
        "The no-composite guarantee rests entirely on every measure keeping a "
        "physical unit. A single dimension result carrying a unitless or "
        "rescaled value means a composite is already assembled, whether or not "
        "anybody has written the operator yet."),
    wrong_if=(
        "the system decided to publish a blended score, which every other part "
        "of the design refuses"))

RENDERER_COVERAGE = Floor(
    name="renderer coverage of kinds and reason codes",
    value=1.0, kind=RATIO,
    derivation=(
        "An event kind or reason code with no rendering reaches the review "
        "interface unreadable, and the rendered sentence is the deliverable. "
        "Partial coverage means some findings are undeliverable, which is not a "
        "degraded version of delivering them."),
    wrong_if=(
        "an event kind were introduced that is deliberately internal and never "
        "shown, which would need excluding by name rather than by omission"))

FLOORS = (
    VERDICT_ACCURACY,
    NAME_MATCH_PRECISION,
    NAME_MATCH_RECALL,
    ABSTENTION_SET_EQUALITY,
    AUTONOMY_VIOLATIONS,
    STRUCTURAL_GUARANTEES,
    UNIT_VIOLATIONS,
    RENDERER_COVERAGE,
)
