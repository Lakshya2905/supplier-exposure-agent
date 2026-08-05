"""The gate's own guarantees.

Everything else in the suite tests the system. This file tests the thing that
decides whether the system ships, which is the one component that cannot be
checked by the component it checks.
"""
import ast
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from codescan import code_of
from src import floors, frozen

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "eval_harness.py"
BUILDER = ROOT / "eval_build.py"
README = ROOT / "README.md"


class TestFloorProvenance(unittest.TestCase):
    """A floor set just below today's number is a description, not a floor."""

    def test_every_floor_states_where_it_came_from(self):
        for floor in floors.FLOORS:
            with self.subTest(floor=floor.name):
                self.assertTrue(floor.derivation.strip())
                self.assertGreater(len(floor.derivation), 80,
                                   "a one-line derivation is a restatement")

    def test_every_floor_says_what_would_make_it_wrong(self):
        # A floor that cannot be argued with cannot be revised honestly either.
        for floor in floors.FLOORS:
            with self.subTest(floor=floor.name):
                self.assertTrue(floor.wrong_if.strip())

    def test_a_floor_without_a_derivation_is_refused_at_construction(self):
        with self.assertRaises(ValueError):
            floors.Floor(name="x", value=0.9, kind=floors.RATIO,
                         derivation="  ", wrong_if="something")

    def test_a_floor_without_a_falsifier_is_refused(self):
        with self.assertRaises(ValueError):
            floors.Floor(name="x", value=0.9, kind=floors.RATIO,
                         derivation="a" * 100, wrong_if="")

    def test_no_derivation_cites_the_current_measurement(self):
        # "we currently score 0.93 so the floor is 0.92" is the failure mode
        # this whole module exists to prevent.
        for floor in floors.FLOORS:
            lowered = floor.derivation.lower()
            with self.subTest(floor=floor.name):
                for phrase in ("currently", "today", "at present",
                               "we score", "measured at"):
                    self.assertNotIn(phrase, lowered)

    def test_the_two_ratio_floors_below_one_are_the_trade_off_pair(self):
        # Everything else is 1.0 or 0, which is a claim that the quantity has
        # no legitimate source of variance rather than an ambition.
        partial = [f.name for f in floors.FLOORS
                   if f.kind == floors.RATIO and f.value < 1.0]
        self.assertEqual(sorted(partial),
                         ["supplier name-match precision",
                          "supplier name-match recall"])

    def test_floor_comparison_is_directional(self):
        self.assertTrue(floors.NAME_MATCH_PRECISION.holds(0.95))
        self.assertFalse(floors.NAME_MATCH_PRECISION.holds(0.9499))
        self.assertTrue(floors.UNIT_VIOLATIONS.holds(0))
        self.assertFalse(floors.UNIT_VIOLATIONS.holds(1))


class TestTheHarnessCannotReachTheGenerator(unittest.TestCase):
    """Eval expectations are never produced by the thing under test."""

    def imported_modules(self, path):
        tree = ast.parse(path.read_text())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
        return names

    def test_the_harness_does_not_import_the_generator(self):
        imported = self.imported_modules(HARNESS)
        for forbidden in ("src.generate_data", "src.synthetic.config",
                          "src.synthetic.build", "eval_build"):
            with self.subTest(module=forbidden):
                self.assertNotIn(forbidden, imported)

    def test_the_harness_does_not_reach_the_generator_transitively(self):
        # Importing the builder for its path constants would have made
        # generate() reachable from the gate, which is the hole rather than the
        # rule. src/frozen.py exists to keep the two apart.
        completed = subprocess.run(
            [sys.executable, "-c",
             "import sys, eval_harness;"
             "print('src.generate_data' in sys.modules)"],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(completed.stdout.strip(), "False", completed.stderr)

    def test_the_path_module_itself_imports_no_generator(self):
        self.assertNotIn("generate", code_of(frozen))

    def test_the_builder_is_the_only_file_allowed_to_generate(self):
        self.assertIn("src.generate_data", self.imported_modules(BUILDER))


class TestManifest(unittest.TestCase):

    def frozen_copy(self, tmp):
        shutil.copytree(ROOT / "evals", tmp / "evals")
        return tmp / "evals"

    def test_the_shipped_manifest_verifies(self):
        ok, problems = frozen.check_manifest(ROOT / "evals")
        self.assertTrue(ok, problems)

    def test_an_edit_to_a_frozen_input_is_detected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self.frozen_copy(Path(tmp))
            target = root / "inputs" / "part_master.csv"
            target.write_text(target.read_text() + "\n# tampered\n")
            import os
            cwd = os.getcwd()
            try:
                os.chdir(tmp)
                ok, problems = frozen.check_manifest(root)
            finally:
                os.chdir(cwd)
            self.assertFalse(ok)
            self.assertTrue(any("edited" in p for p in problems), problems)

    def test_a_missing_manifest_fails_rather_than_passing_vacuously(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ok, problems = frozen.check_manifest(Path(tmp))
            self.assertFalse(ok)
            self.assertTrue(problems)

    def test_the_manifest_states_its_own_limit(self):
        # Surfaced where somebody would rely on it, not only in a plan.
        recorded = json.loads((ROOT / "evals" / "MANIFEST.json").read_text())
        note = recorded["note"].lower()
        self.assertIn("does not prevent", note)
        self.assertIn("branch protection", note)

    def test_the_harness_prints_the_limit(self):
        self.assertIn("does not PREVENT one", frozen.MANIFEST_LIMIT)
        self.assertIn("NOT in place for a purely local repository",
                      frozen.MANIFEST_LIMIT)


class TestFailedFloorReport(unittest.TestCase):
    """The correct response to a missed floor is a finding about the system."""

    def report_for(self, measured, failing=()):
        import eval_harness
        report = eval_harness.Report()
        report.floor(floors.NAME_MATCH_PRECISION, measured, failing)
        return "\n".join(report.lines), report

    def test_a_miss_prints_the_derivation_beside_it(self):
        # "precision 0.93 < 0.95" invites editing 0.95. The derivation invites
        # fixing the normaliser.
        text, _ = self.report_for(0.93)
        self.assertIn("why this floor exists", text)
        self.assertIn("phantom single source", text.lower())

    def test_a_miss_states_what_would_make_the_floor_wrong(self):
        text, _ = self.report_for(0.93)
        self.assertIn("it would be wrong only if", text)

    def test_a_miss_names_the_failing_items_not_just_the_aggregate(self):
        # A number is arguable. A list of specific pairs is a bug report.
        text, _ = self.report_for(0.93, ["merged but distinct: 'A' and 'B'"])
        self.assertIn("failing items", text)
        self.assertIn("'A' and 'B'", text)

    def test_a_miss_never_suggests_a_replacement_value(self):
        # A harness that offers "consider 0.93" has made the decision and left
        # the human to ratify it.
        text, _ = self.report_for(0.93, ["merged but distinct: 'A' and 'B'"])
        lowered = text.lower()
        for phrase in ("consider lowering", "suggest", "recommend setting",
                       "try ", "relax the floor", "new floor"):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, lowered)

    def test_a_miss_is_recorded_as_a_blocking_failure(self):
        _, report = self.report_for(0.93)
        self.assertEqual(report.failures, [floors.NAME_MATCH_PRECISION.name])

    def test_a_pass_prints_no_derivation_and_no_items(self):
        text, report = self.report_for(1.0, ["should not appear"])
        self.assertNotIn("why this floor exists", text)
        self.assertNotIn("should not appear", text)
        self.assertEqual(report.failures, [])

    def test_a_long_failing_list_is_truncated_and_says_so(self):
        text, _ = self.report_for(0.5, [f"pair {i}" for i in range(40)])
        self.assertIn("and 20 more", text)


class TestSnapshotIsNeverCalledAFloor(unittest.TestCase):

    def test_the_snapshot_section_says_it_does_not_gate(self):
        source = HARNESS.read_text()
        self.assertIn("not a floor, not gated", source)

    def test_no_snapshot_count_is_registered_as_a_failure(self):
        code = code_of(__import__("eval_harness").snapshot)
        self.assertNotIn("failures.append", code)

    def test_the_snapshot_names_the_seed_it_belongs_to(self):
        source = HARNESS.read_text()
        self.assertIn("seed 42", source)


class TestNotCoveredIsReported(unittest.TestCase):

    def test_the_deferred_scenario_paths_are_named_in_the_gate_output(self):
        import eval_harness
        names = [name for name, _ in eval_harness.NOT_COVERED]
        self.assertIn("supplier_only concentration", names)
        self.assertIn("the merge-uncertain exception lane", names)

    def test_each_uncovered_path_says_why(self):
        import eval_harness
        for name, reason in eval_harness.NOT_COVERED:
            with self.subTest(path=name):
                self.assertGreater(len(reason), 40)

    def test_it_points_at_the_scenario_document(self):
        self.assertIn("docs/EVAL_SCENARIO.md", HARNESS.read_text())
        self.assertTrue((ROOT / "docs" / "EVAL_SCENARIO.md").exists())


class TestDocIntegrity(unittest.TestCase):
    """The README is the artifact a reader trusts, so it is checked."""

    def xfail_reasons(self):
        reasons = []
        for path in (ROOT / "tests").glob("test_*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                target = getattr(node.func, "attr", "")
                if target != "xfail":
                    continue
                for keyword in node.keywords:
                    if keyword.arg == "reason":
                        reasons.append(ast.literal_eval(keyword.value))
        return reasons

    def test_there_are_exactly_four_known_gaps(self):
        self.assertEqual(len(self.xfail_reasons()), 4)

    def test_the_readme_names_every_xfail_gap(self):
        # The README quotes these verbatim, so without this check the two
        # drift and the README is the one a reader believes.
        readme = README.read_text().lower()
        markers = {
            "tier correlation is unrepresentable": "tier",
            "in-house concentration is not modelled": "in-house",
            "qualification-lead-time field": "qualification lead time",
            "fractional quantities": "fractional quantities",
        }
        for marker, label in markers.items():
            with self.subTest(gap=label):
                self.assertIn(marker, readme)

    def test_every_xfail_gap_appears_in_the_readme_known_gaps_section(self):
        readme = README.read_text()
        section = readme[readme.index("## Known gaps"):readme.index(
            "## How it is verified")]
        self.assertEqual(section.count("**"), 10,
                         "five bold gap headings expected in Known gaps")

    def test_the_readme_says_which_figures_are_gated_and_which_are_not(self):
        # Asserting every count would fail the build whenever the snapshot
        # moved legitimately, which is worse than the drift. So the README
        # states the distinction instead, and this checks the statement exists.
        readme = README.read_text()
        self.assertIn("Which figures are gated", readme)
        self.assertIn("not gated", readme)

    def test_the_readme_records_the_manifest_limit(self):
        readme = README.read_text().lower()
        self.assertIn("does not prevent", readme)
        self.assertIn("branch protection", readme)


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
