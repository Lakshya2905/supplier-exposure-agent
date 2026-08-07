"""The clean world: a fully consistent dataset with no messiness at all.

Every part has suppliers, every part-supplier pair has a lead time, every
finished good has demand, every name is canonical. Messiness is applied
afterwards as explicit damage, so "all rates zero" is a real, testable state
rather than an aspiration.

Acyclicity is by construction, not by check: parts are assigned a level and
edges only ever run from level n to level n-1. A cycle would make stage 2's
traversal hang rather than fail, which is the worst way for it to break.
"""
from datetime import datetime, timedelta

from .config import FINISHED_GOOD_VOLUMES, REGIONS
from .model import (FG_PREFIX, PART_PREFIX, SUPPLIER_PREFIX, TOOLING_COMPANY,
                    TOOLING_SUPPLIER, LeadTime, Part, SourceExtract, Supplier,
                    SupplierLink, World)
from .verdicts import BUY, MAKE, VERIFIED

ADJECTIVES = ("Axial", "Beveled", "Cast", "Damped", "Etched", "Forged",
              "Guided", "Hardened", "Inline", "Keyed", "Laminated", "Milled")
NOUNS = ("Bracket", "Bushing", "Collar", "Damper", "Elbow", "Flange",
         "Gasket", "Housing", "Insert", "Journal", "Knuckle", "Lever")
SUPPLIER_STEMS = ("Northwind", "Braxton", "Calder", "Deepwater", "Eastvale",
                  "Fairmont", "Glenmoor", "Harrowgate", "Ironside", "Jasper",
                  "Kestrel", "Lindholm", "Marrow", "Norbury", "Oakhaven",
                  "Pellworth", "Quillon", "Ravensford", "Stanmore", "Thackery",
                  "Underhill", "Vantage", "Westmere", "Yarrow")
SUPPLIER_SUFFIXES = ("Corporation", "Industries", "Manufacturing", "Works")


def _part_number(index):
    return f"{PART_PREFIX}{index:04d}"


def _fg_number(index):
    return f"{FG_PREFIX}{index:02d}"


def build_suppliers(rng, config):
    """The canonical supplier registry. One identity, one canonical name."""
    suppliers = {}
    stems = list(SUPPLIER_STEMS)
    rng.shuffle(stems)
    for i in range(config.n_suppliers_pool):
        stem = stems[i % len(stems)]
        suffix = rng.choice(SUPPLIER_SUFFIXES)
        supplier_id = f"{SUPPLIER_PREFIX}{i:03d}"
        suppliers[supplier_id] = Supplier(
            supplier_id=supplier_id,
            canonical_name=f"{stem} {suffix}",
            region=rng.choice(REGIONS),
        )
    return suppliers


def build_bom(rng, config):
    """Finished goods, subassemblies and leaves, wired downward only.

    Guarantees, because stages 2 and 4 need them and random wiring will not
    reliably produce them:
      - at least `min_parts_under_two_finished_goods` parts sit under two
        different finished goods, so blast radius has a real case
      - at least `min_parts_at_two_depths` part appears at two different
        depths under different parents, which is what breaks the likely
        stage-2 bug of treating depth as a property of the part
    """
    world = World()
    n_fg = config.n_finished_goods
    remaining = config.n_parts_target - n_fg
    n_leaf = int(remaining * 0.7)
    n_sub = remaining - n_leaf

    for i in range(n_fg):
        pn = _fg_number(i)
        world.finished_goods.append(pn)
        world.parts[pn] = Part(pn, f"Finished Good {i + 1}", MAKE, level=0)

    subs = []
    for i in range(n_sub):
        pn = _part_number(i)
        subs.append(pn)
        world.parts[pn] = Part(pn, _describe(rng), MAKE, level=1)

    leaves = []
    for i in range(n_leaf):
        pn = _part_number(n_sub + i)
        leaves.append(pn)
        world.parts[pn] = Part(pn, _describe(rng), BUY, level=2)

    # every subassembly hangs off exactly one finished good, round robin so no
    # finished good ends up empty
    for i, sub in enumerate(subs):
        parent = world.finished_goods[i % n_fg]
        world.bom.append((parent, sub, rng.randint(1, 4)))

    # every leaf hangs off at least one subassembly
    for i, leaf in enumerate(leaves):
        world.bom.append((subs[i % len(subs)], leaf, rng.randint(1, 6)))

    _guarantee_shared_parts(rng, world, config, subs, leaves, n_fg)
    _guarantee_two_depths(rng, world, leaves)
    return world


def _guarantee_shared_parts(rng, world, config, subs, leaves, n_fg):
    """Force common parts across DIFFERENT finished goods.

    A part shared between two parents inside one finished good does not
    exercise blast radius; a part shared across finished goods does.
    """
    subs_by_fg = {}
    for parent, child, _ in world.bom:
        if parent in world.finished_goods:
            subs_by_fg.setdefault(parent, []).append(child)

    needed = max(config.min_parts_under_two_finished_goods,
                 config.min_parts_shared_with_absent_fg)
    for i in range(needed):
        leaf = leaves[i]
        # attach this leaf under a subassembly of every finished good, which
        # puts it under all of them including the absent-demand one
        for fg in world.finished_goods[:n_fg]:
            sub = subs_by_fg[fg][0]
            if not any(p == sub and c == leaf for p, c, _ in world.bom):
                world.bom.append((sub, leaf, rng.randint(1, 3)))


def _guarantee_two_depths(rng, world, leaves):
    """One part that appears at two different depths.

    Hung directly off a finished good as well as under a subassembly, so its
    depth is a property of the path and not of the part. This is the case that
    breaks a stage-2 explosion that memoises depth per part.
    """
    leaf = leaves[-1]
    world.bom.append((world.finished_goods[0], leaf, 1))


def _describe(rng):
    return f"{rng.choice(ADJECTIVES)} {rng.choice(NOUNS)}"


def build_sourcing(rng, config, world):
    """Suppliers, links and lead times, all complete and all canonical.

    Only `buy` parts get suppliers here. Make parts with suppliers are a
    contradiction, and contradictions are damage, so messiness adds them.
    """
    supplier_ids = list(world.suppliers)
    for part in world.parts.values():
        if part.source_type != BUY:
            continue
        part.sourcing_list_status = VERIFIED
        n = rng.choices((1, 2, 3), weights=(0.30, 0.45, 0.25))[0]
        chosen = rng.sample(supplier_ids, n)
        for supplier_id in chosen:
            world.links.append(SupplierLink(
                part_number=part.part_number,
                supplier_id=supplier_id,
                qualification_date=_qual_date(rng),
            ))
            quoted = rng.randint(config.lead_time_min_days,
                                 config.lead_time_max_days)
            low, high = config.lead_time_p95_uplift
            world.lead_times.append(LeadTime(
                part_number=part.part_number,
                supplier_id=supplier_id,
                quoted_lead_time_days=quoted,
                lead_time_p95_days=int(quoted * rng.uniform(low, high)),
            ))
    return world


def _qual_date(rng):
    return (f"20{rng.randint(18, 25):02d}-"
            f"{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}")


def build_part_attributes(rng, config, world):
    """On-hand, tooling and spend. All present and sane at this stage."""
    for part in world.parts.values():
        part.on_hand_units = rng.randint(20, 4000)
        part.tooling_owner = (TOOLING_SUPPLIER if rng.random() < 0.30
                              else TOOLING_COMPANY)
        part.annual_spend_usd = rng.randint(2_000, 900_000)
    return world


def build_demand(rng, config, world):
    """Annual units per finished good, spread rather than flat."""
    for i, fg in enumerate(world.finished_goods):
        volumes = FINISHED_GOOD_VOLUMES
        world.demand[fg] = volumes[i] if i < len(volumes) else volumes[-1]
    return world


def build_extracts(config, world):
    """The extract manifest: which system each file came out of, and when.

    Derived from the config's anchor and per-file lags rather than from a clock,
    so a second build at the same seed produces the same bytes. Sorted by file
    name because a manifest ordered by lag would put the freshest extract first
    and read as a ranking of the sources.
    """
    anchor = datetime.fromisoformat(config.extract_anchor)
    world.sources = [
        SourceExtract(
            source_file=name,
            system_of_record=config.system_of_record[name],
            retrieved_at=(anchor - timedelta(
                hours=config.extract_lag_hours[name])).isoformat())
        for name in sorted(config.system_of_record)
    ]
    return world


def build_clean_world(rng, config):
    world = build_bom(rng, config)
    world.suppliers = build_suppliers(rng, config)
    build_sourcing(rng, config, world)
    build_part_attributes(rng, config, world)
    build_demand(rng, config, world)
    build_extracts(config, world)
    return world
