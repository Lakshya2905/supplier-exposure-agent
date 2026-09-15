"""What binds on a part, and the comparison it must never make.

THE RISK THIS MODULE CARRIES is not that it computes the wrong answer. It is
that it computes a composite while looking like prose. "Which dimension is worst
for this part" is a comparison between days and finished-good units, and a
function that answered it would be the index this project refuses, hidden inside
a superlative where no unit test would look for arithmetic.

So the tests below are mostly about what the module does NOT do: it reads one
dimension at a time, it compares states rather than magnitudes, it returns every
dimension that qualifies rather than picking one, and a dimension with no
threshold-free worst value is named as having none rather than left out.
"""
import unittest
from fractions import Fraction

from codescan import code_of
from src import binding
from src import governance as gov
from src import scoring
from src.concentration import ConcentrationScore
from src.demand import USAGE_KNOWN, Usage
from src.scoring import (ExposureProfile, blast_radius, buffer_cover,
                         portability, resource_days, wait_out_days)

TIMED = {"alternate_source_days": 10, "tooling_lead_time_days": 20,
         "engineering_transfer_days": 30, "first_article_days": 40,
         "qualification_test_days": 50, "ramp_to_rate_days": 60,
         "qualification_cycles": 1}


# An explicit sentinel, because `stages or TIMED` reads `{}` as "unspecified"
# and silently hands back a fully timed chain. The first version of this helper
# did exactly that and the untimed-chain test passed against timed data.
_UNSPECIFIED = object()


def profile(verdict="single_source", lead_times=((30, 45),), on_hand=100,
            tooling="company", usage=1000, stages=_UNSPECIFIED,
            cluster_size=None):
    use = Usage("P", Fraction(usage), USAGE_KNOWN)
    built = ExposureProfile(
        part_number="P",
        wait_out_days=wait_out_days("P", verdict, lead_times),
        resource_days=resource_days(
            "P", tooling, TIMED if stages is _UNSPECIFIED else stages),
        blast_radius=blast_radius("P", (), use),
        buffer_cover=buffer_cover("P", on_hand, use),
        portability=portability("P", tooling))
    if cluster_size is None:
        return built
    import dataclasses
    return dataclasses.replace(built, concentration=ConcentrationScore(
        part_number="P", dimension=scoring.CONCENTRATION, value=cluster_size,
        unit=scoring.PARTS, completeness=scoring.KNOWN,
        reasons=("hand-written for this test",)))


class TestItComparesStatesAndNeverMagnitudes(unittest.TestCase):

    def test_no_dimension_is_weighed_against_another(self):
        """The whole point, asserted on the source.

        Each test in the table takes ONE score and answers about that score. A
        comparison between two dimensions could only be written by a function
        holding both, so the absence of the vocabulary for it is the guard.
        """
        code = code_of(binding, functions_only=True)
        for forbidden in ("weight", "composite", "score_total", "normalise",
                          "normalized", "severity", "rank", "worst_of",
                          "max(", "sorted("):
            with self.subTest(word=forbidden):
                self.assertNotIn(forbidden, code)

    def test_a_large_blast_radius_binds_on_nothing(self):
        """The test that would fail if this quietly became a ranking.

        Twelve thousand blocked units is the biggest number on the row by a
        factor of a hundred, and it binds on nothing, because there is no worst
        value for it until somebody states a threshold. A function picking "the
        worst dimension" would pick this one every time.
        """
        big = profile(usage=12000, on_hand=500, tooling="company")
        self.assertEqual(
            [entry["dimension"] for entry in binding.binds(big)], [])
        self.assertIn(scoring.BLAST_RADIUS, binding.NO_TERMINAL_STATE)

    def test_every_dimension_is_either_terminal_or_declared_not_to_be(self):
        # A dimension added later cannot acquire neither, which would make it
        # invisible here without anybody deciding that.
        for dimension in scoring.DIMENSIONS:
            with self.subTest(dimension=dimension):
                self.assertTrue(dimension in binding.BINDS
                                or dimension in binding.NO_TERMINAL_STATE)

    def test_it_returns_every_qualifying_dimension_rather_than_picking_one(self):
        both = profile(verdict="no_qualified_supplier", lead_times=(),
                       on_hand=0, tooling="supplier")
        found = [entry["dimension"] for entry in binding.binds(both)]
        self.assertIn(scoring.WAIT_OUT_DAYS, found)
        self.assertIn(scoring.BUFFER_COVER, found)
        self.assertIn(scoring.PORTABILITY, found)
        self.assertGreater(len(found), 1,
                           "picking one would need the comparison this module "
                           "exists to avoid")

    def test_the_order_is_declaration_order_and_carries_no_meaning(self):
        everything = profile(verdict="no_qualified_supplier", lead_times=(),
                             on_hand=0, tooling="supplier", cluster_size=9)
        found = [entry["dimension"] for entry in binding.binds(everything)]
        expected = [d for d in scoring.DIMENSIONS if d in found]
        self.assertEqual(found, expected)


class TestTheTerminalStates(unittest.TestCase):

    def test_an_empty_supplier_list_binds_on_waiting(self):
        found = binding.binds(profile(verdict="no_qualified_supplier",
                                      lead_times=()))
        self.assertIn(scoring.WAIT_OUT_DAYS,
                      [entry["dimension"] for entry in found])
        self.assertIn("nobody to wait on", found[0]["sentence"])

    def test_a_counted_empty_stock_binds(self):
        found = [e["dimension"] for e in binding.binds(profile(on_hand=0))]
        self.assertIn(scoring.BUFFER_COVER, found)

    def test_a_missing_on_hand_record_does_not_bind_and_blocks_instead(self):
        """The collapse this project exists to prevent, at its worst site.

        A blank on-hand record is not zero cover. Reading it as zero here would
        put "stock is counted and empty" at the top of a part where nobody has
        counted anything, which is a headline asserting a fact that was never
        recorded.
        """
        missing = profile(on_hand=None)
        self.assertNotIn(scoring.BUFFER_COVER,
                         [e["dimension"] for e in binding.binds(missing)])
        self.assertIn(scoring.BUFFER_COVER,
                      [e["dimension"] for e in binding.blocks(missing)])

    def test_supplier_owned_tooling_binds_and_company_owned_does_not(self):
        self.assertIn(scoring.PORTABILITY, [
            e["dimension"] for e in binding.binds(profile(tooling="supplier"))])
        self.assertNotIn(scoring.PORTABILITY, [
            e["dimension"] for e in binding.binds(profile(tooling="company"))])

    def test_a_cluster_of_one_is_correlated_with_nothing(self):
        # The value is a CLUSTER SIZE, not a count of others. `> 0` here would
        # mark every part in the dataset as bound by concentration.
        self.assertEqual(binding.binds(profile(cluster_size=1)), ())
        self.assertIn(scoring.CONCENTRATION, [
            e["dimension"] for e in binding.binds(profile(cluster_size=2))])

    def test_concentration_binds_even_though_it_never_executes(self):
        """Autonomy and bindingness are different questions.

        Concentration is `recommends` permanently because grouping is a
        judgment. That is about who may assert it, not about whether it is what
        is hurting this part, and gating the finding on the confirmation would
        make the review queue a gate on the analysis.
        """
        found = binding.binds(profile(cluster_size=9))
        entry = next(e for e in found
                     if e["dimension"] == scoring.CONCENTRATION)
        self.assertEqual(entry["autonomy"], gov.RECOMMENDS)


class TestBindsAndBlocksStaySeparate(unittest.TestCase):

    def test_an_abstention_blocks_and_never_binds(self):
        unknown = profile(tooling="", stages={})
        blocking = [entry["dimension"] for entry in binding.blocks(unknown)]
        binds = [entry["dimension"] for entry in binding.binds(unknown)]
        self.assertIn(scoring.PORTABILITY, blocking)
        self.assertNotIn(scoring.PORTABILITY, binds)

    def test_an_untimed_chain_blocks(self):
        found = binding.blocks(profile(stages={}))
        self.assertIn(scoring.RESOURCE_DAYS,
                      [entry["dimension"] for entry in found])

    def test_a_part_with_neither_says_so_rather_than_promoting_a_number(self):
        """The empty case is an answer, not a gap in one.

        This is where an index would be irresistible: everything is known,
        nothing is terminal, and the screen looks empty. Naming the biggest
        number to fill it is the composite arriving through the back door.
        """
        quiet = profile(on_hand=500, tooling="company", usage=10,
                        cluster_size=1)
        found = binding.summary(quiet)
        self.assertEqual(found["binds"], ())
        self.assertEqual(found["blocks"], ())
        self.assertTrue(found["nothing_binds"])

    def test_every_sentence_says_what_it_means_without_a_number(self):
        # The sentences are the table's and are fixed prose, so a reader is
        # never shown a figure here that a threshold would be needed to judge.
        for _test, sentence in binding.BINDS.values():
            with self.subTest(sentence=sentence[:30]):
                self.assertFalse(any(char.isdigit() for char in sentence))


class TestLogging(unittest.TestCase):

    def test_it_logs_structure_and_the_reasons_come_from_the_table(self):
        log = gov.DecisionLog()
        binding.log_binding(log, profile(tooling="supplier"))
        event = list(log)[0]
        self.assertEqual(event.evidence["binds"], [scoring.PORTABILITY])
        self.assertTrue(event.evidence["reasons"])

    def test_a_part_with_nothing_binding_still_logs_a_reason(self):
        log = gov.DecisionLog()
        binding.log_binding(log, profile(on_hand=500, tooling="company",
                                         usage=10, cluster_size=1))
        self.assertIn("nothing about this part",
                      list(log)[0].evidence["reasons"][0])


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
