"""The assumption explosion is entitled to make, enforced rather than documented.

Explosion runs at `executes` autonomy because the BOM is structurally complete
by construction: every edge resolves to a known part, and every part reaches at
least one finished good. That is why it has one return shape and no "cannot
tell" path.

This module is the enforcement. Today no damage knob touches BOM structure. If
one is ever added, these fail loudly here rather than showing up as a silent
hole in explosion's coverage, or worse, as an autonomy claim that quietly
stopped being true.
"""
import pytest

from src.explosion import blocking_finished_goods, explode, finished_goods
from src.generate_data import generate
from src.synthetic.config import GeneratorConfig


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("structural")
    built, _ = generate(GeneratorConfig(), out, out / "truth.json")
    return built


@pytest.fixture(scope="module")
def edges(world):
    return [(p, c, q) for p, c, q in world.bom]


class TestEveryEdgeResolves:
    def test_every_parent_exists_in_the_part_master(self, world, edges):
        missing = {p for p, _, _ in edges if p not in world.parts}
        assert missing == set(), f"BOM parents with no part master row: {missing}"

    def test_every_child_exists_in_the_part_master(self, world, edges):
        missing = {c for _, c, _ in edges if c not in world.parts}
        assert missing == set(), f"BOM children with no part master row: {missing}"

    def test_explosion_accepts_the_generated_bom_without_raising(self, world,
                                                                 edges):
        """The positive form of the same claim: explosion validates and does
        not refuse. If a structural knob lands, this is where it surfaces."""
        rows = explode(edges, known_parts=set(world.parts))
        assert rows


class TestEveryPartReachesAFinishedGood:
    def test_no_orphan_parts(self, world, edges):
        """A part nobody can build into anything has no exposure story, and its
        presence would mean explosion silently covers less than the part master
        claims exists."""
        rows = explode(edges, known_parts=set(world.parts))
        reached = {r.part_number for r in rows} | set(world.finished_goods)
        orphans = set(world.parts) - reached
        assert orphans == set(), f"parts reaching no finished good: {orphans}"

    def test_every_part_blocks_at_least_one_finished_good(self, world, edges):
        rows = explode(edges, known_parts=set(world.parts))
        for part in set(world.parts) - set(world.finished_goods):
            assert blocking_finished_goods(rows, part), part


class TestFinishedGoodsComeFromStructure:
    def test_roots_are_parents_that_are_never_children(self, world, edges):
        assert finished_goods(edges) == sorted(world.finished_goods)

    def test_a_finished_good_absent_from_demand_is_still_a_finished_good(
            self, world, edges):
        """The demand plan is not the source of truth for what a finished good
        is. One finished good is deliberately missing from it, and explosion
        must still explode it, or stage 4 could never reason about the parts
        underneath it."""
        absent = set(world.finished_goods) - set(world.demand)
        assert len(absent) == 1
        assert absent <= set(finished_goods(edges))
        rows = explode(edges, known_parts=set(world.parts))
        assert {r.finished_good for r in rows} >= absent


class TestTheAssumptionIsNarrow:
    def test_structure_is_untouched_by_any_damage_knob(self):
        """The claim in one assertion: messiness never edits the BOM.

        Read as source rather than behaviour on purpose. A knob that mutated
        structure would most likely still produce a valid BOM on the day it
        landed, so the behavioural tests above could pass while the autonomy
        claim quietly became conditional.
        """
        from pathlib import Path
        source = (Path(__file__).parent.parent / "src" / "synthetic"
                  / "messiness.py").read_text()
        for forbidden in ("world.bom", ".bom.append", ".bom.remove"):
            assert forbidden not in source, (
                f"messiness.py now touches {forbidden}. BOM structure is no "
                f"longer complete by construction, so explosion's `executes` "
                f"autonomy level and its single return shape both need "
                f"revisiting before this test is changed.")

    def test_clean_and_messy_worlds_have_identical_bom_structure(
            self, tmp_path_factory):
        """The behavioural half. Damage changes sourcing, never the tree."""
        out = tmp_path_factory.mktemp("compare")
        messy, _ = generate(GeneratorConfig(), out / "m", out / "m.json")
        clean, _ = generate(GeneratorConfig().zeroed(), out / "c", out / "c.json")
        assert sorted(messy.bom) == sorted(clean.bom)
        assert set(messy.parts) == set(clean.parts)
