"""Hand-written expectations for tiny_suppliers.csv.

Worked out by hand from the rows in that file, never produced by running the
code under test. This module imports nothing from `src`, so a bug in clustering
cannot reach the expectations.

Every part is `single_source` except the two with no supplier rows at all, which
are stated below. The threshold is 0.90, chosen so the two deliberately
confusable pairs are live: at the shipped 0.95 neither merges and the contingent
and lower-bound cases would not occur.
"""
FIXTURE_THRESHOLD = 0.90

VERDICTS = {
    "CON-P01": "single_source", "CON-P02": "single_source",
    "CON-P03": "single_source", "CON-P04": "single_source",
    "CON-P05": "single_source", "CON-P06": "single_source",
    "CON-P07": "single_source", "CON-P08": "single_source",
    "CON-P09": "single_source", "CON-P10": "single_source",
    "CON-P11": "single_source", "CON-P12": "single_source",
    "CON-P13": "single_source", "CON-P14": "single_source",
    "CON-P15": "single_source", "CON-P16": "single_source",
    "CON-P17": "made_in_house",          # no supplier rows
    "CON-P18": "no_qualified_supplier",  # no supplier rows
}

# (basis, key) -> members, for CONCENTRATED clusters only. Worked by hand:
#   Alpha Works has three rows; Beta Industries two; Zeta Corp two;
#   Theta Group two confirmed; Marrow and Yarrow one each, merging at 0.9444.
#   EMEA holds P01 P02 P03 (Alpha) plus P11 P12 (Marrow/Yarrow) plus P16 (Iota).
#   APAC holds P05 (Beta) plus P13 P14 (Theta Group) plus P15 (Theta Groop).
#   LATAM holds P06 (Gamma) and P07 (Delta), two different companies.
EXPECTED_CLUSTERS = {
    ("supplier", "Alpha Works"): ("CON-P01", "CON-P02", "CON-P03"),
    ("supplier", "Beta Industries"): ("CON-P04", "CON-P05"),
    ("supplier", "Zeta Corp"): ("CON-P09", "CON-P10"),
    ("supplier", "Theta Group"): ("CON-P13", "CON-P14"),
    ("supplier", "Marrow Corporation"): ("CON-P11", "CON-P12"),
    ("region", "EMEA"): ("CON-P01", "CON-P02", "CON-P03", "CON-P11",
                         "CON-P12", "CON-P16"),
    ("region", "APAC"): ("CON-P05", "CON-P13", "CON-P14", "CON-P15"),
    ("region", "LATAM"): ("CON-P06", "CON-P07"),
}

EXPECTED_CLUSTER_COMPLETENESS = {
    ("supplier", "Alpha Works"): "known",
    ("supplier", "Beta Industries"): "known",
    ("supplier", "Zeta Corp"): "known",
    # Concentrated either way; "Theta Groop" would add CON-P15 to it.
    ("supplier", "Theta Group"): "lower_bound",
    # Concentrated ONLY if the merge is confirmed. Two singletons otherwise.
    ("supplier", "Marrow Corporation"): "cannot_tell",
    ("region", "EMEA"): "known",
    ("region", "APAC"): "known",
    ("region", "LATAM"): "known",
}

CONTINGENT_CLUSTERS = (("supplier", "Marrow Corporation"),)

# Not concentrated: a cluster of one is not a correlation with anything.
EXPECTED_UNCONCENTRATED_SUPPLIERS = ("Delta Works", "Epsilon Ltd", "Gamma Mfg",
                                     "Iota Systems", "Theta Groop",
                                     "Yarrow Corporation")

# Agreement class under the CONFIRMED reading. What an unresolved merge would
# make it is carried in detail and is not asserted as the answer.
EXPECTED_AGREEMENT = {
    "CON-P01": "both",           # Alpha Works (3) and EMEA (6)
    "CON-P02": "both",
    "CON-P03": "both",
    "CON-P04": "supplier_only",  # Beta Industries (2), alone in NA
    "CON-P05": "both",           # Beta Industries (2) and APAC (4)
    "CON-P06": "region_only",    # alone on Gamma Mfg, LATAM has two companies
    "CON-P07": "region_only",    # alone on Delta Works, same LATAM pair
    "CON-P08": "neither",        # alone on Epsilon Ltd, alone in NORDIC
    "CON-P09": "",               # Zeta Corp (2), region blank: NOT computed
    "CON-P10": "",
    "CON-P11": "region_only",    # supplier group contingent, EMEA is not
    "CON-P12": "region_only",
    "CON-P13": "both",           # Theta Group (2) and APAC (4)
    "CON-P14": "both",
    "CON-P15": "region_only",    # joins Theta Group only if the merge holds
    "CON-P16": "region_only",    # alone on Iota Systems, EMEA has six
    "CON-P17": "",               # not applicable
    "CON-P18": "",               # not applicable
}

EXPECTED_PART_COMPLETENESS = {
    "CON-P01": "known", "CON-P02": "known", "CON-P03": "known",
    "CON-P04": "known", "CON-P05": "known", "CON-P06": "known",
    "CON-P07": "known", "CON-P08": "known", "CON-P09": "known",
    "CON-P10": "known",
    "CON-P11": "cannot_tell",   # concentration itself depends on the merge
    "CON-P12": "cannot_tell",
    "CON-P13": "lower_bound",   # concentrated either way, may grow to three
    "CON-P14": "lower_bound",
    "CON-P15": "cannot_tell",   # joins a concentrated group only if merged
    "CON-P16": "known",
    "CON-P17": "not_applicable",
    "CON-P18": "not_applicable",
}

NOT_APPLICABLE_PARTS = ("CON-P17", "CON-P18")

EXPECTED_AGREEMENT_SUMMARY = {
    "both": 6, "supplier_only": 1, "region_only": 6, "neither": 1, "": 2,
}
