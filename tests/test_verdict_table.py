"""One test per row of the sourcing verdict table.

Expectations are HARD-CODED BY HAND and this module must not import TABLE. If
it did, a wrong row would be wrong in both the table and its test, and the two
would agree with each other. That is the whole reason the table is declarative
rather than a chain of conditionals.
"""
import pytest

from src.synthetic.verdicts import (BLANK, BUY, MAKE, UNVERIFIED, VERIFIED,
                                    readings, verdict, worse)

# (source_type, n_suppliers, list_status, n_with_lead_time, expected)
ROWS = [
    # make, no supplier rows: nothing contradicts the flag, so believe it
    (MAKE, 0, VERIFIED, 0, "made_in_house"),
    (MAKE, 0, BLANK, 0, "made_in_house"),

    # buy, no supplier rows. verified means somebody checked and found none,
    # which is a real finding. unverified means nobody checked.
    (BUY, 0, VERIFIED, 0, "no_qualified_supplier"),
    (BUY, 0, UNVERIFIED, 0, "supplier_list_unknown"),
    (BUY, 0, BLANK, 0, "supplier_list_unknown"),

    # buy, exactly one supplier
    (BUY, 1, VERIFIED, 1, "single_source"),
    (BUY, 1, VERIFIED, 0, "single_source_no_lead_time"),
    (BUY, 1, UNVERIFIED, 1, "supplier_list_unknown"),
    (BUY, 1, BLANK, 1, "supplier_list_unknown"),

    # buy, several suppliers
    (BUY, 2, VERIFIED, 2, "multi_source"),
    (BUY, 3, VERIFIED, 3, "multi_source"),
    (BUY, 2, VERIFIED, 1, "hidden_single_source"),
    (BUY, 3, BLANK, 1, "hidden_single_source"),
    (BUY, 2, VERIFIED, 0, "multi_source_no_lead_times"),

    # make WITH suppliers: the readings disagree unless every supplier has a
    # lead time and there are at least two of them
    (MAKE, 1, VERIFIED, 1, "readings_disagree"),
    (MAKE, 1, VERIFIED, 0, "readings_disagree"),
    (MAKE, 2, VERIFIED, 1, "readings_disagree"),
    (MAKE, 2, VERIFIED, 0, "readings_disagree"),
    (MAKE, 2, VERIFIED, 2, "multi_source"),
    (MAKE, 3, VERIFIED, 3, "multi_source"),
]


@pytest.mark.parametrize("source_type,n_suppliers,status,n_lead,expected", ROWS)
def test_verdict_row(source_type, n_suppliers, status, n_lead, expected):
    assert verdict(source_type, n_suppliers, status, n_lead) == expected


def test_an_unverified_list_of_one_is_not_single_source():
    """The rule this table exists to make structural. An unconfirmed list of
    one may really be a list of two, so it is not a single-source claim."""
    assert verdict(BUY, 1, VERIFIED, 1) == "single_source"
    assert verdict(BUY, 1, UNVERIFIED, 1) == "supplier_list_unknown"


def test_verified_and_empty_is_not_the_same_as_nobody_checked():
    assert verdict(BUY, 0, VERIFIED, 0) == "no_qualified_supplier"
    assert verdict(BUY, 0, UNVERIFIED, 0) == "supplier_list_unknown"


def test_blank_status_is_treated_as_unverified():
    """Blank and unverified are the same claim: nobody confirmed this list."""
    for n in (0, 1, 2):
        assert verdict(BUY, n, BLANK, n) == verdict(BUY, n, UNVERIFIED, n)


class TestDualReadings:
    """A make part carrying supplier rows takes no side."""

    def test_no_readings_when_nothing_contradicts_the_flag(self):
        assert readings(MAKE, 0, VERIFIED, 0) == {}
        assert readings(BUY, 2, VERIFIED, 2) == {}

    def test_one_supplier_always_disagrees(self):
        both = readings(MAKE, 1, VERIFIED, 1)
        assert both["stale_flag"] == "single_source"
        assert both["dual_mode"] == "multi_source"

    def test_two_suppliers_with_a_gap_disagrees(self):
        """The case an earlier draft of the brief missed. Under the stale-flag
        reading this is a hidden single source; under dual-mode, in-house is a
        usable source that needs no lead time record because it is not a
        purchase."""
        both = readings(MAKE, 2, VERIFIED, 1)
        assert both["stale_flag"] == "hidden_single_source"
        assert both["dual_mode"] == "multi_source"

    def test_two_suppliers_fully_recorded_agrees(self):
        both = readings(MAKE, 2, VERIFIED, 2)
        assert both["stale_flag"] == both["dual_mode"] == "multi_source"


def test_exception_lane_orders_by_the_worse_reading():
    assert worse("single_source", "multi_source") == "single_source"
    assert worse("multi_source", "hidden_single_source") == "hidden_single_source"
    assert worse("no_qualified_supplier", "single_source") == "no_qualified_supplier"
