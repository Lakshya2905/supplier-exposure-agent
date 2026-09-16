"""The scenario: what stops, whether there is a backup, and how long to fix it.

WHAT THESE TESTS GUARD, in order of how expensive the mistake would be:

  A SECOND IMPLEMENTATION OF THE VERDICT. The counterfactual must come from
  `identify()`, not from reasoning about the answer it already gave. Two
  implementations of one question disagree, and the one nobody looks at drifts.

  A CHOSEN PATH. Naming what could be done is `recommends`; choosing needs
  price, quality history and capacity, none of which are in this data. A "best"
  field, or an ordering by duration, would be the system selecting.

  A DURATION THIS MODULE INVENTED. Every figure returned has to be one the
  scoring library already produced, carried through with its completeness.
"""
import unittest

from src import governance as gov
from src import scenario
from src.pipeline import run, DEMO_DIR
from src.scoring import CANNOT_TELL
from src.synthetic import verdicts as V


class TestTheVocabularyIsPartitioned(unittest.TestCase):

    def test_every_verdict_maps_to_an_outcome(self):
        """A verdict added upstream must be mapped by hand.

        A `.get(verdict, STILL_MULTI)` would classify a new code as harmless on
        the day it appears, and harmless is the reassuring direction.
        """
        self.assertEqual(set(scenario.OUTCOME_OF_VERDICT), {
            V.MADE_IN_HOUSE, V.NO_QUALIFIED_SUPPLIER, V.SUPPLIER_LIST_UNKNOWN,
            V.SINGLE_SOURCE, V.SINGLE_SOURCE_NO_LEAD_TIME, V.MULTI_SOURCE,
            V.MULTI_SOURCE_NO_LEAD_TIMES, V.HIDDEN_SINGLE_SOURCE,
            V.READINGS_DISAGREE,
        })

    def test_nobody_left_and_nobody_confirmed_are_different_outcomes(self):
        """The distinction the lookup exists to keep.

        `no_qualified_supplier` is somebody having checked and found nobody.
        `supplier_list_unknown` is nobody having checked. One stops a line and
        the other sends a person to a filing cabinet.
        """
        self.assertEqual(
            scenario.OUTCOME_OF_VERDICT[V.NO_QUALIFIED_SUPPLIER], scenario.STOPS)
        self.assertEqual(
            scenario.OUTCOME_OF_VERDICT[V.SUPPLIER_LIST_UNKNOWN],
            scenario.UNSETTLED)


class TestTheCounterfactualComesFromIdentify(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.result = run(data_dir=DEMO_DIR)

    def rows(self, supplier):
        return scenario.if_supplier_stops(self.result, supplier)

    def test_removing_the_only_supplier_leaves_nobody(self):
        """Not asserted against a hard-coded part: any part that stops must
        have had exactly this shape, and at least one must exist or the
        scenario is not exercising the branch that matters."""
        stopped = [a for a in self.rows("Lindholm Works")
                   if a.outcome == scenario.STOPS]
        self.assertTrue(stopped, "no part stops; the branch is untested")
        for part in stopped:
            with self.subTest(part=part.part_number):
                self.assertEqual(part.verdict_without, V.NO_QUALIFIED_SUPPLIER)
                self.assertEqual(part.suppliers_remaining, 0)

    def test_a_part_the_supplier_does_not_touch_is_absent(self):
        rows = self.rows("Lindholm Works")
        touched = {a.part_number for a in rows}
        every = set(self.result.sourcing_inputs.supplier_names)
        self.assertTrue(touched < every)

    def test_a_supplier_nobody_supplies_affects_nothing(self):
        self.assertEqual(self.rows("A Company That Does Not Exist"), ())

    def test_the_strike_matches_the_way_the_joins_match(self):
        """Spelling. `sources.csv` and `lead_times.csv` disagree about the same
        company, so striking by raw string would remove it from one file and
        leave it in the other, and the counterfactual would describe a company
        that half exists."""
        spaced = self.rows("  lindholm   works  ")
        self.assertEqual([a.part_number for a in spaced],
                         [a.part_number for a in self.rows("Lindholm Works")])

    def test_the_order_is_worst_first_and_stated(self):
        rows = self.rows("Lindholm Works")
        rank = {outcome: i for i, outcome in enumerate(
            (scenario.STOPS, scenario.SOLE_SOURCED, scenario.UNSETTLED,
             scenario.STILL_MULTI, scenario.DOES_NOT_APPLY))}
        seen = [rank[a.outcome] for a in rows]
        self.assertEqual(seen, sorted(seen))
        self.assertIn("not a score", scenario.order_label())


class TestThePathsAreNamedAndNeverChosen(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.result = run(data_dir=DEMO_DIR)
        cls.rows = scenario.if_supplier_stops(cls.result, "Lindholm Works")

    def test_every_path_is_recommends_forever(self):
        for row in self.rows:
            for path in row.paths:
                with self.subTest(part=row.part_number, path=path.kind):
                    self.assertEqual(path.autonomy, gov.RECOMMENDS)

    def test_no_row_names_a_best_or_chosen_path(self):
        for row in self.rows:
            with self.subTest(part=row.part_number):
                self.assertFalse(
                    {"best", "chosen", "recommended", "preferred", "fastest"}
                    & set(vars(row)))

    def test_the_paths_are_not_ordered_by_duration(self):
        """Sorting by days would be the system selecting, quietly. The order is
        fixed: hold, then switch, then qualify."""
        for row in self.rows:
            kinds = [p.kind for p in row.paths]
            with self.subTest(part=row.part_number):
                if kinds:
                    self.assertEqual(kinds[0], scenario.RIDE_IT_OUT)
                if scenario.QUALIFY in kinds:
                    self.assertEqual(kinds[-1], scenario.QUALIFY)

    def test_stock_is_offered_as_time_bought_not_as_a_fix(self):
        for row in self.rows:
            for path in row.paths:
                if path.kind == scenario.RIDE_IT_OUT:
                    with self.subTest(part=row.part_number):
                        self.assertIn("while", path.label)

    def test_a_remaining_supplier_with_no_lead_time_is_a_path_of_unknown_length(self):
        """Not a missing path, and not zero days. The path exists; how long it
        takes is what nobody recorded."""
        untimed = [p for row in self.rows for p in row.paths
                   if p.kind == scenario.SWITCH_UNTIMED]
        for path in untimed:
            with self.subTest():
                self.assertIsNone(path.days)
                self.assertEqual(path.completeness, CANNOT_TELL)

    def test_a_made_part_is_offered_no_paths_at_all(self):
        for row in self.rows:
            if row.outcome == scenario.DOES_NOT_APPLY:
                with self.subTest(part=row.part_number):
                    self.assertEqual(row.paths, ())


class TestItInventsNoDuration(unittest.TestCase):

    def test_every_duration_is_one_the_library_already_computed(self):
        """The strongest guard here. A path whose number this module produced
        would be a sixth measure nobody tested, arriving with no unit
        discipline and no completeness behind it."""
        result = run(data_dir=DEMO_DIR)
        for row in scenario.if_supplier_stops(result, "Lindholm Works"):
            profile = result.profiles[row.part_number]
            source = {
                scenario.RIDE_IT_OUT: profile.buffer_cover,
                scenario.SWITCH: profile.wait_out_days,
                scenario.QUALIFY: profile.resource_days,
            }
            for path in row.paths:
                if path.kind not in source:
                    continue
                with self.subTest(part=row.part_number, path=path.kind):
                    self.assertEqual(path.days, source[path.kind].value)
                    self.assertEqual(path.completeness,
                                     source[path.kind].completeness)
                    self.assertEqual(path.unit, source[path.kind].unit)
