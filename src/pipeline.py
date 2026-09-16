"""End to end, from CSVs on disk to the three review surfaces.

Reads only what a real consumer would have: the six CSVs, plus
`recovery_inputs.csv` where somebody has supplied one. It never touches the
answer key, so the verdicts here come from `identify()` on observed data rather
than from what the generator intended. That distinction matters, because a
runner that quietly read truth would make the interface look correct while
testing nothing.
"""
import collections
from dataclasses import dataclass
from pathlib import Path

from . import archetypes as A
from . import criticality as crit
from . import ranking
from .concentration import analyse, fill_profiles
from .demand import usage_by_part
from .explosion import explode, rows_by_part
from .identify import identify_all
from .interface import model as view
from .commitments import COMMITMENTS_FILE
from .contract import ContractError
from .readers import (read_bom, read_commitments, read_demand_plan,
                      read_demand_rows, read_lead_times, read_part_master,
                      read_recovery_inputs, read_sources,
                      read_sub_tier_sources, read_suppliers, validate)
from .recovery import RECOVERY_INPUTS_FILE
from .subtier import SUB_TIER_FILE, tiers_for
from .scoring import score_part
from .synthetic import verdicts as V


# THREE DIRECTORIES, THREE RULES, AND THEY ARE NOT INTERCHANGEABLE.
#
#   evals/   FROZEN and GATED. Inputs and the answer key, committed in one
#            commit under a manifest, never regenerated. Correctness is measured
#            against this and nothing else.
#   data/    GITIGNORED and REGENERATED from the documented seed. What a
#            developer and CI work against.
#   demo/    COMMITTED FOR DISPLAY ONLY. Generated from the same seed, committed
#            so a cold container has something to render on first page load. It
#            is never read by the harness or by any test, because a dataset that
#            exists to be looked at must not also be a thing correctness is
#            judged against.
WORKING_DIR = Path("data")
DEMO_DIR = Path("demo")


def default_data_dir():
    """`data/` when it exists, otherwise the committed demo set.

    The preference matters: under test and in CI `data/` is always present, so
    the fallback never fires and `demo/` stays out of every correctness path.
    """
    return WORKING_DIR if (WORKING_DIR / "bom.csv").exists() else DEMO_DIR


@dataclass(frozen=True)
class SourcingInputs:
    """What `identify()` was given, per part, so it can be asked again."""
    part_master: dict
    supplier_names: dict
    lead_time_names: dict


@dataclass(frozen=True)
class Result:
    verdicts: dict
    profiles: dict
    report: object
    evidence: dict
    memberships: dict
    catalogue: tuple
    thresholds: object
    # The extract manifest, so a surface can state which systems this run read
    # and when they were pulled without reopening an evidence panel.
    extracts: dict = None
    data_dir: object = None
    # Which parts this run assessed and which it did not. Present even on an
    # unscoped run, where it records that nothing was left out, because "we
    # assessed everything" is a claim a reader should be able to see made.
    scope: object = None
    # THE INPUTS THAT PRODUCED THE VERDICTS, kept so a counterfactual can be
    # computed by the SAME function that computed the actual one. `scenario.py`
    # asks what the verdict would be with one supplier removed, and the only
    # honest way to answer is to call `identify()` again with a shorter list
    # rather than to reason about the answer it already gave. Reconstructing
    # these from the evidence panel would be a second derivation of an input,
    # and the two would drift.
    sourcing_inputs: object = None


def _dependencies(verdicts, suppliers, lead_times):
    """The supplier each exposed part actually DEPENDS on.

    For a single source that is its one supplier; for a hidden single source it
    is the one that can actually quote. By the definition of those verdicts each
    exposed part has exactly one, which is what makes both groupings
    single-valued.
    """
    from .normalise import canonical_key

    dependencies = collections.defaultdict(list)
    for part, rows in suppliers.items():
        quotable = {canonical_key(name)
                    for name, _, _, _ in lead_times.get(part, ())}
        for name, region, _row in rows:
            if (verdicts.get(part) == V.HIDDEN_SINGLE_SOURCE
                    and canonical_key(name) not in quotable):
                continue
            dependencies[part].append((name, region))
    return dict(dependencies)


def run(data_dir=None, config_path="config/archetypes.yaml", criticality=None,
        check_contract=True):
    """Score a dataset, optionally scoped to a set of criticality labels.

    `criticality` is a SET OF LABELS to assess, or None for everything. See
    `criticality.py` for why it is a set rather than a cut-off, and why the
    default is the inclusive one.

    THE SCOPE FILTERS WHAT IS PRESENTED, NOT WHAT CORRELATION IS COMPUTED OVER.
    Two parts share a supplier whether or not somebody scoped this run to one of
    them, so clusters are built from every exposed part and their membership may
    name parts this run did not assess. The alternative understates shared
    exposure in proportion to how tightly a reviewer scoped, which is the error
    direction this system refuses everywhere else: a missed correlation reads as
    independence, and independence is the reassuring answer.
    """
    data_dir = Path(data_dir) if data_dir is not None else default_data_dir()

    # THE CONTRACT IS CHECKED BEFORE ANYTHING IS READ, and it raises rather than
    # scoring what it can. A header spelled `parent` instead of `parent_part`
    # used to surface as `KeyError: 'parent_part'` from inside pandas: the
    # column name, with no file, no row and no statement of what the column is
    # for. `check_contract=False` exists for a caller that has already checked,
    # and for nothing else: it is not a way to score data the contract refuses.
    if check_contract:
        report = validate(data_dir)
        if not report.ok:
            raise ContractError(report)

    edges = read_bom(data_dir / "bom.csv")
    parts = read_part_master(data_dir / "part_master.csv")
    demand = read_demand_plan(data_dir / "demand_plan.csv")
    suppliers = read_suppliers(data_dir / "suppliers.csv")
    lead_times = read_lead_times(data_dir / "lead_times.csv")
    extracts = read_sources(data_dir / "sources.csv")
    demand_row_numbers = read_demand_rows(data_dir / "demand_plan.csv")
    # OPTIONAL, and absent from every dataset this repository generates. A
    # missing file is not an empty plan: it means nobody has timed a single
    # stage of the resourcing chain, and `resource_days` reports that rather
    # than a chain of zeroes.
    recovery_stages = read_recovery_inputs(data_dir / RECOVERY_INPUTS_FILE)
    # ALSO OPTIONAL. Absent, no tier grouping is built and every other reading
    # is unchanged; present, it makes visible the correlation where two
    # different companies turn out to be one supplier a hop down.
    sub_tier_sources = read_sub_tier_sources(data_dir / SUB_TIER_FILE)
    # None where no order book exists, which is NOT an empty order book. See
    # `readers.read_commitments`.
    commitments = read_commitments(data_dir / COMMITMENTS_FILE)

    rows = rows_by_part(explode(edges, known_parts=set(parts)))
    usage = usage_by_part(rows, demand)

    part_master = {part: (record["source_type"],
                          record["sourcing_list_status"])
                   for part, record in parts.items()}
    supplier_names = {part: [name for name, _, _ in entries]
                      for part, entries in suppliers.items()}
    lead_time_names = {part: [name for name, _, _, _ in entries]
                       for part, entries in lead_times.items()}
    findings = identify_all(part_master, supplier_names, lead_time_names)
    sourcing_inputs = SourcingInputs(
        part_master=part_master, supplier_names=supplier_names,
        lead_time_names=lead_time_names)
    verdicts = {finding.subject: finding.verdict for finding in findings}

    dependencies = _dependencies(verdicts, suppliers, lead_times)
    report = analyse(verdicts, dependencies,
                     tiers=tiers_for(
                         {part: [name for name, _ in pairs]
                          for part, pairs in dependencies.items()},
                         sub_tier_sources))

    profiles = {}
    for part, record in sorted(parts.items()):
        if part not in rows:
            continue
        profiles[part] = score_part(
            part_number=part, verdict=verdicts.get(part, ""), rows=rows[part],
            usage=usage[part], on_hand_units=record["on_hand_units"],
            tooling_owner=record["tooling_owner"],
            lead_times=[(quoted, p95)
                        for _, quoted, p95, _ in lead_times.get(part, ())],
            recovery_stages=recovery_stages.get(part),
            commitments=commitments)
    profiles = fill_profiles(profiles, report)

    # SCOPED AFTER SCORING, not before. Explosion needs the whole tree to reach
    # a finished good, demand needs every parent, and correlation needs every
    # exposed part; a filter applied at the top would quietly change all three.
    # OVER THE SCOREABLE PARTS, not the whole part master. A finished good has
    # no supplier and is never scored, so counting it as "not assessed because
    # of the scope" would blame the scope for an exclusion the BOM already made.
    scope = crit.scope_for({part: parts[part] for part in profiles},
                           criticality)
    in_scope = set(scope.parts_in_scope)
    profiles = {part: profile for part, profile in profiles.items()
                if part in in_scope}

    evidence = {
        part: view.evidence_for(part, suppliers.get(part, ()), rows[part],
                                demand, lead_times.get(part, ()), extracts,
                                demand_row_numbers)
        for part in profiles
    }

    thresholds = A.load_thresholds(config_path)
    catalogue = A.catalogue(thresholds)
    memberships = ranking.classify(list(profiles.values()), verdicts, catalogue)

    return Result(verdicts=verdicts, profiles=profiles, report=report,
                  evidence=evidence, memberships=memberships,
                  catalogue=catalogue, thresholds=thresholds,
                  extracts=extracts, data_dir=data_dir, scope=scope,
                  sourcing_inputs=sourcing_inputs)


def surfaces(result):
    return {
        view.EXPOSURE: view.exposure_surface(
            list(result.profiles.values()), result.verdicts, result.catalogue,
            result.evidence, report=result.report,
            thresholds=result.thresholds),
        view.FIND_OUT: view.find_out_surface(result.memberships,
                                             result.catalogue),
        view.CONFIRM: view.confirm_surface(result.report),
    }
