"""A reviewer's click, turned into a decision event. Nothing else.

THERE IS NO WRITE PATH TO SOURCE DATA, and that is a rule rather than an
omission. No function here edits a CSV, and the module imports nothing that
could. "Validation flags, never fixes" has to hold at the surface where fixing
would feel most natural: a reviewer looking at a missing on-hand figure they
happen to know is exactly the person who would type it in.

The correct action there is to fix it in the system of record and re-run, and
the interface says so where the abstention appears. What gets recorded here is a
DECISION, never a value.
"""
from .. import governance as gov

# Applying a control writes one event. A cluster control writes ONE event
# covering its members, carrying member_count, which is agent 1's envelope
# field for precisely this.


def apply(log, control, decided_by, reason_code="", note="", *, at,
          act_id=None):
    """Record one act. Raises rather than guessing anything.

    `at` IS KEYWORD-ONLY AND HAS NO DEFAULT, deliberately. It used to default to
    the Unix epoch, and the painter never passed it, so every decision the
    deployed app recorded was stamped 1970-01-01. Nothing displayed the field, so
    a governance record carrying a false date was invisible for as long as it
    took somebody to render it.

    A default clock here would be the same trap one layer down: it would make
    the wrong value silent again, and it would put a clock inside a module whose
    output is golden-pinned. So the caller supplies the time, and omitting it is
    a loud failure in the same register as omitting the decider.
    """
    if not (decided_by or "").strip():
        raise ValueError("an anonymous decision is not a decision")
    if not (at or "").strip():
        raise ValueError("an undated decision is not a decision")
    if control.requires_reason and not reason_code:
        raise ValueError(f"{control.action} requires a reason code")
    if reason_code and reason_code not in control.reason_codes:
        raise ValueError(f"reason code not offered for this control: "
                         f"{reason_code!r}")
    if reason_code == gov.REASON_OTHER and not (note or "").strip():
        raise ValueError("'other' requires the note it promises")

    status = (gov.STATUS_APPROVED if control.action == "confirm"
              else gov.STATUS_REJECTED)

    prior = _latest_decision_on(log, control.subject)
    if prior is not None:
        if _is_unchanged(prior, status, decided_by, reason_code, note):
            # The status word, not rendered prose. This module records and does
            # not render, so it must not import the renderer to phrase a refusal.
            raise ValueError(
                f"{control.subject} is already {status} by {decided_by}; "
                f"an unchanged decision is not a new decision")

    evidence = {"members": list(control.__dict__.get("members", ())),
                "member_count": control.member_count,
                "resulting_verdict": ""}
    # A CHANGED MIND IS A NEW JUDGMENT THAT CITES THE OLD ONE, never an edit.
    # The log is append-only and its events are frozen, so the earlier decision
    # is not touched: the later one carries a backward reference and the panel
    # reads like a paper ledger, where a correction is written below the line it
    # corrects rather than over it.
    #
    # This lives in `evidence`, not in `act_id`. `act_id` is agent 1's envelope
    # field, carried field for field, so its meaning is agent 1's to define;
    # giving it a second meaning here would be worse than renaming it, because a
    # cross-agent join would silently read a relation that agent 1 never wrote.
    # `evidence` is the additive agent-3 column that such a join does not see.
    if prior is not None:
        evidence["replaces"] = prior.event_id

    return log.append(
        status=status, sku_id=control.subject, field="concentration",
        value=control.action, decided_by=decided_by, reason_code=reason_code,
        note=note, act_id=act_id, act_kind=control.act_kind,
        member_count=control.member_count, at=at,
        kind=gov.KIND_HUMAN_DECISION, evidence=evidence)


def _latest_decision_on(log, subject):
    """The most recent human decision about this subject, or None.

    Derived by reading the sequence rather than stored, because the log is
    append-only and nothing may be stamped after the fact.
    """
    found = None
    for event in log:
        if (event.kind == gov.KIND_HUMAN_DECISION
                and event.sku_id == subject):
            found = event
    return found


def _is_unchanged(prior, status, decided_by, reason_code, note):
    """Whether this act would say exactly what the last one already said.

    The DECIDER is part of the identity on purpose. A second reviewer reaching
    the same conclusion is a corroborating judgment and is worth recording; the
    same reviewer clicking the same button twice is one judgment arriving twice,
    which is usually a double click or a click after a rerun.
    """
    return (prior.status == status
            and prior.decided_by == decided_by
            and prior.reason_code == (reason_code or "")
            and prior.note == (note or ""))
