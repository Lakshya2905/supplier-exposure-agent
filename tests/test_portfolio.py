"""The supplier view: two counts, never a score, and no correlation claim.

WHAT THESE TESTS ARE GUARDING. The brief permits a portfolio-level ranking
across suppliers because its job is triage, and the temptation that comes with
that permission is a single supplier score -- which is the thing every
competitor ships and the thing this product exists to refuse one level down.
So the tests assert the absences as hard as the presences: no blend of the two
axes, no imputation of an unsettled part, and no inference that parts on one
supplier share a fate.
"""
import unittest

from src import governance as gov
from src import portfolio
from src.synthetic import verdicts as V


def rows(pairs, verdicts, region="europe"):
    return portfolio.by_supplier(
        tuple((part, supplier, region) for part, supplier in pairs), verdicts)


class TestTheVocabularyIsPartitioned(unittest.TestCase):

    def test_every_verdict_is_classified_exactly_once(self):
        """A verdict added upstream must be classified by hand, not defaulted.

        Deriving "not exposed" as everything else would classify a NEW verdict
        as safe on the day it is introduced, and the cost of that error is a
        supplier reading clean because nobody had triaged a new code yet.
        """
        known = (portfolio.EXPOSED_VERDICTS | portfolio.UNSETTLED_VERDICTS
                 | portfolio.NOT_EXPOSED_VERDICTS)
        vocabulary = {
            V.MADE_IN_HOUSE, V.NO_QUALIFIED_SUPPLIER, V.SUPPLIER_LIST_UNKNOWN,
            V.SINGLE_SOURCE, V.SINGLE_SOURCE_NO_LEAD_TIME, V.MULTI_SOURCE,
            V.MULTI_SOURCE_NO_LEAD_TIMES, V.HIDDEN_SINGLE_SOURCE,
            V.READINGS_DISAGREE,
        }
        self.assertEqual(known, vocabulary)
        for pair in ((portfolio.EXPOSED_VERDICTS, portfolio.UNSETTLED_VERDICTS),
                     (portfolio.EXPOSED_VERDICTS, portfolio.NOT_EXPOSED_VERDICTS),
                     (portfolio.UNSETTLED_VERDICTS, portfolio.NOT_EXPOSED_VERDICTS)):
            self.assertEqual(pair[0] & pair[1], set())


class TestAnUnsettledPartIsNeverAnUnexposedOne(unittest.TestCase):

    def test_an_unsettled_part_is_not_counted_as_exposed(self):
        row, = rows([("P1", "S")], {"P1": V.SUPPLIER_LIST_UNKNOWN})
        self.assertEqual(row.exposed_parts, 0)
        self.assertEqual(row.parts_unsettled, 1)

    def test_and_the_count_says_it_can_only_rise(self):
        """The whole point. A smaller number here reads as a smaller risk."""
        row, = rows([("P1", "S"), ("P2", "S")],
                    {"P1": V.SINGLE_SOURCE, "P2": V.READINGS_DISAGREE})
        self.assertEqual(row.exposed_parts, 1)
        self.assertTrue(row.exposed_is_lower_bound)

    def test_a_settled_supplier_carries_no_bound(self):
        row, = rows([("P1", "S"), ("P2", "S")],
                    {"P1": V.SINGLE_SOURCE, "P2": V.MULTI_SOURCE})
        self.assertEqual(row.exposed_parts, 1)
        self.assertFalse(row.exposed_is_lower_bound)

    def test_a_part_with_no_verdict_at_all_is_unsettled_not_safe(self):
        row, = rows([("P1", "S")], {})
        self.assertEqual(row.exposed_parts, 0)
        self.assertEqual(row.parts_unsettled, 1)
        self.assertTrue(row.exposed_is_lower_bound)


class TestTheTwoAxesAreNeverCombined(unittest.TestCase):

    def test_the_row_carries_no_field_derived_from_both_counts(self):
        """No score, no product, no ratio, no share-of-total.

        A supplier row is where a composite would reappear after being refused
        per part, because "one number to triage on" is exactly what the market
        sells. The two counts are carried and nothing is computed across them.
        """
        # FOUR AND THREE, CHOSEN SO A BLEND IS VISIBLE. With two parts and one
        # exposed, the product is 2 and so is `parts_supplied`, and a score
        # field would hide inside a legitimate count. 4 and 3 give 12 and 7,
        # which are neither.
        row, = rows([("P1", "S"), ("P2", "S"), ("P3", "S"), ("P4", "S")],
                    {"P1": V.SINGLE_SOURCE, "P2": V.SINGLE_SOURCE,
                     "P3": V.SINGLE_SOURCE, "P4": V.MULTI_SOURCE})
        self.assertEqual((row.parts_supplied, row.exposed_parts), (4, 3))
        numbers = {v for v in vars(row).values() if isinstance(v, int)
                   and not isinstance(v, bool)}
        # Exactly the three counts, and nothing a blend could have produced.
        self.assertEqual(numbers, {4, 3, 0})
        for blend in (4 * 3, 4 + 3, 4 - 3):
            with self.subTest(blend=blend):
                self.assertNotIn(blend, numbers - {4, 3, 0})

    def test_more_of_the_build_does_not_make_a_supplier_rank_higher(self):
        """Ordering is by ONE axis. Carrying more parts is not, by itself,
        worse, and a supplier with twenty settled multi-source parts must not
        outrank one with a single sole-sourced part."""
        big, small = rows(
            [(f"P{i}", "Big") for i in range(20)] + [("X", "Small")],
            {**{f"P{i}": V.MULTI_SOURCE for i in range(20)},
             "X": V.SINGLE_SOURCE})
        self.assertEqual(big.supplier, "Small")
        self.assertEqual(small.supplier, "Big")


class TestTheOrderIsTotalAndStated(unittest.TestCase):

    def test_ties_are_broken_to_a_single_arrangement(self):
        first = rows([("P1", "B"), ("P2", "A")],
                     {"P1": V.SINGLE_SOURCE, "P2": V.SINGLE_SOURCE})
        second = rows([("P2", "A"), ("P1", "B")],
                      {"P2": V.SINGLE_SOURCE, "P1": V.SINGLE_SOURCE})
        self.assertEqual([r.supplier for r in first], ["A", "B"])
        self.assertEqual([r.supplier for r in first],
                         [r.supplier for r in second])

    def test_the_order_names_the_axis_it_sorted_on(self):
        label = portfolio.order_label()
        self.assertIn("one real source", label)
        self.assertIn("never combined", label)


class TestItDrillsThroughAndClaimsNoCorrelation(unittest.TestCase):

    def test_the_row_carries_its_parts(self):
        """A supplier view that cannot reach part detail is the index this
        product refuses, one level up."""
        row, = rows([("P1", "S"), ("P2", "S")],
                    {"P1": V.SINGLE_SOURCE, "P2": V.MULTI_SOURCE})
        self.assertEqual(row.part_numbers, ("P1", "P2"))
        self.assertEqual(row.exposed_part_numbers, ("P1",))

    def test_it_executes_because_it_asserts_no_shared_fate(self):
        """Counting a field that was read is a fact. Claiming the parts under
        it are CORRELATED is a judgment, and it stays in `concentration`, which
        is `recommends` permanently."""
        row, = rows([("P1", "S")], {"P1": V.SINGLE_SOURCE})
        self.assertEqual(row.autonomy, gov.EXECUTES)
        self.assertFalse(any("correlat" in str(v).lower()
                             for v in vars(row).values()))
