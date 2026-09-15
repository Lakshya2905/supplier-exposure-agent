"""The two folders an enterprise starts from, kept honest by the contract.

THE FAILURE BEING PREVENTED IS A TEMPLATE THAT HAS GONE STALE. Somebody edits
the schema, the validator follows, and the folder a new user copies still has
last quarter's headers. They then meet a refusal about a file this repository
gave them, which is worse than no template at all.

So the headers are asserted against `contract.py` rather than against a
remembered list, and the worked example is scored rather than admired.
"""
import unittest
from pathlib import Path

from src import contract
from src.pipeline import run
from src.readers import validate

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "template"
SAMPLE = ROOT / "sample"


class TestTheTemplateMatchesTheContract(unittest.TestCase):

    def test_every_file_in_the_contract_has_a_template(self):
        for file_contract in contract.CONTRACT:
            with self.subTest(file=file_contract.name):
                self.assertTrue((TEMPLATE / file_contract.name).exists())

    def test_every_template_carries_exactly_the_contract_headers(self):
        """EXACTLY: not a subset, and in order.

        A template missing a column teaches somebody to leave it out; one
        carrying a column the contract does not know teaches them to fill in a
        field nothing reads, which the validator would then report as ignored.
        """
        for file_contract in contract.CONTRACT:
            path = TEMPLATE / file_contract.name
            headers = path.read_text().strip().split("\n")[0].split(",")
            with self.subTest(file=file_contract.name):
                self.assertEqual(headers,
                                 [c.name for c in file_contract.columns])

    def test_the_templates_carry_headers_and_no_rows(self):
        # A template with a row in it is a sample, and somebody will ship it.
        for file_contract in contract.CONTRACT:
            path = TEMPLATE / file_contract.name
            lines = [line for line in path.read_text().split("\n")
                     if line.strip() and not line.startswith("#")]
            with self.subTest(file=file_contract.name):
                self.assertEqual(len(lines), 1)

    def test_the_template_readme_says_which_files_are_optional(self):
        text = (TEMPLATE / "README.md").read_text()
        for name in contract.OPTIONAL_FILES:
            with self.subTest(file=name):
                self.assertIn(name, text)


class TestTheSampleIsAWorkedExampleAndNotAnOracle(unittest.TestCase):

    def test_it_satisfies_the_contract_it_is_an_example_of(self):
        report = validate(SAMPLE)
        self.assertTrue(report.ok, [p.sentence() for p in report.problems])
        self.assertEqual(report.notices, [])

    def test_it_scores(self):
        result = run(data_dir=SAMPLE)
        self.assertEqual(len(result.profiles), 7)

    def test_it_fills_in_all_three_optional_files(self):
        """The only dataset here that does, which is the point of it.

        Nothing this repository generates carries a resourcing duration, an
        order book or a sub-tier source, so without this folder those three
        features are only ever seen abstaining.
        """
        for name in contract.OPTIONAL_FILES:
            with self.subTest(file=name):
                self.assertTrue((SAMPLE / name).exists())

    def test_every_case_its_readme_claims_actually_fires(self):
        """The README is the artifact a new user trusts, so it is checked.

        A worked example whose labels have drifted from its data teaches the
        wrong lesson with this project's own name on it.
        """
        result = run(data_dir=SAMPLE)
        verdicts = result.verdicts
        self.assertEqual(verdicts["SAMPLE-P-02"], "hidden_single_source")
        self.assertEqual(verdicts["SAMPLE-P-03"], "no_qualified_supplier")
        self.assertEqual(verdicts["SAMPLE-P-04"], "made_in_house")

        # The pair the whole tool is built around: a blank on-hand record and a
        # counted zero, side by side, reaching opposite states.
        blank = result.profiles["SAMPLE-P-05"].buffer_cover
        counted = result.profiles["SAMPLE-P-06"].buffer_cover
        self.assertEqual(blank.completeness, "cannot_tell")
        self.assertEqual(counted.completeness, "known")
        self.assertEqual(counted.value, 0)

        # A settled resourcing chain and a bounded one.
        self.assertEqual(
            result.profiles["SAMPLE-P-05"].resource_days.completeness, "known")
        self.assertEqual(
            result.profiles["SAMPLE-P-01"].resource_days.completeness,
            "lower_bound")

        # An order book covering one finished good of two.
        self.assertEqual(
            result.profiles["SAMPLE-P-02"].committed_at_risk.completeness,
            "lower_bound")

    def test_the_sub_tier_correlation_crosses_supplier_and_region(self):
        """The reason the sub-tier column exists, demonstrated on data.

        Two of these three parts share a supplier and a region. The third shares
        neither, and all three depend on one mill. If the tier cluster ever
        stops containing the third, this example has stopped showing the thing
        it is here to show.
        """
        result = run(data_dir=SAMPLE)
        tier = [c for c in result.report.clusters if c.basis == "tier"
                and c.is_concentrated]
        self.assertEqual(len(tier), 1)
        self.assertEqual(set(tier[0].members),
                         {"SAMPLE-P-01", "SAMPLE-P-05", "SAMPLE-P-06"})
        supplier = [c for c in result.report.clusters
                    if c.basis == "supplier" and c.is_concentrated]
        self.assertNotIn("SAMPLE-P-06", supplier[0].members)

    def test_a_supplier_spelled_two_ways_is_reconciled_and_says_so(self):
        result = run(data_dir=SAMPLE)
        evidence = result.evidence["SAMPLE-P-07"]
        self.assertTrue(evidence.transformations)
        self.assertEqual(evidence.transformations[0].original, "Calder Corp")

    def test_scoping_it_to_one_tier_leaves_the_rest_stated(self):
        result = run(data_dir=SAMPLE, criticality=["A"])
        self.assertTrue(result.scope.is_scoped)
        self.assertEqual(set(result.scope.parts_in_scope),
                         {"SAMPLE-P-01", "SAMPLE-P-02"})
        self.assertEqual(len(result.scope.parts_excluded), 5)

    def test_nothing_that_judges_correctness_grades_against_it(self):
        """A worked example must not become an oracle, as `demo/` must not.

        It carries no answer key, and the harness does not name it. Without
        that, the dataset that exists to be read is also the one correctness is
        judged against, and nobody notices because everything still passes.
        """
        self.assertEqual(list(SAMPLE.glob("*.json")), [])
        self.assertNotIn("sample", (ROOT / "eval_harness.py").read_text())


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
