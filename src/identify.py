"""Single-source identification, with autonomy decided per finding.

The verdict table's inputs are not facts. Supplier count is the output of a
fuzzy match, and so is whether a supplier has a quotable lead time, because the
two files spell the same supplier differently. So the same dual-reading
primitive the brief now records applies here:

    compute the verdict with uncertain merges APPLIED
    compute the verdict with uncertain merges WITHHELD
    agree     -> executes
    disagree  -> recommends, exception lane, carrying both raw strings and the
                 score that would settle it

This is why no default merge direction is needed, which matters because the
safe direction is not constant. A missed merge in the supplier list overcounts
sources and UNDERSTATES exposure, which is expensive. A missed match in the
lead-time join undercounts lead times and OVERSTATES it, which is merely noisy.
Leaning one way protects one join and harms the other. Computing both does not
have to choose.
"""
from . import governance as gov
from .normalise import (cluster, cluster_certain_only, cluster_of, match_score)
from .synthetic import verdicts as V

# FLOORS FIRST, THEN THE THRESHOLD. The floors come from what the task
# requires; the threshold moves to meet them, never the reverse.
#
#   RECALL_FLOOR    a missed merge counts one supplier as two, reads
#                   multi_source where the truth is single_source, and
#                   UNDERSTATES exposure. That is the error that stops a line,
#                   so the floor is near-absolute.
#   PRECISION_FLOOR a false merge manufactures a PHANTOM single source and
#                   sends somebody to qualify a supplier that already exists.
#                   Wasteful and self-correcting, so the floor is lower.
RECALL_FLOOR = 0.99
PRECISION_FLOOR = 0.95

# Measured, not guessed. Swept against the damage ledger at seed 42:
#
#   threshold  precision  recall
#     0.90       0.917     1.000   <- fails the precision floor
#     0.95       1.000     1.000   <- meets both
#
# Recall is flat across the sweep because every variant the generator produces
# canonicalises to an identical key and merges at score 1.0 regardless of
# threshold. Only precision moves, and it is precision that forced 0.90 up.
#
# The 30 false merges at 0.90 are all one pair of REAL suppliers whose names
# differ by a single letter, "Marrow Corporation" and "Yarrow Corporation",
# scoring 0.944. Merging them would have been a phantom single source.
DEFAULT_THRESHOLD = 0.95


def _counts(supplier_names, lead_time_names, clusters):
    """(distinct suppliers, how many have a lead time) under one clustering."""
    supplier_groups = {cluster_of(clusters, name) for name in supplier_names}
    lead_time_groups = {cluster_of(clusters, name) for name in lead_time_names}
    return len(supplier_groups), len(supplier_groups & lead_time_groups)


def identify(part_number, source_type, list_status, supplier_names,
             lead_time_names, threshold=DEFAULT_THRESHOLD, log=None,
             at="1970-01-01T00:00:00+00:00"):
    """One finding, with its own autonomy level."""
    names = list(supplier_names) + list(lead_time_names)
    merged_clusters, uncertain = cluster(names, threshold)
    certain_clusters = cluster_certain_only(names)

    n_sup_merged, n_lt_merged = _counts(
        supplier_names, lead_time_names, merged_clusters)
    n_sup_apart, n_lt_apart = _counts(
        supplier_names, lead_time_names, certain_clusters)

    verdict_merged = V.verdict(source_type, n_sup_merged, list_status,
                               n_lt_merged)
    verdict_apart = V.verdict(source_type, n_sup_apart, list_status,
                              n_lt_apart)

    # TWO INDEPENDENT DISAGREEMENTS, and both have to reach the lane.
    #
    #   merge conflict     the two CLUSTERINGS give different verdicts
    #   readings conflict  the clusterings agree, and what they agree ON is
    #                      READINGS_DISAGREE, because a make part carries
    #                      supplier rows and the flag contradicts the rows
    #
    # Comparing the clusterings alone misses the second one entirely: both
    # readings return READINGS_DISAGREE, they match, and a finding whose verdict
    # literally means "nobody can tell" gets stamped EXECUTES. So a verdict of
    # READINGS_DISAGREE is disqualifying on its own, regardless of agreement.
    make_readings = V.readings(source_type, n_sup_merged, list_status,
                               n_lt_merged)
    merge_conflict = verdict_merged != verdict_apart
    readings_conflict = V.READINGS_DISAGREE in (verdict_merged, verdict_apart)
    decidable = not (merge_conflict or readings_conflict)
    autonomy = gov.EXECUTES if decidable else gov.RECOMMENDS

    reasons = []
    if readings_conflict:
        reasons.append("the part is flagged make but carries supplier rows, and "
                       "the two readings of that contradiction disagree")
    if merge_conflict:
        reasons.append("the verdict depends on an uncertain name match")
    if decidable and uncertain:
        reasons.append("an uncertain name match exists but does not change the "
                       "verdict either way")
    elif decidable:
        reasons.append("no uncertain name match affects this part")

    # Confidence is the weakest link that could move the answer.
    if decidable:
        confidence_value = 1.0
    elif merge_conflict:
        confidence_value = min(score for _, _, score in uncertain)
    else:
        # A readings conflict has no score to report. There is no field in the
        # data that favours either reading, so this is not low confidence in an
        # answer, it is the absence of one: an even split between two defensible
        # readings. 0.5 encodes that rather than implying a measurement.
        confidence_value = 0.5

    evidence = {
        "verdict_if_merged": verdict_merged,
        "verdict_if_separate": verdict_apart,
        "resulting_verdict": verdict_merged if decidable else None,
        "suppliers_if_merged": n_sup_merged,
        "suppliers_if_separate": n_sup_apart,
        "threshold": threshold,
        "autonomy": autonomy,
        "merge_conflict": merge_conflict,
        "readings_conflict": readings_conflict,
        "uncertain_pairs": [
            {"raw_a": a, "raw_b": b, "score": score} for a, b, score in uncertain
        ],
    }
    if uncertain:
        worst = min(uncertain, key=lambda pair: pair[2])
        evidence.update(raw_a=worst[0], raw_b=worst[1], score=worst[2])
    if make_readings:
        evidence.update(stale_flag=make_readings["stale_flag"],
                        dual_mode=make_readings["dual_mode"])

    finding = gov.Finding(
        subject=part_number,
        verdict=verdict_merged if decidable else V.READINGS_DISAGREE,
        autonomy=autonomy,
        confidence=gov.Confidence(confidence_value, tuple(reasons)),
        evidence=evidence,
    )

    if log is not None:
        if decidable:
            kind, value = gov.KIND_VERDICT_ASSIGNED, verdict_merged
        elif merge_conflict:
            kind, value = gov.KIND_MERGE_UNCERTAIN, V.READINGS_DISAGREE
        else:
            kind, value = gov.KIND_READINGS_DISAGREE, V.READINGS_DISAGREE
        log.append(status=gov.STATUS_PROPOSED, sku_id=part_number,
                   field="sourcing_verdict", value=value, kind=kind, at=at,
                   evidence=evidence)
    return finding


def exception_lane(findings):
    """Everything that could not be decided automatically, worst reading first.

    Ordered by exposure under the WORSE candidate reading, so a possible single
    source sorts above a possible multi-source, which is the order a person
    should work them in.

    READINGS_DISAGREE is deliberately absent from SEVERITY: it is not a level of
    exposure, it is the absence of a settled one, so it cannot be ranked. The
    candidates below are the concrete readings underneath it, which can be.
    """
    def rank(finding):
        evidence = finding.evidence
        candidates = [evidence.get(key) for key in
                      ("verdict_if_merged", "verdict_if_separate",
                       "stale_flag", "dual_mode")]
        ranked = [V.SEVERITY.index(v) for v in candidates
                  if v and v != V.READINGS_DISAGREE]
        return min(ranked) if ranked else len(V.SEVERITY)

    return sorted([f for f in findings if f.autonomy == gov.RECOMMENDS], key=rank)


def identify_all(part_master, supplier_rows, lead_time_rows,
                 threshold=DEFAULT_THRESHOLD, log=None):
    """part_master: {part -> (source_type, list_status)}."""
    findings = []
    for part_number, (source_type, list_status) in sorted(part_master.items()):
        findings.append(identify(
            part_number, source_type, list_status,
            supplier_rows.get(part_number, []),
            lead_time_rows.get(part_number, []),
            threshold=threshold, log=log))
    return findings
