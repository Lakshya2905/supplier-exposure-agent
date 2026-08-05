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


def apply(log, control, decided_by, reason_code="", note="",
          at="1970-01-01T00:00:00+00:00", act_id=None):
    """Record one act. Raises rather than guessing anything."""
    if not (decided_by or "").strip():
        raise ValueError("an anonymous decision is not a decision")
    if control.requires_reason and not reason_code:
        raise ValueError(f"{control.action} requires a reason code")
    if reason_code and reason_code not in control.reason_codes:
        raise ValueError(f"reason code not offered for this control: "
                         f"{reason_code!r}")
    if reason_code == gov.REASON_OTHER and not (note or "").strip():
        raise ValueError("'other' requires the note it promises")

    status = (gov.STATUS_APPROVED if control.action == "confirm"
              else gov.STATUS_REJECTED)
    return log.append(
        status=status, sku_id=control.subject, field="concentration",
        value=control.action, decided_by=decided_by, reason_code=reason_code,
        note=note, act_id=act_id, act_kind=control.act_kind,
        member_count=control.member_count, at=at,
        kind=gov.KIND_HUMAN_DECISION,
        evidence={"members": list(control.__dict__.get("members", ())),
                  "member_count": control.member_count,
                  "resulting_verdict": ""})
