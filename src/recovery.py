"""The resourcing chain: how long to bring an ALTERNATIVE source to production.

WHY THIS MODULE EXISTS. A program manager read the tool and asked what time and
activities "how long it would take to recover" accounts for. The answer was
purchase lead time, and his reply is the specification for this file:

    qualification can vary significantly by part, and does not always go
    smoothly

Two claims, and each one breaks a different assumption. "Varies by part" breaks
the idea that a single number covers it. "Does not always go smoothly" breaks
the idea that even a known part has ONE number, because a failed qualification
adds a cycle.

So recovery is two quantities and they are never merged:

    wait_out_days    purchase lead time. What it costs to sit out a disruption
                     with the source you already have. Lives in `scoring`,
                     because it is read straight off `lead_times.csv`.
    resource_days    this module. A CHAIN of stages, each of which either has a
                     duration or does not, ending in a total that says which
                     stages it could time and which it could not.

THE CHAIN IS A LOWER BOUND UNLESS EVERY STAGE IS TIMED. An untimed stage is
`cannot_tell` for that stage and never zero, so the total under-counts by
whatever the untimed stages take. Reporting it as a plain number would be the
missing-versus-zero collapse this project exists to refuse, wearing a duration.
A total with NO timed stage is not a bound at all: zero days is the trivial
lower bound of any non-negative duration, so it promises a figure and delivers
nothing. That case abstains instead, which is the same repair
`render._blocked_volume_absent` already carries for blast radius.

THREE CONFIDENCE CLASSES, AND THEY ARE NOT AVERAGED. A quoted lead time was
reported by somebody with a system of record behind them. A tooling lead time is
knowable: nobody has supplied it, but a toolmaker could. A qualification
duration is a judgment, and no amount of asking turns it into a measurement.
Those are different kinds of claim, so the chain keeps each class's subtotal
separately and names the weakest class it drew on. The stages still SUM, because
they happen one after another and elapsed days really do add; what is refused is
presenting a total that mixes classes as though it were one kind of fact, and
any statistic (a mean, a blend, a confidence number) computed across them.

THE RETRY IS MODELLED, NOT ASSUMED. Where a reviewer supplies how many
qualification cycles to plan for, the chain reports both readings: the days if
it passes first time, and the days if it takes the supplied number of cycles.
Where that input is absent the chain does NOT quietly assume one pass; it says
the assumption is unrecorded and reports a lower bound.
"""
from dataclasses import dataclass

# ------------------------------------------------------- confidence classes --
# What KIND of claim a duration is, never how good it is. These are nominal
# labels: there is no arithmetic on them, and a chain never averages across
# them. "reported" appears here and is never produced by this module, because
# the only reported duration in the system is purchase lead time and that is the
# other half of recovery, in `scoring.wait_out_days`.
REPORTED = "reported"    # read from a system of record
KNOWABLE = "knowable"    # nobody supplied it; somebody could
JUDGMENT = "judgment"    # an estimate a person makes and owns

CONFIDENCE_CLASSES = (REPORTED, KNOWABLE, JUDGMENT)

# Weakest last. Used ONLY to name which class a total leans on, never to score
# one, and a chain reports the weakest class it actually drew on rather than
# blending them into a number.
_WEAKEST_LAST = (REPORTED, KNOWABLE, JUDGMENT)


# --------------------------------------------------------------- the stages --

@dataclass(frozen=True)
class Stage:
    """One activity in the resourcing chain, with the kind of claim it is."""
    key: str
    label: str
    confidence: str

    def __post_init__(self):
        if self.confidence not in CONFIDENCE_CLASSES:
            raise ValueError(f"unknown confidence class: {self.confidence!r}")


ALTERNATE_SOURCE = "alternate_source_days"
COMMERCIAL = "commercial_agreement_days"
TOOLING = "tooling_lead_time_days"
ENGINEERING_TRANSFER = "engineering_transfer_days"
SUPPLIER_INPUTS = "supplier_input_lead_time_days"
FIRST_ARTICLE = "first_article_days"
QUALIFICATION_TEST = "qualification_test_days"
CUSTOMER_APPROVAL = "customer_approval_days"
CAPACITY_SLOT = "capacity_slot_days"
RAMP = "ramp_to_rate_days"

# The activities, in the order they happen. Sequential on purpose: see
# UNMODELLED at the foot of this file for what that costs.
#
# SIX OF THESE THE PRACTITIONER NAMED. FOUR WERE ADDED ON 2026-09-16, and they
# are the ones a chain of engineering stages quietly omits, because each is
# somebody else's queue rather than your own work:
#
#   commercial      nobody cuts metal before the contract is signed, and a
#                   quality agreement and a price can take longer than the
#                   first article. Frequently the real bottleneck, and
#                   invisible to a chain that models only technical work
#   supplier inputs the alternate has their OWN lead time on raw material and
#                   sub-components. Qualified and waiting for bar stock is
#                   still waiting
#   customer        a source change often needs the customer or a regulator to
#                   accept it, and in a regulated programme that single stage
#                   can exceed every other stage combined
#   capacity        qualified with no slot until Q3 is a different problem from
#                   not qualified, and only one of the two is fixed by
#                   qualifying faster
#
# ALL FOUR ARE `KNOWABLE`, NOT `JUDGMENT`, and the distinction is the point:
# every one of them is a fact somebody already holds -- a contracts lead, the
# alternate supplier, the customer's quality function, the alternate's planner.
# Nobody in this dataset has been asked. That is a different claim from
# "how long will qualification take", which no amount of asking settles.
STAGES = (
    Stage(ALTERNATE_SOURCE, "finding and qualifying an alternate source",
          JUDGMENT),
    Stage(COMMERCIAL, "commercial and contractual agreement", KNOWABLE),
    Stage(TOOLING, "tooling dedicated to the part", KNOWABLE),
    Stage(ENGINEERING_TRANSFER, "engineering transfer of drawings and specs",
          JUDGMENT),
    Stage(SUPPLIER_INPUTS, "the alternate's own material and component lead "
          "time", KNOWABLE),
    Stage(FIRST_ARTICLE, "first article inspection", JUDGMENT),
    Stage(QUALIFICATION_TEST, "qualification and reliability testing",
          JUDGMENT),
    Stage(CUSTOMER_APPROVAL, "customer or regulatory approval of the source "
          "change", KNOWABLE),
    Stage(CAPACITY_SLOT, "a production slot at the alternate", KNOWABLE),
    Stage(RAMP, "ramp to rate", JUDGMENT),
)

STAGE_KEYS = tuple(stage.key for stage in STAGES)

# How many qualification cycles to plan for. A COUNT SUPPLIED BY A PERSON, and
# deliberately not a first-pass yield. A yield is a probability, and turning one
# into a duration needs a model of how failures distribute; that model is a
# judgment, and inventing it here would attribute it to nobody. A cycle count is
# the same judgment made by somebody who owns it.
CYCLES = "qualification_cycles"

INPUT_FIELDS = STAGE_KEYS + (CYCLES,)

# NOT IN `synthetic/model.py` with the other file names, and the exception is
# the point: every file named there is one the generator writes. This one it
# never writes, because the durations in it are judgments a person owns. It is
# named here, beside the model that reads it.
RECOVERY_INPUTS_FILE = "recovery_inputs.csv"

# ------------------------------------------------------------ applicability --
# A stage that does not happen is not a stage nobody timed. Both contribute zero
# days and they mean opposite things: one is settled, the other is a gap.
APPLIES = "applies"
DOES_NOT_APPLY = "does_not_apply"
APPLICABILITY_UNKNOWN = "applicability_unknown"

TOOLING_COMPANY = "company"
TOOLING_SUPPLIER = "supplier"


def tooling_applicability(tooling_owner):
    """Whether retooling is on the path, from who owns the tooling today.

    The same categorical `portability` reports, read for a different question,
    and the two never merge: portability says how portable the part is, this
    says whether one stage of the chain happens at all.
    """
    owner = (tooling_owner or "").strip()
    if owner == TOOLING_SUPPLIER:
        return APPLIES               # the tooling does not come with you
    if owner == TOOLING_COMPANY:
        return DOES_NOT_APPLY        # company tooling moves to the new source
    return APPLICABILITY_UNKNOWN     # nobody recorded an owner


@dataclass(frozen=True)
class StageTiming:
    """One stage for one part: does it happen, and how long does it take."""
    stage: Stage
    applicability: str
    days: object = None              # None means UNTIMED, never zero days

    @property
    def is_timed(self):
        return self.applicability == APPLIES and self.days is not None

    @property
    def is_untimed(self):
        """On the path, and nobody has said how long. The gap that bounds."""
        return self.applicability != DOES_NOT_APPLY and self.days is None


@dataclass(frozen=True)
class Chain:
    """Every stage for one part, and what can honestly be said about the total.

    Carries no completeness state of its own. `scoring.resource_days` reads
    these properties and decides the state, so the routing rule keeps one home.
    """
    timings: tuple
    cycles: object = None

    def __post_init__(self):
        """A plan for fewer than one qualification cycle is not a plan.

        REFUSED AT CONSTRUCTION rather than clamped, in the same spirit as
        `DimensionScore`'s unit check. Zero cycles would make the retry total
        SHORTER than the first-pass total, which is a wrong answer rather than a
        missing one, and a silently clamped value would put a number nobody
        supplied into a measure whose whole claim is that it does not do that.
        """
        if self.cycles is not None and self.cycles < 1:
            raise ValueError(
                f"qualification_cycles is {self.cycles}; a chain that runs "
                f"fewer than one qualification cycle has not qualified "
                f"anything. Leave the cell blank to say nobody has planned it")

    @property
    def timed(self):
        return tuple(t for t in self.timings if t.is_timed)

    @property
    def untimed(self):
        return tuple(t for t in self.timings if t.is_untimed)

    @property
    def skipped(self):
        return tuple(t for t in self.timings
                     if t.applicability == DOES_NOT_APPLY)

    @property
    def first_pass_days(self):
        """Elapsed days across the timed stages, one pass. None if none timed.

        A SUM OF DAYS AND NOTHING ELSE. The stages run one after another, so
        their durations add; no class is given more of the total than the days
        it contributes, because nothing here is applied to them but addition.
        """
        timed = self.timed
        return sum(t.days for t in timed) if timed else None

    @property
    def with_retry_days(self):
        """Days if qualification takes the supplied number of cycles.

        Only the qualification and reliability test repeats. Finding the source,
        transferring the drawings and cutting the tooling are not redone because
        a test failed, so the retry adds that one stage again rather than
        re-running the chain. Returns None when the cycle count is absent, or
        when the stage that repeats has no duration to repeat.
        """
        cycles = self.cycles
        first_pass = self.first_pass_days
        if cycles is None or first_pass is None:
            return None
        repeated = {t.stage.key: t.days for t in self.timed}.get(
            QUALIFICATION_TEST)
        if repeated is None:
            return None
        return first_pass + (cycles - 1) * repeated

    @property
    def days_by_class(self):
        """Subtotal per confidence class. KEPT APART, never combined.

        A reader who wants to know how much of a 260 day chain rests on an
        estimate rather than a quote can read it here. Collapsing this into one
        number is the move the whole design refuses.
        """
        totals = {}
        for timing in self.timed:
            key = timing.stage.confidence
            totals[key] = totals.get(key, 0) + timing.days
        return totals

    @property
    def weakest_class(self):
        """The weakest KIND of claim the total rests on. A label, not a number.

        A total drawing on one judgment is a judgment, however many reported
        days sit beside it, which is why this reports the weakest rather than
        anything computed across the classes.
        """
        present = [t.stage.confidence for t in self.timed]
        for confidence in reversed(_WEAKEST_LAST):
            if confidence in present:
                return confidence
        return None


def chain(tooling_owner, stages=None):
    """Build the chain for one part from whatever durations exist.

    `stages` is the part's row of `recovery_inputs.csv` as a dict, or None when
    the file does not exist. An absent key and a key whose cell was blank are
    the same fact and both mean UNTIMED; a recorded 0 is a real duration and is
    kept, exactly as `on_hand_units` treats a counted zero.
    """
    supplied = dict(stages or {})
    timings = []
    for stage in STAGES:
        applicability = (tooling_applicability(tooling_owner)
                         if stage.key == TOOLING else APPLIES)
        days = supplied.get(stage.key)
        timings.append(StageTiming(stage=stage, applicability=applicability,
                                   days=None if applicability == DOES_NOT_APPLY
                                   else days))
    return Chain(timings=tuple(timings), cycles=supplied.get(CYCLES))


# ---------------------------------------------------------------- UNMODELLED --
# Recorded here rather than discovered later, and each of these is a reason the
# total is optimistic rather than merely incomplete:
#
#   THE CHAIN IS SEQUENTIAL. Tooling and source qualification overlap in real
#   programmes, so a chain that adds them overstates a schedule somebody has
#   already crashed. It also means the total is not a lower bound in the
#   direction the untimed stages make it one, and those two errors do not
#   cancel.
#
#   THAT COST ROSE ON 2026-09-16 AND IS WORTH NAMING SEPARATELY. Ten sequential
#   stages overlap more than six did: commercial negotiation runs alongside
#   engineering transfer in any programme worth the name, and a capacity slot is
#   usually booked long before qualification finishes rather than after it. The
#   four added stages make the chain more COMPLETE and its sequencing more
#   pessimistic at the same time. Neither error was introduced by the other and
#   neither cancels it; a dependency graph rather than a chain is what would fix
#   the sequencing, and that is a different piece of work.
#
#   THE CHAIN IS PER PART, NOT PER CANDIDATE SOURCE. How long qualification
#   takes depends on WHICH alternative you go to, and nothing in this schema
#   represents a candidate source. That is the known gap this version leaves
#   open, and `tests/test_scoring.py` carries it as a strict xfail.
