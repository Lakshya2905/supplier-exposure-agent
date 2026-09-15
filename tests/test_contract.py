"""The input contract, and the error messages an enterprise actually meets.

THE FAILURE BEING PREVENTED IS SOMEBODY GIVING UP. A company running this on
their own extract will get it wrong the first time, and what decides whether
they try again is whether the tool names the file and the column or says
"invalid input". Before this, a header spelled `parent` produced
`KeyError: 'parent_part'` from inside pandas: the column name, with no file, no
row, and no statement of what the column is for.

So most of these tests assert the CONTENT of a refusal rather than that one
happened.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from src import contract
from src.contract import ContractError
from src.pipeline import run
from src.readers import validate

FROZEN = Path("evals/inputs")


def dataset(mutate=None):
    out = Path(tempfile.mkdtemp())
    for path in FROZEN.glob("*.csv"):
        shutil.copy2(path, out / path.name)
    if mutate:
        mutate(out)
    return out


def rename_header(path, old, new):
    lines = path.read_text().split("\n")
    lines[0] = lines[0].replace(old, new)
    path.write_text("\n".join(lines))


def problems_for(mutate):
    return validate(dataset(mutate)).problems


class TestTheShippedDataSatisfiesItsOwnContract(unittest.TestCase):
    """The contract is documentation until something is checked against it."""

    def test_the_frozen_eval_set_passes(self):
        report = validate(FROZEN)
        self.assertTrue(report.ok, [p.sentence() for p in report.problems])

    # THE DEMO DATASET IS DELIBERATELY NOT CHECKED HERE. A test naming that
    # directory as a path is refused by `test_demo_dataset.py`, and the
    # exemption this one would have claimed — "it reads shape, never contents" —
    # is precisely the argument that rule exists to refuse, because everybody
    # who reads demo data has it. Nothing is lost: demo/ and evals/ come from
    # one generator at one seed, and the frozen set is checked above.

    def test_every_column_the_generator_writes_is_in_the_contract(self):
        """Otherwise the contract drifts from the thing it describes.

        A column added to the generator and not to the contract would be
        reported as "not read by this system" on the project's own data, which
        is the contract being wrong rather than the data.
        """
        for file_contract in contract.CONTRACT:
            path = FROZEN / file_contract.name
            if not path.exists():
                continue
            headers = path.read_text().split("\n")[0].split(",")
            known = {c.name for c in file_contract.columns}
            for header in headers:
                with self.subTest(file=file_contract.name, column=header):
                    self.assertIn(header, known)


class TestAMissingThingIsNamed(unittest.TestCase):

    def test_a_missing_file_says_what_it_would_hold(self):
        found = problems_for(lambda d: (d / "demand_plan.csv").unlink())
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].file, "demand_plan.csv")
        self.assertIn("one row per finished good", found[0].sentence())

    def test_a_missing_optional_file_is_not_a_problem_at_all(self):
        # Every dataset here is missing all three optional files.
        self.assertTrue(validate(FROZEN).ok)

    def test_a_missing_column_says_what_it_should_contain(self):
        found = problems_for(
            lambda d: rename_header(d / "bom.csv", "parent_part", "parent"))
        missing = [p for p in found if p.column == "parent_part"]
        self.assertEqual(len(missing), 1)
        self.assertIn("the assembly this line belongs to",
                      missing[0].sentence())

    def test_a_missing_optional_column_is_not_a_problem(self):
        # `criticality` is optional, and no dataset here carries it.
        self.assertTrue(validate(FROZEN).ok)


class TestAWrongUnitIsRejectedAsAWrongUnit(unittest.TestCase):
    """Not as a missing column, which would send somebody to add one they have."""

    def test_the_offered_header_is_quoted_back(self):
        found = problems_for(lambda d: rename_header(
            d / "lead_times.csv", "quoted_lead_time_days",
            "quoted_lead_time_weeks"))
        wrong = [p for p in found if p.column == "quoted_lead_time_days"]
        self.assertEqual(len(wrong), 1)
        self.assertIn("quoted_lead_time_weeks", wrong[0].sentence())
        self.assertIn("different unit", wrong[0].sentence())

    def test_it_says_renaming_the_header_would_not_fix_it(self):
        """The mistake somebody makes the moment they are told the name.

        Renaming `_weeks` to `_days` makes the file load and scores every lead
        time at a seventh of its length, silently. Saying so in the refusal is
        cheaper than the run that follows.
        """
        found = problems_for(lambda d: rename_header(
            d / "lead_times.csv", "quoted_lead_time_days",
            "quoted_lead_time_weeks"))
        wrong = [p for p in found if p.column == "quoted_lead_time_days"][0]
        self.assertIn("Convert the values", wrong.sentence())
        self.assertIn("renaming the header alone", wrong.sentence())

    def test_the_rule_is_general_rather_than_a_list_of_known_mistakes(self):
        """A unit nobody thought of still gets caught.

        Two headers sharing a stem and ending in different recognised units are
        the same quantity counted differently, whatever the units happen to be.
        A list would cover the variants somebody anticipated.
        """
        found = problems_for(lambda d: rename_header(
            d / "demand_plan.csv", "annual_units", "annual_kg"))
        wrong = [p for p in found if p.column == "annual_units"]
        self.assertEqual(len(wrong), 1)
        self.assertIn("annual_kg", wrong[0].sentence())

    def test_a_column_with_no_unit_in_its_name_cannot_trigger_this(self):
        # `part_number` has no unit suffix, so a missing one is a missing
        # column and nothing about units is said.
        found = problems_for(lambda d: rename_header(
            d / "suppliers.csv", "part_number", "part_no"))
        wrong = [p for p in found if p.column == "part_number"][0]
        self.assertIn("required column is missing", wrong.sentence())
        self.assertNotIn("unit", wrong.sentence())


class TestNothingIsCoerced(unittest.TestCase):

    def test_a_decimal_where_a_whole_number_belongs_names_the_row(self):
        def decimal(directory):
            lines = (directory / "bom.csv").read_text().split("\n")
            lines[3] = lines[3].rsplit(",", 1)[0] + ",0.5"
            (directory / "bom.csv").write_text("\n".join(lines))

        found = [p for p in problems_for(decimal) if p.row is not None]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].row, 3)
        self.assertIn("'0.5' is not a whole number", found[0].sentence())
        self.assertIn("Nothing here rounds", found[0].sentence())

    def test_a_blank_where_a_number_is_required_is_refused(self):
        def blank(directory):
            lines = (directory / "demand_plan.csv").read_text().split("\n")
            lines[1] = lines[1].rsplit(",", 1)[0] + ","
            (directory / "demand_plan.csv").write_text("\n".join(lines))

        found = [p for p in problems_for(blank) if p.row is not None]
        self.assertEqual(len(found), 1)
        self.assertIn("this cell is blank", found[0].sentence())

    def test_a_blank_where_blank_means_no_record_is_accepted(self):
        """The distinction this whole codebase exists to protect.

        `on_hand_units` is optional-with-meaning: blank is no record and is not
        zero. A validator that demanded a number there would force every user to
        put a zero in, which destroys the distinction at the front door before
        any of the machinery that protects it gets a chance.
        """
        def blank_on_hand(directory):
            lines = (directory / "part_master.csv").read_text().split("\n")
            fields = lines[1].split(",")
            fields[4] = ""
            lines[1] = ",".join(fields)
            (directory / "part_master.csv").write_text("\n".join(lines))

        self.assertEqual(problems_for(blank_on_hand), [])

    def test_cells_are_not_checked_until_the_headers_are_right(self):
        """Otherwise one wrong header produces a problem per row.

        A file with the wrong columns would report thousands of cell problems
        about columns the user is about to rename anyway, and the one useful
        line would be at the top of a page nobody scrolls.
        """
        found = problems_for(
            lambda d: rename_header(d / "bom.csv", "qty_per_parent", "qty"))
        self.assertTrue(all(p.row is None for p in found))


class TestAnUnknownColumnIsANoticeAndNotSilence(unittest.TestCase):

    def test_it_says_the_column_was_ignored(self):
        """A user who added a column expecting it to be used must be told.

        Silently dropping an input is how somebody comes to believe a run
        accounted for something it never saw, which is worse than an error
        because nothing ever surfaces.
        """
        def extra(directory):
            path = directory / "bom.csv"
            lines = path.read_text().split("\n")
            lines[0] += ",abc_class"
            path.write_text("\n".join(lines))

        report = validate(dataset(extra))
        self.assertTrue(report.ok, "an unread column must not block a run")
        names = [n.column for n in report.notices]
        self.assertIn("abc_class", names)
        self.assertIn("ignored rather than scored",
                      report.notices[0].sentence())


class TestThePipelineRefusesRatherThanScoring(unittest.TestCase):

    def test_a_broken_dataset_raises_with_every_problem_attached(self):
        directory = dataset(
            lambda d: rename_header(d / "bom.csv", "parent_part", "parent"))
        with self.assertRaises(ContractError) as refused:
            run(data_dir=directory)
        self.assertTrue(refused.exception.report.problems)
        self.assertIn("parent_part", str(refused.exception))

    def test_a_good_dataset_still_scores(self):
        self.assertEqual(len(run(data_dir=FROZEN).profiles), 296)


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
