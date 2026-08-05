"""The decision log has to be readable by a person, not just parseable here.

STORE STRUCTURED, RENDER PROSE, NEVER STORE THE PROSE. The rendered sentence is
what appears in the stage 7 review interface and in any demo, so it is treated
as a deliverable: the golden files below make a wording change show up as a
diff rather than sliding through unnoticed.
"""
import dataclasses
import pathlib
import unittest

from src import governance as gov
from src.governance.render import (STATUS_PROSE, VERDICT_PROSE, render,
                                   render_all)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def read_golden(name):
    return (FIXTURES / name).read_text().strip()


def merge_uncertain_event():
    return gov.DecisionEvent(
        event_id=1, at="2026-08-04T09:15:00+00:00",
        status=gov.STATUS_PROPOSED, sku_id="SEA-P-0248",
        field="sourcing_verdict", value="readings_disagree",
        source_file="suppliers.csv", kind=gov.KIND_MERGE_UNCERTAIN,
        evidence={"raw_a": "Marrow Corporation", "raw_b": "Yarrow Corporation",
                  "score": 0.9444444444444444, "threshold": 0.90,
                  "verdict_if_merged": "single_source",
                  "verdict_if_separate": "multi_source"})


def human_decision_event():
    return gov.DecisionEvent(
        event_id=2, at="2026-08-04T10:02:00+00:00",
        status=gov.STATUS_REJECTED, sku_id="SEA-P-0248",
        field="sourcing_verdict", value="multi_source",
        source_file="suppliers.csv", decided_by="r.okafor",
        reason_code=gov.REASON_MERGE_REJECTED, note="different legal entities",
        act_id=7, act_kind=gov.ACT_REJECT, kind=gov.KIND_HUMAN_DECISION,
        evidence={"raw_a": "Marrow Corporation", "raw_b": "Yarrow Corporation",
                  "score": 0.9444444444444444, "threshold": 0.90,
                  "resulting_verdict": "multi_source"})


def readings_disagree_event():
    return gov.DecisionEvent(
        event_id=3, at="2026-08-04T09:15:00+00:00",
        status=gov.STATUS_PROPOSED, sku_id="SEA-P-0000",
        field="sourcing_verdict", value="readings_disagree",
        source_file="part_master.csv", kind=gov.KIND_READINGS_DISAGREE,
        evidence={"verdict_if_merged": "readings_disagree",
                  "verdict_if_separate": "readings_disagree",
                  "stale_flag": "hidden_single_source",
                  "dual_mode": "multi_source"})


def verdict_assigned_event():
    return gov.DecisionEvent(
        event_id=4, at="2026-08-04T09:15:00+00:00",
        status=gov.STATUS_PROPOSED, sku_id="SEA-P-0001",
        field="sourcing_verdict", value="single_source",
        source_file="suppliers.csv", kind=gov.KIND_VERDICT_ASSIGNED,
        evidence={"resulting_verdict": "single_source",
                  "autonomy": gov.EXECUTES})


def dimension_scored_event():
    return gov.DecisionEvent(
        event_id=5, at="2026-08-04T09:15:00+00:00",
        status=gov.STATUS_PROPOSED, sku_id="SEA-P-0031",
        field="buffer_cover", value="11", source_file="part_master.csv",
        kind=gov.KIND_DIMENSION_SCORED,
        evidence={"dimension": "buffer_cover", "unit": "days",
                  "completeness": "upper_bound", "autonomy": gov.EXECUTES,
                  "reasons": ["440 units on hand covers 11.0 days at the "
                              "recorded consumption rate, and unrecorded "
                              "demand can only reduce cover"]})


def dimension_abstained_event():
    return gov.DecisionEvent(
        event_id=6, at="2026-08-04T09:15:00+00:00",
        status=gov.STATUS_PROPOSED, sku_id="SEA-P-0044",
        field="buffer_cover", value="", source_file="part_master.csv",
        kind=gov.KIND_DIMENSION_ABSTAINED,
        evidence={"dimension": "buffer_cover", "unit": "days",
                  "completeness": "cannot_tell", "autonomy": gov.RECOMMENDS,
                  "reasons": ["there is no on-hand record for this part, so "
                              "cover cannot be computed; this is not zero "
                              "cover"]})


def cluster_flagged_event():
    return gov.DecisionEvent(
        event_id=7, at="2026-08-04T09:15:00+00:00",
        status=gov.STATUS_PROPOSED, sku_id="Alpha Works",
        field="concentration_supplier", value="3", source_file="suppliers.csv",
        member_count=3, kind=gov.KIND_CLUSTER_FLAGGED,
        evidence={"basis": "supplier",
                  "members": ["CON-P01", "CON-P02", "CON-P03"],
                  "member_count": 3, "completeness": "known",
                  "contingent": False, "autonomy": gov.RECOMMENDS,
                  "reasons": ["3 exposed parts depend on this supplier"]})


def cluster_contingent_event():
    return gov.DecisionEvent(
        event_id=8, at="2026-08-04T09:15:00+00:00",
        status=gov.STATUS_PROPOSED, sku_id="Marrow Corporation",
        field="concentration_supplier", value="2", source_file="suppliers.csv",
        member_count=2, kind=gov.KIND_CLUSTER_CONTINGENT,
        evidence={"basis": "supplier", "members": ["CON-P13", "CON-P14"],
                  "member_count": 2, "completeness": "cannot_tell",
                  "contingent": True, "autonomy": gov.RECOMMENDS,
                  "reasons": ["these 2 parts share a supplier only if an "
                              "unresolved name merge is confirmed; under the "
                              "confirmed spellings alone they are separate "
                              "suppliers"]})


def part_ranked_event():
    return gov.DecisionEvent(
        event_id=9, at="2026-08-04T09:15:00+00:00",
        status=gov.STATUS_PROPOSED, sku_id="SEA-P-0248",
        field="ranked_summary", value="single_source",
        source_file="part_master.csv", kind=gov.KIND_PART_RANKED,
        evidence={
            "verdict": "single_source",
            "clauses": [
                {"dimension": "lead_time_to_recover", "unit": "days",
                 "completeness": "known", "value": [182, 266],
                 "detail": {"quoted_days": 182, "p95_days": 266}},
                {"dimension": "buffer_cover", "unit": "days",
                 "completeness": "upper_bound", "value": [389, 35],
                 "detail": {}},
                {"dimension": "blast_radius", "unit": "finished_good_units",
                 "completeness": "lower_bound", "value": 16500, "detail": {}},
                {"dimension": "portability", "unit": "categorical",
                 "completeness": "known", "value": "supplier", "detail": {}},
            ],
            "archetypes": ["the resourcing trap"]})


class TestGoldens(unittest.TestCase):
    """Committed sentences. A wording change is a reviewable diff, not a
    surprise in the review interface."""

    def test_merge_uncertain_golden(self):
        self.assertEqual(render(merge_uncertain_event()),
                         read_golden("golden_merge_uncertain.txt"))

    def test_human_decision_golden(self):
        self.assertEqual(render(human_decision_event()),
                         read_golden("golden_human_decision.txt"))

    def test_readings_disagree_golden(self):
        self.assertEqual(render(readings_disagree_event()),
                         read_golden("golden_readings_disagree.txt"))

    def test_dimension_scored_golden(self):
        self.assertEqual(render(dimension_scored_event()),
                         read_golden("golden_dimension_scored.txt"))

    def test_dimension_abstained_golden(self):
        self.assertEqual(render(dimension_abstained_event()),
                         read_golden("golden_dimension_abstained.txt"))

    def test_cluster_flagged_golden(self):
        self.assertEqual(render(cluster_flagged_event()),
                         read_golden("golden_cluster_flagged.txt"))

    def test_cluster_contingent_golden(self):
        self.assertEqual(render(cluster_contingent_event()),
                         read_golden("golden_cluster_contingent.txt"))

    def test_a_cluster_names_its_members_not_just_a_count(self):
        # The membership IS the finding; the count is only its summary.
        sentence = render(cluster_flagged_event())
        for member in ("CON-P01", "CON-P02", "CON-P03"):
            self.assertIn(member, sentence)

    def test_a_cluster_always_says_the_grouping_is_a_judgment(self):
        # A reviewer never told the grouping is a choice reads it as a
        # measurement, and the ceiling stops meaning anything.
        for event in (cluster_flagged_event(), cluster_contingent_event()):
            with self.subTest(kind=event.kind):
                self.assertIn("modelling judgment", render(event))
                self.assertIn("never applied automatically", render(event))

    def test_part_ranked_golden(self):
        self.assertEqual(render(part_ranked_event()),
                         read_golden("golden_ranked_part.txt"))

    def test_the_ranked_sentence_renders_bound_direction_in_words(self):
        # A bare number reads as a measurement when the true figure could be
        # anything below it. This is where carrying the bound direction since
        # stage 4 is paid out, and a reader who never sees "at most" has no way
        # to recover it.
        sentence = render(part_ranked_event())
        self.assertIn("at most", sentence)
        self.assertIn("at least", sentence)

    def test_the_ranked_sentence_rounds_only_here(self):
        # 389/35 is 11.114..., carried exactly all the way from stage 2.
        self.assertIn("11.1 days of cover", render(part_ranked_event()))

    def test_a_scored_dimension_always_renders_its_unit(self):
        # A bare number in a review interface is the first step toward somebody
        # adding it to the one beside it, and these are not addable.
        self.assertIn("11 days", render(dimension_scored_event()))


class TestEveryEnumMemberRenders(unittest.TestCase):

    def test_every_event_kind_renders_a_sentence(self):
        events = {gov.KIND_MERGE_UNCERTAIN: merge_uncertain_event(),
                  gov.KIND_HUMAN_DECISION: human_decision_event(),
                  gov.KIND_READINGS_DISAGREE: readings_disagree_event(),
                  gov.KIND_VERDICT_ASSIGNED: verdict_assigned_event(),
                  gov.KIND_DIMENSION_SCORED: dimension_scored_event(),
                  gov.KIND_DIMENSION_ABSTAINED: dimension_abstained_event(),
                  gov.KIND_CLUSTER_FLAGGED: cluster_flagged_event(),
                  gov.KIND_CLUSTER_CONTINGENT: cluster_contingent_event(),
                  gov.KIND_PART_RANKED: part_ranked_event()}
        self.assertEqual(set(events), set(gov.EVENT_KINDS),
                         "a new event kind must arrive with a rendering, or it "
                         "reaches the review interface unreadable")
        for kind, event in events.items():
            with self.subTest(kind=kind):
                sentence = render(event)
                self.assertTrue(sentence.endswith("."))
                self.assertIn(event.sku_id, sentence)
                self.assertNotIn("None", sentence)
                self.assertNotIn("  ", sentence)

    def test_every_reason_code_renders(self):
        for reason in gov.REASON_CODES:
            with self.subTest(reason=reason):
                event = gov.DecisionEvent(
                    event_id=1, at="2026-08-04T10:02:00+00:00",
                    status=gov.STATUS_APPROVED, sku_id="SEA-P-0248",
                    decided_by="r.okafor", reason_code=reason,
                    act_id=1, act_kind=gov.ACT_APPROVE,
                    kind=gov.KIND_HUMAN_DECISION,
                    evidence={"resulting_verdict": "single_source"})
                self.assertIn(reason, render(event))

    def test_every_status_renders_as_words_not_as_a_code(self):
        for status in gov.STATUSES:
            with self.subTest(status=status):
                event = gov.DecisionEvent(
                    event_id=1, at="2026-08-04T10:02:00+00:00", status=status,
                    sku_id="SEA-P-0248", decided_by="r.okafor",
                    kind=gov.KIND_HUMAN_DECISION, evidence={})
                # Lowercased because the clause leads the sentence and gets
                # sentence-cased; the point is that the status reads as words
                # rather than as a raw code, not which letter is capital.
                self.assertIn(STATUS_PROSE[status], render(event).lower())

    def test_every_verdict_the_table_can_produce_has_prose(self):
        from src.synthetic.verdicts import SEVERITY, READINGS_DISAGREE
        for verdict in tuple(SEVERITY) + (READINGS_DISAGREE,):
            with self.subTest(verdict=verdict):
                self.assertIn(verdict, VERDICT_PROSE,
                              "an unmapped verdict renders as a bare code in "
                              "the review interface")


class TestRendererHonesty(unittest.TestCase):

    def test_a_missing_clause_is_omitted_rather_than_invented(self):
        event = gov.DecisionEvent(
            event_id=1, at="2026-08-04T09:15:00+00:00",
            status=gov.STATUS_PROPOSED, sku_id="SEA-P-0009",
            kind=gov.KIND_MERGE_UNCERTAIN, evidence={})
        sentence = render(event)
        self.assertIn("SEA-P-0009", sentence)
        for absent in ("0.00", "threshold", "None"):
            self.assertNotIn(absent, sentence)

    def test_an_unmapped_verdict_renders_as_its_code_not_as_a_guess(self):
        event = gov.DecisionEvent(
            event_id=1, at="2026-08-04T09:15:00+00:00",
            status=gov.STATUS_PROPOSED, sku_id="SEA-P-0009",
            kind=gov.KIND_VERDICT_ASSIGNED, value="some_future_verdict",
            evidence={})
        self.assertIn("some_future_verdict", render(event))

    def test_score_below_threshold_is_not_described_as_meeting_it(self):
        event = merge_uncertain_event()
        below = dataclasses.replace(
            event, evidence={**event.evidence, "threshold": 0.99})
        self.assertIn("falls short of", render(below))
        self.assertNotIn("meets", render(below))

    def test_sentence_case_does_not_corrupt_the_data_it_capitalises(self):
        # str.capitalize() lowercases the remainder, which turns "r.okafor"
        # into "R.okafor". A username is an identifier rather than a word, so
        # changing its case makes the output stop matching a search for the
        # person who decided. The ISO timestamp used to be the second example
        # here and no longer appears in any sentence: time is carried on
        # DecisionEvent.at and read directly, so that the rendered wording stays
        # a pure function of structure and the goldens keep their meaning.
        sentence = render(human_decision_event())
        self.assertIn("r.okafor", sentence)

    def test_no_rendered_sentence_carries_a_timestamp(self):
        """A clock in golden-pinned output makes the goldens a liability.

        Either they freeze at a fake time, which is what shipped (every decision
        in the app was stamped at the Unix epoch), or they change on every run.
        The record carries time; the sentence does not.
        """
        for event in (human_decision_event(), merge_uncertain_event(),
                      part_ranked_event()):
            with self.subTest(kind=event.kind):
                self.assertTrue(event.at, "the record must still carry a time")
                self.assertNotIn(event.at, render(event))
                self.assertNotIn("T00:00:00", render(event))


class TestProseIsNeverStored(unittest.TestCase):

    def test_rendering_writes_nothing_back_into_the_event(self):
        event = merge_uncertain_event()
        before = dict(event.evidence)
        render(event)
        self.assertEqual(event.evidence, before)

    def test_no_stored_field_holds_a_sentence(self):
        log = gov.DecisionLog()
        log.append(status=gov.STATUS_PROPOSED, sku_id="SEA-P-0001",
                   field="sourcing_verdict", value="single_source",
                   at="2026-08-04T09:15:00+00:00",
                   kind=gov.KIND_VERDICT_ASSIGNED,
                   evidence={"resulting_verdict": "single_source"})
        rendered = render_all(log)[0]
        for record in log.to_records():
            flattened = repr(record)
            self.assertNotIn(rendered, flattened)
            self.assertNotIn("one qualified supplier", flattened,
                             "prose in the log cannot be re-rendered when the "
                             "wording improves")

    def test_render_all_covers_the_whole_log_in_order(self):
        log = gov.DecisionLog()
        for part in ("SEA-P-0001", "SEA-P-0002"):
            log.append(status=gov.STATUS_PROPOSED, sku_id=part,
                       at="2026-08-04T09:15:00+00:00",
                       kind=gov.KIND_VERDICT_ASSIGNED, value="single_source",
                       evidence={"resulting_verdict": "single_source"})
        sentences = render_all(log)
        self.assertEqual(len(sentences), 2)
        self.assertIn("SEA-P-0001", sentences[0])
        self.assertIn("SEA-P-0002", sentences[1])


class TestRenderedContentIsComplete(unittest.TestCase):
    """The brief lists what a rendered event has to answer. Each is checked."""

    def test_a_merge_event_answers_all_seven_questions(self):
        sentence = render(merge_uncertain_event())
        self.assertIn("SEA-P-0248", sentence)                    # which part
        self.assertIn("Marrow Corporation", sentence)            # raw string a
        self.assertIn("Yarrow Corporation", sentence)            # raw string b
        self.assertIn("0.94", sentence)                          # match score
        self.assertIn("0.90 threshold", sentence)                # threshold
        self.assertIn("single_source", sentence)                 # reading one
        self.assertIn("multi_source", sentence)                  # reading two
        self.assertIn("routed for review", sentence)             # what happened

    def test_a_human_decision_answers_who_why_and_what_now(self):
        sentence = render(human_decision_event())
        self.assertIn("r.okafor", sentence)                      # who
        self.assertIn(gov.REASON_MERGE_REJECTED, sentence)       # reason code
        self.assertIn("different legal entities", sentence)      # the note
        self.assertIn("multi_source", sentence)                  # resulting

    def test_a_readings_disagreement_names_both_readings(self):
        sentence = render(readings_disagree_event())
        self.assertIn("stale make flag", sentence)
        self.assertIn("in-house", sentence)
        self.assertIn("hidden_single_source", sentence)
        self.assertIn("multi_source", sentence)


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
