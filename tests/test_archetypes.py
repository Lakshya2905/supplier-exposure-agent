"""Archetypes: named conjunctions, three-valued membership, no scores.

SELF-AGREEMENT GUARD. Every expected membership below is written out by hand.
Nothing here iterates the catalogue to build its own expectations, because the
corrections log records that a hand-written expectation is necessary and not
sufficient: stage 5's contingency bug had hand-written expectations and still
passed, by testing the wrong noun.
"""
import inspect
import unittest
from fractions import Fraction
from pathlib import Path

from codescan import code_of
from src import archetypes as A
from src import governance as gov
from src import scoring
from src.demand import USAGE_KNOWN, USAGE_PARTIAL, Usage

CONFIG = Path(__file__).resolve().parent.parent / "config" / "archetypes.yaml"

CONFIGURED = {"version": "test-v1", "long_lead_days": 90, "thin_cover_days": 14}


def profile(part="P", on_hand=100, tooling="company", lead_times=((30, 45),),
            usage_value=1000, usage_completeness=USAGE_KNOWN,
            verdict="single_source", concentration=None):
    usage = Usage(part, Fraction(usage_value), usage_completeness,
                  blocked_finished_good_units=1000,
                  reasons=("fixture",))
    built = scoring.score_part(
        part_number=part, verdict=verdict, rows=(), usage=usage,
        on_hand_units=on_hand, tooling_owner=tooling,
        lead_times=list(lead_times))
    if concentration is not None:
        import dataclasses
        built = dataclasses.replace(built, concentration=concentration)
    return built


def concentration_score(part="P", completeness=scoring.KNOWN, agreement="both"):
    from src.concentration import ConcentrationScore
    return ConcentrationScore(
        part_number=part, dimension="concentration",
        value=None if completeness in (scoring.CANNOT_TELL,
                                       scoring.NOT_APPLICABLE) else 3,
        unit=scoring.PARTS, completeness=completeness, agreement=agreement,
        reasons=("fixture",))


def state(archetype, prof, verdict="single_source"):
    return A.membership(
        archetype.evaluate({"profile": prof, "verdict": verdict}).values())


class TestKleeneLogic(unittest.TestCase):
    """The truth table, asserted directly rather than inferred from behaviour."""

    def test_all_true_is_true(self):
        self.assertEqual(A.conjoin([A.TRUE, A.TRUE]), A.TRUE)

    def test_any_false_is_false(self):
        self.assertEqual(A.conjoin([A.TRUE, A.FALSE]), A.FALSE)

    def test_false_beats_unknown(self):
        # THE LOAD-BEARING ROW. Without it every part carrying any abstention
        # falls into "cannot tell", the bucket swallows the dataset, and its one
        # useful property is lost.
        self.assertEqual(A.conjoin([A.FALSE, A.UNKNOWN]), A.FALSE)
        self.assertEqual(A.conjoin([A.UNKNOWN, A.FALSE]), A.FALSE)

    def test_unknown_with_true_is_unknown(self):
        self.assertEqual(A.conjoin([A.TRUE, A.UNKNOWN]), A.UNKNOWN)

    def test_all_unknown_is_unknown(self):
        self.assertEqual(A.conjoin([A.UNKNOWN, A.UNKNOWN]), A.UNKNOWN)

    def test_membership_maps_the_three_values(self):
        self.assertEqual(A.membership([A.TRUE]), A.MATCHED)
        self.assertEqual(A.membership([A.FALSE]), A.EXCLUDED)
        self.assertEqual(A.membership([A.UNKNOWN]), A.CANNOT_TELL)


class TestOneTestPerArchetype(unittest.TestCase):
    """Expectations hard-coded, one archetype at a time."""

    def test_resourcing_trap_matches_single_source_with_supplier_tooling(self):
        self.assertEqual(
            state(A.RESOURCING_TRAP, profile(tooling="supplier")), A.MATCHED)

    def test_resourcing_trap_excludes_company_owned_tooling(self):
        self.assertEqual(
            state(A.RESOURCING_TRAP, profile(tooling="company")), A.EXCLUDED)

    def test_resourcing_trap_excludes_a_multi_source_part(self):
        self.assertEqual(
            state(A.RESOURCING_TRAP, profile(tooling="supplier",
                                             verdict="multi_source"),
                  verdict="multi_source"), A.EXCLUDED)

    def test_nobody_to_call_matches_a_verified_empty_list(self):
        self.assertEqual(
            state(A.NOBODY_TO_CALL, profile(verdict="no_qualified_supplier",
                                            lead_times=()),
                  verdict="no_qualified_supplier"), A.MATCHED)

    def test_nobody_to_call_excludes_an_unconfirmed_list(self):
        self.assertEqual(
            state(A.NOBODY_TO_CALL, profile(verdict="supplier_list_unknown",
                                            lead_times=()),
                  verdict="supplier_list_unknown"), A.EXCLUDED)

    def test_no_quotable_single_source_matches_when_no_lead_time_exists(self):
        self.assertEqual(
            state(A.NO_QUOTABLE_SINGLE_SOURCE,
                  profile(verdict="single_source_no_lead_time", lead_times=()),
                  verdict="single_source_no_lead_time"), A.MATCHED)

    def test_no_quotable_single_source_excludes_a_quoted_part(self):
        self.assertEqual(
            state(A.NO_QUOTABLE_SINGLE_SOURCE, profile()), A.EXCLUDED)

    def test_counted_empty_matches_a_recorded_zero(self):
        # A STRUCTURAL fact, not a band: on_hand of 0 gives cover of 0 by
        # arithmetic, with no threshold deciding what "thin" means.
        self.assertEqual(
            state(A.COUNTED_EMPTY_SINGLE_SOURCE, profile(on_hand=0)),
            A.MATCHED)

    def test_counted_empty_excludes_a_stocked_part(self):
        self.assertEqual(
            state(A.COUNTED_EMPTY_SINGLE_SOURCE, profile(on_hand=500)),
            A.EXCLUDED)

    def test_counted_empty_cannot_tell_when_on_hand_is_missing(self):
        self.assertEqual(
            state(A.COUNTED_EMPTY_SINGLE_SOURCE, profile(on_hand=None)),
            A.CANNOT_TELL)

    def test_correlated_resourcing_trap_matches_all_three(self):
        self.assertEqual(
            state(A.CORRELATED_RESOURCING_TRAP,
                  profile(tooling="supplier",
                          concentration=concentration_score())), A.MATCHED)

    def test_correlated_resourcing_trap_excludes_an_uncorrelated_part(self):
        self.assertEqual(
            state(A.CORRELATED_RESOURCING_TRAP,
                  profile(tooling="supplier",
                          concentration=concentration_score(
                              agreement="neither"))), A.EXCLUDED)

    def test_a_part_with_nobody_to_correlate_with_is_excluded_not_unknown(self):
        # NOT_APPLICABLE is a definite negative, so it excludes rather than
        # producing an abstention. Treating it as unknown would park the most
        # exposed parts in the work queue forever.
        self.assertEqual(
            state(A.CORRELATED_RESOURCING_TRAP,
                  profile(tooling="supplier",
                          concentration=concentration_score(
                              completeness=scoring.NOT_APPLICABLE,
                              agreement=""))), A.EXCLUDED)


class TestExclusionSurvivesAbstention(unittest.TestCase):

    def test_a_definitely_false_condition_excludes_despite_an_abstention(self):
        # Missing tooling makes one condition unknown; the multi-source verdict
        # makes another definitely false. The part is EXCLUDED, not undecided,
        # because no tooling value could rescue it.
        prof = profile(tooling="", verdict="multi_source")
        self.assertEqual(state(A.RESOURCING_TRAP, prof,
                               verdict="multi_source"), A.EXCLUDED)

    def test_the_same_abstention_leaves_it_undecided_when_nothing_else_fails(self):
        prof = profile(tooling="", verdict="single_source")
        self.assertEqual(state(A.RESOURCING_TRAP, prof), A.CANNOT_TELL)


class TestMagnitudeArchetypesShipDisabled(unittest.TestCase):

    def test_the_shipped_config_sets_no_thresholds(self):
        self.assertIsNone(A.load_thresholds(CONFIG),
                          "a default threshold is a judgment the system made "
                          "on a reviewer's behalf and attributed to nobody")

    def test_no_magnitude_archetype_exists_without_a_config(self):
        names = [a.name for a in A.catalogue(A.load_thresholds(CONFIG))]
        self.assertNotIn("headline_exposure", names)
        self.assertNotIn("long_lead_single_source", names)
        for archetype in A.catalogue(None):
            with self.subTest(archetype=archetype.name):
                self.assertEqual(archetype.kind, A.STRUCTURAL)

    def test_a_missing_config_file_disables_them_rather_than_raising(self):
        self.assertIsNone(A.load_thresholds(CONFIG.parent / "nope.yaml"))

    def test_structural_archetypes_are_available_with_no_config(self):
        self.assertEqual(len(A.catalogue(None)), 5)

    def test_configured_thresholds_build_the_magnitude_archetypes(self):
        names = [a.name for a in A.catalogue(CONFIGURED)]
        self.assertIn("headline_exposure", names)

    def test_every_magnitude_archetype_names_its_threshold_source(self):
        for archetype in A.catalogue(CONFIGURED):
            if archetype.kind != A.MAGNITUDE:
                continue
            with self.subTest(archetype=archetype.name):
                self.assertIn("test-v1", archetype.threshold_source)

    def test_the_threshold_number_appears_in_the_condition_prose(self):
        headline = [a for a in A.catalogue(CONFIGURED)
                    if a.name == "headline_exposure"][0]
        described = " ".join(c.describe for c in headline.conditions)
        self.assertIn("90 days", described)
        self.assertIn("14 days", described)
        self.assertIn("test-v1", described)


class TestBoundsAnswerDefinitelyInOneDirection(unittest.TestCase):
    """Where carrying the bound direction since stage 4 gets paid out."""

    def headline(self):
        return [a for a in A.catalogue(CONFIGURED)
                if a.name == "headline_exposure"][0]

    def test_an_upper_bound_below_the_threshold_is_definitely_true(self):
        # Cover is at most 11 days, so it is certainly at most 14.
        prof = profile(on_hand=1734, usage_value=57000,
                       usage_completeness=USAGE_PARTIAL, tooling="supplier",
                       lead_times=((182, 266),))
        self.assertEqual(prof.buffer_cover.completeness, scoring.UPPER_BOUND)
        self.assertEqual(state(self.headline(), prof), A.MATCHED)

    def test_an_upper_bound_above_the_threshold_is_unknown_not_false(self):
        # Cover is at most 365 days, which could be anything below that,
        # including under the threshold. Neither answer is available.
        prof = profile(on_hand=1000, usage_value=1000,
                       usage_completeness=USAGE_PARTIAL, tooling="supplier",
                       lead_times=((182, 266),))
        self.assertEqual(prof.buffer_cover.completeness, scoring.UPPER_BOUND)
        self.assertEqual(state(self.headline(), prof), A.CANNOT_TELL)

    def test_no_recovery_path_is_a_long_lead_time_definitely(self):
        prof = profile(verdict="no_qualified_supplier", lead_times=(),
                       tooling="supplier", on_hand=0)
        self.assertEqual(prof.lead_time_to_recover.completeness,
                         scoring.NO_RECOVERY_PATH)
        long_lead = [c for c in self.headline().conditions
                     if c.name == "long_lead"][0]
        self.assertEqual(
            long_lead.evaluate({"profile": prof,
                                "verdict": "no_qualified_supplier"}), A.TRUE)

    def test_made_in_house_is_definitely_not_a_long_purchase_lead(self):
        prof = profile(verdict="made_in_house", lead_times=())
        long_lead = [c for c in self.headline().conditions
                     if c.name == "long_lead"][0]
        self.assertEqual(
            long_lead.evaluate({"profile": prof, "verdict": "made_in_house"}),
            A.FALSE)


class TestAutonomy(unittest.TestCase):

    def test_the_catalogue_carries_the_ceiling(self):
        # Which conjunctions are worth naming is a modelling judgment, and it
        # carries the same permanent recommends as grouping.
        self.assertEqual(A.CATALOGUE_AUTONOMY, gov.RECOMMENDS)

    def test_structural_membership_executes(self):
        # A conjunction of facts each computed at executes is a fact.
        self.assertEqual(A.RESOURCING_TRAP.autonomy, gov.EXECUTES)
        self.assertEqual(A.NOBODY_TO_CALL.autonomy, gov.EXECUTES)

    def test_magnitude_membership_recommends(self):
        for archetype in A.catalogue(CONFIGURED):
            if archetype.kind == A.MAGNITUDE:
                with self.subTest(archetype=archetype.name):
                    self.assertEqual(archetype.autonomy, gov.RECOMMENDS)

    def test_a_conjunction_touching_concentration_inherits_stage_five(self):
        # A conjunct that may not be claimed alone may not be claimed inside a
        # conjunction either.
        self.assertEqual(A.CORRELATED_RESOURCING_TRAP.autonomy, gov.RECOMMENDS)

    def test_the_ceiling_is_placed_where_the_judgment_is(self):
        # One catalogue reused across every part, so confirming per part would
        # be three hundred confirmations of a single decision.
        self.assertEqual(A.CATALOGUE_AUTONOMY, gov.RECOMMENDS)
        self.assertEqual(A.RESOURCING_TRAP.autonomy, gov.EXECUTES)


class TestDominance(unittest.TestCase):

    def test_dominance_is_strict_subset_inclusion(self):
        self.assertTrue(A.dominates(A.CORRELATED_RESOURCING_TRAP,
                                    A.RESOURCING_TRAP))
        self.assertFalse(A.dominates(A.RESOURCING_TRAP,
                                     A.CORRELATED_RESOURCING_TRAP))

    def test_an_archetype_does_not_dominate_itself(self):
        self.assertFalse(A.dominates(A.RESOURCING_TRAP, A.RESOURCING_TRAP))

    def test_incomparable_archetypes_are_incomparable_in_both_directions(self):
        self.assertFalse(A.dominates(A.NOBODY_TO_CALL, A.RESOURCING_TRAP))
        self.assertFalse(A.dominates(A.RESOURCING_TRAP, A.NOBODY_TO_CALL))

    def test_layers_place_incomparable_archetypes_together(self):
        layers = A.dominance_layers(A.catalogue(None))
        placement = {a.name: index for index, layer in enumerate(layers)
                     for a in layer}
        self.assertLess(placement["correlated_resourcing_trap"],
                        placement["resourcing_trap"])

    def test_layers_are_ordered_by_name_within_a_layer(self):
        for layer in A.dominance_layers(A.catalogue(CONFIGURED)):
            with self.subTest(layer=[a.name for a in layer]):
                self.assertEqual([a.name for a in layer],
                                 sorted(a.name for a in layer))

    def test_no_ordering_other_than_subset_inclusion_exists(self):
        # A total order over archetypes could only be produced by scoring them.
        # CODE ONLY: the docstring explains that no weights are needed.
        source = code_of(A.dominates)
        for forbidden in ("weight", "score", "severity", "priority"):
            with self.subTest(word=forbidden):
                self.assertNotIn(forbidden, source)


class TestNoComposite(unittest.TestCase):

    def test_no_archetype_exposes_a_score(self):
        for forbidden in ("score", "weight", "severity", "priority", "rank",
                          "total"):
            with self.subTest(attribute=forbidden):
                self.assertNotIn(forbidden, A.Archetype.__dataclass_fields__)

    def test_conditions_are_named_not_weighted(self):
        for forbidden in ("weight", "score", "points"):
            with self.subTest(attribute=forbidden):
                self.assertNotIn(forbidden, A.Condition.__dataclass_fields__)

    def test_no_module_function_weights_or_sums_conditions(self):
        joined = code_of(A)
        for forbidden in ("weight", "composite", "severity_score"):
            with self.subTest(word=forbidden):
                self.assertNotIn(forbidden, joined)


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
