"""The demo dataset must never become an oracle.

THESE TESTS CHECK THE SHAPE OF `demo/`, NEVER ITS CONTENTS. That distinction is
the point rather than a technicality: the rule is that no test reads the demo
data, so a test that opened a demo CSV to verify it would be the first breach of
the thing it was written to protect. What is checked here is which files exist,
which files must not, and who is allowed to reference the directory at all.

The failure being prevented is a slow one. A committed dataset sitting next to
the code is convenient, and the first time somebody needs a fixture in a hurry it
is right there. From then on the dataset that exists to be looked at is also the
dataset correctness is judged against, and nobody notices because everything
still passes.
"""
import ast
import unittest
from pathlib import Path

from src import pipeline

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
HARNESS = ROOT / "eval_harness.py"
TESTS = ROOT / "tests"


class TestDemoDatasetShape(unittest.TestCase):

    def test_the_demo_dataset_is_committed(self):
        # A cold container cannot regenerate during its first page load, and
        # Community Cloud sleeps idle apps, so without this a visitor arriving
        # at a sleeping app finds a blank screen.
        for name in ("bom.csv", "part_master.csv", "suppliers.csv",
                     "lead_times.csv", "demand_plan.csv"):
            with self.subTest(file=name):
                self.assertTrue((DEMO / name).exists())

    def test_the_demo_dataset_carries_no_answer_key(self):
        # Without an answer key it cannot become an oracle even by accident.
        # Correctness is measured against evals/, which is frozen and gated.
        self.assertFalse((DEMO / "answer_key.json").exists())
        self.assertEqual(list(DEMO.glob("*.json")), [])

    def test_the_demo_dataset_states_its_own_rule(self):
        # Where somebody finds the files, not only in the top-level README.
        rule = (DEMO / "README.md").read_text().lower()
        self.assertIn("display only", rule)
        self.assertIn("never read by the eval harness or by any test", rule)


class TestNothingThatJudgesCorrectnessReadsIt(unittest.TestCase):

    def test_the_harness_never_references_the_demo_directory(self):
        self.assertNotIn("demo", HARNESS.read_text())

    def test_no_test_names_the_demo_directory_as_a_path(self):
        """A PATH, not the word.

        The corrections log records this exact hazard twice: a system that
        refuses concepts by name contains those names in its refusals, so a
        scan has to tell a guard from a breach. `test_governance_render.py`
        says "in any demo" in prose about the renderer, which is a mention and
        not a read. So the check walks the syntax tree for string constants
        that are the directory or live under it, which prose cannot produce.
        """
        for path in sorted(TESTS.glob("test_*.py")):
            if path.name == Path(__file__).name:
                continue
            paths = [node.value for node in ast.walk(ast.parse(path.read_text()))
                     if isinstance(node, ast.Constant)
                     and isinstance(node.value, str)
                     and (node.value == "demo"
                          or node.value.startswith("demo/"))]
            with self.subTest(test=path.name):
                self.assertEqual(paths, [])

    def test_this_file_opens_no_demo_data(self):
        """Enforced on itself, and the line is between naming and opening.

        `(DEMO / "bom.csv").exists()` names a file to check it is there, which
        is shape. `.read_text()` on the same path is content. So the walk looks
        for READ CALLS whose receiver is a demo path, and the only one it may
        find is the README that states the rule.
        """
        reads = {"read_text", "read_bytes", "read_csv", "open"}
        offenders = []
        for node in ast.walk(ast.parse(Path(__file__).read_text())):
            if not isinstance(node, ast.Call):
                continue
            if getattr(node.func, "attr", "") not in reads:
                continue
            receiver = ast.unparse(getattr(node.func, "value", node.func))
            if "DEMO" in receiver and "README" not in receiver:
                offenders.append(receiver)
        self.assertEqual(offenders, [], "shape, never content")


class TestTheResolverKeepsDemoOutOfEveryTestPath(unittest.TestCase):

    def test_data_is_preferred_when_present(self):
        # Under test and in CI data/ always exists, so the fallback never fires
        # and demo/ stays out of every correctness path.
        self.assertTrue((ROOT / "data" / "bom.csv").exists(),
                        "the suite generates data/ before running")
        self.assertEqual(pipeline.default_data_dir(), pipeline.WORKING_DIR)

    def test_the_fallback_is_the_demo_directory(self):
        self.assertEqual(pipeline.DEMO_DIR, Path("demo"))

    def test_the_resolver_is_the_only_thing_choosing(self):
        # The app calls the resolver rather than naming a directory, so there
        # is one place the choice is made and one place to check it.
        app = (ROOT / "review_app.py").read_text()
        self.assertIn("default_data_dir()", app)
        self.assertNotIn('run(data_dir="', app)

    def test_the_harness_passes_its_own_directory_explicitly(self):
        # The gate reads evals/inputs and never the resolver, so a missing
        # data/ can never silently redirect the gate at the demo set.
        self.assertIn("run(data_dir=INPUTS)", HARNESS.read_text())


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
