"""The CLAUDE.md command contract, and determinism.

The command is run through subprocess rather than by importing the module.
Importing would pass even if the package layout were wrong, because the repo
root happens to be on sys.path during a test run. Only the literal command
proves the contract.
"""
import subprocess
import sys
from pathlib import Path

import pytest

from src.generate_data import generate
from src.synthetic.config import GeneratorConfig

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_FILES = ("bom.csv", "part_master.csv", "suppliers.csv",
                  "lead_times.csv", "demand_plan.csv")


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "src.generate_data", *args],
        cwd=ROOT, capture_output=True, text=True)


class TestTheLiteralCommand:
    def test_the_command_from_claude_md_runs(self, tmp_path):
        """`python -m src.generate_data --seed 42`, exactly as documented."""
        result = run_cli("--seed", "42", "--out-dir", str(tmp_path),
                         "--truth-path", str(tmp_path / "truth.json"))
        assert result.returncode == 0, result.stderr
        for name in EXPECTED_FILES:
            assert (tmp_path / name).exists(), f"{name} was not written"
        assert (tmp_path / "truth.json").exists()

    def test_it_reports_what_it_built(self, tmp_path):
        result = run_cli("--seed", "42", "--out-dir", str(tmp_path),
                         "--truth-path", str(tmp_path / "t.json"))
        assert "parts" in result.stdout
        assert "verdicts:" in result.stdout


class TestDeterminism:
    def test_same_seed_is_byte_identical(self, tmp_path):
        one, two = tmp_path / "one", tmp_path / "two"
        for out in (one, two):
            generate(GeneratorConfig(seed=42), out, out / "truth.json")
        for name in EXPECTED_FILES:
            assert (one / name).read_bytes() == (two / name).read_bytes(), (
                f"{name} differs between two runs at the same seed")

    def test_a_different_seed_differs(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        generate(GeneratorConfig(seed=42), a, a / "truth.json")
        generate(GeneratorConfig(seed=43), b, b / "truth.json")
        assert (a / "bom.csv").read_bytes() != (b / "bom.csv").read_bytes()

    def test_generating_does_not_disturb_global_random_state(self, tmp_path):
        """One Random threaded explicitly, never module-level seeding, so
        importing or running the generator cannot reach into anyone else's
        random stream."""
        import random
        random.seed(7)
        expected = [random.random() for _ in range(3)]

        random.seed(7)
        generate(GeneratorConfig(seed=42), tmp_path, tmp_path / "t.json")
        assert [random.random() for _ in range(3)] == expected


class TestExplicitSpec:
    def test_a_config_can_be_passed_instead_of_only_a_seed(self, tmp_path):
        """Targeted edge cases get constructed on demand rather than by
        fishing for a seed that happens to contain one."""
        config = GeneratorConfig(seed=1, n_hidden_single_source=11)
        _, truth = generate(config, tmp_path, tmp_path / "t.json")
        hidden = [p for p, intents in truth.intents.items()
                  if "hidden_single_source" in intents]
        assert len(hidden) == 11

    def test_the_answer_key_records_the_seed_and_config(self, tmp_path):
        """A stale answer key against fresh CSVs must be detectable rather than
        silently grading a later stage wrong."""
        _, truth = generate(GeneratorConfig(seed=5), tmp_path,
                            tmp_path / "t.json")
        assert truth.seed == 5
        assert truth.config_hash


@pytest.mark.xfail(strict=True, reason=(
    "Known gap: the generator cannot express fractional quantities or units of "
    "measure. Every qty_per_parent is a whole number of pieces, so a BOM line "
    "of 0.5 metres of extrusion or 2.5 kg of compound cannot be represented. "
    "This is a GENERATOR limitation, chosen deliberately over a "
    "stage-2-does-not-exist-yet placeholder, which would fail the build the "
    "moment stage 2 lands."))
def test_fractional_quantities_are_supported(tmp_path):
    config = GeneratorConfig(seed=42)
    world, _ = generate(config, tmp_path, tmp_path / "t.json")
    assert any(not float(qty).is_integer() for _, _, qty in world.bom)
