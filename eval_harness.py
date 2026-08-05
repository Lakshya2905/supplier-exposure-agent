"""The ship gate. One command, locally and in CI, so the two cannot diverge.

    python eval_harness.py

THREE LAYERS WITH DIFFERENT EPISTEMIC STATUS, and conflating them is the trap
this file exists to avoid:

  1  CORRECTNESS against an independent oracle. The frozen answer key records
     what the generator DECIDED, which the analysis never sees, so agreement
     means something. Gates.
  2  INVARIANTS. Properties that must hold on any input, asserted rather than
     snapshotted: no finding meaning "nobody can tell" executes, no measure
     without a unit, no unrendered event kind. These are the project's claims.
     Gates.
  3  A REGRESSION SNAPSHOT, which is NOT a floor and is NEVER called one. It is
     produced by the current system, so it tests only that the system agrees
     with itself. It detects change and asserts nothing. Reported, never gates.

A number the system produced cannot also be the standard it is judged against.

WHEN A FLOOR IS MISSED the report is written so that lowering the floor is the
least attractive option on the table: it prints the derivation beside the miss,
names the specific failing items rather than an aggregate, states the claim
about the world that would have to be false for the floor to be wrong, and
NEVER suggests a replacement value. A harness that offers "consider 0.93" has
made the decision and left the human to ratify it.
"""
import collections
import json
import subprocess
import sys
from pathlib import Path

from src.frozen import (ANSWER_KEY, INPUTS, MANIFEST, MANIFEST_LIMIT,
                        check_manifest)
from src import archetypes as A
from src import concentration, floors, governance as gov, ranking, scoring
from src.demand import usage_by_part
from src.explosion import explode, rows_by_part
from src.governance.render import render
from src.grading import grade_pairs
from src.identify import DEFAULT_THRESHOLD, identify_all
from src.interface import model as view
from src.pipeline import run, surfaces
from src.readers import (read_bom, read_demand_plan, read_lead_times,
                         read_part_master, read_suppliers)

RULE = "-" * 74

# Paths the primary dataset structurally cannot exercise. Printed rather than
# left in a document, so the gap is visible where somebody reads the result.
NOT_COVERED = (
    ("supplier_only concentration",
     "every supplier has exactly one region, so a multinational cannot be "
     "represented and supplier concentration always implies region "
     "concentration"),
    ("the merge-uncertain exception lane",
     "the normaliser resolves every name pair in this dataset at the shipped "
     "threshold, so no merge is uncertain"),
    ("bounded and contingent clusters",
     "same cause as above: no uncertain merge reaches a cluster"),
)


class Report:
    def __init__(self):
        self.failures = []
        self.lines = []

    def say(self, text=""):
        self.lines.append(text)

    def heading(self, text):
        self.say()
        self.say(text)
        self.say(RULE)

    def floor(self, floor, measured, failing=()):
        ok = floor.holds(measured)
        self.say(f"  {'PASS' if ok else 'FAIL'}  {floor.name}")
        self.say(f"        {floor.render(measured)}")
        if not ok:
            self.failures.append(floor.name)
            self.say(f"        why this floor exists: {floor.derivation}")
            self.say(f"        it would be wrong only if {floor.wrong_if}")
            if failing:
                self.say("        failing items:")
                for item in list(failing)[:20]:
                    self.say(f"          {item}")
                if len(failing) > 20:
                    self.say(f"          ... and {len(failing) - 20} more")
        return ok

    def emit(self):
        print("\n".join(self.lines))


def load_frozen():
    """Read the frozen set exactly as a consumer would. The generator is never
    imported here, and a source scan in the tests asserts it."""
    parts = read_part_master(INPUTS / "part_master.csv")
    suppliers = read_suppliers(INPUTS / "suppliers.csv")
    lead_times = read_lead_times(INPUTS / "lead_times.csv")
    key = json.loads(ANSWER_KEY.read_text())
    return parts, suppliers, lead_times, key


def measure(report):
    """Layers 1 and 2. Returns the snapshot for layer 3."""
    parts, suppliers, lead_times, key = load_frozen()
    result = run(data_dir=INPUTS)

    # ------------------------------------------------ layer 1, correctness --
    report.heading("LAYER 1  correctness against the frozen answer key")

    expected = key["verdicts"]
    wrong = [f"{part}: read {verdict}, key says {expected[part]}"
             for part, verdict in sorted(result.verdicts.items())
             if expected.get(part) != verdict]
    accuracy = 1.0 - len(wrong) / max(len(expected), 1)
    report.floor(floors.VERDICT_ACCURACY, accuracy, wrong)

    graded = grade_pairs(key["supplier_variants"], DEFAULT_THRESHOLD)
    report.floor(floors.NAME_MATCH_PRECISION, graded["precision"],
                 [f"merged but distinct: {a!r} and {b!r}"
                  for a, b in graded["false_positive"]])
    report.floor(floors.NAME_MATCH_RECALL, graded["recall"],
                 [f"not merged but identical: {a!r} and {b!r}"
                  for a, b in graded["false_negative"]])

    intents = key["intents"]
    missing_on_hand = {p for p, kinds in intents.items()
                       if "on_hand_unknown" in kinds and p in result.profiles}
    missing_tooling = {p for p, kinds in intents.items()
                       if "tooling_unknown" in kinds and p in result.profiles}
    cover_abstains = {p for p, prof in result.profiles.items()
                      if prof.buffer_cover.completeness == scoring.CANNOT_TELL}
    tooling_abstains = {p for p, prof in result.profiles.items()
                        if prof.portability.completeness == scoring.CANNOT_TELL}
    gaps = ([f"{p}: no on-hand record but cover did not abstain"
             for p in sorted(missing_on_hand - cover_abstains)] +
            [f"{p}: no tooling owner but portability did not abstain"
             for p in sorted(missing_tooling - tooling_abstains)] +
            [f"{p}: portability abstained with a tooling owner on file"
             for p in sorted(tooling_abstains - missing_tooling)])
    checked = len(missing_on_hand) + len(missing_tooling) + len(tooling_abstains)
    report.floor(floors.ABSTENTION_SET_EQUALITY,
                 1.0 - len(gaps) / max(checked, 1), gaps)

    # -------------------------------------------------- layer 2, invariants --
    report.heading("LAYER 2  invariants that must hold on any input")

    violations = [
        f"{f.subject}: verdict {f.verdict} but autonomy {f.autonomy}"
        for f in identify_all(
            {p: (r["source_type"], r["sourcing_list_status"])
             for p, r in parts.items()},
            {p: [n for n, _ in rows] for p, rows in suppliers.items()},
            {p: [n for n, _, _ in rows] for p, rows in lead_times.items()})
        if f.verdict == "readings_disagree" and f.autonomy == gov.EXECUTES]
    violations += [
        f"{p}: concentration executed"
        for p, prof in sorted(result.profiles.items())
        if prof.concentration is not None
        and prof.concentration.autonomy != gov.RECOMMENDS]
    report.floor(floors.AUTONOMY_VIOLATIONS, len(violations), violations)

    edges = read_bom(INPUTS / "bom.csv")
    structural = []
    try:
        exploded = explode(edges, known_parts=set(parts))
        reached = {row.part_number for row in exploded}
        for part in sorted(set(parts) - reached):
            if any(part == parent for parent, _, _ in edges):
                continue
            structural.append(f"{part}: in the part master, reaches no "
                              f"finished good")
    except Exception as failure:                      # noqa: BLE001
        structural.append(f"explosion refused the BOM: {failure}")
    for _, region in [pair for rows in suppliers.values() for pair in rows]:
        if region != region.strip() or region.lower() == "nan":
            structural.append(f"region read as a null: {region!r}")
    report.floor(floors.STRUCTURAL_GUARANTEES,
                 1.0 if not structural else 0.0, structural)

    bad_units = [f"{p}.{sc.dimension}: unit {sc.unit!r}"
                 for p, prof in sorted(result.profiles.items())
                 for sc in prof.all_scores() if sc.unit not in scoring.UNITS]
    report.floor(floors.UNIT_VIOLATIONS, len(bad_units), bad_units)

    unrendered = []
    for kind in gov.EVENT_KINDS:
        event = gov.DecisionEvent(
            event_id=1, at="1970-01-01T00:00:00+00:00",
            status=gov.STATUS_PROPOSED, sku_id="PROBE", kind=kind,
            evidence={"members": ["PROBE"], "basis": "supplier",
                      "reasons": ["probe"]})
        if not (render(event) or "").strip().endswith("."):
            unrendered.append(f"event kind {kind!r} renders nothing usable")
    for reason in gov.REASON_CODES:
        event = gov.DecisionEvent(
            event_id=1, at="1970-01-01T00:00:00+00:00",
            status=gov.STATUS_APPROVED, sku_id="PROBE",
            decided_by="probe", reason_code=reason,
            kind=gov.KIND_HUMAN_DECISION, evidence={})
        if reason not in render(event):
            unrendered.append(f"reason code {reason!r} does not appear")
    total = len(gov.EVENT_KINDS) + len(gov.REASON_CODES)
    report.floor(floors.RENDERER_COVERAGE,
                 1.0 - len(unrendered) / total, unrendered)

    return result


def snapshot(report, result):
    """Layer 3. NOT A FLOOR. Detects change, asserts nothing."""
    report.heading("SNAPSHOT  not a floor, not gated, produced by the system "
                   "under test")
    report.say("  These counts are properties of seed 42's data rather than of")
    report.say("  the tool. A number the system produced cannot also be the")
    report.say("  standard it is judged against, so nothing here blocks a")
    report.say("  merge. If one moves, read the diff and decide whether the")
    report.say("  change was intended.")
    report.say()

    built = surfaces(result)
    results = [sc for prof in result.profiles.values()
               for sc in prof.all_scores()]
    counts = {
        "parts scored": len(result.profiles),
        "dimension results": len(results),
        "executing": sum(1 for sc in results if sc.autonomy == gov.EXECUTES),
        "deferring": sum(1 for sc in results if sc.autonomy == gov.RECOMMENDS),
        "clusters concentrated": len(result.report.concentrated()),
        "parts in the global caveat": len(result.report.unplaceable_parts),
        "fields in the work queue": len(built[view.FIND_OUT].rows),
    }
    for state, count in sorted(collections.Counter(
            sc.completeness for sc in results).items()):
        counts[f"completeness {state}"] = count
    for name, count in counts.items():
        report.say(f"  {count:>6}  {name}")
    return counts


def not_covered(report):
    report.heading("NOT COVERED  paths this dataset structurally cannot reach")
    for name, reason in NOT_COVERED:
        report.say(f"  {name}")
        report.say(f"        {reason}")
    report.say()
    report.say("  A second frozen scenario would exercise these. What it has to")
    report.say("  contain, and what it must not do, is in docs/EVAL_SCENARIO.md.")
    report.say("  Its numbers would stay diagnostic and are never promoted into")
    report.say("  the floors above.")


def run_tests(report):
    report.heading("TESTS")
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header"],
        capture_output=True, text=True)
    tail = [line for line in completed.stdout.strip().splitlines() if line][-1:]
    for line in tail:
        report.say(f"  {line}")
    if completed.returncode != 0:
        report.failures.append("test suite")
        report.say("  the suite is not green; the floors below are measured on "
                   "code that is failing its own tests")
        for line in completed.stdout.strip().splitlines():
            if line.startswith(("FAILED", "ERROR", "SUBFAIL")):
                report.say(f"    {line}")
    report.say()
    report.say("  xfail_strict is on: a KNOWN GAP that gets fixed reports XPASS")
    report.say("  and FAILS this gate, so a gap cannot be closed silently.")
    return completed.returncode == 0


def check_frozen(report):
    report.heading("MANIFEST")
    ok, problems = check_manifest()
    recorded = (json.loads(MANIFEST.read_text())["files"]
                if MANIFEST.exists() else {})
    report.say(f"  {len(recorded)} frozen files checked against {MANIFEST}")
    for problem in problems:
        report.say(f"  {problem}")
    if not ok:
        report.failures.append("frozen eval set")
    report.say()
    report.say(f"  LIMIT: {MANIFEST_LIMIT}")
    return ok


def main():
    report = Report()
    report.say("SUPPLIER EXPOSURE AGENT: SHIP GATE")
    report.say(f"frozen eval set at {INPUTS}, seed 42")

    intact = check_frozen(report)
    run_tests(report)
    if intact:
        result = measure(report)
        snapshot(report, result)
    else:
        report.heading("FLOORS")
        report.say("  not measured: the frozen set failed its manifest check, "
                   "so any number taken from it would be meaningless")
    not_covered(report)

    report.say()
    report.say(RULE)
    if report.failures:
        report.say("SHIP GATE: FAIL")
        report.say(f"  blocked by: {', '.join(report.failures)}")
        report.say("  The correct response to a missed floor is a finding about")
        report.say("  the system. No replacement value is suggested here, on")
        report.say("  purpose: a harness that proposes one has made the")
        report.say("  decision and left you to ratify it.")
    else:
        report.say("SHIP GATE: PASS")
    report.emit()
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
