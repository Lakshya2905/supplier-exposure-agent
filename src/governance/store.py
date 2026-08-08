"""Where a decision goes so that it is still there tomorrow.

The decision log was append-only, correctly shaped, carried a named decider and
a UTC timestamp, and **lived entirely in `st.session_state`**. It was gone on
reload. For a tool whose stated purpose is a reviewable audit trail, "who decided
what" survived exactly as long as a browser tab, and nothing on the screen said
so. That is the gap this module closes.

STRUCTURED, NEVER PROSE. CLAUDE.md: the decision log holds no rendered text;
`render(event)` produces it on demand and golden files pin the wording. So a
line here is the event's fields and nothing else, and a test asserts no rendered
sentence reaches the file. Storing the prose would fork the record from the
renderer the first time a word changed.

THIS IS NOT A WRITE PATH TO SOURCE DATA. `src/interface/actions.py` states the
rule: no function edits a CSV, and a reviewer who knows a missing on-hand figure
must fix it in the system of record and re-run. What is written here is a
DECISION, never a value, and `decisions/` is not an input to anything: the
pipeline never reads it and no test grades against it.

APPEND-ONLY ON DISK AS WELL AS IN MEMORY. One line per event, opened in append
mode, never rewritten and never deleted. An audit trail that can be edited in
place is a document, not a trail.
"""
import json
import os
from dataclasses import asdict
from pathlib import Path

from . import DecisionEvent, DecisionLog

# REDIRECTABLE, because the test suite drives the real app and the Confirm
# surface records as it is clicked. Without an override, running the suite
# appended a decision by a fixture name to the operator's live record, which is
# a test forging an entry in the log the product exists to be trusted for.
# `tests/conftest.py` points this at a temporary directory for the whole run.
DECISIONS_ENV = "SEA_DECISIONS_DIR"


def decisions_file():
    return Path(os.environ.get(DECISIONS_ENV, "decisions")) / "decisions.jsonl"

# The fields that are the record. Anything the renderer produces is excluded by
# construction rather than by filtering: this is the dataclass, and the
# dataclass holds no sentences.
FIELDS = tuple(DecisionEvent.__dataclass_fields__)


def _line(event):
    payload = asdict(event)
    # `event_id` is the log's own ordinal and is reassigned on load, so storing
    # it would let a hand-edited file dictate ordering it does not own.
    payload.pop("event_id", None)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def append(event, path=None):
    """One event, one line. Opened in append mode and closed immediately.

    Written per decision rather than batched at exit, because the failure this
    protects against is the process going away.
    """
    path = Path(path) if path else decisions_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(_line(event) + "\n")
    return path


def load(path=None):
    """Rebuild the log from disk, or an empty one if nothing is recorded yet.

    A malformed line RAISES rather than being skipped. A silently dropped
    decision is the audit trail lying by omission, which is worse than the file
    refusing to load and saying which line is wrong.
    """
    path = Path(path) if path else decisions_file()
    log = DecisionLog()
    if not path.exists():
        return log
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as broken:
            raise ValueError(
                f"{path}:{number} is not readable as a decision: {broken}"
            ) from broken
        unknown = set(payload) - set(FIELDS)
        if unknown:
            raise ValueError(
                f"{path}:{number} carries fields the log has no place for: "
                f"{sorted(unknown)}")
        payload.pop("event_id", None)
        log.append(**payload)
    return log


def decisions_by_subject(log):
    """The LATEST decision per subject, for a surface that has to show state.

    Latest rather than first: the log is append-only, so a changed decision is a
    new event beside the old one, and the row has to show what stands now while
    the panel below still shows both.
    """
    latest = {}
    for event in log:
        if event.decided_by:
            latest[event.sku_id] = event
    return latest
