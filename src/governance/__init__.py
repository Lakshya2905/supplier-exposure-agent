"""Governance placeholder. Option 2 from the brief: a thin interface only.

Option 1 is unavailable and this was verified rather than assumed:
`../intake-agent/packages/governance` does not exist, agent 1 being flat-layout
with no `pyproject.toml`, no `packages/`, and no governance module. Extraction
into a shared package waits until after this agent ships, because the right
shared interface is not visible until two real consumers exist.

WHAT IS COPIED FROM AGENT 1 VERBATIM, and why only these things:

  the decision-log field shape   two agents' logs under different schemas
                                 cannot be joined later, and an append-only log
                                 cannot be retrofitted into agreement
  the four statuses              proposed / approved / rejected / superseded
  the four act kinds             approve / bulk_approve / reject / resolve_conflict
  two reason codes               the domain-neutral ones

Agent 1's other four reason codes are intake-specific ("measurement corrected
at dock", "packaging changes effective tier"). There is no dock and no tier
here, and copying them literally would degrade the vocabulary rather than share
it. The enum below marks which codes are inherited and which are agent 3's,
and that marking IS the migration plan: on extraction, the inherited codes move
to the shared package unchanged and the agent-3 codes are promoted or left
behind deliberately, one at a time.

STORE STRUCTURED, RENDER PROSE, NEVER STORE THE PROSE. See `render.py`. A log
that stores its own sentences cannot be re-rendered when the wording improves,
and the wording is a deliverable here, not a debug view.
"""
from dataclasses import asdict, dataclass
from dataclasses import field as dataclass_field   # `field` is one of agent 1's
# envelope column names and is kept verbatim, so it shadows dataclasses.field
# inside the class bodies below. Aliasing the import is the smaller compromise:
# renaming the column is what makes two decision logs unjoinable.

# ---------------------------------------------------------------- statuses --
# Inherited from agent 1 VERBATIM. Do not reword.
STATUS_PROPOSED = "proposed"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_SUPERSEDED = "superseded"
STATUSES = (STATUS_PROPOSED, STATUS_APPROVED, STATUS_REJECTED,
            STATUS_SUPERSEDED)

# ------------------------------------------------------------- act kinds ----
# Inherited from agent 1 VERBATIM. resolve_conflict covers a dual-reading
# disagreement, which is what agent 1 used it for too.
ACT_APPROVE = "approve"
ACT_BULK_APPROVE = "bulk_approve"
ACT_REJECT = "reject"
ACT_RESOLVE_CONFLICT = "resolve_conflict"
ACT_KINDS = (ACT_APPROVE, ACT_BULK_APPROVE, ACT_REJECT, ACT_RESOLVE_CONFLICT)

# ----------------------------------------------------------- reason codes ---
# INHERITED FROM AGENT 1, VERBATIM. These two are domain-neutral and must not
# be reworded: they are the codes both agents' logs will share.
REASON_SOURCE_DATA_WRONG = "source data wrong"
REASON_OTHER = "other (note below)"

# AGENT 3 SPECIFIC. Everything below this line is the migration surface. On
# extraction, each is promoted to the shared package or left here, deliberately
# and one at a time.
REASON_MERGE_CONFIRMED = "same supplier, merge confirmed"
REASON_MERGE_REJECTED = "different suppliers, merge rejected"
REASON_LIST_CONFIRMED = "supplier list confirmed complete"
REASON_LIST_INCOMPLETE = "supplier list known incomplete"
REASON_MAKE_FLAG_STALE = "make flag stale, part is purchased"
REASON_MAKE_CAPABILITY_REAL = "in-house capability confirmed"
REASON_ON_HAND_COUNTED = "on-hand counted, record added"
REASON_DEMAND_RECORDED = "demand added for a finished good that had none"
REASON_TOOLING_CONFIRMED = "tooling ownership confirmed"
REASON_CORRELATION_CONFIRMED = "correlation confirmed"
REASON_CORRELATION_REJECTED = "not correlated in practice"
REASON_GROUPING_UNSUITED = "grouping definition does not fit this case"

INHERITED_REASON_CODES = (REASON_SOURCE_DATA_WRONG, REASON_OTHER)
AGENT_3_REASON_CODES = (REASON_MERGE_CONFIRMED, REASON_MERGE_REJECTED,
                        REASON_LIST_CONFIRMED, REASON_LIST_INCOMPLETE,
                        REASON_MAKE_FLAG_STALE, REASON_MAKE_CAPABILITY_REAL,
                        REASON_ON_HAND_COUNTED, REASON_DEMAND_RECORDED,
                        REASON_TOOLING_CONFIRMED, REASON_CORRELATION_CONFIRMED,
                        REASON_CORRELATION_REJECTED, REASON_GROUPING_UNSUITED)
REASON_CODES = INHERITED_REASON_CODES + AGENT_3_REASON_CODES

# ------------------------------------------------------------ event kinds ---
KIND_MERGE_UNCERTAIN = "merge_uncertain"
KIND_READINGS_DISAGREE = "readings_disagree"
KIND_VERDICT_ASSIGNED = "verdict_assigned"
KIND_HUMAN_DECISION = "human_decision"
# stage 4. One event per dimension per part, because autonomy is per dimension.
KIND_DIMENSION_SCORED = "dimension_scored"
KIND_DIMENSION_ABSTAINED = "dimension_abstained"
# stage 5. One event per CLUSTER, never one per member: member_count carries
# the size, which is what agent 1's envelope field was always for.
KIND_CLUSTER_FLAGGED = "cluster_flagged"
KIND_CLUSTER_CONTINGENT = "cluster_contingent"
EVENT_KINDS = (KIND_MERGE_UNCERTAIN, KIND_READINGS_DISAGREE,
               KIND_VERDICT_ASSIGNED, KIND_HUMAN_DECISION,
               KIND_DIMENSION_SCORED, KIND_DIMENSION_ABSTAINED,
               KIND_CLUSTER_FLAGGED, KIND_CLUSTER_CONTINGENT)

# Autonomy, per finding rather than per stage.
EXECUTES = "executes"
RECOMMENDS = "recommends"

# The envelope, field for field as agent 1 writes it. `sku_id` keeps its name
# even though this agent calls them parts: they are the same entity class, and
# renaming the column is exactly what makes two logs unjoinable.
ENVELOPE_FIELDS = ("event_id", "at", "status", "decided_by", "reason_code",
                   "note", "act_id", "act_kind", "member_count", "sku_id",
                   "field", "value", "source_file")


@dataclass(frozen=True)
class DecisionEvent:
    """One append-only record.

    The envelope is agent 1's, unchanged. `kind` and `evidence` are ADDITIVE
    agent-3 columns: a join across both agents uses the envelope and simply
    does not see them, which is why adding them does not split the schema.

    `evidence` holds structure, never sentences.
    """
    event_id: int
    at: str
    status: str
    sku_id: str
    field: str = ""
    value: str = ""
    source_file: str = ""
    decided_by: str = ""
    reason_code: str = ""
    note: str = ""
    act_id: int = None
    act_kind: str = ""
    member_count: int = 1
    # additive, agent 3
    kind: str = KIND_VERDICT_ASSIGNED
    evidence: dict = dataclass_field(default_factory=dict)

    def envelope(self):
        """Just the inherited fields, which is what a cross-agent join reads."""
        return {name: getattr(self, name) for name in ENVELOPE_FIELDS}


@dataclass(frozen=True)
class Confidence:
    """A number is not a finding. Reasons travel with it, always."""
    value: float
    reasons: tuple = ()

    def __post_init__(self):
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"confidence out of range: {self.value}")


@dataclass(frozen=True)
class Finding:
    """A typed result. Autonomy is a property of THIS finding, not of the stage
    that produced it."""
    subject: str
    verdict: str
    autonomy: str
    confidence: Confidence
    evidence: dict = dataclass_field(default_factory=dict)

    def __post_init__(self):
        if self.autonomy not in (EXECUTES, RECOMMENDS):
            raise ValueError(f"unknown autonomy level: {self.autonomy}")


class DecisionLog:
    """Append-only. No update, no delete, and no rendered text stored."""

    def __init__(self):
        self._events = []

    def append(self, **kwargs):
        if kwargs.get("status") not in STATUSES:
            raise ValueError(f"unknown status: {kwargs.get('status')!r}")
        if kwargs.get("kind", KIND_VERDICT_ASSIGNED) not in EVENT_KINDS:
            raise ValueError(f"unknown event kind: {kwargs.get('kind')!r}")
        reason = kwargs.get("reason_code", "")
        if reason and reason not in REASON_CODES:
            raise ValueError(f"unknown reason code: {reason!r}")
        if kwargs.get("status") != STATUS_PROPOSED and not (
                kwargs.get("decided_by") or "").strip():
            raise ValueError(
                f"{kwargs.get('status')} requires a named decider; an "
                f"anonymous decision is not a decision")
        event = DecisionEvent(event_id=len(self._events) + 1, **kwargs)
        self._events.append(event)
        return event

    def __len__(self):
        return len(self._events)

    def __iter__(self):
        return iter(self._events)

    def events(self):
        return tuple(self._events)

    def to_records(self):
        return [asdict(event) for event in self._events]
