"""The API wrap, and the proof that it is only a wrap.

THE CLAIM UNDER TEST IS A NEGATIVE ONE: putting HTTP in front of the scoring
library changed no answer. A negative claim needs the comparison made against
something independent, so these tests call `pipeline.run` IN PROCESS and compare
it with the same inputs scored THROUGH the transport, dimension by dimension,
for every part in the frozen eval set. Not a spot check and not a count: 296
parts across six measures, with the value, the unit, the completeness, the
autonomy and the reasons each asserted.

WHY THAT SHAPE. A wrapper breaks things in exactly one way, and it is never the
obvious one. The scores do not change; their ENCODING does. `Fraction(73, 2)`
becomes 36.5 and the exactness the fixtures are built on is gone. `None` becomes
`""` because a display helper was within reach on the way out. `UNBOUNDED`
becomes null and an answered dimension lands in the caller's unknown pile. Each
of those is silent, each passes a smoke test that checks a 200 and a part count,
and each destroys a distinction this project spent its design on. So they are
asserted by name below, on top of the wholesale comparison.
"""
import json
import unittest
from fractions import Fraction
from pathlib import Path

from fastapi.testclient import TestClient

from src import governance as gov
from src import scoring
from src.governance import store
from src.api import runs
from src.api.encode import encode
from src.api.main import app
from src.interface import model as view
from src.pipeline import run as run_pipeline
from src.pipeline import surfaces

ROOT = Path(__file__).resolve().parent.parent
FROZEN = ROOT / "evals" / "inputs"

client = TestClient(app)


def scored_through_the_api():
    response = client.post("/api/score", data={"dataset": "frozen"})
    assert response.status_code == 200, response.text
    return response.json()


def scored_in_process():
    return run_pipeline(data_dir=FROZEN)


class TestTheWrapChangesNoScore(unittest.TestCase):
    """The regression test the API wrap exists to pass."""

    @classmethod
    def setUpClass(cls):
        cls.wire = scored_through_the_api()
        cls.library = scored_in_process()

    def test_the_same_parts_are_scored(self):
        self.assertEqual(sorted(self.wire["profiles"]),
                         sorted(self.library.profiles))
        self.assertEqual(len(self.wire["profiles"]), 296)

    def test_every_dimension_of_every_part_survives_unchanged(self):
        """The whole comparison, not a sample.

        A sampled version of this test would pass for years and then miss the
        one dimension whose encoding is wrong, which would be the dimension
        somebody added after the test was written.
        """
        for part, profile in self.library.profiles.items():
            for score in profile.all_scores():
                delivered = self.wire["profiles"][part][score.dimension]
                with self.subTest(part=part, dimension=score.dimension):
                    self.assertEqual(delivered["value"], encode(score.value))
                    self.assertEqual(delivered["unit"], score.unit)
                    self.assertEqual(delivered["completeness"],
                                     score.completeness)
                    self.assertEqual(delivered["autonomy"], score.autonomy)
                    self.assertEqual(delivered["reasons"],
                                     list(score.reasons))

    def test_every_verdict_survives_unchanged(self):
        self.assertEqual(self.wire["verdicts"], dict(self.library.verdicts))

    def test_the_rendered_sentences_are_the_same_sentences(self):
        """The deliverable is a sentence, so the sentence is compared too.

        `test_scoring` proves the numbers; this proves the prose a planner
        actually reads is the prose the golden files pin, and that nothing was
        re-assembled on the way through the transport.
        """
        built = surfaces(self.library)
        for key, name in (("exposure", view.EXPOSURE),
                          ("what_to_check", view.FIND_OUT),
                          ("review", view.CONFIRM)):
            expected = [row.sentence for row in built[name].all_rows()]
            delivered = [row["sentence"] for row in
                         _all_rows(self.wire["surfaces"][key])]
            with self.subTest(surface=key):
                self.assertEqual(delivered, expected)
                self.assertTrue(expected, "a surface with no rows proves "
                                          "nothing about its sentences")

    def test_the_counts_agree_with_the_scores_they_summarise(self):
        counts = self.wire["run"]["counts"]
        results = [s for p in self.library.profiles.values()
                   for s in p.all_scores()]
        self.assertEqual(counts["parts_scored"], len(self.library.profiles))
        self.assertEqual(counts["dimension_results"], len(results))
        self.assertEqual(counts["executing"],
                         sum(1 for s in results if s.autonomy == gov.EXECUTES))
        self.assertEqual(counts["executing"] + counts["deferring"],
                         len(results))


def _all_rows(surface):
    return ([row for layer in surface["layers"] for group in layer
             for row in group["rows"]] + list(surface["rows"]))


class TestTheDistinctionsSurviveTheWire(unittest.TestCase):
    """Four encodings, each of which would be silently wrong."""

    def test_a_rational_crosses_exactly_and_is_never_a_float(self):
        # 100 x 365 / 1000 is 36.5 EXACTLY, and the fixtures assert equality
        # rather than a tolerance. A float here would make every downstream
        # comparison approximate and nothing would say when that happened.
        crossed = encode(Fraction(73, 2))
        self.assertEqual(crossed, {"type": "exact", "numerator": 73,
                                   "denominator": 2})
        self.assertNotIsInstance(crossed, float)
        self.assertNotIn("36.5", json.dumps(crossed))

    def test_a_missing_value_and_a_recorded_zero_stay_different(self):
        """The distinction the whole reader layer exists to protect.

        `interface.model._plain` turns None into `""` because it paints table
        cells. It is one import away from this module, and using it here would
        fuse a blank on-hand record with a counted zero on the wire, after
        `readers.py` went to considerable trouble to keep them apart.
        """
        self.assertIsNone(encode(None))
        self.assertEqual(encode(0), 0)
        self.assertNotEqual(encode(None), encode(0))
        self.assertNotEqual(encode(None), "")

    def test_unbounded_is_a_value_and_does_not_cross_as_null(self):
        crossed = encode(scoring.UNBOUNDED)
        self.assertEqual(crossed, {"type": "unbounded"})
        self.assertIsNotNone(crossed)

    def test_a_pair_and_a_rational_are_not_confusable(self):
        """Both are two ints. `render._measure` tells them apart by branch
        order, which a caller holding only the payload cannot do."""
        pair = encode((73, 2))
        rational = encode(Fraction(73, 2))
        self.assertEqual(pair, [73, 2])
        self.assertNotEqual(pair, rational)
        self.assertIsInstance(pair, list)
        self.assertIsInstance(rational, dict)

    def test_the_payload_is_json_and_loses_nothing_in_the_round_trip(self):
        wire = scored_through_the_api()
        self.assertEqual(json.loads(json.dumps(wire)), wire)


class TestAutonomyIsStillAnAffordance(unittest.TestCase):
    """The rule that must not evaporate at the transport layer."""

    def test_an_executed_row_carries_no_control_on_the_wire(self):
        wire = scored_through_the_api()
        for key in ("exposure", "what_to_check", "review"):
            for row in _all_rows(wire["surfaces"][key]):
                with self.subTest(surface=key, row=row["key"]):
                    if row["autonomy"] == gov.EXECUTES:
                        self.assertEqual(row["controls"], [])

    def test_a_recommends_row_that_offers_an_act_still_carries_its_control(self):
        wire = scored_through_the_api()
        actionable = [row for row in _all_rows(wire["surfaces"]["review"])
                      if row["controls"]]
        self.assertTrue(actionable, "the Review surface offers no act, so the "
                                    "affordance rule is untested here")
        for row in actionable:
            self.assertEqual(row["autonomy"], gov.RECOMMENDS)


class TestScoringInputs(unittest.TestCase):

    def test_an_unknown_dataset_is_refused_and_says_what_exists(self):
        response = client.post("/api/score", data={"dataset": "whatever"})
        self.assertEqual(response.status_code, 404)
        detail = response.json()["detail"]
        self.assertIn("frozen", detail["available"])

    def test_an_upload_missing_a_required_file_names_the_file(self):
        """Loud, and specific. "Invalid input" sends somebody back to guess."""
        response = client.post("/api/score", files=[
            ("files", ("bom.csv", b"parent_part,child_part,qty_per_parent\n",
                       "text/csv"))])
        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIn("part_master.csv", detail["missing"])
        self.assertNotIn("bom.csv", detail["missing"])
        self.assertIn("recovery_inputs.csv", detail["optional"])

    def test_an_upload_is_scored_from_the_bytes_it_was_given(self):
        files = [("files", (path.name, path.read_bytes(), "text/csv"))
                 for path in sorted(FROZEN.glob("*.csv"))]
        response = client.post("/api/score", files=files,
                               data={"dataset": "an upload"})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        library = scored_in_process()
        self.assertEqual(payload["verdicts"], dict(library.verdicts))
        digests = {entry["name"]: entry["sha256"]
                   for entry in payload["run"]["files"]}
        self.assertEqual(digests["bom.csv"],
                         runs.sha256(FROZEN / "bom.csv"))


class TestRunsAreReScoredNotReplayed(unittest.TestCase):

    def test_a_run_can_be_fetched_again_and_scores_the_same(self):
        first = scored_through_the_api()
        again = client.get(f"/api/run/{first['run']['id']}")
        self.assertEqual(again.status_code, 200, again.text)
        self.assertEqual(again.json()["profiles"], first["profiles"])

    def test_an_unknown_run_is_a_404_rather_than_a_default_run(self):
        response = client.get("/api/run/nosuchrun")
        self.assertEqual(response.status_code, 404)

    def test_the_stored_record_holds_no_rendered_sentence(self):
        """CLAUDE.md's rule, applied to the run store.

        A saved payload would freeze the wording of a run at the moment it was
        scored, and every later improvement to a sentence would stop at the
        boundary of runs recorded before it.
        """
        wire = scored_through_the_api()
        record = runs.load_run(wire["run"]["id"])
        text = json.dumps(record)
        self.assertNotIn("quoted lead time", text)
        self.assertNotIn("days to resource", text)
        self.assertEqual(sorted(record),
                         ["created_at", "data_dir", "dataset", "files", "id"])

    def test_a_run_whose_inputs_are_gone_says_so_rather_than_substituting(self):
        record = runs.record_run(FROZEN, "temporary", copy_inputs=True)
        for path in Path(record["data_dir"]).glob("*.csv"):
            path.unlink()
        response = client.get(f"/api/run/{record['id']}")
        self.assertEqual(response.status_code, 410)
        self.assertIn("a run is its inputs", response.json()["detail"]["error"])


class TestScopingARun(unittest.TestCase):
    """Criticality over the wire: a set of labels, never a cut-off."""

    def test_an_unscoped_run_says_it_assessed_everything(self):
        payload = scored_through_the_api()
        self.assertFalse(payload["scope"]["is_scoped"])
        self.assertIn("Every part", payload["scope"]["sentence"])

    def test_a_scope_that_matches_nothing_says_what_it_left_out(self):
        """The failure mode worth catching: a silently empty screen.

        A caller who asks for a tier this extract does not contain gets no
        parts, and the difference between "nothing is exposed" and "nothing was
        assessed" is the whole point of carrying the scope.
        """
        response = client.post("/api/score", data={"dataset": "frozen",
                                                   "criticality": "A,B"})
        payload = response.json()
        self.assertEqual(payload["run"]["counts"]["parts_scored"], 0)
        self.assertTrue(payload["scope"]["is_scoped"])
        self.assertIn("not examined", payload["scope"]["sentence"])
        self.assertEqual(payload["scope"]["included"], ["A", "B"])

    def test_an_empty_criticality_parameter_is_not_an_empty_scope(self):
        # "?criticality=" is somebody who left the box blank, and scoring
        # nothing at all is never what they meant.
        payload = client.post("/api/score", data={"dataset": "frozen",
                                                  "criticality": ""}).json()
        self.assertFalse(payload["scope"]["is_scoped"])

    def test_scoping_never_reaches_a_score(self):
        # `criticality` decides which parts are presented. No DimensionScore has
        # ever heard of it, and the payload is where that would first show.
        payload = scored_through_the_api()
        for scores in payload["profiles"].values():
            for score in scores.values():
                self.assertNotIn("criticality", score["detail"])


class TestComparingTwoRuns(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.first = scored_through_the_api()
        files = [("files", (path.name, path.read_bytes(), "text/csv"))
                 for path in sorted(FROZEN.glob("*.csv"))]
        cls.second = client.post("/api/score", files=files,
                                 data={"dataset": "the same bytes"}).json()

    def compare(self, before, after):
        return client.get("/api/changes",
                          params={"before": before, "after": after})

    def test_the_same_data_twice_produces_no_changes(self):
        """The control, and it is not trivial.

        A diff that reports churn between one dataset and a copy of it is
        comparing something other than the answers, and every count after that
        is noise a reader learns to ignore.
        """
        answer = self.compare(self.first["run"]["id"],
                              self.second["run"]["id"]).json()
        self.assertEqual(answer["changes"], [])
        self.assertEqual(answer["counts"], {})

    def test_both_sides_carry_their_provenance(self):
        """Two runs of different datasets are not a trend.

        "Cover fell across the board" means one thing between two Mondays and
        another between an ERP extract and a hand-built spreadsheet, so the
        comparison says which two it read.
        """
        answer = self.compare(self.first["run"]["id"],
                              self.second["run"]["id"]).json()
        for side in ("before", "after"):
            self.assertIn("dataset", answer[side])
            self.assertIn("provenance", answer[side])
            self.assertIn("parts_assessed", answer[side]["provenance"])

    def test_worsened_and_unjudged_are_counted_separately(self):
        answer = self.compare(self.first["run"]["id"],
                              self.second["run"]["id"]).json()
        self.assertIn("worsened", answer)
        self.assertIn("unjudged", answer)

    def test_an_unknown_run_on_either_side_names_which_side(self):
        for before, after, side in (
                ("nosuchrun", self.first["run"]["id"], "before"),
                (self.first["run"]["id"], "nosuchrun", "after")):
            response = self.compare(before, after)
            with self.subTest(side=side):
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()["detail"]["side"], side)


class TestDecisions(unittest.TestCase):
    """Every refusal `actions.apply` makes must still be made."""

    def setUp(self):
        self.wire = scored_through_the_api()
        self.run_id = self.wire["run"]["id"]
        self.subject = next(
            row["key"] for row in _all_rows(self.wire["surfaces"]["review"])
            if row["controls"])

    def post(self, **overrides):
        body = {"run_id": self.run_id, "subject": self.subject,
                "action": "confirm", "decided_by": "A Reviewer",
                "reason_code": "", "note": ""}
        body.update(overrides)
        return client.post("/api/decisions", json=body)

    def test_a_decision_is_recorded_and_comes_back_rendered(self):
        response = self.post(decided_by="First Reviewer")
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["decision"]["decided_by"], "First Reviewer")
        self.assertEqual(payload["decision"]["status"], gov.STATUS_APPROVED)
        self.assertTrue(payload["sentence"].endswith("."))

        listed = client.get("/api/decisions").json()["decisions"]
        self.assertIn("First Reviewer",
                      [entry["decided_by"] for entry in listed])

    def test_an_anonymous_decision_is_refused_with_the_reason(self):
        response = self.post(decided_by="   ")
        self.assertEqual(response.status_code, 409)
        self.assertIn("anonymous", response.json()["detail"]["error"])

    def test_a_rejection_without_a_reason_code_is_refused(self):
        response = self.post(action="reject", decided_by="Second Reviewer")
        self.assertEqual(response.status_code, 409)
        self.assertIn("requires a reason", response.json()["detail"]["error"])

    def test_a_reason_code_not_offered_for_the_control_is_refused(self):
        response = self.post(action="reject", decided_by="Third Reviewer",
                             reason_code="because I said so")
        self.assertEqual(response.status_code, 409)

    def test_the_same_decision_twice_is_refused_as_one_judgment(self):
        self.post(decided_by="Fourth Reviewer")
        repeat = self.post(decided_by="Fourth Reviewer")
        self.assertEqual(repeat.status_code, 409)
        self.assertIn("already", repeat.json()["detail"]["error"])

    def test_a_subject_with_no_control_cannot_be_decided_over_http(self):
        """The affordance rule, enforced at the transport layer.

        A control is FOUND on the Review surface, never constructed from the
        request. Building one here to satisfy a caller would hand a human the
        power to decide something this system does not offer, and it would do it
        somewhere no interface test looks.
        """
        response = self.post(subject="SEA-P-0001")
        self.assertEqual(response.status_code, 404)
        self.assertIn("no 'confirm' control", response.json()["detail"]["error"])

    def test_the_stored_log_still_holds_no_prose(self):
        self.post(decided_by="Fifth Reviewer")
        path = Path(store.decisions_file())
        self.assertTrue(path.exists())
        for line in path.read_text().splitlines():
            if line.strip():
                self.assertNotIn("sentence", json.loads(line))


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
