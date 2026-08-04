"""CSV emission, and the single place null encoding is decided.

Missing and zero are different facts and the encoding has to keep them that
way through a default `pd.read_csv`:

    on_hand_units = ""   no record exists
    on_hand_units = "0"  somebody counted and found none

Written with the stdlib csv module rather than pandas so the bytes are exactly
what this file says they are, which is what makes byte-identical determinism
testable.
"""
import csv

from .model import (ANNUAL_SPEND_USD, ANNUAL_UNITS, BOM_COLUMNS, CHILD_PART,
                    DEMAND_COLUMNS, DESCRIPTION, FINISHED_GOOD_PART,
                    LEAD_TIME_COLUMNS, LEAD_TIME_P95_DAYS, ON_HAND_UNITS,
                    PARENT_PART, PART_MASTER_COLUMNS, PART_NUMBER,
                    QTY_PER_PARENT, QUALIFICATION_DATE,
                    QUOTED_LEAD_TIME_DAYS, SOURCE_TYPE, SOURCING_LIST_STATUS,
                    SUPPLIER_COLUMNS, SUPPLIER_NAME, SUPPLIER_REGION,
                    TOOLING_OWNER)

BOM_FILE = "bom.csv"
PART_MASTER_FILE = "part_master.csv"
SUPPLIERS_FILE = "suppliers.csv"
LEAD_TIMES_FILE = "lead_times.csv"
DEMAND_FILE = "demand_plan.csv"


def _blank_if_none(value):
    """None becomes an empty cell. Zero stays zero. This is the whole rule."""
    return "" if value is None else value


def _write(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns),
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_world(world, out_dir):
    """Write every file. Called once, at the end, from a complete in-memory
    world, so a crash cannot leave the CSVs and the answer key disagreeing."""
    out_dir.mkdir(parents=True, exist_ok=True)

    _write(out_dir / BOM_FILE, BOM_COLUMNS, [
        {PARENT_PART: parent, CHILD_PART: child, QTY_PER_PARENT: qty}
        for parent, child, qty in sorted(world.bom)
    ])

    _write(out_dir / PART_MASTER_FILE, PART_MASTER_COLUMNS, [
        {
            PART_NUMBER: part.part_number,
            DESCRIPTION: part.description,
            SOURCE_TYPE: part.source_type,
            SOURCING_LIST_STATUS: part.sourcing_list_status,
            ON_HAND_UNITS: _blank_if_none(part.on_hand_units),
            TOOLING_OWNER: part.tooling_owner,
            ANNUAL_SPEND_USD: part.annual_spend_usd,
        }
        for part in sorted(world.parts.values(), key=lambda p: p.part_number)
    ])

    _write(out_dir / SUPPLIERS_FILE, SUPPLIER_COLUMNS, [
        {
            PART_NUMBER: link.part_number,
            SUPPLIER_NAME: link.name_in_suppliers,
            SUPPLIER_REGION: world.suppliers[link.supplier_id].region,
            QUALIFICATION_DATE: link.qualification_date,
        }
        for link in sorted(world.links,
                           key=lambda l: (l.part_number, l.supplier_id))
    ])

    # A lead time row carries the supplier name as spelled IN THIS FILE, which
    # for a diverged pair is not the spelling in suppliers.csv.
    name_by_pair = {(l.part_number, l.supplier_id): l.name_in_lead_times
                    for l in world.links}
    _write(out_dir / LEAD_TIMES_FILE, LEAD_TIME_COLUMNS, [
        {
            PART_NUMBER: lt.part_number,
            SUPPLIER_NAME: name_by_pair.get(
                (lt.part_number, lt.supplier_id),
                world.suppliers[lt.supplier_id].canonical_name),
            QUOTED_LEAD_TIME_DAYS: lt.quoted_lead_time_days,
            LEAD_TIME_P95_DAYS: lt.lead_time_p95_days,
        }
        for lt in sorted(world.lead_times,
                         key=lambda lt: (lt.part_number, lt.supplier_id))
    ])

    _write(out_dir / DEMAND_FILE, DEMAND_COLUMNS, [
        {FINISHED_GOOD_PART: fg, ANNUAL_UNITS: units}
        for fg, units in sorted(world.demand.items())
    ])
