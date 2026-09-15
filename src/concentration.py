"""Concentration: correlated exposure across a SET of parts.

A SHAPE CHANGE FROM THE FIRST FIVE DIMENSIONS. Wait-out days, resourcing days,
blast radius, cover and portability are properties of one part and can be
computed from that part alone. Concentration is a property of a group, and no part carries the answer by
itself. So the primary record here is the CLUSTER, and the per-part slot
references it rather than restating it. Nine parts on one supplier is ONE
finding, not nine, and a reviewer confirms it once.

THE DECISION CEILING. Grouping is the first real modelling judgment in the
system. Same supplier, same region and same tier are three different definitions
of correlated and they give three different answers. So concentration is
`recommends` PERMANENTLY, and the reason it cannot drift is worth stating
precisely, because the argument for drifting is a good one:

    "once a definition is chosen the arithmetic is deterministic and
     reproducible, so a deterministic function of settled inputs should
     execute"

The determinism is DOWNSTREAM OF THE JUDGMENT. The autonomy question is not
"is this reproducible" but "could a reasonable person have chosen differently
and got a different answer", and here they could. So there are two independent
gates and this dimension fails the second one forever:

    completeness      do we have the data?           varies, as at stage 4
    decision ceiling  may a system claim this alone?  no, and complete data
                                                      does not change it

Enforced structurally rather than by comment: `ConcentrationScore.autonomy` is
pinned and `autonomy_for()` is never called on it, so there is no code path from
any completeness state to `executes`.

THE DUAL READING HERE IS COMPLEMENTARY, NOT CONTESTED. Supplier grouping and
region grouping answer different questions and can both be true at once, so
their disagreement is REPORTED as the finding rather than routed as a doubt. See
the governance section of docs/BRIEF.md. The test is whether any fact could
settle it; nothing can settle what "correlated" ought to mean.
"""
from dataclasses import dataclass, field, replace

from . import governance as gov
from .identify import DEFAULT_THRESHOLD
from .normalise import cluster, cluster_certain_only, cluster_of
from .scoring import (CANNOT_TELL, CONCENTRATION, KNOWN, LOWER_BOUND,
                      NOT_APPLICABLE, PARTS, DimensionScore)
from .synthetic import verdicts as V

# Parts whose exposure is confirmed. A cluster of multi-source parts sharing a
# supplier is not a single point of failure, so it is not a concentration.
# This is a LOOKUP against stage 3's verdicts, not a threshold.
EXPOSED_VERDICTS = (V.SINGLE_SOURCE, V.SINGLE_SOURCE_NO_LEAD_TIME,
                    V.HIDDEN_SINGLE_SOURCE)

# Parts that MIGHT be exposed and MIGHT belong to any cluster. They are the
# global caveat: see `unplaceable_parts` below.
UNPLACEABLE_VERDICTS = (V.SUPPLIER_LIST_UNKNOWN, V.READINGS_DISAGREE)

# Parts with nobody to be correlated with. Not a gap in the data.
NO_SUPPLIER_VERDICTS = (V.MADE_IN_HOUSE, V.NO_QUALIFIED_SUPPLIER)

# Grouping bases. All three of the brief's definitions, since the sub-tier
# source field arrived; before it, tier was a declared absence.
BY_SUPPLIER = "supplier"
BY_REGION = "region"
# THE THIRD READING, and the one the brief named that the schema could not hold.
# Two parts bought from two different companies are not independent if both of
# those companies buy the critical input from the same place, and no amount of
# supplier or region grouping can see it. It needs one optional field naming
# where a supplier sources that input, which is the smallest thing that makes
# the reading representable: no supplier graph, no tiers below the second.
BY_TIER = "tier"
BASES = (BY_SUPPLIER, BY_REGION, BY_TIER)

# Agreement between the two readings. THIS IS THE FINDING, not a defect report.
BOTH = "both"
SUPPLIER_ONLY = "supplier_only"
REGION_ONLY = "region_only"
NEITHER = "neither"
AGREEMENT_CLASSES = (BOTH, SUPPLIER_ONLY, REGION_ONLY, NEITHER)

# WHICH READINGS `agreement` IS ABOUT, stated rather than assumed. It is the
# supplier-versus-region comparison the README calls a COMPLEMENTARY
# disagreement, and adding a third basis does not silently widen it: a part
# correlated only by sub-tier source is `neither` here, which is true of
# supplier and region and would be a lie if read as "not correlated at all".
#
# So `correlated_bases` carries the whole truth and this carries the pair. A
# test asserts a tier-only part has both, so the two cannot mislead together.
AGREEMENT_SCOPE = (BY_SUPPLIER, BY_REGION)

# Used when one reading is settled and the other is not. The agreement class is
# NOT computed rather than defaulting the unknown side to "not concentrated",
# which would silently downgrade the finding.
UNDETERMINED = ""

# ARITY, NOT MAGNITUDE. A cluster is concentrated when more than one exposed
# part shares the dependency. Two is not a tuned threshold, it is the number at
# which a correlation exists at all: one part is not correlated with anything.
# Any figure above two would be a judgment about severity and is refused for
# exactly the reason stage 4 refused to band a lead time. Severity is carried
# by the raw member count and by the membership list, unbanded.
MINIMUM_CORRELATION = 2


@dataclass(frozen=True)
class Cluster:
    """A set of exposed parts sharing one dependency.

    MEMBERS ARE CARRIED BY IDENTITY, NOT ONLY COUNTED. Nine parts on one
    supplier where seven are long lead is a different finding from nine
    catalogue parts, and a reviewer needs the membership at the moment they
    decide whether to act. The count is the summary; the membership is the
    finding. No severity is computed from either.
    """
    key: str
    basis: str
    members: tuple
    completeness: str
    contingent: bool = False
    reasons: tuple = field(default_factory=tuple)
    members_if_merged: tuple = ()

    def __post_init__(self):
        if self.basis not in BASES:
            raise ValueError(f"unknown grouping basis: {self.basis!r}")
        if list(self.members) != sorted(self.members):
            raise ValueError("members must be sorted, so that a cluster's "
                             "identity does not depend on iteration order")

    @property
    def size(self):
        return len(self.members)

    @property
    def is_concentrated(self):
        return self.size >= MINIMUM_CORRELATION

    @property
    def autonomy(self):
        """PINNED. See the module docstring: the ceiling is not derived."""
        return gov.RECOMMENDS


@dataclass(frozen=True)
class ConcentrationScore(DimensionScore):
    """One part's view of the clusters it belongs to.

    A `DimensionScore` so it sits in the profile beside the other five, with one
    difference that is the entire point: `autonomy` is PINNED rather than
    derived. Overriding the property is what makes the ceiling structural, since
    there is then no completeness value that can produce `executes`.
    """
    agreement: str = UNDETERMINED
    supplier_cluster: str = ""
    region_cluster: str = ""
    tier_cluster: str = ""
    # EVERY basis under which this part is correlated, not just the two
    # `agreement` compares. See AGREEMENT_SCOPE.
    correlated_bases: tuple = ()

    @property
    def autonomy(self):
        """Always `recommends`, whatever the completeness.

        Complete data does not turn a modelling choice into a fact.
        """
        return gov.RECOMMENDS


@dataclass(frozen=True)
class ConcentrationReport:
    """Everything stage 5 produces, including what it could not see."""
    clusters: tuple
    scores: dict
    unplaceable_parts: tuple
    reasons: tuple = field(default_factory=tuple)

    def concentrated(self, basis=None):
        return tuple(c for c in self.clusters if c.is_concentrated
                     and (basis is None or c.basis == basis))

    def review_queue(self):
        """Clusters awaiting confirmation, largest first.

        SEPARATE FROM THE ABSTENTION LANE, and they are different reviewer
        tasks. The lane means "fetch me a number"; this queue means "confirm my
        model". Every cluster is in this queue by definition of the ceiling, so
        merging the two would flood the lane and make both useless.
        """
        return tuple(sorted(self.concentrated(),
                            key=lambda c: (-c.size, c.basis, c.key)))

    def agreement_summary(self):
        counts = {name: 0 for name in AGREEMENT_CLASSES}
        counts[UNDETERMINED] = 0
        for score in self.scores.values():
            if score.completeness != NOT_APPLICABLE:
                counts[score.agreement] = counts.get(score.agreement, 0) + 1
        return counts


def _supplier_key(clusters, name):
    """A stable label for a supplier identity: its alphabetically first spelling."""
    return min(cluster_of(clusters, name))


def _group(part_keys):
    """{part -> keys} inverted into {key -> sorted member tuple}."""
    grouped = {}
    for part, keys in part_keys.items():
        for key in keys:
            grouped.setdefault(key, set()).add(part)
    return {key: tuple(sorted(members)) for key, members in grouped.items()}


def analyse(verdicts, dependencies, threshold=DEFAULT_THRESHOLD, tiers=None):
    """Cluster exposed parts under every reading, and classify the agreement.

    `dependencies` maps a part to the ((supplier_name, region), ...) it actually
    depends on: for a single-source part its one supplier, for a hidden single
    source the one supplier that can actually quote. `verdicts` comes from
    stage 3.

    `tiers` maps a part to where its supplier sources the critical input, and is
    OPTIONAL. Absent, no tier cluster is built and nothing else changes, which
    is every dataset this repository generates. A part missing from the mapping
    is a part whose supplier has not said, and it simply does not join a tier
    group: it is not placed in an "unknown" group, because two suppliers who
    have both declined to say are not thereby buying from the same place.
    """
    exposed = {part for part, verdict in verdicts.items()
               if verdict in EXPOSED_VERDICTS and dependencies.get(part)}
    unplaceable = tuple(sorted(
        part for part, verdict in verdicts.items()
        if verdict in UNPLACEABLE_VERDICTS))

    names = sorted({name for part in exposed
                    for name, _ in dependencies.get(part, ())})
    merged_clusters, _ = cluster(names, threshold)
    certain_clusters = cluster_certain_only(names)

    # Supplier grouping, under both readings. Region grouping needs only one:
    # a region is a controlled value read straight from the row, so an
    # unresolved NAME merge cannot move a part between regions.
    supplied_tiers = tiers or {}
    certain_by_part, merged_by_part, region_by_part = {}, {}, {}
    tier_by_part = {}
    for part in sorted(exposed):
        pairs = dependencies[part]
        certain_by_part[part] = {_supplier_key(certain_clusters, name)
                                 for name, _ in pairs}
        merged_by_part[part] = {_supplier_key(merged_clusters, name)
                                for name, _ in pairs}
        region_by_part[part] = {region.strip() for _, region in pairs
                                if region and region.strip()}
        source = (supplied_tiers.get(part) or "").strip()
        # An empty set, not a set containing "": a part with no sub-tier source
        # on file joins nothing, and `_group` would otherwise build a group of
        # every part nobody has answered for and call it a correlation.
        tier_by_part[part] = {source} if source else set()

    certain_groups = _group(certain_by_part)
    merged_groups = _group(merged_by_part)
    region_groups = _group(region_by_part)
    tier_groups = _group(tier_by_part)

    clusters = []
    for key, members in sorted(certain_groups.items()):
        grown = _merged_counterpart(members, merged_by_part, merged_groups)
        if len(members) >= MINIMUM_CORRELATION and len(grown) > len(members):
            # The cluster is concentrated either way and may simply be bigger.
            # Membership can only GROW, so this is a lower bound, the same
            # direction as blast radius and for the same reason: the uncertain
            # quantity sits in the numerator.
            completeness, reason = LOWER_BOUND, (
                f"{len(members)} exposed parts are confirmed on this supplier "
                f"and {len(grown)} would be if an unresolved name merge is "
                f"confirmed, so the membership is a lower bound")
        else:
            completeness, reason = KNOWN, (
                "membership is confirmed; no unresolved name merge reaches "
                "this cluster")
        clusters.append(Cluster(key=key, basis=BY_SUPPLIER, members=members,
                                completeness=completeness, reasons=(reason,),
                                members_if_merged=grown))

    # Concentrations that exist ONLY under the merged reading. Note the test is
    # on the CONCENTRATION, not on the cluster key: two singleton suppliers
    # whose names may be one supplier both exist under either reading, and it
    # is their correlation that is contingent. Testing key novelty instead
    # would miss exactly the case the mirror trap was built to produce.
    for key, members in sorted(merged_groups.items()):
        if len(members) < MINIMUM_CORRELATION:
            continue
        already = max((len(set(group) & set(members))
                       for group in certain_groups.values()), default=0)
        if already >= MINIMUM_CORRELATION:
            continue          # the concentration exists without the merge
        clusters.append(Cluster(
            key=key, basis=BY_SUPPLIER, members=members,
            completeness=CANNOT_TELL, contingent=True,
            members_if_merged=members,
            reasons=(f"these {len(members)} parts share a supplier only if an "
                     f"unresolved name merge is confirmed; under the confirmed "
                     f"spellings alone they are separate suppliers",)))

    for key, members in sorted(region_groups.items()):
        clusters.append(Cluster(
            key=key, basis=BY_REGION, members=members, completeness=KNOWN,
            members_if_merged=members,
            reasons=(f"a disruption reaching {key} reaches all of them, "
                     f"whichever company each one buys from",)))

    # THE READING NEITHER OF THE OTHER TWO CAN SEE. These parts may be bought
    # from different companies in different regions and still fail together,
    # because the companies buy the critical input from the same place.
    for key, members in sorted(tier_groups.items()):
        clusters.append(Cluster(
            key=key, basis=BY_TIER, members=members, completeness=KNOWN,
            members_if_merged=members,
            reasons=(f"every supplier behind these parts sources the critical "
                     f"input from {key}, so they are not independent of each "
                     f"other however many companies are named on the parts",)))

    scores = _score_parts(verdicts, dependencies, exposed, certain_by_part,
                          merged_by_part, region_by_part, certain_groups,
                          merged_groups, region_groups, tier_by_part,
                          tier_groups)

    reasons = ()
    if unplaceable:
        # THE GLOBAL CAVEAT, reported once rather than smeared over every
        # cluster. An uncertainty every cluster shares does not discriminate
        # between clusters, and a completeness state that is always the same
        # state is a footer rather than a state.
        reasons = (f"{len(unplaceable)} parts have an unconfirmed or unresolved "
                   f"supplier list and could belong to any cluster here, so "
                   f"every membership count is a lower bound",)

    return ConcentrationReport(clusters=tuple(clusters), scores=scores,
                               unplaceable_parts=unplaceable, reasons=reasons)


def _merged_counterpart(members, merged_by_part, merged_groups):
    """Everyone these members would sit with once uncertain merges apply."""
    grown = set(members)
    for member in members:
        for key in merged_by_part.get(member, ()):
            grown |= set(merged_groups.get(key, ()))
    return tuple(sorted(grown))


def _largest(groups, keys):
    return max((len(groups[key]) for key in keys if key in groups), default=1)


def _score_parts(verdicts, dependencies, exposed, certain_by_part,
                 merged_by_part, region_by_part, certain_groups, merged_groups,
                 region_groups, tier_by_part=None, tier_groups=None):
    """Per part, because the question is per part even though the finding is not.

    Membership is read under BOTH supplier readings and the difference decides
    completeness. Comparing cluster records instead would miss a part that sits
    outside a concentrated cluster under the confirmed spellings and inside it
    under the merged ones, which is the whole contingent case.
    """
    scores = {}
    for part, verdict in sorted(verdicts.items()):
        if not dependencies.get(part):
            scores[part] = _not_applicable(part, verdict)
            continue
        if part not in exposed:
            scores[part] = ConcentrationScore(
                part_number=part, dimension=CONCENTRATION, value=1,
                unit=PARTS, completeness=KNOWN, agreement=NEITHER,
                reasons=("this part is not single-sourced, so it is not a "
                         "correlated point of failure under either grouping",))
            continue

        confirmed = _largest(certain_groups, certain_by_part.get(part, ()))
        if_merged = _largest(merged_groups, merged_by_part.get(part, ()))
        regions = region_by_part.get(part, ())
        region_size = _largest(region_groups, regions)
        sources = (tier_by_part or {}).get(part, ())
        tier_size = _largest(tier_groups or {}, sources)

        supplier_hit = confirmed >= MINIMUM_CORRELATION
        merged_hit = if_merged >= MINIMUM_CORRELATION
        region_hit = region_size >= MINIMUM_CORRELATION
        tier_hit = tier_size >= MINIMUM_CORRELATION
        region_known = bool(regions)

        # THE AGREEMENT CLASS IS REPORTED UNDER THE CONFIRMED READING. What an
        # unresolved merge WOULD make it is carried in detail, not asserted.
        if not region_known:
            agreement = UNDETERMINED
        elif supplier_hit and region_hit:
            agreement = BOTH
        elif supplier_hit:
            agreement = SUPPLIER_ONLY
        elif region_hit:
            agreement = REGION_ONLY
        else:
            agreement = NEITHER

        if merged_hit and not supplier_hit:
            completeness = CANNOT_TELL      # concentration itself is contingent
        elif supplier_hit and if_merged > confirmed:
            completeness = LOWER_BOUND      # concentrated either way, may grow
        else:
            completeness = KNOWN

        agreement_if_merged = agreement
        if merged_hit and region_known:
            agreement_if_merged = BOTH if region_hit else SUPPLIER_ONLY

        correlated = tuple(basis for basis, hit in (
            (BY_SUPPLIER, supplier_hit), (BY_REGION, region_hit),
            (BY_TIER, tier_hit)) if hit)

        scores[part] = ConcentrationScore(
            part_number=part, dimension=CONCENTRATION,
            # THE LARGEST GROUP UNDER ANY READING. A part correlated with two
            # under one grouping and nine under another is exposed to nine; the
            # smaller figure would understate it, and understating exposure is
            # the direction this system refuses.
            value=max(confirmed, region_size, tier_size), unit=PARTS,
            completeness=completeness, agreement=agreement,
            supplier_cluster=min(certain_by_part.get(part, ("",))),
            region_cluster=min(regions) if regions else "",
            tier_cluster=min(sources) if sources else "",
            correlated_bases=correlated,
            reasons=(_reason_for(agreement, completeness, confirmed,
                                 if_merged, region_size, region_known,
                                 tier_size),),
            detail={"supplier_cluster_size": confirmed,
                    "supplier_cluster_size_if_merged": if_merged,
                    "region_cluster_size": region_size,
                    "region_reading": "known" if region_known else "unknown",
                    "agreement_if_merged": agreement_if_merged,
                    "contingent": merged_hit and not supplier_hit})
    return scores


def _not_applicable(part, verdict):
    """No supplier at all, so there is nobody to be correlated with.

    THE COUNTERINTUITIVE CASE IS `no_qualified_supplier`, which is among the
    most exposed findings in the dataset and is nonetheless not applicable here.
    A reviewer seeing that will assume a bug unless the sentence says why, so
    the reason spells out that correlation needs someone to correlate with and
    points at the dimension that does carry the exposure.
    """
    if verdict == V.NO_QUALIFIED_SUPPLIER:
        reason = ("the supplier list was verified and contains nobody, so there "
                  "is no supplier and no region for this part to share with "
                  "anything; correlation needs someone to correlate with. This "
                  "is not a downgrade of the finding: the exposure is carried "
                  "in full by wait out days, which reports nobody to wait on "
                  "for exactly these parts, beside a resourcing time that is "
                  "the only path such a part has")
    else:
        reason = ("the part is made in-house with no external suppliers, so "
                  "there is no supplier and no region to share; correlation "
                  "needs someone to correlate with. Concentration on a single "
                  "internal line is real and is not modelled, because the data "
                  "has no representation of internal capacity")
    return ConcentrationScore(
        part_number=part, dimension=CONCENTRATION, value=None, unit=PARTS,
        completeness=NOT_APPLICABLE, agreement=UNDETERMINED, reasons=(reason,))


def _reason_for(agreement, completeness, confirmed, if_merged, region_size,
                region_known, tier_size=0):
    if completeness == CANNOT_TELL:
        return (f"this part sits in a concentrated group of {if_merged} only if "
                f"an unresolved supplier name merge is confirmed; under the "
                f"confirmed spellings alone it shares its supplier with nobody")
    if agreement == BOTH:
        base = (f"{confirmed} exposed parts share this supplier and "
                f"{region_size} share its region, so the exposure is "
                f"correlated under both definitions")
    elif agreement == SUPPLIER_ONLY:
        base = (f"{confirmed} exposed parts share this supplier but are spread "
                f"across regions, so this is a commercial correlation rather "
                f"than a geographic one")
    elif agreement == REGION_ONLY:
        base = (f"{region_size} exposed parts share this region while their "
                f"suppliers are different companies, so a regional disruption "
                f"reaches all of them even though no single company failure "
                f"would")
    elif agreement == NEITHER:
        base = ("no other exposed part shares this part's supplier or its "
                "region")
    elif not region_known:
        base = (f"{confirmed} exposed parts share this supplier; no region is "
                f"recorded for it, so whether they are also geographically "
                f"correlated cannot be read from the data")
    else:
        base = "concentration could not be classified"
    # THE THIRD READING IS APPENDED, NEVER FOLDED INTO THE AGREEMENT. `agreement`
    # compares supplier with region and says so; a part correlated only by
    # sub-tier source reads "neither" there, which is true of those two, and
    # this clause is what stops that being the whole sentence.
    if tier_size >= MINIMUM_CORRELATION:
        base += (f". Separately, {tier_size} exposed parts depend on suppliers "
                 f"that all source the critical input from the same place, so "
                 f"they are not independent of each other however many "
                 f"companies are named on them")
    if completeness == LOWER_BOUND:
        base += (f", and the supplier group would reach {if_merged} parts if an "
                 f"unresolved name merge is confirmed")
    return base


def log_report(log, report, at="1970-01-01T00:00:00+00:00"):
    """One event per CLUSTER, never one per member.

    `member_count` carries the size, which is agent 1's envelope field for
    exactly this: a single act covering many subjects. Copied verbatim at stage
    3 and unused until now.
    """
    for cluster_record in report.review_queue():
        log.append(
            status=gov.STATUS_PROPOSED, sku_id=cluster_record.key,
            field=f"concentration_{cluster_record.basis}",
            value=str(cluster_record.size), at=at,
            member_count=cluster_record.size,
            kind=gov.KIND_CLUSTER_CONTINGENT if cluster_record.contingent
            else gov.KIND_CLUSTER_FLAGGED,
            evidence={"basis": cluster_record.basis,
                      "members": list(cluster_record.members),
                      "member_count": cluster_record.size,
                      "completeness": cluster_record.completeness,
                      "contingent": cluster_record.contingent,
                      "autonomy": cluster_record.autonomy,
                      "reasons": list(cluster_record.reasons)})


def fill_profiles(profiles, report):
    """Fill the reserved slot. Adds no field and changes no existing method."""
    return {part: replace(profile, concentration=report.scores.get(part))
            for part, profile in profiles.items()}
