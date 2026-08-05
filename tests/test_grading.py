"""Grade the normaliser against the damage ledger.

THE FLOORS ARE THE CONTRACT AND THE THRESHOLD IS THE DIAL. These tests assert
that the shipped threshold clears both floors. If a change to the normaliser
drops it below one, the fix is to move the threshold or improve the normaliser,
never to lower the floor to meet the code.

Precision and recall are asserted separately and never combined. One number
would hide which way the system is failing, and the two failures have opposite
costs.
"""
import collections
import unittest

from src.generate_data import generate
from src.grading import grade_pairs, sweep, verdict_impact
from src.identify import (DEFAULT_THRESHOLD, PRECISION_FLOOR, RECALL_FLOOR,
                          identify_all)
from src.synthetic.config import GeneratorConfig


def build_world(tmp_dir):
    """Regenerated, not committed. Eval floors are never produced by the
    generator under test, and this is a property test rather than an eval."""
    return generate(GeneratorConfig(), tmp_dir, tmp_dir / "answer_key.json")


class GradingCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import tempfile
        import pathlib
        cls._tmp = tempfile.TemporaryDirectory()
        cls.world, cls.truth = build_world(pathlib.Path(cls._tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def observed(self):
        """What stage 3 actually sees: names as spelled in each file."""
        part_master = {number: (part.source_type, part.sourcing_list_status)
                       for number, part in self.world.parts.items()}
        suppliers = collections.defaultdict(list)
        lead_times = collections.defaultdict(list)
        for link in self.world.links:
            suppliers[link.part_number].append(link.name_in_suppliers)
        spelling = {(link.part_number, link.supplier_id): link.name_in_lead_times
                    for link in self.world.links}
        for row in self.world.lead_times:
            lead_times[row.part_number].append(
                spelling.get((row.part_number, row.supplier_id), ""))
        return part_master, suppliers, lead_times


class TestFloors(GradingCase):

    def test_the_shipped_threshold_clears_both_floors(self):
        graded = grade_pairs(self.truth.supplier_variants, DEFAULT_THRESHOLD)
        self.assertGreaterEqual(
            graded["precision"], PRECISION_FLOOR,
            "a false merge manufactures a phantom single source; move the "
            "threshold or improve the normaliser, never the floor")
        self.assertGreaterEqual(
            graded["recall"], RECALL_FLOOR,
            "a missed merge understates exposure, which is the error that "
            "stops a line")

    def test_precision_and_recall_are_reported_separately(self):
        graded = grade_pairs(self.truth.supplier_variants, DEFAULT_THRESHOLD)
        self.assertIn("precision", graded)
        self.assertIn("recall", graded)
        self.assertNotIn("f1", graded)
        self.assertNotIn("f_score", graded)

    def test_the_threshold_that_was_rejected_really_does_fail_a_floor(self):
        # 0.90 was the starting point and is kept here as evidence rather than
        # as folklore: it fails precision, which is why the dial moved.
        graded = grade_pairs(self.truth.supplier_variants, 0.90)
        self.assertLess(graded["precision"], PRECISION_FLOOR)
        self.assertGreaterEqual(graded["recall"], RECALL_FLOOR)


class TestSweep(GradingCase):

    def test_recall_is_flat_because_variants_canonicalise_exactly(self):
        # Every variant the generator produces reaches an identical canonical
        # key and merges at 1.0 regardless of threshold. Only precision moves,
        # so the threshold is a precision dial in this data and nothing else.
        recalls = {row["recall"] for row in
                   sweep(self.truth.supplier_variants, [0.80, 0.90, 0.95, 1.0])}
        self.assertEqual(recalls, {1.0})

    def test_precision_does_not_fall_as_the_threshold_rises(self):
        rows = sweep(self.truth.supplier_variants, [0.80, 0.85, 0.90, 0.95, 1.0])
        precisions = [row["precision"] for row in rows]
        self.assertEqual(precisions, sorted(precisions))

    def test_at_least_one_threshold_meets_both_floors(self):
        # If none did, that would be a finding about the normaliser rather than
        # something to resolve by relaxing a floor.
        rows = sweep(self.truth.supplier_variants, [0.80, 0.90, 0.95, 1.0])
        self.assertTrue(any(row["precision"] >= PRECISION_FLOOR
                            and row["recall"] >= RECALL_FLOOR for row in rows))


class TestVerdictImpact(GradingCase):

    def test_false_merges_are_costed_by_consequence_not_just_counted(self):
        # Precision alone cannot separate a false merge on a four-supplier part,
        # which is invisible, from the same merge on a two-supplier part, which
        # is a phantom single source.
        graded = grade_pairs(self.truth.supplier_variants, 0.90)
        part_master, suppliers, lead_times = self.observed()
        parts = {number: (source_type, status, suppliers.get(number, []),
                          lead_times.get(number, []))
                 for number, (source_type, status) in part_master.items()}
        impact = verdict_impact(graded["false_positive"], parts)
        self.assertTrue(impact)
        self.assertEqual([row["verdicts_changed"] for row in impact],
                         sorted((row["verdicts_changed"] for row in impact),
                                reverse=True))
        for row in impact:
            for change in row["changes"]:
                self.assertNotEqual(change["verdict_if_merged"],
                                    change["verdict_if_separate"])

    def test_the_shipped_threshold_leaves_nothing_to_cost(self):
        graded = grade_pairs(self.truth.supplier_variants, DEFAULT_THRESHOLD)
        self.assertEqual(graded["false_positive"], [])


class TestAgainstTruth(GradingCase):

    def test_every_verdict_matches_the_generator_answer_key(self):
        findings = identify_all(*self.observed())
        mismatched = [f.subject for f in findings
                      if f.verdict != self.truth.verdicts[f.subject]]
        self.assertEqual(mismatched, [])

    def test_the_answer_key_is_not_trivially_uniform(self):
        # Guards the test above: matching truth means nothing if truth has one
        # verdict in it.
        self.assertGreater(len(set(self.truth.verdicts.values())), 5)

    def test_every_undecided_finding_is_a_genuine_disagreement(self):
        findings = identify_all(*self.observed())
        for finding in findings:
            if finding.autonomy == "recommends":
                with self.subTest(part=finding.subject):
                    self.assertTrue(finding.evidence["merge_conflict"]
                                    or finding.evidence["readings_conflict"])
                    self.assertEqual(finding.verdict, "readings_disagree")

    def test_no_finding_that_means_nobody_can_tell_is_decided_automatically(self):
        # The defect this catches: both clusterings agree ON readings_disagree,
        # so comparing them alone stamps the finding executes.
        findings = identify_all(*self.observed())
        automatic = [f.subject for f in findings
                     if f.autonomy == "executes"
                     and f.verdict == "readings_disagree"]
        self.assertEqual(automatic, [])

    def test_the_data_actually_contains_undecidable_parts(self):
        # Guards the test above from passing because there is nothing to catch.
        self.assertGreater(
            sum(1 for v in self.truth.verdicts.values()
                if v == "readings_disagree"), 0)


class TestScoringAgainstTheAnswerKey(GradingCase):
    """Scoring against truth, INSIDE the truth boundary.

    Cover values are not checked here and cannot be: computing one requires a
    BOM traversal, so a generator bug and a scoring bug could agree with each
    other. What truth does record is the generator's DECISIONS, which is why
    the abstention SETS are checkable and the numbers are not.
    """

    def profiles(self):
        from src.demand import usage_by_part
        from src.explosion import explode, rows_by_part
        from src.scoring import score_part

        rows = rows_by_part(explode(list(self.world.bom)))
        demand = dict(self.world.demand)
        built = {}
        for number, part in self.world.parts.items():
            if number not in rows:
                continue
            built[number] = score_part(
                part_number=number, verdict=self.truth.verdicts[number],
                rows=rows[number],
                usage=usage_by_part({number: rows[number]}, demand)[number],
                on_hand_units=part.on_hand_units,
                tooling_owner=part.tooling_owner,
                lead_times=[(lt.quoted_lead_time_days, lt.lead_time_p95_days)
                            for lt in self.world.lead_times_for(number)])
        return built

    def test_cover_abstains_on_every_part_truth_says_lacks_on_hand(self):
        profiles = self.profiles()
        abstained = {number for number, profile in profiles.items()
                     if profile.buffer_cover.completeness == "cannot_tell"}
        missing_on_hand = {number for number, intents in self.truth.intents.items()
                           if "on_hand_unknown" in intents and number in profiles}
        self.assertTrue(missing_on_hand)
        self.assertTrue(
            missing_on_hand <= abstained,
            "every part truth recorded as having no on-hand record must "
            "abstain on cover")

    def test_every_other_cover_abstention_is_a_demand_gap_not_an_unexplained_one(self):
        # Cover has exactly two inputs, so it has exactly two reasons to
        # abstain. Any abstention that is neither is a bug rather than a gap,
        # and this is what would catch it.
        profiles = self.profiles()
        missing_on_hand = {number for number, intents in self.truth.intents.items()
                           if "on_hand_unknown" in intents}
        for number, profile in profiles.items():
            if profile.buffer_cover.completeness != "cannot_tell":
                continue
            if number in missing_on_hand:
                continue
            with self.subTest(part=number):
                self.assertIn("demand plan", profile.buffer_cover.reasons[0])

    def test_portability_abstains_on_exactly_the_parts_truth_says_lack_tooling(self):
        profiles = self.profiles()
        abstained = {number for number, profile in profiles.items()
                     if profile.portability.completeness == "cannot_tell"}
        recorded = {number for number, intents in self.truth.intents.items()
                    if "tooling_unknown" in intents and number in profiles}
        self.assertTrue(recorded)
        self.assertEqual(abstained, recorded,
                         "tooling is portability's only input, so the two sets "
                         "must match exactly in both directions")

    def _recorded_zeroes(self, profiles):
        return {number for number, intents in self.truth.intents.items()
                if "on_hand_genuine_zero" in intents and number in profiles}

    def test_a_recorded_zero_with_known_demand_scores_zero_days_of_cover(self):
        # THE REGRESSION GUARD for missing-versus-zero at full scale. A counted
        # and empty part has zero cover, which is an answer and the worst one.
        profiles = self.profiles()
        answered = [number for number in self._recorded_zeroes(profiles)
                    if profiles[number].buffer_cover.completeness != "cannot_tell"]
        self.assertTrue(answered, "the data must contain at least one counted "
                                  "and empty part with usable demand, or this "
                                  "guard proves nothing")
        for number in answered:
            with self.subTest(part=number):
                self.assertEqual(profiles[number].buffer_cover.value, 0)
                self.assertEqual(profiles[number].buffer_cover.completeness,
                                 "known")

    def test_a_recorded_zero_never_abstains_because_of_its_on_hand_figure(self):
        # Where a counted-and-empty part DOES abstain it is the demand input,
        # never the on-hand one. An empty buffer runs out instantly under any
        # positive consumption, but ABSENCE IS NOT ZERO: an unrecorded finished
        # good could genuinely have zero demand, and then an empty buffer never
        # runs out at all. Zero and unbounded are the two answers, the data
        # cannot say which, so it abstains rather than picking the likelier one.
        profiles = self.profiles()
        for number in self._recorded_zeroes(profiles):
            cover = profiles[number].buffer_cover
            if cover.completeness != "cannot_tell":
                continue
            with self.subTest(part=number):
                self.assertIn("demand plan", cover.reasons[0])
                self.assertNotIn("no on-hand record", cover.reasons[0])

    def test_every_dimension_on_every_part_carries_a_reason(self):
        for number, profile in self.profiles().items():
            for score in profile.scored():
                with self.subTest(part=number, dimension=score.dimension):
                    self.assertTrue(score.reasons)

    def test_no_part_is_scored_without_a_unit(self):
        from src.scoring import UNITS
        for profile in self.profiles().values():
            for score in profile.scored():
                self.assertIn(score.unit, UNITS)


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
