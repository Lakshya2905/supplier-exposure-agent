"""One hop below the supplier, which is as far as anybody can usually see.

WHY ONE FIELD AND NOT A GRAPH. Roughly 95% of companies can see their own
suppliers and fewer than half can see one level below that, so a tool demanding
a supply-chain graph is unusable by most of the people it is for. One optional
column naming where a supplier sources the critical input is the smallest thing
that makes the correlation visible, and it is a question a buyer can actually
ask on a call.

WHAT IT BUYS. Two parts bought from two different companies in two different
regions are not independent if both companies buy the critical input from the
same place. Neither supplier grouping nor region grouping can see that, and it
is the third definition of correlated the brief named and the schema could not
hold. `concentration.BY_TIER` is where it is read.

WHAT IT DOES NOT BUY, stated here so nobody reads more into it: this is ONE hop.
It says nothing about where that source buys, so two sub-tier suppliers who both
depend on one mill read as independent. That is a strict xfail in
`tests/test_concentration.py` rather than a silence.

ABSENCE GROUPS NOTHING. A supplier with no entry has not answered, and two
suppliers who have both not answered are not thereby the same supplier. The
reader drops blanks rather than keeping an empty source, because a group built
out of an absence is a correlation manufactured from a gap and then handed to
somebody to confirm.
"""

# The file and its column. NOT in `synthetic/model.py` with the generated
# names, for the reason `recovery.RECOVERY_INPUTS_FILE` gives: everything named
# there is something the generator writes, and this it never will.
SUB_TIER_FILE = "sub_tier_sources.csv"
SUB_TIER_SOURCE = "sub_tier_source"


def tiers_for(parts_to_suppliers, sources):
    """part -> where its supplier sources the critical input.

    `parts_to_suppliers` maps a part to the supplier names it depends on, which
    for an exposed part is exactly one. A part whose supplier is not in
    `sources` is absent from the result rather than present with an empty value:
    see the module docstring on why an absence must not group.

    A part depending on several suppliers takes the FIRST source by sorted name
    rather than an arbitrary one. Only exposed parts are grouped and an exposed
    part has one supplier by definition of the verdict, so this is a tie-break
    that cannot fire on real input; it is written explicitly anyway, because an
    arbitrary pick that silently becomes meaningful is the ordering defect this
    project has a rule about.
    """
    out = {}
    for part, suppliers in parts_to_suppliers.items():
        found = sorted({sources[name] for name in suppliers
                        if name in sources})
        if found:
            out[part] = found[0]
    return out
