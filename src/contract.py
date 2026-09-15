"""The input contract: what each file must contain, checked before anything reads it.

WHY THIS FILE EXISTS. An enterprise running this on their own extract will get it
wrong the first time, and what decides whether they try again is whether the tool
names the file and the column or says "invalid input". Before this, a header
spelled `parent` instead of `parent_part` produced `KeyError: 'parent_part'` from
somewhere inside pandas: technically the column name, with no file, no row, and
no statement of what the column is for.

THREE RULES, and the third is the one that is usually missing:

  NAME THE FILE, THE COLUMN, AND WHAT IT SHOULD CONTAIN. A problem here carries
  all three plus the fix, because a reader who knows a column is wrong and not
  what it should hold has to go and find the documentation anyway.

  NEVER INFER A DEFAULT AND NEVER COERCE. A cell that should be a whole number
  and is not is refused by name, with its row and its value quoted. The
  alternative is `int(x or 0)`, which is the defect this whole codebase is built
  around, arriving at the front door.

  UNITS ARE PART OF THE CONTRACT. `lead_time_weeks` is not `lead_time_days`, and
  a file offering the first is not missing a column, it is offering the same
  measure in a unit this system does not read. Reporting that as "column missing"
  sends somebody to add a column they already have. The rule is general rather
  than a list: a supplied header sharing a stem with a required one and ending in
  a DIFFERENT known unit is a unit mismatch, and it is said in those words.

WHAT IS A NOTICE RATHER THAN A PROBLEM. A column this system does not read is
not an error, and it is not silence either: a user who added `abc_class`
expecting it to be used should be told it was ignored. Silently dropping an
input is how somebody comes to believe a run accounted for something it never
saw.
"""
from dataclasses import dataclass, field

from .commitments import COMMITMENTS_FILE, COMMITTED_UNITS
from .criticality import CRITICALITY_COLUMN
from .recovery import INPUT_FIELDS as RECOVERY_FIELDS
from .recovery import RECOVERY_INPUTS_FILE
from .subtier import SUB_TIER_FILE, SUB_TIER_SOURCE
from .synthetic import model as m

# ---------------------------------------------------------------- the kinds --
TEXT = "text"
WHOLE_NUMBER = "whole number"
# A cell that may be blank, where BLANK MEANS NO RECORD and is not zero. The
# distinction this codebase exists to protect, declared in the contract so a
# user reads it before they fill the file in rather than after.
OPTIONAL_WHOLE_NUMBER = "whole number, or blank for no record"

BLOCKING = "blocking"
NOTICE = "notice"

# Unit suffixes this system recognises on a column name. Used only to tell a
# WRONG UNIT from a MISSING COLUMN: `quoted_lead_time_weeks` and
# `quoted_lead_time_days` share a stem and differ in unit, so the first is the
# right measure in the wrong unit and saying "column missing" would be useless.
UNIT_SUFFIXES = ("days", "weeks", "months", "years", "hours",
                 "units", "usd", "eur", "gbp", "kg", "lb", "pieces")


@dataclass(frozen=True)
class Column:
    name: str
    kind: str
    means: str
    unit: str = ""
    required: bool = True

    @property
    def stem(self):
        """The name with its unit suffix removed, or the name."""
        for suffix in UNIT_SUFFIXES:
            if self.name.endswith(f"_{suffix}"):
                return self.name[: -len(suffix) - 1]
        return self.name


@dataclass(frozen=True)
class FileContract:
    name: str
    describes: str
    columns: tuple
    required: bool = True

    def required_columns(self):
        return tuple(c for c in self.columns if c.required)

    def column(self, name):
        return next((c for c in self.columns if c.name == name), None)


@dataclass(frozen=True)
class Problem:
    """One thing wrong, with everything needed to fix it and nothing else."""
    severity: str
    file: str
    column: str = ""
    row: object = None
    says: str = ""
    fix: str = ""

    def sentence(self):
        where = self.file
        if self.column:
            where += f", column {self.column!r}"
        if self.row is not None:
            where += f", row {self.row}"
        return f"{where}: {self.says} {self.fix}".strip()


def _whole(name, means, unit=""):
    return Column(name, WHOLE_NUMBER, means, unit)


CONTRACT = (
    FileContract(
        name=m.BOM_FILE,
        describes="the bill of materials, one row per parent-child edge",
        columns=(
            Column(m.PARENT_PART, TEXT, "the assembly this line belongs to"),
            Column(m.CHILD_PART, TEXT,
                   "the part that goes into it; every value must also appear "
                   "in part_master.csv"),
            _whole(m.QTY_PER_PARENT,
                   "how many of the child go into one of the parent, a whole "
                   "number of pieces and at least 1", "pieces"),
        )),
    FileContract(
        name=m.PART_MASTER_FILE,
        describes="one row per part, from the ERP part master",
        columns=(
            Column(m.PART_NUMBER, TEXT, "the part identifier"),
            Column(m.DESCRIPTION, TEXT, "free text, shown but never read"),
            Column(m.SOURCE_TYPE, TEXT, "'make' or 'buy'. Required, never blank"),
            Column(m.SOURCING_LIST_STATUS, TEXT,
                   "'verified', 'unverified', or blank. Gates the verdict "
                   "only; it never enters a score"),
            Column(m.ON_HAND_UNITS, OPTIONAL_WHOLE_NUMBER,
                   "stock on hand. BLANK MEANS NO RECORD and is not zero: a "
                   "counted zero is the worst cover in the dataset and a blank "
                   "is a gap in a spreadsheet", "units"),
            Column(m.TOOLING_OWNER, TEXT,
                   "'company', 'supplier', or blank when nobody has recorded it"),
            _whole(m.ANNUAL_SPEND_USD,
                   "display only. Never scored, ranked or weighted", "usd"),
            Column(CRITICALITY_COLUMN, TEXT,
                   "optional. A criticality label your company already "
                   "maintains. Blank or absent means unclassified, which stays "
                   "in scope", required=False),
        )),
    FileContract(
        name=m.SUPPLIERS_FILE,
        describes="one row per qualified supplier of a part",
        columns=(
            Column(m.PART_NUMBER, TEXT, "the part identifier"),
            Column(m.SUPPLIER_NAME, TEXT,
                   "as spelled in your system. Spellings that differ across "
                   "files are reconciled and the reconciliation is shown"),
            Column(m.SUPPLIER_REGION, TEXT,
                   "a controlled value. 'NA' is read as North America and not "
                   "as a null"),
            Column(m.QUALIFICATION_DATE, TEXT, "ISO date, shown but never read"),
        )),
    FileContract(
        name=m.LEAD_TIMES_FILE,
        describes="one row per supplier who can quote a lead time",
        columns=(
            Column(m.PART_NUMBER, TEXT, "the part identifier"),
            Column(m.SUPPLIER_NAME, TEXT,
                   "as spelled in THIS file, which may differ from "
                   "suppliers.csv"),
            _whole(m.QUOTED_LEAD_TIME_DAYS,
                   "the quoted purchase lead time, in calendar days", "days"),
            _whole(m.LEAD_TIME_P95_DAYS,
                   "the worst-case lead time, in calendar days", "days"),
        )),
    FileContract(
        name=m.DEMAND_FILE,
        describes="one row per finished good with a demand figure",
        columns=(
            Column(m.FINISHED_GOOD_PART, TEXT, "the finished good identifier"),
            _whole(m.ANNUAL_UNITS,
                   "annual demand. A finished good ABSENT from this file is "
                   "absent from the plan, which is load-bearing: it makes "
                   "usage partial rather than zero", "units"),
        )),
    FileContract(
        name=m.SOURCES_FILE,
        describes="the extract manifest: one row per input file, saying which "
                  "system it came out of and when",
        columns=(
            Column(m.SOURCE_FILE, TEXT, "the file name this row describes"),
            Column(m.SYSTEM_OF_RECORD, TEXT,
                   "which system it was pulled from, in words"),
            Column(m.RETRIEVED_AT, TEXT, "when it was pulled, as an ISO time"),
        )),
    FileContract(
        name=RECOVERY_INPUTS_FILE, required=False,
        describes="optional. How long each step of approving a new supplier "
                  "takes, per part",
        columns=(Column(m.PART_NUMBER, TEXT, "the part identifier"),) + tuple(
            Column(field, OPTIONAL_WHOLE_NUMBER,
                   "blank means nobody has timed this step, which makes the "
                   "chain a lower bound rather than a total",
                   unit="days" if field.endswith("_days") else "attempts",
                   required=False)
            for field in RECOVERY_FIELDS)),
    FileContract(
        name=COMMITMENTS_FILE, required=False,
        describes="optional. The order book: what has already been promised",
        columns=(
            Column(m.FINISHED_GOOD_PART, TEXT, "the finished good identifier"),
            Column(COMMITTED_UNITS, WHOLE_NUMBER,
                   "units already promised to a customer", "units"),
        )),
    FileContract(
        name=SUB_TIER_FILE, required=False,
        describes="optional. Where a supplier sources the critical input, one "
                  "hop below your own suppliers",
        columns=(
            Column(m.SUPPLIER_NAME, TEXT, "as spelled in suppliers.csv"),
            Column(SUB_TIER_SOURCE, TEXT,
                   "where they buy it. Blank means they have not said, and a "
                   "blank groups with nothing"),
        )),
)

REQUIRED_FILES = tuple(c.name for c in CONTRACT if c.required)
OPTIONAL_FILES = tuple(c.name for c in CONTRACT if not c.required)


def _unit_of(name):
    for suffix in UNIT_SUFFIXES:
        if name.endswith(f"_{suffix}"):
            return suffix
    return ""


def _stem_of(name):
    unit = _unit_of(name)
    return name[: -len(unit) - 1] if unit else name


def _wrong_unit_for(column, supplied):
    """A supplied header that is this column's measure in another unit.

    THE RULE IS GENERAL, not a list of known mistakes. Two headers share a stem
    and end in different recognised units, so one of them is the right quantity
    counted in something this system does not read. A list would cover the
    variants somebody thought of; this covers the one they did not.
    """
    wanted_unit = _unit_of(column.name)
    if not wanted_unit:
        return None
    stem = _stem_of(column.name)
    for header in supplied:
        if header == column.name:
            return None
        offered = _unit_of(header)
        if offered and offered != wanted_unit and _stem_of(header) == stem:
            return header
    return None


@dataclass
class Report:
    problems: list = field(default_factory=list)
    notices: list = field(default_factory=list)

    @property
    def ok(self):
        """Blocking problems only. A notice never stops a run."""
        return not self.problems

    def sentences(self):
        return tuple(p.sentence() for p in self.problems + self.notices)


class ContractError(Exception):
    """Raised instead of scoring data the contract refuses.

    Carries the problems rather than a message, so a caller can render them as
    rows with the file and the column in their own columns instead of parsing a
    sentence back apart.
    """

    def __init__(self, report):
        self.report = report
        super().__init__("; ".join(p.sentence() for p in report.problems))


def check_headers(file_name, contract, supplied):
    """Header-level checks for one file. Returns (problems, notices)."""
    problems, notices = [], []
    supplied = tuple(supplied)

    for column in contract.required_columns():
        if column.name in supplied:
            continue
        wrong = _wrong_unit_for(column, supplied)
        if wrong:
            problems.append(Problem(
                severity=BLOCKING, file=file_name, column=column.name,
                says=(f"this file offers {wrong!r}, which is the same measure "
                      f"in a different unit."),
                fix=(f"This system reads {column.name!r}, in "
                     f"{column.unit or 'the documented unit'}: {column.means}. "
                     f"Convert the values; renaming the header alone would "
                     f"score {wrong.split('_')[-1]} as "
                     f"{column.unit or 'the wrong unit'}.")))
            continue
        problems.append(Problem(
            severity=BLOCKING, file=file_name, column=column.name,
            says="required column is missing.",
            fix=f"It should contain {column.means}."))

    known = {c.name for c in contract.columns}
    for header in supplied:
        if header not in known:
            notices.append(Problem(
                severity=NOTICE, file=file_name, column=header,
                says="this column is not read by this system.",
                fix=("It is ignored rather than scored. Nothing here infers a "
                     "meaning from a column name.")))
    return problems, notices


def check_cells(file_name, contract, rows):
    """Cell-level checks. `rows` is an iterable of dicts of strings.

    NOTHING IS COERCED HERE OR ANYWHERE ELSE. A cell that should be a whole
    number and is not is named with its row and its value, rather than being
    read as zero, rounded, or skipped.
    """
    problems = []
    numeric = {c.name: c for c in contract.columns
               if c.kind in (WHOLE_NUMBER, OPTIONAL_WHOLE_NUMBER)}
    for position, row in enumerate(rows, start=1):
        for name, column in numeric.items():
            if name not in row:
                continue
            raw = (row[name] or "").strip()
            if raw == "":
                if column.kind == OPTIONAL_WHOLE_NUMBER:
                    continue
                problems.append(Problem(
                    severity=BLOCKING, file=file_name, column=name,
                    row=position, says="this cell is blank.",
                    fix=(f"It is required and must be a whole number: "
                         f"{column.means}.")))
                continue
            try:
                int(raw)
            except ValueError:
                problems.append(Problem(
                    severity=BLOCKING, file=file_name, column=name,
                    row=position, says=f"{raw!r} is not a whole number.",
                    fix=(f"This column holds {column.means}. Nothing here "
                         f"rounds a decimal or reads a blank as zero.")))
    return problems


def check_dataset(data_dir, read_rows):
    """Every file in the contract, against a directory. Returns a `Report`.

    `read_rows` is injected so this module opens nothing itself: it decides what
    is wrong, and `readers` decides how a CSV becomes rows. Keeping the two
    apart is what lets the contract be checked against an upload held in memory
    and against a directory on disk with one implementation.
    """
    report = Report()
    for contract in CONTRACT:
        path = data_dir / contract.name
        if not path.exists():
            if contract.required:
                report.problems.append(Problem(
                    severity=BLOCKING, file=contract.name,
                    says="required file is missing.",
                    fix=f"It holds {contract.describes}."))
            continue
        headers, rows = read_rows(path)
        problems, notices = check_headers(contract.name, contract, headers)
        report.problems.extend(problems)
        report.notices.extend(notices)
        # Cells are only worth checking once the headers are right: a file with
        # the wrong columns would otherwise report one problem per row about
        # columns the user is about to rename anyway.
        if not problems:
            report.problems.extend(check_cells(contract.name, contract, rows))
    return report
