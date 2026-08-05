"""annual_usage: the demand-plan join and the completeness it carries.

Expectations come from tests/fixtures/tiny_expected_scores.py, which is written
by hand from the tree in tiny_scoring_bom.csv. Nothing here imports a value the
code under test produced.
"""
import unittest
from fractions import Fraction
from pathlib import Path

from fixtures.tiny_expected_scores import (ABSENT_FINISHED_GOOD,
                                           EXPECTED_BLOCKED_UNITS,
                                           EXPECTED_USAGE,
                                           EXPECTED_USAGE_COMPLETENESS,
                                           SCORED_PARTS)
from src.demand import (USAGE_CANNOT_TELL, USAGE_KNOWN, USAGE_PARTIAL,
                        annual_usage, usage_by_part)
from src.explosion import explode, rows_by_part
from src.readers import read_bom, read_demand_plan

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_rows():
    edges = read_bom(FIXTURES / "tiny_scoring_bom.csv")
    return rows_by_part(explode(edges))


def fixture_demand():
    return read_demand_plan(FIXTURES / "tiny_demand.csv")


class TestAnnualUsage(unittest.TestCase):

    def setUp(self):
        self.rows = fixture_rows()
        self.demand = fixture_demand()
        self.usage = usage_by_part(self.rows, self.demand)

    def test_usage_matches_the_hand_computed_values(self):
        for part in SCORED_PARTS:
            with self.subTest(part=part):
                self.assertEqual(self.usage[part].value, EXPECTED_USAGE[part])

    def test_completeness_matches_the_hand_written_expectations(self):
        for part in SCORED_PARTS:
            with self.subTest(part=part):
                self.assertEqual(self.usage[part].completeness,
                                 EXPECTED_USAGE_COMPLETENESS[part])

    def test_blocked_finished_good_units_match(self):
        for part in SCORED_PARTS:
            with self.subTest(part=part):
                self.assertEqual(self.usage[part].blocked_finished_good_units,
                                 EXPECTED_BLOCKED_UNITS[part])

    def test_usage_is_exact_not_floating_point(self):
        for part in SCORED_PARTS:
            with self.subTest(part=part):
                self.assertIsInstance(self.usage[part].value, Fraction)


class TestTheThreeDemandCases(unittest.TestCase):
    """The three cases the brief names, one test each."""

    def setUp(self):
        self.usage = usage_by_part(fixture_rows(), fixture_demand())

    def test_fully_recorded_demand_is_known(self):
        usage = self.usage["ONLY-M01"]
        self.assertEqual(usage.completeness, USAGE_KNOWN)
        self.assertEqual(usage.absent_finished_goods, ())
        self.assertEqual(usage.value, 1000)

    def test_partial_demand_is_a_bound_not_an_abstention(self):
        # Computed on the recorded finished goods only, and it still answers.
        usage = self.usage["SHARED-M01"]
        self.assertEqual(usage.completeness, USAGE_PARTIAL)
        self.assertEqual(usage.absent_finished_goods, (ABSENT_FINISHED_GOOD,))
        self.assertEqual(usage.recorded_finished_goods, ("FG-M01", "FG-M02"))
        self.assertEqual(usage.value, 3500)
        self.assertTrue(usage.is_partial)

    def test_a_part_fed_only_by_the_absent_finished_good_cannot_tell(self):
        # No known demand at all, so there is nothing to compute a bound FROM.
        usage = self.usage["ORPHAN-M01"]
        self.assertEqual(usage.completeness, USAGE_CANNOT_TELL)
        self.assertEqual(usage.recorded_finished_goods, ())
        self.assertEqual(usage.absent_finished_goods, (ABSENT_FINISHED_GOOD,))


class TestRecordedZeroDemandIsNotAbsence(unittest.TestCase):

    def test_zero_annual_units_is_known_demand_not_missing_demand(self):
        # FG-M04 is in the plan with a recorded 0. That is the plan saying
        # nobody is buying it, which is not the plan failing to say.
        usage = usage_by_part(fixture_rows(), fixture_demand())["ZEROUSE-M01"]
        self.assertEqual(usage.completeness, USAGE_KNOWN)
        self.assertEqual(usage.value, 0)
        self.assertEqual(usage.absent_finished_goods, ())

    def test_zero_demand_and_absent_demand_do_not_produce_the_same_usage(self):
        usage = usage_by_part(fixture_rows(), fixture_demand())
        self.assertEqual(usage["ZEROUSE-M01"].value,
                         usage["ORPHAN-M01"].value,
                         "both sum to zero, which is exactly why the VALUE "
                         "cannot be what distinguishes them")
        self.assertNotEqual(usage["ZEROUSE-M01"].completeness,
                            usage["ORPHAN-M01"].completeness)


class TestDirectionIsNotDecidedHere(unittest.TestCase):

    def test_partial_names_no_bound_direction(self):
        # The same missing row makes cover an upper bound and blast radius a
        # lower one, so naming a direction here would hard-code one consumer's
        # perspective into a function two consumers share.
        usage = usage_by_part(fixture_rows(), fixture_demand())["SHARED-M01"]
        self.assertEqual(usage.completeness, "partial")
        for direction in ("upper", "lower"):
            self.assertNotIn(direction, usage.completeness)


class TestGuards(unittest.TestCase):

    def test_mixing_parts_in_one_call_is_refused(self):
        rows = fixture_rows()
        mixed = list(rows["SHARED-M01"]) + list(rows["ONLY-M01"])
        with self.assertRaises(ValueError):
            annual_usage(mixed, fixture_demand())

    def test_no_rows_is_refused_rather_than_answered_as_zero(self):
        with self.assertRaises(ValueError):
            annual_usage([], fixture_demand())

    def test_reasons_always_travel_with_the_value(self):
        for usage in usage_by_part(fixture_rows(), fixture_demand()).values():
            with self.subTest(part=usage.part_number):
                self.assertTrue(usage.reasons)


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
