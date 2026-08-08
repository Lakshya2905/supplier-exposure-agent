"""The audit trail, on disk.

The decision log was append-only, correctly shaped, carried a named decider and
a UTC timestamp, and lived entirely in `st.session_state`. It was gone on
reload. For a tool whose stated purpose is a reviewable audit trail, "who
decided what" survived exactly as long as a browser tab, and nothing on screen
said otherwise.

What is asserted here is the part that makes the record worth having: that it
comes back, that it comes back UNCHANGED, and that it holds no prose.
"""
import json
import unittest
from pathlib import Path

from src import governance as gov
from src.governance import render as govrender
from src.governance import store
from src.interface import actions
from src.interface.model import Control

AT = "2026-08-07T10:02:00+00:00"


def control(subject="south_asia", action="confirm", members=28):
    return Control(action=action, act_kind=gov.ACT_BULK_APPROVE, subject=subject,
                   requires_reason=(action == "reject"), member_count=members,
                   reason_codes=(gov.REASON_CORRELATION_CONFIRMED,
                                 gov.REASON_CORRELATION_REJECTED))


def record(path, log=None, **kwargs):
    log = log if log is not None else gov.DecisionLog()
    event = actions.apply(log, kwargs.pop("control", control()),
                          kwargs.pop("who", "Ada Lovelace"), at=kwargs.pop("at", AT),
                          **kwargs)
    store.append(event, path)
    return log, event


class TestADecisionSurvivesTheProcess(unittest.TestCase):

    def test_an_event_written_is_an_event_read_back(self, ):
        path = Path(self.tmp) / "d.jsonl"
        _log, written = record(path)
        restored = list(store.load(path))
        self.assertEqual(len(restored), 1)
        for field in ("at", "status", "sku_id", "decided_by", "reason_code",
                      "note", "act_kind", "member_count", "kind"):
            with self.subTest(field=field):
                self.assertEqual(getattr(restored[0], field),
                                 getattr(written, field))

    def test_the_file_is_appended_to_not_rewritten(self):
        path = Path(self.tmp) / "d.jsonl"
        log, _ = record(path)
        record(path, log=log, control=control("europe", members=21))
        self.assertEqual(len(store.load(path)), 2)
        self.assertEqual(len(path.read_text().strip().splitlines()), 2)

    def test_an_empty_location_loads_as_an_empty_log_not_an_error(self):
        # A first run has nothing recorded, and that is a recorded zero rather
        # than a fault.
        self.assertEqual(len(store.load(Path(self.tmp) / "absent.jsonl")), 0)

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()


class TestTheRecordHoldsNoProse(unittest.TestCase):
    """CLAUDE.md: store structured, render prose, never store the prose.

    The renderer owns the wording and golden files pin it. A sentence on disk
    would fork from the renderer the first time a word changed, and the file
    would then be the older of two truths with nothing marking it as such.
    """

    def setUp(self):
        import tempfile
        self.path = Path(tempfile.mkdtemp()) / "d.jsonl"

    def test_no_rendered_sentence_reaches_the_file(self):
        _log, event = record(self.path,
                             reason_code=gov.REASON_CORRELATION_CONFIRMED)
        sentence = govrender.render(event)
        raw = self.path.read_text()
        self.assertNotIn(sentence, raw)
        # The distinctive verb the renderer uses, rather than the whole
        # sentence, so this still fails if the wording is only partly stored.
        self.assertNotIn("Accepted by", raw)

    def test_the_line_carries_only_fields_the_event_declares(self):
        record(self.path)
        payload = json.loads(self.path.read_text().splitlines()[0])
        self.assertEqual(set(payload) - set(store.FIELDS), set())

    def test_the_event_id_is_not_stored(self):
        # It is the log's own ordinal. Storing it would let a hand-edited file
        # dictate an ordering it does not own.
        record(self.path)
        self.assertNotIn("event_id", json.loads(self.path.read_text()))


class TestACorruptedTrailFailsLoudly(unittest.TestCase):
    """A silently skipped line is the audit trail lying by omission, which is
    worse than the file refusing to load and naming the line that is wrong."""

    def setUp(self):
        import tempfile
        self.path = Path(tempfile.mkdtemp()) / "d.jsonl"

    def test_a_malformed_line_raises_rather_than_being_skipped(self):
        record(self.path)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write("{not json}\n")
        with self.assertRaises(ValueError) as refusal:
            store.load(self.path)
        self.assertIn(":2", str(refusal.exception))

    def test_an_unknown_field_raises(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": AT, "status": gov.STATUS_APPROVED,
                                     "sku_id": "x", "decided_by": "A",
                                     "smuggled": "value"}) + "\n")
        with self.assertRaises(ValueError):
            store.load(self.path)


class TestARepeatedDecisionIsRefusedAcrossSessions(unittest.TestCase):
    """The defect QA ISSUE-004 named: the same cluster could be confirmed again
    and again with no warning, because each reload started from nothing."""

    def setUp(self):
        import tempfile
        self.path = Path(tempfile.mkdtemp()) / "d.jsonl"

    def test_an_unchanged_repeat_is_refused_after_a_reload(self):
        record(self.path, reason_code=gov.REASON_CORRELATION_CONFIRMED)
        reloaded = store.load(self.path)          # the next session
        with self.assertRaises(ValueError) as refusal:
            actions.apply(reloaded, control(), "Ada Lovelace",
                          reason_code=gov.REASON_CORRELATION_CONFIRMED, at=AT)
        self.assertIn("already", str(refusal.exception))

    def test_the_latest_decision_per_subject_is_what_a_row_shows(self):
        log, _ = record(self.path, reason_code=gov.REASON_CORRELATION_CONFIRMED)
        record(self.path, log=log, control=control(action="reject"),
               reason_code=gov.REASON_CORRELATION_REJECTED, note="on reflection")
        latest = store.decisions_by_subject(store.load(self.path))
        self.assertEqual(latest["south_asia"].status, gov.STATUS_REJECTED)
        # Both survive: append-only means the earlier one is still in the file.
        self.assertEqual(len(store.load(self.path)), 2)


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
