"""Exposure scoring: four dimensions, no composite, autonomy per dimension.

Expectations are hand-written in tests/fixtures/tiny_expected_scores.py, derived
from the tree and the demand plan by hand. Nothing here imports a value the code
under test produced.
"""
import inspect
import textwrap
import unittest

import pytest
from fractions import Fraction
from pathlib import Path

from codescan import code_of
from fixtures.tiny_expected_scores import (EXPECTED_BLAST_RADIUS_COMPLETENESS,
                                           EXPECTED_RESOURCE_COMPLETENESS,
                                           EXPECTED_RESOURCE_DAYS,
                                           EXPECTED_RESOURCE_DAYS_BY_CLASS,
                                           EXPECTED_RESOURCE_WITH_RETRY,
                                           EXPECTED_BLOCKED_UNITS,
                                           EXPECTED_COVER_COMPLETENESS,
                                           EXPECTED_COVER_DAYS,
                                           EXPECTED_FINISHED_GOODS_BLOCKED,
                                           EXPECTED_PORTABILITY, SCORED_PARTS)
from src import governance as gov
from src import scoring
from src.demand import (Usage, usage_by_part, USAGE_CANNOT_TELL, USAGE_KNOWN,
                        USAGE_PARTIAL)
from src import recovery as R
from src.explosion import explode, rows_by_part
from src.readers import (read_bom, read_demand_plan, read_part_master,
                         read_recovery_inputs)
from src.scoring import (CANNOT_TELL, DAYS, KNOWN, LOWER_BOUND, NOT_APPLICABLE,
                         NO_RECOVERY_PATH, UPPER_BOUND, DimensionScore,
                         ExposureProfile, abstention_lane, blast_radius,
                         buffer_cover, portability, resource_days, score_part,
                         wait_out_days)

FIXTURES = Path(__file__).parent / "fixtures"

# Every stage timed and a cycle count on file, written by hand. Used where a
# test needs a SETTLED chain and nothing else about the chain matters.
TIMED = {"alternate_source_days": 10, "tooling_lead_time_days": 20,
         "engineering_transfer_days": 30, "first_article_days": 40,
         "qualification_test_days": 50, "ramp_to_rate_days": 60,
         "qualification_cycles": 1}


def fixture_profiles():
    edges = read_bom(FIXTURES / "tiny_scoring_bom.csv")
    rows = rows_by_part(explode(edges))
    demand = read_demand_plan(FIXTURES / "tiny_demand.csv")
    parts = read_part_master(FIXTURES / "tiny_part_master.csv")
    usage = usage_by_part(rows, demand)
    stages = read_recovery_inputs(FIXTURES / "tiny_recovery.csv")
    profiles = {}
    for part in SCORED_PARTS:
        record = parts[part]
        profiles[part] = score_part(
            part_number=part, verdict="single_source", rows=rows[part],
            usage=usage[part], on_hand_units=record["on_hand_units"],
            tooling_owner=record["tooling_owner"],
            lead_times=[(30, 45)], recovery_stages=stages.get(part))
    return profiles


class TestBufferCover(unittest.TestCase):

    def setUp(self):
        self.profiles = fixture_profiles()

    def test_cover_days_match_the_hand_computed_values(self):
        for part in SCORED_PARTS:
            with self.subTest(part=part):
                expected = EXPECTED_COVER_DAYS[part]
                actual = self.profiles[part].buffer_cover.value
                if expected == "unbounded":
                    self.assertIs(actual, scoring.UNBOUNDED)
                else:
                    self.assertEqual(actual, expected)

    def test_cover_completeness_matches(self):
        for part in SCORED_PARTS:
            with self.subTest(part=part):
                self.assertEqual(self.profiles[part].buffer_cover.completeness,
                                 EXPECTED_COVER_COMPLETENESS[part])

    def test_cover_is_exact_not_floating_point(self):
        # 100 x 365 / 1000 is 36.5 exactly. A float would need a tolerance and
        # the fixture would stop being an oracle.
        cover = self.profiles["ONLY-M01"].buffer_cover
        self.assertIsInstance(cover.value, Fraction)
        self.assertEqual(cover.value, Fraction(73, 2))

    def test_partial_demand_makes_cover_an_upper_bound(self):
        cover = self.profiles["SHARED-M01"].buffer_cover
        self.assertEqual(cover.completeness, UPPER_BOUND)
        self.assertEqual(cover.value, 73)

    def test_a_bound_is_an_answer_and_executes(self):
        self.assertEqual(self.profiles["SHARED-M01"].buffer_cover.autonomy,
                         gov.EXECUTES)

    def test_zero_consumption_gives_unbounded_cover_not_an_error(self):
        cover = self.profiles["ZEROUSE-M01"].buffer_cover
        self.assertEqual(cover.completeness, KNOWN)
        self.assertTrue(cover.detail["unbounded"])
        self.assertEqual(cover.autonomy, gov.EXECUTES)
        self.assertIs(cover.value, scoring.UNBOUNDED)

    def test_unbounded_is_a_value_and_is_not_none(self):
        # None means "no value" everywhere else in this module, and unbounded
        # is an answer. Conflating them would put an answered dimension in the
        # abstention lane.
        cover = self.profiles["ZEROUSE-M01"].buffer_cover
        self.assertIsNotNone(cover.value)
        self.assertEqual(str(cover.value), "unbounded")

    def test_unbounded_supports_no_arithmetic(self):
        # math.inf would have been the obvious choice and would have been the
        # one summable measure in the module.
        with self.assertRaises(TypeError):
            scoring.UNBOUNDED + 1


class TestMissingOnHandVersusRecordedZero(unittest.TestCase):
    """The pair that a single `or 0` anywhere upstream would fuse forever."""

    def setUp(self):
        self.profiles = fixture_profiles()
        self.zero = self.profiles["ONLY-M02"].buffer_cover
        self.missing = self.profiles["MISSING-M01"].buffer_cover

    def test_recorded_zero_is_an_answer_of_zero_days(self):
        self.assertEqual(self.zero.value, 0)
        self.assertEqual(self.zero.completeness, KNOWN)
        self.assertEqual(self.zero.autonomy, gov.EXECUTES)

    def test_missing_on_hand_is_not_an_answer(self):
        self.assertIsNone(self.missing.value)
        self.assertEqual(self.missing.completeness, CANNOT_TELL)
        self.assertEqual(self.missing.autonomy, gov.RECOMMENDS)

    def test_the_two_are_unequal_at_every_level(self):
        self.assertNotEqual(self.zero, self.missing)
        self.assertNotEqual(self.zero.value, self.missing.value)
        self.assertNotEqual(self.zero.completeness, self.missing.completeness)
        self.assertNotEqual(self.zero.autonomy, self.missing.autonomy)
        self.assertNotEqual(self.zero.reasons, self.missing.reasons)

    def test_the_reader_never_coerces_a_blank_to_zero(self):
        parts = read_part_master(FIXTURES / "tiny_part_master.csv")
        self.assertIsNone(parts["MISSING-M01"]["on_hand_units"])
        self.assertEqual(parts["ONLY-M02"]["on_hand_units"], 0)
        self.assertIsNot(parts["MISSING-M01"]["on_hand_units"],
                         parts["ONLY-M02"]["on_hand_units"])

    def test_missing_cover_never_renders_as_a_number(self):
        self.assertIn("not the same as having no stock", self.missing.reasons[0])


class TestBlastRadius(unittest.TestCase):

    def setUp(self):
        self.profiles = fixture_profiles()

    def test_blocked_units_match_the_hand_computed_values(self):
        for part in SCORED_PARTS:
            with self.subTest(part=part):
                self.assertEqual(self.profiles[part].blast_radius.value,
                                 EXPECTED_BLOCKED_UNITS[part])

    def test_structural_reach_is_always_known(self):
        for part in SCORED_PARTS:
            with self.subTest(part=part):
                detail = self.profiles[part].blast_radius.detail
                self.assertEqual(detail["finished_goods_blocked"],
                                 EXPECTED_FINISHED_GOODS_BLOCKED[part])

    def test_completeness_matches(self):
        for part in SCORED_PARTS:
            with self.subTest(part=part):
                self.assertEqual(self.profiles[part].blast_radius.completeness,
                                 EXPECTED_BLAST_RADIUS_COMPLETENESS[part])

    def test_the_detail_names_which_usage_branch_produced_the_completeness(self):
        """LOWER_BOUND is assigned by two branches and they mean different things.

        Partial usage means some finished goods are recorded, so the figure is a
        real lower bound. Cannot-tell means none are, so the volume is absent
        rather than small. A consumer cannot separate them from `completeness`
        and `value` alone, and inferring it from `value == 0` is wrong: partial
        usage whose recorded goods total zero is a RECORDED zero. Collapsing
        those is the missing-versus-zero conflation this module separates before
        any arithmetic.
        """
        for part in SCORED_PARTS:
            with self.subTest(part=part):
                score = self.profiles[part].blast_radius
                self.assertIn("usage_completeness", score.detail)
                self.assertIn(score.detail["usage_completeness"],
                              (USAGE_KNOWN, USAGE_PARTIAL, USAGE_CANNOT_TELL))

    def test_the_branch_is_named_rather_than_reduced_to_a_flag(self):
        """A boolean would let a third usage state inherit a reading by default.

        `units_countable: False` cannot distinguish "none recorded" from a state
        nobody has written yet. A name arrives unrecognised, which forces the
        consumer to handle it instead of silently reading it as one of these two.
        """
        for part in SCORED_PARTS:
            detail = self.profiles[part].blast_radius.detail
            with self.subTest(part=part):
                self.assertIsInstance(detail["usage_completeness"], str)
                self.assertNotIsInstance(detail["usage_completeness"], bool)

    def test_the_detail_contract_is_pinned_so_a_removal_is_loud(self):
        """`log_profile` splats detail into event evidence (scoring.py:491).

        That makes the key set a cross-module contract, and nothing else pins it:
        no golden and no frozen eval contains these keys, so dropping one would
        be silent at every layer. This is the pin.
        """
        expected = {"finished_goods_blocked", "finished_goods",
                    "assemblies_blocked", "usage_completeness",
                    "min_depth", "max_depth", "spans_depths"}
        for part in SCORED_PARTS:
            with self.subTest(part=part):
                self.assertEqual(
                    set(self.profiles[part].blast_radius.detail), expected)

    def test_blast_radius_never_abstains(self):
        for part in SCORED_PARTS:
            with self.subTest(part=part):
                self.assertEqual(self.profiles[part].blast_radius.autonomy,
                                 gov.EXECUTES)

    def test_a_part_fed_only_by_absent_demand_still_reports_its_reach(self):
        # Saying "this stops one finished good, volume unrecorded" is more
        # useful than saying nothing.
        score = self.profiles["ORPHAN-M01"].blast_radius
        self.assertEqual(score.detail["finished_goods_blocked"], 1)
        self.assertEqual(score.completeness, LOWER_BOUND)


class TestTheBoundDirectionsInvert(unittest.TestCase):
    """One part, one missing demand row, two opposite bounds.

    This is the assertion that catches the direction being got backwards, and
    it has to be one test on one part or the inversion is invisible.
    """

    def test_the_same_missing_row_bounds_cover_up_and_blast_radius_down(self):
        profile = fixture_profiles()["SHARED-M01"]
        self.assertEqual(profile.buffer_cover.completeness, UPPER_BOUND)
        self.assertEqual(profile.blast_radius.completeness, LOWER_BOUND)

    def test_each_bound_says_which_way_it_is_wrong(self):
        profile = fixture_profiles()["SHARED-M01"]
        # THE DIRECTION IN WORDS, and the plain-language pass had to keep it:
        # cover can only be LOWER than stated and blocked units can only be
        # HIGHER, from the identical missing row. A shared hedge like "roughly"
        # would read more naturally and would destroy the distinction.
        self.assertIn("can only be lower", profile.buffer_cover.reasons[0])
        self.assertIn("can only be higher", profile.blast_radius.reasons[0])


class TestPortability(unittest.TestCase):

    def test_portability_matches_the_hand_written_expectations(self):
        profiles = fixture_profiles()
        for part in SCORED_PARTS:
            with self.subTest(part=part):
                self.assertEqual(profiles[part].portability.value,
                                 EXPECTED_PORTABILITY[part])

    def test_blank_tooling_owner_abstains(self):
        score = fixture_profiles()["MISSING-M01"].portability
        self.assertEqual(score.completeness, CANNOT_TELL)
        self.assertEqual(score.autonomy, gov.RECOMMENDS)


class TestWaitOutDays(unittest.TestCase):
    """Hard-coded expectations; the verdict strings are literals."""

    def test_both_lead_time_columns_are_returned_not_one(self):
        score = wait_out_days("P", "single_source", [(30, 45)])
        self.assertEqual(score.value, (30, 45))
        self.assertEqual(score.detail["quoted_days"], 30)
        self.assertEqual(score.detail["p95_days"], 45)

    def test_the_fastest_supplier_sets_the_recovery_time(self):
        score = wait_out_days("P", "multi_source", [(60, 90), (30, 45)])
        self.assertEqual(score.value, (30, 45))

    def test_no_lead_time_record_abstains(self):
        score = wait_out_days("P", "single_source_no_lead_time", [])
        self.assertEqual(score.completeness, CANNOT_TELL)
        self.assertEqual(score.autonomy, gov.RECOMMENDS)

    def test_no_qualified_supplier_is_not_an_abstention(self):
        # Undefined by absence, not missing from the spreadsheet. Rendering it
        # as "cannot tell" would understate the most serious finding here.
        score = wait_out_days("P", "no_qualified_supplier", [])
        self.assertEqual(score.completeness, NO_RECOVERY_PATH)
        self.assertEqual(score.autonomy, gov.EXECUTES)

    def test_made_in_house_does_not_apply_rather_than_being_unknown(self):
        # A lane that keeps showing in-house parts asks a reviewer to fetch
        # data that does not exist anywhere and never will.
        score = wait_out_days("P", "made_in_house", [])
        self.assertEqual(score.completeness, NOT_APPLICABLE)
        self.assertEqual(score.autonomy, gov.EXECUTES)

    def test_the_three_no_value_states_stay_distinct(self):
        states = {
            wait_out_days("P", "single_source_no_lead_time", []
                                 ).completeness,
            wait_out_days("P", "no_qualified_supplier", []).completeness,
            wait_out_days("P", "made_in_house", []).completeness,
        }
        self.assertEqual(len(states), 3,
                         "all three have no value, and collapsing any two "
                         "would tell a reviewer the wrong thing to do next")

    def test_an_unconfirmed_supplier_list_abstains_even_with_a_lead_time(self):
        score = wait_out_days("P", "supplier_list_unknown", [(30, 45)])
        self.assertEqual(score.completeness, CANNOT_TELL)

    def test_nothing_here_bands_a_duration(self):
        # "Long lead" is a threshold and a threshold is a judgment. Stage 4
        # returns raw durations so its autonomy claim does not rest on one.
        # CODE ONLY: the docstring explains why there is no banding, so a raw
        # source scan would flag the explanation rather than a violation.
        code = code_of(wait_out_days)
        for banding_word in ("long_lead", "is_long", "band", "tier",
                             "severity", "critical"):
            with self.subTest(word=banding_word):
                self.assertNotIn(banding_word, code)



class TestResourceDays(unittest.TestCase):
    """The resourcing chain. Expectations hand-summed in tiny_recovery.csv."""

    def setUp(self):
        self.profiles = fixture_profiles()

    def test_chain_totals_match_the_hand_summed_values(self):
        for part in SCORED_PARTS:
            with self.subTest(part=part):
                self.assertEqual(self.profiles[part].resource_days.value,
                                 EXPECTED_RESOURCE_DAYS[part])

    def test_chain_completeness_matches(self):
        for part in SCORED_PARTS:
            with self.subTest(part=part):
                self.assertEqual(
                    self.profiles[part].resource_days.completeness,
                    EXPECTED_RESOURCE_COMPLETENESS[part])

    # ------------------------------------------- the four required chains --
    def test_a_chain_with_every_stage_present_is_known(self):
        score = self.profiles["SHARED-M01"].resource_days
        self.assertEqual(score.completeness, KNOWN)
        self.assertEqual(score.value, 300)
        self.assertEqual(score.detail["stages_untimed"], ())
        self.assertEqual(score.autonomy, gov.EXECUTES)

    def test_a_chain_with_tooling_missing_is_a_lower_bound_naming_tooling(self):
        # Supplier-owned tooling, so retooling IS on the path, and nobody has
        # said how long it takes. The total under-counts by exactly that.
        score = self.profiles["ZEROUSE-M01"].resource_days
        self.assertEqual(score.completeness, LOWER_BOUND)
        self.assertEqual(score.value, 115)
        self.assertEqual(score.detail["stages_untimed"],
                         (R.TOOLING,))
        self.assertIn("tooling", score.reasons[0])
        self.assertIn("could take longer", score.reasons[0])

    def test_a_chain_with_qualification_missing_is_a_lower_bound(self):
        score = self.profiles["ONLY-M01"].resource_days
        self.assertEqual(score.completeness, LOWER_BOUND)
        self.assertEqual(score.value, 80)
        self.assertIn(R.QUALIFICATION_TEST, score.detail["stages_untimed"])
        self.assertIn("qualification and reliability testing", score.reasons[0])

    def test_a_present_retry_cycle_reports_both_readings(self):
        score = self.profiles["SHARED-M01"].resource_days
        self.assertEqual(score.detail["qualification_cycles"], 2)
        self.assertEqual(score.detail["with_retry_days"], 360)
        sentence = " ".join(score.reasons)
        self.assertIn("300 days if it is approved first time", sentence)
        self.assertIn("360 days over the 2 attempts", sentence)

    def test_an_absent_retry_cycle_is_said_rather_than_assumed(self):
        """The row that exists to prove one pass is never the default.

        ONLY-M02 has every stage on its path timed. The only thing missing is
        how many qualification cycles to plan for, and that alone keeps the
        total a bound: counting one pass is an assumption, and an assumption
        nobody made must not be made here.
        """
        score = self.profiles["ONLY-M02"].resource_days
        self.assertEqual(score.detail["stages_untimed"], ())
        self.assertIsNone(score.detail["qualification_cycles"])
        self.assertIsNone(score.detail["with_retry_days"])
        self.assertEqual(score.completeness, LOWER_BOUND)
        self.assertIn("nobody has said how many approval attempts",
                      " ".join(score.reasons))

    def test_with_retry_totals_match_the_hand_computed_values(self):
        for part in SCORED_PARTS:
            with self.subTest(part=part):
                self.assertEqual(
                    self.profiles[part].resource_days.detail["with_retry_days"],
                    EXPECTED_RESOURCE_WITH_RETRY[part])

    # ------------------------------------------------ nothing timed at all --
    def test_nothing_timed_abstains_rather_than_bounding_at_zero(self):
        """Zero is the trivial lower bound of any duration.

        Reporting "at least 0 days to resource" would be a true statement
        carrying no information, dressed as a measurement. It is the same defect
        `render._blocked_volume_absent` exists to repair for blast radius.
        """
        score = self.profiles["ORPHAN-M01"].resource_days
        self.assertEqual(score.completeness, CANNOT_TELL)
        self.assertIsNone(score.value)
        self.assertNotEqual(score.value, 0)
        self.assertEqual(score.autonomy, gov.RECOMMENDS)

    def test_a_missing_stage_is_never_read_as_zero_days(self):
        """The same asymmetry as a blank on-hand count, in days.

        Both chains below total 200 days. One got there because somebody timed
        finding an alternate source at zero, which is a measurement; the other
        because nobody timed it at all, which is a gap. The totals are identical
        and the states are not, which is the whole distinction: one `or 0`
        anywhere in the chain would fuse them and the bound would vanish.
        """
        timed_zero = resource_days("P", "supplier",
                                   dict(TIMED, alternate_source_days=0))
        untimed = resource_days(
            "P", "supplier",
            {k: v for k, v in TIMED.items() if k != R.ALTERNATE_SOURCE})

        self.assertEqual(timed_zero.value, untimed.value)
        self.assertEqual(timed_zero.value, 200)
        self.assertIn(R.ALTERNATE_SOURCE, timed_zero.detail["stages_timed"])
        self.assertEqual(timed_zero.detail["days_by_stage"][R.ALTERNATE_SOURCE],
                         0)
        self.assertEqual(timed_zero.completeness, KNOWN)

        self.assertIn(R.ALTERNATE_SOURCE, untimed.detail["stages_untimed"])
        self.assertEqual(untimed.completeness, LOWER_BOUND)

    # -------------------------------------------------------- applicability --
    def test_company_tooling_takes_the_stage_off_the_path(self):
        # Not the same as untimed: company tooling moves to the new source, so
        # the stage does not happen and contributes nothing WITHOUT bounding.
        score = self.profiles["ONLY-M02"].resource_days
        self.assertEqual(score.detail["stages_not_applicable"], (R.TOOLING,))
        self.assertNotIn(R.TOOLING, score.detail["stages_untimed"])
        self.assertEqual(score.completeness, LOWER_BOUND)   # the cycle count

    def test_an_unrecorded_tooling_owner_bounds_rather_than_skipping(self):
        score = self.profiles["MISSING-M01"].resource_days
        self.assertIn(R.TOOLING, score.detail["stages_untimed"])
        self.assertEqual(score.detail["stages_not_applicable"], ())

    # ---------------------------------------------------- confidence classes --
    def test_each_confidence_class_keeps_its_own_subtotal(self):
        for part in SCORED_PARTS:
            with self.subTest(part=part):
                self.assertEqual(
                    self.profiles[part].resource_days.detail["days_by_class"],
                    EXPECTED_RESOURCE_DAYS_BY_CLASS[part])

    def test_the_classes_are_not_averaged_into_one_figure(self):
        """The subtotals partition the total. Nothing blends them.

        Summing sequential stages is an elapsed duration and is legitimate.
        What is refused is any statistic ACROSS the classes: a mean of 180
        judgment days and 120 knowable days is 150 days of nothing.
        """
        score = self.profiles["SHARED-M01"].resource_days
        by_class = score.detail["days_by_class"]
        self.assertEqual(sum(by_class.values()), score.value)
        self.assertEqual(len(by_class), 2)
        code = code_of(resource_days) + code_of(R.Chain)
        for blended in ("mean", "average", "/ len(", "statistics"):
            with self.subTest(word=blended):
                self.assertNotIn(blended, code)

    def test_the_total_names_the_weakest_class_it_rests_on(self):
        # One judgment in the chain makes the total a judgment, however many
        # quoted days sit beside it.
        score = self.profiles["SHARED-M01"].resource_days
        self.assertEqual(score.detail["weakest_class"], R.JUDGMENT)
        self.assertIn(R.KNOWABLE, score.detail["days_by_class"])

    def test_a_purchase_lead_time_never_enters_the_chain(self):
        """The reported class stays in the other measure, always.

        `wait_out_days` is the only duration in this system that somebody
        reported, and the chain must not absorb it: a total mixing a quoted lead
        time with an estimate is the composite this project refuses, expressed
        in days.
        """
        for part in SCORED_PARTS:
            classes = self.profiles[part].resource_days.detail["days_by_class"]
            with self.subTest(part=part):
                self.assertNotIn(R.REPORTED, classes)
        self.assertNotIn("lead_time", code_of(resource_days))

    def test_a_cycle_count_below_one_is_refused_rather_than_clamped(self):
        # Zero cycles would make the retry total SHORTER than the first-pass
        # total, which is a wrong answer rather than a missing one. Clamping it
        # would put a number nobody supplied into the one measure whose claim is
        # that it never does that.
        with self.assertRaises(ValueError):
            resource_days("P", "supplier", dict(TIMED, qualification_cycles=0))
        with self.assertRaises(ValueError):
            resource_days("P", "supplier", dict(TIMED, qualification_cycles=-2))

    def test_one_planned_cycle_reads_as_one_cycle(self):
        score = resource_days("P", "supplier", TIMED)
        self.assertIn("a single attempt planned for", " ".join(score.reasons))

    # ------------------------------------------------------- no banding here --
    def test_nothing_here_bands_a_duration(self):
        code = code_of(resource_days)
        for banding_word in ("long_lead", "is_long", "band", "tier",
                             "severity", "critical"):
            with self.subTest(word=banding_word):
                self.assertNotIn(banding_word, code)


class TestTheTwoHalvesOfRecoveryStaySeparate(unittest.TestCase):
    """The practitioner's point, expressed as tests.

    "Tooling and qualification vary significantly by part, and it doesn't always
    go smoothly." Two parts identical in purchase lead time can be a fortnight
    or forty weeks apart in what it takes to replace the source, and the old
    single dimension could not say so.
    """

    def test_two_parts_with_the_same_lead_time_can_differ_on_resourcing(self):
        slow = resource_days("SLOW", "supplier",
                             {"qualification_test_days": 280,
                              "qualification_cycles": 1})
        fast = resource_days("FAST", "supplier",
                             {"qualification_test_days": 14,
                              "qualification_cycles": 1})
        wait = wait_out_days("SLOW", "single_source", [(30, 45)])
        self.assertEqual(wait.value,
                         wait_out_days("FAST", "single_source",
                                       [(30, 45)]).value)
        self.assertNotEqual(slow.value, fast.value)

    def test_the_two_measures_are_never_added(self):
        profile = fixture_profiles()["SHARED-M01"]
        with self.assertRaises(TypeError):
            profile.wait_out_days + profile.resource_days

    def test_they_carry_separate_completeness_and_separate_autonomy(self):
        """One part, one settled measure, one abstention, at the same moment.

        This is what a single `lead_time_to_recover` slot could not express, and
        it is why the split is two dimensions rather than two numbers in one.
        """
        profile = fixture_profiles()["ORPHAN-M01"]
        self.assertEqual(profile.wait_out_days.completeness, KNOWN)
        self.assertEqual(profile.wait_out_days.autonomy, gov.EXECUTES)
        self.assertEqual(profile.resource_days.completeness, CANNOT_TELL)
        self.assertEqual(profile.resource_days.autonomy, gov.RECOMMENDS)

    def test_an_empty_supplier_list_still_reports_a_resourcing_time(self):
        """Nobody to buy from is the case where resourcing is the ONLY path.

        `wait_out_days` reports no recovery path, which is true of waiting.
        Reporting the same of the chain would say the part cannot be recovered
        at all, which is the opposite of what an empty supplier list means.
        """
        wait = wait_out_days("P", "no_qualified_supplier", [])
        chain = resource_days("P", "supplier", TIMED)
        self.assertEqual(wait.completeness, NO_RECOVERY_PATH)
        self.assertEqual(chain.completeness, KNOWN)
        self.assertEqual(chain.value, 210)      # 10+20+30+40+50+60, hand-summed

    def test_an_in_house_part_still_reports_a_resourcing_time(self):
        # You cannot place a purchase order on your own factory, but you can
        # qualify an outside source for the part it makes.
        wait = wait_out_days("P", "made_in_house", [])
        chain = resource_days("P", "supplier", TIMED)
        self.assertEqual(wait.completeness, NOT_APPLICABLE)
        self.assertEqual(chain.completeness, KNOWN)

    def test_the_verdict_is_not_an_input_to_the_chain(self):
        # Structural rather than asserted by example: resourcing does not depend
        # on what the supplier list says, so the verdict cannot reach it.
        self.assertNotIn("verdict",
                         inspect.signature(resource_days).parameters)
        self.assertIn("verdict", inspect.signature(wait_out_days).parameters)



class TestAutonomyIsPerDimensionPerPart(unittest.TestCase):

    def test_one_part_can_execute_and_abstain_at_the_same_time(self):
        profile = fixture_profiles()["MISSING-M01"]
        self.assertEqual(profile.blast_radius.autonomy, gov.EXECUTES)
        self.assertEqual(profile.buffer_cover.autonomy, gov.RECOMMENDS)
        self.assertEqual(profile.portability.autonomy, gov.RECOMMENDS)

    def test_only_a_missing_input_abstains(self):
        settled = (KNOWN, UPPER_BOUND, LOWER_BOUND, NO_RECOVERY_PATH,
                   NOT_APPLICABLE)
        for state in settled:
            with self.subTest(state=state):
                self.assertEqual(scoring.autonomy_for(state), gov.EXECUTES)
        self.assertEqual(scoring.autonomy_for(CANNOT_TELL), gov.RECOMMENDS)

    def test_autonomy_is_derived_not_stored(self):
        # One rule with one home. A stored autonomy field could drift away from
        # the completeness it is supposed to follow.
        self.assertNotIn("autonomy",
                         DimensionScore.__dataclass_fields__)

    def test_an_unknown_completeness_state_raises(self):
        with self.assertRaises(ValueError):
            scoring.autonomy_for("probably_fine")

    def test_the_abstention_lane_groups_by_dimension(self):
        lane = abstention_lane(fixture_profiles().values())
        self.assertIn("buffer_cover", lane)
        self.assertIn("portability", lane)
        self.assertNotIn("blast_radius", lane)
        covered = [score.part_number for score in lane["buffer_cover"]]
        self.assertEqual(covered, ["MISSING-M01", "ORPHAN-M01"])

    def _in_house_profile(self, stages):
        return ExposureProfile(
            part_number="P",
            wait_out_days=wait_out_days("P", "made_in_house", []),
            resource_days=resource_days("P", "company", stages),
            blast_radius=blast_radius("P", (), Usage("P", Fraction(0),
                                                     USAGE_KNOWN)),
            buffer_cover=buffer_cover("P", 0, Usage("P", Fraction(0),
                                                    USAGE_KNOWN)),
            portability=portability("P", "company"))

    def test_in_house_parts_never_reach_the_lane_for_a_purchase_lead_time(self):
        # The dimension that does not apply cannot be resolved by fetching
        # anything, so it must never queue. Every other dimension here is
        # settled, so the lane is empty.
        self.assertEqual(abstention_lane([self._in_house_profile(TIMED)]), {})

    def test_an_in_house_part_still_queues_an_untimed_resourcing_chain(self):
        """The asymmetry the split creates, and it is the right way round.

        Nobody can fetch a purchase lead time for a part the company makes, so
        `wait_out_days` is not applicable and never queues. Somebody CAN supply
        how long it would take to stand an outside source up for that same part,
        so an untimed chain is a fetchable gap and belongs in the lane. One part,
        two recovery measures, opposite routing.
        """
        lane = abstention_lane([self._in_house_profile(None)])
        self.assertEqual(list(lane), ["resource_days"])


class TestNoComposite(unittest.TestCase):
    """Two guarantees that have to hold together.

    Blocking the `+` is the easy half. What ENABLES the `+` is normalisation,
    and a rescaled unitless number is a composite already assembled.
    """

    def test_the_container_exposes_no_total(self):
        for forbidden in ("total", "overall", "score", "weighted", "rank",
                          "composite", "__add__", "sum"):
            with self.subTest(attribute=forbidden):
                self.assertFalse(
                    hasattr(ExposureProfile, forbidden),
                    f"ExposureProfile.{forbidden} would be a composite")

    def test_a_dimension_score_cannot_be_added_to_another(self):
        profiles = fixture_profiles()
        left = profiles["ONLY-M01"].buffer_cover
        right = profiles["ONLY-M01"].blast_radius
        with self.assertRaises(TypeError):
            left + right

    def test_no_module_function_combines_dimensions_in_code(self):
        # functions_only: FORBIDDEN_UNIT_WORDS declares these words as data
        # so a unit named any of them can be refused at construction.
        code = code_of(scoring, functions_only=True)
        for forbidden in ("weight", "composite", "overall_score",
                          "normalise", "normalize"):
            with self.subTest(word=forbidden):
                self.assertNotIn(forbidden, code)

    # --------------------------------------------------------------- units --
    def test_every_measure_keeps_a_unit(self):
        for profile in fixture_profiles().values():
            for score in profile.scored():
                with self.subTest(part=profile.part_number,
                                  dimension=score.dimension):
                    self.assertTrue(score.unit)
                    self.assertIn(score.unit, scoring.UNITS)

    def test_no_unit_is_a_unitless_range(self):
        # A unit named "score", "index" or "risk" is a number that has been
        # stripped of what it counts and rescaled, which is a composite in
        # preparation whether or not anyone writes the `+`.
        for unit in scoring.UNITS:
            with self.subTest(unit=unit):
                for forbidden in scoring.FORBIDDEN_UNIT_WORDS:
                    self.assertNotIn(forbidden, unit)

    def test_a_score_with_a_unitless_unit_is_refused_at_construction(self):
        for bad_unit in ("score", "risk_index", "normalised", "percent"):
            with self.subTest(unit=bad_unit):
                with self.assertRaises(ValueError):
                    DimensionScore(part_number="P", dimension="buffer_cover",
                                   value=1, unit=bad_unit, completeness=KNOWN,
                                   reasons=("because",))

    def test_no_dimension_exposes_a_normalised_variant_of_its_value(self):
        for forbidden in ("normalised", "normalized", "scaled", "index",
                          "percentile", "rating"):
            with self.subTest(attribute=forbidden):
                self.assertNotIn(forbidden, DimensionScore.__dataclass_fields__)

    def test_no_numeric_measure_is_confined_to_a_zero_to_one_range(self):
        # The signature of a normalised dimension is that every value it ever
        # produces sits inside [0, 1]. Cover in days and blocked units in units
        # both leave that range in real data, which is what makes them units
        # rather than scores.
        profiles = fixture_profiles()
        covers = [p.buffer_cover.value for p in profiles.values()
                  if isinstance(p.buffer_cover.value, Fraction)]
        blocked = [p.blast_radius.value for p in profiles.values()]
        self.assertTrue(any(value > 1 for value in covers))
        self.assertTrue(any(value > 100 for value in blocked))

    def test_the_units_in_use_are_mutually_unaddable(self):
        units = {score.unit for profile in fixture_profiles().values()
                 for score in profile.scored()}
        self.assertGreater(len(units), 1,
                           "if every dimension shared one unit they could be "
                           "summed, and the separation would be decorative")


class TestReasonsAndConstruction(unittest.TestCase):

    def test_every_dimension_carries_a_reason(self):
        for profile in fixture_profiles().values():
            for score in profile.scored():
                with self.subTest(part=profile.part_number,
                                  dimension=score.dimension):
                    self.assertTrue(score.reasons)
                    self.assertIsInstance(score.reasons[0], str)

    def test_a_score_without_a_reason_is_refused(self):
        with self.assertRaises(ValueError):
            DimensionScore(part_number="P", dimension="buffer_cover", value=1,
                           unit=DAYS, completeness=KNOWN, reasons=())

    def test_an_unknown_dimension_is_refused(self):
        with self.assertRaises(ValueError):
            DimensionScore(part_number="P", dimension="vibes", value=1,
                           unit=DAYS, completeness=KNOWN, reasons=("x",))


class TestConcentrationSlotIsReserved(unittest.TestCase):

    def test_the_slot_exists_and_is_unfilled(self):
        profile = fixture_profiles()["ONLY-M01"]
        self.assertIn("concentration", ExposureProfile.__dataclass_fields__)
        self.assertIsNone(profile.concentration)

    def test_concentration_is_not_one_of_the_scored_five(self):
        # Reserved is distinct from answered AND from abstained. Collapsing it
        # into either would be a claim about a stage that has not run.
        profile = fixture_profiles()["ONLY-M01"]
        self.assertEqual(len(profile.scored()), 5)
        self.assertNotIn("concentration",
                         [score.dimension for score in profile.scored()])

    def test_concentration_is_declared_as_a_dimension(self):
        self.assertIn("concentration", scoring.DIMENSIONS)
        self.assertEqual(len(scoring.DIMENSIONS), 6)


class TestLogging(unittest.TestCase):

    def test_one_event_per_dimension_with_the_right_kind(self):
        log = gov.DecisionLog()
        scoring.log_profile(log, fixture_profiles()["MISSING-M01"])
        self.assertEqual(len(log), 5)
        kinds = {event.field: event.kind for event in log}
        self.assertEqual(kinds["blast_radius"], gov.KIND_DIMENSION_SCORED)
        self.assertEqual(kinds["buffer_cover"], gov.KIND_DIMENSION_ABSTAINED)
        self.assertEqual(kinds["portability"], gov.KIND_DIMENSION_ABSTAINED)

    def test_the_log_stores_no_prose(self):
        from src.governance.render import render
        log = gov.DecisionLog()
        scoring.log_profile(log, fixture_profiles()["SHARED-M01"])
        for event in log:
            self.assertNotIn(render(event), repr(event.evidence))


# ------------------------------------------------------------- known gap ----
# Marked xfail(strict=True) so the gap stays visible, CI stays green, and the
# test fails LOUDLY the day somebody closes it without noticing.
#
# REWRITTEN, NOT DELETED. The gap this slot used to hold was that recovery time
# ignored qualification entirely: there was no qualification-lead-time field
# anywhere in the schema, so a part needing forty weeks to requalify scored
# identically to one resourceable in a fortnight. `resource_days` closes that
# one: `TestTheTwoHalvesOfRecoveryStaySeparate` asserts the two parts now score
# differently, and `recovery_inputs.csv` is where the durations live.
#
# What is left is the next layer down, and it is unrepresentable in the same way
# the first one was.
@pytest.mark.xfail(strict=True, reason=(
    "The resourcing chain is timed PER PART, never per candidate alternate "
    "source. How long qualification takes depends on WHICH alternative you go "
    "to: a supplier already running the process next door and one that has to "
    "buy the capability are not the same programme, and the practitioner's "
    "point that qualification varies significantly by part is equally a point "
    "that it varies by source. Nothing in this schema represents a candidate "
    "source, so the chain times a generic alternative, as though every "
    "candidate were interchangeable. A part with one near-drop-in second "
    "source and a part whose only candidate needs a new process score "
    "identically."))
def test_resource_days_distinguishes_between_candidate_alternate_sources():
    """BEHAVIOURAL, and deliberately not `hasattr`, for the reason the
    predecessor recorded: a bare name with no logic behind it satisfies an
    attribute check and flips a strict xfail to XPASS while the measure still
    answers the wrong question. That is a proxy standing in for the property,
    which is the defect shape this project's corrections log is about.

    This asserts the scenario the gap is named for. Two parts have identical
    stage durations for everything the schema can express. One has a candidate
    already running the process and one does not, and the qualification
    durations for those candidates differ by twenty to one. Candidates ride in
    a `candidates` key, which is one shape the future input could take; today
    the chain reads the flat stage fields and ignores anything else, so both
    parts score identically and this fails on the assertion rather than on the
    input. That equality is the gap.
    """
    near = scoring.resource_days("NEAR-Q", "supplier", dict(
        TIMED, candidates=({"name": "already runs the process",
                            "qualification_test_days": 14},)))
    far = scoring.resource_days("FAR-Q", "supplier", dict(
        TIMED, candidates=({"name": "has to buy the capability",
                            "qualification_test_days": 280},)))

    assert near.value != far.value, (
        "a part whose only candidate source needs forty weeks to qualify "
        "scores identically to one with a near drop-in alternative, so the "
        "chain times a generic alternative rather than the one that would "
        "actually be used")


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
