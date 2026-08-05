"""requirements.txt and pyproject.toml must not drift apart.

Community Cloud installs from requirements.txt and the local install comes from
pyproject.toml, so the two describe the same thing in two places. That is a
duplication the deployment target forces rather than one anybody chose, and the
failure it invites is quiet: a dependency added to pyproject works locally and
in CI, and the deployed app dies on import with a traceback no test produced.
"""
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def declared():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return sorted(data["project"]["dependencies"])


def pinned():
    lines = (ROOT / "requirements.txt").read_text().splitlines()
    return sorted(line.strip() for line in lines
                  if line.strip() and not line.startswith("#"))


class TestRequirementsMatchPyproject(unittest.TestCase):

    def test_the_runtime_dependencies_are_the_same_set(self):
        self.assertEqual(pinned(), declared())

    def test_every_requirement_carries_a_version_floor(self):
        # "Pin dependency versions" is a project rule, and an unpinned
        # dependency on a hosted container resolves to whatever shipped today.
        for requirement in pinned():
            with self.subTest(requirement=requirement):
                self.assertTrue(re.search(r"[><=]=?\d", requirement))

    def test_the_dev_extras_are_not_deployed(self):
        # A deployed container runs the app and never the suite.
        self.assertNotIn("pytest", " ".join(pinned()))

    def test_the_file_says_why_it_exists(self):
        header = (ROOT / "requirements.txt").read_text().lower()
        self.assertIn("community cloud installs from this file", header)


if __name__ == "__main__":  # keep last: classes below an entrypoint never run
    unittest.main()
