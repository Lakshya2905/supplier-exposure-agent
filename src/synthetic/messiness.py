"""Damage applied to a clean world, each operation recording what it did.

Nothing here invents data. Every operation removes a record, contradicts a
record, or renders a name differently, and writes that decision into the answer
key. With every rate at zero, nothing runs and the answer key stays empty.
"""
import random

from .model import LeadTime, SupplierLink, TOOLING_COMPANY, TOOLING_SUPPLIER
from .verdicts import BLANK, BUY, MAKE, UNVERIFIED, VERIFIED

ABBREVIATIONS = {
    "Corporation": "Corp",
    "Industries": "Inds",
    "Manufacturing": "Mfg",
    "Works": "Wks",
}


def name_variants(canonical, rng):
    """Plausible ways the same supplier gets typed into different systems."""
    out = {canonical}
    for long, short in ABBREVIATIONS.items():
        if long in canonical:
            out.add(canonical.replace(long, short))
            out.add(canonical.replace(long, short + "."))
    out.add(canonical.upper())
    out.add(canonical.lower())
    out.add(canonical.replace(" ", "  "))
    out.add(canonical + " ")
    return sorted(out)


def render_supplier_names(rng, config, world, truth):
    """Choose the string each link shows, per file.

    Cross-file divergence is the point. If a supplier is spelled the same way
    in suppliers.csv and lead_times.csv then an exact-string join works and the
    whole canonical registry buys nothing, so a configured fraction of links
    are deliberately spelled differently in the two files.
    """
    for link in world.links:
        canonical = world.suppliers[link.supplier_id].canonical_name
        variants = name_variants(canonical, rng)

        if rng.random() < config.supplier_name_variant_rate:
            in_suppliers = rng.choice(variants)
        else:
            in_suppliers = canonical

        if rng.random() < config.cross_file_name_divergence_rate:
            others = [v for v in variants if v != in_suppliers]
            in_lead_times = rng.choice(others) if others else in_suppliers
            truth.record_divergence(link.part_number, link.supplier_id,
                                    in_suppliers, in_lead_times)
        else:
            in_lead_times = in_suppliers

        link.name_in_suppliers = in_suppliers
        link.name_in_lead_times = in_lead_times
        truth.record_variant(in_suppliers, link.supplier_id)
        truth.record_variant(in_lead_times, link.supplier_id)


def add_confusable_suppliers(rng, config, world, truth):
    """Two genuinely DIFFERENT suppliers with near-identical names.

    The mirror image of the variant trap. Without this, a stage-2 matcher that
    collapses anything similar looks correct; with it, over-eager fuzzy
    matching is caught rather than rewarded.
    """
    ids = list(world.suppliers)
    for i in range(config.n_confusable_supplier_pairs):
        base = world.suppliers[ids[i]]
        twin_id = f"{base.supplier_id}-B"
        stem = base.canonical_name.split()[0]
        twin_name = f"{stem} Holdings"
        world.suppliers[twin_id] = type(base)(
            supplier_id=twin_id, canonical_name=twin_name,
            region=base.region)
        truth.record_confusable(base.supplier_id, twin_id,
                                base.canonical_name, twin_name)


def drop_lead_times(rng, config, world, truth):
    """Some part-supplier pairs simply have no lead time on file."""
    survivors = []
    for lt in world.lead_times:
        if rng.random() < config.missing_lead_time_rate:
            truth.record_omitted_lead_time(lt.part_number, lt.supplier_id)
        else:
            survivors.append(lt)
    world.lead_times = survivors


def make_hidden_single_sources(rng, config, world, truth):
    """Parts with several suppliers on paper but only one usable.

    Chosen from parts that currently have two or more lead times, then trimmed
    to exactly one. This is the case the brief calls out by name.
    """
    candidates = [pn for pn, part in world.parts.items()
                  if part.source_type == BUY
                  and len(world.lead_times_for(pn)) >= 2]
    rng.shuffle(candidates)
    for part_number in candidates[:config.n_hidden_single_source]:
        keep = rng.choice(world.lead_times_for(part_number))
        for lt in world.lead_times_for(part_number):
            if lt is not keep:
                world.lead_times.remove(lt)
                truth.record_omitted_lead_time(lt.part_number, lt.supplier_id)
        truth.record_intent(part_number, "hidden_single_source")


def make_zero_supplier_parts(rng, config, world, truth):
    """Buy parts with no supplier rows at all.

    Verified means somebody checked and found none, which is a real and serious
    finding. Unverified means nobody checked, which is an unknown. The two look
    identical in the data without sourcing_list_status, which is exactly why
    that column exists.
    """
    candidates = [pn for pn, part in world.parts.items()
                  if part.source_type == BUY and len(world.links_for(pn)) >= 1]
    rng.shuffle(candidates)

    total = config.n_no_qualified_supplier + config.n_supplier_list_unknown
    chosen = candidates[:total]
    for i, part_number in enumerate(chosen):
        for link in world.links_for(part_number):
            world.links.remove(link)
        for lt in world.lead_times_for(part_number):
            world.lead_times.remove(lt)
        verified = i < config.n_no_qualified_supplier
        world.parts[part_number].sourcing_list_status = (
            VERIFIED if verified else UNVERIFIED)
        truth.record_intent(part_number,
                            "no_qualified_supplier" if verified
                            else "supplier_list_unknown")


def make_parts_with_suppliers(rng, config, world, truth):
    """Supplier rows attached to parts marked `make`.

    A contradiction in the data, and the reason the dual reading exists. With
    one supplier the two readings always differ. With two, they differ unless
    every supplier carries a lead time.
    """
    make_parts = [pn for pn, part in world.parts.items()
                  if part.source_type == MAKE and pn not in world.finished_goods
                  and not world.links_for(pn)]
    rng.shuffle(make_parts)
    supplier_ids = list(world.suppliers)

    wanted = ([1] * config.n_make_with_one_supplier
              + [2] * config.n_make_with_two_suppliers)
    for part_number, n_suppliers in zip(make_parts, wanted):
        world.parts[part_number].sourcing_list_status = VERIFIED
        for supplier_id in rng.sample(supplier_ids, n_suppliers):
            canonical = world.suppliers[supplier_id].canonical_name
            world.links.append(SupplierLink(
                part_number=part_number, supplier_id=supplier_id,
                qualification_date="2024-06-01",
                name_in_suppliers=canonical, name_in_lead_times=canonical,
            ))
            # these links are created after name rendering has already run, so
            # they record their own name; every string that reaches a CSV must
            # resolve back to exactly one supplier
            truth.record_variant(canonical, supplier_id)
            quoted = rng.randint(config.lead_time_min_days,
                                 config.lead_time_max_days)
            world.lead_times.append(LeadTime(
                part_number=part_number, supplier_id=supplier_id,
                quoted_lead_time_days=quoted,
                lead_time_p95_days=int(quoted * 1.3)))
        truth.record_intent(part_number, "make_with_suppliers")

    # Strip a lead time from some make-with-two parts so the SECOND
    # disagreement case exists: readings differ whenever a make part has
    # suppliers and any of them lacks a lead time.
    two_supplier_parts = [pn for pn in make_parts[:len(wanted)]
                          if len(world.links_for(pn)) == 2]
    for part_number in two_supplier_parts[:config.n_make_with_two_missing_lead_time]:
        victim = world.lead_times_for(part_number)[0]
        world.lead_times.remove(victim)
        truth.record_omitted_lead_time(victim.part_number, victim.supplier_id)
        truth.record_intent(part_number, "make_with_suppliers_missing_lead_time")


def make_multi_source_no_lead_times(rng, config, world, truth):
    """Buy parts with several suppliers on paper and no lead times at all.

    Distinct from a hidden single source, where exactly one supplier is usable.
    Here none is, so the part is not single-sourced but nothing about recovery
    time is knowable either.
    """
    candidates = [pn for pn, part in world.parts.items()
                  if part.source_type == BUY
                  and len(world.links_for(pn)) >= 2
                  and len(world.lead_times_for(pn)) >= 2]
    rng.shuffle(candidates)
    for part_number in candidates[:config.n_multi_source_no_lead_times]:
        for lt in world.lead_times_for(part_number):
            world.lead_times.remove(lt)
            truth.record_omitted_lead_time(lt.part_number, lt.supplier_id)
        truth.record_intent(part_number, "multi_source_no_lead_times")


def link_confusable_pair(rng, config, world, truth):
    """Attach BOTH confusable suppliers to one part.

    Without this, an over-eager merge cannot reach a verdict anywhere in the
    data, so verdict-level precision would score perfectly for free. Here, a
    matcher that collapses "Yarrow Corporation" and "Yarrow Holdings" turns a
    genuine multi_source into a PHANTOM single source, which sends somebody to
    qualify a second supplier that already exists.
    """
    if not truth.confusable_suppliers:
        return
    pair = truth.confusable_suppliers[0]
    a_id, b_id = pair["a"]["supplier_id"], pair["b"]["supplier_id"]

    candidates = [pn for pn, part in world.parts.items()
                  if part.source_type == BUY and len(world.links_for(pn)) >= 1
                  and pn not in truth.intents]
    rng.shuffle(candidates)
    for part_number in candidates[:config.n_parts_linking_confusable_pair]:
        for link in world.links_for(part_number):
            world.links.remove(link)
        for lt in world.lead_times_for(part_number):
            world.lead_times.remove(lt)
        world.parts[part_number].sourcing_list_status = VERIFIED
        for supplier_id in (a_id, b_id):
            canonical = world.suppliers[supplier_id].canonical_name
            world.links.append(SupplierLink(
                part_number=part_number, supplier_id=supplier_id,
                qualification_date="2024-03-01",
                name_in_suppliers=canonical, name_in_lead_times=canonical))
            truth.record_variant(canonical, supplier_id)
            quoted = rng.randint(config.lead_time_min_days,
                                 config.lead_time_max_days)
            world.lead_times.append(LeadTime(
                part_number=part_number, supplier_id=supplier_id,
                quoted_lead_time_days=quoted,
                lead_time_p95_days=int(quoted * 1.25)))
        truth.record_intent(part_number, "links_confusable_pair")


def add_duplicate_vendor_rows(rng, config, world, truth):
    """The SAME supplier, linked twice to one part under two spellings.

    Duplicate vendor records are the most common real form of inconsistent
    supplier naming, and this is the ONLY case where a name merge changes a
    part's supplier COUNT. Every other variant in this data set changes how a
    supplier is spelled, not how many there are.

    That makes it the only case exercising the expensive direction: a missed
    merge counts one supplier as two, reads multi_source where the truth is
    single_source, and understates exposure. An over-eager merge only
    overstates it.

    No second lead time row is added: a duplicate vendor record is a duplicate
    identity, not a second quotation.
    """
    candidates = [pn for pn, part in world.parts.items()
                  if part.source_type == BUY and world.links_for(pn)
                  and pn not in truth.intents]
    rng.shuffle(candidates)
    # SINGLE-supplier parts first, deliberately. A duplicate on a part with two
    # real suppliers still reads multi_source whether or not the merge happens,
    # so it exercises nothing. Only a duplicate on a single-supplier part flips
    # the verdict: two rows read as multi_source where the truth is
    # single_source. Left to chance, most draws cover only the harmless shape.
    candidates.sort(key=lambda pn: len({l.supplier_id
                                        for l in world.links_for(pn)}))
    for part_number in candidates[:config.n_duplicate_vendor_rows]:
        original = world.links_for(part_number)[0]
        canonical = world.suppliers[original.supplier_id].canonical_name
        alternatives = [v for v in name_variants(canonical, rng)
                        if v != original.name_in_suppliers]
        if not alternatives:
            continue
        spelling = rng.choice(alternatives)
        world.links.append(SupplierLink(
            part_number=part_number, supplier_id=original.supplier_id,
            qualification_date=original.qualification_date,
            name_in_suppliers=spelling, name_in_lead_times=spelling))
        truth.record_variant(spelling, original.supplier_id)
        truth.record_intent(part_number, "duplicate_vendor_row")


def damage_part_attributes(rng, config, world, truth):
    """Missing on-hand, genuine zero on-hand, and missing tooling owner.

    Missing and zero are different facts and must stay different. A blank means
    no record exists; a zero means somebody counted and found none.
    """
    for part in world.parts.values():
        roll = rng.random()
        if roll < config.missing_on_hand_rate:
            part.on_hand_units = None
            truth.record_intent(part.part_number, "on_hand_unknown")
        elif roll < config.missing_on_hand_rate + config.genuine_zero_on_hand_rate:
            part.on_hand_units = 0
            truth.record_intent(part.part_number, "on_hand_genuine_zero")

        if rng.random() < config.missing_tooling_owner_rate:
            part.tooling_owner = ""
            truth.record_intent(part.part_number, "tooling_unknown")


def damage_list_status(rng, config, world, truth):
    """Unverified and blank sourcing lists on parts that do have suppliers."""
    for part in world.parts.values():
        if part.source_type != BUY or not world.links_for(part.part_number):
            continue
        if part.sourcing_list_status != VERIFIED:
            continue          # already set deliberately elsewhere
        roll = rng.random()
        if roll < config.unverified_list_rate:
            part.sourcing_list_status = UNVERIFIED
            truth.record_intent(part.part_number, "list_unverified")
        elif roll < config.unverified_list_rate + config.blank_list_status_rate:
            part.sourcing_list_status = BLANK
            truth.record_intent(part.part_number, "list_status_blank")


def remove_absent_demand(rng, config, world, truth):
    """Drop one finished good from the demand plan entirely.

    Truth records only WHICH finished good was dropped. Which parts become
    partially or wholly unknown requires walking the BOM, and a traversal
    belongs to stage 2, not to an answer key.
    """
    index = config.absent_demand_fg_index
    if index is None or index < 0 or index >= len(world.finished_goods):
        return
    fg = world.finished_goods[index]
    world.demand.pop(fg, None)
    truth.absent_demand_finished_good = fg


def apply_messiness(rng, config, world, truth):
    render_supplier_names(rng, config, world, truth)
    add_confusable_suppliers(rng, config, world, truth)
    drop_lead_times(rng, config, world, truth)
    make_hidden_single_sources(rng, config, world, truth)
    make_zero_supplier_parts(rng, config, world, truth)
    make_parts_with_suppliers(rng, config, world, truth)
    make_multi_source_no_lead_times(rng, config, world, truth)
    link_confusable_pair(rng, config, world, truth)
    add_duplicate_vendor_rows(rng, config, world, truth)
    damage_part_attributes(rng, config, world, truth)
    damage_list_status(rng, config, world, truth)
    remove_absent_demand(rng, config, world, truth)
    return world
