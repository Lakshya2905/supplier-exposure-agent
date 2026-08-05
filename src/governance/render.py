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
from . import (EXECUTES, KIND_HUMAN_DECISION, KIND_MERGE_UNCERTAIN,
               KIND_READINGS_DISAGREE, KIND_VERDICT_ASSIGNED,
               STATUS_APPROVED, STATUS_PROPOSED, STATUS_REJECTED,
               STATUS_SUPERSEDED)

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
    if event.at:
        clause += f" on {event.at}"
    if event.reason_code:
        clause += f", reason: {event.reason_code}"
    if event.note:
        clause += f" ({event.note})"
    return clause


def _outcome_clause(evidence):
    resulting = evidence.get("resulting_verdict")
    if not resulting:
        return ""
    return f"the verdict now stands at {describe_verdict(resulting)}"


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
        opening = _strings_clause(evidence)
        parts.append(
            f"{_subject_clause(event)}: " +
            (opening + "." if opening else "a review decision was recorded."))
        score = _score_clause(evidence)
        if score:
            parts.append("The system had them " + score + ".")
        decision = _decision_clause(event)
        if decision:
            parts.append(_sentence_case(decision) + ".")
        outcome = _outcome_clause(evidence)
        if outcome:
            parts.append(_sentence_case(outcome) + ".")

    else:  # pragma: no cover - EVENT_KINDS is closed and validated on append
        parts.append(f"{_subject_clause(event)}: {event.kind}.")

    return " ".join(p for p in parts if p)


def render_all(log):
    return [render(event) for event in log]
