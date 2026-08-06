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
from ..synthetic.model import (ANNUAL_UNITS, DEMAND_FILE, LEAD_TIME_P95_DAYS,
                               LEAD_TIMES_FILE, QTY_PER_PARENT,
                               QUOTED_LEAD_TIME_DAYS, SUPPLIER_NAME,
                               SUPPLIER_REGION, SUPPLIERS_FILE)

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
#
# THE SIX FIELDS OF AN EVIDENCE RECORD, and where each one comes from:
#
#   source id             `source_file` and `row`, carried by the reader from
#                         the line that produced the value
#   system of record      sources.csv, via the extract manifest
#   field cited           the column constant, spelled as the CSV spells it
#   as of                 sources.csv, the extract's retrieval time
#   transformation        stated with both the original and the resolved string
#   inverse link          the locator, which names a file and a line a reviewer
#                         can open, and which the plain-text export carries so
#                         the chain is walkable from a raw row back to the
#                         claims that used it
#
# `system of record`, NOT `source type`. DESIGN.md called this field source type
# and that name was already taken: `source_type` is a part_master column meaning
# make or buy. One word cannot carry both, and the CSV column is the older name
# and is load-bearing in the verdict table, so the anatomy was renamed instead.

RECORDED = "recorded"   # the value appears verbatim in a source file
DERIVED = "derived"     # this pipeline computed it from values that do

# The two merges this pipeline performs, separated because they are not the same
# claim. A cross-file merge reconciles two spellings of one supplier across two
# files and changes no count. A duplicate vendor merge collapses two rows of ONE
# file into one supplier and therefore CHANGES THE SUPPLIER COUNT, which is the
# number the verdict turns on. A reviewer counting rows in the panel gets two and
# the sentence says one; without this stated, that gap looks like a bug in the
# sentence.
CROSS_FILE_MERGE = "cross_file_merge"
DUPLICATE_VENDOR_MERGE = "duplicate_vendor_merge"


@dataclass(frozen=True)
class Citation:
    """One value and everything needed to check it.

    `row` is None and `source_file` empty exactly when `authority` is DERIVED:
    a computed value has no line to open, and pointing at one would be a
    citation to a number that is not there.
    """
    field: str
    value: str
    source_file: str = ""
    row: object = None
    system_of_record: str = ""
    retrieved_at: str = ""
    authority: str = RECORDED
    transformation: str = ""
    derived_from: str = ""

    def __post_init__(self):
        if self.authority == RECORDED and not (self.source_file and self.row):
            raise ValueError(
                f"a recorded citation must name the file and row it came from; "
                f"{self.field!r} names {self.source_file!r} row {self.row!r}")
        if self.authority == DERIVED and (self.source_file or self.row):
            raise ValueError(
                f"a derived value has no line to open, so {self.field!r} must "
                f"not cite one; it cites {self.source_file!r} row {self.row!r}")

    @property
    def locator(self):
        """The inverse link: what a reviewer opens, and what the export carries.

        Empty for a derived value, which is the honest answer rather than a
        pointer at a row that does not contain the number.
        """
        return f"{self.source_file}:{self.row}" if self.source_file else ""


@dataclass(frozen=True)
class Transformation:
    """A merge or normalisation, with BOTH strings and the rule that fired.

    Never just the resolved string. The whole point of showing a transformation
    is that a reviewer can disagree with it, and they cannot disagree with a
    result whose input has been discarded.
    """
    kind: str
    original: str
    resolved: str
    rule: str
    certain: bool = True

    @property
    def changes_supplier_count(self):
        return self.kind == DUPLICATE_VENDOR_MERGE


@dataclass(frozen=True)
class Contradiction:
    """Two records that answer the same question differently.

    SHOWN, NEVER RESOLVED. Both citations render and the tool does not pick.
    Picking would be the system deciding a question it has no basis to decide,
    and doing it silently, which is the failure mode this panel exists against.
    """
    field: str
    subject: str
    citations: tuple


@dataclass(frozen=True)
class SupplierRow:
    """One row of suppliers.csv as it was actually read, plus its lead time."""
    supplier_name: str
    region: str
    has_lead_time: bool
    quoted_lead_time_days: object = None
    p95_lead_time_days: object = None
    citations: tuple = ()


@dataclass(frozen=True)
class DemandRow:
    """One finished good's contribution to this part's annual usage."""
    finished_good: str
    qty_per_finished_good: str
    annual_units: object          # None means ABSENT from the demand plan
    contribution: str
    citations: tuple = ()


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
    transformations: tuple = ()
    contradictions: tuple = ()
    absences: tuple = ()
    lead_time_citations: tuple = ()

    @property
    def absent_finished_goods(self):
        return tuple(row.finished_good for row in self.demand_rows
                     if row.annual_units is None)

    def all_citations(self):
        """Every citation in this record, in the order the panel shows them.

        Deduplicated, and `lead_time_citations` is deliberately not appended:
        the lead time used belongs to one of the supplier rows above, so adding
        it again would print the same line three times and inflate what a
        reader takes for the amount of evidence.
        """
        seen, out = set(), []
        for citation in (
                tuple(c for row in self.supplier_rows for c in row.citations)
                + tuple(c for row in self.demand_rows for c in row.citations)):
            if citation in seen:
                continue
            seen.add(citation)
            out.append(citation)
        return tuple(out)

    def sources_used(self):
        """One entry per file this record drew on, with the rows it cited.

        IDENTITY AND TYPE, NEVER A TALLY. DESIGN.md forbids rendering a bare
        count of sources, because "3 sources" invites reading count as strength
        and three weak records do not outrank one authoritative one. So this
        returns which file, out of which system, pulled when, and exactly which
        lines, and never a number standing on its own.
        """
        seen = {}
        for citation in self.all_citations():
            if citation.authority != RECORDED:
                continue
            entry = seen.setdefault(citation.source_file, {
                "source_file": citation.source_file,
                "system_of_record": citation.system_of_record,
                "retrieved_at": citation.retrieved_at,
                "rows": set()})
            entry["rows"].add(citation.row)
        return tuple(dict(entry, rows=tuple(sorted(entry["rows"])))
                     for _, entry in sorted(seen.items()))

    def as_text(self):
        """The record as plain text, for pasting into a review memo intact.

        Carries the locator for every cited row, which is what makes the chain
        walkable in the other direction: given a raw line, a reviewer can find
        which claims used it by searching the exports for `file:row`.
        """
        lines = [f"evidence for {self.part_number}", ""]
        for entry in self.sources_used():
            rows = ", ".join(str(row) for row in entry["rows"])
            label = "rows" if len(entry["rows"]) > 1 else "row"
            lines.append(f"  {entry['source_file']}  "
                         f"{entry['system_of_record']}, retrieved "
                         f"{entry['retrieved_at']}, {label} {rows}")
        lines.append("")
        for citation in self.all_citations():
            where = citation.locator or f"derived: {citation.derived_from}"
            lines.append(f"  {citation.field} = {citation.value}   [{where}]")
            if citation.transformation:
                lines.append(f"      transformation: {citation.transformation}")
        for transformation in self.transformations:
            lines.append("")
            lines.append(f"  {transformation.rule}")
            lines.append(f"      original: {transformation.original!r}")
            lines.append(f"      resolved: {transformation.resolved!r}")
        for contradiction in self.contradictions:
            lines.append("")
            lines.append(f"  sources disagree on {contradiction.field} for "
                         f"{contradiction.subject}; both are shown and neither "
                         f"is chosen:")
            for citation in contradiction.citations:
                lines.append(f"      {citation.value}   [{citation.locator}]")
        for kind, subject in self.absences:
            lines.append("")
            lines.append(f"  {subject} [{kind}]")
        return "\n".join(lines) + "\n"


def _provenance(extracts, source_file):
    """The manifest entry for a file, or a refusal.

    REFUSED AT CONSTRUCTION rather than defaulted, in the same spirit as
    `Row.__post_init__`. A missing manifest row would otherwise render as a
    blank as-of, and a blank date beside a value reads as "no transformation
    happened recently" rather than as "nobody knows". `tests/test_provenance.py`
    asserts the manifest describes every input file, so this cannot fire in a
    dataset the generator produced; it fires for one somebody assembled by hand.
    """
    if source_file not in extracts:
        raise ValueError(
            f"{source_file} has no row in the extract manifest, so a citation "
            f"to it could state no system of record and no as-of; the panel "
            f"would print a blank where a reviewer expects a date")
    return extracts[source_file]


def _cite(extracts, source_file, row, field, value, transformation=""):
    system, retrieved_at = _provenance(extracts, source_file)
    return Citation(field=field, value=str(value), source_file=source_file,
                    row=row, system_of_record=system, retrieved_at=retrieved_at,
                    authority=RECORDED, transformation=transformation)


def _lead_times_by_key(lead_time_records):
    """Group lead time rows by canonical supplier key, KEEPING ALL OF THEM.

    The previous version built a dict comprehension keyed by canonical key, so
    two rows that canonicalise together silently kept the last one and the panel
    showed a quoted lead time without ever saying another row disagreed. Nothing
    in the shipped dataset triggers it, which is what made it a latent trap
    rather than a live defect: the first duplicate vendor pair to carry two lead
    time rows would have had one of them disappear with three guards saying the
    evidence was complete.
    """
    from ..normalise import canonical_key

    grouped = {}
    for name, quoted, p95, row in sorted(lead_time_records):
        grouped.setdefault(canonical_key(name), []).append(
            (name, quoted, p95, row))
    return grouped


def evidence_for(part_number, supplier_records, exploded_rows, demand_plan,
                 lead_time_records, extracts, demand_row_numbers):
    """Assemble the workings from the same inputs the pipeline consumed.

    `supplier_records` are (name_as_spelled, region, row) rows of suppliers.csv;
    `lead_time_records` are (name_as_spelled, quoted, p95, row) rows of
    lead_times.csv; `extracts` is the manifest read from sources.csv.

    THE JOIN IS SHOWN, NOT ASSUMED. The two files spell the same supplier
    differently, so the lead time is matched by canonical key exactly as stage 3
    does, and where the raw strings differ a note records both spellings. That
    cross-file join is the single most load-bearing inference in the pipeline
    and it is the thing a reviewer most needs to be able to check.
    """
    from ..normalise import canonical_key

    grouped_lead_times = _lead_times_by_key(lead_time_records)

    # WITHIN ONE FILE, TWO ROWS CAN BE ONE SUPPLIER. That is the duplicate
    # vendor record, and unlike the cross-file merge it changes the supplier
    # COUNT, which is the number the verdict turns on. A reviewer counting rows
    # in the panel gets two where the sentence says one, so the collapse is
    # stated rather than left to be inferred from the arithmetic.
    supplier_keys = {}
    for name, _region, _row in sorted(supplier_records):
        supplier_keys.setdefault(canonical_key(name), []).append(name)

    transformations, contradictions = [], []
    for key, names in sorted(supplier_keys.items()):
        if len(names) > 1:
            transformations.append(Transformation(
                kind=DUPLICATE_VENDOR_MERGE,
                original=" / ".join(names),
                # THE CANONICAL KEY, NOT THE FIRST SPELLING. `names[0]` is
                # whichever string sorted first, which is arbitrary and would
                # read as the system having preferred one vendor record over
                # the other. The key is what the merge actually resolved to.
                resolved=key,
                rule=(f"{len(names)} rows of {SUPPLIERS_FILE} name one "
                      f"supplier and were counted once, because they are "
                      f"identical after case, punctuation and abbreviation are "
                      f"normalised"),
                certain=True))

    supplier_rows, join_notes = [], []
    for name, region, row in sorted(supplier_records):
        candidates = grouped_lead_times.get(canonical_key(name), [])
        matched = candidates[0] if candidates else None
        transformation = ""
        if matched and matched[0] != name:
            transformation = (f"{matched[0]!r} in {LEAD_TIMES_FILE} resolved "
                              f"to {name!r} in {SUPPLIERS_FILE}")
            join_notes.append(
                f"the lead time for {name!r} was matched to the row spelled "
                f"{matched[0]!r} in lead_times.csv, because the two files "
                f"spell the same supplier differently")
            transformations.append(Transformation(
                kind=CROSS_FILE_MERGE, original=matched[0], resolved=name,
                rule=(f"the two files spell one supplier differently; they "
                      f"were joined on the key they share after case, "
                      f"punctuation and abbreviation are normalised"),
                certain=True))

        # BOTH RECORDS, NEVER A CHOICE. Two lead time rows for one supplier
        # that disagree are a question this tool has no basis to settle, so it
        # shows them and declines. Picking the first silently would be the
        # system answering a question it cannot answer.
        if len({(quoted, p95) for _n, quoted, p95, _r in candidates}) > 1:
            contradictions.append(Contradiction(
                field=QUOTED_LEAD_TIME_DAYS, subject=name,
                citations=tuple(
                    _cite(extracts, LEAD_TIMES_FILE, candidate_row,
                          QUOTED_LEAD_TIME_DAYS, quoted)
                    for _n, quoted, _p95, candidate_row in candidates)))

        citations = [
            _cite(extracts, SUPPLIERS_FILE, row, SUPPLIER_NAME, name),
            _cite(extracts, SUPPLIERS_FILE, row, SUPPLIER_REGION, region),
        ]
        if matched:
            citations.append(_cite(
                extracts, LEAD_TIMES_FILE, matched[3], QUOTED_LEAD_TIME_DAYS,
                matched[1], transformation=transformation))
            citations.append(_cite(
                extracts, LEAD_TIMES_FILE, matched[3], LEAD_TIME_P95_DAYS,
                matched[2], transformation=transformation))

        supplier_rows.append(SupplierRow(
            supplier_name=name, region=region, has_lead_time=matched is not None,
            quoted_lead_time_days=matched[1] if matched else None,
            p95_lead_time_days=matched[2] if matched else None,
            citations=tuple(citations)))

    demand_rows = []
    for row in sorted(exploded_rows, key=lambda r: r.finished_good):
        annual = demand_plan.get(row.finished_good)
        contribution = ("" if annual is None
                        else _plain(row.qty_per_finished_good * annual))
        citations = []
        if annual is not None:
            citations.append(_cite(
                extracts, DEMAND_FILE, demand_row_numbers[row.finished_good],
                ANNUAL_UNITS, annual))
            # THE PRODUCT IS DERIVED AND SAYS SO. It appears in no file, so it
            # cites no line: a locator pointing at a row that does not contain
            # the number is worse than none, because a reviewer who follows it
            # finds a different figure and does not know which is wrong.
            citations.append(Citation(
                field="contribution", value=contribution, authority=DERIVED,
                derived_from=(f"{QTY_PER_PARENT} through the bill of materials "
                              f"× {ANNUAL_UNITS} from {DEMAND_FILE}")))
        demand_rows.append(DemandRow(
            finished_good=row.finished_good,
            qty_per_finished_good=_plain(row.qty_per_finished_good),
            annual_units=annual, contribution=contribution,
            citations=tuple(citations)))

    quotable = [row for row in supplier_rows if row.has_lead_time]
    used = min(quotable, key=lambda row: row.quoted_lead_time_days) \
        if quotable else None
    lead_time_citations = tuple(
        c for c in (used.citations if used else ())
        if c.source_file == LEAD_TIMES_FILE)

    # ABSENT EVIDENCE IS A STATE, NOT AN EMPTY PANEL, and the manifest is what
    # made the state sayable. "No supplier rows" used to be indistinguishable
    # from "nobody has looked"; now the panel can say the approved vendor list
    # was pulled on a date and has no row for this part, which is `no record` in
    # DESIGN.md's vocabulary rather than an unexplained gap.
    absences = []
    if not supplier_rows:
        system, retrieved_at = _provenance(extracts, SUPPLIERS_FILE)
        absences.append((
            "no_record",
            f"the {system} was retrieved {retrieved_at} and has no row for "
            f"this part"))
    if not quotable and supplier_rows:
        system, retrieved_at = _provenance(extracts, LEAD_TIMES_FILE)
        absences.append((
            "no_record",
            f"the {system} was retrieved {retrieved_at} and has no row for "
            f"any supplier on this part"))
    for absent_good in sorted(row.finished_good for row in demand_rows
                              if row.annual_units is None):
        system, retrieved_at = _provenance(extracts, DEMAND_FILE)
        absences.append((
            "no_record",
            f"the {system} was retrieved {retrieved_at} and has no row for "
            f"{absent_good}"))

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
                    notes=tuple(notes),
                    transformations=tuple(transformations),
                    contradictions=tuple(contradictions),
                    absences=tuple(absences),
                    lead_time_citations=lead_time_citations)


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
    """One thing this page did not assess, and WHICH KIND of not-assessed it is.

    `kind` exists because the kinds are not interchangeable and a reader who
    cannot tell them apart will collapse them. A part whose supplier list is
    unresolved is not the same as a part the question does not attach to, and
    neither is the same as a threshold nobody has set. The painter needs the
    distinction to label the absence; the sentence alone leaves it implicit.
    """
    subject: str
    count: int
    sentence: str
    kind: str = ""


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
                "unplaceable", len(report.unplaceable_parts)),
            kind="unplaceable"))

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
                                          dimension=dimension),
            kind="not_applicable"))

    if not thresholds:
        notes.append(CoverageNote(
            subject="magnitude archetypes disabled", count=0,
            sentence=render_coverage_note("no_thresholds", 0),
            kind="no_thresholds"))

    return Coverage(heading="What this page does not cover",
                    notes=tuple(notes))


# ---------------------------------------------------- structural views -----
# TOPOLOGY, NOT MAGNITUDE. Both views below encode WHICH, never HOW MUCH. A mark
# is present or absent and every mark is identical, so nothing here can be read
# as a quantity, a rank or a severity. That is the whole reason they are
# permissible: a bar, a gauge or a colour ramp would encode magnitude as length
# or intensity across incommensurable units, which is the composite this system
# spent eight stages refusing to compute, arriving through the picture instead
# of through the arithmetic.

MARK = "x"


def blocking_matrix(part_numbers, evidence_by_part):
    """Which finished goods each part can stop.

    Returns (finished_goods, rows). Makes blast radius legible at a glance
    without ranking anything: a part blocking three products has three marks,
    and the reader does the comparison rather than the system.
    """
    parts = ranking.in_default_order(part_numbers)
    goods = sorted({row.finished_good for part in parts
                    for row in evidence_by_part[part].demand_rows})
    matrix = []
    for part in parts:
        blocks = {row.finished_good for row in evidence_by_part[part].demand_rows}
        entry = {"part": part}
        entry.update({good: (MARK if good in blocks else "") for good in goods})
        matrix.append(entry)
    return tuple(goods), tuple(matrix)


def cluster_membership(report):
    """Which parts sit with which supplier and which region.

    One row per part in a concentrated cluster, so a reviewer confirming a
    grouping can see the grouping rather than read about it. Nominal throughout:
    the cells are identifiers.
    """
    supplier_of, region_of = {}, {}
    for cluster in report.concentrated():
        for member in cluster.members:
            target = supplier_of if cluster.basis == "supplier" else region_of
            target.setdefault(member, cluster.key)
    parts = ranking.in_default_order(set(supplier_of) | set(region_of))
    return tuple({"part": part,
                  "supplier": supplier_of.get(part, ""),
                  "region": region_of.get(part, "")} for part in parts)


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
    evidence_by_part: dict = field(default_factory=dict)

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
                   layers=tuple(layers), evidence_by_part=dict(evidence_by_part),
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
