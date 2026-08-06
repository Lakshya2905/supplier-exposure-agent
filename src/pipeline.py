"""End to end, from CSVs on disk to the three review surfaces.

Reads only what a real consumer would have: the five CSVs. It never touches the
answer key, so the verdicts here come from `identify()` on observed data rather
than from what the generator intended. That distinction matters, because a
runner that quietly read truth would make the interface look correct while
testing nothing.
"""
import collections
from dataclasses import dataclass
from pathlib import Path

from . import archetypes as A
from . import ranking
from .concentration import analyse, fill_profiles
from .demand import usage_by_part
from .explosion import explode, rows_by_part
from .identify import identify_all
from .interface import model as view
from .readers import (read_bom, read_demand_plan, read_demand_rows,
                      read_lead_times, read_part_master, read_sources,
                      read_suppliers)
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
class Result:
    verdicts: dict
    profiles: dict
    report: object
    evidence: dict
    memberships: dict
    catalogue: tuple
    thresholds: object


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


def run(data_dir=None, config_path="config/archetypes.yaml"):
    data_dir = Path(data_dir) if data_dir is not None else default_data_dir()
    edges = read_bom(data_dir / "bom.csv")
    parts = read_part_master(data_dir / "part_master.csv")
    demand = read_demand_plan(data_dir / "demand_plan.csv")
    suppliers = read_suppliers(data_dir / "suppliers.csv")
    lead_times = read_lead_times(data_dir / "lead_times.csv")
    extracts = read_sources(data_dir / "sources.csv")
    demand_row_numbers = read_demand_rows(data_dir / "demand_plan.csv")

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
    verdicts = {finding.subject: finding.verdict for finding in findings}

    report = analyse(verdicts, _dependencies(verdicts, suppliers, lead_times))

    profiles = {}
    for part, record in sorted(parts.items()):
        if part not in rows:
            continue
        profiles[part] = score_part(
            part_number=part, verdict=verdicts.get(part, ""), rows=rows[part],
            usage=usage[part], on_hand_units=record["on_hand_units"],
            tooling_owner=record["tooling_owner"],
            lead_times=[(quoted, p95)
                        for _, quoted, p95, _ in lead_times.get(part, ())])
    profiles = fill_profiles(profiles, report)

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
                  catalogue=catalogue, thresholds=thresholds)


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
