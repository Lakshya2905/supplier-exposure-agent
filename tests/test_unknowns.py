"""The "cannot tell" contract, which is the rule most likely to rot.

Three unknowns are named in CLAUDE.md: missing lead times, incomplete supplier
lists, and missing on-hand records. Each must surface as unknown rather than as
a default value. Plus the fourth case the brief adds, which is not an unknown at
all but a BOUND: usage that is partially known.
"""
import pandas as pd
import pytest

from src.generate_data import generate
from src.synthetic.config import FORBIDDEN_REGION_TOKENS, GeneratorConfig
from src.synthetic.model import (ANNUAL_UNITS, FINISHED_GOOD_PART,
                                 ON_HAND_UNITS, PART_NUMBER, SOURCE_TYPE,
                                 SOURCING_LIST_STATUS, SUPPLIER_REGION)
from src.synthetic.truth import verdict_coverage
from src.synthetic.writers import (DEMAND_FILE, PART_MASTER_FILE,
                                   SUPPLIERS_FILE)


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    out = tmp_path_factory.mktemp("unknowns")
    world, truth = generate(GeneratorConfig(), out, out / "truth.json")
    return world, truth, out


class TestMissingIsNotZero:
    def test_blank_and_zero_both_occur(self, generated):
        _, _, out = generated
        raw = pd.read_csv(out / PART_MASTER_FILE, dtype=str)
        blanks = raw[ON_HAND_UNITS].isna().sum()
        zeros = (raw[ON_HAND_UNITS] == "0").sum()
        assert blanks > 0, "no missing on-hand records were generated"
        assert zeros > 0, "no genuine zero on-hand records were generated"

    def test_a_default_read_keeps_them_distinct(self, generated):
        """The failure this guards: one fillna(0) collapses 'no record' into
        'counted and found none'. If the generator never produced a genuine
        zero, that bug would pass every test anyone could write."""
        _, _, out = generated
        frame = pd.read_csv(out / PART_MASTER_FILE)
        missing = frame[ON_HAND_UNITS].isna()
        zero = frame[ON_HAND_UNITS] == 0
        assert missing.any() and zero.any()
        assert not (missing & zero).any(), "a row cannot be both"


class TestSupplierListUnknowns:
    def test_source_type_is_always_present(self, generated):
        """It is what separates 'we make this' from 'nobody recorded the
        suppliers'. A blank would put the system back to guessing."""
        _, _, out = generated
        frame = pd.read_csv(out / PART_MASTER_FILE)
        assert frame[SOURCE_TYPE].notna().all()
        assert set(frame[SOURCE_TYPE].unique()) <= {"make", "buy"}

    def test_both_zero_supplier_cases_exist(self, generated):
        """A buy part with no suppliers is either a real finding or an unknown,
        and only sourcing_list_status tells them apart."""
        _, truth, _ = generated
        coverage = verdict_coverage(truth)
        assert coverage.get("no_qualified_supplier", 0) >= 1
        assert coverage.get("supplier_list_unknown", 0) >= 1

    def test_every_verdict_row_is_represented(self, generated):
        """No row of the table ships without at least one part exercising it."""
        _, truth, _ = generated
        coverage = verdict_coverage(truth)
        for expected in ("made_in_house", "no_qualified_supplier",
                         "supplier_list_unknown", "single_source",
                         "single_source_no_lead_time", "multi_source",
                         "multi_source_no_lead_times", "hidden_single_source",
                         "readings_disagree"):
            assert coverage.get(expected, 0) >= 1, f"no part covers {expected}"


class TestPartialDemandIsABound:
    """Unrecorded demand can only REDUCE cover, never increase it, so a part
    with partially known usage yields an upper bound rather than an unknown.

    The walk here is a naive local one. Truth deliberately does not record
    which parts are affected, because that needs a traversal and an answer key
    that traverses could agree with a buggy traversal in stage 2.
    """

    def feeding_finished_goods(self, world, part):
        found = set()

        def walk(node, target):
            for parent, child, _ in world.bom:
                if child == target:
                    if parent in world.finished_goods:
                        found.add(parent)
                    else:
                        walk(node, parent)

        walk(part, part)
        return found

    def test_one_finished_good_is_absent_from_the_demand_plan(self, generated):
        world, truth, out = generated
        demand = pd.read_csv(out / DEMAND_FILE)
        listed = set(demand[FINISHED_GOOD_PART])
        assert truth.absent_demand_finished_good
        assert truth.absent_demand_finished_good not in listed
        assert len(listed) == len(world.finished_goods) - 1

    def test_a_partially_known_part_exists(self, generated):
        """Fed by recorded finished goods AND the absent one. Neither known nor
        unknown; the honest answer is a bounded number."""
        world, truth, _ = generated
        absent = truth.absent_demand_finished_good
        partial = [p for p in world.parts
                   if absent in self.feeding_finished_goods(world, p)
                   and self.feeding_finished_goods(world, p) - {absent}]
        assert partial, "no part has partially known usage"

    def test_a_wholly_unknown_part_exists(self, generated):
        """Fed only by the absent finished good. The full cannot-tell."""
        world, truth, _ = generated
        absent = truth.absent_demand_finished_good
        only = [p for p in world.parts
                if self.feeding_finished_goods(world, p) == {absent}]
        assert only, "no part is fed exclusively by the absent finished good"


class TestRegionsSurviveReading:
    def test_no_region_is_swallowed_as_nan(self, generated):
        """pandas reads a bare NA as NaN by default, which would silently
        delete a region from stage 5's concentration analysis."""
        _, _, out = generated
        frame = pd.read_csv(out / SUPPLIERS_FILE)
        assert frame[SUPPLIER_REGION].notna().all()
        for token in FORBIDDEN_REGION_TOKENS:
            assert token not in set(frame[SUPPLIER_REGION].astype(str))
