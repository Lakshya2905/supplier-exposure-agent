"""Criticality tiering: a supplied classification that must never become a score.

THE RISK IS NOT THAT THE FILTER IS WRONG. It is that a tier quietly acquires the
powers of a measure: ordered A above B, used to rank a list, or worst, DERIVED
from the measures, at which point it is a weighted sum of them wearing a letter
and attributed to nobody. Most of what is asserted below is that none of that
happened.
"""
import unittest

from codescan import code_of
from src import criticality as crit
from src import scoring
from src.pipeline import run
from src.readers import read_part_master

PARTS = {
    "A-1": {"criticality": "A"},
    "A-2": {"criticality": "A"},
    "B-1": {"criticality": "B"},
    "BLANK": {"criticality": ""},
    "ABSENT": {},                       # a part master that predates the column
}


class TestItIsReadAndNeverDerived(unittest.TestCase):

    def test_nothing_here_computes_a_tier_from_a_measure(self):
        """The defect this module exists to not be.

        A criticality inferred from blast radius or spend is a composite: it
        combines measures in different units and publishes the result as a
        letter. The vocabulary for doing it is absent, and the absence is the
        guard.
        """
        code = code_of(crit, functions_only=True)
        for forbidden in ("blast_radius", "buffer_cover", "annual_spend",
                          "weight", "score", "rank", "threshold", "percentile"):
            with self.subTest(word=forbidden):
                self.assertNotIn(forbidden, code)

    def test_no_dimension_has_ever_heard_of_criticality(self):
        # `sourcing_list_status` gates the verdict only and `annual_spend_usd`
        # is display-only. This joins that list, and the list is only worth
        # anything if somebody checks it.
        self.assertNotIn("criticality", code_of(scoring, functions_only=True))
        self.assertNotIn("criticality", [d for d in scoring.DIMENSIONS])


class TestAbsenceIsNotATier(unittest.TestCase):

    def test_a_blank_cell_and_a_missing_column_both_read_unclassified(self):
        labels = crit.labels_of(PARTS)
        self.assertEqual(labels["BLANK"], crit.UNCLASSIFIED)
        self.assertEqual(labels["ABSENT"], crit.UNCLASSIFIED)

    def test_unclassified_stays_in_scope_by_default(self):
        """The one default in this module, and it is the inclusive one.

        Dropping parts nobody has classified would shrink the assessment to the
        part of the BOM somebody has already curated, and report a clean result
        for the rest.
        """
        scope = crit.scope_for(PARTS)
        self.assertIn("ABSENT", scope.parts_in_scope)
        self.assertIn("BLANK", scope.parts_in_scope)
        self.assertFalse(scope.is_scoped)

    def test_unclassified_is_not_offered_as_a_level(self):
        # It appears in the counts, because a reader needs to know how many
        # parts are in it, and it is not a tier.
        scope = crit.scope_for(PARTS)
        self.assertEqual(scope.counts[crit.UNCLASSIFIED], 2)


class TestScopeIsASetAndNotACutOff(unittest.TestCase):

    def test_scoping_takes_the_labels_asked_for_and_no_others(self):
        scope = crit.scope_for(PARTS, include=["A"])
        self.assertEqual(scope.parts_in_scope, ("A-1", "A-2"))
        self.assertEqual(scope.parts_excluded, ("ABSENT", "B-1", "BLANK"))

    def test_two_labels_can_be_included_without_implying_an_order(self):
        # A and C without B. A cut-off cannot express this, which is why the
        # input is a set: the ordering of a company's tiers is theirs, and this
        # module is never told it.
        scope = crit.scope_for(dict(PARTS, **{"C-1": {"criticality": "C"}}),
                               include=["A", "C"])
        self.assertIn("C-1", scope.parts_in_scope)
        self.assertNotIn("B-1", scope.parts_in_scope)

    def test_a_label_that_appears_nowhere_is_kept_rather_than_dropped(self):
        # So a caller can see they asked for something this extract does not
        # contain, instead of getting an empty result with no explanation.
        scope = crit.scope_for(PARTS, include=["Z"])
        self.assertIn("Z", scope.included)
        self.assertEqual(scope.parts_in_scope, ())

    def test_the_same_request_gives_the_same_scope_whatever_the_order(self):
        one = crit.scope_for(PARTS, include=["B", "A"])
        two = crit.scope_for(PARTS, include=["A", "B", "A"])
        self.assertEqual(one, two)


class TestExcludingIsNotAssessing(unittest.TestCase):

    def test_what_was_left_out_is_counted_and_named(self):
        scope = crit.scope_for(PARTS, include=["A"])
        self.assertEqual(len(scope.parts_excluded), 3)
        self.assertEqual(scope.excluded_labels(), ("B", crit.UNCLASSIFIED))

    def test_the_sentence_says_they_were_not_examined(self):
        """The distinction a coverage panel exists to make.

        "Not assessed" and "assessed and fine" look identical on a screen that
        only lists findings, and a scoped run is exactly where somebody will
        read the absence of a finding as good news.
        """
        sentence = crit.describe(crit.scope_for(PARTS, include=["A"]))
        self.assertIn("not examined", sentence)
        self.assertIn("3 parts", sentence)

    def test_an_unscoped_run_says_it_assessed_everything(self):
        sentence = crit.describe(crit.scope_for(PARTS))
        self.assertIn("Every part", sentence)

    def test_the_sentence_is_neutral_rather_than_a_warning(self):
        sentence = crit.describe(crit.scope_for(PARTS, include=["A"])).lower()
        for alarm in ("error", "failed", "warning", "missing", "should"):
            with self.subTest(word=alarm):
                self.assertNotIn(alarm, sentence)


class TestThroughThePipeline(unittest.TestCase):

    def test_a_part_master_with_no_criticality_column_still_reads(self):
        parts = read_part_master("evals/inputs/part_master.csv")
        self.assertTrue(all(record["criticality"] == ""
                            for record in parts.values()))

    def test_an_unscoped_run_assesses_every_scoreable_part(self):
        result = run(data_dir="evals/inputs")
        self.assertFalse(result.scope.is_scoped)
        self.assertEqual(len(result.scope.parts_in_scope),
                         len(result.profiles))

    def test_the_scope_counts_only_parts_that_could_be_scored(self):
        """A finished good is never scored and the scope must not blame itself.

        Counting the four finished goods as "not assessed because of the scope"
        would attribute an exclusion to a decision that did not make it.
        """
        result = run(data_dir="evals/inputs")
        self.assertEqual(sum(result.scope.counts.values()),
                         len(result.profiles))

    def test_scoping_filters_what_is_presented_and_not_what_is_correlated(self):
        """Correlation is a property of the world, not of the scope.

        Two parts share a supplier whether or not somebody scoped a run to one
        of them. Rebuilding clusters from the scoped set would understate shared
        exposure in proportion to how tightly a reviewer scoped, and
        understating exposure is the error direction this system refuses.
        """
        everything = run(data_dir="evals/inputs")
        scoped = run(data_dir="evals/inputs", criticality=["nothing-matches"])
        self.assertEqual(len(scoped.profiles), 0)
        self.assertEqual(len(scoped.report.clusters),
                         len(everything.report.clusters))


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
