# The second frozen dataset: what stage 8 must exercise

Written at the close of stage 5, while the reasons are fresh, so that stage 8
inherits the requirements rather than reconstructing them from findings lists.

The primary generator stays as it is. **Nothing recorded here is a defect in it**
and nothing here should be fixed by amending it. Each item is a capability the
primary dataset structurally cannot express, discovered by building a stage and
watching a real code path never fire. The pattern by now is established: an
unexercised path is a finding, and the right response is a second frozen
scenario rather than reshaping the primary generator around the code that
consumes it.

The precedent is the empty merge lane at stage 3. Engineering a supplier pair to
land between 0.95 and 1.0 would have inverted the derivation, because the
threshold comes from the floors and fitting data to the threshold makes the
number a consequence of the case built to justify it. The same logic applies to
everything below: these belong in a **separate, deliberately harder scenario**,
frozen with its own manifest, never in the dataset that produces the shipped
measurements.

## Why a second dataset rather than a harder primary one

The primary dataset has a job: to be a realistic, moderately messy world against
which the shipped floors and thresholds are measured. Making it adversarial
would change what those numbers mean. A precision figure measured on a dataset
built to break the normaliser is not the precision anybody would see.

So the second dataset is explicitly adversarial and its numbers are never
promoted into shipped floors. It answers a different question: **does the
machinery fire at all when the world is hard enough to need it?**

## 1. A harder supplier-name distribution

**What is unexercised.** The merge-uncertain exception lane. At the shipped
0.95 threshold the normaliser resolves every name pair in the primary dataset,
so the lane is empty and the dual-reading merge path never runs on generated
data. Coverage today is unit tests plus a golden pinned at 0.90.

**What the scenario needs.** Name pairs that genuinely sit in the uncertain band
at 0.95, produced by a mechanism rather than by hand-picking two strings:

- longer multi-word supplier names, where a single differing token moves the
  similarity ratio less than it does in a two-word name
- shared prefixes and suffixes across genuinely distinct companies, which is how
  real supplier masters look once holding companies and regional subsidiaries
  are in them
- at least one pair of genuinely distinct suppliers scoring above 0.95, so that
  precision can actually fail and the floor is doing work rather than being
  trivially satisfied

**What it must prove.** That the merge lane fires, that a phantom single source
is caught rather than merged, and that the precision floor is a live constraint
on this data rather than a satisfied-by-construction one.

## 2. Multinational suppliers

**What is unexercised.** The `supplier_only` agreement class, and with it the
argument for computing supplier grouping separately from region grouping at all.

**Why it is structural.** The primary generator gives every supplier exactly one
region. A supplier cluster is therefore always inside one region, so a
concentrated supplier cluster always implies a concentrated region cluster and
`supplier_only` cannot occur. This is not a rare case that seed 42 happened to
miss; it is unreachable.

**What the scenario needs.** Suppliers with plants in more than one region: one
`supplier_id` appearing with different `supplier_region` values across its
part rows. That is the ordinary shape of a real supplier master and the primary
generator's one-region-per-supplier model is the simplification.

**What it must prove.** That `supplier_only` occurs; that a company failing as a
company is visible when no region grouping would see it; and therefore that the
two readings are genuinely complementary on real data and not only in the
hand-authored fixture.

## 3. Uncertain merges that reach the clusters

**What is unexercised.** `LOWER_BOUND` and contingent clusters on generated
data. Both depend on an unresolved merge, and at 0.95 nothing merges
uncertainly, so no cluster in the primary dataset is bounded or contingent. This
is the same root cause as item 1 rather than an independent finding, but it
needs stating separately because it exercises different code: the membership
comparison across the two clusterings, and the rule that contingency is detected
on the correlation rather than on the cluster key.

**What the scenario needs.** The harder names from item 1, arranged so that the
uncertain pairs actually fall on **exposed** parts that share suppliers. An
uncertain merge between two suppliers who each serve one multi-source part
changes no cluster and proves nothing.

**What it must prove.** That a cluster's membership is reported as a lower bound
when a merge would enlarge it; that a correlation existing only under the merged
reading is routed rather than asserted; and that both vanish when the threshold
is raised, which is what shows the uncertainty comes from the merge and not from
the clustering code.

## 4. What the scenario must NOT do

- **It must not become the dataset the floors are measured on.** Its numbers are
  diagnostic, never promoted.
- **It must not be tuned to the shipped threshold.** If a case is constructed to
  sit at 0.951 because 0.95 is the current value, the case dies the next time
  the floors move the threshold, and it was never testing the normaliser.
- **It must not replace the hand-authored fixtures.** Those remain the
  independent oracle; a generated scenario grades machinery, not arithmetic.

## Freezing

Same discipline as the primary eval set: generated once from a documented seed,
frozen with its own SHA-256 manifest, and its answer key frozen with it. It is a
second scenario alongside the first, not a version of it, so both run in the
gate and neither supersedes the other.
