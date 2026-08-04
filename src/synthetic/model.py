"""Column names and the in-memory model.

Stage 2 onward imports these constants rather than typing string literals, so a
column rename is one edit and a typo is an ImportError instead of a silently
empty join.
"""
from dataclasses import dataclass, field

# ---- bom.csv ----
PARENT_PART = "parent_part"
CHILD_PART = "child_part"
QTY_PER_PARENT = "qty_per_parent"
BOM_COLUMNS = (PARENT_PART, CHILD_PART, QTY_PER_PARENT)

# ---- part_master.csv ----
PART_NUMBER = "part_number"
DESCRIPTION = "description"
SOURCE_TYPE = "source_type"
SOURCING_LIST_STATUS = "sourcing_list_status"
ON_HAND_UNITS = "on_hand_units"
TOOLING_OWNER = "tooling_owner"
ANNUAL_SPEND_USD = "annual_spend_usd"
PART_MASTER_COLUMNS = (PART_NUMBER, DESCRIPTION, SOURCE_TYPE,
                       SOURCING_LIST_STATUS, ON_HAND_UNITS, TOOLING_OWNER,
                       ANNUAL_SPEND_USD)

# ---- suppliers.csv ----
SUPPLIER_NAME = "supplier_name"
SUPPLIER_REGION = "supplier_region"
QUALIFICATION_DATE = "qualification_date"
SUPPLIER_COLUMNS = (PART_NUMBER, SUPPLIER_NAME, SUPPLIER_REGION,
                    QUALIFICATION_DATE)

# ---- lead_times.csv ----
QUOTED_LEAD_TIME_DAYS = "quoted_lead_time_days"
LEAD_TIME_P95_DAYS = "lead_time_p95_days"
LEAD_TIME_COLUMNS = (PART_NUMBER, SUPPLIER_NAME, QUOTED_LEAD_TIME_DAYS,
                     LEAD_TIME_P95_DAYS)

# ---- demand_plan.csv ----
FINISHED_GOOD_PART = "finished_good_part"
ANNUAL_UNITS = "annual_units"
DEMAND_COLUMNS = (FINISHED_GOOD_PART, ANNUAL_UNITS)

# Tooling ownership
TOOLING_COMPANY = "company"
TOOLING_SUPPLIER = "supplier"

# Namespaced so "no real part numbers" is machine-checkable rather than a
# promise. tests assert every identifier carries one of these prefixes.
PART_PREFIX = "SEA-P-"
FG_PREFIX = "SEA-FG-"
SUPPLIER_PREFIX = "SEA-SUP-"


@dataclass
class Part:
    part_number: str
    description: str
    source_type: str
    level: int
    sourcing_list_status: str = ""
    on_hand_units: int | None = None
    tooling_owner: str = ""
    annual_spend_usd: int = 0


@dataclass
class Supplier:
    """A supplier identity. `canonical_name` is the truth; what lands in a CSV
    may be any of `variants`."""
    supplier_id: str
    canonical_name: str
    region: str


@dataclass
class SupplierLink:
    part_number: str
    supplier_id: str
    qualification_date: str
    # Rendered per file, so the same supplier can appear spelled differently in
    # suppliers.csv and lead_times.csv. That divergence is the point.
    name_in_suppliers: str = ""
    name_in_lead_times: str = ""


@dataclass
class LeadTime:
    part_number: str
    supplier_id: str
    quoted_lead_time_days: int
    lead_time_p95_days: int


@dataclass
class World:
    """Everything, in memory. Written out only at the end, so a crash cannot
    leave the CSVs and the answer key disagreeing."""
    parts: dict = field(default_factory=dict)
    bom: list = field(default_factory=list)
    suppliers: dict = field(default_factory=dict)
    links: list = field(default_factory=list)
    lead_times: list = field(default_factory=list)
    demand: dict = field(default_factory=dict)
    finished_goods: list = field(default_factory=list)

    def links_for(self, part_number):
        return [l for l in self.links if l.part_number == part_number]

    def lead_times_for(self, part_number):
        return [lt for lt in self.lead_times if lt.part_number == part_number]
