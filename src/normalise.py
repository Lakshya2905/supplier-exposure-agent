"""Supplier name normalisation, with a confidence on every fuzzy match.

Supplier count is not an input. It is the OUTPUT of this module, which means
the verdict table's inputs are themselves uncertain, and that is what forces
stage 3's autonomy to be decided per finding rather than per stage.

Two tiers, deliberately separated:

  CERTAIN    identical after deterministic canonicalisation. Score 1.0. These
             merges are applied in every reading and never reach a reviewer,
             because there is nothing for a reviewer to add.
  UNCERTAIN  similar but not identical. Carries a score. These are the only
             merges that can send a finding to the exception lane.

Keeping them apart is what stops the lane filling with "ACME CORP" versus
"Acme Corp", which is a formatting difference rather than a judgment.
"""
import re
from difflib import SequenceMatcher

# Expanded, not abbreviated, so "Braxton Inds" and "Braxton Industries" reach
# the same key. Mirrors the abbreviation table the generator damages with.
ABBREVIATIONS = {
    "corp": "corporation",
    "inds": "industries",
    "mfg": "manufacturing",
    "wks": "works",
}


def canonical_key(name):
    """Deterministic. Case, punctuation, whitespace and abbreviations only.

    This is the part that is NOT a judgment. Anything requiring one belongs in
    `match_score` where it arrives with a number attached.
    """
    if name is None:
        return ""
    text = str(name).lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    words = [ABBREVIATIONS.get(word, word) for word in text.split()]
    return " ".join(words)


def match_score(a, b):
    """1.0 when canonicalisation makes them identical, else a similarity."""
    key_a, key_b = canonical_key(a), canonical_key(b)
    if key_a == key_b:
        return 1.0
    return SequenceMatcher(None, key_a, key_b).ratio()


def cluster(names, threshold):
    """Group names into supplier identities.

    Returns (clusters, uncertain_pairs) where a cluster is a frozenset of raw
    strings, and an uncertain pair is (a, b, score) for merges that were
    applied on the strength of a score below 1.0.

    Certain merges are applied unconditionally. Uncertain merges are applied
    here and withheld by `cluster_certain_only`, and the difference between
    those two readings is exactly what decides autonomy.
    """
    names = sorted(set(names))
    parent = {name: name for name in names}

    def find(name):
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    def union(a, b):
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    uncertain = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            score = match_score(a, b)
            if score >= 1.0:
                union(a, b)
            elif score >= threshold:
                union(a, b)
                uncertain.append((a, b, score))

    groups = {}
    for name in names:
        groups.setdefault(find(name), set()).add(name)
    return [frozenset(group) for group in groups.values()], uncertain


def cluster_certain_only(names):
    """The same grouping with every uncertain merge withheld.

    Not "no merging at all": collapsing "ACME CORP" and "Acme Corp" is a fact
    about formatting, not a judgment, and pretending otherwise would send
    every part in the data to a reviewer.
    """
    groups = {}
    for name in sorted(set(names)):
        groups.setdefault(canonical_key(name), set()).add(name)
    return [frozenset(group) for group in groups.values()]


def cluster_of(clusters, name):
    for group in clusters:
        if name in group:
            return group
    return frozenset({name})
