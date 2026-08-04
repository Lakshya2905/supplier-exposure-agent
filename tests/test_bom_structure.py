"""BOM structure, and the hand-authored fixture that will grade stage 2.

The fixture assertions here duplicate the arithmetic written in the fixture's
own comment block on purpose. Two independent statements of the same numbers,
one for a human reading the file and one the test runner checks.

The walk used below is a deliberately naive brute-force recursion. Stage 2 will
write a real explosion; this is not it, and must not be reused as one.
"""
from pathlib import Path

import pandas as pd
import pytest

from src.generate_data import generate
from src.synthetic.config import GeneratorConfig
from src.synthetic.model import CHILD_PART, PARENT_PART, QTY_PER_PARENT

FIXTURE = Path(__file__).parent / "fixtures" / "tiny_bom.csv"

# Worked out by hand from the tree in the fixture's comment block.
EXPECTED_QTY_PER_FG = {
    "SUB-T01": 2, "SUB-T02": 1, "SUB-T03": 3,
    "LEAF-T01": 11,          # (2 x 3) + (1 x 4) + 1
    "LEAF-T02": 2, "LEAF-T03": 4, "LEAF-T04": 5, "LEAF-T05": 1,
    "LEAF-T06": 6, "LEAF-T07": 3,
    "LEAF-T08": 2, "LEAF-T09": 1, "LEAF-T10": 4, "LEAF-T11": 1,
}
EXPECTED_DEPTHS = {
    "SUB-T01": {1}, "SUB-T02": {1}, "SUB-T03": {1},
    "LEAF-T01": {1, 2},      # the whole point of the fixture
    "LEAF-T02": {2}, "LEAF-T03": {2}, "LEAF-T04": {2}, "LEAF-T05": {2},
    "LEAF-T06": {2}, "LEAF-T07": {2},
    "LEAF-T08": {1}, "LEAF-T09": {1}, "LEAF-T10": {1}, "LEAF-T11": {1},
}


def load_edges(path, comment=None):
    frame = pd.read_csv(path, comment=comment)
    return [(r[PARENT_PART], r[CHILD_PART], int(r[QTY_PER_PARENT]))
            for _, r in frame.iterrows()]


def brute_force_quantities(edges, root):
    """Naive path enumeration. Not an implementation to reuse, an oracle."""
    totals = {}

    def walk(node, multiplier):
        for parent, child, qty in edges:
            if parent == node:
                totals[child] = totals.get(child, 0) + multiplier * qty
                walk(child, multiplier * qty)

    walk(root, 1)
    return totals


def brute_force_depths(edges, root):
    depths = {}

    def walk(node, depth):
        for parent, child, _ in edges:
            if parent == node:
                depths.setdefault(child, set()).add(depth + 1)
                walk(child, depth + 1)

    walk(root, 0)
    return depths


class TestHandAuthoredFixture:
    def test_the_fixture_is_hand_authored_and_says_so(self):
        text = FIXTURE.read_text()
        assert "HAND-AUTHORED" in text
        assert "Never generated" in text

    def test_shape(self):
        edges = load_edges(FIXTURE, comment="#")
        parts = {e[0] for e in edges} | {e[1] for e in edges}
        assert len(parts) == 15
        assert len(edges) == 16

    def test_quantities_match_the_hand_worked_numbers(self):
        edges = load_edges(FIXTURE, comment="#")
        assert brute_force_quantities(edges, "FG-T01") == EXPECTED_QTY_PER_FG

    def test_the_common_part_exists_at_two_depths(self):
        """Depth is a property of the PATH, not of the part. An explosion that
        memoises depth per part gets LEAF-T01 wrong and everything downstream
        of it wrong too."""
        edges = load_edges(FIXTURE, comment="#")
        depths = brute_force_depths(edges, "FG-T01")
        assert depths["LEAF-T01"] == {1, 2}
        assert {part: depths[part] for part in EXPECTED_DEPTHS} == EXPECTED_DEPTHS


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("gen")
    built, _ = generate(GeneratorConfig(), out, out / "truth.json")
    return built


class TestGeneratedBom:
    def test_part_count_is_within_the_brief(self, world):
        assert 200 <= len(world.parts) <= 400

    def test_finished_goods_are_roots_and_never_children(self, world):
        children = {child for _, child, _ in world.bom}
        parents = {parent for parent, _, _ in world.bom}
        assert set(world.finished_goods) <= parents
        for fg in world.finished_goods:
            assert fg not in children

    def test_every_child_exists_in_the_part_master(self, world):
        for _, child, _ in world.bom:
            assert child in world.parts

    def test_the_bom_is_acyclic(self, world):
        """Acyclic by construction, since edges only run downward by level. A
        cycle would make a traversal hang rather than fail, which is the worst
        way for stage 2 to break."""
        for parent, child, _ in world.bom:
            assert world.parts[parent].level < world.parts[child].level

    def test_parts_are_shared_across_different_finished_goods(self, world):
        """Shared between two parents inside one finished good does not
        exercise blast radius. Shared across finished goods does."""
        edges = [(p, c, q) for p, c, q in world.bom]
        shared = []
        for part in world.parts:
            feeding = {fg for fg in world.finished_goods
                       if part in brute_force_quantities(edges, fg)}
            if len(feeding) >= 2:
                shared.append(part)
        assert len(shared) >= 3

    def test_a_part_exists_at_two_depths(self, world):
        edges = [(p, c, q) for p, c, q in world.bom]
        multi = set()
        for fg in world.finished_goods:
            for part, depths in brute_force_depths(edges, fg).items():
                if len(depths) > 1:
                    multi.add(part)
        assert multi, "no part appears at two different depths"

    def test_quantities_are_positive_whole_numbers(self, world):
        for _, _, qty in world.bom:
            assert isinstance(qty, int) and qty >= 1
