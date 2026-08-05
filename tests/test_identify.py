"""Single-source identification, verdict by verdict.

SELF-AGREEMENT GUARD. Nothing in this file imports `src.synthetic.verdicts`.
Every expected verdict below is written out by hand as a literal string, from
the table in docs/BRIEF.md. Importing the table would let a wrong row be wrong
in both the code and the test, and the suite would agree with the bug.
"""
import unittest

from src import governance as gov
from src.identify import (DEFAULT_THRESHOLD, exception_lane, identify,
                          identify_all)

# Deliberately unalike, so no test below merges two suppliers by accident and
# quietly changes the count it is asserting on.
A = "Acme Works"
B = "Zenith Industries"
C = "Corvid Manufacturing"


def verdict_of(source_type, list_status, suppliers, lead_times,
               threshold=DEFAULT_THRESHOLD):
    return identify("SEA-P-TEST", source_type, list_status, suppliers,
                    lead_times, threshold=threshold).verdict


class TestVerdictRowsThroughIdentify(unittest.TestCase):
    """One test per row of the brief's table, expectations hand-written.

    Stage 1 already tests the table as a function. These test the row as it is
    reached through the observed-data path, which is where the counts come from
    a fuzzy match rather than from the generator's own bookkeeping.
    """

    # ------------------------------------------------------------- buy / 0 --
    def test_buy_zero_suppliers_verified_list(self):
        # Somebody checked and found nobody. A real and serious finding.
        self.assertEqual(verdict_of("buy", "verified", [], []),
                         "no_qualified_supplier")

    def test_buy_zero_suppliers_unverified_list(self):
        # Nobody checked. Not the same finding, and must not collapse into it.
        self.assertEqual(verdict_of("buy", "unverified", [], []),
                         "supplier_list_unknown")

    def test_buy_zero_suppliers_blank_list_status(self):
        self.assertEqual(verdict_of("buy", "", [], []),
                         "supplier_list_unknown")

    # ------------------------------------------------------------- buy / 1 --
    def test_buy_one_supplier_verified_with_lead_time(self):
        self.assertEqual(verdict_of("buy", "verified", [A], [A]),
                         "single_source")

    def test_buy_one_supplier_verified_without_lead_time(self):
        self.assertEqual(verdict_of("buy", "verified", [A], []),
                         "single_source_no_lead_time")

    def test_buy_one_supplier_unverified_is_not_single_source(self):
        # An unconfirmed list of one may really be a list of two.
        self.assertEqual(verdict_of("buy", "unverified", [A], [A]),
                         "supplier_list_unknown")

    # ----------------------------------------------------------- buy / many --
    def test_buy_two_suppliers_both_quotable(self):
        self.assertEqual(verdict_of("buy", "verified", [A, B], [A, B]),
                         "multi_source")

    def test_buy_two_suppliers_only_one_quotable(self):
        self.assertEqual(verdict_of("buy", "verified", [A, B], [A]),
                         "hidden_single_source")

    def test_buy_two_suppliers_none_quotable(self):
        self.assertEqual(verdict_of("buy", "verified", [A, B], []),
                         "multi_source_no_lead_times")

    def test_buy_three_suppliers_only_one_quotable_is_still_hidden(self):
        self.assertEqual(verdict_of("buy", "verified", [A, B, C], [B]),
                         "hidden_single_source")

    # ---------------------------------------------------------------- make --
    def test_make_with_no_suppliers_is_believed(self):
        # Nothing in the data contradicts the flag, so the flag stands.
        self.assertEqual(verdict_of("make", "verified", [], []),
                         "made_in_house")

    def test_make_with_one_supplier_takes_no_side(self):
        # Stale flag reads single_source; genuine dual mode reads multi_source.
        self.assertEqual(verdict_of("make", "verified", [A], [A]),
                         "readings_disagree")

    def test_make_with_two_quotable_suppliers_agrees_on_multi_source(self):
        # Stale flag: two sources. Dual mode: three. Both are multi_source.
        self.assertEqual(verdict_of("make", "verified", [A, B], [A, B]),
                         "multi_source")

    def test_make_with_two_suppliers_and_no_lead_times_disagrees(self):
        # Stale flag reads multi_source_no_lead_times; dual mode counts in-house
        # as the one quotable source and reads hidden_single_source. The
        # disagreement is NOT confined to make-with-exactly-one-supplier.
        self.assertEqual(verdict_of("make", "verified", [A, B], []),
                         "readings_disagree")


class TestAutonomyIsPerFinding(unittest.TestCase):

    def test_an_unambiguous_part_executes(self):
        finding = identify("SEA-P-0001", "buy", "verified", [A, B], [A, B])
        self.assertEqual(finding.autonomy, gov.EXECUTES)
        self.assertEqual(finding.confidence.value, 1.0)
        self.assertTrue(finding.confidence.reasons)

    def test_a_merge_that_changes_the_verdict_only_recommends(self):
        # Merged: one supplier, one lead time -> single_source. Separate: two of
        # each -> multi_source. The answer turns on the merge, so a person calls
        # it. This is the PHANTOM SINGLE SOURCE case.
        names = ["Marrow Corporation", "Yarrow Corporation"]
        finding = identify("SEA-P-0248", "buy", "verified", names, names,
                           threshold=0.90)
        self.assertEqual(finding.autonomy, gov.RECOMMENDS)
        self.assertEqual(finding.verdict, "readings_disagree")
        self.assertEqual(finding.evidence["verdict_if_merged"], "single_source")
        self.assertEqual(finding.evidence["verdict_if_separate"], "multi_source")
        self.assertIsNone(finding.evidence["resulting_verdict"])
        self.assertTrue(finding.evidence["merge_conflict"])
        self.assertLess(finding.confidence.value, 1.0)

    def test_the_same_part_executes_once_the_merge_falls_below_threshold(self):
        names = ["Marrow Corporation", "Yarrow Corporation"]
        finding = identify("SEA-P-0248", "buy", "verified", names, names,
                           threshold=0.99)
        self.assertEqual(finding.autonomy, gov.EXECUTES)
        self.assertEqual(finding.verdict, "multi_source")

    def test_an_uncertain_merge_that_changes_nothing_still_executes(self):
        # Both names plus a third supplier: merged is two sources, separate is
        # three, and both read multi_source. Uncertainty that cannot move the
        # answer must not spend a reviewer's attention.
        names = ["Marrow Corporation", "Yarrow Corporation", C]
        finding = identify("SEA-P-0002", "buy", "verified", names, names,
                           threshold=0.90)
        self.assertEqual(finding.autonomy, gov.EXECUTES)
        self.assertEqual(finding.verdict, "multi_source")
        self.assertEqual(finding.confidence.value, 1.0)
        self.assertTrue(finding.evidence["uncertain_pairs"],
                        "the uncertain pair must still be recorded even though "
                        "it did not change the outcome")

    def test_a_readings_disagreement_never_executes(self):
        # THE DEFECT THIS TEST EXISTS FOR: both clusterings return
        # readings_disagree, they match, and comparing them alone marks a
        # finding that means "nobody can tell" as decided automatically.
        finding = identify("SEA-P-0027", "make", "verified", [A], [A])
        self.assertEqual(finding.autonomy, gov.RECOMMENDS)
        self.assertEqual(finding.verdict, "readings_disagree")
        self.assertTrue(finding.evidence["readings_conflict"])
        self.assertFalse(finding.evidence["merge_conflict"])
        self.assertEqual(finding.evidence["stale_flag"], "single_source")
        self.assertEqual(finding.evidence["dual_mode"], "multi_source")

    def test_a_readings_disagreement_reports_no_score_it_does_not_have(self):
        # There is no fuzzy match involved, so there is no score to report. 0.5
        # is an even split between two defensible readings, not a measurement.
        finding = identify("SEA-P-0027", "make", "verified", [A], [A])
        self.assertEqual(finding.confidence.value, 0.5)
        self.assertNotIn("score", finding.evidence)


class TestExceptionLane(unittest.TestCase):

    def test_only_undecided_findings_enter_the_lane(self):
        findings = [
            identify("SEA-P-0001", "buy", "verified", [A, B], [A, B]),
            identify("SEA-P-0027", "make", "verified", [A], [A]),
        ]
        lane = exception_lane(findings)
        self.assertEqual([f.subject for f in lane], ["SEA-P-0027"])

    def test_lane_is_ordered_by_the_worst_candidate_reading(self):
        # single_source outranks hidden_single_source outranks multi_source.
        worst = identify("SEA-P-A", "make", "verified", [A], [A])
        milder = identify("SEA-P-B", "make", "verified", [A, B], [])
        lane = exception_lane([milder, worst])
        self.assertEqual([f.subject for f in lane], ["SEA-P-A", "SEA-P-B"])

    def test_readings_disagree_is_not_itself_a_severity(self):
        # It is the absence of a settled exposure level, not a level, so the
        # lane must rank the concrete readings underneath it without raising.
        lane = exception_lane([identify("SEA-P-A", "make", "verified", [A], [A])])
        self.assertEqual(len(lane), 1)


class TestLogging(unittest.TestCase):

    def test_each_outcome_logs_its_own_event_kind(self):
        log = gov.DecisionLog()
        identify("SEA-P-0001", "buy", "verified", [A, B], [A, B], log=log)
        identify("SEA-P-0027", "make", "verified", [A], [A], log=log)
        names = ["Marrow Corporation", "Yarrow Corporation"]
        identify("SEA-P-0248", "buy", "verified", names, names, threshold=0.90,
                 log=log)
        self.assertEqual([e.kind for e in log],
                         [gov.KIND_VERDICT_ASSIGNED,
                          gov.KIND_READINGS_DISAGREE,
                          gov.KIND_MERGE_UNCERTAIN])

    def test_every_logged_event_is_proposed_and_undecided(self):
        log = gov.DecisionLog()
        identify("SEA-P-0001", "buy", "verified", [A, B], [A, B], log=log)
        for event in log:
            self.assertEqual(event.status, gov.STATUS_PROPOSED)
            self.assertEqual(event.decided_by, "",
                            "the agent proposes; nothing reaches a decided "
                            "state without a named person")

    def test_identify_without_a_log_still_returns_a_finding(self):
        self.assertIsNotNone(identify("SEA-P-0001", "buy", "verified", [A], [A]))


class TestIdentifyAll(unittest.TestCase):

    def test_one_finding_per_part_in_sorted_order(self):
        part_master = {"SEA-P-0002": ("buy", "verified"),
                       "SEA-P-0001": ("make", "verified")}
        findings = identify_all(part_master, {"SEA-P-0002": [A]},
                                {"SEA-P-0002": [A]})
        self.assertEqual([f.subject for f in findings],
                         ["SEA-P-0001", "SEA-P-0002"])

    def test_a_part_with_no_supplier_rows_at_all_is_still_answered(self):
        findings = identify_all({"SEA-P-0003": ("buy", "verified")}, {}, {})
        self.assertEqual(findings[0].verdict, "no_qualified_supplier")


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
