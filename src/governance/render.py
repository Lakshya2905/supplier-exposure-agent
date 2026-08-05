"""Turn a decision event into a sentence a person can read.

STORE STRUCTURED, RENDER PROSE, NEVER STORE THE PROSE. Nothing here writes back
into the log. A log that stored its own sentences could never be re-rendered
when the wording improved, and the wording is a deliverable: this output is
what appears in the stage 7 review interface and in any demo. It is not a debug
view and should not read like one.

Every rendered event answers, in order:

  which part          the subject
  what verdict        what the system concluded, and under which reading
  the two raw strings the actual text from the actual files
  score and threshold how close the match was, against what bar
  why they disagreed  what would have changed if the merge went the other way
  what a human did    the decision, its author, and the reason code
  resulting verdict   what stands now

An event that cannot answer one of these omits that clause rather than
inventing it. A renderer that fabricates a plausible number is worse than one
that says nothing.
"""
from . import (ACT_RESOLVE_CONFLICT,
               EXECUTES, KIND_CLUSTER_CONTINGENT, KIND_CLUSTER_FLAGGED,
               KIND_DIMENSION_ABSTAINED, KIND_DIMENSION_SCORED,
               KIND_PART_RANKED,
               KIND_HUMAN_DECISION, KIND_MERGE_UNCERTAIN,
               KIND_READINGS_DISAGREE, KIND_VERDICT_ASSIGNED,
               STATUS_APPROVED, STATUS_PROPOSED, STATUS_REJECTED,
               STATUS_SUPERSEDED)

DIMENSION_PROSE = {
    "lead_time_to_recover": "lead time to recover",
    "blast_radius": "blast radius",
    "buffer_cover": "buffer cover",
    "portability": "portability",
    "concentration": "concentration",
}

# Concentration reports a count of parts, so the dimension renderer needs the
# unit to read naturally: "3 parts", not "3 parts parts".

# What each completeness state means in words. A bound says which DIRECTION it
# is wrong in, because "incomplete" alone is the thing that lets a reader take
# an upper bound for a lower one.
COMPLETENESS_PROSE = {
    "known": "",
    "upper_bound": "an upper bound",
    "lower_bound": "a lower bound",
    "cannot_tell": "not answerable from the data",
    "no_recovery_path": "undefined because there is no recovery path at all",
    "not_applicable": "not applicable to this part",
}

VERDICT_PROSE = {
    "single_source": "one qualified supplier",
    "single_source_no_lead_time": "one qualified supplier, no lead time on file",
    "multi_source": "more than one qualified supplier",
    "multi_source_no_lead_times": "several suppliers, none with a lead time",
    "hidden_single_source": "several suppliers on paper, only one quotable",
    "no_qualified_supplier": "no qualified supplier, and the list was checked",
    "supplier_list_unknown": "supplier list unconfirmed",
    "made_in_house": "made in-house",
    "readings_disagree": "two defensible readings that disagree",
}

STATUS_PROSE = {
    STATUS_PROPOSED: "raised for review",
    STATUS_APPROVED: "accepted",
    STATUS_REJECTED: "rejected",
    STATUS_SUPERSEDED: "superseded",
}


def _sentence_case(text):
    """Uppercase the first character only.

    str.capitalize() lowercases everything after it, which corrupts a reviewer
    name like "r.okafor" into "R.okafor" and an ISO timestamp's "T" into "t".
    Both appear verbatim in this output, so this is data corruption in a
    deliverable rather than a cosmetic slip.
    """
    return text[:1].upper() + text[1:] if text else text


def describe_verdict(verdict):
    """Plain words for a verdict, falling back to the code itself.

    An unmapped verdict renders as its raw code rather than as a guess. Silence
    is recoverable; a wrong sentence in a review interface is not.
    """
    if not verdict:
        return ""
    prose = VERDICT_PROSE.get(verdict)
    return f"{prose} ({verdict})" if prose else verdict


def _subject_clause(event):
    return f"{event.sku_id}"


def _strings_clause(evidence):
    left, right = evidence.get("raw_a"), evidence.get("raw_b")
    if not (left and right):
        return ""
    return f"two rows spell a supplier {left!r} and {right!r}"


def _score_clause(evidence):
    score, threshold = evidence.get("score"), evidence.get("threshold")
    if score is None:
        return ""
    if threshold is None:
        return f"matching at {score:.2f}"
    verb = "meets" if score >= threshold else "falls short of"
    return f"matching at {score:.2f}, which {verb} the {threshold:.2f} threshold"


def _readings_clause(evidence):
    merged = evidence.get("verdict_if_merged")
    apart = evidence.get("verdict_if_separate")
    if not (merged and apart):
        return ""
    if merged == apart:
        return (f"both readings agree on {describe_verdict(merged)}")
    return (f"treated as one supplier the part is "
            f"{describe_verdict(merged)}; treated as two it is "
            f"{describe_verdict(apart)}")


def _make_readings_clause(evidence):
    """The make-flag contradiction, which is NOT the merge contradiction.

    A make part carrying supplier rows has two honest readings, and under both
    of them `verdict_if_merged` and `verdict_if_separate` read READINGS_DISAGREE
    identically. Rendering from those fields produces "both readings agree on
    two defensible readings that disagree", which is nonsense. The concrete
    readings live in stale_flag and dual_mode, so they are what gets rendered.
    """
    stale, dual = evidence.get("stale_flag"), evidence.get("dual_mode")
    if not (stale and dual):
        return ""
    return (f"read as a stale make flag the part is {describe_verdict(stale)}; "
            f"read as genuine in-house capability alongside its suppliers it is "
            f"{describe_verdict(dual)}")


def _decision_clause(event):
    if not event.decided_by:
        return ""
    # Lead with the verb, not the name. Sentence-casing a clause that starts
    # with "r.okafor" would emit "R.okafor", and a username is an identifier
    # rather than a word: changing its case makes the log output stop matching
    # a search for the person who made the decision.
    clause = (f"{STATUS_PROSE.get(event.status, event.status)} by "
              f"{event.decided_by}")
    # (see _act_opening for why the arity is rendered and not only counted)
    # TIME BELONGS IN THE RECORD, NOT IN THE SENTENCE, and this is a
    # determinism constraint rather than a wording preference. Every sentence
    # this module produces is golden-pinned, so a real clock reaching this line
    # would make the goldens either frozen at a fake time or meaningless. The
    # timestamp is carried on `DecisionEvent.at` and read directly by whatever
    # displays the log, which keeps `render` a pure function of structure.
    if event.reason_code:
        clause += f", reason: {event.reason_code}"
    if event.note:
        clause += f" ({event.note})"
    # A CORRECTION CITES THE LINE IT CORRECTS. The log is append-only, so a
    # reviewer who changes their mind produces a second judgment rather than an
    # edit, and without this reference two contradictory sentences about one
    # subject sit in the list with nothing saying which one stands.
    replaces = (event.evidence or {}).get("replaces")
    if replaces:
        clause += f", replacing decision {replaces}"
    return clause


def _outcome_clause(evidence):
    resulting = evidence.get("resulting_verdict")
    if not resulting:
        return ""
    return f"the verdict now stands at {describe_verdict(resulting)}"


def _dimension_clause(event, evidence):
    """One dimension on one part, with its unit and its bound direction.

    THE UNIT IS ALWAYS RENDERED ALONGSIDE THE NUMBER. A bare figure in a review
    interface is the first step toward somebody adding it to the one beside it,
    and these measures are deliberately not addable.
    """
    dimension = evidence.get("dimension", event.field)
    name = DIMENSION_PROSE.get(dimension, dimension)
    completeness = evidence.get("completeness", "")
    qualifier = COMPLETENESS_PROSE.get(completeness, completeness)

    if event.kind == KIND_DIMENSION_ABSTAINED:
        sentence = f"{event.sku_id}: {name} is {qualifier or 'not answerable'}"
    elif not event.value:
        sentence = f"{event.sku_id}: {name} is {qualifier}" if qualifier \
            else f"{event.sku_id}: {name} was scored"
    else:
        unit = evidence.get("unit", "")
        measure = f"{event.value} {unit}" if unit and unit != "categorical" \
            else f"{event.value}"
        sentence = f"{event.sku_id}: {name} is {measure}"
        if qualifier:
            sentence += f", {qualifier}"

    reasons = evidence.get("reasons") or []
    if reasons:
        sentence += f", because {reasons[0]}"
    return sentence + "."


BASIS_PROSE = {
    "supplier": "depend on this supplier",
    "region": "are sourced from this region",
}


def _cluster_clause(event, evidence):
    """A cluster, WITH ITS MEMBERS NAMED.

    The membership is the finding and the count is only its summary. Nine parts
    on one supplier where seven are long lead is a different decision from nine
    catalogue parts, and a reviewer needs to see which parts at the moment they
    decide whether to act, not a number they have to go and expand.
    """
    members = evidence.get("members") or []
    basis = evidence.get("basis", "")
    verb = BASIS_PROSE.get(basis, "share this dependency")
    listing = ", ".join(members)

    if event.kind == KIND_CLUSTER_CONTINGENT:
        opening = (f"{event.sku_id}: {len(members)} exposed parts would {verb} "
                   f"only if an unresolved supplier name merge is confirmed")
    else:
        opening = f"{event.sku_id}: {len(members)} exposed parts {verb}"
    if listing:
        opening += f" ({listing})"

    parts = [opening + "."]
    reasons = evidence.get("reasons") or []
    if reasons:
        parts.append(_sentence_case(reasons[0]) + ".")
    # THE CEILING, said out loud every time. A reviewer who is never told that
    # the grouping is a choice will read it as a measurement.
    parts.append("Grouping parts by " + (basis or "this dependency") +
                 " is a modelling judgment rather than a fact, so this is "
                 "recommended for confirmation and is never applied "
                 "automatically.")
    return " ".join(parts)


# THE ONLY PLACE ROUNDING HAPPENS. Quantities stay exact Fractions from stage 2
# to here, so nothing accumulates drift across a three-level explosion.
def _measure(value):
    if isinstance(value, list) and len(value) == 2 and all(
            isinstance(part, int) for part in value):
        numerator, denominator = value
        if denominator == 1:
            return str(numerator)
        return f"{numerator / denominator:.1f}"
    return str(value)


# BOUND DIRECTION IN WORDS. Rendering an upper bound as a bare number is a lie
# by omission: "11 days of cover" reads as a measurement when the true figure
# could be anything below it. This is where carrying the direction since stage 4
# is paid out, and a reader who never sees "at most" has no way to recover it.
BOUND_WORDS = {
    "upper_bound": "at most ",
    "lower_bound": "at least ",
}

RANKED_CLAUSE = {
    "lead_time_to_recover": "{measure} days quoted lead time",
    "buffer_cover": "{prefix}{measure} days of cover",
    "blast_radius": "blocks {prefix}{measure} finished good units",
    "portability": "{measure}-owned tooling",
    "concentration": "correlated with {measure} other exposed parts",
}

RANKED_ABSENT = {
    "lead_time_to_recover": {
        "cannot_tell": "no quotable lead time on file",
        "no_recovery_path": "no recovery path at all",
        "not_applicable": "made in-house, so no purchase lead time",
    },
    "buffer_cover": {
        "cannot_tell": "no on-hand record, so cover is unknown",
    },
    "portability": {
        "cannot_tell": "no tooling owner recorded",
    },
    "concentration": {
        "cannot_tell": "correlation depends on an unresolved supplier merge",
        "not_applicable": "nobody to be correlated with",
    },
}


def _blocked_volume_absent(clause):
    """The structural reach, when the volume behind it could not be counted.

    "blocks at least 0 finished good units" was a true statement carrying no
    information: zero is the trivial lower bound of any non-negative quantity, so
    the bound prefix promised a figure and then delivered nothing. Worse, in every
    occurrence it sat beside a correct example of the opposite treatment, "no
    on-hand record, so cover is unknown", forty characters away. One absence in
    words, one absence as the number zero, in the same sentence.

    THE MODEL WAS NEVER WRONG. `blast_radius` carries two facets: the structural
    reach, which is KNOWN, and the blocked volume, which inherits the demand
    plan's gaps. Its own reason text says so. The renderer was rendering only the
    volumetric facet, so a part that certainly stops a finished good read as
    blocking nothing. Rendering this as a plain absence would have discarded the
    known facet too, which is why the fix names the reach.

    Keyed on `usage_completeness`, the branch that set the completeness, NEVER on
    `value == 0`. Partial usage whose recorded goods total zero is a recorded
    zero, and reading that as an absence is the same missing-versus-zero collapse
    this function exists to prevent.
    """
    # The literal, matching this module's existing convention for completeness
    # values (see RANKED_ABSENT). Importing src.demand here would add a layer
    # dependency from the renderer to the model for one string; a test pins the
    # correspondence instead, so drift is loud.
    detail = clause.get("detail") or {}
    if detail.get("usage_completeness") != "cannot_tell":
        return ""
    goods = detail.get("finished_goods_blocked")
    if not goods:
        return ""
    plural = "" if goods == 1 else "s"
    return (f"blocks {goods} finished good{plural}, "
            f"{'' if goods == 1 else 'all '}absent from the demand plan, so no "
            f"units could be counted")


def _ranked_clause(clause):
    """One clause of the ranked sentence, with its unit and its bound direction.

    An absent value renders as WORDS, never as a blank or a zero. A gap in a
    sentence invites the reader to substitute zero, and zero is both a real
    measurement and the worst one.
    """
    dimension = clause["dimension"]
    completeness = clause.get("completeness", "")
    if completeness in RANKED_ABSENT.get(dimension, {}):
        return RANKED_ABSENT[dimension][completeness]

    value = clause.get("value")
    if value is None:
        return ""
    if dimension == "lead_time_to_recover":
        detail = clause.get("detail") or {}
        quoted, p95 = detail.get("quoted_days"), detail.get("p95_days")
        if quoted is None:
            return ""
        return f"{quoted} days quoted lead time ({p95} at p95)"
    if dimension == "buffer_cover" and value == "unbounded":
        return "unbounded cover, nothing consuming it"
    if dimension == "concentration" and clause.get("value") in (1, None):
        return ""
    if dimension == "blast_radius":
        absent = _blocked_volume_absent(clause)
        if absent:
            return absent

    prefix = BOUND_WORDS.get(completeness, "")
    return RANKED_CLAUSE[dimension].format(
        prefix=prefix, measure=_measure(value))


def _ranked_sentence(event, evidence):
    parts = [f"{event.sku_id}: "
             f"{describe_verdict(evidence.get('verdict', ''))}"]
    for clause in evidence.get("clauses", []):
        rendered = _ranked_clause(clause)
        if rendered:
            parts.append(rendered)
    sentence = ", ".join(part for part in parts if part) + "."

    names = evidence.get("archetypes") or []
    if names:
        sentence += (" This matches " + ", ".join(names) + ".")
    return sentence


def render(event):
    """One event, one readable paragraph. Never stored, always recomputed."""
    evidence = event.evidence or {}
    parts = []

    if event.kind == KIND_MERGE_UNCERTAIN:
        opening = f"{_subject_clause(event)}: " + (
            _strings_clause(evidence) or "a supplier name match is uncertain")
        score = _score_clause(evidence)
        if score:
            opening += f", {score}"
        parts.append(opening + ".")
        readings = _readings_clause(evidence)
        if readings:
            parts.append(_sentence_case(readings) +
                         ", so the merge was routed for review rather than "
                         "decided automatically.")

    elif event.kind == KIND_READINGS_DISAGREE:
        parts.append(f"{_subject_clause(event)}: the part is flagged make but "
                     f"carries supplier rows, and the two readings of that "
                     f"contradiction disagree.")
        readings = _make_readings_clause(evidence) or _readings_clause(evidence)
        if readings:
            parts.append(_sentence_case(readings) + ".")
        parts.append("No field in the data settles it, so it was routed for "
                     "review rather than decided automatically.")

    elif event.kind == KIND_VERDICT_ASSIGNED:
        verdict = evidence.get("resulting_verdict") or event.value
        sentence = f"{_subject_clause(event)}: {describe_verdict(verdict)}"
        if evidence.get("autonomy") == EXECUTES:
            sentence += ", decided automatically because no uncertain match " \
                        "could change it"
        parts.append(sentence + ".")

    elif event.kind == KIND_HUMAN_DECISION:
        opening = _strings_clause(evidence) or _act_opening(event)
        parts.append(f"{_subject_clause(event)}: {opening}.")
        score = _score_clause(evidence)
        if score:
            parts.append("The system had them " + score + ".")
        decision = _decision_clause(event)
        if decision:
            parts.append(_sentence_case(decision) + ".")
        outcome = _outcome_clause(evidence)
        if outcome:
            parts.append(_sentence_case(outcome) + ".")

    elif event.kind in (KIND_DIMENSION_SCORED, KIND_DIMENSION_ABSTAINED):
        parts.append(_dimension_clause(event, evidence))

    elif event.kind in (KIND_CLUSTER_FLAGGED, KIND_CLUSTER_CONTINGENT):
        parts.append(_cluster_clause(event, evidence))

    elif event.kind == KIND_PART_RANKED:
        parts.append(_ranked_sentence(event, evidence))

    else:  # pragma: no cover - EVENT_KINDS is closed and validated on append
        parts.append(f"{_subject_clause(event)}: {event.kind}.")

    return " ".join(p for p in parts if p)


def _act_opening(event):
    """What kind of act this was, and over how many members.

    ONE ACT OVER N MEMBERS IS THE POINT OF A CLUSTER DECISION. The model refuses
    to flatten a cluster to its parts precisely so that a reviewer confirms one
    judgment once instead of once per member, and `member_count` is the field
    carrying that. A renderer that drops it undoes at the point of display what
    the model is built to protect, which is the same failure as a palette that
    ranks perceptually while the arithmetic says it cannot: the guarantee holds
    everywhere except where somebody reads it.

    `bulk_approve` differs from `approve` only in arity, so the count carries the
    act kind for those two. `resolve_conflict` is a different act and is named.
    """
    if event.act_kind == ACT_RESOLVE_CONFLICT:
        return "a conflict between two readings was resolved by review"
    if event.member_count > 1:
        return (f"one review decision covering {event.member_count} members "
                f"was recorded")
    return "a review decision was recorded"


def render_all(log):
    return [render(event) for event in log]


# ---------------------------------------------- wording with no event ------
# The work queue and the coverage panel are not decisions, so they have no
# decision event and cannot be rendered from one. Their wording lives here
# anyway, because this module is where user-facing sentences are written and
# golden-pinned, and splitting it would let two vocabularies drift apart.

FIELD_PROSE = {
    "on_hand_units": "an on-hand count",
    "tooling_owner": "a tooling owner",
    "verdict": "a confirmed supplier list",
    "concentration": "a resolved supplier name merge",
    "lead_time_to_recover": "a lead time record",
}

ARCHETYPE_PROSE = {
    "resourcing_trap": "the resourcing trap",
    "correlated_resourcing_trap": "the correlated resourcing trap",
    "counted_empty_single_source": "single source, counted empty",
    "no_quotable_single_source": "single source, nobody quoting",
    "nobody_to_call": "nobody to call",
    "headline_exposure": "single source, long lead, thin cover, supplier tooling",
    "long_lead_single_source": "single source on a long lead time",
}


def render_field_request(field_name, part_count, archetype_names):
    """One trip to one system of record. THE ROW IS THE FIELD, NOT THE PART.

    Says what fetching it would settle, never what the value is likely to be.
    Nothing here imputes: the sentence describes a question, not a forecast.
    """
    described = FIELD_PROSE.get(field_name, field_name)
    patterns = ", ".join(ARCHETYPE_PROSE.get(name, name)
                         for name in archetype_names)
    plural = "part" if part_count == 1 else "parts"
    return (f"Fetching {described} for {part_count} {plural} would settle "
            f"whether they match {patterns}.")


COVERAGE_PROSE = {
    "unplaceable": (
        "{count} parts have an unconfirmed or unresolved supplier list, so they "
        "could belong to any cluster here and every membership count on this "
        "page is a lower bound."),
    "not_applicable": (
        "{count} parts are not applicable for {dimension}, meaning the question "
        "does not attach to them rather than that the answer is no."),
    "no_thresholds": (
        "Magnitude archetypes are off. No threshold is set for long lead or "
        "thin cover, and the system will not choose one. Set them in "
        "config/archetypes.yaml, where the number is owned and versioned."),
    "catalogue": (
        "Which conjunctions are worth naming is a modelling judgment, so the "
        "catalogue is confirmed once here rather than once per part."),
}


def render_coverage_note(kind, count, dimension=""):
    """Neutral by construction.

    These are properties of the data and of deliberate design decisions, not
    faults. Phrasing them as warnings would train a reader to dismiss them, and
    the panel exists precisely so that what was not assessed is as visible as
    what was.
    """
    template = COVERAGE_PROSE.get(kind, "")
    return template.format(count=count,
                           dimension=DIMENSION_PROSE.get(dimension, dimension))
