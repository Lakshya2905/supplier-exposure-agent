"""Concentration: a property of a set, with a permanent decision ceiling.

Expectations are hand-written in tests/fixtures/tiny_expected_clusters.py from
the rows of tiny_suppliers.csv. Nothing here imports a value the code under test
produced, and no verdict string is imported from the verdict table.
"""
import collections
import dataclasses
import inspect
import unittest
from pathlib import Path

import pandas as pd
import pytest

from fixtures.tiny_expected_clusters import (CONTINGENT_CLUSTERS,
                                             EXPECTED_AGREEMENT,
                                             EXPECTED_AGREEMENT_SUMMARY,
                                             EXPECTED_CLUSTERS,
                                             EXPECTED_CLUSTER_COMPLETENESS,
                                             EXPECTED_PART_COMPLETENESS,
                                             EXPECTED_UNCONCENTRATED_SUPPLIERS,
                                             FIXTURE_THRESHOLD,
                                             NOT_APPLICABLE_PARTS, VERDICTS)
from src import concentration as C
from src import governance as gov
from src import scoring
from src.concentration import Cluster, ConcentrationScore, analyse

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_dependencies():
    frame = pd.read_csv(FIXTURES / "tiny_suppliers.csv", comment="#",
                        keep_default_na=False, dtype=str)
    dependencies = collections.defaultdict(list)
    for _, row in frame.iterrows():
        dependencies[row["part_number"]].append(
            (row["supplier_name"], row["supplier_region"]))
    return {part: tuple(pairs) for part, pairs in dependencies.items()}


def fixture_report(threshold=FIXTURE_THRESHOLD):
    return analyse(VERDICTS, fixture_dependencies(), threshold=threshold)


class TestClusters(unittest.TestCase):

    def setUp(self):
        self.report = fixture_report()
        self.by_key = {(c.basis, c.key): c for c in self.report.clusters}

    def test_every_expected_cluster_is_found_with_the_right_members(self):
        for (basis, key), members in EXPECTED_CLUSTERS.items():
            with self.subTest(basis=basis, key=key):
                self.assertIn((basis, key), self.by_key)
                self.assertEqual(self.by_key[(basis, key)].members, members)

    def test_no_unexpected_cluster_is_concentrated(self):
        found = {(c.basis, c.key) for c in self.report.concentrated()}
        self.assertEqual(found, set(EXPECTED_CLUSTERS))

    def test_cluster_completeness_matches(self):
        for key, completeness in EXPECTED_CLUSTER_COMPLETENESS.items():
            with self.subTest(cluster=key):
                self.assertEqual(self.by_key[key].completeness, completeness)

    def test_members_are_carried_by_identity_not_only_counted(self):
        # Nine parts on one supplier where seven are long lead is a different
        # finding from nine catalogue parts. The count is the summary; the
        # membership is the finding, and a reviewer needs it at the moment they
        # decide whether to act.
        for cluster in self.report.concentrated():
            with self.subTest(cluster=cluster.key):
                self.assertEqual(len(cluster.members), cluster.size)
                for member in cluster.members:
                    self.assertIsInstance(member, str)
                    self.assertTrue(member)

    def test_membership_is_sorted_so_identity_does_not_depend_on_order(self):
        for cluster in self.report.clusters:
            with self.subTest(cluster=cluster.key):
                self.assertEqual(list(cluster.members),
                                 sorted(cluster.members))

    def test_a_cluster_with_unsorted_members_is_refused(self):
        with self.assertRaises(ValueError):
            Cluster(key="X", basis="supplier", members=("B", "A"),
                    completeness="known")


class TestArityNotMagnitude(unittest.TestCase):
    """"Concentrated" must not become a tuned threshold in disguise."""

    def test_two_is_the_minimum_correlation(self):
        self.assertEqual(C.MINIMUM_CORRELATION, 2)

    def test_a_cluster_of_one_is_never_concentrated(self):
        report = fixture_report()
        by_key = {c.key: c for c in report.clusters if c.basis == "supplier"}
        for key in EXPECTED_UNCONCENTRATED_SUPPLIERS:
            with self.subTest(supplier=key):
                self.assertFalse(by_key[key].is_concentrated)

    def test_a_cluster_of_two_is_always_concentrated(self):
        # Two is the arity at which a correlation exists at all, not a severity
        # judgment. One part is not correlated with anything.
        cluster = Cluster(key="X", basis="supplier", members=("A", "B"),
                          completeness="known")
        self.assertTrue(cluster.is_concentrated)

    def test_no_banding_constant_exists_anywhere_in_the_module(self):
        # CODE ONLY, docstrings and comments stripped, as at stage 4: the
        # docstrings explain at length why there is no band.
        source = inspect.getsource(C)
        import ast
        tree = ast.parse(source)
        code = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                body = list(node.body)
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    body = body[1:]
                code.extend(ast.unparse(item) for item in body)
            elif not (isinstance(node, ast.Expr)
                      and isinstance(node.value, ast.Constant)):
                code.append(ast.unparse(node))
        joined = "\n".join(code)
        # WORD BOUNDARIES, not substrings: "LOW" occurs inside LOWER_BOUND,
        # which is a bound direction rather than a band label. A substring scan
        # here fails on correct code and teaches the next person to delete the
        # test rather than fix the violation.
        import re
        for banding_word in ("severity", "critical", "band", "bands", "HIGH",
                             "LOW", "MEDIUM", "tier"):
            with self.subTest(word=banding_word):
                self.assertIsNone(
                    re.search(rf"\b{banding_word}\b", joined),
                    f"{banding_word!r} appears in concentration code; "
                    f"severity is carried by the raw count, never banded")

    def test_severity_is_carried_by_the_raw_count_with_a_unit(self):
        for score in fixture_report().scores.values():
            with self.subTest(part=score.part_number):
                self.assertEqual(score.unit, scoring.PARTS)


class TestTheDecisionCeiling(unittest.TestCase):
    """Permanent `recommends`, and it must be impossible rather than merely
    unwritten."""

    def test_no_concentration_finding_ever_executes(self):
        for score in fixture_report().scores.values():
            with self.subTest(part=score.part_number):
                self.assertEqual(score.autonomy, gov.RECOMMENDS)

    def test_the_ceiling_holds_on_completely_settled_data(self):
        # THE TEST THAT MATTERS. The argument for drifting to executes is that
        # the arithmetic is deterministic once a definition is chosen, so the
        # ceiling has to survive data with no uncertainty in it at all.
        score = ConcentrationScore(
            part_number="P", dimension="concentration", value=4,
            unit=scoring.PARTS, completeness=scoring.KNOWN,
            agreement=C.BOTH, reasons=("everything is known",))
        self.assertEqual(score.completeness, scoring.KNOWN)
        self.assertEqual(score.autonomy, gov.RECOMMENDS)

    def test_the_ceiling_holds_for_every_completeness_state(self):
        for state in scoring.COMPLETENESS_STATES:
            with self.subTest(completeness=state):
                score = ConcentrationScore(
                    part_number="P", dimension="concentration",
                    value=None if state in (scoring.CANNOT_TELL,
                                            scoring.NOT_APPLICABLE,
                                            scoring.NO_RECOVERY_PATH) else 2,
                    unit=scoring.PARTS, completeness=state,
                    reasons=("because",))
                self.assertEqual(score.autonomy, gov.RECOMMENDS)

    def test_autonomy_is_not_derived_from_completeness_here(self):
        # Stage 4 derives autonomy from completeness in one place. This is a
        # DELIBERATE divergence: completeness answers "do we have the data",
        # the ceiling answers "may a system claim this alone", and complete
        # data does not turn a modelling choice into a fact.
        self.assertEqual(scoring.autonomy_for(scoring.KNOWN), gov.EXECUTES)
        score = ConcentrationScore(
            part_number="P", dimension="concentration", value=2,
            unit=scoring.PARTS, completeness=scoring.KNOWN,
            reasons=("because",))
        self.assertNotEqual(score.autonomy,
                            scoring.autonomy_for(score.completeness))

    def test_a_cluster_also_carries_the_ceiling(self):
        for cluster in fixture_report().clusters:
            self.assertEqual(cluster.autonomy, gov.RECOMMENDS)


class TestComplementaryDisagreement(unittest.TestCase):
    """The two readings answer different questions, so disagreement REPORTS."""

    def setUp(self):
        self.report = fixture_report()

    def test_agreement_class_matches_the_hand_written_expectations(self):
        for part, agreement in EXPECTED_AGREEMENT.items():
            with self.subTest(part=part):
                self.assertEqual(self.report.scores[part].agreement, agreement)

    def test_all_four_agreement_classes_occur(self):
        found = {score.agreement for score in self.report.scores.values()}
        for name in C.AGREEMENT_CLASSES:
            with self.subTest(agreement=name):
                self.assertIn(name, found)

    def test_the_summary_counts_match(self):
        self.assertEqual(self.report.agreement_summary(),
                         EXPECTED_AGREEMENT_SUMMARY)

    def test_region_only_is_a_finding_and_not_a_false_positive(self):
        # Two different companies in one region. Supplier grouping is
        # structurally blind to this, and reporting it as a defect of supplier
        # grouping would discard the reason for computing both.
        score = self.report.scores["CON-P06"]
        self.assertEqual(score.agreement, C.REGION_ONLY)
        self.assertEqual(score.autonomy, gov.RECOMMENDS)
        self.assertIn("different companies", score.reasons[0])
        self.assertEqual(score.completeness, scoring.KNOWN,
                         "a complementary disagreement is not an uncertainty "
                         "and must not be recorded as one")

    def test_both_is_materially_different_from_region_only(self):
        stronger = self.report.scores["CON-P01"]
        weaker = self.report.scores["CON-P16"]
        self.assertEqual(stronger.agreement, C.BOTH)
        self.assertEqual(weaker.agreement, C.REGION_ONLY)
        self.assertNotEqual(stronger.reasons, weaker.reasons)

    def test_supplier_only_names_the_commercial_correlation(self):
        score = self.report.scores["CON-P04"]
        self.assertEqual(score.agreement, C.SUPPLIER_ONLY)
        self.assertIn("commercial", score.reasons[0])

    def test_a_north_america_region_is_not_swallowed_as_a_null(self):
        # `NA` is North America. A region read as NaN would silently shrink a
        # cluster, and the part would look less correlated than it is.
        dependencies = fixture_dependencies()
        self.assertEqual(dependencies["CON-P04"][0][1], "NA")


class TestOneReadingUnsettled(unittest.TestCase):

    def test_a_blank_region_leaves_the_agreement_uncomputed(self):
        # NOT defaulted to "not concentrated", which would silently downgrade
        # the finding by treating an unread reading as a negative answer.
        score = fixture_report().scores["CON-P09"]
        self.assertEqual(score.agreement, C.UNDETERMINED)
        self.assertEqual(score.detail["region_reading"], "unknown")
        self.assertNotEqual(score.agreement, C.SUPPLIER_ONLY)

    def test_the_settled_reading_is_still_reported(self):
        score = fixture_report().scores["CON-P09"]
        self.assertEqual(score.detail["supplier_cluster_size"], 2)
        self.assertIn("no region is recorded", score.reasons[0])


class TestMembershipUncertainty(unittest.TestCase):
    """Aggregation cannot manufacture certainty."""

    def setUp(self):
        self.report = fixture_report()

    def test_part_completeness_matches_the_hand_written_expectations(self):
        for part, completeness in EXPECTED_PART_COMPLETENESS.items():
            with self.subTest(part=part):
                self.assertEqual(self.report.scores[part].completeness,
                                 completeness)

    def test_a_growable_cluster_is_a_lower_bound_not_an_abstention(self):
        # Membership can only GROW, and more members can only worsen
        # concentration. Same direction as blast radius, same reason: the
        # uncertain quantity sits in the numerator.
        cluster = {(c.basis, c.key): c for c in self.report.clusters}[
            ("supplier", "Theta Group")]
        self.assertEqual(cluster.completeness, scoring.LOWER_BOUND)
        self.assertEqual(cluster.members, ("CON-P13", "CON-P14"))
        self.assertEqual(cluster.members_if_merged,
                         ("CON-P13", "CON-P14", "CON-P15"))
        self.assertTrue(set(cluster.members_if_merged) > set(cluster.members))

    def test_a_contingent_concentration_routes_rather_than_bounds(self):
        # Two singletons that may be one supplier. It is the CORRELATION whose
        # existence is in doubt, not the size of an existing one, and that is a
        # contested disagreement.
        for key in CONTINGENT_CLUSTERS:
            cluster = {(c.basis, c.key): c for c in self.report.clusters}[key]
            with self.subTest(cluster=key):
                self.assertTrue(cluster.contingent)
                self.assertEqual(cluster.completeness, scoring.CANNOT_TELL)

    def test_contingency_is_detected_on_the_correlation_not_the_cluster_key(self):
        # Both spellings exist as keys under both readings, so testing key
        # novelty would miss this case entirely. What is new is the CONCENTRATION.
        self.assertEqual(self.report.scores["CON-P11"].completeness,
                         scoring.CANNOT_TELL)
        self.assertTrue(self.report.scores["CON-P11"].detail["contingent"])

    def test_a_part_that_would_join_a_concentrated_group_is_contingent_too(self):
        # CON-P15 sits outside Theta Group under the confirmed spellings and
        # inside it under the merged ones.
        score = self.report.scores["CON-P15"]
        self.assertEqual(score.completeness, scoring.CANNOT_TELL)
        self.assertEqual(score.detail["supplier_cluster_size"], 1)
        self.assertEqual(score.detail["supplier_cluster_size_if_merged"], 3)

    def test_what_a_merge_would_change_is_recorded_not_asserted(self):
        score = self.report.scores["CON-P11"]
        self.assertEqual(score.agreement, C.REGION_ONLY)
        self.assertEqual(score.detail["agreement_if_merged"], C.BOTH)

    def test_raising_the_threshold_removes_both_uncertainties(self):
        # At the shipped 0.95 neither confusable pair merges, so nothing here
        # is contingent or bounded. Proves the uncertainty comes from the merge
        # and not from the clustering code.
        report = fixture_report(threshold=0.95)
        states = {score.completeness for score in report.scores.values()}
        self.assertNotIn(scoring.CANNOT_TELL, states)
        self.assertNotIn(scoring.LOWER_BOUND, states)


class TestGlobalCaveat(unittest.TestCase):

    def test_unplaceable_parts_are_reported_once_not_per_cluster(self):
        # An uncertainty every cluster shares does not discriminate between
        # clusters. A completeness state that is always the same state is a
        # footer, not a state, and smearing it would destroy the signal that
        # marks the clusters with a real local problem.
        verdicts = dict(VERDICTS)
        verdicts["CON-P16"] = "supplier_list_unknown"
        report = analyse(verdicts, fixture_dependencies(),
                         threshold=FIXTURE_THRESHOLD)
        self.assertEqual(report.unplaceable_parts, ("CON-P16",))
        self.assertTrue(report.reasons)
        self.assertIn("lower bound", report.reasons[0])
        for cluster in report.clusters:
            with self.subTest(cluster=cluster.key):
                self.assertIn(cluster.completeness,
                              (scoring.KNOWN, scoring.LOWER_BOUND,
                               scoring.CANNOT_TELL))

    def test_the_caveat_is_never_silent(self):
        verdicts = dict(VERDICTS)
        verdicts["CON-P16"] = "supplier_list_unknown"
        report = analyse(verdicts, fixture_dependencies())
        self.assertTrue(report.reasons,
                        "silence is what would let a reviewer read a cluster "
                        "of three as complete")


class TestNotApplicable(unittest.TestCase):

    def setUp(self):
        self.report = fixture_report()

    def test_parts_with_no_supplier_are_not_applicable(self):
        for part in NOT_APPLICABLE_PARTS:
            with self.subTest(part=part):
                self.assertEqual(self.report.scores[part].completeness,
                                 scoring.NOT_APPLICABLE)

    def test_no_qualified_supplier_says_why_it_is_not_applicable(self):
        # A reviewer seeing the most exposed part in the dataset marked not
        # applicable will assume a bug unless the sentence says that
        # correlation requires someone to correlate with.
        reason = self.report.scores["CON-P18"].reasons[0]
        self.assertIn("correlation needs someone to correlate with", reason)
        self.assertIn("not a downgrade", reason)
        self.assertIn("lead time to recover", reason)

    def test_made_in_house_says_why_and_names_the_gap(self):
        reason = self.report.scores["CON-P17"].reasons[0]
        self.assertIn("correlation needs someone to correlate with", reason)
        self.assertIn("internal", reason)

    def test_a_multi_source_part_is_answered_no_rather_than_not_applicable(self):
        # The question APPLIES and the answer is negative. Using
        # NOT_APPLICABLE for a negative answer would collapse "does not apply"
        # into "no", which is the collapse the six states exist to prevent.
        verdicts = dict(VERDICTS)
        verdicts["CON-P01"] = "multi_source"
        score = analyse(verdicts, fixture_dependencies()).scores["CON-P01"]
        self.assertEqual(score.completeness, scoring.KNOWN)
        self.assertEqual(score.agreement, C.NEITHER)
        self.assertEqual(score.value, 1)


class TestReviewQueue(unittest.TestCase):

    def test_the_queue_holds_only_concentrated_clusters_largest_first(self):
        queue = fixture_report().review_queue()
        self.assertTrue(all(c.is_concentrated for c in queue))
        self.assertEqual([c.size for c in queue],
                         sorted((c.size for c in queue), reverse=True))

    def test_the_queue_is_not_the_abstention_lane(self):
        # Different reviewer tasks: the lane means "fetch me a number", the
        # queue means "confirm my model". Merging them floods the lane.
        report = fixture_report()
        self.assertTrue(report.review_queue())
        self.assertFalse(hasattr(report, "abstention_lane"))


class TestLogging(unittest.TestCase):

    def test_one_event_per_cluster_never_one_per_member(self):
        log = gov.DecisionLog()
        report = fixture_report()
        C.log_report(log, report)
        self.assertEqual(len(log), len(report.review_queue()))
        total_members = sum(c.size for c in report.review_queue())
        self.assertLess(len(log), total_members,
                        "one act per member would make a reviewer confirm the "
                        "same judgment once for every part in the cluster")

    def test_member_count_carries_the_cluster_size(self):
        log = gov.DecisionLog()
        report = fixture_report()
        C.log_report(log, report)
        sizes = {c.key: c.size for c in report.review_queue()}
        for event in log:
            with self.subTest(cluster=event.sku_id):
                self.assertEqual(event.member_count, sizes[event.sku_id])
                self.assertEqual(event.evidence["member_count"],
                                 sizes[event.sku_id])

    def test_the_members_travel_with_the_event(self):
        log = gov.DecisionLog()
        C.log_report(log, fixture_report())
        for event in log:
            with self.subTest(cluster=event.sku_id):
                self.assertTrue(event.evidence["members"])
                self.assertEqual(len(event.evidence["members"]),
                                 event.member_count)

    def test_a_contingent_cluster_logs_its_own_kind(self):
        log = gov.DecisionLog()
        C.log_report(log, fixture_report())
        kinds = {event.sku_id: event.kind for event in log}
        self.assertEqual(kinds["Marrow Corporation"],
                         gov.KIND_CLUSTER_CONTINGENT)
        self.assertEqual(kinds["Alpha Works"], gov.KIND_CLUSTER_FLAGGED)

    def test_the_log_stores_no_prose(self):
        from src.governance.render import render
        log = gov.DecisionLog()
        C.log_report(log, fixture_report())
        for event in log:
            self.assertNotIn(render(event), repr(event.evidence))


class TestFillingTheReservedSlot(unittest.TestCase):
    """Stage 5 may add a method. It may not change what an existing one means."""

    def build_profile(self):
        from fractions import Fraction

        from src.demand import USAGE_KNOWN, Usage
        usage = Usage("CON-P01", Fraction(1000), USAGE_KNOWN)
        return scoring.score_part(
            part_number="CON-P01", verdict="single_source", rows=(),
            usage=usage, on_hand_units=100, tooling_owner="company",
            lead_times=[(30, 45)])

    def test_the_slot_is_filled_without_adding_a_field(self):
        before = set(scoring.ExposureProfile.__dataclass_fields__)
        profile = self.build_profile()
        filled = dataclasses.replace(
            profile, concentration=fixture_report().scores["CON-P01"])
        self.assertEqual(set(type(filled).__dataclass_fields__), before)
        self.assertIsNotNone(filled.concentration)

    def test_the_four_stage_four_dimensions_are_unchanged_by_value(self):
        # THE FROZEN DATACLASS AND `replace` MAKE THIS TRUE TODAY, which is
        # exactly why it needs asserting before somebody makes the profile
        # mutable for convenience and fills the slot in place.
        profile = self.build_profile()
        filled = dataclasses.replace(
            profile, concentration=fixture_report().scores["CON-P01"])
        self.assertEqual(len(profile.scored()), len(filled.scored()))
        for original, after in zip(profile.scored(), filled.scored()):
            with self.subTest(dimension=original.dimension):
                self.assertEqual(original, after)
                self.assertEqual(original.value, after.value)
                self.assertEqual(original.unit, after.unit)
                self.assertEqual(original.completeness, after.completeness)
                self.assertEqual(original.autonomy, after.autonomy)
                self.assertEqual(original.reasons, after.reasons)
                self.assertEqual(original.detail, after.detail)

    def test_the_original_profile_is_not_mutated(self):
        profile = self.build_profile()
        dataclasses.replace(
            profile, concentration=fixture_report().scores["CON-P01"])
        self.assertIsNone(profile.concentration)

    def test_scored_keeps_its_stage_four_meaning(self):
        filled = dataclasses.replace(
            self.build_profile(),
            concentration=fixture_report().scores["CON-P01"])
        self.assertEqual(len(filled.scored()), 4)
        self.assertNotIn("concentration",
                         [s.dimension for s in filled.scored()])

    def test_all_scores_adds_concentration_without_replacing_scored(self):
        profile = self.build_profile()
        filled = dataclasses.replace(
            profile, concentration=fixture_report().scores["CON-P01"])
        self.assertEqual(len(profile.all_scores()), 4)
        self.assertEqual(len(filled.all_scores()), 5)
        self.assertIn("concentration",
                      [s.dimension for s in filled.all_scores()])

    def test_fill_profiles_leaves_a_part_without_a_score_alone(self):
        profiles = {"CON-P01": self.build_profile()}
        filled = C.fill_profiles(profiles, fixture_report())
        self.assertIsNotNone(filled["CON-P01"].concentration)


# ------------------------------------------------------------- known gaps ----
@pytest.mark.xfail(strict=True, reason=(
    "Tier correlation is UNREPRESENTABLE. The brief names same-supplier, "
    "same-region and same-tier as three definitions of correlated. There is no "
    "tier field anywhere in the schema, so the third reading cannot be "
    "computed at all. Choosing two of three is a scoping decision and should "
    "not look like the data happened to support exactly the right two."))
def test_concentration_can_group_by_tier():
    import src.synthetic.model as model
    assert hasattr(model, "SUPPLIER_TIER"), "no tier field exists"


@pytest.mark.xfail(strict=True, reason=(
    "In-house concentration is not modelled. A part made on one internal line "
    "or cell is a single point of failure that neither supplier grouping nor "
    "region grouping can see, because the data has no representation of "
    "internal capacity at all. Made-in-house parts are therefore "
    "NOT_APPLICABLE for concentration while still carrying real correlated "
    "risk."))
def test_in_house_parts_can_be_concentrated_on_an_internal_line():
    import src.synthetic.model as model
    assert hasattr(model, "INTERNAL_WORK_CENTRE"), "no internal capacity field"


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
