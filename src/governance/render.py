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

THE VOCABULARY IS A PLANNER'S, NOT A MODELLER'S, and that is a correctness
property rather than a courtesy. The test applied to every string below is
whether a procurement analyst with no statistics background reads it once and
knows what to do next. "Abstains instead of imputing" is precise and tells that
reader nothing; "we do not have this data, so this part is not scored on it"
tells them the same fact and what it means for them.

WHAT DID NOT GET SIMPLIFIED, AND WHY. Bound direction survives intact. An upper
bound reads "at most" and a lower bound reads "at least", and they are never
softened into a shared word like "about" or "roughly". The whole system turns on
those two pointing opposite ways from the identical missing row: unrecorded
demand can only REDUCE cover and can only ADD to what is blocked. A reader who
cannot tell which way a figure is wrong has been given a number and no way to
use it, which is worse than plain-sounding prose that means nothing.
"""
from . import (ACT_RESOLVE_CONFLICT,
               EXECUTES, KIND_CLUSTER_CONTINGENT, KIND_CLUSTER_FLAGGED,
               KIND_DIMENSION_ABSTAINED, KIND_DIMENSION_SCORED,
               KIND_PART_RANKED,
               KIND_HUMAN_DECISION, KIND_MERGE_UNCERTAIN,
               KIND_READINGS_DISAGREE, KIND_VERDICT_ASSIGNED,
               STATUS_APPROVED, STATUS_PROPOSED, STATUS_REJECTED,
               STATUS_SUPERSEDED)

# WHAT THE MEASURE IS, IN THE WORDS SOMEBODY WOULD USE TO ASK FOR IT. The old
# names were the modelling names: blast radius, buffer cover, portability. Each
# is exact, each is a term of art, and none of them says what a reader should do
# about it.
DIMENSION_PROSE = {
    "wait_out_days": "how long until parts flow again from this supplier",
    "resource_days": "how long to get a new supplier approved",
    "blast_radius": "how much of the build stops",
    "buffer_cover": "how long current stock lasts",
    "portability": "how hard it is to move to another supplier",
    "concentration": "how many other parts share this supplier or region",
}

# Concentration reports a count of parts, so the dimension renderer needs the
# unit to read naturally: "3 parts", not "3 parts parts".

# What each completeness state means in words. A bound says which DIRECTION it
# is wrong in, because "incomplete" alone is the thing that lets a reader take
# an upper bound for a lower one.
# A BOUND WRAPS THE FIGURE RATHER THAN TRAILING IT. "11 days, an upper bound"
# puts the correction after the number, where a reader has already taken the
# number; "at most 11 days, and possibly less" cannot be read the wrong way
# because the qualifier arrives first. The direction is never softened into a
# shared word: which way a figure is wrong is the whole of its usefulness.
BOUND_SENTENCE = {
    "upper_bound": ("at most ", ", and possibly less"),
    "lower_bound": ("at least ", ", and possibly more"),
}

COMPLETENESS_PROSE = {
    "known": "",
    "upper_bound": "at most this, and possibly less",
    "lower_bound": "at least this, and possibly more",
    "cannot_tell": "not enough data to say",
    # NARROWED with the recovery split. This state is reached only by
    # `wait_out_days`, and what an empty supplier list rules out is the waiting,
    # not the recovering: the resourcing chain is precisely the path such a part
    # still has, and it is reported beside this.
    "no_recovery_path": "not a number: there is no supplier to wait for",
    "not_applicable": "not a question that applies to this part",
}

VERDICT_PROSE = {
    "single_source": "one supplier",
    "single_source_no_lead_time": "one supplier, and no lead time on file",
    "multi_source": "more than one supplier",
    "multi_source_no_lead_times":
        "several suppliers, and no lead time on file for any of them",
    "hidden_single_source":
        "several suppliers listed, only one can actually quote",
    "no_qualified_supplier":
        "no supplier on file, and somebody checked the list",
    "supplier_list_unknown": "nobody has confirmed the supplier list",
    "made_in_house": "made in-house",
    "readings_disagree": "the data supports two different readings",
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


def describe_verdict(verdict, with_code=False):
    """Plain words for a verdict, falling back to the code itself.

    An unmapped verdict renders as its raw code rather than as a guess. Silence
    is recoverable; a wrong sentence in a review interface is not.

    `with_code` IS OFF BY DEFAULT AND ON FOR THE DUAL READINGS, which is a
    distinction about who is reading. A planner working the exposure list does
    not need "(hidden_single_source)" after the sentence that already says
    several suppliers are listed and only one can quote; the code is noise that
    survives every reading. A reviewer resolving a merge is comparing two
    readings AS readings, and the code is the key those readings join on in the
    verdict table, so dropping it there would take away the thing being
    compared.
    """
    if not verdict:
        return ""
    prose = VERDICT_PROSE.get(verdict)
    if not prose:
        return verdict
    return f"{prose} ({verdict})" if with_code else prose


def display_subject(subject):
    """An internal key, spelled the way a person reads it.

    THE KEY IS NEVER REWRITTEN, ONLY PRESENTED. `south_asia` is the identity a
    cluster is decided against and every row of the decision log joins on that
    exact string; changing it to make a sentence read well would fork the audit
    trail from the thing it audits. So this is the last step before paint and
    nothing downstream of it is stored.

    THE TEST IS AN UNDERSCORE, deliberately narrow. Cluster subjects are either
    a region key, which is snake_case, or a supplier name as spelled in the
    file, which carries spaces and its own capitals. Title-casing anything
    lowercase would rewrite a supplier called `acme`, and a supplier name as
    spelled IS evidence: the dataset deliberately contains `calder corporation`
    lowercase, and tidying it would hide the messiness the matcher exists to
    survive. An underscore does not appear in a supplier name, so it is the one
    signal that separates a key from a name.

    Closes a real defect: `north_america`, `SOUTH_ASIA` and `south_asia` all
    appeared on screen, which reads as three different places.
    """
    if "_" not in subject:
        return subject
    return " ".join(word.capitalize() for word in subject.split("_"))


def _subject_clause(event):
    return display_subject(event.sku_id)


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
        return (f"both readings agree on "
                f"{describe_verdict(merged, with_code=True)}")
    return (f"treated as one supplier the part is "
            f"{describe_verdict(merged, with_code=True)}; treated as two it is "
            f"{describe_verdict(apart, with_code=True)}")


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
    return (f"read as a stale make flag the part is "
            f"{describe_verdict(stale, with_code=True)}; read as genuine "
            f"in-house capability alongside its suppliers it is "
            f"{describe_verdict(dual, with_code=True)}")


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
    # WITH THE CODE. This clause appears on a human decision record, which is a
    # governance artefact: the code is the key a later reader joins on to find
    # what the verdict table said, and the person reading a decision log is the
    # person who needs it.
    return (f"the verdict now stands at "
            f"{describe_verdict(resulting, with_code=True)}")


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
        bound = BOUND_SENTENCE.get(completeness)
        if bound:
            prefix, suffix = bound
            sentence = f"{event.sku_id}: {name} is {prefix}{measure}{suffix}"
        else:
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
        opening = (f"{display_subject(event.sku_id)}: {len(members)} exposed parts would {verb} "
                   f"only if an unresolved supplier name merge is confirmed")
    else:
        opening = (f"{display_subject(event.sku_id)}: {len(members)} exposed parts {verb}")
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
    """A figure, rounded once and grouped for reading.

    THOUSANDS SEPARATORS, because "stops 16500 finished units a year" makes a
    reader count digits and the tile beside it already says 16,500. Applied to
    whole numbers only: a rounded decimal is short enough to read and grouping
    it would introduce a second convention for one digit of gain.
    """
    if isinstance(value, list) and len(value) == 2 and all(
            isinstance(part, int) for part in value):
        numerator, denominator = value
        if denominator == 1:
            return f"{numerator:,}"
        return f"{numerator / denominator:.1f}"
    if isinstance(value, int) and not isinstance(value, bool):
        return f"{value:,}"
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
    "wait_out_days": "{measure} days quoted lead time",
    "resource_days": "{prefix}{measure} days to approve a new supplier",
    "buffer_cover": "{prefix}{measure} days of stock left",
    "blast_radius": "stops {prefix}{measure} finished units a year",
    "portability": "tooling owned by the {measure}",
    "concentration":
        "shares a supplier or region with {measure} other exposed parts",
}

RANKED_ABSENT = {
    "wait_out_days": {
        "cannot_tell": "no lead time on file for any supplier",
        # NOT "no recovery path at all" any more, and the narrowing is the
        # point. Nobody to buy from is a statement about the wait-it-out path
        # only; the resourcing path is exactly what such a part still has, and
        # the clause beside this one now says how long it takes.
        "no_recovery_path":
            "no supplier on file to wait for: somebody checked the list",
        "not_applicable": "made in-house, so there is nothing to order",
    },
    "resource_days": {
        "cannot_tell":
            "nobody has timed what approving a new supplier would take",
    },
    "buffer_cover": {
        "cannot_tell":
            "no stock count on file, so we cannot say how long stock lasts",
    },
    "portability": {
        "cannot_tell": "no tooling owner on file",
    },
    "concentration": {
        "cannot_tell":
            "depends on two supplier names nobody has confirmed are the same",
        "not_applicable": "no other parts to share a supplier or region with",
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


def _resource_clause(clause, value):
    """The resourcing chain in one clause: the total, the bound, the retry.

    THREE THINGS A BARE NUMBER WOULD DROP. That the total counts only the stages
    somebody timed, so it is a floor rather than a figure. That a second
    qualification cycle changes it, where anybody has said how many to plan for.
    And that the days rest on estimates rather than quotes, which is the
    difference between a schedule and a hope. Each is stated in words, because
    the reader who does not see them has no way to recover them.
    """
    detail = clause.get("detail") or {}
    prefix = BOUND_WORDS.get(clause.get("completeness", ""), "")
    text = f"{prefix}{_measure(value)} days to approve a new supplier"
    untimed = detail.get("stages_untimed") or ()
    if untimed:
        count = len(untimed)
        step = "step" if count == 1 else "steps"
        text += f", with {count} {step} nobody has timed"
    retry = detail.get("with_retry_days")
    cycles = detail.get("qualification_cycles")
    if retry is not None and cycles:
        text += (f" ({_measure(retry)} days if approval takes "
                 f"{cycles} attempts)")
    elif cycles is None:
        text += " (counting one attempt, because nobody said how many to plan)"
    return text


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
    if dimension == "wait_out_days":
        detail = clause.get("detail") or {}
        quoted, p95 = detail.get("quoted_days"), detail.get("p95_days")
        if quoted is None:
            return ""
        # "p95" IS A STATISTICIAN'S WORD. A planner reading this once needs to
        # know the second figure is the bad case, not which percentile it sits
        # at; the percentile is in the evidence panel for anybody who wants it.
        return f"{quoted} days quoted lead time, {p95} days at worst"
    if dimension == "resource_days":
        return _resource_clause(clause, value)
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
    parts = [f"{display_subject(event.sku_id)}: "
             f"{describe_verdict(evidence.get('verdict', ''))}"]
    for clause in evidence.get("clauses", []):
        rendered = _ranked_clause(clause)
        if rendered:
            parts.append(rendered)
    sentence = ", ".join(part for part in parts if part) + "."

    names = evidence.get("archetypes") or []
    if names:
        # "FLAGGED AS", NOT "THIS MATCHES". The pattern names are now short
        # descriptions rather than coined terms, and "this matches one supplier,
        # and they own the tooling" reads as a sentence that lost its verb.
        sentence += (" Flagged as: " + "; ".join(names) + ".")
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

DECISION_PANEL_HEADING = "Decisions recorded"

# ORDER IS DECLARED, never left to be inferred. A linear list with no stated
# order reads as a ranking, which is the same objection that governs every other
# ordered set in this system.
DECISION_PANEL_ORDER = "in the order they were recorded"

# THE SCOPE IS STATED AT FULL WEIGHT, not dimmed into a caption, and it changed
# on 2026-08-07 because the behaviour did. This sentence used to read "This
# record covers this browser session only. Nothing here is written to disk, and
# closing the tab ends it." That was true, and it was the defect: for a tool
# whose purpose is a reviewable audit trail, who decided what survived exactly as
# long as a browser tab. The log is now appended to disk as it is written, so the
# sentence says what the record actually is.
DECISION_PANEL_SCOPE = ("This record is append-only and is written to disk as "
                        "each decision is made, so it survives a reload. "
                        "Nothing here can be edited or removed.")

# The empty state is a RECORDED zero, not an absence: it is the reviewer's own
# count of their own decisions, so a figure is honest here in a way it would not
# be for a measurement.
DECISION_PANEL_EMPTY = "No decision has been recorded yet."


def decision_panel_count(recorded, outstanding):
    """The denominator before the numerator, which is this system's habit.

    A reviewer facing 23 judgments should know it is 23 before they start, and
    what remains at any point. Stated as counts of acts, never as a fraction or a
    proportion, because a bar or a percentage is a normalised scale and this
    surface refuses those.
    """
    decisions = "decision" if recorded == 1 else "decisions"
    return (f"{recorded} {decisions} recorded, {outstanding} still outstanding "
            f"of {recorded + outstanding}")


FIELD_PROSE = {
    "on_hand_units": "a stock count",
    "tooling_owner": "who owns the tooling",
    "verdict": "confirmation that the supplier list is complete",
    "concentration": "confirmation that two supplier names are the same firm",
    "wait_out_days": "a lead time",
    "resource_days": "how long approving a new supplier takes",
}

# THE PATTERN NAMES, SPELLED AS WHAT THEY ARE. "The resourcing trap" is a term
# of art this tool invented, and a reader meeting it for the first time has to
# be told what it means somewhere else. Each name now carries its own
# definition, which costs a few words per row and saves a glossary.
#
# KEPT IN STEP WITH `archetypes.py` BY HAND, and a test asserts the two agree:
# the catalogue owns the label a surface renders and this owns the label a
# sentence renders, and a reader seeing one name on a row and another in the
# sentence about that row has found a bug rather than a synonym.
ARCHETYPE_PROSE = {
    "resourcing_trap": "one supplier, supplier-owned tooling",
    "correlated_resourcing_trap":
        "one supplier, supplier-owned tooling, shared with other parts",
    "counted_empty_single_source": "one supplier, no stock left",
    "no_quotable_single_source": "one supplier, nobody quoting",
    "nobody_to_call": "no supplier on file",
    "headline_exposure":
        "one supplier, long lead, low stock, supplier-owned tooling",
    "long_lead_single_source": "one supplier, long lead",
}


def render_field_request(field_name, part_count, archetype_names):
    """One trip to one system of record. THE ROW IS THE FIELD, NOT THE PART.

    Says what fetching it would settle, never what the value is likely to be.
    Nothing here imputes: the sentence describes a question, not a forecast.
    """
    described = FIELD_PROSE.get(field_name, field_name)
    patterns = "; ".join(ARCHETYPE_PROSE.get(name, name)
                         for name in archetype_names)
    plural = "part" if part_count == 1 else "parts"
    return (f"Getting {described} for {part_count} {plural} would settle "
            f"whether they are: {patterns}.")


COVERAGE_PROSE = {
    "unplaceable": (
        "Nobody has confirmed the supplier list for {count} parts, so any of "
        "them could belong to the groups on this page. Every count here is "
        "therefore a floor: the real number can only be higher."),
    "not_applicable": (
        "{count} parts are not scored on {dimension}. The question does not "
        "apply to them, which is not the same as the answer being no."),
    "no_thresholds": (
        "Nobody has said what counts as a long lead time or as thin stock, so "
        "this tool will not say it either. Set the numbers in "
        "config/archetypes.yaml, where they carry the name of whoever set "
        "them."),
    "catalogue": (
        "Which combinations are worth naming is a judgment, so it is agreed "
        "once here rather than once for every part."),
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
