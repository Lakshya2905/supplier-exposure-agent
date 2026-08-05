"""Grade the normaliser against the damage ledger.

Precision and recall are reported SEPARATELY, never as an F-score, for the same
reason the five scoring dimensions stay separate: one number hides which way
the system is failing, and the two failures have opposite costs.

    recall miss     two names for one supplier read as two suppliers.
                    Overcounts sources, UNDERSTATES exposure. Expensive.
    precision miss  two suppliers merged into one. Produces a PHANTOM single
                    source and sends somebody to qualify a second supplier that
                    already exists.

And a third number, because precision alone does not say how much a false merge
costs: **verdict impact**. A false merge on a four-supplier part is invisible,
since the part reads multi_source either way. The same merge on a two-supplier
part is a phantom single source. Identical precision, entirely different
consequence, so the consequence is counted rather than inferred.
"""
from collections import defaultdict

from .normalise import cluster, match_score
from .synthetic import verdicts as V


def _truth_pairs(supplier_variants):
    """Every name pair that truly refers to one supplier."""
    by_supplier = defaultdict(set)
    for name, supplier_id in supplier_variants.items():
        by_supplier[supplier_id].add(name)
    same = set()
    for names in by_supplier.values():
        ordered = sorted(names)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                same.add((a, b))
    return same


def _predicted_pairs(names, threshold):
    clusters, _ = cluster(names, threshold)
    merged = set()
    for group in clusters:
        ordered = sorted(group)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                merged.add((a, b))
    return merged


def grade_pairs(supplier_variants, threshold):
    """Pair-level precision and recall, plus the raw pair sets for inspection."""
    names = sorted(supplier_variants)
    truth = _truth_pairs(supplier_variants)
    predicted = _predicted_pairs(names, threshold)

    true_positive = predicted & truth
    false_positive = predicted - truth
    false_negative = truth - predicted

    def ratio(numerator, denominator):
        return 1.0 if denominator == 0 else numerator / denominator

    return {
        "threshold": threshold,
        "precision": ratio(len(true_positive),
                           len(true_positive) + len(false_positive)),
        "recall": ratio(len(true_positive),
                        len(true_positive) + len(false_negative)),
        "true_positive": len(true_positive),
        "false_positive": sorted(false_positive),
        "false_negative": sorted(false_negative),
    }


def verdict_impact(false_positive_pairs, parts):
    """How many verdicts each false merge would actually have changed.

    `parts` maps part_number -> (source_type, list_status, supplier_names,
    lead_time_names). A false merge that changes no verdict anywhere is a
    precision miss with no consequence; one that manufactures a single source
    is the expensive kind. Both count once in precision and must not count the
    same here.
    """
    impact = []
    for name_a, name_b in false_positive_pairs:
        changed = []
        for part_number, (source_type, status, suppliers, lead_times) in parts.items():
            names = set(suppliers) | set(lead_times)
            if not {name_a, name_b} <= names:
                continue
            apart = V.verdict(source_type, len(set(suppliers)), status,
                              len(set(suppliers) & set(lead_times)))
            merged_suppliers = {n for n in suppliers if n != name_b}
            merged_lead_times = {
                (name_a if n == name_b else n) for n in lead_times}
            merged = V.verdict(source_type, len(merged_suppliers), status,
                               len(merged_suppliers & merged_lead_times))
            if merged != apart:
                changed.append({"part_number": part_number,
                                "verdict_if_merged": merged,
                                "verdict_if_separate": apart})
        impact.append({
            "pair": [name_a, name_b],
            "score": match_score(name_a, name_b),
            "verdicts_changed": len(changed),
            "changes": changed,
        })
    return sorted(impact, key=lambda row: -row["verdicts_changed"])


def sweep(supplier_variants, thresholds):
    """Precision and recall across candidate thresholds.

    The floors come from what the task requires; the threshold moves to meet
    them, never the reverse. If no threshold meets both floors, that is a
    finding about the normaliser and is reported as one rather than resolved by
    lowering a floor.
    """
    return [grade_pairs(supplier_variants, threshold)
            for threshold in thresholds]
