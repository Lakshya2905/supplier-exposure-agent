"""One test per row of the run-out table, and the expectations are hand-written.

NOTHING HERE IMPORTS `TABLE`. A test that read the table to find its expected
answer would agree with a wrong row, and the two would be wrong together and
silent about it. That is the same rule the sourcing verdict table carries, for
the same reason.

WHAT THIS IS NOT. It is not `buffer_cover - resource_days`, which the README
declines and this does not revive. It compares cover against the PURCHASE lead
time, and it produces an ORDERING rather than a margin: asserted only where the
two intervals do not overlap, abstaining everywhere they do.
"""
import unittest
from fractions import Fraction

from src import runout
from src.scoring import (BUFFER_COVER, CANNOT_TELL, DAYS, DimensionScore,
                         KNOWN, NOT_APPLICABLE, NO_RECOVERY_PATH, UNBOUNDED,
                         UPPER_BOUND, WAIT_OUT_DAYS)


def cover(value, completeness=KNOWN):
    return DimensionScore(part_number="P", dimension=BUFFER_COVER, value=value,
                          unit=DAYS, completeness=completeness, reasons=("c",))


def wait(value, completeness=KNOWN):
    return DimensionScore(part_number="P", dimension=WAIT_OUT_DAYS, value=value,
                          unit=DAYS, completeness=completeness, reasons=("w",))


class Profile:
    """Only the two fields the comparison reads."""

    def __init__(self, buffer_cover, wait_out_days):
        self.part_number = "P"
        self.buffer_cover = buffer_cover
        self.wait_out_days = wait_out_days


def outcome(c, w):
    return runout.run_out(Profile(c, w)).outcome


class TestOneRowEach(unittest.TestCase):

    def test_a_made_part_has_no_lead_time_to_outlast(self):
        self.assertEqual(
            outcome(cover(Fraction(5)), wait(None, NOT_APPLICABLE)),
            "does_not_apply")

    def test_no_supplier_at_all_is_not_a_missing_lead_time(self):
        self.assertEqual(
            outcome(cover(Fraction(5)), wait(None, NO_RECOVERY_PATH)),
            "no_supplier_at_all")

    def test_no_lead_time_on_file_cannot_be_compared(self):
        self.assertEqual(
            outcome(cover(Fraction(5)), wait(None, CANNOT_TELL)), "cannot_say")

    def test_no_stock_count_cannot_be_compared(self):
        self.assertEqual(
            outcome(cover(None, CANNOT_TELL), wait((10, 20))), "cannot_say")

    def test_cover_below_the_fastest_quote_runs_out_first(self):
        self.assertEqual(
            outcome(cover(Fraction(5)), wait((10, 20))), "runs_out_first")

    def test_cover_above_the_worst_case_outlasts_it(self):
        self.assertEqual(
            outcome(cover(Fraction(30)), wait((10, 20))), "outlasts_it")

    def test_cover_inside_the_quote_range_is_too_close_to_call(self):
        self.assertEqual(
            outcome(cover(Fraction(15)), wait((10, 20))), "too_close_to_call")

    def test_an_upper_bound_above_the_quote_has_no_floor_under_it(self):
        self.assertEqual(
            outcome(cover(Fraction(30), UPPER_BOUND), wait((10, 20))),
            "cannot_say")


class TestTheDistinctionsTheTableExistsToKeep(unittest.TestCase):

    def test_an_upper_bound_below_the_quote_still_settles_it(self):
        """A CEILING settles the comparison downward and nothing else does.

        "at most 5 days" against a 10-day quote is 5 days or fewer against 10,
        which runs out first however much demand nobody recorded. The same
        ceiling above the quote settles nothing, and the row above asserts that.
        """
        self.assertEqual(
            outcome(cover(Fraction(5), UPPER_BOUND), wait((10, 20))),
            "runs_out_first")

    def test_unbounded_cover_outlasts_any_lead_time(self):
        """Stock with nothing consuming it is an answer, not a gap."""
        self.assertEqual(
            outcome(cover(UNBOUNDED), wait((10, 20))), "outlasts_it")

    def test_equal_to_the_quote_is_not_runs_out_first(self):
        """The boundary is crossed strictly. Equal is inside the range."""
        self.assertEqual(
            outcome(cover(Fraction(10)), wait((10, 20))), "too_close_to_call")

    def test_equal_to_the_worst_case_is_not_outlasts(self):
        self.assertEqual(
            outcome(cover(Fraction(20)), wait((10, 20))), "too_close_to_call")

    def test_a_made_part_with_no_stock_count_still_does_not_apply(self):
        """The wait side is read first: the question does not arise at all."""
        self.assertEqual(
            outcome(cover(None, CANNOT_TELL), wait(None, NOT_APPLICABLE)),
            "does_not_apply")


class TestItCarriesNoMargin(unittest.TestCase):

    def test_the_result_holds_no_difference_of_the_two_figures(self):
        """The README declines a margin, and this must not smuggle one back.

        It carries the two figures it compared, which is evidence, and nothing
        derived from both, which would be the subtraction.
        """
        result = runout.run_out(Profile(cover(Fraction(5)), wait((10, 20))))
        self.assertEqual(result.cover_days, Fraction(5))
        self.assertEqual((result.quoted_days, result.p95_days), (10, 20))
        for value in vars(result).values():
            self.assertNotIn(value, (-5, 5 - 10, Fraction(-5)))

    def test_every_outcome_carries_a_reason(self):
        for c, w in ((cover(Fraction(5)), wait((10, 20))),
                     (cover(None, CANNOT_TELL), wait((10, 20))),
                     (cover(Fraction(5)), wait(None, NOT_APPLICABLE))):
            result = runout.run_out(Profile(c, w))
            with self.subTest(outcome=result.outcome):
                self.assertTrue(result.reasons and result.reasons[0])
                self.assertNotIn(result.outcome, result.reasons[0])
