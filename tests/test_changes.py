"""What changed between two runs, and the four ways a diff lies.

EVERY TEST HERE IS ABOUT A DISTINCTION THE TWO RUNS BOTH GOT RIGHT and the
comparison could still destroy. Neither run ever confused a missing value with a
low one; subtracting them is where that confusion gets reintroduced, by code
that never touches a CSV and looks like arithmetic.
"""
import unittest
from fractions import Fraction

import dataclasses

from src import changes as ch
from src import scoring
from src.concentration import Cluster, ConcentrationReport, ConcentrationScore
from src.demand import USAGE_CANNOT_TELL, USAGE_KNOWN, USAGE_PARTIAL, Usage
from src.scoring import (ExposureProfile, blast_radius, buffer_cover,
                         committed_at_risk, portability, resource_days,
                         wait_out_days)

TIMED = {"alternate_source_days": 10, "tooling_lead_time_days": 20,
         "engineering_transfer_days": 30, "first_article_days": 40,
         "qualification_test_days": 50, "ramp_to_rate_days": 60,
         "qualification_cycles": 1}


def profile(part="P", on_hand=100, usage=1000, tooling="company",
            usage_state=USAGE_KNOWN, verdict="single_source",
            lead_times=((30, 45),), blocked=None, cluster_size=None):
    # `blocked` defaults to the annual usage, which is what the real join
    # produces for a part feeding one finished good. Carried separately because
    # blast radius reads it and buffer cover reads `value`, and a test that
    # moved one expecting both to follow would be testing its own fixture.
    use = Usage(part, Fraction(usage), usage_state,
                blocked_finished_good_units=(usage if blocked is None
                                             else blocked),
                reasons=("computed on 2 of 3 finished goods",))
    built = ExposureProfile(
        part_number=part,
        wait_out_days=wait_out_days(part, verdict, lead_times),
        resource_days=resource_days(part, tooling, TIMED),
        blast_radius=blast_radius(part, (), use),
        committed_at_risk=committed_at_risk(part, (), None),
        buffer_cover=buffer_cover(part, on_hand, use),
        portability=portability(part, tooling))
    if cluster_size is None:
        return built
    return dataclasses.replace(built, concentration=ConcentrationScore(
        part_number=part, dimension=scoring.CONCENTRATION, value=cluster_size,
        unit=scoring.PARTS, completeness=scoring.KNOWN,
        reasons=("hand-written for this test",)))


def one(before, after, dimension):
    found = [c for c in ch.compare_profiles({"P": before}, {"P": after})
             if c.dimension == dimension]
    return found[0] if found else None


class TestAnUnknownIsNotADecrease(unittest.TestCase):
    """The missing-versus-zero collapse, arriving in the diff layer."""

    def test_a_measure_that_stopped_being_answerable_is_its_own_kind(self):
        change = one(profile(on_hand=100), profile(on_hand=None),
                     scoring.BUFFER_COVER)
        self.assertEqual(change.kind, ch.BECAME_UNKNOWN)
        self.assertIsNone(change.after)

    def test_it_is_not_reported_as_having_worsened(self):
        """40 days to "no stock count on file" is not a fall to zero.

        `worsened` is three-valued precisely so this case has somewhere to go.
        Forcing it into a boolean would make it True or False and both are
        assertions nobody can support.
        """
        change = one(profile(on_hand=100), profile(on_hand=None),
                     scoring.BUFFER_COVER)
        self.assertIsNone(change.worsened)
        self.assertNotIn(change, ch.Comparison(changes=(change,)).worsened())

    def test_an_answer_appearing_is_also_a_change_worth_reporting(self):
        change = one(profile(on_hand=None), profile(on_hand=100),
                     scoring.BUFFER_COVER)
        self.assertEqual(change.kind, ch.BECAME_KNOWN)
        self.assertIsNone(change.worsened)

    def test_two_unknowns_are_not_a_change(self):
        self.assertIsNone(one(profile(on_hand=None), profile(on_hand=None),
                              scoring.BUFFER_COVER))

    def test_the_reason_travels_with_it(self):
        # A row saying "became unknown" and nothing else sends somebody back to
        # the part to find out which field went missing.
        change = one(profile(on_hand=100), profile(on_hand=None),
                     scoring.BUFFER_COVER)
        self.assertIn("no stock count on file", change.detail["reason"])


class TestABoundIsNotAMeasurement(unittest.TestCase):

    def test_a_bound_that_moved_is_reported_without_a_verdict(self):
        """Two upper bounds can both fall while the true figures rise.

        Cover at "at most 40" and then "at most 30" may not have moved at all,
        so the change is reported and the judgment is withheld. A bare delta
        here would be the most confident wrong number on the screen.
        """
        before = profile(on_hand=100, usage=1000, usage_state=USAGE_PARTIAL)
        after = profile(on_hand=50, usage=1000, usage_state=USAGE_PARTIAL)
        change = one(before, after, scoring.BUFFER_COVER)
        self.assertEqual(change.kind, ch.MEASURE_MOVED)
        self.assertIsNone(change.worsened)
        self.assertTrue(change.detail["involves_a_bound"])

    def test_a_settled_measure_that_moved_does_carry_a_verdict(self):
        change = one(profile(on_hand=100), profile(on_hand=50),
                     scoring.BUFFER_COVER)
        self.assertTrue(change.worsened)
        self.assertFalse(change.detail["involves_a_bound"])

    def test_the_direction_comes_from_ranking_and_is_not_restated(self):
        """Less cover is worse; more blocked units are worse.

        `WORSE_IS` is imported rather than copied, because a second statement of
        which way is bad is a second place to get it backwards, and the two
        would disagree silently.
        """
        self.assertIs(ch.WORSE_IS, __import__(
            "src.ranking", fromlist=["WORSE_IS"]).WORSE_IS)
        cover = one(profile(on_hand=100), profile(on_hand=50),
                    scoring.BUFFER_COVER)
        blocked = one(profile(usage=1000), profile(usage=5000),
                      scoring.BLAST_RADIUS)
        self.assertIsNotNone(blocked)
        self.assertTrue(cover.worsened)      # less cover
        self.assertTrue(blocked.worsened)    # more blocked

    def test_a_bound_becoming_settled_is_a_change_not_an_improvement(self):
        before = profile(on_hand=100, usage_state=USAGE_PARTIAL)
        after = profile(on_hand=100, usage_state=USAGE_KNOWN)
        change = one(before, after, scoring.BUFFER_COVER)
        self.assertEqual(change.kind, ch.MEASURE_MOVED)
        self.assertIsNone(change.worsened)


class TestThingsWithNoNumberAreComparedByEquality(unittest.TestCase):

    def test_a_categorical_change_is_reported_without_a_delta(self):
        change = one(profile(tooling="company"), profile(tooling="supplier"),
                     scoring.PORTABILITY)
        self.assertEqual(change.kind, ch.MEASURE_MOVED)
        self.assertFalse(change.detail["comparable"])
        self.assertIsNone(change.worsened)

    def test_unbounded_cover_has_no_numeric_position(self):
        """Unbounded is a settled ANSWER and still not a number.

        Comparing it with 40 days by subtraction needs it to be a quantity, and
        the sentinel supports no arithmetic at all, which is the property that
        makes this safe rather than lucky.
        """
        before = profile(on_hand=40, usage=0)     # nothing consuming it
        after = profile(on_hand=40, usage=100)
        change = one(before, after, scoring.BUFFER_COVER)
        self.assertEqual(change.kind, ch.MEASURE_MOVED)
        self.assertFalse(change.detail["comparable"])

    def test_an_unchanged_categorical_is_not_a_change(self):
        self.assertIsNone(one(profile(tooling="company"),
                              profile(tooling="company"),
                              scoring.PORTABILITY))


class TestLeavingTheScopeIsNotRecovering(unittest.TestCase):

    def test_a_part_that_was_not_assessed_is_a_departure(self):
        """Otherwise the exposure count falls by narrowing the question.

        A run scoped to one criticality tier does not contain the parts it did
        not assess, and reading their absence as "no longer exposed" would let
        anybody improve the numbers by scoping harder.
        """
        changes = ch.compare_verdicts(
            {"P": "single_source"}, {}, {"P"}, set())
        kinds = [c.kind for c in changes]
        self.assertIn(ch.LEFT_SCOPE, kinds)
        self.assertNotIn(ch.NO_LONGER_EXPOSED, kinds)

    def test_a_part_that_arrived_exposed_is_said_twice(self):
        changes = ch.compare_verdicts(
            {}, {"P": "single_source"}, set(), {"P"})
        kinds = [c.kind for c in changes]
        self.assertIn(ch.ENTERED_SCOPE, kinds)
        self.assertIn(ch.NEWLY_EXPOSED, kinds)

    def test_a_part_that_arrived_multi_sourced_is_not_newly_exposed(self):
        changes = ch.compare_verdicts({}, {"P": "multi_source"}, set(), {"P"})
        self.assertEqual([c.kind for c in changes], [ch.ENTERED_SCOPE])

    def test_becoming_single_source_in_place_is_the_headline(self):
        changes = ch.compare_verdicts(
            {"P": "multi_source"}, {"P": "single_source"}, {"P"}, {"P"})
        self.assertEqual(changes[0].kind, ch.NEWLY_EXPOSED)
        self.assertTrue(changes[0].worsened)

    def test_the_diff_iterates_the_union_and_not_the_intersection(self):
        """The version of this that loses the new single source.

        A diff over the parts both runs share cannot see a part that only the
        later run has, which is exactly the part somebody needs to be told about.
        """
        changes = ch.compare_verdicts(
            {"OLD": "multi_source"}, {"NEW": "single_source"},
            {"OLD"}, {"NEW"})
        subjects = {c.subject for c in changes}
        self.assertEqual(subjects, {"OLD", "NEW"})


def report(*clusters):
    return ConcentrationReport(clusters=tuple(clusters), scores={},
                               unplaceable_parts=())


def cluster(key, members, basis="supplier"):
    return Cluster(key=key, basis=basis, members=tuple(sorted(members)),
                   completeness=scoring.KNOWN, reasons=("test",))


class TestClusters(unittest.TestCase):

    def test_a_cluster_is_identified_by_basis_and_key_together(self):
        """A supplier and a region can share a name.

        Keying on the name alone would report a supplier growing when a region
        did, and the two groupings answer different questions.
        """
        before = report(cluster("alpha", ["A", "B"], basis="supplier"))
        after = report(cluster("alpha", ["A", "B", "C"], basis="region"))
        kinds = {(c.kind, c.detail["basis"])
                 for c in ch.compare_clusters(before, after)}
        self.assertIn((ch.CLUSTER_SHRANK, "supplier"), kinds)
        self.assertIn((ch.CLUSTER_APPEARED, "region"), kinds)

    def test_a_cluster_that_gained_a_part_names_which(self):
        before = report(cluster("alpha", ["A", "B"]))
        after = report(cluster("alpha", ["A", "B", "C"]))
        change = ch.compare_clusters(before, after)[0]
        self.assertEqual(change.kind, ch.CLUSTER_GREW)
        self.assertEqual(change.detail["gained"], ["C"])
        self.assertTrue(change.worsened)

    def test_a_cluster_below_the_arity_is_not_a_cluster_at_all(self):
        # One part is correlated with nothing, so a pair falling to one is a
        # cluster that stopped existing rather than one that shrank by one.
        before = report(cluster("alpha", ["A", "B"]))
        after = report(cluster("alpha", ["A"]))
        change = ch.compare_clusters(before, after)[0]
        self.assertEqual(change.kind, ch.CLUSTER_SHRANK)
        self.assertEqual(change.after, 0)

    def test_an_unchanged_cluster_is_not_reported(self):
        same = report(cluster("alpha", ["A", "B"]))
        self.assertEqual(ch.compare_clusters(same, same), ())


class TestTheComparisonSaysWhatItCompared(unittest.TestCase):

    def test_worsened_unjudged_and_the_rest_are_separable(self):
        comparison = ch.Comparison(changes=(
            ch.Change(kind=ch.NEWLY_EXPOSED, subject="A", worsened=True),
            ch.Change(kind=ch.BECAME_UNKNOWN, subject="B", worsened=None),
            ch.Change(kind=ch.NO_LONGER_EXPOSED, subject="C", worsened=False)))
        self.assertEqual(len(comparison.worsened()), 1)
        self.assertEqual(len(comparison.unjudged()), 1)

    def test_an_unknown_change_kind_is_refused_at_construction(self):
        with self.assertRaises(ValueError):
            ch.Change(kind="got_a_bit_worse", subject="A")

    def test_two_runs_of_the_same_data_produce_no_changes(self):
        """The control, and it is not trivial.

        A diff that reports churn between a run and itself is comparing
        something other than the answers, and every count it produces afterwards
        is noise a reader has to learn to ignore.
        """
        from src.pipeline import run
        first, second = run(data_dir="evals/inputs"), run(data_dir="evals/inputs")
        self.assertEqual(ch.compare_runs(first, second).changes, ())

    def test_the_provenance_of_both_runs_travels_with_the_comparison(self):
        from src.pipeline import run
        comparison = ch.compare_runs(run(data_dir="evals/inputs"),
                                     run(data_dir="evals/inputs"))
        for side in (comparison.before, comparison.after):
            self.assertIn("data_dir", side)
            self.assertIn("parts_assessed", side)
            self.assertIn("scoped", side)


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
