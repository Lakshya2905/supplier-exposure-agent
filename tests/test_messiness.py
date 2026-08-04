"""Messiness, and the clean-world control.

The control is the most valuable test here: with every rate at zero the world
must be perfectly consistent and the answer key empty. It proves the damage is
genuinely separable from the construction rather than baked in.
"""
import pandas as pd
import pytest

from src.generate_data import generate
from src.synthetic.config import GeneratorConfig
from src.synthetic.messiness import name_variants
from src.synthetic.model import (PART_NUMBER, SUPPLIER_NAME, FG_PREFIX,
                                 PART_PREFIX, SUPPLIER_PREFIX)
from src.synthetic.writers import LEAD_TIMES_FILE, SUPPLIERS_FILE


@pytest.fixture(scope="module")
def messy(tmp_path_factory):
    out = tmp_path_factory.mktemp("messy")
    world, truth = generate(GeneratorConfig(), out, out / "truth.json")
    return world, truth, out


@pytest.fixture(scope="module")
def clean(tmp_path_factory):
    out = tmp_path_factory.mktemp("clean")
    world, truth = generate(GeneratorConfig().zeroed(), out, out / "truth.json")
    return world, truth, out


class TestCleanWorldControl:
    def test_zero_rates_leave_the_answer_key_empty(self, clean):
        _, truth, _ = clean
        assert truth.is_empty(), (
            f"damage recorded with every rate at zero: "
            f"{truth.intents or truth.omitted_lead_times}")

    def test_every_pair_has_a_lead_time(self, clean):
        world, _, _ = clean
        pairs = {(l.part_number, l.supplier_id) for l in world.links}
        with_lt = {(lt.part_number, lt.supplier_id) for lt in world.lead_times}
        assert pairs == with_lt

    def test_every_buy_part_has_a_supplier(self, clean):
        world, _, _ = clean
        for part in world.parts.values():
            if part.source_type == "buy":
                assert world.links_for(part.part_number)

    def test_every_finished_good_has_demand(self, clean):
        world, _, _ = clean
        assert set(world.demand) == set(world.finished_goods)

    def test_no_on_hand_is_missing(self, clean):
        world, _, _ = clean
        assert all(p.on_hand_units is not None for p in world.parts.values())


class TestConfigClassification:
    """Every damage knob must be reachable by zeroed().

    This exists because it already failed once: zeroed() enumerated the case
    knobs inline, two added later were missed, and the clean-world control
    silently stopped being clean while still passing its own name. Classifying
    every knob makes the next omission a failure here rather than a quiet hole
    in the control.
    """

    def test_every_integer_knob_is_classified(self):
        from src.synthetic.config import CASE_FIELDS, SHAPE_FIELDS
        config = GeneratorConfig()
        knobs = {name for name, value in vars(config).items()
                 if name.startswith("n_") and isinstance(value, int)}
        classified = set(SHAPE_FIELDS) | set(CASE_FIELDS)
        assert knobs - classified == set(), (
            f"unclassified knobs, so zeroed() will not zero them: "
            f"{knobs - classified}")
        assert set(SHAPE_FIELDS) & set(CASE_FIELDS) == set()

    def test_zeroed_actually_zeros_every_case_knob(self):
        from src.synthetic.config import CASE_FIELDS
        clean = GeneratorConfig().zeroed()
        for name in CASE_FIELDS:
            assert getattr(clean, name) == 0, f"{name} survived zeroed()"

    def test_zeroed_leaves_the_shape_alone(self):
        from src.synthetic.config import SHAPE_FIELDS
        config, clean = GeneratorConfig(), GeneratorConfig().zeroed()
        for name in SHAPE_FIELDS:
            assert getattr(clean, name) == getattr(config, name)


class TestSupplierNameVariants:
    def test_variants_are_plausible_renderings_of_one_name(self):
        variants = name_variants("Northwind Corporation", rng=None)
        assert "Northwind Corporation" in variants
        assert "NORTHWIND CORPORATION" in variants
        assert "Northwind Corp" in variants
        assert any(v.endswith(" ") for v in variants)

    def test_names_diverge_across_files(self, messy):
        """If a supplier were spelled the same way in both files, an exact
        string join would work and the canonical registry would buy nothing."""
        _, truth, _ = messy
        assert truth.cross_file_divergences, "no cross-file divergence"
        sample = truth.cross_file_divergences[0]
        assert sample["name_in_suppliers"] != sample["name_in_lead_times"]

    def test_divergences_really_appear_in_the_files(self, messy):
        _, truth, out = messy
        suppliers = pd.read_csv(out / SUPPLIERS_FILE)
        lead_times = pd.read_csv(out / LEAD_TIMES_FILE)
        case = truth.cross_file_divergences[0]
        part = case["part_number"]

        in_suppliers = set(
            suppliers[suppliers[PART_NUMBER] == part][SUPPLIER_NAME])
        in_lead_times = set(
            lead_times[lead_times[PART_NUMBER] == part][SUPPLIER_NAME])
        assert case["name_in_suppliers"] in in_suppliers
        # the lead time row may have been dropped by other damage
        if in_lead_times:
            assert in_suppliers != in_lead_times or len(in_suppliers) > 1

    def test_every_emitted_name_maps_back_to_one_supplier(self, messy):
        _, truth, out = messy
        suppliers = pd.read_csv(out / SUPPLIERS_FILE)
        for name in suppliers[SUPPLIER_NAME]:
            assert name in truth.supplier_variants, f"unmapped name: {name!r}"

    def test_confusable_suppliers_are_recorded_as_distinct(self, messy):
        """The mirror trap. Without it, a matcher that collapses anything
        similar looks correct instead of being caught."""
        _, truth, _ = messy
        assert truth.confusable_suppliers
        pair = truth.confusable_suppliers[0]
        assert pair["a"]["supplier_id"] != pair["b"]["supplier_id"]
        assert pair["a"]["name"].split()[0] == pair["b"]["name"].split()[0]


class TestSyntheticIdentifiers:
    def test_no_real_part_numbers(self, messy):
        """CLAUDE.md forbids real part numbers. Machine-checked rather than
        promised: every identifier carries a namespaced prefix."""
        world, _, _ = messy
        for part_number in world.parts:
            assert part_number.startswith((PART_PREFIX, FG_PREFIX))

    def test_no_real_supplier_names(self, messy):
        world, _, _ = messy
        for supplier_id in world.suppliers:
            assert supplier_id.startswith(SUPPLIER_PREFIX)


class TestGuaranteedCases:
    def test_hidden_single_sources_exist(self, messy):
        _, truth, _ = messy
        hidden = [p for p, intents in truth.intents.items()
                  if "hidden_single_source" in intents]
        assert len(hidden) >= 1

    def test_make_parts_with_suppliers_exist(self, messy):
        _, truth, _ = messy
        contradictions = [p for p, intents in truth.intents.items()
                          if "make_with_suppliers" in intents]
        assert len(contradictions) >= 1

    def test_a_make_part_with_two_suppliers_is_missing_a_lead_time(self, messy):
        """Covers the second disagreement case, which an earlier draft of the
        brief missed entirely."""
        _, truth, _ = messy
        gapped = [p for p, intents in truth.intents.items()
                  if "make_with_suppliers_missing_lead_time" in intents]
        assert gapped
