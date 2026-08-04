"""The sourcing verdict, as an explicit lookup table.

A table rather than nested conditionals because the distinctions here are the
product. Two of them are easy to lose in an `if` chain:

  buy / 0 suppliers / verified   is no_qualified_supplier, a real and serious
                                 finding, NOT the same as nobody having checked
  buy / 1 supplier / unverified  is NOT single_source, because an unconfirmed
                                 list of one may really be a list of two

Tests hard-code their expected verdict by hand and must not import TABLE. If
they imported it, a wrong row would be wrong in both the table and its test and
the two would agree with each other.
"""
from dataclasses import dataclass

# source_type
MAKE = "make"
BUY = "buy"
SOURCE_TYPES = (MAKE, BUY)

# sourcing_list_status. Blank and "unverified" are the same claim: nobody
# confirmed this list is complete.
VERIFIED = "verified"
UNVERIFIED = "unverified"
BLANK = ""
LIST_STATUSES = (VERIFIED, UNVERIFIED, BLANK)

# verdicts
MADE_IN_HOUSE = "made_in_house"
NO_QUALIFIED_SUPPLIER = "no_qualified_supplier"
SUPPLIER_LIST_UNKNOWN = "supplier_list_unknown"
SINGLE_SOURCE = "single_source"
SINGLE_SOURCE_NO_LEAD_TIME = "single_source_no_lead_time"
MULTI_SOURCE = "multi_source"
MULTI_SOURCE_NO_LEAD_TIMES = "multi_source_no_lead_times"
HIDDEN_SINGLE_SOURCE = "hidden_single_source"
READINGS_DISAGREE = "readings_disagree"

ANY = "*"
ZERO, ONE, MANY = "0", "1", "2+"


def bucket(n):
    return ZERO if n == 0 else (ONE if n == 1 else MANY)


def status_bucket(status):
    """Blank and unverified collapse: both mean nobody confirmed the list."""
    return VERIFIED if status == VERIFIED else UNVERIFIED


@dataclass(frozen=True)
class Row:
    source_type: str
    suppliers: str
    list_status: str
    with_lead_time: str
    verdict: str


# Ordered. First match wins, so more specific rows precede ANY rows.
TABLE = (
    Row(BUY, ZERO, VERIFIED, ANY, NO_QUALIFIED_SUPPLIER),
    Row(BUY, ZERO, UNVERIFIED, ANY, SUPPLIER_LIST_UNKNOWN),
    Row(BUY, ONE, VERIFIED, ONE, SINGLE_SOURCE),
    Row(BUY, ONE, VERIFIED, ZERO, SINGLE_SOURCE_NO_LEAD_TIME),
    Row(BUY, ONE, UNVERIFIED, ANY, SUPPLIER_LIST_UNKNOWN),
    Row(BUY, MANY, ANY, MANY, MULTI_SOURCE),
    Row(BUY, MANY, ANY, ONE, HIDDEN_SINGLE_SOURCE),
    Row(BUY, MANY, ANY, ZERO, MULTI_SOURCE_NO_LEAD_TIMES),
)


def _matches(row, source_type, suppliers, list_status, with_lead_time):
    return all(
        expected in (ANY, actual)
        for expected, actual in (
            (row.source_type, source_type),
            (row.suppliers, suppliers),
            (row.list_status, list_status),
            (row.with_lead_time, with_lead_time),
        )
    )


def _lookup(source_type, n_suppliers, list_status, n_with_lead_time):
    key = (source_type, bucket(n_suppliers), status_bucket(list_status),
           bucket(n_with_lead_time))
    for row in TABLE:
        if _matches(row, *key):
            return row.verdict
    raise KeyError(f"no verdict row matches {key}")


def readings(source_type, n_suppliers, list_status, n_with_lead_time):
    """Both readings of a make part that also has suppliers.

    Supplier rows on a part marked `make` are a contradiction in the data, and
    the contradiction has two honest readings:

      stale_flag  the make flag is out of date and the part is really bought,
                  so the external suppliers are the only sources
      dual_mode   in-house capability is real and counts as a source, so there
                  is one more source than the supplier table shows, and it needs
                  no lead time record because it is not a purchase

    Returns {} when there is nothing to disagree about: a `buy` part, or a
    `make` part with no supplier rows. With no supplier rows there is no
    contradiction, so the flag is taken at its word.
    """
    if source_type != MAKE or n_suppliers == 0:
        return {}
    stale = _lookup(BUY, n_suppliers, list_status, n_with_lead_time)
    # in-house adds one source on paper and one usable source
    dual = _lookup(BUY, n_suppliers + 1, list_status, n_with_lead_time + 1)
    return {"stale_flag": stale, "dual_mode": dual}


def verdict(source_type, n_suppliers, list_status, n_with_lead_time):
    """The verdict, or READINGS_DISAGREE when the two readings differ.

    A `make` part with no suppliers is made_in_house. Nothing in the data
    contradicts the flag, so it is believed.
    """
    if source_type == MAKE:
        if n_suppliers == 0:
            return MADE_IN_HOUSE
        both = readings(source_type, n_suppliers, list_status, n_with_lead_time)
        if both["stale_flag"] == both["dual_mode"]:
            return both["stale_flag"]
        return READINGS_DISAGREE
    return _lookup(source_type, n_suppliers, list_status, n_with_lead_time)


# Severity order, worst first. The exception lane sorts by exposure under the
# WORSE reading, so this is what orders it.
SEVERITY = (
    NO_QUALIFIED_SUPPLIER,
    SINGLE_SOURCE_NO_LEAD_TIME,
    SINGLE_SOURCE,
    HIDDEN_SINGLE_SOURCE,
    SUPPLIER_LIST_UNKNOWN,
    MULTI_SOURCE_NO_LEAD_TIMES,
    MULTI_SOURCE,
    MADE_IN_HOUSE,
)


def worse(a, b):
    """The worse of two verdicts, for ordering the exception lane."""
    return a if SEVERITY.index(a) <= SEVERITY.index(b) else b
