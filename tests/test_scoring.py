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

from fixtures.tiny_expected_scores import (EXPECTED_BLAST_RADIUS_COMPLETENESS,
                                           EXPECTED_BLOCKED_UNITS,
                                           EXPECTED_COVER_COMPLETENESS,
                                           EXPECTED_COVER_DAYS,
                                           EXPECTED_FINISHED_GOODS_BLOCKED,
                                           EXPECTED_PORTABILITY, SCORED_PARTS)
from src import governance as gov
from src import scoring
from src.demand import Usage, usage_by_part, USAGE_CANNOT_TELL, USAGE_KNOWN
from src.explosion import explode, rows_by_part
from src.readers import read_bom, read_demand_plan, read_part_master
from src.scoring import (CANNOT_TELL, DAYS, KNOWN, LOWER_BOUND, NOT_APPLICABLE,
                         NO_RECOVERY_PATH, UPPER_BOUND, DimensionScore,
                         ExposureProfile, abstention_lane, blast_radius,
                         buffer_cover, lead_time_to_recover, portability,
                         score_part)

FIXTURES = Path(__file__).parent / "fixtures"


def code_of(function):
    """A function's CODE, with its docstring and comments removed.

    Several tests below assert that a word does not appear in an
    implementation. The words in question ("composite", "band", "weight") are
    exactly the words the docstrings use to explain why the thing is refused,
    so scanning raw source flags the explanations and not the violations.
    `ast.unparse` drops comments, and the docstring is stripped explicitly.
    """
    import ast
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    node = tree.body[0]
    body = list(node.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return "\n".join(ast.unparse(statement) for statement in body)


def fixture_profiles():
    edges = read_bom(FIXTURES / "tiny_scoring_bom.csv")
    rows = rows_by_part(explode(edges))
    demand = read_demand_plan(FIXTURES / "tiny_demand.csv")
    parts = read_part_master(FIXTURES / "tiny_part_master.csv")
    usage = usage_by_part(rows, demand)
    profiles = {}
    for part in SCORED_PARTS:
        record = parts[part]
        profiles[part] = score_part(
            part_number=part, verdict="single_source", rows=rows[part],
            usage=usage[part], on_hand_units=record["on_hand_units"],
            tooling_owner=record["tooling_owner"],
            lead_times=[(30, 45)])
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
        self.assertIn("not zero cover", self.missing.reasons[0])


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
        self.assertIn("only reduce cover", profile.buffer_cover.reasons[0])
        self.assertIn("only add", profile.blast_radius.reasons[0])


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


class TestLeadTimeToRecover(unittest.TestCase):
    """Hard-coded expectations; the verdict strings are literals."""

    def test_both_lead_time_columns_are_returned_not_one(self):
        score = lead_time_to_recover("P", "single_source", [(30, 45)])
        self.assertEqual(score.value, (30, 45))
        self.assertEqual(score.detail["quoted_days"], 30)
        self.assertEqual(score.detail["p95_days"], 45)

    def test_the_fastest_supplier_sets_the_recovery_time(self):
        score = lead_time_to_recover("P", "multi_source", [(60, 90), (30, 45)])
        self.assertEqual(score.value, (30, 45))

    def test_no_lead_time_record_abstains(self):
        score = lead_time_to_recover("P", "single_source_no_lead_time", [])
        self.assertEqual(score.completeness, CANNOT_TELL)
        self.assertEqual(score.autonomy, gov.RECOMMENDS)

    def test_no_qualified_supplier_is_not_an_abstention(self):
        # Undefined by absence, not missing from the spreadsheet. Rendering it
        # as "cannot tell" would understate the most serious finding here.
        score = lead_time_to_recover("P", "no_qualified_supplier", [])
        self.assertEqual(score.completeness, NO_RECOVERY_PATH)
        self.assertEqual(score.autonomy, gov.EXECUTES)

    def test_made_in_house_does_not_apply_rather_than_being_unknown(self):
        # A lane that keeps showing in-house parts asks a reviewer to fetch
        # data that does not exist anywhere and never will.
        score = lead_time_to_recover("P", "made_in_house", [])
        self.assertEqual(score.completeness, NOT_APPLICABLE)
        self.assertEqual(score.autonomy, gov.EXECUTES)

    def test_the_three_no_value_states_stay_distinct(self):
        states = {
            lead_time_to_recover("P", "single_source_no_lead_time", []
                                 ).completeness,
            lead_time_to_recover("P", "no_qualified_supplier", []).completeness,
            lead_time_to_recover("P", "made_in_house", []).completeness,
        }
        self.assertEqual(len(states), 3,
                         "all three have no value, and collapsing any two "
                         "would tell a reviewer the wrong thing to do next")

    def test_an_unconfirmed_supplier_list_abstains_even_with_a_lead_time(self):
        score = lead_time_to_recover("P", "supplier_list_unknown", [(30, 45)])
        self.assertEqual(score.completeness, CANNOT_TELL)

    def test_nothing_here_bands_a_duration(self):
        # "Long lead" is a threshold and a threshold is a judgment. Stage 4
        # returns raw durations so its autonomy claim does not rest on one.
        # CODE ONLY: the docstring explains why there is no banding, so a raw
        # source scan would flag the explanation rather than a violation.
        code = code_of(lead_time_to_recover)
        for banding_word in ("long_lead", "is_long", "band", "tier",
                             "severity", "critical"):
            with self.subTest(word=banding_word):
                self.assertNotIn(banding_word, code)


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

    def test_in_house_parts_never_reach_the_lane(self):
        profile = ExposureProfile(
            part_number="P",
            lead_time_to_recover=lead_time_to_recover("P", "made_in_house", []),
            blast_radius=blast_radius("P", (), Usage("P", Fraction(0),
                                                     USAGE_KNOWN)),
            buffer_cover=buffer_cover("P", 0, Usage("P", Fraction(0),
                                                    USAGE_KNOWN)),
            portability=portability("P", "company"))
        self.assertEqual(abstention_lane([profile]), {})


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
        # Scans CODE only. Docstrings and comments in this module discuss
        # composites at length in order to refuse them, so scanning raw source
        # would flag the very explanations that make the refusal legible.
        import ast
        tree = ast.parse(inspect.getsource(scoring))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            body = list(node.body)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body = body[1:]           # drop the docstring
            code = "\n".join(ast.unparse(statement) for statement in body)
            with self.subTest(function=node.name):
                for forbidden in ("weight", "composite", "overall_score",
                                  "normalise", "normalize"):
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

    def test_concentration_is_not_one_of_the_scored_four(self):
        # Reserved is distinct from answered AND from abstained. Collapsing it
        # into either would be a claim about a stage that has not run.
        profile = fixture_profiles()["ONLY-M01"]
        self.assertEqual(len(profile.scored()), 4)
        self.assertNotIn("concentration",
                         [score.dimension for score in profile.scored()])

    def test_concentration_is_declared_as_a_dimension(self):
        self.assertIn("concentration", scoring.DIMENSIONS)
        self.assertEqual(len(scoring.DIMENSIONS), 5)


class TestLogging(unittest.TestCase):

    def test_one_event_per_dimension_with_the_right_kind(self):
        log = gov.DecisionLog()
        scoring.log_profile(log, fixture_profiles()["MISSING-M01"])
        self.assertEqual(len(log), 4)
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
@pytest.mark.xfail(strict=True, reason=(
    "The brief defines lead time to recover as how long to QUALIFY AN "
    "ALTERNATIVE or wait out the disruption. The data carries quoted and p95 "
    "purchase lead times, so this dimension answers the second half only. "
    "There is no qualification-lead-time field anywhere in the schema, so the "
    "first half is not merely uncomputed, it is unrepresentable. A part with a "
    "30 day purchase lead time whose only supplier needs 40 weeks to qualify a "
    "replacement scores identically to one that can be resourced in a "
    "fortnight."))
def test_lead_time_to_recover_covers_qualification_time():
    from src.synthetic.model import QUOTED_LEAD_TIME_DAYS
    import src.synthetic.model as model
    assert hasattr(model, "QUALIFICATION_LEAD_TIME_DAYS"), (
        "no field records how long qualifying an alternative source takes")


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
