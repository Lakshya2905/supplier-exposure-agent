"""BOM explosion: quantity and depth per finished good.

Returns one row per (finished good, part). It does NOT aggregate across
finished goods, and there is deliberately no rollup function here. Summing
`qty_per_finished_good` across finished goods produces an unlabelled scalar
with no unit, and the obvious next thing anyone would do with it is divide
on-hand by it to get buffer cover, which would be wrong: annual usage needs the
demand plan, and it carries the partial-demand upper-bound rule. That belongs in
stage 4 as `annual_usage(rows, demand_plan)` returning a value AND a
completeness flag. Keying the rows is offered here; summing them is not.

ARITHMETIC. Quantities are `Fraction`. They multiply down three levels then sum
across branches for common parts, and `Fraction` is exact under both. Floats
would give 11.999999999999998 against a hand-computed 12, and the moment the
fixture needs a tolerance it has stopped being an oracle. `Fraction(11, 1) == 11`
is True, so assertions stay literal integers. Rounding happens at display only,
never in this module.

Every quantity today is a whole number, so this looks like overkill until stage
1's known gap closes and 0.5 metres of extrusion arrives. Then it is the
difference between working and a silent rewrite.

ONE RETURN SHAPE. No damage knob touches BOM structure, so there is no missing
edge or unresolvable parent to model and explosion never returns "cannot tell".
That is a property of the data being structurally complete, enforced by
`tests/test_structural_completeness.py`, not a property of this code being
clever. Given a malformed BOM it raises rather than answering partially.
"""
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction


class StructuralError(ValueError):
    """The BOM is not the shape explosion is entitled to assume."""


class CycleError(StructuralError):
    """A part is its own ancestor. Raised rather than recursed into."""


@dataclass(frozen=True)
class ExplodedPart:
    finished_good: str
    part_number: str
    qty_per_finished_good: Fraction
    depths: frozenset

    @property
    def min_depth(self):
        return min(self.depths)

    @property
    def max_depth(self):
        return max(self.depths)

    @property
    def spans_depths(self):
        """True when this part sits at more than one depth under this finished
        good. Depth belongs to the path, not to the part."""
        return len(self.depths) > 1


def finished_goods(edges):
    """Roots: parts that are a parent and never a child.

    Derived from BOM structure alone, deliberately NOT from demand_plan.csv. A
    finished good absent from the demand plan is still a finished good; that is
    precisely the case stage 4 has to reason about.
    """
    parents = {parent for parent, _, _ in edges}
    children = {child for _, child, _ in edges}
    return sorted(parents - children)


def validate(edges, known_parts):
    """Refuse a BOM that names a part nobody has a record of.

    Raising is not an "unknown" result. Explosion still has exactly one return
    shape; it simply declines to answer about a structure it cannot trust.
    """
    unknown = set()
    for parent, child, _ in edges:
        for part in (parent, child):
            if part not in known_parts:
                unknown.add(part)
    if unknown:
        raise StructuralError(
            f"{len(unknown)} part(s) appear in the BOM but not in the part "
            f"master: {sorted(unknown)[:5]}")


def _edges_by_parent(edges):
    grouped = defaultdict(list)
    for parent, child, qty in edges:
        grouped[parent].append((child, Fraction(qty)))
    return grouped


def _merge(into, part, qty, depths):
    existing_qty, existing_depths = into.get(part, (Fraction(0), frozenset()))
    into[part] = (existing_qty + qty, existing_depths | depths)


def _subtree(node, by_parent, memo, stack):
    """Quantities and depths of everything under `node`, RELATIVE to `node`.

    Memoised, which is safe because a subtree is path-independent when its
    depths are relative. Storing an absolute depth per part instead is the bug
    the hand-authored fixture exists to catch: LEAF-T01 sits at depth 1 and
    depth 2 under the same finished good, and neither is more correct.
    """
    if node in stack:
        cycle = " -> ".join(stack[stack.index(node):] + [node])
        raise CycleError(f"cycle in the BOM: {cycle}")
    if node in memo:
        return memo[node]

    stack.append(node)
    result = {}
    for child, qty in by_parent.get(node, []):
        _merge(result, child, qty, frozenset({1}))
        for part, (child_qty, child_depths) in _subtree(
                child, by_parent, memo, stack).items():
            _merge(result, part, qty * child_qty,
                   frozenset({d + 1 for d in child_depths}))
    stack.pop()

    memo[node] = result
    return result


def explode(edges, known_parts=None):
    """One row per (finished good, part). Never aggregated."""
    if known_parts is not None:
        validate(edges, known_parts)

    by_parent = _edges_by_parent(edges)
    memo = {}
    rows = []
    for finished_good in finished_goods(edges):
        subtree = _subtree(finished_good, by_parent, memo, [])
        for part, (qty, depths) in sorted(subtree.items()):
            rows.append(ExplodedPart(
                finished_good=finished_good,
                part_number=part,
                qty_per_finished_good=qty,
                depths=depths,
            ))
    return rows


def rows_by_part(rows):
    """Index the rows by part, KEEPING them per finished good.

    Deliberately not a sum. Every value is a tuple of per-finished-good rows,
    so a caller that wants a total has to decide what unit it is in and say so,
    which is stage 4's job and comes with the demand plan attached.
    """
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.part_number].append(row)
    return {part: tuple(sorted(group, key=lambda r: r.finished_good))
            for part, group in grouped.items()}


def blocking_finished_goods(rows, part_number):
    """Which finished goods this part can stop. Labels, not a count."""
    return {row.finished_good for row in rows if row.part_number == part_number}
