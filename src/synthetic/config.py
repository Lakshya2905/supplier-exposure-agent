"""Generator configuration. Every count and every messiness rate lives here.

No magic numbers in the builders. Setting all messiness rates to zero must
produce a perfectly consistent world with an empty answer key, which is the
single most valuable test in this stage, and that only works if the rates are
addressable from one place.
"""
from dataclasses import dataclass, field

# Regions. "NA" is forbidden: pandas reads it as NaN by default, so a region
# would silently vanish from stage 5's concentration analysis.
REGIONS = ("north_america", "europe", "east_asia", "south_asia")
FORBIDDEN_REGION_TOKENS = ("NA", "N/A", "NaN", "null", "")

# Four finished goods with SPREAD volumes. The spread is the load-bearing part,
# not the count: cover is measured in days, so a part shared between a high
# runner and a low runner has its exposure set almost entirely by the high
# runner. A flat demand plan hides that completely.
FINISHED_GOOD_VOLUMES = (12000, 4500, 900, 300)

# Every integer knob is classified as either SHAPE (how big the world is) or
# CASE (how much damage is in it). zeroed() zeros the CASE knobs.
#
# Listed rather than inferred, and asserted complete by test, because an
# earlier version enumerated them inline inside zeroed(); two knobs added later
# were missed, and the clean-world control silently stopped being clean. A
# knob added in future fails the classification test rather than quietly
# leaking damage into the control.
SHAPE_FIELDS = ("n_finished_goods", "n_parts_target", "n_levels",
                "n_suppliers_pool")
CASE_FIELDS = ("n_hidden_single_source", "n_no_qualified_supplier",
               "n_supplier_list_unknown", "n_make_with_one_supplier",
               "n_make_with_two_suppliers", "n_make_with_two_missing_lead_time",
               "n_multi_source_no_lead_times", "n_confusable_supplier_pairs")


@dataclass
class GeneratorConfig:
    seed: int = 42

    # ---- shape ----
    n_finished_goods: int = 4
    n_parts_target: int = 300          # within the brief's 200-400
    n_levels: int = 3                  # finished good -> sub -> leaf
    n_suppliers_pool: int = 24

    # The finished good deliberately absent from demand_plan.csv, by index.
    # It must share parts with the others so that "partially known" usage
    # exists as well as "wholly unknown".
    absent_demand_fg_index: int = 3
    min_parts_shared_with_absent_fg: int = 3

    # ---- messiness rates, all in [0, 1] ----
    # A supplier name is rendered as a variant rather than canonically.
    supplier_name_variant_rate: float = 0.35
    # A part-supplier pair is spelled DIFFERENTLY in suppliers.csv than in
    # lead_times.csv. Without this an exact-string join works and the whole
    # canonical-registry design buys nothing.
    cross_file_name_divergence_rate: float = 0.20
    # A part-supplier pair has no lead_times row at all.
    missing_lead_time_rate: float = 0.12
    # A part has no on_hand record. Distinct from a recorded zero.
    missing_on_hand_rate: float = 0.15
    # A part has a recorded on-hand of exactly zero. Real, not missing.
    genuine_zero_on_hand_rate: float = 0.05
    # A part has no tooling owner recorded, so portability is unknown.
    missing_tooling_owner_rate: float = 0.10
    # Sourcing list status distribution for buy parts.
    unverified_list_rate: float = 0.18
    blank_list_status_rate: float = 0.12

    # ---- guaranteed cases, by count ----
    # Parts with >=2 suppliers but only one carrying a lead time record.
    n_hidden_single_source: int = 6
    # buy parts with zero supplier rows and a verified list: a real finding.
    n_no_qualified_supplier: int = 2
    # buy parts with zero supplier rows and an unverified list: unknown.
    n_supplier_list_unknown: int = 3
    # make parts carrying supplier rows, which is the readings-disagree case.
    n_make_with_one_supplier: int = 3
    n_make_with_two_suppliers: int = 2
    # Of the make-with-two parts, how many are missing a lead time. With every
    # supplier carrying a lead time the two readings agree on multi_source;
    # with one missing they disagree (stale-flag says hidden_single_source,
    # dual-mode says multi_source because in-house needs no lead time). Without
    # this the second disagreement case would have no coverage in the data.
    n_make_with_two_missing_lead_time: int = 1
    # buy parts with >=2 suppliers and NO lead time records at all.
    n_multi_source_no_lead_times: int = 2
    # A genuinely distinct supplier pair with near-identical names, so an
    # over-eager fuzzy matcher in stage 2 is caught rather than rewarded.
    n_confusable_supplier_pairs: int = 1

    # ---- lead time shape ----
    # A few days to 40+ weeks, so the tail actually matters.
    lead_time_min_days: int = 3
    lead_time_max_days: int = 300
    lead_time_p95_uplift: tuple = (1.05, 1.60)

    # ---- structural floors, asserted after generation ----
    min_parts_under_two_finished_goods: int = 3
    min_parts_at_two_depths: int = 1

    def zeroed(self):
        """A copy with every messiness rate and every guaranteed damage case
        at zero. Produces a clean world with an empty answer key, which is the
        control this whole design rests on."""
        clean = GeneratorConfig(**{**self.__dict__})
        for name in vars(clean):
            if name.endswith("_rate"):
                setattr(clean, name, 0.0)
        for name in CASE_FIELDS:
            setattr(clean, name, 0)
        clean.absent_demand_fg_index = -1   # every finished good has demand
        return clean
