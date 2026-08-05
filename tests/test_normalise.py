"""Supplier name normalisation.

Two tiers are tested separately on purpose. Certain merges are a fact about
formatting and must never reach a reviewer; uncertain merges are the only ones
that can, and they must arrive carrying a score.
"""
import unittest

from src.normalise import (ABBREVIATIONS, canonical_key, cluster,
                           cluster_certain_only, cluster_of, match_score)


class TestCanonicalKey(unittest.TestCase):
    """Deterministic, and only the things that are not judgments."""

    def test_case_is_not_a_supplier_difference(self):
        self.assertEqual(canonical_key("ACME CORPORATION"),
                         canonical_key("Acme Corporation"))

    def test_punctuation_is_not_a_supplier_difference(self):
        self.assertEqual(canonical_key("Acme, Inc."), canonical_key("Acme Inc"))

    def test_whitespace_is_not_a_supplier_difference(self):
        self.assertEqual(canonical_key("  Acme   Works "),
                         canonical_key("Acme Works"))

    def test_abbreviations_expand_rather_than_contract(self):
        # Expanding is the safe direction: "Corp" has one expansion, but
        # "Corporation" contracted could collide with an unrelated "Corp".
        self.assertEqual(canonical_key("Braxton Inds"),
                         canonical_key("Braxton Industries"))
        self.assertEqual(canonical_key("Vane Corp"),
                         canonical_key("Vane Corporation"))

    def test_every_abbreviation_in_the_table_actually_expands(self):
        for short, long in ABBREVIATIONS.items():
            with self.subTest(abbreviation=short):
                self.assertEqual(canonical_key(f"Test {short}"),
                                 canonical_key(f"Test {long}"))

    def test_distinct_suppliers_do_not_share_a_key(self):
        self.assertNotEqual(canonical_key("Marrow Corporation"),
                            canonical_key("Yarrow Corporation"))

    def test_none_and_blank_are_the_empty_key_not_an_error(self):
        self.assertEqual(canonical_key(None), "")
        self.assertEqual(canonical_key("   "), "")

    def test_is_deterministic_across_calls(self):
        first = canonical_key("Acme, Inc.")
        for _ in range(5):
            self.assertEqual(canonical_key("Acme, Inc."), first)


class TestMatchScore(unittest.TestCase):

    def test_identical_canonical_keys_score_exactly_one(self):
        self.assertEqual(match_score("ACME CORP", "Acme Corporation"), 1.0)

    def test_near_miss_scores_below_one(self):
        score = match_score("Marrow Corporation", "Yarrow Corporation")
        self.assertLess(score, 1.0)
        self.assertGreater(score, 0.9)

    def test_unrelated_names_score_low(self):
        self.assertLess(match_score("Acme Works", "Zenith Industries"), 0.6)

    def test_is_symmetric(self):
        self.assertEqual(match_score("Acme Corp", "Acme Cxrp"),
                         match_score("Acme Cxrp", "Acme Corp"))


class TestCluster(unittest.TestCase):

    def test_certain_merges_are_applied_and_reported_as_certain(self):
        clusters, uncertain = cluster(["ACME CORP", "Acme Corporation"], 0.95)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(uncertain, [],
                         "a formatting difference is not a judgment and must "
                         "never reach a reviewer")

    def test_uncertain_merge_is_applied_and_carries_its_score(self):
        clusters, uncertain = cluster(
            ["Marrow Corporation", "Yarrow Corporation"], 0.90)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(uncertain), 1)
        left, right, score = uncertain[0]
        self.assertEqual({left, right},
                         {"Marrow Corporation", "Yarrow Corporation"})
        self.assertGreaterEqual(score, 0.90)
        self.assertLess(score, 1.0)

    def test_below_threshold_names_stay_apart(self):
        clusters, uncertain = cluster(
            ["Marrow Corporation", "Yarrow Corporation"], 0.99)
        self.assertEqual(len(clusters), 2)
        self.assertEqual(uncertain, [])

    def test_certain_only_withholds_uncertain_merges_but_keeps_certain_ones(self):
        names = ["ACME CORP", "Acme Corporation", "Marrow Corporation",
                 "Yarrow Corporation"]
        merged, _ = cluster(names, 0.90)
        withheld = cluster_certain_only(names)
        self.assertEqual(len(merged), 2)
        self.assertEqual(len(withheld), 3,
                         "withholding uncertain merges must not also undo the "
                         "formatting collapse, or every part goes to review")

    def test_cluster_of_returns_a_singleton_for_an_unseen_name(self):
        clusters = cluster_certain_only(["Acme Corp"])
        self.assertEqual(cluster_of(clusters, "Nowhere Ltd"),
                         frozenset({"Nowhere Ltd"}))

    def test_clustering_is_order_independent(self):
        names = ["Acme Corporation", "ACME CORP", "Zenith Works"]
        forward, _ = cluster(names, 0.95)
        backward, _ = cluster(list(reversed(names)), 0.95)
        self.assertEqual(set(forward), set(backward))


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
