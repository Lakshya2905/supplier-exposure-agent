"""The view model. Pure data, no Streamlit, no decisions.

AUTONOMY IS AN AFFORDANCE, NOT AN APPEARANCE. An `executes` finding has nothing
to click; a `recommends` finding has a control. That distinction is functional
rather than decorative, so it survives restyling, a theme change, or somebody
tidying the stylesheet. A colour-based distinction is one commit from
evaporating; a missing button is not. `Row.__post_init__` refuses to construct
an executed row that carries a control, which makes the claim structural instead
of conventional.

THE ENCODING RULE FOR EVERYTHING ELSE: NOMINAL ONLY. Hue may distinguish
categories. Intensity, size, length and fill fraction may not, because those are
ordinal encodings and an ordinal encoding across a heterogeneous set is a
composite drawn rather than computed. That is the objection that killed the
radar chart and it applies identically to a red-to-green severity ramp. The
corollary is testable: strip every colour and no information is lost, because
the state is always carried in words.
"""
from dataclasses import dataclass, field
from fractions import Fraction

from .. import archetypes as A
from .. import governance as gov
from .. import ranking, scoring
from ..governance.render import (render, render_coverage_note,
                                 render_field_request)

# The three surfaces. Each has ONE row entity, and that is the structural
# reason they cannot be merged into a single table: a unified view has to pick
# one entity, and the other two get denormalised. Flatten clusters to parts and
# a cluster of nine becomes nine rows, so a reviewer confirms one judgment nine
# times and `member_count` stops meaning anything. Flatten fields to parts and
# "fetch on-hand for twenty-six parts" becomes twenty-six rows that each mention
# on-hand, which is a list of parts rather than a list of trips.
EXPOSURE = "exposure"
FIND_OUT = "find_out"
CONFIRM = "confirm"
SURFACES = (EXPOSURE, FIND_OUT, CONFIRM)

PART = "part"
FIELD = "field"
CLUSTER = "cluster"
ROW_ENTITIES = {EXPOSURE: PART, FIND_OUT: FIELD, CONFIRM: CLUSTER}

SURFACE_QUESTION = {
    EXPOSURE: "What is worst?",
    FIND_OUT: "What should I go and find out?",
    CONFIRM: "Do I agree with your model?",
}
SURFACE_VERB = {EXPOSURE: "look at", FIND_OUT: "go and get",
                CONFIRM: "agree or disagree"}
# Short names for cross-references. A reference carries the page NAME, never the
# other page's question, so that one surface quoting another cannot be mistaken
# for the two having been merged.
SURFACE_TITLE = {EXPOSURE: "Exposure", FIND_OUT: "Find out",
                 CONFIRM: "Confirm"}


def _plain(value):
    """Render a measure. THE ONLY PLACE THIS MODULE ROUNDS."""
    if isinstance(value, Fraction):
        return str(value.numerator) if value.denominator == 1 \
            else f"{float(value):.1f}"
    if value is scoring.UNBOUNDED:
        return "unbounded"
    return "" if value is None else str(value)


# ------------------------------------------------------------- evidence ----

@dataclass(frozen=True)
class SupplierRow:
    """One row of suppliers.csv as it was actually read, plus its lead time."""
    supplier_name: str
    region: str
    has_lead_time: bool
    quoted_lead_time_days: object = None
    p95_lead_time_days: object = None


@dataclass(frozen=True)
class DemandRow:
    """One finished good's contribution to this part's annual usage."""
    finished_good: str
    qty_per_finished_good: str
    annual_units: object          # None means ABSENT from the demand plan
    contribution: str


@dataclass(frozen=True)
class Evidence:
    """How a finding was reached. READ ONLY, and it carries no control.

    An executed finding is the least inspectable thing in a system whose claim
    is inspectability, unless the workings are one click away. A reviewer who
    cannot see how a number was reached has to trust it, and trust is precisely
    what this system replaces with verification. So every part row carries this
    whether it executes or recommends.
    """
    part_number: str
    supplier_rows: tuple = ()
    demand_rows: tuple = ()
    lead_time_used: object = None
    notes: tuple = ()

    @property
    def absent_finished_goods(self):
        return tuple(row.finished_good for row in self.demand_rows
                     if row.annual_units is None)


def evidence_for(part_number, supplier_records, exploded_rows, demand_plan,
                 lead_time_records):
    """Assemble the workings from the same inputs the pipeline consumed.

    `supplier_records` are (name_as_spelled, region) rows of suppliers.csv;
    `lead_time_records` are (name_as_spelled, quoted, p95) rows of
    lead_times.csv.

    THE JOIN IS SHOWN, NOT ASSUMED. The two files spell the same supplier
    differently, so the lead time is matched by canonical key exactly as stage 3
    does, and where the raw strings differ a note records both spellings. That
    cross-file join is the single most load-bearing inference in the pipeline
    and it is the thing a reviewer most needs to be able to check.
    """
    from ..normalise import canonical_key

    quoted_by_key = {canonical_key(name): (name, quoted, p95)
                     for name, quoted, p95 in lead_time_records}

    supplier_rows, join_notes = [], []
    for name, region in sorted(supplier_records):
        matched = quoted_by_key.get(canonical_key(name))
        if matched and matched[0] != name:
            join_notes.append(
                f"the lead time for {name!r} was matched to the row spelled "
                f"{matched[0]!r} in lead_times.csv, because the two files "
                f"spell the same supplier differently")
        supplier_rows.append(SupplierRow(
            supplier_name=name, region=region, has_lead_time=matched is not None,
            quoted_lead_time_days=matched[1] if matched else None,
            p95_lead_time_days=matched[2] if matched else None))

    demand_rows = []
    for row in sorted(exploded_rows, key=lambda r: r.finished_good):
        annual = demand_plan.get(row.finished_good)
        contribution = ("" if annual is None
                        else _plain(row.qty_per_finished_good * annual))
        demand_rows.append(DemandRow(
            finished_good=row.finished_good,
            qty_per_finished_good=_plain(row.qty_per_finished_good),
            annual_units=annual, contribution=contribution))

    quotable = [row for row in supplier_rows if row.has_lead_time]
    used = min(quotable, key=lambda row: row.quoted_lead_time_days) \
        if quotable else None

    notes = list(join_notes)
    if not supplier_rows:
        notes.append("no supplier rows exist for this part")
    absent = [row.finished_good for row in demand_rows
              if row.annual_units is None]
    if absent:
        notes.append(
            f"{', '.join(absent)} is in the bill of materials but absent from "
            f"the demand plan, so its contribution could not be counted")
    if not quotable and supplier_rows:
        notes.append("no supplier on this part has a lead time record")

    return Evidence(part_number=part_number,
                    supplier_rows=tuple(supplier_rows),
                    demand_rows=tuple(demand_rows), lead_time_used=used,
                    notes=tuple(notes))


# ------------------------------------------------------------- controls ----

@dataclass(frozen=True)
class Control:
    """Something a reviewer may do. Its existence IS the autonomy claim."""
    action: str
    act_kind: str
    subject: str
    requires_reason: bool = True
    member_count: int = 1
    reason_codes: tuple = ()


@dataclass(frozen=True)
class Row:
    entity: str
    key: str
    sentence: str
    autonomy: str
    controls: tuple = ()
    evidence: object = None
    detail: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.entity not in (PART, FIELD, CLUSTER):
            raise ValueError(f"unknown row entity: {self.entity!r}")
        if self.autonomy == gov.EXECUTES and self.controls:
            raise ValueError(
                "an executed finding must have nothing to click; a control on "
                "it is the autonomy claim quietly evaporating")
        if self.entity == PART and self.evidence is None:
            raise ValueError(
                "every part row carries its workings; a conclusion without "
                "reachable evidence asks a reviewer to trust it")

    @property
    def is_actionable(self):
        return bool(self.controls)


# ------------------------------------------------------------- coverage ----

@dataclass(frozen=True)
class CoverageNote:
    subject: str
    count: int
    sentence: str


@dataclass(frozen=True)
class Coverage:
    """What this page does NOT cover, and why.

    The counterpart to the work queue. That surface says what to go and get;
    this says what was not assessed at all. It sits at the same level as the
    archetype groups rather than beneath them, and its wording is NEUTRAL: these
    are properties of the data and of deliberate design decisions, not faults,
    and phrasing them as warnings would train a reader to dismiss them.
    """
    heading: str
    notes: tuple = ()

    @property
    def is_empty(self):
        return not self.notes


def coverage(profiles, report, thresholds, catalogue):
    notes = []
    if report is not None and report.unplaceable_parts:
        notes.append(CoverageNote(
            subject="unconfirmed supplier lists",
            count=len(report.unplaceable_parts),
            sentence=render_coverage_note(
                "unplaceable", len(report.unplaceable_parts))))

    per_dimension = {}
    for profile in profiles:
        for score in profile.all_scores():
            if score.completeness == scoring.NOT_APPLICABLE:
                per_dimension[score.dimension] = per_dimension.get(
                    score.dimension, 0) + 1
    for dimension, count in sorted(per_dimension.items()):
        notes.append(CoverageNote(
            subject=f"{dimension} not applicable", count=count,
            sentence=render_coverage_note("not_applicable", count,
                                          dimension=dimension)))

    if not thresholds:
        notes.append(CoverageNote(
            subject="magnitude archetypes disabled", count=0,
            sentence=render_coverage_note("no_thresholds", 0)))

    return Coverage(heading="What this page does not cover",
                    notes=tuple(notes))


# ------------------------------------------------------------- surfaces ----

@dataclass(frozen=True)
class Group:
    name: str
    label: str
    rows: tuple
    autonomy: str
    order_label: str = ranking.DEFAULT_ORDER_LABEL


@dataclass(frozen=True)
class Surface:
    name: str
    question: str
    verb: str
    row_entity: str
    layers: tuple = ()
    rows: tuple = ()
    coverage: object = None
    notices: tuple = ()

    def all_rows(self):
        return tuple(row for layer in self.layers for group in layer
                     for row in group.rows) + tuple(self.rows)


def _part_row(profile, verdict, evidence, archetype_labels):
    """A part, with the renderer's sentence and no control.

    Part rows never carry a control. Everything a reviewer can decide is a
    cluster or a catalogue, both of which live on the Confirm surface.
    """
    log = gov.DecisionLog()
    ranking.log_ranked(log, profile, verdict, list(archetype_labels))
    return Row(entity=PART, key=profile.part_number,
               sentence=render(list(log)[0]),
               autonomy=gov.EXECUTES, controls=(), evidence=evidence,
               detail={"archetypes": tuple(archetype_labels)})


def exposure_surface(profiles, verdicts, catalogue, evidence_by_part,
                     report=None, thresholds=None):
    """Archetype groups in dominance layers, plus the coverage panel.

    VERTICAL POSITION MEANS DOMINANCE; HORIZONTAL POSITION MEANS NOTHING.
    Archetypes in the same layer are incomparable and are laid out side by side,
    so the layout itself declines to imply an order that does not exist. No
    group is numbered: a "1., 2., 3." list is a total order asserted by
    typography, and it is how the composite arrives through the back door.
    """
    by_part = {profile.part_number: profile for profile in profiles}
    view = ranking.default_view(profiles, verdicts, catalogue)
    labels = {}
    for layer in view["layers"]:
        for group in layer:
            for part in group.members:
                labels.setdefault(part, []).append(group.label)

    layers = []
    for layer in view["layers"]:
        groups = []
        for group in layer:
            rows = tuple(
                _part_row(by_part[part], verdicts.get(part, ""),
                          evidence_by_part[part], labels.get(part, ()))
                for part in group.members if part in by_part)
            groups.append(Group(name=group.name, label=group.label, rows=rows,
                                autonomy=group.autonomy))
        layers.append(tuple(groups))

    notices = ()
    if not thresholds:
        notices = (render_coverage_note("no_thresholds", 0),)

    return Surface(name=EXPOSURE, question=SURFACE_QUESTION[EXPOSURE],
                   verb=SURFACE_VERB[EXPOSURE], row_entity=PART,
                   layers=tuple(layers),
                   coverage=coverage(profiles, report, thresholds, catalogue),
                   notices=notices)


def find_out_surface(memberships, catalogue):
    """The work queue, INVERTED SO THE ROW IS A FIELD.

    Stage 6 groups the queue by archetype, which answers "what is undecided".
    This surface answers "what should I go and get", and the answer is a list of
    trips to systems of record, not a list of parts. One row per field is what
    makes it that.
    """
    queued = ranking.work_queue(memberships, catalogue)
    by_field = {}
    for archetype_name, items in queued.items():
        for item in items:
            for missing in item.missing_fields:
                entry = by_field.setdefault(missing, {"parts": set(),
                                                      "archetypes": set()})
                entry["parts"].add(item.part_number)
                entry["archetypes"].add(archetype_name)

    rows = []
    for missing, entry in sorted(by_field.items()):
        parts = ranking.in_default_order(entry["parts"])
        archetype_names = tuple(sorted(entry["archetypes"]))
        rows.append(Row(
            entity=FIELD, key=missing,
            sentence=render_field_request(missing, len(parts), archetype_names),
            autonomy=gov.RECOMMENDS,
            controls=(),
            detail={"parts": parts, "archetypes": archetype_names,
                    "order_label": ranking.DEFAULT_ORDER_LABEL}))
    return Surface(name=FIND_OUT, question=SURFACE_QUESTION[FIND_OUT],
                   verb=SURFACE_VERB[FIND_OUT], row_entity=FIELD,
                   rows=tuple(rows))


CLUSTER_REASONS = (gov.REASON_CORRELATION_CONFIRMED,
                   gov.REASON_CORRELATION_REJECTED,
                   gov.REASON_GROUPING_UNSUITED,
                   gov.REASON_SOURCE_DATA_WRONG,
                   gov.REASON_OTHER)


def confirm_surface(report):
    """Clusters awaiting confirmation. ONE ROW PER CLUSTER, ONE ACT PER ROW.

    `member_count` carries the size, which is agent 1's envelope field for
    exactly this. Denormalising a nine-member cluster into nine rows would make
    a reviewer confirm one judgment nine times, which is the concrete damage a
    unified table does.
    """
    log = gov.DecisionLog()
    from ..concentration import log_report
    log_report(log, report)
    events = {event.sku_id: event for event in log}

    rows = []
    for cluster in report.review_queue():
        event = events.get(cluster.key)
        controls = (
            Control(action="confirm", act_kind=gov.ACT_BULK_APPROVE,
                    subject=cluster.key, requires_reason=False,
                    member_count=cluster.size, reason_codes=CLUSTER_REASONS),
            Control(action="reject", act_kind=gov.ACT_REJECT,
                    subject=cluster.key, requires_reason=True,
                    member_count=cluster.size, reason_codes=CLUSTER_REASONS),
        )
        rows.append(Row(
            entity=CLUSTER, key=cluster.key,
            sentence=render(event) if event else "",
            autonomy=gov.RECOMMENDS, controls=controls,
            detail={"members": cluster.members, "basis": cluster.basis,
                    "member_count": cluster.size,
                    "completeness": cluster.completeness}))

    catalogue_row = Row(
        entity=CLUSTER, key="archetype catalogue",
        sentence=render_coverage_note("catalogue", 0),
        autonomy=gov.RECOMMENDS,
        controls=(Control(action="confirm", act_kind=gov.ACT_APPROVE,
                          subject="archetype catalogue", requires_reason=False,
                          member_count=1, reason_codes=CLUSTER_REASONS),),
        detail={"catalogue": True})

    return Surface(name=CONFIRM, question=SURFACE_QUESTION[CONFIRM],
                   verb=SURFACE_VERB[CONFIRM], row_entity=CLUSTER,
                   rows=tuple(rows) + (catalogue_row,))
