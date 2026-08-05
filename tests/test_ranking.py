"""Ranking: the orders that exist, and no order that does not.

Two properties get the most attention here because both are the kind that hold
today by accident of implementation and stop holding silently:

  the default order is ARBITRARY AND STABLE
  the work queue IMPUTES NOTHING
"""
import random
import unittest
from fractions import Fraction
from pathlib import Path

from codescan import code_of
from src import archetypes as A
from src import governance as gov
from src import ranking
from src import scoring
from src.demand import USAGE_KNOWN, USAGE_PARTIAL, Usage

CONFIGURED = {"version": "test-v1", "long_lead_days": 90, "thin_cover_days": 14}


def build(part, on_hand=100, tooling="company", lead_times=((30, 45),),
          usage_value=1000, usage_completeness=USAGE_KNOWN, blocked=1000,
          verdict="single_source"):
    usage = Usage(part, Fraction(usage_value), usage_completeness,
                  blocked_finished_good_units=blocked, reasons=("fixture",))
    return scoring.score_part(
        part_number=part, verdict=verdict, rows=(), usage=usage,
        on_hand_units=on_hand, tooling_owner=tooling,
        lead_times=list(lead_times))


class TestDefaultOrder(unittest.TestCase):
    """Arbitrary AND stable. Both halves matter and for different reasons."""

    def test_the_default_order_is_by_part_number(self):
        self.assertEqual(ranking.DEFAULT_ORDER_FIELD, "part_number")

    def test_the_default_order_is_labelled(self):
        # A plausible default is read as a ranking within minutes and nobody
        # checks, so the label is not decoration.
        self.assertIn("part number", ranking.DEFAULT_ORDER_LABEL)
        self.assertIn("choose a dimension", ranking.DEFAULT_ORDER_LABEL)

    def test_the_default_order_is_not_insertion_order(self):
        # INSERTION AND DICT ORDER ARE ARBITRARY TODAY AND MEANINGFUL TOMORROW.
        # They silently acquire an ordering the moment an upstream function
        # changes how it iterates, and nobody can see that it happened.
        inserted = ["ZZ-P-09", "AA-P-01", "MM-P-05"]
        self.assertEqual(ranking.in_default_order(inserted),
                         ("AA-P-01", "MM-P-05", "ZZ-P-09"))
        self.assertNotEqual(ranking.in_default_order(inserted),
                            tuple(inserted))

    def test_the_default_order_is_deterministic_across_runs(self):
        parts = [f"SEA-P-{index:04d}" for index in range(40)]
        first = ranking.in_default_order(parts)
        for seed in range(12):
            shuffled = list(parts)
            random.Random(seed).shuffle(shuffled)
            with self.subTest(seed=seed):
                self.assertEqual(ranking.in_default_order(shuffled), first)

    def test_group_membership_is_deterministic_across_input_orderings(self):
        profiles = [build("ZZ-P-09", tooling="supplier"),
                    build("AA-P-01", tooling="supplier"),
                    build("MM-P-05", tooling="supplier")]
        verdicts = {p.part_number: "single_source" for p in profiles}
        catalogue = A.catalogue(None)
        expected = ranking.default_view(profiles, verdicts, catalogue)
        for seed in range(8):
            shuffled = list(profiles)
            random.Random(seed).shuffle(shuffled)
            view = ranking.default_view(shuffled, verdicts, catalogue)
            with self.subTest(seed=seed):
                self.assertEqual(
                    [[g.members for g in layer] for layer in view["layers"]],
                    [[g.members for g in layer]
                     for layer in expected["layers"]])

    def test_the_view_carries_its_order_label(self):
        view = ranking.default_view([build("AA-P-01")], {"AA-P-01": "single_source"},
                                    A.catalogue(None))
        self.assertEqual(view["order_label"], ranking.DEFAULT_ORDER_LABEL)
        for layer in view["layers"]:
            for group in layer:
                self.assertEqual(group.order_label, ranking.DEFAULT_ORDER_LABEL)

    def test_sorting_never_relies_on_dict_iteration(self):
        code = code_of(ranking.in_default_order)
        self.assertIn("sorted", code)
        self.assertIn("key", code)


class TestWorkQueueImputesNothing(unittest.TestCase):
    """The ranking criterion is 'could this field change the outcome', evaluated
    against the conditions as they stand with the field unknown."""

    def queue(self, profiles, catalogue=None):
        catalogue = catalogue or A.catalogue(None)
        verdicts = {p.part_number: "single_source" for p in profiles}
        return ranking.work_queue(
            ranking.classify(profiles, verdicts, catalogue), catalogue)

    def test_a_part_a_missing_field_could_move_is_queued(self):
        queued = self.queue([build("AA-P-01", on_hand=None,
                                   tooling="supplier")])
        self.assertIn("counted_empty_single_source", queued)
        self.assertEqual(
            [item.part_number
             for item in queued["counted_empty_single_source"]], ["AA-P-01"])

    def test_a_part_a_missing_field_cannot_move_is_not_queued(self):
        # On-hand is missing, but the part is multi-source, so no on-hand value
        # could ever make it match. Listing it would waste a real trip to a
        # real system.
        profiles = [build("AA-P-01", on_hand=None, verdict="multi_source")]
        verdicts = {"AA-P-01": "multi_source"}
        catalogue = A.catalogue(None)
        queued = ranking.work_queue(
            ranking.classify(profiles, verdicts, catalogue), catalogue)
        self.assertNotIn("counted_empty_single_source", queued)

    def test_no_queued_part_has_a_definitely_false_condition(self):
        profiles = [build("AA-P-01", on_hand=None, tooling=""),
                    build("BB-P-02", on_hand=None, tooling="supplier"),
                    build("CC-P-03", on_hand=0, tooling="")]
        verdicts = {p.part_number: "single_source" for p in profiles}
        catalogue = A.catalogue(None)
        memberships = ranking.classify(profiles, verdicts, catalogue)
        queued = ranking.work_queue(memberships, catalogue)
        for archetype_name, items in queued.items():
            for item in items:
                with self.subTest(part=item.part_number, a=archetype_name):
                    values = memberships[
                        (item.part_number, archetype_name)].values
                    self.assertNotIn(A.FALSE, values.values())

    def test_the_queue_order_ignores_every_dimension_value(self):
        # THE DIRECT ASSERTION. Both parts are missing on-hand. ZZ has a blast
        # radius sixty times bigger and a far longer lead time, so any ordering
        # that consulted a dimension, or imputed a cover from one, would put ZZ
        # first. The queue is by part number, so AA is first.
        profiles = [
            build("ZZ-P-09", on_hand=None, tooling="supplier", blocked=60000,
                  lead_times=((400, 500),)),
            build("AA-P-01", on_hand=None, tooling="supplier", blocked=10,
                  lead_times=((5, 6),)),
        ]
        queued = self.queue(profiles)["counted_empty_single_source"]
        self.assertEqual([item.part_number for item in queued],
                         ["AA-P-01", "ZZ-P-09"])

    def test_the_queue_order_is_unchanged_when_other_values_swap(self):
        # Same two parts with their dimension values exchanged. If any value
        # reached the ordering, this would reverse it.
        swapped = [
            build("ZZ-P-09", on_hand=None, tooling="supplier", blocked=10,
                  lead_times=((5, 6),)),
            build("AA-P-01", on_hand=None, tooling="supplier", blocked=60000,
                  lead_times=((400, 500),)),
        ]
        queued = self.queue(swapped)["counted_empty_single_source"]
        self.assertEqual([item.part_number for item in queued],
                         ["AA-P-01", "ZZ-P-09"])

    def test_a_work_item_carries_no_value_for_the_missing_field(self):
        # Six parts where supplying on-hand could flip them is honest. Six
        # parts ordered by a guessed cover is a forecast wearing a work queue's
        # clothes, and there is nowhere to put the guess.
        fields = ranking.WorkItem.__dataclass_fields__
        self.assertEqual(set(fields),
                         {"part_number", "archetype", "missing_fields"})
        for forbidden in ("estimated", "assumed", "imputed", "projected",
                          "likely", "expected_value", "default"):
            with self.subTest(field=forbidden):
                self.assertNotIn(forbidden, fields)

    def test_the_queue_names_the_field_to_fetch(self):
        queued = self.queue([build("AA-P-01", on_hand=None,
                                   tooling="supplier")])
        item = queued["counted_empty_single_source"][0]
        self.assertEqual(item.missing_fields, ("on_hand_units",))

    def test_nothing_in_the_queue_code_imputes(self):
        code = code_of(ranking.work_queue)
        for forbidden in ("impute", "assume", "estimate", "guess", "plausible",
                          "projected", "fillna", "or 0"):
            with self.subTest(word=forbidden):
                self.assertNotIn(forbidden, code)


class TestRankByDimension(unittest.TestCase):
    """A total order inside one unit is honest. That is the only total order."""

    def profiles(self):
        return [
            build("AA-P-01", on_hand=1000),   # cover 365 days
            build("BB-P-02", on_hand=100),    # cover 36.5 days
            build("CC-P-03", on_hand=0),      # cover 0 days, the worst
            build("DD-P-04", on_hand=None),   # no cover at all
        ]

    def test_cover_ranks_least_first_because_less_cover_is_worse(self):
        ranked, _ = ranking.rank_by(self.profiles(), scoring.BUFFER_COVER)
        self.assertEqual([p.part_number for p in ranked],
                         ["CC-P-03", "BB-P-02", "AA-P-01"])

    def test_an_abstention_is_not_ranked_at_either_end(self):
        # A value that does not exist has no position, and putting it at an end
        # is a claim about where it would have been.
        ranked, not_comparable = ranking.rank_by(self.profiles(),
                                                 scoring.BUFFER_COVER)
        self.assertNotIn("DD-P-04", [p.part_number for p in ranked])
        self.assertIn("DD-P-04", not_comparable)

    def test_lead_time_ranks_longest_first(self):
        profiles = [build("AA-P-01", lead_times=((10, 12),)),
                    build("BB-P-02", lead_times=((300, 400),))]
        ranked, _ = ranking.rank_by(profiles, scoring.LEAD_TIME_TO_RECOVER)
        self.assertEqual([p.part_number for p in ranked],
                         ["BB-P-02", "AA-P-01"])

    def test_no_recovery_path_sorts_worst_without_a_number(self):
        profiles = [build("AA-P-01", lead_times=((300, 400),)),
                    build("BB-P-02", verdict="no_qualified_supplier",
                          lead_times=())]
        ranked, _ = ranking.rank_by(profiles, scoring.LEAD_TIME_TO_RECOVER)
        self.assertEqual(ranked[0].part_number, "BB-P-02")

    def test_ties_fall_back_to_the_arbitrary_stable_order(self):
        profiles = [build("ZZ-P-09", on_hand=100), build("AA-P-01", on_hand=100)]
        ranked, _ = ranking.rank_by(profiles, scoring.BUFFER_COVER)
        self.assertEqual([p.part_number for p in ranked],
                         ["AA-P-01", "ZZ-P-09"])

    def test_ranking_is_deterministic_across_input_orderings(self):
        profiles = self.profiles()
        expected, _ = ranking.rank_by(profiles, scoring.BUFFER_COVER)
        for seed in range(8):
            shuffled = list(profiles)
            random.Random(seed).shuffle(shuffled)
            ranked, _ = ranking.rank_by(shuffled, scoring.BUFFER_COVER)
            with self.subTest(seed=seed):
                self.assertEqual([p.part_number for p in ranked],
                                 [p.part_number for p in expected])

    def test_every_dimension_declares_which_end_is_worse(self):
        for dimension in scoring.DIMENSIONS:
            with self.subTest(dimension=dimension):
                self.assertIn(dimension, ranking.WORSE_IS)

    def test_direction_is_not_a_threshold(self):
        # WORSE_IS says which way is bad, never where bad begins.
        for value in ranking.WORSE_IS.values():
            self.assertIn(value, ("higher", "lower", "categorical"))
            self.assertNotIsInstance(value, (int, float))


class TestNoOverallRanking(unittest.TestCase):

    def test_no_function_produces_a_single_overall_order(self):
        for forbidden in ("overall", "total_rank", "composite", "final_score",
                          "weighted"):
            with self.subTest(name=forbidden):
                self.assertFalse(hasattr(ranking, forbidden))

    def test_no_count_of_matched_archetypes_is_computed(self):
        # THE COUNT TRAP. Ordering by how many archetypes a part matches looks
        # like counting and is a weighted sum with every weight set to 1. Two
        # matches is not worse than one unless one dominates the other, and
        # dominance is already expressed properly.
        code = code_of(ranking, functions_only=True)
        for forbidden in ("match_count", "archetype_count", "n_matched",
                          "len(matched", "sum("):
            with self.subTest(word=forbidden):
                self.assertNotIn(forbidden, code)

    def test_no_module_function_weights_anything(self):
        code = code_of(ranking, functions_only=True)
        for forbidden in ("weight", "composite", "normalise", "normalize"):
            with self.subTest(word=forbidden):
                self.assertNotIn(forbidden, code)

    def test_the_view_returns_layers_rather_than_one_ordered_list(self):
        # Incomparable archetypes come back in the same layer so a display can
        # place them side by side and decline, in the layout, to imply an order
        # that does not exist.
        view = ranking.default_view([build("AA-P-01", tooling="supplier")],
                                    {"AA-P-01": "single_source"},
                                    A.catalogue(None))
        self.assertGreater(len(view["layers"]), 1)
        self.assertTrue(any(len(layer) > 1 for layer in view["layers"]))


class TestTheSentence(unittest.TestCase):

    def test_the_sentence_stores_structure_and_no_prose(self):
        from src.governance.render import render
        profile = build("SEA-P-0248", on_hand=1734, usage_value=57000,
                        usage_completeness=USAGE_PARTIAL, tooling="supplier",
                        lead_times=((182, 266),))
        log = gov.DecisionLog()
        ranking.log_ranked(log, profile, "single_source",
                           ["the resourcing trap"])
        event = list(log)[0]
        self.assertNotIn(render(event), repr(event.evidence))
        self.assertNotIn("at most", repr(event.evidence))

    def test_exact_values_are_stored_and_rounded_only_at_render(self):
        # 100 units against 1000 a year is 100 x 365 / 1000 = 36.5 days, which
        # is Fraction(73, 2). Stored exact; the renderer is the only place that
        # turns it into "36.5".
        from src.governance.render import render
        profile = build("AA-P-01", on_hand=100)
        evidence = ranking.sentence_evidence(profile, "single_source")
        cover = [c for c in evidence["clauses"]
                 if c["dimension"] == "buffer_cover"][0]
        self.assertEqual(cover["value"], [73, 2])
        log = gov.DecisionLog()
        ranking.log_ranked(log, profile, "single_source")
        self.assertIn("36.5 days of cover", render(list(log)[0]))

    def test_an_abstention_appears_as_words_not_a_blank(self):
        from src.governance.render import render
        profile = build("AA-P-01", on_hand=None, tooling="")
        log = gov.DecisionLog()
        ranking.log_ranked(log, profile, "single_source")
        sentence = render(list(log)[0])
        self.assertIn("no on-hand record", sentence)
        self.assertIn("no tooling owner recorded", sentence)

    def test_every_number_in_the_sentence_carries_its_unit(self):
        from src.governance.render import render
        profile = build("AA-P-01", on_hand=100, tooling="supplier")
        log = gov.DecisionLog()
        ranking.log_ranked(log, profile, "single_source")
        sentence = render(list(log)[0])
        self.assertIn("days", sentence)
        self.assertIn("finished good units", sentence)


class TestMagnitudeFindingsCarryTheirThreshold(unittest.TestCase):

    def test_a_magnitude_membership_records_its_config_version(self):
        profile = build("AA-P-01", on_hand=0, tooling="supplier",
                        lead_times=((200, 300),))
        catalogue = A.catalogue(CONFIGURED)
        memberships = ranking.classify([profile], {"AA-P-01": "single_source"},
                                       catalogue)
        headline = memberships[("AA-P-01", "headline_exposure")]
        self.assertEqual(headline.state, A.MATCHED)
        self.assertIn("test-v1", headline.threshold_source)
        self.assertEqual(headline.autonomy, gov.RECOMMENDS)

    def test_a_structural_membership_has_no_threshold_source(self):
        profile = build("AA-P-01", tooling="supplier")
        memberships = ranking.classify([profile], {"AA-P-01": "single_source"},
                                       A.catalogue(None))
        trap = memberships[("AA-P-01", "resourcing_trap")]
        self.assertEqual(trap.threshold_source, "")
        self.assertEqual(trap.autonomy, gov.EXECUTES)


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
