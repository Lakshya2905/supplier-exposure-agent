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


def copied_into_the_image():
    """The top-level names the Dockerfile puts in /app."""
    names = set()
    for line in (ROOT / "Dockerfile").read_text().splitlines():
        match = re.match(r"COPY\s+(\S+)", line.strip())
        if match:
            names.add(match.group(1).rstrip("/").split("/")[0])
    return names


class TestTheImageShipsWhatTheApiReads(unittest.TestCase):
    """The same quiet failure as above, one layer over: files instead of
    dependencies.

    Endpoints read `assets/` and `evals/` from the working directory at request
    time. Locally and in CI the whole repository is the working directory, so
    every one of those reads succeeds and nothing in the suite runs against the
    image. `assets/` was left out of the Dockerfile and the gate stayed green:
    the map endpoint 404d on every request a deployed page made, and the page
    fell back to plotly's built-in India, which follows a different territorial
    convention. That is the exact substitution `assets/README.md` exists to
    prevent, and the only thing that would have caught it was a deploy.
    """

    def test_every_path_the_api_reads_from_disk_is_in_the_image(self):
        source = (ROOT / "src" / "api" / "main.py").read_text()
        read = {literal.split("/")[0]
                for literal in re.findall(r'Path\("([^"]+)"\)', source)}
        # A scan that finds nothing passes forever. If the API stops writing
        # its paths as literals this has to fail rather than go quiet.
        self.assertTrue(read, "no relative paths found in the API source")
        for name in sorted(read):
            with self.subTest(path=name):
                self.assertIn(name, copied_into_the_image())

    def test_the_default_dataset_is_in_the_image(self):
        """A cold container cannot generate data during its first request, so
        without it the first caller gets an error rather than a page.

        THE NAME IS READ, NEVER RETYPED. `test_demo_dataset.py` refuses any
        test that writes that directory as a path constant, because nothing
        which judges correctness may read the demo set. This asserts against
        the Dockerfile and opens nothing, and taking the name from the module
        that defines it keeps the guard whole rather than arguing with it.
        """
        from src.pipeline import DEMO_DIR
        self.assertIn(DEMO_DIR.name, copied_into_the_image())
