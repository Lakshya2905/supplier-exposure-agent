"""BOM explosion, graded by the hand-authored fixture.

The assertions here compare against literals worked out by hand in
`fixtures/tiny_bom_expected.py`. They deliberately do NOT use stage 1's
`brute_force_quantities` as the oracle: two implementations grading each other
is exactly what the hand-authored fixture exists to prevent. The brute-force
walk appears once at the bottom as a secondary cross-check, clearly labelled.
"""
from fractions import Fraction
from pathlib import Path

import pandas as pd
import pytest

from fixtures.tiny_bom_expected import (EXPECTED_DEPTHS, EXPECTED_EDGE_COUNT,
                                        EXPECTED_FINISHED_GOOD,
                                        EXPECTED_PART_COUNT,
                                        EXPECTED_QTY_PER_FG)
from src.explosion import (CycleError, ExplodedPart, StructuralError,
                           blocking_finished_goods, explode, finished_goods,
                           rows_by_part, validate)
from src.generate_data import generate
from src.synthetic.config import GeneratorConfig
from src.synthetic.model import CHILD_PART, PARENT_PART, QTY_PER_PARENT

FIXTURES = Path(__file__).parent / "fixtures"


def load_edges(name):
    frame = pd.read_csv(FIXTURES / name, comment="#")
    return [(r[PARENT_PART], r[CHILD_PART], int(r[QTY_PER_PARENT]))
            for _, r in frame.iterrows()]


@pytest.fixture(scope="module")
def tiny_rows():
    return explode(load_edges("tiny_bom.csv"))


class TestAgainstTheHandAuthoredFixture:
    def test_the_finished_good_is_found_from_structure_alone(self):
        assert finished_goods(load_edges("tiny_bom.csv")) == [
            EXPECTED_FINISHED_GOOD]

    def test_every_part_is_reached(self, tiny_rows):
        # 15 parts in the file, minus the finished good itself
        assert len(tiny_rows) == EXPECTED_PART_COUNT - 1
        assert len(load_edges("tiny_bom.csv")) == EXPECTED_EDGE_COUNT

    def test_quantities_match_the_hand_worked_numbers(self, tiny_rows):
        got = {row.part_number: row.qty_per_finished_good for row in tiny_rows}
        assert got == EXPECTED_QTY_PER_FG

    def test_the_common_part_sums_across_branches_and_depths(self, tiny_rows):
        """LEAF-T01 = (2 x 3) + (1 x 4) + 1. Three contributions, two of them
        at depth 2 and one at depth 1."""
        leaf = next(r for r in tiny_rows if r.part_number == "LEAF-T01")
        assert leaf.qty_per_finished_good == 11
        assert leaf.depths == {1, 2}
        assert leaf.spans_depths

    def test_depths_match_the_hand_worked_sets(self, tiny_rows):
        got = {row.part_number: set(row.depths) for row in tiny_rows}
        assert got == EXPECTED_DEPTHS

    def test_min_and_max_depth_are_derived(self, tiny_rows):
        leaf = next(r for r in tiny_rows if r.part_number == "LEAF-T01")
        assert (leaf.min_depth, leaf.max_depth) == (1, 2)
        assert "min_depth" not in ExplodedPart.__dataclass_fields__
        assert "max_depth" not in ExplodedPart.__dataclass_fields__


class TestArithmeticIsExact:
    def test_quantities_are_fractions(self, tiny_rows):
        assert all(isinstance(r.qty_per_finished_good, Fraction)
                   for r in tiny_rows)

    def test_a_whole_number_compares_equal_to_an_int(self, tiny_rows):
        """The property that keeps the fixture literal. If this needed a
        tolerance the fixture would have stopped being an oracle."""
        leaf = next(r for r in tiny_rows if r.part_number == "LEAF-T01")
        assert leaf.qty_per_finished_good == 11
        assert leaf.qty_per_finished_good.denominator == 1

    def test_fractional_quantities_stay_exact(self):
        """Three thirds sum to exactly one, which is what floats cannot do.
        Stage 1 cannot emit these yet; explosion is ready for when it can."""
        edges = [("FG", "SUB", Fraction(1, 3)),
                 ("FG", "SUB2", Fraction(1, 3)),
                 ("FG", "SUB3", Fraction(1, 3))]
        rows = explode(edges)
        assert sum(r.qty_per_finished_good for r in rows) == 1

    def test_multiplication_down_levels_stays_exact(self):
        edges = [("FG", "A", Fraction(1, 3)), ("A", "B", 3)]
        rows = {r.part_number: r.qty_per_finished_good for r in explode(edges)}
        assert rows["B"] == 1


class TestPerFinishedGoodIsPreserved:
    """Blast radius needs to know WHICH finished goods a part blocks. An early
    rollup would destroy that, which is why there is no rollup here."""

    def test_rows_are_per_finished_good(self):
        edges = [("FG-1", "SHARED", 2), ("FG-2", "SHARED", 5)]
        rows = explode(edges)
        assert len(rows) == 2
        assert {r.finished_good for r in rows} == {"FG-1", "FG-2"}
        assert {r.qty_per_finished_good for r in rows} == {2, 5}

    def test_rows_by_part_keys_rather_than_sums(self):
        edges = [("FG-1", "SHARED", 2), ("FG-2", "SHARED", 5)]
        grouped = rows_by_part(explode(edges))
        assert len(grouped["SHARED"]) == 2, "the per-FG rows must survive"
        assert all(isinstance(r, ExplodedPart) for r in grouped["SHARED"])

    def test_there_is_no_rollup_function(self):
        """Summing across finished goods yields an unlabelled scalar with no
        unit, and the obvious next step is dividing on-hand by it. Annual usage
        needs the demand plan and the partial-demand rule, so it is stage 4."""
        import src.explosion as explosion
        assert not hasattr(explosion, "rollup")

    def test_blocking_finished_goods_returns_labels(self):
        edges = [("FG-1", "SHARED", 2), ("FG-2", "SHARED", 5),
                 ("FG-1", "LOCAL", 1)]
        rows = explode(edges)
        assert blocking_finished_goods(rows, "SHARED") == {"FG-1", "FG-2"}
        assert blocking_finished_goods(rows, "LOCAL") == {"FG-1"}


class TestCyclesAndDiamonds:
    def test_a_cycle_raises_rather_than_recursing(self):
        with pytest.raises(CycleError) as caught:
            explode(load_edges("tiny_cycle.csv"))
        assert "SUB-C01" in str(caught.value)
        assert "->" in str(caught.value), "the cycle path should be named"

    def test_a_diamond_is_not_a_cycle(self):
        """Visited twice on different paths is correct. Confusing it with a
        cycle would reject a perfectly ordinary common part."""
        rows = {r.part_number: r.qty_per_finished_good
                for r in explode(load_edges("tiny_diamond.csv"))}
        assert rows["LEAF-D01"] == 11        # (2 x 3) + (5 x 1), by hand

    def test_a_self_edge_is_a_cycle(self):
        with pytest.raises(CycleError):
            explode([("FG", "A", 1), ("A", "A", 1)])


class TestStructuralRefusal:
    def test_an_unknown_part_raises(self):
        edges = [("FG", "GHOST", 1)]
        with pytest.raises(StructuralError) as caught:
            explode(edges, known_parts={"FG"})
        assert "GHOST" in str(caught.value)

    def test_validation_is_skipped_when_no_part_master_is_given(self):
        assert explode([("FG", "A", 1)]) != []

    def test_refusing_is_not_an_unknown_result(self):
        """Explosion has ONE return shape. It declines to answer about a
        structure it cannot trust rather than returning a partial answer."""
        with pytest.raises(StructuralError):
            validate([("FG", "GHOST", 1)], known_parts={"FG"})


class TestAgainstGeneratedData:
    @staticmethod
    @pytest.fixture(scope="class")
    def generated(tmp_path_factory):
        out = tmp_path_factory.mktemp("explode")
        world, _ = generate(GeneratorConfig(), out, out / "truth.json")
        edges = [(p, c, q) for p, c, q in world.bom]
        return world, edges, explode(edges, known_parts=set(world.parts))

    def test_every_finished_good_produces_rows(self, generated):
        world, _, rows = generated
        covered = {r.finished_good for r in rows}
        assert covered == set(world.finished_goods)

    def test_every_non_finished_good_part_is_reached(self, generated):
        world, _, rows = generated
        reached = {r.part_number for r in rows}
        expected = set(world.parts) - set(world.finished_goods)
        assert reached == expected

    def test_a_shared_part_blocks_more_than_one_finished_good(self, generated):
        _, _, rows = generated
        shared = [part for part, group in rows_by_part(rows).items()
                  if len(group) >= 2]
        assert len(shared) >= 3

    def test_a_part_spans_two_depths(self, generated):
        _, _, rows = generated
        assert any(row.spans_depths for row in rows)

    def test_all_quantities_are_positive(self, generated):
        _, _, rows = generated
        assert all(r.qty_per_finished_good > 0 for r in rows)


def _brute_force(edges, root):
    """Secondary cross-check only. NOT the oracle: the hand-worked literals in
    fixtures/tiny_bom_expected.py are."""
    totals = {}

    def walk(node, multiplier):
        for parent, child, qty in edges:
            if parent == node:
                totals[child] = totals.get(child, 0) + multiplier * qty
                walk(child, multiplier * qty)

    walk(root, 1)
    return totals


def test_brute_force_agrees_as_a_secondary_check(tiny_rows):
    got = {row.part_number: row.qty_per_finished_good for row in tiny_rows}
    assert got == _brute_force(load_edges("tiny_bom.csv"), "FG-T01")
